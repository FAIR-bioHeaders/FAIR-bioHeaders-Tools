# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Rule V5 near-miss warning (FAIR-bioHeaders-Tools#125).

A ``schema`` value that carries a FAIR-bioHeaders URL prefix (the w3id prefix or a
raw GitHub URL into the FAIR-bioHeaders org) yet matches no rule V1-V4 form is read
as FHR by rule V5. Such near-misses — the w3id path form, a cross-type ``fhp.json``,
a mistyped ``fht.json``, ``…/main/core.yaml``, a mistyped tag — now print an
informational warning; selection, validity and exit codes are unchanged. Arbitrary
third-party URLs are not near-misses and stay completely silent.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import fhr, schema_warnings, selection
from bioheaders.cli import combine

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
RAW = "https://raw.githubusercontent.com/FAIR-bioHeaders/"
SPEC = f"{RAW}FAIR-bioHeaders-Specification/"
W3ID = "https://w3id.org/fair-bioheaders/"
RELEASE = selection.BUNDLED["current"]["release"]  # the suggestion's version source
CURRENT = f"{W3ID}fhr/{RELEASE}"
SEQUENCE = b">chr1\nACGTACGT\n"


def run(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], capture_output=True, text=True
    )


def write(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


@pytest.fixture
def record():
    """A current FHR example record whose ``schema`` cites the w3id path form (V5)."""
    data = json.loads((ROOT / "examples/example.fhr.json").read_text())
    data["schema"] = f"{W3ID}fhr/v0.4.0/fhr.json"
    return data


# The predicate ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        f"{W3ID}fhr/v0.4.0/fhr.json",  # the w3id path form (the issue's example)
        f"{W3ID}fhr/v0.4",  # a mistyped tag
        f"{W3ID}fhr/v0.4.0.1",  # a mistyped tag
        f"{W3ID}fhp/v0.5.0/fhp.json",  # cross-type path form: read as FHR, not FHP
        f"{W3ID}fhgff3/v0.4.1/fhgff3.json",  # cross-type path form
        f"{SPEC}main/fht.json",  # a mistyped file name (no released FHT schema)
        f"{RAW}FHT-Specification/main/fht.json",  # the FHT repo's own URL
        f"{SPEC}main/core.yaml",  # a non-schema file path
        f"{RAW}FHR-Specification/main/fhr_schema.json",  # old name, other file
        f"{W3ID}profiles/agbiodata.yaml",  # a future profile path (#51/#56): the
        # warning is informational, never a rejection
        f"{W3ID}FHGFF3/v0.4.0",  # a mistyped type segment (W3ID is case-sensitive)
        "https://raw.githubusercontent.com/fair-bioheaders/fair-bioheaders-"
        "specification/main/fht.json",  # GitHub org/repo names are case-insensitive
    ],
)
def test_near_miss_values_are_flagged(value):
    assert selection.near_miss(value)
    assert selection.parse(value) is None  # exactly the silent V5 class
    warning = selection.near_miss_warning(value)
    assert warning is not None
    assert warning.startswith(f"schema {value} is not a FAIR-bioHeaders schema URL")
    assert "rule V5" in warning


@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/my-profile.json",  # the spec's V5 conformance vector
        "https://example.org/fair-bioheaders/fhr/v0.4.0/fhr.json",  # lookalike host
        f"{W3ID}fhr/v0.4.0",  # V3 proper
        f"{W3ID}fhr/v0.4.0/",  # V3 proper, trailing slash
        f"{SPEC}main/fhr.json",  # V1 proper
        f"{RAW}FHR-Specification/main/fhp.json",  # V1 proper, old name, other type
        f"{SPEC}refs/tags/v0.4.0/fhr.json",  # V4: parses, then fails loudly
        f"{W3ID}fhr/v9.9.9",  # V4: unbundled release, fails loudly
        f"{W3ID}fhp/v9.9.9",  # V4 cross-type form, fails loudly
        f"http://{W3ID[len('https://') :]}fhr/v0.4.0/fhr.json",  # not https
        f"http://{SPEC[len('https://') :]}main/fht.json",  # not https
        "ftp://w3id.org/fair-bioheaders/x",  # foreign scheme
        "file:///home/user/FAIR-bioHeaders-Specification/main/fhr.json",
        "https://w3id.org/fair-bioheaders",  # the prefix needs its trailing slash
        "https://w3id.org/fair-bioheaders-io/x.json",  # a different w3id namespace
        "https://raw.githubusercontent.com/other-org/"
        "FAIR-bioHeaders-Specification/main/fhr.json",  # a fork, not the org
        "",  # empty value
        None,  # missing schema
        123,  # not a string
        {"schema": f"{W3ID}fhr/v0.4.0/fhr.json"},  # not a string
    ],
)
def test_other_values_stay_silent(value):
    assert not selection.near_miss(value)
    assert selection.near_miss_warning(value) is None
    assert schema_warnings({"schema": value, "schemaVersion": "2.1"}) == []


# The messages, byte-pinned -----------------------------------------------------


def test_near_miss_message_bytes():
    assert selection.near_miss_warning(f"{W3ID}fhr/v0.4.0/fhr.json") == (
        "schema https://w3id.org/fair-bioheaders/fhr/v0.4.0/fhr.json is not a "
        "FAIR-bioHeaders schema URL; read as FHR against the current schema "
        f"(rule V5); did you mean {CURRENT}?"
    )


