# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Rule V6: FHR 1 records citing the raw-main schema URL are read as v0.3.1.

FAIR-bioHeaders-Specification docs/SCHEMA-VERSIONS.md. FHR 1 (releases up to v0.3.1)
told writers to cite the raw-main ``fhr.json`` URL with ``schemaVersion`` 1, a number.
Since raw-main selects FHR 2.0, such a record is read against the bundled v0.3.1
schema with a deprecation warning; everything else selects as before (V1-V5).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema.exceptions import ValidationError

from bioheaders import fhr, schema_for, schema_warnings, selection
from bioheaders.cli import combine

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
RAW = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/"
RAW_CANONICAL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/"
)
RAW_MAIN = f"{RAW}main/fhr.json"
W3ID = "https://w3id.org/fair-bioheaders/"
WARNING = (
    "FHR: warning: schemaVersion 1 via the raw-main schema URL is read as FHR 1 "
    "(v0.3.1); cite https://w3id.org/fair-bioheaders/fhr/v0.3.1 or move to "
    'schemaVersion "2.0"'
)
SEQUENCE = b">chr1\nACGTACGT\n"


def bundled(name):
    path = ROOT / "bioheaders" / name
    return json.loads(path.read_text(encoding="utf-8"))


FHR1 = bundled("schemas/fhr-1.json")
FHR2 = bundled("schemas/fhr-2.0.json")


@pytest.fixture
def record():
    """An FHR 1 record as FHR 1 writers produced it: raw-main and the number 1.0."""
    data = json.loads((ROOT / "examples/example.fhr.json").read_text())
    for author in data["metadataAuthor"] + data["assemblyAuthor"]:
        author.pop("nameType", None)  # FHR 2.0 only
    data.update(schema=RAW_MAIN, schemaVersion=1.0)
    fhr(**data).fhr_validate()
    return data


def run(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], capture_output=True, text=True
    )


