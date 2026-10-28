# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Schema selection by the ``schema`` URL (FHR-Specification docs/SCHEMA-VERSIONS.md)."""

import hashlib
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

import bioheaders
from bioheaders import UnsupportedSchemaVersion, fhr, header_type, schema_for, selection

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
SPEC = Path(os.environ.get("FHR_SPECIFICATION", ROOT.parent / "FHR-Specification"))
RAW = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/"
W3ID = "https://w3id.org/fair-bioheaders/"


@pytest.fixture
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


@pytest.mark.parametrize(
    "value, expected",
    [
        (f"{RAW}main/fhr.json", ("FHR", "main", "fhr_schema.json")),  # V1
        (f"{RAW}main/fhp.json", ("FHP", "main", "fhp_schema.json")),
        (f"{RAW}main/fhgff3.json", ("FHGFF3", "main", "fhgff3_schema.json")),
        (f"{RAW}v0.4.0/fhr.json", ("FHR", "v0.4.0", "schemas/fhr-2.0.json")),  # V2
        (f"{RAW}v0.3.1/fhr.json", ("FHR", "v0.3.1", "schemas/fhr-1.json")),
        (f"{W3ID}fhr/v0.4.0", ("FHR", "v0.4.0", "schemas/fhr-2.0.json")),  # V3
        (f"{W3ID}fhr/v0.4.0/", ("FHR", "v0.4.0", "schemas/fhr-2.0.json")),
        (f"{W3ID}fhr/v0.3.0", ("FHR", "v0.3.0", "schemas/fhr-1.json")),
        (f"{W3ID}fhp/v0.4.0", ("FHP", "v0.4.0", "schemas/fhp-1.0.json")),
        (f"{W3ID}fhgff3/v0.4.0", ("FHGFF3", "v0.4.0", "schemas/fhgff3-1.0.json")),
        (
            "https://example.org/my-profile.json",
            ("FHR", "main", "fhr_schema.json"),
        ),  # V5
        (f"{W3ID}fhr/v0.4.0/fhr.json", ("FHR", "main", "fhr_schema.json")),
        (f"{RAW}main/fht.json", ("FHR", "main", "fhr_schema.json")),
        (None, ("FHR", "main", "fhr_schema.json")),
    ],
)
def test_selection(value, expected):
    kind, ref, schema = selection.select(value)
    assert (kind, ref, selection.bundled_file(value)) == expected
    content = files("bioheaders").joinpath(expected[2]).read_text(encoding="utf-8")
    assert schema == json.loads(content)


@pytest.mark.parametrize(
    "value, kind",
    [
        (f"{W3ID}fhr/v0.0.0", "FHR"),
        (f"{W3ID}fhr/v9.9.9", "FHR"),
        (f"{W3ID}fhp/v0.3.1", "FHP"),  # v0.3.1 published no FHP schema
        (f"{RAW}release-v0.4/fhr.json", "FHR"),
        (f"{RAW}0123abc/fhgff3.json", "FHGFF3"),
    ],
)
def test_unsupported_versions_are_never_substituted(value, kind):
    """V4: no schema is selected; the message names the value and what is bundled."""
    with pytest.raises(UnsupportedSchemaVersion) as error:
        selection.select(value)
    assert error.value.header_type == kind
    message = str(error.value)
    assert message.startswith(
        f"unsupported schema version: {value} (this tool has {kind}"
    )
    assert "main (v0.4.0)" in message
    assert header_type({"schema": value}) == kind
    with pytest.raises(UnsupportedSchemaVersion):
        schema_for({"schema": value})


@pytest.mark.parametrize("ref", ["refs/tags/v0.4.0", "refs/heads/main", "feature/x"])
def test_multi_segment_raw_refs_are_unsupported(ref):
    """V4: keep the whole ref, so only ``main`` or ``vX.Y.Z`` select a schema."""
    for kind, name in (("FHR", "fhr"), ("FHP", "fhp"), ("FHGFF3", "fhgff3")):
        value = f"{RAW}{ref}/{name}.json"
        assert selection.parse(value) == (kind, ref)
        with pytest.raises(UnsupportedSchemaVersion) as error:
            selection.select(value)
        assert error.value.header_type == kind


