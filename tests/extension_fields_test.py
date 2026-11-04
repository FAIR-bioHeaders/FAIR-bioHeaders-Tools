# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Extension fields: top-level ``x-`` keys (FAIR-bioHeaders-Specification FORMAT.md R15).

FHR 2.1 and FHP and FHGFF3 1.1 (specification release v0.5.0) accept them; a record
that states the older minor or cites a v0.4.x schema does not. JSON-LD, the
schema.org export and microdata carry none (rules J9 and M5).
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema.exceptions import ValidationError

from bioheaders import (
    NonFiniteValueError,
    extensions,
    fhp_microdata,
    fhr,
    jsonld,
    load_yaml,
    schema_for,
    selection,
    validation_message,
)
from bioheaders.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
W3ID = "https://w3id.org/fair-bioheaders/"
RAW_MAIN = "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/"
BODIES = {
    "fasta": b">chr1 one\nACGTACGTAC\n>chr2 two\nGGGGCCCCAA\n",
    "gfa": b"H\tVN:Z:1.0\nS\tchr1\tACGTACGTAC\n",
    "gff3": b"##gff-version 3\nctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n",
}
# Header type: (example record, the older minor, the new minor, container)
TYPES = {
    "FHR": ("examples/example.fhr.json", "2.0", "2.1", "fasta"),
    "FHP": ("examples/fhp/minimal-predicted.fhp.json", "1.0", "1.1", "fasta"),
    "FHGFF3": ("examples/fhgff3/minimal-reference.fhgff3.json", "1.0", "1.1", "gff3"),
}
SEGMENT = {"FHR": "fhr", "FHP": "fhp", "FHGFF3": "fhgff3"}
VALID_KEYS = ["x-a", "x-1", "x-refget-commonName", "x-a.b-c_d", "x-A", "x-genome"]
INVALID_KEYS = [
    "genom", "X-a", "x-", "x--a", "x-_a", "x-.a", "x- a", "x-a b", "x-a ", " x-a",
    "x-ä", "x-K", "x-ａ", "ｘ-a", "x-a\n", "x-a\r", "x-a\r\n",
    "x-a\t", "x-a ", "x-a:b", "x-a@b", "x-a>b", "x-a#b", "x-a/b", "xa", "x_a",
    "ext-a", "x-a\x00",
]  # fmt: skip
VALUES = [
    "text", 1, 1.5, True, None, [], {}, [1, "a", {"b": None}],
    {"@context": {"@vocab": "https://example.org/"}, "@id": "https://example.org/x"},
    "</script><script>alert(1)</script> & more",
    "contigs > 1000 bp, someone@example.org",
    "line one\nchecksum: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n;~schema: x",
    ["- item", "key: value", "&anchor", "*alias", "!tag", "yes", "1.0", "010", "null",
     "~", "", " lead", "trail ", "#hash", "{a: b}", "[1]", "'", '"'],
]  # fmt: skip


def record(header_type, version=None, schema=None, **extra):
    path, _, new, _ = TYPES[header_type]
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    data["schemaVersion"] = new if version is None else version
    if schema is not None:
        data["schema"] = schema
    data.update(copy.deepcopy(extra))
    return data


def valid(data):
    try:
        fhr(**copy.deepcopy(data)).fhr_validate()
    except (ValidationError, ValueError):
        return False
    return True


def run(*args, stdin=None):
    return subprocess.run(
        [str(arg) for arg in args], capture_output=True, text=True, input=stdin
    )


# Validation by version and schema URL.


@pytest.mark.parametrize("header_type", TYPES)
def test_new_minor_accepts_extension_fields(header_type):
    for key in VALID_KEYS:
        for value in VALUES:
            data = record(header_type, **{key: value})
            assert valid(data), (key, value)


@pytest.mark.parametrize("header_type", TYPES)
def test_older_minor_rejects_extension_fields(header_type):
    _, old, _, _ = TYPES[header_type]
    assert valid(record(header_type, old))
    data = record(header_type, old, **{"x-a": 1})
    with pytest.raises(ValidationError) as error:
        fhr(**data).fhr_validate()
    message = validation_message(error.value)
    assert message.startswith("x-a: extension fields (x- keys) are not allowed")
    assert "FORMAT.md R15" in message


