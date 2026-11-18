# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""``pattern`` and ``format: date`` as JSON Schema 2020-12 defines them.

``pattern`` is an ECMA-262 regular expression, where ``$`` (without the ``m``
flag) matches only at the end of the string; Python's ``$`` also matches before a
final newline. ``format: date`` is RFC 3339 ``full-date``, whose year is any four
digits, 0000 included; Python's ``date`` starts at year 1.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import ValidationError

from bioheaders import fhr, schema_validator

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent


@pytest.fixture
def record():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("^a$", r"^a\Z"),
        (r"^a\$$", r"^a\$\Z"),
        ("^[$]$", r"^[$]\Z"),
        (r"^[\]$]+$", r"^[\]$]+\Z"),
        ("^(a|b)$|^c$", r"^(a|b)\Z|^c\Z"),
        ("no anchors", "no anchors"),
    ],
)
def test_dollar_is_end_of_string_only(pattern, expected):
    assert schema_validator.ecma_pattern(pattern).pattern == expected


@pytest.mark.parametrize(
    "pattern,text,expected",
    [
        ("[]", "", False),
        ("[]", "]a$", False),
        ("[]a$]", "a", False),
        ("[]]$", "]", False),
        ("[^]$]", "]", False),
        ("[^]", "", False),
        ("[^]", "\n", True),
        ("^[^]$", "\n", True),
        ("^[^]$", "a\n", False),
        ("[]*", "", True),
        ("^[\\]$]+$", "]$", True),
    ],
)
def test_empty_classes_keep_ecma_semantics(pattern, text, expected):
    assert bool(schema_validator.ecma_pattern(pattern).search(text)) is expected


def test_empty_class_translation_agrees_with_ecmascript():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is an optional independent regex oracle")
    patterns = ["[]", "[^]", "[]a$]", "[]]$", "[^]$]", "^[^]$", "[]*"]
    strings = ["", "a", "]", "$", "]a$", "\n", "a\n"]
    script = (
        "const p=JSON.parse(process.argv[1]),s=JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(p.map(r=>s.map(t=>new RegExp(r).test(t)))));"
    )
    actual = subprocess.run(
        [node, "-e", script, json.dumps(patterns), json.dumps(strings)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(actual.stdout) == [
        [bool(schema_validator.ecma_pattern(p).search(s)) for s in strings]
        for p in patterns
    ]


def test_unsupported_regex_fails_as_a_validation_error():
    # ECMA named capture syntax is outside this bounded Python adapter.
    schema = {"type": "object", "properties": {"value": {"pattern": "(?<x>a)"}}}
    errors = list(schema_validator.validator(schema).iter_errors({"value": "a"}))
    assert len(errors) == 1
    assert list(errors[0].path) == ["value"]
    assert errors[0].validator == "pattern"
    assert "cannot evaluate contract pattern" in errors[0].message
    assert "bounded Python translation" in errors[0].message


@pytest.mark.parametrize("field", ["masking"])
@pytest.mark.parametrize("suffix", ["\n", "\r\n", " "])
def test_trailing_newline_fails_a_pattern(record, field, suffix):
    record[field] = record[field] + suffix
    with pytest.raises(ValidationError, match="does not match"):
        fhr(**record).fhr_validate()


def test_trailing_newline_fails_from_the_cli(record, tmp_path):
    record["masking"] = "not-masked\n"
    path = tmp_path / "nl.fhr.json"
    path.write_text(json.dumps(record))
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", path], capture_output=True, text=True
    )
    assert result.returncode == 1 and "$.masking" in result.stderr


def test_values_that_matched_still_match(record):
    fhr(**record).fhr_validate()


@pytest.mark.parametrize("value", ["0000-01-01", "0000-02-29", "9999-12-31"])
def test_rfc3339_dates_from_year_0000_are_valid(record, value):
    record["dateCreated"] = value
    fhr(**record).fhr_validate()


@pytest.mark.parametrize(
    "value",
    [
        "0001-02-29",
        "1900-02-29",
        "2026-02-30",
        "2026-13-01",
        "26-01-01",
        "2026-01-01\n",
    ],
)
def test_impossible_or_malformed_dates_are_invalid(record, value):
    record["dateCreated"] = value
    with pytest.raises(ValidationError, match="is not a 'date'"):
        fhr(**record).fhr_validate()