def test_bundled_registry_and_copies():
    bundled = selection.BUNDLED
    assert bundled["current"]["release"] == "v0.4.0"
    assert selection.supported("FHR") == [
        "main (v0.4.0)",
        "v0.3.0",
        "v0.3.1",
        "v0.4.0",
        "v0.4.1",
        "v0.4.2",
    ]
    assert selection.supported("FHP") == ["main (v0.4.0)", "v0.4.0", "v0.4.1", "v0.4.2"]
    # v0.4.0 is the current release (v0.4.1 and v0.4.2 have the same schemas), so its frozen copies equal the current ones.
    for kind, name in bundled["releases"]["v0.4.0"].items():
        current = bundled["current"]["files"][kind]
        assert files("bioheaders").joinpath(name).read_bytes() == (
            files("bioheaders").joinpath(current).read_bytes()
        )
    old = files("bioheaders").joinpath("schemas/fhr-1.json").read_bytes()
    assert hashlib.sha256(old).hexdigest() == (
        "e3d3843e1a1646e12495ccc9a615df94b7abe71b833c5f336c59444e0a49620a"
    )


def test_bundled_copies_match_the_specification_releases():
    registry = SPEC / "schemas" / "versions.json"
    if not registry.is_file():
        pytest.skip("no FHR-Specification checkout with schemas/versions.json")
    spec = json.loads(registry.read_text())
    assert selection.BUNDLED["current"]["release"] == spec["current"]
    for tag, types in selection.BUNDLED["releases"].items():
        assert set(types) == set(spec["releases"][tag]), tag
        for kind, name in types.items():
            ours = json.loads(files("bioheaders").joinpath(name).read_text())
            if tag == spec["current"]:
                theirs = json.loads((SPEC / spec["files"][kind]).read_text())
            else:
                shown = subprocess.run(
                    ["git", "show", f"{tag}:{spec['files'][kind]}"],
                    cwd=SPEC,
                    capture_output=True,
                    text=True,
                )
                if shown.returncode:
                    pytest.skip(f"FHR-Specification checkout has no tag {tag}")
                theirs = json.loads(shown.stdout)
            assert ours == theirs, (tag, kind)


def test_an_older_release_is_selected(metadata):
    """V3: a file citing v0.3.1 is checked against v0.3.1, not the current 2.0."""
    old = dict(metadata, schema=f"{W3ID}fhr/v0.3.1", schemaVersion=1)
    del old["metadataAuthor"][0]["nameType"]  # not in v0.3.1
    fhr(**old).fhr_validate()
    # V1: no fallback for raw-main records of the current version; schemaVersion 1
    # under raw-main is rule V6 (tests/fhr1_compat_test.py).
    with pytest.raises(ValidationError, match="schemaVersion|1 is not"):
        fhr(**dict(old, schema=f"{RAW}v0.4.0/fhr.json")).fhr_validate()
    with pytest.raises(ValidationError):
        fhr(**dict(metadata, schema=f"{W3ID}fhr/v0.3.1")).fhr_validate()


def test_cli_reports_unsupported_versions(metadata, tmp_path):
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(dict(metadata, schema=f"{W3ID}fhr/v0.0.0")))
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", str(path)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert result.stderr.startswith(
        f"FHR: unsupported schema version: {W3ID}fhr/v0.0.0 (this tool has FHR schemas"
    )


def test_writers_keep_the_schema_value(metadata, tmp_path):
    """FR-011: combine, strip and convert keep ``schema`` as written."""
    for value in (f"{W3ID}fhr/v0.4.0/", f"{RAW}v0.4.0/fhr.json", f"{RAW}main/fhr.json"):
        source = tmp_path / "metadata.json"
        source.write_text(json.dumps(dict(metadata, schema=value)))
        out = tmp_path / "out.yaml"
        subprocess.run(
            [str(BIN / "bioheaders"), "convert", str(source), str(out)], check=True
        )
        loaded = fhr()
        loaded.input_yaml(out.read_text())
        assert loaded.schema == value
        assert loaded.schemaVersion == "2.0"
        assert "schemaVersion: '2.0'" in out.read_text()


def test_header_type_predicates():
    assert bioheaders.is_fhp_schema(f"{W3ID}fhp/v0.4.0")
    assert bioheaders.is_fhgff3_schema(f"{RAW}main/fhgff3.json")
    assert not bioheaders.is_fhp_schema(f"{W3ID}fhr/v0.4.0")
    assert not bioheaders.is_fhp_schema("https://example.org/fhp.json")