@pytest.mark.parametrize("header_type", TYPES)
@pytest.mark.parametrize("release", ["v0.4.0", "v0.4.1", "v0.4.2"])
def test_older_releases_select_their_schemas(header_type, release):
    """V2/V3: a record citing v0.4.x is checked against FHR 2.0 / FHP and FHGFF3 1.0."""
    _, old, new, _ = TYPES[header_type]
    schema = f"{W3ID}{SEGMENT[header_type]}/{release}"
    assert selection.select(schema)[1] == release
    assert schema_for({"schema": schema})["properties"]["schemaVersion"]["enum"] == [
        old
    ]
    assert valid(record(header_type, old, schema))
    assert not valid(record(header_type, old, schema, **{"x-a": 1}))
    assert not valid(record(header_type, new, schema, **{"x-a": 1}))
    assert not valid(record(header_type, new, schema))


@pytest.mark.parametrize("header_type", TYPES)
def test_raw_main_selects_the_new_minor(header_type):
    _, old, new, _ = TYPES[header_type]
    schema = f"{RAW_MAIN}{SEGMENT[header_type]}.json"
    enum = schema_for({"schema": schema})["properties"]["schemaVersion"]["enum"]
    assert enum == [old, new]
    assert valid(record(header_type, new, schema, **{"x-a": 1}))
    assert valid(record(header_type, old, schema))
    assert not valid(record(header_type, old, schema, **{"x-a": 1}))


def test_v0_5_0_is_bundled_and_current():
    assert selection.BUNDLED["current"]["release"] == "v0.5.0"
    for header_type, (_, _, new, _) in TYPES.items():
        kind, ref, schema = selection.select(f"{W3ID}{SEGMENT[header_type]}/v0.5.0")
        assert (kind, ref) == (header_type, "v0.5.0")
        assert schema["properties"]["schemaVersion"]["enum"][-1] == new
        assert list(schema["patternProperties"]) == [r"^x-[A-Za-z0-9][A-Za-z0-9_.-]*$"]


def test_fhr_1_records_are_unaffected():
    """V6 still reads raw-main schemaVersion 1 as v0.3.1, which has no extensions."""
    data = record("FHR", 1, f"{RAW_MAIN}fhr.json")
    data["metadataAuthor"][0].pop("nameType")
    data.pop("vitalStats")  # v0.3.1 has no scaffold statistics; keep it simple
    assert selection.select_record(data)[1] == "v0.3.1"
    assert not valid(dict(data, **{"x-a": 1}))


# Keys.


@pytest.mark.parametrize("header_type", TYPES)
@pytest.mark.parametrize("key", INVALID_KEYS, ids=repr)
def test_malformed_and_unknown_keys_stay_invalid(header_type, key):
    _, old, new, _ = TYPES[header_type]
    for version in (old, new):
        assert not valid(record(header_type, version, **{key: "value"}))


def test_unknown_key_message_names_the_key():
    data = record("FHR", **{"genom": "typo", "x-ok": 1})
    with pytest.raises(ValidationError) as error:
        fhr(**data).fhr_validate()
    message = validation_message(error.value)
    assert message.startswith("unknown field 'genom': not a field of this schema")
    assert "x-ok" not in message


def test_line_feed_message():
    data = record("FHR", **{"x-a\n": 1})
    with pytest.raises(ValidationError) as error:
        fhr(**data).fhr_validate()
    assert validation_message(error.value) == (
        "the key 'x-a\\n' contains a line feed "
        "(FAIR-bioHeaders-Specification docs/FORMAT.md R15)"
    )


@pytest.mark.parametrize("header_type", TYPES)
def test_nested_objects_stay_closed(header_type):
    data = record(header_type)
    data["taxon"]["x-a"] = 1
    assert not valid(data)
    data = record(header_type)
    data["metadataAuthor"][0]["x-a"] = 1
    assert not valid(data)


def test_extension_keys_helper():
    data = {"x-a": 1, "genome": "g", "x-": 2, "X-b": 3, 5: 6}
    assert extensions.extension_keys(data) == ["x-a", "x-"]
    assert extensions.without_extensions(data) == {"genome": "g", "X-b": 3, 5: 6}
    assert extensions.extension_keys(["x-a"]) == []


# R8, R11, R12 and R13 apply to extension keys and values.


def test_yaml_rules_apply_to_extension_values():
    base = "schemaVersion: '2.1'\n"
    with pytest.raises(Exception, match="YAML 1.1 and YAML 1.2"):
        load_yaml(base + "x-a: yes\n")
    with pytest.raises(Exception, match="YAML 1.1 and YAML 1.2"):
        load_yaml(base + "x-a: [010]\n")
    with pytest.raises(Exception, match="duplicate key"):
        load_yaml(base + "x-a: 1\nx-a: 2\n")
    with pytest.raises(Exception, match="anchors and aliases"):
        load_yaml(base + "x-a: &one 1\nx-b: *one\n")
    with pytest.raises(Exception, match="tags"):
        load_yaml(base + "x-a: !!binary aGk=\n")
    assert load_yaml(base + "x-a: 'yes'\n")["x-a"] == "yes"


