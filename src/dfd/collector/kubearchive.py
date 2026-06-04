"""KubeArchive API client — fetches PipelineRuns, TaskRuns, and pod logs."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from dfd.common.config import PipelineTypeConfig
from dfd.common.models import PipelineRunMetadata, PipelineRunRecord, RunStatus

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=30, read=120, write=30, pool=30)


class KubeArchiveClient:
    """Queries the KubeArchive API for Tekton PipelineRuns, TaskRuns, and pod logs."""

    def __init__(self, base_url: str, token: str, verify_tls: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
            verify=verify_tls,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Pre-flight
    # ------------------------------------------------------------------

    def check_access(self, namespace: str) -> bool:
        """Verify KubeArchive is reachable and the token is valid for a namespace."""
        url = (
            f"{self.base_url}/apis/tekton.dev/v1/namespaces/"
            f"{namespace}/pipelineruns?limit=1"
        )
        try:
            resp = self._client.get(url)
            if resp.status_code in (401, 403):
                logger.error(
                    "KubeArchive returned %d for namespace %s — token is expired or invalid",
                    resp.status_code,
                    namespace,
                )
                return False
            if resp.status_code != 200:
                logger.warning(
                    "KubeArchive returned HTTP %d for namespace %s (expected 200)",
                    resp.status_code,
                    namespace,
                )
            return True
        except httpx.HTTPError as e:
            logger.error("KubeArchive connection failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Fetch PipelineRuns
    # ------------------------------------------------------------------

    def fetch_pipeline_runs(
        self, pipeline_type: PipelineTypeConfig, hours_back: int
    ) -> list[PipelineRunRecord]:
        """Fetch PipelineRuns for a pipeline type within the time window.

        Paginates through all results using the continue token so runs
        are never silently dropped when the count exceeds a single page.
        Stops early once an entire page of results falls before the cutoff.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        namespace = pipeline_type.namespace
        base_url = (
            f"{self.base_url}/apis/tekton.dev/v1/namespaces/"
            f"{namespace}/pipelineruns"
            f"?labelSelector={pipeline_type.label_selector}"
        )

        logger.info("[%s] Fetching pipelineruns from KubeArchive...", pipeline_type.display_name)

        all_items: list[dict] = []
        url = base_url
        page = 0
        while True:
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            all_items.extend(items)
            page += 1

            cont = data.get("metadata", {}).get("continue")
            if not cont:
                break

            if _all_items_before_cutoff(items, cutoff):
                break

            url = f"{base_url}&continue={cont}"

        if page > 1:
            logger.info("[%s] Fetched %d items across %d pages", pipeline_type.display_name, len(all_items), page)

        runs: list[PipelineRunRecord] = []
        stats = {"total": 0, "succeeded": 0, "failed": 0, "aborted": 0}

        for item in all_items:
            name = item["metadata"]["name"]

            ct_str = item.get("status", {}).get("completionTime", "")
            if not ct_str:
                continue

            ct = _parse_timestamp(ct_str)
            if ct is None or ct < cutoff:
                continue

            status = _extract_status(item)
            if status is None:
                continue

            stats["total"] += 1
            stats[status.value] += 1

            labels = item["metadata"].get("labels", {})
            annotations = item["metadata"].get("annotations", {})

            runs.append(
                PipelineRunRecord(
                    id=name,
                    pipeline_type_id=pipeline_type.id,
                    completion_time=ct,
                    status=status,
                    namespace=namespace,
                    package_name=_extract_package_name(labels, annotations),
                    package_version=_extract_package_version(labels, annotations),
                    target_os=_extract_target_os(labels, annotations),
                    event_type=(
                        labels.get("pac.test.appstudio.openshift.io/event-type") or None
                    ),
                    git_org=(
                        labels.get("pac.test.appstudio.openshift.io/url-org") or None
                    ),
                    git_repo=(
                        labels.get("pac.test.appstudio.openshift.io/url-repository") or None
                    ),
                    source_url=_extract_source_url(labels, annotations),
                    pipeline_url=_extract_pipeline_url(labels, annotations),
                )
            )

        logger.info(
            "[%s] Total: %d, Succeeded: %d, Failed: %d, Aborted: %d",
            pipeline_type.display_name,
            stats["total"],
            stats["succeeded"],
            stats["failed"],
            stats["aborted"],
        )
        return runs

    def fetch_pipelinerun_json(
        self, pipeline_run_id: str, namespace: str,
    ) -> dict | None:
        """Fetch the full PipelineRun CR JSON."""
        ns = namespace
        url = (
            f"{self.base_url}/apis/tekton.dev/v1/namespaces/"
            f"{ns}/pipelineruns/{pipeline_run_id}"
        )
        try:
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(
                "Failed to fetch PipelineRun %s: HTTP %d",
                pipeline_run_id,
                resp.status_code,
            )
            return None
        except httpx.HTTPError as e:
            logger.warning("Error fetching PipelineRun %s: %s", pipeline_run_id, e)
            return None

    # ------------------------------------------------------------------
    # Fetch TaskRuns + extract metadata for a failed PipelineRun
    # ------------------------------------------------------------------

    def fetch_taskruns_json(
        self, pipeline_run_id: str, namespace: str,
    ) -> dict:
        """Fetch raw TaskRun resources for a PipelineRun."""
        ns = namespace
        url = (
            f"{self.base_url}/apis/tekton.dev/v1/namespaces/"
            f"{ns}/taskruns"
            f"?labelSelector=tekton.dev/pipelineRun={pipeline_run_id}"
        )
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    def extract_metadata(
        self, pipeline_run_id: str, pipeline_type_id: str, taskruns_data: dict
    ) -> PipelineRunMetadata:
        """Extract failure metadata from TaskRun data."""
        result = PipelineRunMetadata(
            pipelinerun=pipeline_run_id, pipeline_type=pipeline_type_id
        )

        for tr in taskruns_data.get("items", []):
            task = tr["metadata"].get("labels", {}).get("tekton.dev/pipelineTask", "?")

            for c in tr.get("status", {}).get("conditions", []):
                if c.get("type") == "Succeeded" and c.get("status") == "False":
                    result.failed_task = task
                    result.pod_name = tr.get("status", {}).get("podName", "")
                    result.completion_time = tr.get("status", {}).get("completionTime", "")
                    result.condition_message = (c.get("message", "") or "")[:300]

                    for s in tr.get("status", {}).get("steps", []):
                        t = s.get("terminated", {})
                        if t.get("exitCode", 0) != 0:
                            result.failed_step = s["name"]
                            break

                    if result.failed_step:
                        break

        return result

    # ------------------------------------------------------------------
    # Fetch pod log for the failed step
    # ------------------------------------------------------------------

    def fetch_failed_step_log(
        self,
        pod_name: str,
        step_name: str,
        namespace: str,
        tail_lines: int = 500,
    ) -> str | None:
        """Fetch pod log for a specific step container from KubeArchive."""
        if not pod_name or not step_name:
            return None

        ns = namespace
        url = (
            f"{self.base_url}/api/v1/namespaces/"
            f"{ns}/pods/{pod_name}/log"
            f"?container=step-{step_name}&tailLines={tail_lines}"
        )

        try:
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning(
                "Failed to fetch log for %s/step-%s: HTTP %d",
                pod_name,
                step_name,
                resp.status_code,
            )
            return None
        except httpx.HTTPError as e:
            logger.warning("Error fetching log for %s/step-%s: %s", pod_name, step_name, e)
            return None


