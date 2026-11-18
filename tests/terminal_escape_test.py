# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Values read from an input never reach the terminal raw.

A ``schema`` value can carry terminal escape sequences (``ESC [2J`` clears the
screen, ``ESC ]0;…BEL`` retitles the window) and bidirectional overrides (U+202E).
The rule V4 message, the assess "cited schema:" line and every header line that
assess cites verbatim show them escaped, as the near-miss warning has since #174
(``selection.shown`` and ``selection.escape_controls``).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import selection

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
HOSTILE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/"
    "\x1b[2J\x1b]0;owned\x07‮X/fhr.json"
)
RAW = ("\x1b", "\x07", "‮")


@pytest.fixture(autouse=True)
def _lane_closed(monkeypatch):
    monkeypatch.delenv(selection.DRAFT_ENV, raising=False)


def run(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def assert_clean(text):
    for raw in RAW:
        assert raw not in text, f"{raw!r} reached the output"


@pytest.fixture
def fasta(tmp_path):
    path = tmp_path / "ansi.fa"
    path.write_text(
        f';~schema: {json.dumps(HOSTILE)}\n;~schemaVersion: "2.1"\n>c\nACGT\n',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def record(tmp_path):
    data = json.loads((ROOT / "examples/example.fhr.json").read_text())
    data["schema"] = HOSTILE
    path = tmp_path / "ansi.fhr.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_helpers_escape_controls_and_bidi():
    assert selection.shown(HOSTILE) == repr(HOSTILE)
    assert_clean(selection.shown(HOSTILE))
    escaped = selection.escape_controls("a\x1b[31mb‮c\x00d\te\nf​g")
    assert escaped == "a\\x1b[31mb\\u202ec\\x00d\te\nf\\u200bg"
    assert selection.escape_controls("plain ‘text’ é") == "plain ‘text’ é"


def test_unsupported_message_is_escaped():
    with pytest.raises(selection.UnsupportedSchemaVersion) as error:
        selection.select(HOSTILE)
    assert_clean(str(error.value))
    assert "\\x1b[2J" in str(error.value)


@pytest.mark.parametrize("command", ["validate", "verify"])
def test_fasta_commands_escape_the_schema(command, fasta):
    result = run(command, fasta)
    assert result.returncode == 1
    assert "unsupported schema version" in result.stderr
    assert_clean(result.stdout + result.stderr)
    assert "\\u202e" in result.stderr


def test_json_input_escapes_the_schema(record):
    result = run("validate", record)
    assert result.returncode == 1
    assert "unsupported schema version" in result.stderr
    assert_clean(result.stdout + result.stderr)


@pytest.mark.parametrize("form", ["text", "markdown"])
def test_assess_cited_schema_is_escaped(form, fasta):
    result = run("assess", "--format", form, fasta)
    assert_clean(result.stdout + result.stderr)
    assert "cited schema: " in result.stdout
    assert "\\u202e" in result.stdout


@pytest.mark.parametrize("form", ["text", "markdown"])
def test_assess_cited_lines_are_escaped(form, tmp_path):
    path = tmp_path / "raw.vcf"
    path.write_bytes(
        b"##fileformat=VCFv4.3\n##source=ev\x1b[2Jil\x1b]0;t\x07\n"
        b"##reference=file:///x\x1b[31m.fa\n"
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    )
    result = run("assess", "--format", form, path)
    assert result.returncode == 0, result.stderr
    assert_clean(result.stdout + result.stderr)
    assert "x1b" in result.stdout
