# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHP/FHGFF3 1.2: dotted BUSCO dataset versions (FAIR-bioHeaders-Specification#170).

The 1.2 contracts, staged for specification release v0.6.0 in
FAIR-bioHeaders-Specification#222, widen ``completeness.lineageDataset`` to the
dotted dataset ids the BUSCO user guide documents (for example
``diptera_odb12.2``). The widening is held to the stated minor (docs/
SCHEMA-VERSIONS.md): a record that states ``'1.0'`` or ``'1.1'`` keeps the old
pattern even when it cites a 1.2 schema, a record that cites a v0.4.x or v0.5.0
schema is checked against that release's frozen bytes, and no record is ever
silently validated against a different contract than the one it cites. FHR has
no completeness slot: FHR stays at 2.1 in v0.6.0, and no FHR 2.2 exists.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from bioheaders import fhr, schema_for, selection
from bioheaders.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
W3ID = "https://w3id.org/fair-bioheaders/"
RAW_MAIN = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/"
)
SEGMENT = {"FHP": "fhp", "FHGFF3": "fhgff3"}
BASE = {
    "FHP": "examples/fhp/minimal-predicted.fhp.json",
    "FHGFF3": "examples/fhgff3/minimal-reference.fhgff3.json",
}
BODIES = {
    "FHP": (
        b">p1 one\nMKTAYIAKQR*\n>p2 two\nMUOBZJXmAKQR\n",
        "fasta",
        "out.fhp.fasta",
    ),
    "FHGFF3": (
        b"##gff-version 3\n##sequence-region ctg1 1 20\n"
        b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n",
        "gff3",
        "out.fhgff3.gff3",
    ),
}
DOTTED = "diptera_odb12.2"
PLAIN = "diptera_odb12"
# The completeness block of the specification's dotted conformance vectors,
# counts included; only lineageDataset's pattern is under test here.
COMPLETENESS = {
    "lineageDataset": DOTTED,
    "mode": "proteins",
    "completeSingle": 1,
    "completeDuplicated": 0,
    "fragmented": 0,
    "missing": 1,
    "total": 2,
}


def record(header_type, version, schema=None, lineage=None):
    data = json.loads((ROOT / BASE[header_type]).read_text(encoding="utf-8"))
    data["schemaVersion"] = version
    if schema is not None:
        data["schema"] = schema
    data["completeness"] = dict(COMPLETENESS)
    if lineage is not None:
        data["completeness"]["lineageDataset"] = lineage
    return data


def valid(data):
    try:
        fhr(**copy.deepcopy(data)).fhr_validate()
    except (ValidationError, ValueError):
        return False
    return True


def run(*args, cwd=None):
    return subprocess.run(
        [str(arg) for arg in args], capture_output=True, text=True, cwd=cwd
    )


# The bundled registry and the prepared release.


@pytest.mark.parametrize("header_type", SEGMENT)
def test_current_and_v0_6_0_select_the_1_2_contract(header_type):
    segment = SEGMENT[header_type]
    for value in (f"{RAW_MAIN}{segment}.json", f"{W3ID}{segment}/v0.6.0"):
        enum = schema_for({"schema": value})["properties"]["schemaVersion"]["enum"]
        assert enum == ["1.0", "1.1", "1.2"], value


def test_v0_6_0_keeps_fhr_at_2_1():
    """FHR has no completeness slot: #170 changes no FHR contract (no 2.2)."""
    schema = schema_for({"schema": f"{W3ID}fhr/v0.6.0"})
    assert schema["properties"]["schemaVersion"]["enum"] == ["2.0", "2.1"]
    assert selection.bundled_file(f"{W3ID}fhr/v0.6.0") == "schemas/fhr-2.1.json"


# Held to the stated minor: the version gate lives in the 1.2 schema itself.


@pytest.mark.parametrize("header_type", SEGMENT)
def test_dotted_requires_the_stated_minor(header_type):
    segment = SEGMENT[header_type]
    for value in (f"{RAW_MAIN}{segment}.json", f"{W3ID}{segment}/v0.6.0"):
        assert valid(record(header_type, "1.2", value)), value
        assert valid(record(header_type, "1.2", value, lineage=PLAIN)), value
        assert not valid(record(header_type, "1.1", value)), value
        assert not valid(record(header_type, "1.0", value)), value
        # The older minors keep their exact pre-#170 outcomes: an undotted
        # dataset id stating 1.1 still validates against the 1.2 contract.
        assert valid(record(header_type, "1.1", value, lineage=PLAIN)), value