# ============================================================================
# Helpers
# ============================================================================


def _all_items_before_cutoff(items: list[dict], cutoff: datetime) -> bool:
    """Return True if every item on the page completed before the cutoff."""
    found_any = False
    for item in items:
        ct_str = item.get("status", {}).get("completionTime", "")
        if not ct_str:
            continue
        ct = _parse_timestamp(ct_str)
        if ct is None:
            continue
        found_any = True
        if ct >= cutoff:
            return False
    return found_any


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse a Kubernetes ISO 8601 timestamp into a timezone-aware datetime."""
    ts_clean = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_clean)
    except ValueError:
        ts_clean = ts_clean.split(".")[0] + "+00:00"
        try:
            return datetime.fromisoformat(ts_clean)
        except ValueError:
            logger.warning("Could not parse timestamp: %s", ts)
            return None


def _extract_status(item: dict) -> RunStatus | None:
    """Extract run status from PipelineRun conditions."""
    for c in item.get("status", {}).get("conditions", []):
        if c.get("type") == "Succeeded":
            if c["status"] == "True":
                return RunStatus.SUCCEEDED
            elif c.get("reason") in ("Cancelled", "StoppedRunFinally"):
                return RunStatus.ABORTED
            else:
                return RunStatus.FAILED
    return None


def _parse_sha_title(labels: dict, annotations: dict) -> tuple[str | None, str | None]:
    """Parse package name and version from the sha-title annotation.

    Handles:
      "Automatic build deltalake==1.6.0"  → ("deltalake", "1.6.0")
      "Onboard package pymilvus"          → ("pymilvus", None)
      "chore(deps): update dependency pydantic-core to v2.47.0"
                                          → ("pydantic-core", "2.47.0")
    """
    sha_title = (
        annotations.get("pipelinesascode.tekton.dev/sha-title")
        or annotations.get("pac.test.appstudio.openshift.io/sha-title")
        or ""
    ).split("\n")[0].strip()

    if not sha_title:
        return None, None

    if sha_title.startswith("Automatic build "):
        rest = sha_title.removeprefix("Automatic build ")
        if "==" in rest:
            name, _, version = rest.partition("==")
            return name.strip(), version.strip() or None
        return rest.strip(), None

    m = re.match(r"[Oo]nboard\s+(?:package\s+)?(\S+)", sha_title)
    if m:
        return m.group(1).strip(), None

    m = re.match(r"(?:chore\(deps\): )?[Uu]pdate dependency (.+) to v(.+)", sha_title)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return None, None


def _extract_package_name(labels: dict, annotations: dict) -> str | None:
    """Extract the Python package name from sha-title annotation."""
    name, _ = _parse_sha_title(labels, annotations)
    return name


def _extract_package_version(labels: dict, annotations: dict) -> str | None:
    """Extract the Python package version from sha-title annotation."""
    _, version = _parse_sha_title(labels, annotations)
    return version


def _extract_source_url(labels: dict, annotations: dict) -> str | None:
    """Build a GitHub PR or commit URL from PipelineRun annotations."""
    repo_url = (
        annotations.get("pac.test.appstudio.openshift.io/repo-url")
        or annotations.get("pipelinesascode.tekton.dev/repo-url")
        or ""
    )
    pr_number = (
        annotations.get("pac.test.appstudio.openshift.io/pull-request")
        or annotations.get("pipelinesascode.tekton.dev/pull-request")
        or ""
    )
    if repo_url and pr_number:
        return f"{repo_url.rstrip('/')}/pull/{pr_number}"
    return (
        annotations.get("pac.test.appstudio.openshift.io/sha-url")
        or annotations.get("pipelinesascode.tekton.dev/sha-url")
        or None
    )


def _extract_pipeline_url(labels: dict, annotations: dict) -> str | None:
    """Extract the Konflux UI link for this pipeline run."""
    return (
        annotations.get("pac.test.appstudio.openshift.io/log-url")
        or annotations.get("pipelinesascode.tekton.dev/log-url")
        or None
    )


def _extract_target_os(labels: dict, annotations: dict) -> str | None:
    """Extract the target OS for integration test runs.

    Derived from the test scenario label, e.g. 'wheel-check-ubuntu' -> 'ubuntu'.
    """
    scenario = labels.get("test.appstudio.openshift.io/scenario", "")
    if scenario.startswith("wheel-check-"):
        return scenario.removeprefix("wheel-check-")
    return None
