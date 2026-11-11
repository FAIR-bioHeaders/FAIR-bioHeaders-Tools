#!/usr/bin/env bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Smoke-test a PUBLISHED fair-bioheaders container image.
#
# Unlike the in-workflow checks of container.yml (which test a locally built
# image before pushing), this script verifies the artifact that users actually
# pull: anonymous registry access, the multi-arch index, per-platform manifest
# digests, and a combine/verify round trip run on each architecture. Use it
# after every publication, and record the printed summary (tag, digests,
# platforms, date) in the release or issue thread. FAIR-bioHeaders-Tools#49.
#
# Requirements: docker (with buildx), python3, and, for the round-trip, the
# repository's examples/ directory (run it from the repository root, or pass
# --examples-dir). It only pulls and runs; it never pushes or logs in.
#
# Usage:
#   scripts/smoke_container_image.sh IMAGE EXPECTED_VERSION [options]
#
# Examples:
#   scripts/smoke_container_image.sh \
#     ghcr.io/fair-bioheaders/fair-bioheaders:0.9.0 0.9.0
#   scripts/smoke_container_image.sh \
#     docker.io/<DOCKERHUB_NAMESPACE>/fair-bioheaders:0.9.0 0.9.0 --platforms linux/amd64
#
# Options:
#   --platforms LIST   Space-separated platforms to run (default:
#                      "linux/amd64 linux/arm64"). Use one platform on hosts
#                      whose daemon cannot emulate the other.
#   --examples-dir DIR Directory with example.fhr.json, example.fhr.fasta and
#                      minimal.fhr.json (default: ./examples).
#   --check-only       Only inspect the registry index and digests; do not
#                      pull or run containers.
#   --keep             Keep the pulled images afterwards (default: remove).
#   -h                 Show this help.

set -euo pipefail

usage() { awk 'NR<=4 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"; }

if [ $# -lt 2 ]; then usage; exit 2; fi

IMAGE="$1"; shift
EXPECTED_VERSION="$1"; shift
PLATFORMS="linux/amd64 linux/arm64"
EXAMPLES_DIR="./examples"
CHECK_ONLY=false
KEEP=false
while [ $# -gt 0 ]; do
  case "$1" in
    --platforms) PLATFORMS="$2"; shift 2 ;;
    --examples-dir) EXAMPLES_DIR="$2"; shift 2 ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --keep) KEEP=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

IMAGE_NAME="${IMAGE%%@*}"
IMAGE_LAST_COMPONENT="${IMAGE_NAME##*/}"
IMAGE_REPOSITORY="${IMAGE_LAST_COMPONENT%%:*}"
if [ "$IMAGE_NAME" = "$IMAGE_LAST_COMPONENT" ]; then
  IMAGE_NAME="$IMAGE_REPOSITORY"
else
  IMAGE_NAME="${IMAGE_NAME%/*}/$IMAGE_REPOSITORY"
fi

fail() { echo "FAIL: $*" >&2; exit 1; }
note() { echo "  $*"; }

command -v docker >/dev/null || fail "docker is required"
command -v python3 >/dev/null || fail "python3 is required"

ANON_DOCKER_CONFIG="$(mktemp -d)" || fail "could not create isolated Docker config"
PULLED=()
cleanup() {
  if ! $KEEP; then
    for ref in ${PULLED[@]+"${PULLED[@]}"}; do docker rmi "$ref" >/dev/null 2>&1 || true; done
  fi
  rm -rf "$ANON_DOCKER_CONFIG"
}
trap cleanup EXIT

echo "== Published image smoke test"
echo "image:            $IMAGE"
echo "expected version: $EXPECTED_VERSION"
echo "platforms:        $PLATFORMS"
echo "date (UTC):       $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- 1. Anonymous, unauthenticated access to the registry --------------------
# Use an empty isolated Docker config so caller credentials and credential
# helpers cannot authenticate this request.
INDEX_JSON="$(docker --config "$ANON_DOCKER_CONFIG" buildx imagetools inspect --raw "$IMAGE" 2>/dev/null)" \
  || fail "anonymous manifest fetch of $IMAGE failed (is the package public?)"
echo
echo "== 1. Anonymous registry access: OK"

# --- 2. Multi-arch index: platform manifests and digests ---------------------
# Parse the OCI index: one "platform digest" line per non-attestation manifest
# plus the index digest reported by the registry.
PARSED="$(printf '%s' "$INDEX_JSON" | python3 -c '
import hashlib, json, sys
raw = sys.stdin.buffer.read()
index = json.loads(raw)
print("index-digest sha256:" + hashlib.sha256(raw).hexdigest())
for m in index.get("manifests", []):
    p = m.get("platform", {})
    os_, arch = p.get("os", "?"), p.get("architecture", "?")
    if os_ == "unknown":  # provenance/SBOM attestation manifest
        print("attestation %s %s" % (m["digest"], p.get("architecture") or "-"))
        continue
    print("platform %s/%s %s" % (os_, arch, m["digest"]))
')" || fail "could not parse the index of $IMAGE"
INDEX_DIGEST="$(printf '%s\n' "$PARSED" | awk '/^index-digest/{print $2}')"
[ -n "$INDEX_DIGEST" ] || fail "no index digest"
echo
echo "== 2. Index digest: $INDEX_DIGEST"
printf '%s\n' "$PARSED" | grep '^platform' | while read -r _ plat digest; do
  note "$plat  $digest"
done
for plat in $PLATFORMS; do
  have="$(printf '%s\n' "$PARSED" | awk -v p="$plat" '$1=="platform" && $2==p {n++} END{print n+0}')"
  [ "$have" -ge 1 ] || fail "index of $IMAGE has no $plat manifest"
