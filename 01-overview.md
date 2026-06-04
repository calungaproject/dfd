# Red Hat Trusted Libraries (Calunga) — System Overview

## What Is It?

Red Hat Trusted Libraries (RHTL), codenamed **Calunga**, is a system for building, verifying,
and distributing **Python wheels compiled from source** in a trusted build environment. It is
Red Hat's answer to Chainguard's Trusted Libraries — providing a curated PyPI-compatible index
at `packages.redhat.com/trusted-libraries/python/` where every wheel is:

- Built from source (not downloaded pre-built from PyPI)
- Built using [Fromager](https://github.com/python-wheel-build/fromager) inside a controlled [manylinux_2_28 builder image](https://github.com/calungaproject/plumbing/blob/main/builder/Containerfile)
- Built in Konflux CI with full SLSA provenance and supply-chain attestations
- Verified by Enterprise Contract policy before release
- Integration-tested on UBI8, UBI9, UBI10, Fedora 43, Hummingbird, and Ubuntu 24.04
- Published to a Pulp-backed PyPI repository with PEP 740 attestations and embedded SBOMs

## Two Repositories, One Pipeline

| Repository | Purpose | GitHub |
|---|---|---|
| **index** | Package registry — declares *what* to build (1035+ packages, each a JSON file with a version pin) | [`calungaproject/index`](https://github.com/calungaproject/index) |
| **plumbing** | Build infrastructure — declares *how* to build (builder image, Tekton tasks/pipelines, utils image) | [`calungaproject/plumbing`](https://github.com/calungaproject/plumbing) |

## End-to-End Flow (30-second version)

```
1. New package version detected on PyPI (GitHub Action cron, every 12h)
         ↓
2. Auto-PR created in `index` repo updating the package's JSON version
         ↓
3. PR triggers Konflux build pipeline (PipelinesAsCode)
   → identify-packages: diffs git to find changed packages
   → build-wheels: Fromager builds wheels from source inside builder image
   → security scans: Snyk, Coverity, ClamAV, shell-check, unicode-check
         ↓
4. PR merges (auto-merge enabled)
         ↓
5. Push event triggers same pipeline (this time comparing HEAD^ for packages)
         ↓
6. Snapshot created → Integration tests run on 6+ OS images
   (install wheel, import every module, verify it works)
         ↓
7. Enterprise Contract validation (Red Hat policy)
         ↓
8. Auto-release to release engineering tenant → Pulp repository
   (packages.redhat.com/trusted-libraries/python/)
```

## Key Artifacts Produced by Plumbing

| Artifact | Image | Type |
|---|---|---|
| Builder image | `quay.io/…/plumbing-builder` | Container image (UBI8-based manylinux, CPython 3.12, Rust, OpenBLAS, 20+ source-built libs) |
| Wheel build task | `quay.io/…/task-build-python-wheels` | Tekton Bundle (OCI artifact containing the `build-python-wheels-oci-ta` Task) |
| Integration test pipeline | `quay.io/…/plumbing-pipelines` | Tekton Bundle (wheel-integration-test Pipeline) |
| Utils image | `quay.io/…/plumbing-utils` | Container image (twine, PEP 740 converter, Pulp publishing) |
| Config task | `quay.io/…/task-get-config` | Tekton Bundle |

## How Users Consume It

```bash
# pip
pip install numpy --index-url https://<user>:<token>@packages.redhat.com/trusted-libraries/python/

# uv (pyproject.toml)
[[tool.uv.index]]
name = "trusted-libraries"
url = "https://packages.redhat.com/trusted-libraries/python"
default = true
```

Wheels include embedded SBOMs at `<pkg>.dist-info/sboms/redhat.spdx.json`.

## Current Support Matrix

- **Python**: 3.12 (3.11, 3.13, 3.14 planned)
- **Architecture**: x86_64 (aarch64 planned)
- **Manylinux**: manylinux_2_28
- **Packages**: 1035+ onboarded
