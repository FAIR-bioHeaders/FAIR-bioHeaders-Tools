# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Header families must match the sequence format (issue #72)."""

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import cli, fhr

ROOT = Path(__file__).resolve().parents[1]
METADATA = {
    "FHR": "examples/example.fhr.json",
    "FHP": "examples/fhp/minimal-predicted.fhp.json",
    "FHGFF3": "examples/fhgff3/minimal-reference.fhgff3.json",
}
BODIES = {
    "fasta": b">ctg1\r\nACGT\r\n",
    "gfa": b"S\tctg1\tACGT\r\n",
    "gff3": b"##gff-version 3\r\nctg1\tx\tgene\t1\t4\t.\t+\t.\tID=g\r\n",
}


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("family", METADATA)
@pytest.mark.parametrize("kind", BODIES)
def test_family_format_matrix(family, kind, compressed, tmp_path, monkeypatch, capsys):
    data = fhr(**json.loads((ROOT / METADATA[family]).read_text()))
    valid = (family, kind) in {
        ("FHR", "fasta"),
        ("FHR", "gfa"),
        ("FHP", "fasta"),
        ("FHGFF3", "gff3"),
    }
    body = BODIES[kind]
    suffix = kind + (".gz" if compressed else "")
    source = tmp_path / ("input." + suffix)
    source.write_bytes(gzip.compress(body) if compressed else body)
    output = tmp_path / ("output." + suffix)
    args = cli.argparse.Namespace(
        metadata=str(ROOT / METADATA[family]), sequence=str(source), output=str(output)
    )
    if valid:
        cli._combine(args, kind)
        content = output.read_bytes()
        if compressed:
            content = gzip.decompress(content)
        assert cli.strip_header(content, kind) == body
        cli._verify(cli.argparse.Namespace(input=str(output)), kind)
        assert capsys.readouterr().out == "Checksum verified.\n"
        return

    message = f"{family} metadata is incompatible with {kind.upper()}"
    with pytest.raises(ValueError, match=message):
        cli.combine(data, body, kind)
    # Both file and stdin combine fail before reading sequence or writing output.
    for sequence in (str(source), "-"):
        args.sequence = sequence
        with pytest.raises(ValueError, match=message):
            cli._combine(args, kind)
        assert not output.exists()
        assert capsys.readouterr().out == ""

    # Build a file as older versions did: a valid checksum cannot excuse a
    # mismatched family. Keep real schema and checksum validation enabled.
    with monkeypatch.context() as patch:
        patch.setattr(cli, "validate_header_family", lambda *args: None)
        content = cli.combine(data, body, kind)
        output.write_bytes(gzip.compress(content) if compressed else content)
    parsed = fhr()
    getattr(parsed, "input_" + kind)(content)
    assert parsed.checksum == cli.checksum(content, kind)
    assert (
        cli.run(lambda: cli._verify(cli.argparse.Namespace(input=str(output)), kind))
        == 1
    )
    captured = capsys.readouterr()
    assert message in captured.err
    assert "Checksum verified" not in captured.out

    # Installed unified and compatibility commands must expose the same error,
    # including stdin and stdout, when run outside the checkout.
    bin_dir = Path(sys.executable).parent
    commands = (
        [bin_dir / "bioheaders", "combine", "--type", kind],
        [bin_dir / f"fhr-{kind}-combine"],
    )
    for command in commands:
        result = subprocess.run(
            [*command, str(ROOT / METADATA[family]), "-", "-o", "-"],
            input=body,
            capture_output=True,
            cwd=tmp_path,
        )
        assert result.returncode == 1
        assert message.encode() in result.stderr
        assert result.stdout == b""
    for command in (
        [bin_dir / "bioheaders", "verify"],
        [bin_dir / "bioheaders", "checksum"],
        [bin_dir / f"fhr-{kind}-validate"],
    ):
        result = subprocess.run(
            [*command, str(output)], capture_output=True, cwd=tmp_path
        )
        assert result.returncode == 1
        assert message.encode() in result.stderr
        assert result.stdout == b""

    default = tmp_path / (
        f"input.{family.lower()}.{kind}" + (".gz" if compressed else "")
    )
    original = source.read_bytes()
    result = subprocess.run(
        [bin_dir / "bioheaders", "combine", str(ROOT / METADATA[family]), str(source)],
        capture_output=True,
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert message.encode() in result.stderr
    assert result.stdout == b""
    assert not default.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "family,kind",
    [
        ("FHR", "gff3"),
        ("FHP", "gfa"),
        ("FHP", "gff3"),
        ("FHGFF3", "fasta"),
        ("FHGFF3", "gfa"),
    ],
)
def test_combine_rejects_family_before_stripping(family, kind, monkeypatch):
    data = fhr(**json.loads((ROOT / METADATA[family]).read_text()))

    def refuse(*args):
        pytest.fail("combine processed sequence data before checking its header family")

    monkeypatch.setattr(cli, "strip_header", refuse)
    with pytest.raises(ValueError, match=f"{family} metadata is incompatible with"):
        cli.combine(data, BODIES[kind], kind)
