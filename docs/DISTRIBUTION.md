# Container image distribution — maintainer runbook

This page is the single reference for publishing and verifying the
fair-bioheaders container image. It records the verified registry baseline,
the decision not to publish on Docker Hub, the existing conditional workflow
configuration, and the smoke tests to run against every published artifact.
It exists for
[FAIR-bioHeaders-Tools#49](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/49);
it changes no workflow.

## 1. Where the images live (verified 2026-11-10)

| Channel | Coordinates | Verified state |
|---|---|---|
| GHCR (primary) | `ghcr.io/fair-bioheaders/fair-bioheaders` | Public; anonymous manifest fetch HTTP 200; tags `0.5.0`…`0.9.0` plus `X.Y` series aliases and `latest`; `linux/amd64` + `linux/arm64` + provenance/SBOM attestations |
| BioContainers | `quay.io/biocontainers/fair-bioheaders` | Built automatically from the Bioconda recipe; tag `0.9.0--pyhdfd78af_0` recorded 2026-11-05; this is the image the FHR-Nextflow modules and the Galaxy wrappers declare |
| Docker Hub | `docker.io/<DOCKERHUB_NAMESPACE>/fair-bioheaders` | **Not published.** Hub API returns 404 for `fair-bioheaders/*`, `fairbioheaders/*` repositories and for both namespace accounts (2026-11-10); the pushing secrets are not configured |

The release wheel is on PyPI as `fair-bioheaders` (0.9.0 at the time of
writing) and the CLI is also installable via Bioconda; neither is a container
channel but both are checked by the same release process.

### GHCR baseline (digest evidence, 2026-11-10)

Multi-arch OCI index digests; the per-platform entries are the image manifests
users get when they pull the tag. `latest`, `0.9` and `0.9.0` resolve to the
**same index digest**, so the mutable `latest` tag currently equals the newest
release (this answers the staleness concern recorded in #49).

| Tag | Index digest | linux/amd64 manifest | linux/arm64 manifest |
|---|---|---|---|
| `0.9.0` = `0.9` = `latest` | `sha256:406347c2d480bd29c764868a9aae64afd695be897932e890cebc4c712991fe57` | `sha256:1582f3b53e9827c665961ca1b9faa48f9c997aa45af0b6e55feb5a0e00afeef9` | `sha256:2a06502457a755e12b1fe2b259d6b4dad65521b7238f713a2aa019808019eacc` |
| `0.8.6` | `sha256:a0ea04d28c8a712db8791d432bbe9ed43b46311132d63ddb0e04db61f64ab169` | `sha256:c0406154ea1ea575ded1121a9b5aab287d7b37b8dbaa9c18ffa159bcd61b7996` | `sha256:c45854ff285a0b9337e67ce100ec64672c98f4316f793ff2fa3e7c305deea712` |
| `0.5.0` (first published) | `sha256:022665da4db142c9b14a6cc9db05970eb98efd93f9e0e4f3ef17dbb348a3ff87` | `sha256:adf0114a00a21468ec45425aedc126cec811b39edb20f33024c9d0a45a3db4aa` | `sha256:0c248e24b8119a51a6311332032cc967d21c3a70cd1cd7c965fba224043931d6` |

Each index additionally carries two `unknown/unknown` attestation manifests
(provenance `mode=max` + SBOM, per `container.yml`). Full tag list on 2026-11-10:
`0.5.0 0.5 0.6.0 0.6 0.7.0 0.7 0.8.0 0.8.1 0.8.2 0.8.3 0.8.4 0.8.5 0.8.6 0.9.0 0.9 latest`
(`0.8.0` confirmed present via the registry `tags/list` API).

Reproduce anytime:

```bash
curl -fsSL "https://ghcr.io/v2/fair-bioheaders/fair-bioheaders/tags/list" \
  -H "Authorization: Bearer $(curl -fsSL 'https://ghcr.io/token?scope=repository:fair-bioheaders/fair-bioheaders:pull' | sed -n 's/.*"token":"***"]*\)".*/\1/p')"
docker buildx imagetools inspect ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0
```

## 2. Docker Hub distribution decision — not publishing

The maintainers decided on 2026-10-24 not to publish on Docker Hub: GHCR and
BioContainers cover current needs, and another registry adds maintenance with
little benefit. Docker Hub is not part of issue #49's acceptance criteria.

This distribution decision is distinct from the workflow configuration:
`container.yml` still has a secret-gated Docker Hub push, and `release.yml`
still calls it. The repository has no `fair-bioheaders` or `fairbioheaders`
Docker Hub repository (404 as of 2026-11-10), and no Docker Hub secrets or
namespace variable are set at repository scope. Do not configure or use that
push under the current decision; removing the unused workflow path requires a
separate maintainer-approved code change.

## 3. Secrets and variables consumed by `container.yml`

Names only — never record or echo values anywhere.

| Kind | Name | Consumed by | Effect when set |
|---|---|---|---|
| Repository **secret** | `DOCKERHUB_USERNAME` | `container.yml` env, `docker/login-action` (step guarded by `if: env.DOCKERHUB_USERNAME != '' && env.DOCKERHUB_TOKEN != ''`) | Enables the Docker Hub push, together with the token |
| Repository **secret** | `DOCKERHUB_TOKEN` | same login step | Docker Hub access-token password |
| Repository **variable** | `DOCKERHUB_NAMESPACE` | `container.yml` step "Choose the image names": `docker.io/${DOCKERHUB_NAMESPACE:-$DOCKERHUB_USERNAME}/fair-bioheaders` | Optional; use the organisation login (e.g. `fairbioheaders`) when the image must live under an org rather than the personal user of `DOCKERHUB_USERNAME` |

Verified 2026-11-10 (`gh api repos/…/actions/secrets|variables`, names only):
all three are unset at repository scope. Org-level Actions secrets could not be
listed with the audit credential (requires `admin:org`), so if the org ever
adds them, child-repo runs would inherit them — re-check before assuming the
gate is closed.

## 4. Workflow configuration

The current distribution decision is GHCR (and BioContainers for the
Nextflow/Galaxy integrations), but this runbook does not remove the optional
Docker Hub publishing path from the workflow. If maintainers later revise the
decision, they should update issue #49 and make a separate code change to the
workflow before configuring or publishing to another registry.

## 5. Smoke test a published image (any registry, any tag)

From a checkout of this repository (uses `examples/`):

```bash
scripts/smoke_container_image.sh ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0 0.9.0
# after a Docker Hub publication:
scripts/smoke_container_image.sh docker.io/<DOCKERHUB_NAMESPACE>/fair-bioheaders:0.9.0 0.9.0
# inspection only (no pulls), e.g. from CI or a small disk:
scripts/smoke_container_image.sh <image> 0.9.0 --check-only
```

The script (a) fetches the manifest with an isolated, empty Docker config so
caller credentials and credential helpers cannot authenticate the request,
proving public access; (b) lists the index digest and the `linux/amd64` / `linux/arm64`
manifest digests, failing if a requested platform is missing; (c) for each
platform pulls **by digest** and runs `bioheaders --version`,
`fhr-convert --version`, `bioheaders validate` + `verify` on the shipped
examples, a `combine` → `verify` round trip, and the `pyld` JSON-LD import —
the same battery as the in-workflow smoke tests; and (d) re-pulls **by tag**
and compares the resolved digest against the inspected index/manifest digest
(digest stability: the tag must not have moved between the two pulls).
It prints a `SUMMARY` block to paste into the release/#49 thread.

Manual equivalents, if preferred:

```bash
REF=ghcr.io/fair-bioheaders/fair-bioheaders
docker buildx imagetools inspect "$REF:0.9.0"          # index + per-platform digests
docker pull --platform linux/arm64 "$REF@sha256:2a06502457a755e12b1fe2b259d6b4dad65521b7238f713a2aa019808019eacc"
docker run --rm --platform linux/arm64 "$REF:0.9.0" bioheaders --version   # expect 0.9.0
docker run --rm --platform linux/amd64 "$REF:0.9.0" bioheaders --version   # expect 0.9.0
# round trip inside the container:
docker run --rm -v "$PWD/examples:/data:ro" "$REF:0.9.0" \
  sh -c 'printf ">c1\nACGT\n" > /tmp/a.fa && bioheaders combine /data/minimal.fhr.json /tmp/a.fa -o /tmp/a.fhr.fa && bioheaders verify /tmp/a.fhr.fa'
```

## 6. Results record

| Date | Image | Tag digest | Platforms run | Checks | Evidence |
|---|---|---|---|---|---|
| 2026-11-10 | `ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0` | index `sha256:406347c2…91fe57` | linux/amd64, linux/arm64 | full battery, PASS | `scripts/smoke_container_image.sh` run on Apple-silicon (arm64) host with amd64 emulation; summary in the #49 preparation notes |
| — | `docker.io/<DOCKERHUB_NAMESPACE>/fair-bioheaders:…` | — | — | **not a distribution target by maintainer decision** | — |
