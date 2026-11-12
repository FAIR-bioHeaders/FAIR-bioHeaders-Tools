# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHT conformance-vector consumer — PREP STUB (skipped by default).

The 65 byte-exact vectors of FHT-Specification ``conformance/`` (issue #8,
delivered by PR #29, merged into ``main`` as ``b9ad19a`` on 2026-11-12) are the
authoritative acceptance gate for this toolkit's FHT support
(FHT-Specification#9). This file is deliberately written so that turning it on
is mechanical; it copies nothing into this repository in the prep state.

Run it with BOTH:

1. ``BIOHEADERS_EXPERIMENTAL_FHT=1`` — the draft lane (docs/FHT-SELECTION-DESIGN.md);
2. ``FHT_SPECIFICATION=/path/to/FHT-Specification`` — a checkout whose
   ``conformance/manifest.json`` exists (or a sibling ``FHT-Specification``
   directory, the fallback used by ``tests/fhp_test.py``).

When the FHT toolkit support ships for real (shared publication or the agreed
default-on draft recognition), drop the gate condition and wire this into CI
the way the shared suite's ``fhp-fasta`` vectors are wired today.

Semantics implemented below, from the suite README and manifest:

- ``expected: valid``     — ``bioheaders verify`` exits 0 and the recomputed
  SHA-512/256 of the exact bytes equals ``checksum``.
- ``expected: invalid``   — the toolkit must reject, with the failure class the
  vector declares: ``selfChecksum: broken`` is a checksum mismatch,
  ``selfChecksum: matches`` is a schema/contract rejection under an
  otherwise-consistent file, and ``selfChecksum: unreachable`` is a header the
  reader cannot even parse. Exception: a vector whose only failure is a
  ``parentLink`` verdict of ``checked-fail`` (T3) is byte- and schema-valid;
  ``verify`` passes it and ``verify-links`` reports mismatch
  (``fht-fasta-parent-mismatched``), matching the suite README exactly.
- ``parentLink`` entries  — ``bioheaders verify-links`` must report matched /
  not matched / not checked distinctly (never invent or substitute an
  identifier), exit 0 for matched and unchecked, and exit 3 for a mismatch.
"""

import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

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


def pytest_param_id(vector):
    return vector["id"]


params = [pytest.param(vector, id=vector["id"]) for vector in VECTORS]

pytestmark = pytest.mark.skipif(not (HAVE_VECTORS and GATE_OPEN), reason=SKIP_REASON)


def vector_bytes(vector):
    data = (CONFORMANCE / vector["file"]).read_bytes()
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
    source = CONFORMANCE / vector["file"]
    target = tmp_path / source.name
    target.write_bytes(source.read_bytes())
    return target


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
        # T3: the file itself is byte- and schema-valid; only the recorded
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