def test_cross_type_message_bytes_and_no_url_suggestion():
    # #125: a path naming fhp/fhgff3/fht must say the record is read as FHR and
    # must not suggest that the named type's release URL works for that file —
    # in particular never an FHT URL, for which no contract is released.
    for value, kind in [
        (f"{W3ID}fhp/v0.5.0/fhp.json", "FHP"),
        (f"{W3ID}fhgff3/v0.4.1/fhgff3.json", "FHGFF3"),
        (f"{SPEC}main/fht.json", "FHT"),
    ]:
        assert selection.near_miss_warning(value) == (
            f"schema {value} is not a FAIR-bioHeaders schema URL; read as FHR, "
            f"not {kind}, against the current schema (rule V5)"
        )
        assert "did you mean" not in selection.near_miss_warning(value)
    assert "fht/" not in selection.near_miss_warning(f"{SPEC}main/fht.json")


def test_suggestion_follows_the_bundled_registry():
    # The suggested URL is derived from schemas/bundled.json, never hard-coded:
    # bundling a new release must not need a change in selection.py.
    assert CURRENT in selection.near_miss_warning(f"{W3ID}fhr/v0.4.0/fhr.json")
    assert selection.current_fhr_url() == f"{W3ID}fhr/{RELEASE}"


# schema_warnings composition ----------------------------------------------------


def test_near_miss_record_keeps_selecting_fhr(record):
    assert schema_warnings(record) == [selection.near_miss_warning(record["schema"])]
    assert selection.select_record(record) == selection.select(record["schema"])
    assert selection.header_type(record["schema"]) == "FHR"


def test_fhr1_and_near_miss_never_cofire(record):
    # The raw-main FHR 1 citation matches V1, so it is never a near-miss; the two
    # warnings are mutually exclusive by construction.
    assert not selection.near_miss(f"{SPEC}main/fhr.json")
    fhr1 = dict(record, schema=f"{SPEC}main/fhr.json", schemaVersion=1)
    assert schema_warnings(fhr1) == [selection.FHR1_WARNING]


# End to end: every command family warns, nothing else changes --------------------


def test_validate_warns_without_changing_the_outcome(record, tmp_path):
    result = run("validate", write(tmp_path / "in.yaml", record))
    assert result.returncode == 0, result.stderr
    assert result.stdout == "FHR metadata is valid.\n"
    assert result.stderr == (
        f"FHR: warning: {selection.near_miss_warning(record['schema'])}\n"
    )
    # An invalid record still fails exactly like before, after the warning.
    write(tmp_path / "in.yaml", {k: v for k, v in record.items() if k != "taxon"})
    result = run("validate", tmp_path / "in.yaml")
    assert result.returncode == 1
    assert result.stderr.startswith("FHR: warning: ")
    assert "schema validation failed" in result.stderr


def test_convert_warns_and_keeps_the_value(record, tmp_path):
    out = tmp_path / "out.json"
    result = run("convert", write(tmp_path / "in.yaml", record), out)
    assert result.returncode == 0, result.stderr
    assert result.stderr == (
        f"FHR: warning: {selection.near_miss_warning(record['schema'])}\n"
    )
    assert json.loads(out.read_text())["schema"] == record["schema"]


def test_combine_verify_and_verify_links_warn(record, tmp_path):
    warning = f"FHR: warning: {selection.near_miss_warning(record['schema'])}\n"
    metadata = write(tmp_path / "metadata.yaml", record)
    (tmp_path / "plain.fa").write_bytes(SEQUENCE)
    out = tmp_path / "out.fhr.fa"
    result = run("combine", metadata, tmp_path / "plain.fa", "-o", out)
    assert result.returncode == 0, result.stderr
    assert result.stderr == warning
    assert f";~schema: {record['schema']}\n".encode() in out.read_bytes()
    result = run("verify", out)
    assert (result.returncode, result.stdout) == (0, "Checksum verified.\n")
    assert result.stderr == warning
    result = run("verify-links", out)
    assert result.returncode == 0, result.stderr
    assert result.stderr == warning
    # strip prints no schema warnings and stays silent.
    result = run("strip", out, tmp_path / "again.fa")
    assert (result.returncode, result.stderr) == (0, "")
    assert (tmp_path / "again.fa").read_bytes() == SEQUENCE


def test_third_party_profile_stays_silent_end_to_end(record, tmp_path):
    # The spec's own fasta-schema-other-value shape: example.org prints nothing.
    record["schema"] = "https://example.org/my-profile.json"
    result = run("validate", write(tmp_path / "in.yaml", record))
    assert (result.returncode, result.stderr) == (0, "")


def test_assess_text_report_shows_the_near_miss(record, tmp_path):
    from bioheaders.assess import assess_file
    from bioheaders.assess.render import _conformance_lines

    path = tmp_path / "genome.fhr.fa"
    path.write_bytes(combine(fhr(**record), SEQUENCE, "fasta"))
    conformance = assess_file(path)["conformance"]
    assert conformance["cited_schema"] == record["schema"]
    lines = _conformance_lines(conformance)
    assert f"warning: {selection.near_miss_warning(record['schema'])}" in lines
    # A silent value prints no warning line in the report either.
    record["schema"] = "https://example.org/my-profile.json"
    path.write_bytes(combine(fhr(**record), SEQUENCE, "fasta"))
    conformance = assess_file(path)["conformance"]
    assert not any("warning" in line for line in _conformance_lines(conformance))