done
note "all requested platforms are present in the index"

# Also confirm the locally computed index digest matches what the registry
# reports for the tag (digest stability of the tag itself).
REPORTED="$(docker buildx imagetools inspect "$IMAGE" 2>/dev/null \
  | awk '/^Digest:/{print $2; exit}')"
if [ -n "$REPORTED" ] && [ "$REPORTED" != "$INDEX_DIGEST" ]; then
  echo "WARN: registry reports $REPORTED for the tag; the fetched index hashes to $INDEX_DIGEST" >&2
  echo "      (normal for tags served through a redirect; per-manifest digests below are authoritative)" >&2
fi

if $CHECK_ONLY; then
  echo
  echo "== --check-only: stopping before pull/run steps. PULL/RUN NOT VERIFIED."
  exit 0
fi

[ -d "$EXAMPLES_DIR" ] || fail "examples directory not found: $EXAMPLES_DIR (run from the repo root or pass --examples-dir)"
EXAMPLES_ABS="$(cd "$EXAMPLES_DIR" && pwd)"
for f in example.fhr.json example.fhr.fasta minimal.fhr.json; do
  [ -f "$EXAMPLES_ABS/$f" ] || fail "missing $f in $EXAMPLES_ABS"
done

# --- 3. Per-platform: pull by digest, verify, run round trip -----------------
for plat in $PLATFORMS; do
  echo
  echo "== 3. Platform $plat"
  DIGEST="$(printf '%s\n' "$PARSED" | awk -v p="$plat" '$1=="platform" && $2==p {print $3; exit}')"
  REF="${IMAGE_NAME}@${DIGEST}"
  note "pulling by digest: $REF"
  docker pull --quiet --platform "$plat" "$REF" >/dev/null
  PULLED+=("$REF")
  ARCH="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$REF")"
  [ "$ARCH" = "$plat" ] || fail "$REF inspected as $ARCH, expected $plat"
  note "inspected platform: $ARCH"

  run() { docker run --rm --platform "$plat" -v "$EXAMPLES_ABS:/data:ro" "$REF" "$@"; }
  # No ENTRYPOINT is part of the contract (Nextflow runs scripts in it).
  if [ "$(run bioheaders --version)" != "$EXPECTED_VERSION" ]; then
    fail "bioheaders --version mismatch on $plat"
  fi
  note "bioheaders --version = $EXPECTED_VERSION"
  if [ "$(run fhr-convert --version)" != "$EXPECTED_VERSION" ]; then
    fail "fhr-convert --version mismatch on $plat"
  fi
  note "fhr-convert --version = $EXPECTED_VERSION"
  run bioheaders validate /data/example.fhr.json >/dev/null
  run bioheaders verify /data/example.fhr.fasta >/dev/null
  note "validate + verify of the shipped examples: OK"
  run sh -c 'printf ">c1\nACGT\n" > /tmp/a.fa \
    && bioheaders combine /data/minimal.fhr.json /tmp/a.fa -o /tmp/a.fhr.fa \
    && bioheaders verify /tmp/a.fhr.fa >/dev/null'
  note "combine -> verify round trip: OK"
  if run python -c "import pyld" >/dev/null 2>&1; then
    note "JSON-LD extra (pyld) importable"
  else
    fail "pyld not importable on $plat"
  fi
done

# --- 4. Digest stability: pulling the tag must yield the same manifest -------
echo
echo "== 4. Digest stability"
for plat in $PLATFORMS; do
  DIGEST="$(printf '%s\n' "$PARSED" | awk -v p="$plat" '$1=="platform" && $2==p {print $3; exit}')"
  docker pull --quiet --platform "$plat" "$IMAGE" >/dev/null
  PULLED+=("$IMAGE")
  REPO_DIGESTS="$(docker image inspect --format '{{join .RepoDigests "\n"}}' "$IMAGE" 2>/dev/null || true)"
  EXPECTED_REPOSITORY="${IMAGE_NAME#docker.io/}"
  TAG_RESOLVED=""
  while IFS= read -r repo_digest; do
    [ -n "$repo_digest" ] || continue
    digest_repository="${repo_digest%@*}"
    digest_repository="${digest_repository#docker.io/}"
    if [ "$digest_repository" = "$EXPECTED_REPOSITORY" ]; then
      TAG_RESOLVED="${repo_digest##*@}"
      break
    fi
  done <<< "$REPO_DIGESTS"
  # A tag pull records the repo digest it resolved to: the index digest for a
  # multi-arch tag (the usual case), or the platform manifest digest on stores
  # that skip the index. Either proves the tag is stable since step 2.
  if [ -z "$TAG_RESOLVED" ]; then
    note "$plat: no matching RepoDigest recorded for the tag pull (image store without digest pinning or repository-name mismatch); digest comparison skipped"
  elif [ "$TAG_RESOLVED" = "$INDEX_DIGEST" ] || [ "$TAG_RESOLVED" = "$DIGEST" ]; then
    note "$plat: tag resolves to $TAG_RESOLVED (matches the inspected index/manifest)"
  else
    fail "$plat: tag resolves to $TAG_RESOLVED, not inspected index $INDEX_DIGEST or $plat manifest $DIGEST"
  fi
done

echo
echo "== SUMMARY (record this in the release/issue thread)"
echo "image:        $IMAGE"
echo "index:        $INDEX_DIGEST"
printf '%s\n' "$PARSED" | grep '^platform' | sed 's/^platform /manifest: /'
echo "platforms run: $PLATFORMS"
echo "version check: $EXPECTED_VERSION (bioheaders, fhr-convert)"
echo "round trip:   combine + verify OK"
echo "result:       PASS"
