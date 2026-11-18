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
