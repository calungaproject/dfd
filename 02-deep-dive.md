# Red Hat Trusted Libraries — Deep Dive

## 1. Index Repository ([`calungaproject/index`](https://github.com/calungaproject/index))

### 1.1 Package Registry

The `onboarded_packages/` directory contains **1035+ JSON files**, one per Python package.
Each file declares the version to build and a list of ignored (older) versions:

```json
// onboarded_packages/numpy.json
{
    "version": "2.4.6",
    "ignored_versions": ["1.0", "1.1.1", ..., "2.4.3"]
}
```

- `version` — the version that should exist in the Trusted Libraries index
- `ignored_versions` — all other known PyPI versions that should NOT be built

### 1.2 Automated Version Detection (GitHub Actions)

A GitHub Actions workflow ([`get_new_package_versions.yml`](https://github.com/calungaproject/index/blob/main/.github/workflows/get_new_package_versions.yml)) runs **every 12 hours** and on
manual trigger:

**Job 1: `check-for-updates`** — runs [`hack/check-for-updates.py`](https://github.com/calungaproject/index/blob/main/hack/check-for-updates.py):
1. Loads all 1035+ package JSON files
2. Queries PyPI API for all available versions of each package (async, 10 concurrent)
3. Queries Pulp API (packages.redhat.com) for already-published versions (async, 10 concurrent)
4. Computes: `versions_to_build = pypi_versions - pulp_versions - ignored_versions`
5. Outputs the list as a JSON array (e.g., `["urllib3==2.5.1", "numpy==2.4.7"]`)

**Job 2: `create-prs`** — for each update, runs [`hack/replace-package`](https://github.com/calungaproject/index/blob/main/hack/replace-package):
1. Updates the package JSON file with `jq` to set the new version
2. Creates a PR titled "Automatic build numpy==2.4.7"
3. Enables auto-merge (rebase strategy)

### 1.3 Manual Onboarding

New packages are added via [`hack/onboard_package.py`](https://github.com/calungaproject/index/blob/main/hack/onboard_package.py):
1. Queries PyPI for all versions
2. Finds the latest non-yanked semver version
3. Creates `onboarded_packages/<name>.json` with that version and all others as ignored

### 1.4 Containerfile

The index repo's Containerfile is minimal — just `FROM ubi10/ubi:latest`. It exists primarily
as a Konflux Component requirement (every component needs a build artifact). The real output
of the index pipeline is the OCI artifact containing built wheels, not a container image.

### 1.5 Build Pipeline ([`.tekton/build-pipeline.yaml`](https://github.com/calungaproject/index/blob/main/.tekton/build-pipeline.yaml))

This is a **custom Tekton Pipeline** (not a standard Konflux pipeline). It has these tasks:

```
init → clone-repository → identify-packages → build-wheels → [security scans]
                                  ↓                  ↓
                          (git diff to find      (Fromager builds
                           changed packages)      from source)
```

**Task: `identify-packages`**
- Uses [`hack/identify-packages`](https://github.com/calungaproject/index/blob/main/hack/identify-packages) shell script
- Runs `git diff --name-only --diff-filter=AM <prev-ref> -- onboarded_packages/`
- On PRs: compares against `origin/main`
- On push: compares against `HEAD^`
- Extracts package name and version from changed JSON files
- Outputs a JSON array like `["numpy==2.4.6", "requests==2.34.2"]`
- If no packages changed, outputs `no-packages` and build-wheels is skipped

**Task: `build-wheels`**
- References `build-python-wheels-oci-ta` task from a Tekton Bundle
- Uses the plumbing builder image
- Runs Fromager to build wheels from source
- Pushes result as OCI artifact with type `application/vnd.python.wheels`
- The `when` condition skips this task if no packages changed

**Security scan tasks** (run in parallel after build-wheels):
- `sast-snyk-check` — Snyk static analysis
- `sast-coverity-check` — Coverity static analysis
- `sast-shell-check` — ShellCheck for shell scripts
- `sast-unicode-check` — Unicode/homoglyph attack detection
- `clamav-scan` — Malware scanning

### 1.6 PipelineRun Triggers

| File | Trigger | Key Differences |
|---|---|---|
| [`calunga-v2-index-main-pull-request.yaml`](https://github.com/calungaproject/index/blob/main/.tekton/calunga-v2-index-main-pull-request.yaml) | `event == "pull_request" && target_branch == "main"` | Image expires in 5d, compares against `origin/main`, cancel-in-progress |
| [`calunga-v2-index-main-push.yaml`](https://github.com/calungaproject/index/blob/main/.tekton/calunga-v2-index-main-push.yaml) | `event == "push" && target_branch == "main"` | No expiry, compares against `HEAD^`, no cancel-in-progress, supersession disabled |

Both request 20Gi memory for the `build-wheels` task (heavy compilation workload).
Push builds disable snapshot supersession (`ignore-supersession: true`) so concurrent
package builds don't skip each other's releases.

### 1.7 Release Configuration

**ReleasePlan** ([`konflux/release/releaseplan.yaml`](https://github.com/calungaproject/index/blob/main/konflux/release/releaseplan.yaml)):
```yaml
spec:
  application: calunga-v2-index-main
  releaseGracePeriodDays: 7
  target: <releng-tenant>
```
- Auto-release enabled (`auto-release: 'true'`)
- Standing attribution enabled
- Target: release engineering tenant
- Matched to `calunga-push-to-pulp-prod` ReleasePlanAdmission

**EnterpriseContractPolicy** ([`konflux/ecp.yaml`](https://github.com/calungaproject/index/blob/main/konflux/ecp.yaml)):
- Based on Red Hat's internal EC policy
- Has many exclusions (marked TODO) — the project is adapting traditional container
  image policies to work with OCI wheel artifacts
- Key exclusions: source image, base image checks, SBOM (embedded in wheel instead),
  trusted task checks (custom build task not yet certified)

**Nudge ConfigMap** — enables Renovate auto-merge for Konflux nudge PRs.

---

## 2. Plumbing Repository ([`calungaproject/plumbing`](https://github.com/calungaproject/plumbing))

### 2.1 Repository Structure

```
plumbing/
├── builder/           # Builder container image (manylinux_2_28 + CPython 3.12)
│   ├── Containerfile  # Multi-stage build with 20+ stages
│   ├── build_scripts/ # Individual library build scripts
│   ├── scripts/       # Entrypoint scripts (build-wheels, collect-build-files)
│   ├── overrides/     # Fromager settings overrides
│   └── tests/         # manylinux compliance tests
├── tasks/             # Tekton Task definitions
│   ├── build-python-wheels-oci-ta.yaml
│   ├── get-config.yaml
│   └── install-and-import-wheels.yaml
├── pipelines/         # Tekton Pipeline definitions
│   └── wheel-integration-test.yaml
├── utils/             # Utils container image (twine, PEP 740 converter)
│   ├── Containerfile
│   └── scripts/
├── tests/             # Integration test scripts
└── .tekton/           # Konflux CI PipelineRun definitions
```

### 2.2 Builder Image

The builder image is the workhorse of the system — a **UBI8-based manylinux_2_28 image**
with everything needed to compile Python wheels from source.

**Multi-stage [Containerfile](https://github.com/calungaproject/plumbing/blob/main/builder/Containerfile) (20+ stages):**

```
runtime_base_packages (UBI8 base)
  └─ runtime_base (+ autoconf, automake, libtool, libxcrypt)
       └─ build_base (+ build packages)
            ├─ build_git (curl + git from source)
            ├─ build_sqlite3
            ├─ build_tcl_tk
            ├─ build_mpdecimal
            ├─ build_zstd
            ├─ build_rust (Rust 1.95.0 via rustup)
            ├─ build_libjpeg_turbo (3.1.3)
            ├─ build_libyaml (0.2.5)
            ├─ build_libxml2 (2.15.1)
            ├─ build_libxslt (1.1.45, depends on libxml2)
            ├─ build_libffi (3.5.2)
            ├─ build_openblas (0.3.31)
            ├─ build_libomp (20.1.6)
            ├─ build_zlib (1.3.1)
            ├─ build_bzip2 (1.0.8)
            ├─ build_libpng (1.6.44)
            ├─ build_libtiff (4.6.0)
            ├─ build_openssl (3.5.4)
            └─ build_cpython312 (Python 3.12.12)
```

Each library is built from source with:
- SHA256 verification of source tarballs
- Proper pkgconfig generation
- Runtime files in `/manylinux-rootfs/` and build files in `/manylinux-buildfs/`
- Binary stripping for size reduction

**Key tools installed in the final image:**
- Fromager (dependency resolver + wheel builder)
- CPython 3.12.12 (built from source)
- Rust 1.95.0 + Cargo (for cryptography, pydantic-core, ruff, etc.)
- OpenBLAS 0.3.31 (for numpy, scipy)
- OpenSSL 3.5.4 (for cryptography, urllib3)
- All major C library dependencies pre-built

### 2.3 Tekton Tasks

**[`build-python-wheels-oci-ta`](https://github.com/calungaproject/plumbing/blob/main/tasks/build-python-wheels-oci-ta.yaml)** — The core build task:

```
Steps:
1. use-trusted-artifact   — Downloads source code from Trusted Artifact store
2. build-wheels           — Runs Fromager via the builder image entrypoint
                            Uses cache wheel server for pre-built dependencies
                            Authenticates to packages.redhat.com for wheel lookup
3. collect-build-files    — Gathers built wheels and source distributions
4. create-oci-artifact    — Pushes wheels as OCI artifact using oras
                            Artifact type: application/vnd.python.wheels
                            Tags with expiry if specified
```

**[`install-and-import-wheels`](https://github.com/calungaproject/plumbing/blob/main/tasks/install-and-import-wheels.yaml)** — Integration test task:

```
Steps:
1. get-image-urls       — Extracts container image URLs from Snapshot JSON
2. extract-wheels       — Pulls OCI artifacts and extracts .whl files using oras
3. install-and-import   — For each wheel:
   a. Classifies: empty / data-only / importable
   b. Creates fresh venv with python3.12
   c. Installs wheel from local files (--no-index)
   d. Attempts to import every detected module
   e. Reports PASS/FAIL/SKIP with detailed import errors
```

**[`get-config`](https://github.com/calungaproject/plumbing/blob/main/tasks/get-config.yaml)** — Reads a ConfigMap and exposes values as task results (used for
release pipeline configuration, e.g., OCI storage location).

### 2.4 Konflux Component Dependency Chain (Nudges)

The plumbing repo is a **monorepo with 6 Konflux Components**, and changes cascade
via Konflux's nudge system:

```
builder image changed
    → nudge updates task-build-python-wheels (new builder image ref)
        → nudge updates index pipeline (new task bundle ref)

pipelines/ changed
    → plumbing-pipelines bundle rebuilt

tasks/get-config.yaml changed
    → task-get-config bundle rebuilt
```

Each component has path-based CEL expressions for selective triggering:
- `plumbing-builder`: only on `builder/***` changes
- `task-build-python-wheels`: only on `tasks/build-python-wheels-oci-ta.yaml` changes
- `plumbing-pipelines`: only on `pipelines/***` changes

### 2.5 Utils Image

The utils image ([`utils/Containerfile`](https://github.com/calungaproject/plumbing/blob/main/utils/Containerfile)) is a UBI10-based image containing:
- Python 3, jq
- twine (for publishing to PyPI repositories)
- [`convert-dsse-to-pep740.py`](https://github.com/calungaproject/plumbing/blob/main/utils/scripts/convert-dsse-to-pep740.py) — converts DSSE attestations (from Tekton Chains)
  to PEP 740 format for Pulp compatibility

---

## 3. Konflux Cluster Configuration (project tenant namespace)

### 3.1 Applications

| Application | Purpose |
|---|---|
| `calunga-v2` | Plumbing infrastructure (builder, tasks, pipelines, utils) |
| `calunga-v2-index-main` | Package index (wheel builds + releases) |

### 3.2 Components (7 total)

| Component | App | Git Context | Builds |
|---|---|---|---|
| `calunga-v2-index-main` | index-main | `/` | Wheels (OCI artifacts) |
| `plumbing-builder` | calunga-v2 | `builder` | Container image |
| `plumbing-pipelines` | calunga-v2 | `pipelines` | Tekton Bundle |
| `plumbing-utils` | calunga-v2 | `utils` | Container image |
| `task-build-python-wheels` | calunga-v2 | `/` | Tekton Bundle |
| `task-get-config` | calunga-v2 | `/` | Tekton Bundle |
| `task-push-py-pulp` | calunga-v2 | `/` | Tekton Bundle |

### 3.3 Integration Test Scenarios (8 total)

**For `calunga-v2` (plumbing):**
- `calunga-v2-enterprise-contract` — EC validation

**For `calunga-v2-index-main` (index):**
- `calunga-v2-index-main-enterprise-contract` — EC validation with custom `calunga` policy
- `wheel-check-ubi8` — Install + import test on UBI8
- `wheel-check-ubi9` — Install + import test on UBI9
- `wheel-check-ubi10` — Install + import test on UBI10
- `wheel-check-fedora43` — Install + import test on Fedora 43
- `wheel-check-hummingbird-python-312` — Install + import test on Hummingbird Python 3.12
- `wheel-check-ubuntu` — Install + import test on Ubuntu 24.04

All wheel-check tests use the `wheel-integration-test` pipeline from plumbing, resolved
via the git resolver at runtime.

### 3.4 Release Flow (Trigger)

```
Build completes → Snapshot created
    → Integration tests pass (all 7 scenarios)
    → Enterprise Contract validates (custom calunga policy)
    → Release auto-triggered (auto-release label)
    → ReleasePlan targets release engineering tenant
    → ReleasePlanAdmission: calunga-push-to-pulp-prod
    → Release pipeline executes (see §3.5)
```

### 3.5 Release Pipeline (`calunga-push-to-pulp`)

The release pipeline lives in the [`release-service-catalog`](https://github.com/konflux-ci/release-service-catalog)
repository, managed by Red Hat's release engineering team.
It is referenced by the ReleasePlanAdmission in the release engineering tenant.

**Pipeline and task sources:**

All definitions below live in [`konflux-ci/release-service-catalog`](https://github.com/konflux-ci/release-service-catalog)
on the `development` branch (as configured in the ReleasePlanAdmission), except where noted.

| Task | Source |
|---|---|
| **Pipeline** | [`pipelines/managed/calunga-push-to-pulp/calunga-push-to-pulp.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/pipelines/managed/calunga-push-to-pulp/calunga-push-to-pulp.yaml) |
| `config` | Tekton Bundle from plumbing: `quay.io/redhat-user-workloads/<tenant>/task-get-config` (see [§2.3](02-deep-dive.md#23-tekton-tasks)) |
| `collect-data` | [`tasks/managed/collect-data/collect-data.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/collect-data/collect-data.yaml) |
| `collect-atlas-params` | [`tasks/managed/collect-tpa-params/collect-tpa-params.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/collect-tpa-params/collect-tpa-params.yaml) |
| `reduce-snapshot` | [`tasks/managed/reduce-snapshot/reduce-snapshot.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/reduce-snapshot/reduce-snapshot.yaml) |
| `verify-enterprise-contract` | [`enterprise-contract/ec-cli`](https://github.com/enterprise-contract/ec-cli) — [`tasks/verify-conforma-konflux-ta/0.1/verify-conforma-konflux-ta.yaml`](https://github.com/enterprise-contract/ec-cli/blob/main/tasks/verify-conforma-konflux-ta/0.1/verify-conforma-konflux-ta.yaml) (pinned by commit SHA) |
| `extract-py-artifacts` | [`tasks/managed/extract-py-artifacts/extract-py-artifacts.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/extract-py-artifacts/extract-py-artifacts.yaml) |
| `upload-sboms-to-atlas` | [`tasks/managed/extract-and-upload-python-wheel-sboms-to-atlas/extract-and-upload-python-wheel-sboms-to-atlas.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/extract-and-upload-python-wheel-sboms-to-atlas/extract-and-upload-python-wheel-sboms-to-atlas.yaml) |
| `rh-sign-python-wheels` | [`tasks/managed/rh-sign-python-wheels/rh-sign-python-wheels.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/rh-sign-python-wheels/rh-sign-python-wheels.yaml) |
| `push-py-pulp` | [`tasks/managed/upload-py-pulp/upload-py-pulp.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/upload-py-pulp/upload-py-pulp.yaml) |
| `create-advisory` | [`tasks/managed/create-advisory/create-advisory.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/create-advisory/create-advisory.yaml) |
| `cleanup-internal-requests` | [`tasks/managed/cleanup-internal-requests/cleanup-internal-requests.yaml`](https://github.com/konflux-ci/release-service-catalog/blob/development/tasks/managed/cleanup-internal-requests/cleanup-internal-requests.yaml) |

**Task execution flow:**

```
config ──→ collect-data ──→ reduce-snapshot ──→ verify-enterprise-contract
                │                                        │
                ├──→ collect-atlas-params                 │
                │           │                    extract-py-artifacts
                │           │                      │            │
                │           └──→ upload-sboms-to-atlas    rh-sign-python-wheels
                │                                              │
                │                                         push-py-pulp
                │                                              │
                │                                         create-advisory
                │
                └──→ [finally] cleanup-internal-requests
```

**Task-by-task breakdown:**

| # | Task | Purpose |
|---|---|---|
| 1 | `config` | Reads release pipeline ConfigMap (e.g., `ociStorage` location). Uses the `get-config` Tekton Bundle from plumbing. |
| 2 | `collect-data` | Collects Release, ReleasePlan, ReleasePlanAdmission, and Snapshot data into a shared workspace. Stores data as Trusted Artifacts. |
| 3 | `collect-atlas-params` | Gathers Atlas/TPA (Trusted Profile Analyzer) API URLs and SSO credentials for SBOM upload. |
| 4 | `reduce-snapshot` | Filters the Snapshot to relevant components (supports single-component mode). |
| 5 | `verify-enterprise-contract` | Runs EC validation using `verify-conforma` against the release policy (`registry-calunga-prod`). Strict mode, ignores Rekor. |
| 6 | `extract-py-artifacts` | Pulls OCI wheel artifacts from the Snapshot images using `oras`. Parses wheel SBOMs for `pkg:pypi` PURLs and populates release notes. Fetches Tekton Chains SLSA provenance via `cosign verify` (public key from `k8s://openshift-pipelines/public-key`). |
| 7 | `upload-sboms-to-atlas` | Extracts SBOMs embedded in wheels and uploads them to Red Hat's Atlas/TPA system for centralized SBOM management. |
| 8 | `rh-sign-python-wheels` | Signs each wheel and sdist with **AWS KMS** via cosign, producing **PEP 740 attestations**. This converts the SLSA provenance into the format that Pulp/PyPI understands. 2-hour timeout, 3 retries. |
| 9 | `push-py-pulp` | Uploads signed wheels + PEP 740 attestations to `packages.redhat.com` Pulp repository. Authenticates via `rhtl-pulp-credentials-secret`. Target domain: `public-trusted-libraries`, repository: `main`. |
| 10 | `create-advisory` | Creates a Red Hat advisory (RHSA-style) for the release, with CPE `cpe:/a:redhat:trusted_libraries:1`, product stream `rhtl-1`. |
| — | `cleanup-internal-requests` | Finally task — cleans up internal request resources regardless of pipeline success/failure. |

**Key configuration from ReleasePlanAdmission:**

- **Signing**: cosign with `hacbs-signing-pipeline-config-redhatrelease2` + `konflux-cosign-signing-production`
- **Pulp domain**: `public-trusted-libraries`
- **Service account**: `release-pulp-calunga-prod`
- **Pipeline timeouts**: 2h pipeline, 1h per task
- **Advisory metadata**: Product ID 1054, product name "Red Hat Trusted Libraries", stream `rhtl-1`

---

## 4. Security & Supply Chain

### 4.1 Build-time Security

- **Trusted Artifacts**: Source code passed between tasks as OCI artifacts (not PVCs)
- **Fromager**: Builds from source distributions, resolving dependencies automatically
- **Pinned task references**: All Tekton tasks referenced by digest (sha256)
- **Pinned base images**: Builder uses UBI8 image pinned by digest
- **Hermetic identify-packages**: The package identification step runs with network isolation
- **Wheel cache server**: Pre-built wheels looked up from authenticated packages.redhat.com

### 4.2 Verification

- **Tekton Chains**: Generates SLSA provenance attestations for every build
- **Enterprise Contract**: Validates builds against Red Hat's release policy
- **ClamAV**: Malware scanning of built artifacts
- **SAST**: Snyk + Coverity + ShellCheck + Unicode check
- **Integration tests**: Verify wheels install and import correctly on 6 OS targets

### 4.3 Distribution Security

- **Embedded SBOMs**: Each wheel contains `sboms/redhat.spdx.json` in dist-info
- **PEP 740 attestations**: DSSE attestations converted to PEP 740 for Pulp
- **Authenticated access**: packages.redhat.com requires service account credentials
- **Standing attribution**: Release authorship is consistently attributed

---

## 5. Key URLs and Registries

| What | Where |
|---|---|
| Published packages | [`packages.redhat.com/trusted-libraries/python/`](https://packages.redhat.com/trusted-libraries/python/) |
| Builder image | `quay.io/redhat-user-workloads/<tenant>/plumbing-builder` |
| Build task bundle | `quay.io/redhat-user-workloads/<tenant>/task-build-python-wheels` |
| Wheel OCI artifacts | `quay.io/redhat-user-workloads/<tenant>/calunga-v2-index-main` |
| Release artifacts | `quay.io/redhat-user-workloads/<tenant>/release-artifacts` |
| Index repo | [`github.com/calungaproject/index`](https://github.com/calungaproject/index) |
| Plumbing repo | [`github.com/calungaproject/plumbing`](https://github.com/calungaproject/plumbing) |
| Fromager | [`github.com/python-wheel-build/fromager`](https://github.com/python-wheel-build/fromager) |
| Release pipeline catalog | [`github.com/konflux-ci/release-service-catalog`](https://github.com/konflux-ci/release-service-catalog) |
| Enterprise Contract CLI | [`github.com/enterprise-contract/ec-cli`](https://github.com/enterprise-contract/ec-cli) |
