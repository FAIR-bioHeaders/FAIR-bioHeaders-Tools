# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHT conformance-vector consumer — opt-in draft evidence (gated by default).

The byte-exact ``fht-fasta`` vectors of FHT-Specification ``conformance/``
(issue #8, delivered by PR #29, merged into ``main`` as ``b9ad19a`` on
2026-11-12 with 65 vectors; the current deliberate pin is 93 at ``4ddda69``) are the
authoritative acceptance gate for this toolkit's FHT support
(FHT-Specification#9). This file is deliberately written so that turning it on
is mechanical; it copies nothing into this repository in the prep state.

Run it with BOTH:

1. ``BIOHEADERS_EXPERIMENTAL_FHT=1`` — the draft lane (docs/FHT-SELECTION-DESIGN.md);
2. ``FHT_SPECIFICATION=/path/to/FHT-Specification`` — a checkout whose
   ``conformance/manifest.json`` exists (or a sibling ``FHT-Specification``
   directory, the fallback used by ``tests/fhp_test.py``).

After actual shared FHT publication, revise these gates through the reviewed
released-consumer handoff. Draft recognition stays opt-in under V7; a suite
re-pin does not authorize default-on recognition or a released support claim.

The suite is **pinned separately from the contract** (``drafts.FHT.suite`` in
``bioheaders/schemas/bundled.json``): the checkout below is whatever revision
the operator happens to have, so ``test_suite_manifest_matches_pin`` names the
bytes this run scored and fails when they are not the pinned ones. A pass is
only quotable together with that test; a suite move is recorded by a
deliberate, dated commit, never by this file (FAIR-bioHeaders-Specification#241).

Semantics implemented below, from the suite README and manifest:

- ``expected: valid``     — ``bioheaders verify`` exits 0 and the recomputed
  SHA-512/256 of the exact bytes equals ``checksum``.
- ``expected: invalid``   — the toolkit must reject, with the failure class the
  vector declares: ``selfChecksum: broken`` is a checksum mismatch,
  ``selfChecksum: matches`` is a schema/contract rejection under an
  otherwise-consistent file, and ``selfChecksum: unreachable`` is a header the
  reader cannot even parse. Exception: a vector whose only failure is a
  ``parentLink`` verdict of ``checked-fail`` (C3) is byte- and schema-valid;
  ``verify`` passes it and ``verify-links`` reports mismatch
  (``fht-fasta-parent-mismatched``), matching the suite README exactly.
- ``parentLink`` entries  — ``bioheaders verify-links`` must report matched /
  not matched / not checked distinctly (never invent or substitute an
  identifier), exit 0 for matched and unchecked, and exit 3 for a mismatch.
"""

import gzip
import hashlib
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath

import pytest

from bioheaders import selection
from bioheaders.cli import checksum

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
SPEC = Path(os.environ.get("FHT_SPECIFICATION", ROOT.parent / "FHT-Specification"))
CONFORMANCE = SPEC / "conformance"
MANIFEST_PATH = CONFORMANCE / "manifest.json"

HAVE_VECTORS = MANIFEST_PATH.is_file()
GATE_OPEN = selection.draft_support_enabled()
SKIP_REASON = (
    "FHT conformance vectors (FHT-Specification#8) are consumed only with "
    "BIOHEADERS_EXPERIMENTAL_FHT=1 and FHT_SPECIFICATION pointing at a checkout "
    f"with conformance/manifest.json (looked in: {SPEC})"
)
if HAVE_VECTORS and not GATE_OPEN:
    SKIP_REASON = (
        "FHT conformance vectors found in "
        f"{SPEC}, but the draft lane is closed: run with {selection.DRAFT_ENV}=1"
    )

MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if HAVE_VECTORS else {}
VECTORS = [
    vector
    for vector in MANIFEST.get("vectors", [])
    if not vector.get("retired") and vector.get("format") == "fht-fasta"
]

# The suite axis, pinned apart from the contract axis (drafts.FHT and
# drafts.FHT.suite in bioheaders/schemas/bundled.json). The checkout above is
# whatever revision the operator has, so measure the bytes actually scored.
SUITE_PIN = (selection.draft_entry("FHT") or {}).get("suite") or {}
MANIFEST_SHA256 = (
    hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() if HAVE_VECTORS else None
)


def pytest_param_id(vector):
    return vector["id"]


params = [pytest.param(vector, id=vector["id"]) for vector in VECTORS]

# CI's FHT conformance job sets FHT_REQUIRE_SUITE so a missing checkout or a
# closed lane fails there instead of skipping the whole file.
if os.environ.get("FHT_REQUIRE_SUITE") and not (HAVE_VECTORS and GATE_OPEN):
    raise RuntimeError(f"FHT_REQUIRE_SUITE is set but: {SKIP_REASON}")

pytestmark = pytest.mark.skipif(not (HAVE_VECTORS and GATE_OPEN), reason=SKIP_REASON)


def vector_bytes(vector):
    data = suite_file_bytes(vector["file"])
    return gzip.decompress(data) if vector["compressed"] else data


def run(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )  # inherits BIOHEADERS_EXPERIMENTAL_FHT from the skipped-unless-open gate


def materialise(vector, tmp_path):
    """Write the vector's exact bytes under its own name (extension decides
    whether verify transparently decompresses)."""
    source = PurePosixPath(vector["file"])
    target = tmp_path / source.name
    target.write_bytes(suite_file_bytes(vector["file"]))
    return target


@lru_cache(maxsize=None)
def suite_file_bytes(relative_path):
    """Read a fixture only when its bytes match the pinned suite revision."""
    relative = PurePosixPath(relative_path)
    assert (
        relative.parts
        and not relative.is_absolute()
        and ".." not in relative.parts
        and "." not in relative.parts
    ), f"unsafe path in pinned suite manifest: {relative_path}"
    source = CONFORMANCE.joinpath(*relative.parts)
    assert source.resolve().is_relative_to(
        CONFORMANCE.resolve()
    ), f"suite path escapes conformance directory: {relative_path}"
    result = subprocess.run(
        [
            "git",
            "-C",
            str(SPEC),
            "show",
            f"{SUITE_PIN['revision']}:conformance/{relative.as_posix()}",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"could not read {relative_path} from pinned suite revision "
        f"{SUITE_PIN['revision']}: {result.stderr.decode(errors='replace')}"
    )
    actual = source.read_bytes()
    assert actual == result.stdout, (
        f"suite file {source} differs from {SUITE_PIN['repository']} "
        f"@ {SUITE_PIN['revision']}"
    )
    return actual


def declared_link_failure(vector):
    links = vector.get("parentLink") or []
    return any(link.get("result") == "checked-fail" for link in links)


@pytest.mark.parametrize("vector", params)
def test_vector_validity(vector, tmp_path):
    path = materialise(vector, tmp_path)
    result = run("verify", path)
    if vector["expected"] == "valid":
        assert result.returncode == 0, result.stderr
        assert "Checksum verified." in result.stdout
        assert checksum(vector_bytes(vector), "fasta") == vector["checksum"]
        return
    if declared_link_failure(vector):
        # C3: the file itself is byte- and schema-valid; only the recorded
        # parent checksum fails, and that is verify-links' verdict to give.
        assert result.returncode == 0, result.stderr
        return
    assert (
        result.returncode == 1
    ), f"{vector['id']} must be rejected: {result.stdout}{result.stderr}"
    outcome = result.stdout + result.stderr
    self_checksum = vector.get("selfChecksum")
    if self_checksum == "broken":
        assert "Checksum verification failed" in outcome
    elif self_checksum == "matches":
        assert "Checksum verification failed" not in outcome  # rejected as invalid
    # ``unreachable`` rejects before any checksum question arises.


@pytest.mark.parametrize("vector", params)
def test_parent_links(vector, tmp_path):
    links = vector.get("parentLink") or []
    if not links:
        pytest.skip("vector records no parent file")
    child = materialise(vector, tmp_path)
    parents = [
        materialise({"file": link["file"], "compressed": False}, tmp_path)
        for link in links
        if link.get("file")
    ]
    result = run("verify-links", child, *parents)
    outcomes = [link["result"] for link in links]
    if "checked-fail" in outcomes:
        assert result.returncode == 3, result.stdout + result.stderr
        assert "not matched (" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
    if "checked-pass" in outcomes:
        assert "matched (" in result.stdout
    if "unchecked" in outcomes:
        assert "not checked (" in result.stdout
    # The stated checksums are the record's, never a computed substitute:
    for link in links:
        assert link["statedChecksum"]  # the manifest asserts one per vector


def test_suite_manifest_matches_pin():
    """The vectors scored above must be the vectors the pin names.

    ``FHT_SPECIFICATION`` is a checkout path, not a revision: without this check a
    run would report "N/N pass" for bytes nobody recorded (the failure mode
    FAIR-bioHeaders-Specification#241 lists for the suite axis, and the reason the
    contract pin in ``drafts.FHT`` and this suite pin are separate records). This
    is a gate on the harness's own input, not an advisory freshness report about
    upstream: move the pin by a deliberate, dated commit that re-runs this file.
    """
    assert (
        SUITE_PIN
    ), "drafts.FHT.suite is not recorded in bioheaders/schemas/bundled.json"
    suite_files = {vector["file"] for vector in VECTORS} | {
        link["file"]
        for vector in VECTORS
        for link in vector.get("parentLink") or []
        if link.get("file")
    }
    for relative_path in sorted(suite_files):
        suite_file_bytes(relative_path)
    measured = MANIFEST_SHA256
    detail = (
        f"suite manifest scored from {MANIFEST_PATH}\n"
        f"  measured sha256 {measured} ({MANIFEST_PATH.stat().st_size} bytes, "
        f"{len(VECTORS)} fht-fasta vectors)\n"
        f"  pinned    sha256 {SUITE_PIN['sha256']} "
        f"({SUITE_PIN['repository']} @ {SUITE_PIN['revision']}, "
        f"{SUITE_PIN['bytes']} bytes, {SUITE_PIN['fhtFastaVectors']} vectors)\n"
        "Refresh procedure (maintainer act, never automated): re-read the manifest "
        "at a named revision, update drafts.FHT.suite revision/retrieved/sha256/"
        "bytes/fhtFastaVectors together with docs/FHT-SELECTION-DESIGN.md section 6, "
        "and re-run this file against that same revision."
    )
    # The digest is the assertion; size and vector count are checked additionally,
    # never instead. A suite can move bytes while its vector count and every
    # `expected` outcome stay identical: measured on 2026-11-15, FHGM's
    # development/conformance/manifest.json went 31f14f02 (35,269 B) at its #15 to
    # 5620f00c (36,001 B) at its #17 with 31 vectors and the same outcomes both
    # times, so a count- or outcome-keyed gate would have called that FRESH.
    assert measured == SUITE_PIN["sha256"], detail
    assert MANIFEST_PATH.stat().st_size == SUITE_PIN["bytes"], detail
    assert len(VECTORS) == SUITE_PIN["fhtFastaVectors"], detail