@pytest.mark.parametrize("header_type", SEGMENT)
@pytest.mark.parametrize(
    "lineage",
    [
        "Primates_odb12.2",
        "primates_odb12.",
        "primates_odb.12",
        "primates_odb12.2b",
    ],
)
def test_1_2_rejects_malformed_lineages_for_current_contracts(header_type, lineage):
    segment = SEGMENT[header_type]
    for value in (f"{RAW_MAIN}{segment}.json", f"{W3ID}{segment}/v0.6.0"):
        assert not valid(record(header_type, "1.2", value, lineage=lineage)), value


@pytest.mark.parametrize("header_type", SEGMENT)
@pytest.mark.parametrize("release", ["v0.4.0", "v0.4.1", "v0.4.2", "v0.5.0"])
def test_older_releases_never_accept_a_dotted_version(header_type, release):
    """V2/V3: dotted records citing a pre-v0.6.0 schema fail against its bytes.

    A dotted id stating the release's own minor fails the old pattern; stating
    "1.2" fails the release schema's ``schemaVersion`` enum. No record is ever
    silently checked against the newer contract it does not cite.
    """
    value = f"{W3ID}{SEGMENT[header_type]}/{release}"
    old = "1.0" if release.startswith("v0.4") else "1.1"
    assert valid(record(header_type, old, value, lineage=PLAIN))
    assert not valid(record(header_type, old, value))
    assert not valid(record(header_type, "1.2", value))


@pytest.mark.parametrize("header_type", SEGMENT)
@pytest.mark.parametrize("frozen", ["1.0", "1.1"])
def test_frozen_snapshots_reject_1_2_material_directly(header_type, frozen):
    """The frozen files themselves, bypassing selection, hold their contract."""
    path = ROOT / "bioheaders" / "schemas" / f"{SEGMENT[header_type]}-{frozen}.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    assert not validator.is_valid(record(header_type, frozen, lineage=DOTTED))
    assert not validator.is_valid(record(header_type, "1.2", lineage=PLAIN))
    assert validator.is_valid(record(header_type, frozen, lineage=PLAIN))


# Round trips: the 1.2 record survives combine, verify, validate and strip.


@pytest.mark.parametrize("header_type", SEGMENT)
def test_library_round_trip_of_a_dotted_1_2_record(header_type):
    body, kind, _ = BODIES[header_type]
    data = combine(fhr(**copy.deepcopy(record(header_type, "1.2"))), body, kind)
    reader = fhr()
    reader.input_fasta(data) if kind == "fasta" else reader.input_gff3(data)
    assert reader.completeness["lineageDataset"] == DOTTED
    assert reader.schemaVersion == "1.2"
    reader.fhr_validate()
    assert reader.checksum == checksum(data, kind)
    assert strip_header(data, kind) == body


@pytest.mark.parametrize("header_type", SEGMENT)
def test_cli_round_trip_of_a_dotted_1_2_record(header_type, tmp_path):
    body, kind, name = BODIES[header_type]
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(record(header_type, "1.2")), encoding="utf-8")
    source = tmp_path / f"body.{kind}"
    source.write_bytes(body)
    output = tmp_path / name
    result = run(
        BIN / "bioheaders", "combine", meta, source, "-o", output, cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert f"schema: {W3ID}{SEGMENT[header_type]}/v0.6.0" in text
    assert "schemaVersion: '1.2'" in text
    assert f"lineageDataset: {DOTTED}" in text
    assert run(BIN / "bioheaders", "verify", output).stdout == "Checksum verified.\n"
    assert run(BIN / "bioheaders", "validate", output).returncode == 0
    back = tmp_path / "back"
    assert run(BIN / "bioheaders", "strip", output, back).returncode == 0
    assert back.read_bytes() == body
    # Tampering the dotted id in the header breaks the computed checksum.
    tampered = tmp_path / "tampered"
    tampered.write_bytes(output.read_bytes().replace(DOTTED.encode(), PLAIN.encode()))
    assert run(BIN / "bioheaders", "verify", tampered).returncode != 0


@pytest.mark.parametrize("header_type", SEGMENT)
def test_cli_rejects_a_dotted_record_stating_an_older_minor(header_type, tmp_path):
    body, kind, name = BODIES[header_type]
    data = record(header_type, "1.1")  # cites v0.6.0, states 1.1: the gate rejects
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(data), encoding="utf-8")
    source = tmp_path / f"body.{kind}"
    source.write_bytes(body)
    output = tmp_path / name
    result = run(
        BIN / "bioheaders", "combine", meta, source, "-o", output, cwd=tmp_path
    )
    assert result.returncode != 0, "combine accepted a dotted id stating 1.1"
    assert "lineageDataset" in result.stderr or "does not match" in result.stderr
