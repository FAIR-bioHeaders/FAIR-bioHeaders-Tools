# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Explicit R13 finite-number checks and empty required-value warnings (#92, #93)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import fhr, required_value_warnings

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent

# A complete record of each header type, with a nested value R13 can target.
RECORDS = {
    "FHR": (
        "examples/example.fhr.json",
        ("vitalStats", "gcContent"),
        "vitalStats.gcContent",
    ),
    "FHP": (
        "examples/fhp/rich-predicted.fhp.yaml",
        ("completeness", "total"),
        "completeness.total",
    ),
    "FHGFF3": (
        "examples/fhgff3/rich.fhgff3.yaml",
        ("featureCounts", 0, "count"),
        "featureCounts[0].count",
    ),
}


def run(*args):
    return subprocess.run([str(arg) for arg in args], capture_output=True, text=True)


def command(*args):
    return run(BIN / "bioheaders", *args)


def load_record(kind):
    path = ROOT / RECORDS[kind][0]
    text = path.read_text(encoding="utf-8")
    return (
        yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)
    )


def set_path(record, path, value):
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def write_metadata(path, record):
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


# R13: NaN and infinities are explicit errors, not JSON serialisation errors.


@pytest.mark.parametrize("kind", RECORDS)
@pytest.mark.parametrize(
    "value, yaml_text",
    [(float("nan"), ".nan"), (float("inf"), ".inf"), (float("-inf"), "-.inf")],
    ids=["nan", "inf", "-inf"],
)
def test_cli_rejects_nonfinite_yaml_values(kind, value, yaml_text, tmp_path):
    record = load_record(kind)
    path = RECORDS[kind][1]
    set_path(record, path, value)
    metadata = write_metadata(tmp_path / "metadata.yaml", record)
    assert yaml_text in metadata.read_text(encoding="utf-8")
    result = command("validate", metadata)
    assert result.returncode == 1
    assert result.stderr == (
        f"{kind}: {RECORDS[kind][2]} is not a finite number (FORMAT.md R13)\n"
    )
    assert "Traceback" not in result.stderr
    assert "JSON compliant" not in result.stderr


@pytest.mark.parametrize("kind", RECORDS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_direct_nonfinite_float_values_are_rejected(kind, value):
    record = load_record(kind)
    set_path(record, RECORDS[kind][1], value)
    with pytest.raises(ValueError) as caught:
        fhr(**record).fhr_validate()
    assert str(caught.value) == (
        f"{kind}: {RECORDS[kind][2]} is not a finite number (FORMAT.md R13)"
    )


@pytest.mark.parametrize("kind", RECORDS)
def test_finite_values_are_valid(kind, tmp_path):
    record = load_record(kind)
    set_path(record, RECORDS[kind][1], 1)
    metadata = write_metadata(tmp_path / "metadata.yaml", record)
    result = command("validate", metadata)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    fhr(**record).fhr_validate()


# Empty required values: warn, keep exit status 0, and name the field.


CASES = [
    ("FHR", ("genome",), "", "required value genome is empty"),
    ("FHR", ("metadataAuthor",), [], "required value metadataAuthor is empty"),
    ("FHR", ("assemblyAuthor",), [], "required value assemblyAuthor is empty"),
    ("FHR", ("taxon",), {}, "required value taxon is empty"),
    (
        "FHR",
        ("metadataAuthor",),
        [{"uri": "https://orcid.org/0000-0002-5719-4024"}],
        "required value metadataAuthor[0].name is empty",
    ),
    (
        "FHR",
        ("assemblyAuthor",),
        [{"name": ""}],
        "required value assemblyAuthor[0].name is empty",
    ),
    (
        "FHR",
        ("taxon",),
        {"name": ""},
        "required value taxon has neither name nor uri",
    ),
    (
        "FHR",
        ("assemblySoftware",),
        [{"name": ""}],
        "required value assemblySoftware[0].name is empty",
    ),
    ("FHP", ("proteome",), "", "required value proteome is empty"),
    ("FHP", ("metadataAuthor",), [], "required value metadataAuthor is empty"),
    ("FHP", ("taxon",), {}, "required value taxon is empty"),
    (
        "FHP",
        ("metadataAuthor",),
        [{"name": ""}],
        "required value metadataAuthor[0].name is empty",
    ),
    (
        "FHP",
        ("taxon",),
        {"name": ""},
        "required value taxon has neither name nor uri",
    ),
    (
        "FHP",
        ("predictionSoftware", 0, "name"),
        "",
        "required value predictionSoftware[0].name is empty",
    ),
    ("FHGFF3", ("annotation",), "", "required value annotation is empty"),
    (
        "FHGFF3",
        ("metadataAuthor",),
        [],
        "required value metadataAuthor is empty",
    ),
    ("FHGFF3", ("taxon",), {}, "required value taxon is empty"),
    (
        "FHGFF3",
        ("metadataAuthor",),
        [{"name": ""}],
        "required value metadataAuthor[0].name is empty",
    ),
    (
        "FHGFF3",
        ("taxon",),
        {"name": ""},
        "required value taxon has neither name nor uri",
    ),
    (
        "FHGFF3",
        ("annotationSoftware", 0, "name"),
        "",
        "required value annotationSoftware[0].name is empty",
    ),
]


@pytest.mark.parametrize(
    "kind, path, value, expected",
    CASES,
    ids=[f"{case[0]}-{case[3]}" for case in CASES],
)
def test_validate_warns_about_an_empty_required_value(
    kind, path, value, expected, tmp_path
):
    record = load_record(kind)
    set_path(record, path, value)
    assert required_value_warnings(record) == [expected]
    metadata = write_metadata(tmp_path / "metadata.yaml", record)
    result = command("validate", metadata)
    assert result.returncode == 0
    assert result.stdout == f"{kind} metadata is valid.\n"
    assert result.stderr == f"{kind}: warning: {expected}\n"


@pytest.mark.parametrize("kind", RECORDS)
def test_complete_records_emit_no_required_value_warnings(kind):
    record = load_record(kind)
    assert required_value_warnings(record) == []
    result = command("validate", ROOT / RECORDS[kind][0])
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_combine_and_verify_warn_once_for_an_empty_required_value(tmp_path):
    record = load_record("FHR")
    record["genome"] = ""
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(record), encoding="utf-8")
    sequence = tmp_path / "genome.fasta"
    sequence.write_bytes(b">ctg\nACGT\n")
    output = tmp_path / "genome.fhr.fasta"
    expected = "FHR: warning: required value genome is empty\n"

    result = command("combine", metadata, sequence, "-o", output)
    assert result.returncode == 0, result.stderr
    assert result.stderr == expected

    result = command("verify", output)
    assert result.returncode == 0, result.stderr
    assert result.stderr == expected

    result = command("validate", output)
    assert result.returncode == 0, result.stderr
    assert result.stderr == expected