def write(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


@pytest.mark.parametrize("schema", [RAW_MAIN, f"{RAW_CANONICAL}main/fhr.json"])
@pytest.mark.parametrize("version", [1, 1.0])
def test_raw_main_with_the_number_1_selects_v0_3_1(record, schema, version):
    data = dict(record, schema=schema, schemaVersion=version)
    assert selection.reads_as_fhr1(data)
    assert selection.select_record(data)[:2] == ("FHR", "v0.3.1")
    assert selection.record_file(data) == "schemas/fhr-1.json"
    assert schema_for(data) == FHR1
    assert schema_warnings(data) == [selection.FHR1_WARNING]
    fhr(**data).fhr_validate()
    # The schema value alone still selects the current schema (V1).
    assert selection.select(schema)[:2] == ("FHR", "main")


@pytest.mark.parametrize(
    "schema, version",
    [
        (RAW_MAIN, "1"),  # a string was never valid FHR 1
        (RAW_MAIN, "1.0"),
        (RAW_MAIN, True),  # True == 1 in Python, but it is not a number
        (RAW_MAIN, 1.5),
        (RAW_MAIN, 2),
        (RAW_MAIN, None),
        (RAW_MAIN, "2.0"),
        (f"{RAW}v0.4.0/fhr.json", 1),  # V2
        (f"{W3ID}fhr/v0.4.0", 1),  # V3
        ("https://example.org/my-profile.json", 1),  # V5
        (f"{W3ID}fhr/v0.4.0/fhr.json", 1),  # V5
        (f"{RAW}main/fhp.json", 1),  # FHP and FHGFF3 had no FHR 1 era
        (f"{RAW}main/fhgff3.json", 1),
    ],
)
def test_other_records_select_as_before(schema, version):
    data = {"schema": schema, "schemaVersion": version}
    assert not selection.reads_as_fhr1(data)
    assert schema_warnings(data) == []
    assert selection.select_record(data) == selection.select(schema)


def test_missing_schema_version_selects_as_before():
    assert not selection.reads_as_fhr1({"schema": RAW_MAIN})
    assert selection.select_record({"schema": RAW_MAIN})[:2] == ("FHR", "main")
    assert not selection.reads_as_fhr1(None)
    assert selection.select_record(None)[:2] == ("FHR", "main")


def test_raw_main_string_2_0_is_unchanged(record):
    data = dict(record, schemaVersion="2.0")
    assert schema_for(data) == FHR2
    fhr(**data).fhr_validate()


def test_the_v0_3_1_result_decides(record):
    """The v0.3.1 schema's result is the result: what FHR 1 rejects is invalid."""
    with pytest.raises(ValidationError, match="masking"):
        fhr(**{k: v for k, v in record.items() if k != "masking"}).fhr_validate()
    with pytest.raises(ValidationError, match="'N/A' is not of type 'integer'"):
        fhr(**dict(record, vitalStats={"N50": "N/A"})).fhr_validate()
    with pytest.raises(ValidationError, match="derivedFrom"):
        fhr(**dict(record, derivedFrom=[])).fhr_validate()  # closed at the root
    # FHR 1's nested objects are open, so FHR 2.0 additions there pass v0.3.1, as
    # they did before v0.4.0; v0.3.1 does not check them.
    newer = json.loads(json.dumps(record))
    newer["metadataAuthor"][0]["nameType"] = "Personal"
    newer["vitalStats"]["scaffoldN50"] = "not checked by v0.3.1"
    fhr(**newer).fhr_validate()


@pytest.mark.parametrize("command", ["validate", "convert"])
def test_validate_and_convert_warn_and_follow_v0_3_1(record, tmp_path, command):
    source = write(tmp_path / "in.yaml", record)
    extra = [tmp_path / "out.json"] if command == "convert" else []
    result = run(command, source, *extra)
    assert result.returncode == 0, result.stderr
    assert result.stderr == WARNING + "\n"
    if command == "convert":
        assert json.loads(extra[0].read_text())["schemaVersion"] == 1.0
    write(source, dict(record, vitalStats={"N50": "N/A"}))
    result = run(command, source, *extra)
    assert result.returncode == 1
    assert result.stderr.startswith(WARNING + "\nFHR: schema validation failed at ")


def test_no_warning_for_current_records(record, tmp_path):
    named = dict(record, schemaVersion="2.0")
    result = run("validate", write(tmp_path / "in.yaml", named))
    assert (result.returncode, result.stderr) == (0, "")


@pytest.mark.parametrize("version, line", [(1, b";~schemaVersion: 1\n"), (1.0, b"1.0")])
def test_combine_verify_and_strip_keep_fhr_1(record, tmp_path, version, line):
    """combine keeps the record's schema and schemaVersion; it never upgrades."""
    metadata = write(tmp_path / "metadata.yaml", dict(record, schemaVersion=version))
    (tmp_path / "plain.fa").write_bytes(SEQUENCE)
    out = tmp_path / "out.fhr.fa"
    result = run("combine", metadata, tmp_path / "plain.fa", "-o", out)
    assert result.returncode == 0, result.stderr
    assert result.stderr == WARNING + "\n"
    content = out.read_bytes()
    assert f";~schema: {RAW_MAIN}\n".encode() in content
    assert line in content
    assert content == combine(
        fhr(**dict(record, schemaVersion=version)), SEQUENCE, "fasta"
    )
    result = run("verify", out)
    assert (result.returncode, result.stdout) == (0, "Checksum verified.\n")
    assert result.stderr == WARNING + "\n"
    result = run("strip", out, tmp_path / "again.fa")
    assert (result.returncode, result.stderr) == (0, "")
    assert (tmp_path / "again.fa").read_bytes() == SEQUENCE
    # A changed header now fails its checksum, after the warning.
    out.write_bytes(content.replace(b"soft-masked", b"hard-masked"))
    result = run("verify", out)
    assert result.returncode == 1
    assert result.stderr == WARNING + "\nFHR: Checksum verification failed\n"


def test_verify_links_warns(record, tmp_path):
    path = tmp_path / "genome.fhr.fa"
    path.write_bytes(combine(fhr(**record), SEQUENCE, "fasta"))
    result = run("verify-links", path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == WARNING + "\n"
    assert "no parent files recorded" in result.stdout


def test_old_toolkit_examples_still_validate(tmp_path):
    """FHR 1 files written by the v0.3.1 toolkit, typed microdata included."""
    shown = subprocess.run(
        ["git", "tag", "--list", "v0.3.1"], cwd=ROOT, capture_output=True, text=True
    )
    if "v0.3.1" not in shown.stdout:
        pytest.skip("no v0.3.1 tag in this checkout")
    for name in ("example.fhr.yaml", "example.microdata.fhr.html", "example.fhr.fasta"):
        content = subprocess.run(
            ["git", "show", f"v0.3.1:examples/{name}"], cwd=ROOT, capture_output=True
        ).stdout
        path = tmp_path / name
        path.write_bytes(content)
        result = run("verify" if name.endswith(".fasta") else "validate", path)
        assert result.returncode == 0, (name, result.stderr)
        assert result.stderr == WARNING + "\n"


def _microdata(record, typed):
    page = fhr(**record).output_microdata()
    if not typed:
        page = page.replace(' data-fhr-type="number"', "").replace(
            ' data-fhr-type="integer"', ""
        )
    return page


@pytest.mark.parametrize("typed", [True, False])
@pytest.mark.parametrize("version", [1, 1.0])
def test_microdata_reads_fhr_1(record, typed, version):
    """M3: untyped values take the types of the schema the record selects."""
    data = dict(record, schemaVersion=version)
    page = _microdata(data, typed)
    if not typed:
        assert '<span itemprop="schemaVersion">1' in page
    loaded = fhr()
    loaded.input_microdata(page)
    assert loaded.schemaVersion == 1 and not isinstance(loaded.schemaVersion, str)
    assert loaded.vitalStats == record["vitalStats"]
    loaded.fhr_validate()
    assert schema_warnings(loaded) == [selection.FHR1_WARNING]


def test_untyped_microdata_citing_v0_3_1_reads_a_number(record):
    data = dict(record, schema=f"{W3ID}fhr/v0.3.1", schemaVersion=1)
    loaded = fhr()
    loaded.input_microdata(_microdata(data, typed=False))
    assert loaded.schemaVersion == 1
    loaded.fhr_validate()
    assert schema_warnings(loaded) == []


@pytest.mark.parametrize("version", ["1", "true"])
def test_untyped_microdata_other_versions_stay_strings(record, version):
    page = _microdata(dict(record, schemaVersion=2.0), typed=False).replace(
        '<span itemprop="schemaVersion">2.0</span>',
        f'<span itemprop="schemaVersion">{version}</span>',
    )
    loaded = fhr()
    loaded.input_microdata(page)
    if version == "1":
        assert loaded.schemaVersion == 1  # untyped microdata 1 is the number 1
        loaded.fhr_validate()
    else:
        assert loaded.schemaVersion == "true"
        with pytest.raises(ValidationError):
            loaded.fhr_validate()


def test_untyped_microdata_raw_main_2_0_stays_a_string(record):
    page = _microdata(dict(record, schemaVersion=2.0), typed=False)
    loaded = fhr()
    loaded.input_microdata(page)
    assert loaded.schemaVersion == "2.0"


def test_jsonld_round_trip_keeps_fhr_1(record, tmp_path):
    source = write(tmp_path / "in.yaml", record)
    result = run("convert", source, tmp_path / "out.jsonld")
    assert result.returncode == 0, result.stderr
    document = json.loads((tmp_path / "out.jsonld").read_text())
    assert document["schemaVersion"] == 1
    result = run("convert", tmp_path / "out.jsonld", tmp_path / "back.json")
    assert result.returncode == 0, result.stderr
    assert result.stderr == WARNING + "\n"
    back = json.loads((tmp_path / "back.json").read_text())
    assert back["schema"] == RAW_MAIN and back["schemaVersion"] == 1


def test_assess_reports_v0_3_1(record, tmp_path):
    from bioheaders.assess import assess_file
    from bioheaders.assess.render import _conformance_lines

    path = tmp_path / "genome.fhr.fa"
    path.write_bytes(combine(fhr(**record), SEQUENCE, "fasta"))
    conformance = assess_file(path)["conformance"]
    assert (conformance["result"], conformance["reason"]) == ("valid", None)
    assert conformance["cited_schema"] == RAW_MAIN
    assert conformance["cited_schema_version"] == "1.0"
    assert conformance["schema_used"]["canonical_url"] == f"{RAW}v0.3.1/fhr.json"
    assert conformance["schema_used"]["version"] == "1"
    assert f"warning: {selection.FHR1_WARNING}" in _conformance_lines(conformance)
    current = dict(record, schemaVersion="2.0")
    path.write_bytes(combine(fhr(**current), SEQUENCE, "fasta"))
    conformance = assess_file(path)["conformance"]
    assert conformance["schema_used"]["canonical_url"] == RAW_MAIN
    assert not any("warning" in line for line in _conformance_lines(conformance))


def test_numeric_string_field_hint(record, tmp_path):
    source = write(tmp_path / "in.yaml", dict(record, schemaVersion="2.0"))
    source.write_text(source.read_text().replace("version: 0.0.1", "version: 6.67"))
    result = run("validate", source)
    assert result.returncode == 1
    assert result.stderr == (
        "FHR: schema validation failed at $.version: 6.67 is not of type 'string'; "
        "quote the value exactly as written to keep it a string\n"
    )
    # schemaVersion gets no quoting hint: the fix there is the version.
    write(source, dict(record, schema=f"{W3ID}fhr/v0.4.0", schemaVersion=2.0))
    result = run("validate", source)
    assert "quote" not in result.stderr


@pytest.mark.parametrize("schema", [RAW_MAIN, f"{W3ID}fhr/v0.3.1"])
@pytest.mark.parametrize("text", ["1", "1.0"])
def test_typed_string_microdata_schema_version_stays_a_string(record, schema, text):
    """M3: data-fhr-type="string" keeps the value exactly, so V6 does not apply."""
    page = _microdata(dict(record, schema=schema, schemaVersion=1), typed=True)
    page = page.replace(
        '<span itemprop="schemaVersion" data-fhr-type="integer">1</span>',
        f'<span itemprop="schemaVersion" data-fhr-type="string">{text}</span>',
    )
    assert 'data-fhr-type="string">1' in page
    loaded = fhr()
    loaded.input_microdata(page)
    assert loaded.schemaVersion == text and loaded.schemaVersion.__class__ is str
    assert schema_warnings(loaded) == []
    with pytest.raises(ValidationError):
        loaded.fhr_validate()
