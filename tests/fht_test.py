# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Draft transcriptome header FHT (FHT-Specification#9) — PREP, gated.

Everything here pins the two halves of the draft-lane contract:

- **Off is today.** Without ``BIOHEADERS_EXPERIMENTAL_FHT`` a record citing the
  raw-main ``fht.json`` of FHT-Specification is rule V5: read as FHR, with the
  #137 near-miss warning ("read as FHR, not FHT"), and no FASTA command accepts
  an FHT family. These are the published SCHEMA-VERSIONS semantics, and the
  gate must never change them by default.
- **On is a preview.** With the opt-in the citation selects the bundled draft
  contract (``schemas/fht-draft.json``, status ``draft``, no release tag, no
  w3id alias), the FASTA family table admits FHT, and combine/verify/strip/
  convert/verify-links ride the existing ``;~`` machinery — every warning says
  the contract is unreleased. See docs/FHT-SELECTION-DESIGN.md.

The conformance vectors themselves are consumed by tests/fht_conformance_test.py
(skipped stub) once the FHT-Specification checkout is available.
"""

import copy
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from bioheaders import fhr, schema_warnings, selection
from bioheaders.assess import conformance
from bioheaders.cli import checksum, combine, strip_header, validate_header_family

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
FHT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHT-Specification/main/fht.json"
)
# RNA (U), cDNA (T) with CRLF, lower case and ambiguity codes: bytes the
# transcriptome contract promises to preserve (FHT-Specification#9).
TRANSCRIPTS = (
    b">tr1 rna\nAUGCAAAAAAU\n>tr2 cdna\r\natgcaacgtn\n"
    b">tr3 ambiguous\nACGTRYKMDHVSBN*\n"
)


@pytest.fixture()
def minimal():
    """A minimal valid FHT record against the draft contract (the nine required
    fields of fht.json 1.0, no invented values beyond synthetic names)."""
    return {
        "schema": FHT_URL,
        "schemaVersion": "1.0",
        "transcriptome": "Synthetic prep transcript set",
        "assemblyType": "de novo",
        "taxon": {
            "name": "Tribolium castaneum",
            "uri": "https://identifiers.org/taxonomy:7070",
        },
        "version": "1.0.0",
        "metadataAuthor": [{"name": "Prep Test Author"}],
        "dateCreated": "2026-11-12",
    }


@pytest.fixture()
def draft(monkeypatch):
    """Open the draft lane for this test only."""
    monkeypatch.setenv(selection.DRAFT_ENV, "1")
    return True


def run(*args, env=None):
    environment = dict(os.environ)
    if env is not None:
        if env:
            environment[selection.DRAFT_ENV] = "1"
        else:
            environment.pop(selection.DRAFT_ENV, None)
    return subprocess.run(
        [str(BIN / "bioheaders"), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        env=environment,
    )


# The gate itself.


def test_gate_off_keeps_rule_v5(monkeypatch):
    monkeypatch.delenv(selection.DRAFT_ENV, raising=False)
    assert not selection.draft_support_enabled()
    assert selection.parse(FHT_URL) is None
    assert selection.header_type(FHT_URL) == "FHR"
    warning = selection.near_miss_warning(FHT_URL)
    assert warning and "read as FHR, not FHT" in warning


def test_gate_values(monkeypatch):
    for value, enabled in (
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("", False),
        ("0", False),
        ("off", False),
        ("yesplease", False),
    ):
        monkeypatch.setenv(selection.DRAFT_ENV, value)
        assert selection.draft_support_enabled() is enabled, value
    monkeypatch.delenv(selection.DRAFT_ENV)
    assert not selection.draft_support_enabled()


def test_family_table_requires_the_gate(monkeypatch, minimal):
    monkeypatch.delenv(selection.DRAFT_ENV, raising=False)
    # Gate off, the record is FHR (rule V5) and its FHT fields fail the FHR schema.
    data = fhr(**minimal)
    assert data.header_type() == "FHR"
    with pytest.raises(ValidationError):
        data.fhr_validate()


def test_family_table_opens_only_fasta(draft, minimal):
    data = fhr(**minimal)
    assert data.header_type() == "FHT"
    validate_header_family(data, "fasta")  # no exception
    # The FHT draft contract is FASTA-only; GFA stays FHR (FHT-Specification fht.json).
    with pytest.raises(ValueError, match="FHT metadata is incompatible with GFA"):
        validate_header_family(data, "gfa")


# Selection and the registry.


def test_draft_selection(draft, minimal):
    with pytest.warns(selection.ExperimentalDraftWarning):
        kind, ref, schema = selection.select_record(minimal)
    assert (kind, ref) == ("FHT", "main")
    assert schema["title"] == "FHT"
    assert schema["properties"]["schemaVersion"]["enum"] == ["1.0"]
    assert schema["$id"] == FHT_URL
    assert selection.supported("FHT") == ["main (draft, experimental)"]


def test_draft_is_not_a_release(draft):
    # The draft lane must not leak into the published registry shapes: no
    # current entry, no release entry, and therefore no w3id URL for FHT.
    assert "FHT" not in selection.BUNDLED["current"]["files"]
    assert all("FHT" not in types for types in selection.BUNDLED["releases"].values())
    for value in (
        "https://w3id.org/fair-bioheaders/fht/v0.5.0",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/v0.1.0/fht.json",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/fht.json",
    ):
        assert selection.parse(value) is None  # gate on, still rule V5
        warning = selection.near_miss_warning(value)
        assert warning and "not FHT" in warning


def test_bundled_draft_provenance():
    entry = selection.BUNDLED["drafts"]["FHT"]
    assert entry["status"] == "draft"
    assert entry["citation"] == FHT_URL
    assert entry["schemaVersion"] == "1.0"
    assert len(entry["revision"]) == 40 and len(entry["retrieved"]) == 10
    content = (ROOT / "bioheaders" / entry["file"]).read_bytes()
    assert hashlib.sha256(content).hexdigest() == entry["sha256"]
    # Byte-exact copy of the named revision of the development contract.
    assert json.loads(content)["$id"] == FHT_URL


def test_schema_warnings_names_the_draft(draft, minimal):
    messages = schema_warnings(minimal)
    assert any(
        "draft" in message and "not a released schema" in message
        for message in messages
    )
    assert not any("read as FHR" in message for message in messages)


# The FASTA machinery.


def test_combine_round_trip(draft, minimal):
    out = combine(fhr(**minimal), TRANSCRIPTS, "fasta")
    assert out.startswith(b";~")
    assert out.endswith(TRANSCRIPTS)  # exact bytes, CRLF and all
    assert strip_header(out, "fasta") == TRANSCRIPTS
    lines = [line for line in out.splitlines() if line.startswith(b";~checksum:")]
    assert len(lines) == 1
    value = lines[0][len(b";~checksum:") :].strip().strip(b"'\" ")
    assert value.decode() == checksum(out, "fasta")


def test_verify_cli_accepts_and_rejects(draft, tmp_path, minimal):
    path = tmp_path / "prep.fht.fasta"
    path.write_bytes(combine(fhr(**minimal), TRANSCRIPTS, "fasta"))
    result = run("verify", path, env=True)
    assert result.returncode == 0, result.stderr
    assert "Checksum verified." in result.stdout
    assert "FHT: warning:" in result.stderr and "draft" in result.stderr
    # The same file is still not FHT for a run without the opt-in (rule V5).
    closed = run("verify", path, env=False)
    assert closed.returncode == 1
    assert "read as FHR, not FHT" in closed.stderr


def test_gzip_and_tamper(draft, tmp_path, minimal):
    combined = combine(fhr(**minimal), TRANSCRIPTS, "fasta")
    gz = tmp_path / "prep.fht.fasta.gz"
    gz.write_bytes(gzip.compress(combined))
    assert run("verify", gz, env=True).returncode == 0
    assert checksum(gzip.decompress(gz.read_bytes()), "fasta") == checksum(
        combined, "fasta"
    )
    broken = bytearray(combined)
    broken[-2] = ord("A") if broken[-2] != ord("A") else ord("C")
    plain = tmp_path / "tampered.fht.fasta"
    plain.write_bytes(bytes(broken))
    result = run("verify", plain, env=True)
    assert result.returncode == 1 and "Checksum verification failed" in result.stderr


def test_strip_and_convert(draft, tmp_path, minimal):
    combined = combine(fhr(**minimal), TRANSCRIPTS, "fasta")
    source = tmp_path / "prep.fht.fasta"
    source.write_bytes(combined)
    stripped = tmp_path / "bare.fa"
    assert run("strip", source, stripped, env=True).returncode == 0
    assert stripped.read_bytes() == TRANSCRIPTS
    as_yaml = tmp_path / "meta.yaml"
    result = run("convert", source, as_yaml, env=True)
    assert result.returncode == 0, result.stderr
    # A metadata-only form carries no body: re-adding it to the same sequence
    # goes through combine, which recomputes the checksum over the same bytes.
    body = tmp_path / "bare-in.fa"
    body.write_bytes(TRANSCRIPTS)
    again = tmp_path / "again.fht.fasta"
    back = run("combine", as_yaml, body, "-o", again, env=True)
    assert back.returncode == 0, back.stderr
    assert run("verify", again, env=True).returncode == 0


def test_validate_and_assess_stay_draft_aware(draft, tmp_path, minimal):
    path = tmp_path / "prep.fht.fasta"
    path.write_bytes(combine(fhr(**minimal), TRANSCRIPTS, "fasta"))
    result = run("validate", path, env=True)
    assert result.returncode == 0 and "FHT metadata is valid." in result.stdout
    # assess reports the FHT citation as not assessed: its rubric follows the
    # released contracts, and the draft lane does not change that (deferred,
    # docs/FHT-SELECTION-DESIGN.md).
    header = [line for line in path.read_bytes().splitlines() if line.startswith(b";~")]
    report, _ = conformance.check(header, b";~")
    assert report.header_type == "FHT"
    assert report.result == "not_assessed"


# Contract closure (T2) and record validity under the gate.


def test_invalid_records_are_rejected(draft, minimal):
    # A well-formed checksum value stands in for the one combine() would
    # compute; this test is about contract closure, not byte coverage.
    minimal = dict(minimal, checksum="A" * 43 + "=")

    def validate(record):
        fhr(**copy.deepcopy(record)).fhr_validate()

    validate(minimal)  # the baseline itself
    missing = copy.deepcopy(minimal)
    del missing["transcriptome"]
    with pytest.raises(ValidationError):
        validate(missing)
    for bad_type in ("hybrid", "genome guided", ""):
        record = copy.deepcopy(minimal)
        record["assemblyType"] = bad_type
        with pytest.raises(ValidationError):
            validate(record)
    closed = copy.deepcopy(minimal)
    closed["notAField"] = "closed top level plus x- only"
    with pytest.raises(ValidationError):
        validate(closed)
    extension = copy.deepcopy(minimal)
    extension["x-prep-note"] = {"any": ["value"]}  # R15 works in the draft too
    validate(extension)


def test_schema_url_closure_under_the_gate(draft, minimal):
    # T2: only the FHT forms are FHT citations. An FHR URL stays FHR (V5/V1) and
    # fails the FHR contract for this record — never a silent FHT read.
    record = copy.deepcopy(minimal)
    record["schema"] = (
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/main/fhr.json"
    )
    data = fhr(**record)
    assert data.header_type() == "FHR"
    with pytest.raises(ValidationError):
        data.fhr_validate()
    other = copy.deepcopy(minimal)
    other["schema"] = "https://example.org/fht.json"
    assert selection.parse(other["schema"]) is None
    assert not selection.near_miss(other["schema"])  # a third-party URL stays silent


# verify-links (T3): matched, not matched and not checked, never invented.


def _recorded_parent_checksum(parent_bytes):
    return checksum(parent_bytes, "fasta")


def test_verify_links_three_verdicts(draft, tmp_path, minimal):
    genome = combine(
        fhr(
            **json.loads((ROOT / "examples" / "example.fhr.json").read_text()),
        ),
        b">chr1\nACGTACGT\n",
        "fasta",
    )
    parent = tmp_path / "parent.fhr.fasta"
    parent.write_bytes(genome)
    good = copy.deepcopy(minimal)
    good["derivedFrom"] = [
        {
            "headerType": "FHR",
            "relationship": "transcribedFrom",
            "checksum": _recorded_parent_checksum(genome),
        }
    ]
    child = tmp_path / "linked.fht.fasta"
    child.write_bytes(combine(fhr(**good), TRANSCRIPTS, "fasta"))
    matched = run("verify-links", child, parent, env=True)
    assert matched.returncode == 0 and "matched (" in matched.stdout

    bad = copy.deepcopy(good)
    # Any other well-formed checksum is a mismatch: the parent file says
    # otherwise. Never an invented or recomputed substitute.
    bad["derivedFrom"][0]["checksum"] = "B" * 43 + "="
    broken_child = tmp_path / "broken.fht.fasta"
    broken_child.write_bytes(combine(fhr(**bad), TRANSCRIPTS, "fasta"))
    mismatch = run("verify-links", broken_child, parent, env=True)
    assert mismatch.returncode == 3 and "not matched (" in mismatch.stdout

    unchecked = run("verify-links", child, env=True)
    assert unchecked.returncode == 0 and "not checked (" in unchecked.stdout
    required = run("verify-links", "--require-all", child, env=True)
    assert required.returncode == 3


# Non-regression with the gate open.


def test_unbound_forms_are_refused_not_stretched(draft, minimal):
    # No reviewed FHT JSON-LD or microdata binding exists (FHT-Specification#9):
    # an FHT record must be refused by those writers, never emitted under the
    # FHR identity, and an FHR-itemtype document citing FHT is not FHR either.
    data = fhr(**minimal, checksum="A" * 43 + "=")
    data.fhr_validate()
    with pytest.raises(ValueError, match="JSON-LD output is not available for FHT"):
        data.output_jsonld()
    with pytest.raises(ValueError, match="microdata output is not available for FHT"):
        data.output_microdata()
    page = (
        '<div itemscope itemtype="'
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        'FAIR-bioHeaders-Specification/main/fhr.json">'
        '<meta itemprop="schema" content="' + FHT_URL + '">'
        '<meta itemprop="schemaVersion" content="1.0"></div>\n'
    )
    refused = fhr()
    with pytest.raises(ValueError, match="an FHR-itemtype document is not FHT"):
        refused.input_microdata(page)


def test_fhr_and_fhp_unaffected_when_gate_is_open(draft, tmp_path):
    fhr_meta = json.loads((ROOT / "examples" / "example.fhr.json").read_text())
    genome = combine(fhr(**fhr_meta), b">chr1\nACGT\n", "fasta")
    path = tmp_path / "g.fhr.fasta"
    path.write_bytes(genome)
    result = run("verify", path, env=True)
    assert result.returncode == 0 and "Checksum verified." in result.stdout
    assert "warning" not in result.stderr.lower() or "draft" not in result.stderr
    protein = tmp_path / "p.fhp.fasta"
    fhp_meta = json.loads(
        (ROOT / "examples" / "fhp" / "minimal-predicted.fhp.json").read_text()
    )
    protein.write_bytes(combine(fhr(**fhp_meta), b">p1\nMKTAYIAKQR*\n", "fasta"))
    assert run("verify", protein, env=True).returncode == 0
