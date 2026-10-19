"""FASTA record markers in FHR header values (FAIR-bioHeaders-Specification FORMAT.md R11).

kseq-based FASTA readers start a record at a '>' or '@' anywhere in a line, so FASTA
header writers escape them as \\x3E and \\x40 in double-quoted YAML scalars. YAML
readers return the characters, so every other format holds them unchanged.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import fhr, load_yaml
from bioheaders.cli import checksum, combine

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
BODY = b">chr1 one\nACGTACGTAC\n>chr2 two\nGGGGCCCCAA\n"
DOCUMENTATION = "contact someone@example.org; contigs > 1000 bp"


def run(*args):
    return subprocess.run([str(arg) for arg in args], capture_output=True, text=True)


def header_lines(data):
    return [line for line in data.split(b"\n") if line.startswith(b";~")]


@pytest.fixture()
def metadata():
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    record["documentation"] = DOCUMENTATION
    record["metadataAuthor"][0]["name"] = "Name <a@b>"
    return record


def test_combine_escapes_record_markers(metadata):
    combined = combine(fhr(**metadata), BODY, "fasta")
    lines = header_lines(combined)
    assert not any(b">" in line or b"@" in line for line in lines)
    assert (
        b';~documentation: "contact someone\\x40example.org; contigs \\x3E 1000 bp"'
        in lines
    )
    data = fhr()
    data.input_fasta(combined)
    data.fhr_validate()
    assert data.documentation == DOCUMENTATION
    assert data.metadataAuthor[0]["name"] == "Name <a@b>"
    assert data.checksum == checksum(combined, "fasta")


def test_round_trip_fasta_json_fasta(metadata):
    combined = combine(fhr(**metadata), BODY, "fasta")
    data = fhr()
    data.input_fasta(combined)
    text = data.output_json()
    assert "someone@example.org" in text and "> 1000" in text
    again = fhr()
    again.input_json(text)
    assert again.output_fasta() == data.output_fasta()
    assert combine(again, BODY, "fasta") == combined


def test_other_formats_hold_the_characters(metadata):
    data = fhr(**metadata)
    assert "someone@example.org" in data.output_yaml()
    for kind in ("gfa", "gff3"):
        text = getattr(data, "output_" + kind)()
        assert "someone@example.org" in text and "\\x40" not in text


def test_output_unchanged_without_record_markers():
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    data = fhr(**record)
    expected = "".join(
        ";~" + line + "\n" for line in data.output_yaml().split("\n") if line != ""
    )
    assert data.output_fasta() == expected


@pytest.mark.parametrize(
    "value",
    [
        "line one\nline two with a > sign",
        "x" * 150 + " someone@example.org " + "y" * 150,
        "a@b c>d",
        "@starts with an indicator",
        "> also an indicator",
        'back\\slash @ and "quotes" >',
    ],
)
def test_escaped_values_read_back(value):
    data = fhr(documentation=value, **{"key@": "value>"})
    text = data.output_fasta()
    assert ">" not in text and "@" not in text
    loaded = load_yaml("\n".join(line[2:] for line in text.splitlines()))
    assert loaded == {"documentation": value, "key@": "value>"}
    assert yaml.safe_load("\n".join(line[2:] for line in text.splitlines())) == loaded


def raw_marker_file(metadata, tmp_path):
    """A FASTA file whose header holds a raw '@', with a correct checksum."""
    combined = combine(fhr(**metadata), BODY, "fasta")
    raw = combined.replace(
        b'"contact someone\\x40example.org; contigs \\x3E 1000 bp"',
        b"contact someone@example.org",
    )
    data = fhr()
    data.input_fasta(raw)
    raw = raw.replace(data.checksum.encode(), checksum(raw, "fasta").encode())
    path = tmp_path / "raw.fhr.fa"
    path.write_bytes(raw)
    return path


def test_validate_warns_on_raw_record_marker(metadata, tmp_path):
    path = raw_marker_file(metadata, tmp_path)
    for command in (
        [BIN / "fhr-fasta-validate", path],
        [BIN / "bioheaders", "verify", path],
        [BIN / "bioheaders", "validate", path],
    ):
        result = run(*command)
        assert result.returncode == 0, (command, result.stderr)
        assert "contains a raw '@'" in result.stderr, command
        assert "FORMAT.md R11" in result.stderr


def test_no_warning_for_escaped_file(metadata, tmp_path):
    path = tmp_path / "escaped.fhr.fa"
    path.write_bytes(combine(fhr(**metadata), BODY, "fasta"))
    result = run(BIN / "fhr-fasta-validate", path)
    assert result.returncode == 0 and "warning" not in result.stderr


def test_fhp_combine_escapes_record_markers():
    record = json.loads((ROOT / "examples/fhp/minimal-predicted.fhp.json").read_text())
    record["documentation"] = "proteins > 50 aa; contact someone@example.org"
    combined = combine(fhr(**record), b">p1\nMKV*\n", "fasta")
    assert not any(b">" in line or b"@" in line for line in header_lines(combined))
    data = fhr()
    data.input_fasta(combined)
    data.fhr_validate()
    assert data.documentation == record["documentation"]