def test_nonfinite_extension_values_are_invalid():
    for value in (float("nan"), float("inf"), [float("-inf")], {"a": float("nan")}):
        with pytest.raises(NonFiniteValueError, match="x-a"):
            fhr(**record("FHR", **{"x-a": value})).fhr_validate()
    data = fhr()
    with pytest.raises(NonFiniteValueError):
        data.input_yaml("x-a: .nan\n")


@pytest.mark.parametrize("value", VALUES, ids=repr)
def test_fasta_header_round_trip_and_escaping(value):
    data = record("FHR", **{"x-first": "a", "x-value": value})
    combined = combine(fhr(**data), BODIES["fasta"], "fasta")
    lines = [line for line in combined.split(b"\n") if line.startswith(b";~")]
    assert not any(b">" in line or b"@" in line for line in lines)  # R11
    assert [line for line in lines if line.startswith(b";~checksum:")] == [
        lines[[line.startswith(b";~checksum:") for line in lines].index(True)]
    ]
    read = fhr()
    read.input_fasta(combined)
    read.fhr_validate()
    expected = dict(data, checksum=checksum(combined, "fasta"))
    assert read.__dict__ == expected
    assert list(read.__dict__) == list(expected)
    assert strip_header(combined, "fasta") == BODIES["fasta"]


@pytest.mark.parametrize("header_type", TYPES)
def test_combine_verify_strip_round_trips(header_type, tmp_path):
    _, _, _, kind = TYPES[header_type]
    containers = ["fasta", "gfa"] if header_type == "FHR" else [kind]
    for kind in containers:
        data = record(
            header_type, **{"x-example-note": "kept", "x-example-list": [1, None]}
        )
        metadata = tmp_path / f"metadata-{kind}.yaml"
        metadata.write_text(yaml.safe_dump(data, sort_keys=False))
        source = tmp_path / f"plain.{kind}"
        source.write_bytes(BODIES[kind])
        headed = tmp_path / f"headed.{kind}"
        result = run(BIN / "bioheaders", "combine", metadata, source, "-o", headed)
        assert result.returncode == 0, result.stderr
        assert run(BIN / "bioheaders", "verify", headed).returncode == 0
        out = tmp_path / f"metadata-{kind}.json"
        assert run(BIN / "bioheaders", "convert", headed, out).returncode == 0
        converted = json.loads(out.read_text())
        assert converted["x-example-note"] == "kept"
        assert converted["x-example-list"] == [1, None]
        assert [key for key in converted if key.startswith("x-")] == [
            "x-example-note",
            "x-example-list",
        ]
        assert list(converted)[: len(data)] == list(data)
        plain = tmp_path / f"stripped.{kind}"
        assert run(BIN / "bioheaders", "strip", headed, plain).returncode == 0
        assert plain.read_bytes() == BODIES[kind]
        # Tampering with an extension value breaks the checksum.
        tampered = tmp_path / f"tampered.{kind}"
        tampered.write_bytes(headed.read_bytes().replace(b"kept", b"kapt"))
        assert run(BIN / "bioheaders", "verify", tampered).returncode == 1


def test_combine_rejects_an_injected_key(tmp_path):
    data = record("FHR", **{"x-a\n;~checksum: AAAA": 1})
    with pytest.raises(ValidationError):
        combine(fhr(**data), BODIES["fasta"], "fasta")


def test_older_minor_combine_fails_with_the_readable_message(tmp_path):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(record("FHR", "2.0", **{"x-a": 1})))
    source = tmp_path / "plain.fa"
    source.write_bytes(BODIES["fasta"])
    result = run(
        BIN / "bioheaders", "combine", metadata, source, "-o", tmp_path / "o.fa"
    )
    assert result.returncode == 1
    assert "x-a: extension fields (x- keys) are not allowed" in result.stderr


# JSON-LD, the export and microdata carry no extension fields (J9, M5).

EXTENDED = {
    "x-first": {"@context": {"@vocab": "https://extension.invalid/"}, "@id": "_:x"},
    "x-script": "</script><script>alert(1)</script>",
    "x-list": [{"@type": "Person"}, "&"],
}


