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
| Docker Hub | — | **Decision 2026-11-10 (Path B, #49): not adopted.** Baseline at decision time: Hub API 404 for `fair-bioheaders/*`, `fairbioheaders/*` and both namespace accounts; pushing secrets were never configured; the workflow's never-executed Docker Hub branch has been removed |

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

## 2. The Docker Hub decision — CLOSED: dropped (2026-10-24), retired in code (2026-11-10)

**Decision ([Adam, 2026-10-24](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/49#issuecomment-6388051029),
acknowledged by David):** Docker Hub is **not** a distribution channel for this
toolkit; the issue's acceptance criteria were amended then and there — the
image requirement is met by GHCR, with BioContainers (built from the Bioconda
recipe) serving the Nextflow modules and Galaxy wrappers. On 2026-11-10 the
maintainers confirmed implementing that decision in code: the secrets-gated
Docker Hub push in `container.yml` — which had **never executed**, because no
secrets were ever configured — has been removed, not merely left dormant.

**If this is ever revisited:** §4 keeps the exact steps that were prepared for
publication, so no re-investigation would be needed. Until a maintainer
reopens the decision, do not set `DOCKERHUB_*` secrets expecting the workflow
to honour them — the wiring no longer exists.

## 3. Secrets and variables formerly consumed by `container.yml`

Names only — never record or echo values anywhere. **As of the Path B decision
(§2), `container.yml` no longer references any of these** — the table records
what the removed Docker Hub gate used, so a future reopening starts from here.

| Kind | Name | Was consumed by (removed 2026-11-10) |
|---|---|---|
| Repository **secret** | `DOCKERHUB_USERNAME` | a `docker/login-action` step guarded by `if: env.DOCKERHUB_USERNAME != '' && env.DOCKERHUB_TOKEN != ''` — never true |
| Repository **secret** | `DOCKERHUB_TOKEN` | same login step |
| Repository **variable** | `DOCKERHUB_NAMESPACE` | the "Choose the image names" conditional, which now always yields GHCR |

Verified 2026-11-10 (`gh api repos/…/actions/secrets|variables`, names only):
all three were unset at repository scope — so no credential is orphaned by the
removal. Org-level Actions secrets could not be
listed with the audit credential (requires `admin:org`), but with the workflow
references gone an inherited secret would be inert either way.

## 4. Path A — publish to Docker Hub (NOT adopted — retained for reference)

Reopening this path means reversing the §2 decision **and restoring the
workflow wiring removed in 2026-11-10** (git history of
`.github/workflows/container.yml` has the exact diff) — the steps below
assume that restoration.

1. **Create the Hub side** (account action, outside GitHub): an organisation
   or user for `<DOCKERHUB_NAMESPACE>`; for an automation token, a service
   account with **Read & Write** on the namespace.
2. **Configure the repository** (names from §3):
   ```bash
   gh secret set DOCKERHUB_USERNAME --repo FAIR-bioHeaders/FAIR-bioHeaders-Tools   # paste value at the prompt
   gh secret set DOCKERHUB_TOKEN   --repo FAIR-bioHeaders/FAIR-bioHeaders-Tools
   gh variable set DOCKERHUB_NAMESPACE --repo FAIR-bioHeaders/FAIR-bioHeaders-Tools --body '<DOCKERHUB_NAMESPACE>'
   ```
3. **Publish the backlog and test the wiring** without waiting for a release:
   run the **Container image** workflow (`gh workflow run "Container image"
   --repo FAIR-bioHeaders/FAIR-bioHeaders-Tools -f tag=v0.9.0`). The run log
   must show the `docker.io/...` name in "Choose the image names" instead of
   the `::notice:: … pushing to GHCR only` line. Re-publishing an older tag
   does not move `latest` (the workflow checks which tag is newest).
4. **Make the repository public on Docker Hub** if the namespace's default
   visibility is private — the anonymous smoke test below is the check.
5. **Verify the published artifact** with §6 for every pushed tag, and record
   the summary block in the release thread or #49.
6. **Documentation follow-up**: once a Hub tag is verified, replace the
   `<DOCKERHUB_NAMESPACE>` placeholder in this file and in the README
   "Container image" section with the verified coordinates.

## 5. Path B — keep GHCR + BioContainers, amend acceptance (ADOPTED 2026-11-10)

The maintainer chose this path on 2026-11-10. What it comprises:

- `.github/workflows/container.yml`: drop the `DOCKERHUB_*` env entries, the
  "Choose the image names" conditional (leaving `images=ghcr.io/fair-bioheaders/fair-bioheaders`),
  the guarded `docker/login-action` Docker Hub step, and the Docker Hub
  paragraph in the header comment.
- `README.md`: state GHCR (+ BioContainers for Nextflow/Galaxy) as the only
  container channels; remove the "once the maintainers add the Docker Hub
  secrets" bullet and the Docker Hub paragraph under "Releasing the image".
- This `docs/DISTRIBUTION.md`: §2 records the decision, Path A sections are
  struck.
- #49: close with acceptance amended to "public image verified against GHCR"
  (the §6 evidence satisfies it).

The workflow and README items are implemented on the branch that carries
this runbook; #49 closure follows their merge.

## 6. Smoke test a published image (any registry, any tag)

From a checkout of this repository (uses `examples/`):

```bash
scripts/smoke_container_image.sh ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0 0.9.0
# any other public image (same script, e.g. BioContainers):
scripts/smoke_container_image.sh quay.io/biocontainers/fair-bioheaders:0.9.0--pyhdfd78af_0 0.9.0
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

## 7. Results record

| Date | Image | Tag digest | Platforms run | Checks | Evidence |
|---|---|---|---|---|---|
| 2026-11-10 | `ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0` | index `sha256:406347c2…91fe57` | linux/amd64, linux/arm64 | full battery, PASS | `scripts/smoke_container_image.sh` run on Apple-silicon (arm64) host with amd64 emulation; summary in the #49 preparation notes |
| — | Docker Hub | — | — | **n/a — Path B adopted 2026-11-10 (§2)** | — |
