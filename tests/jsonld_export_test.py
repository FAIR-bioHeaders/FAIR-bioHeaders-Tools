# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The one-way schema.org export (FHR-Specification docs/SCHEMAORG-EXPORT.md)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import jsonld

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
# The repository was renamed FAIR-bioHeaders-Specification (#108); an old-named
# checkout still works.
SPEC = Path(
    os.environ.get("FHR_SPECIFICATION")
    or next(
        (
            path
            for path in (
                ROOT.parent / "FAIR-bioHeaders-Specification",
                ROOT.parent / "FHR-Specification",
            )
            if path.exists()
        ),
        ROOT.parent / "FAIR-bioHeaders-Specification",
    )
)
FIXTURES = ROOT / "tests" / "fixtures" / "schemaorg-export"
CASES = sorted(path.name for path in FIXTURES.iterdir() if path.is_dir())


def case(name):
    directory = FIXTURES / name
    record = json.loads((directory / "record.json").read_text(encoding="utf-8"))
    context = directory / "export-context.json"
    export = (
        json.loads(context.read_text(encoding="utf-8")) if context.exists() else None
    )
    return record, export, (directory / "expected.jsonld").read_text(encoding="utf-8")


def bioheaders(*args, stdin=b""):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], input=stdin, capture_output=True
    )


@pytest.mark.parametrize("name", CASES)
def test_export_matches_the_specification_fixture(name):
    record, export, expected = case(name)
    assert jsonld.export_text(record, export) == expected


def test_example_export():
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    expected = (ROOT / "examples/example.fhr.export.jsonld").read_text(encoding="utf-8")
    assert jsonld.export_text(record) == expected


def test_name_type_types_the_export_author_node():
    """The export types an author from nameType before its uri (issue #74)."""
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    record["assemblyAuthor"] = [
        {
            "name": "Person with a ROR ID",
            "uri": "https://ror.org/05gq02987",
            "nameType": "Personal",
        },
        {"name": "Example Sequencing Centre", "nameType": "Organizational"},
    ]
    authors = jsonld.to_export(record)["@graph"][0]["creator"]
    assert [node["@type"] for node in authors] == ["Person", "Organization"]
    assert all("nameType" not in node for node in authors)
    assert jsonld.export_unmapped_keys(record) == []


def test_fixtures_match_the_specification():
    published = SPEC / "tests" / "fixtures" / "schemaorg-export"
    if not published.is_dir():
        pytest.skip("FHR-Specification checkout with the export fixtures not found")
    names = sorted(path.name for path in published.iterdir() if path.is_dir())
    assert names == CASES
    for name in names:
        for path in sorted((published / name).iterdir()):
            assert (FIXTURES / name / path.name).read_bytes() == path.read_bytes()
    example = "examples/example.fhr.export.jsonld"
    assert (ROOT / example).read_bytes() == (SPEC / example).read_bytes()


def test_cli_writes_the_export(tmp_path):
    output = tmp_path / "x.jsonld"
    context = tmp_path / "context.json"
    record, export, expected = case("full")
    source = tmp_path / "full.fhr.json"
    source.write_text(json.dumps(record))
    context.write_text(json.dumps(export))
    result = bioheaders(
        "convert",
        source,
        output,
        "--jsonld-profile",
        "export",
        "--export-context",
        context,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == expected


def test_cli_canonical_is_the_default(tmp_path):
    output = tmp_path / "x.jsonld"
    result = bioheaders("convert", ROOT / "examples/example.fhr.json", output)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == (ROOT / "examples/example.fhr.jsonld").read_bytes()


def test_cli_profile_needs_jsonld_output(tmp_path):
    result = bioheaders(
        "convert",
        ROOT / "examples/example.fhr.json",
        tmp_path / "x.yaml",
        "--jsonld-profile",
        "export",
    )
    assert result.returncode != 0
    assert b"--jsonld-profile applies only to JSON-LD output" in result.stderr


def test_an_export_is_not_read_back(tmp_path):
    exported = tmp_path / "x.jsonld"
    exported.write_bytes((ROOT / "examples/example.fhr.export.jsonld").read_bytes())
    result = bioheaders("convert", exported, tmp_path / "back.json")
    assert result.returncode != 0
    assert b"one-way schema.org export" in result.stderr
    with pytest.raises(ValueError, match="one-way schema.org export"):
        jsonld.from_jsonld(json.loads(exported.read_text()))


def test_unmapped_nested_keys_are_reported_and_left_out(tmp_path):
    record, _, _ = case("metadata-record")
    # Nested objects are closed from FHR 2.0 (v0.4), so the extra key needs a record
    # that cites v0.3.1, whose objects are open (FHR-Specification docs/SCHEMA-VERSIONS.md).
    record.update(schema="https://w3id.org/fair-bioheaders/fhr/v0.3.1", schemaVersion=1)
    record["taxon"]["checksum"] = "nested property, not the file checksum"
    assert jsonld.export_unmapped_keys(record) == ["taxon.checksum"]
    assert "nested property" not in jsonld.export_text(record)
    source = tmp_path / "x.fhr.json"
    source.write_text(json.dumps(record))
    result = bioheaders(
        "convert", source, tmp_path / "x.jsonld", "--jsonld-profile", "export"
    )
    assert result.returncode == 0, result.stderr
    assert b"taxon.checksum has no export target" in result.stderr


def test_export_context_how_to_flag_is_a_boolean():
    record, _, _ = case("provenance-howto")
    with pytest.raises(ValueError, match="assemblyProtocolHowTo must be true or false"):
        jsonld.to_export(record, {"assemblyProtocolHowTo": "yes"})
    # The canonical writer accepts the key and ignores it.
    canonical = jsonld.to_jsonld(record, {"assemblyProtocolHowTo": True})
    assert "actionProcess" not in json.dumps(canonical)


def test_no_values_are_invented():
    record, export, _ = case("funding-grant")
    graph = jsonld.to_export(record, export)["@graph"]
    assert graph[0]["funding"] == {
        "@type": "Grant",
        "description": record["funding"],
    }
    for name in CASES:
        text = jsonld.export_text(*case(name)[:2])
        for absent in ("observationDate", "variableMeasured", "startTime", "funder"):
            assert absent not in text
