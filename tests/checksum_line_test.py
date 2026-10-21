"""The checksum line holds only the value; header YAML reads alike in YAML 1.1 and
1.2 (FAIR-bioHeaders-Specification docs/FORMAT.md R4, R5 and R12)."""

import json
import re
from pathlib import Path

import pytest
import yaml

from fhr import fhr, load_yaml
from fhr.cli import checksum, combine

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


def _combined(metadata, kind="fasta"):
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    return combine(fhr(**metadata), body, kind)


def _edit_checksum_line(data, prefix, edit):
    pattern = re.compile(rb"^" + re.escape(prefix) + rb"checksum: (\S+)$", re.M)
    found = pattern.search(data)
    return data[: found.start()] + edit(found.group(1)) + data[found.end() :]


@pytest.mark.parametrize(("kind", "prefix"), [("fasta", b";~"), ("gfa", b"#~")])
@pytest.mark.parametrize(
    "edit",
    [
        lambda value: b"checksum: " + value + b" # reviewed",
        lambda value: b"checksum: " + value + b" #>decoy",
        lambda value: b"checksum: " + value + b" #@decoy",
        lambda value: b"checksum: !!str " + value,
        lambda value: b"checksum:\t" + value,
        lambda value: b"checksum: " + value + b"\t",
        lambda value: b"checksum: " + value[:-2] + bytes([value[-2] + 1]) + b"=",
    ],
    ids=[
        "comment",
        "comment-gt",
        "comment-at",
        "tag",
        "tab",
        "trailing-tab",
        "noncanonical",
    ],
)
def test_checksum_line_holds_only_the_value(metadata, kind, prefix, edit):
    data = _combined(metadata, kind)
    checksum(data, kind)  # The original verifies.
    changed = _edit_checksum_line(data, prefix, lambda value: prefix + edit(value))
    with pytest.raises((ValueError, yaml.YAMLError)):
        checksum(changed, kind)


@pytest.mark.parametrize(
    "edit",
    [
        lambda value: b"checksum: '" + value + b"'",
        lambda value: b'checksum: "' + value + b'"',
        lambda value: b"checksum  :   " + value + b"   ",
    ],
    ids=["single-quoted", "double-quoted", "spaces"],
)
def test_checksum_line_spellings_that_stay_valid(metadata, edit):
    data = _combined(metadata)
    original = checksum(data, "fasta")
    changed = _edit_checksum_line(data, b";~", lambda value: b";~" + edit(value))
    assert checksum(changed, "fasta") == original


def test_written_checksum_lines_are_canonical(metadata):
    for kind, prefix in (("fasta", b";~"), ("gfa", b"#~")):
        data = _combined(metadata, kind)
        line = re.search(
            rb"^" + re.escape(prefix) + rb"checksum: .*$", data, re.M
        ).group()
        assert re.fullmatch(
            re.escape(prefix) + rb"checksum: [A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=", line
        )


@pytest.mark.parametrize(
    "text",
    [
        "a: 010",
        "a: 1_000",
        "a: 1:30",
        "a: 0b11",
        "a: 0o17",
        "a: yes",
        "a: On",
        "a: n",
        "a: Y",
        "a: 1e3",
        "a: 1.0e3",
        "a: +0x1F",
        "a: !!str x",
        "a: !!binary eA==",
        "a: !!timestamp 2024-01-01",
        "a: ! x",
        "a: !!int '7'",
    ],
)
def test_yaml_read_differently_by_1_1_and_1_2_is_rejected(text):
    with pytest.raises(yaml.YAMLError):
        load_yaml(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("a: 10", 10),
        ("a: 0", 0),
        ("a: -3", -3),
        ("a: 41.5", 41.5),
        ("a: 1.0e+3", 1000.0),
        ("a: true", True),
        ("a: null", None),
        ("a: 2024-01-01", "2024-01-01"),
        ("a: 2024-01-01 10:00:00", "2024-01-01 10:00:00"),
        ("a: '010'", "010"),
        ('a: "yes"', "yes"),
        ("a: 0x1F", 31),
        ("a: Homo sapiens", "Homo sapiens"),
    ],
)
def test_portable_yaml_values(text, value):
    assert load_yaml(text) == {"a": value}


@pytest.mark.parametrize(
    "value",
    [
        "010",
        "1_000",
        "1:30",
        "0o17",
        "0b11",
        "yes",
        "y",
        "N",
        "on",
        "1e3",
        "2024-01-01",
    ],
)
def test_writers_quote_strings_another_yaml_reads_as_another_type(metadata, value):
    metadata["documentation"] = value
    for kind in ("yaml", "fasta", "gfa"):
        output = getattr(fhr(**metadata), "output_" + kind)()
        loaded = fhr()
        getattr(loaded, "input_" + kind)(output)
        assert loaded.documentation == value