def assert_no_extension(text):
    for key, value in EXTENDED.items():
        assert key not in text
    assert "extension.invalid" not in text and "alert(1)" not in text


def test_jsonld_writers_leave_extension_fields_out():
    base = record("FHR")
    data = dict(base, **EXTENDED)
    canonical = fhr(**data).output_jsonld()
    assert canonical == fhr(**base).output_jsonld()
    assert_no_extension(canonical)
    assert_no_extension(jsonld.script_element(json.loads(canonical)))
    export = fhr(**data).output_jsonld(profile="export")
    assert export == fhr(**base).output_jsonld(profile="export")
    assert_no_extension(export)
    read = fhr()
    read.input_jsonld(canonical)
    assert read.__dict__ == base


def test_fhp_jsonld_and_microdata_writers_leave_extension_fields_out():
    base = record("FHP")
    data = dict(base, **EXTENDED)
    assert fhr(**data).output_jsonld() == fhr(**base).output_jsonld()
    page = fhr(**data).output_microdata()
    assert page == fhr(**base).output_microdata()
    assert_no_extension(page)


def test_microdata_writer_leaves_extension_fields_out():
    base = record("FHR")
    page = fhr(**dict(base, **EXTENDED)).output_microdata()
    assert page == fhr(**base).output_microdata()
    assert_no_extension(page)


def test_jsonld_readers_reject_extension_fields():
    document = json.loads(fhr(**record("FHR")).output_jsonld())
    with pytest.raises(ValueError, match="JSON-LD carries no extension fields"):
        fhr().input_jsonld(json.dumps(dict(document, **{"x-a": 1})))
    # Any key with the prefix, valid in JSON or not.
    with pytest.raises(ValueError, match="J9"):
        fhr().input_jsonld(json.dumps(dict(document, **{"x-": 1})))
    fhp = json.loads(fhr(**record("FHP")).output_jsonld())
    with pytest.raises(ValueError, match="J9"):
        fhr().input_jsonld(json.dumps(dict(fhp, **{"x-a": 1})))


def test_jsonld_lenient_reading_drops_them_with_a_warning():
    document = json.loads(fhr(**record("FHR")).output_jsonld())
    warnings = []
    read = jsonld.from_jsonld(
        dict(document, **{"x-a": 1}), ignore_unknown_terms=True, warn=warnings.append
    )
    assert "x-a" not in read
    assert warnings and "x-a" in warnings[0]


def test_general_jsonld_with_an_extension_key_is_invalid():
    pytest.importorskip("pyld")
    document = json.loads(fhr(**record("FHR")).output_jsonld())
    document["@context"] = [document["@context"]]  # not canonical: read by expansion
    with pytest.raises(ValueError, match="J9"):
        jsonld.from_jsonld(dict(document, **{"x-a": 1}))


def test_microdata_readers_reject_extension_fields():
    base = record("FHR")
    page = fhr(**base).output_microdata()
    extended = page.replace(
        "</div>",
        '<span itemprop="x-refget-commonName" data-fhr-type="string">human</span></div>',
        1,
    )
    with pytest.raises(ValueError, match="M5"):
        fhr().input_microdata(extended)
    fhp = fhr(**record("FHP")).output_microdata()
    extended = fhp.replace(
        "</div>",
        '<span itemprop="x-a" data-fhr-type="string">v</span></div>',
        1,
    )
    with pytest.raises(fhp_microdata.MicrodataError, match="M5"):
        fhr().input_microdata(extended)


def test_convert_warns_about_extension_fields_left_out(tmp_path):
    source = tmp_path / "metadata.json"
    source.write_text(json.dumps(record("FHR", **{"x-a": 1, "x-b": "two"})))
    for name, options, form in (
        ("out.jsonld", [], "JSON-LD"),
        ("export.jsonld", ["--jsonld-profile", "export"], "the schema.org export"),
        ("out.html", [], "HTML microdata"),
    ):
        out = tmp_path / name
        result = run(BIN / "bioheaders", "convert", source, out, *options)
        assert result.returncode == 0, result.stderr
        assert (
            f"FHR: warning: extension fields are not written to {form}: x-a, x-b"
            in result.stderr
        )
        assert "x-a" not in out.read_text()
    out = tmp_path / "out.yaml"
    result = run(BIN / "bioheaders", "convert", source, out)
    assert result.returncode == 0 and "warning" not in result.stderr
    assert yaml.safe_load(out.read_text())["x-b"] == "two"
