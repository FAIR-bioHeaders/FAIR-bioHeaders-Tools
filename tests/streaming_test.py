"""Chunked FASTA/GFA processing matches whole-file processing byte for byte."""

import base64
import codecs
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import fhr as fhr_module
from fhr import fhr, header_text, load_yaml, read_chunks, sequence_parts
from fhr.cli import (
    SequenceScan,
    checksum,
    combine,
    strip_header,
    strip_parts,
    write_output,
)

ROOT = Path(__file__).resolve().parents[1]
CHUNK_SIZES = [1, 2, 3, 4, 5, 6, 7, None]


# Whole-file reference: the 0.3.1 implementation based on bytes.splitlines.
def reference_lines(content):
    if content.startswith(codecs.BOM_UTF8):
        raise ValueError("FASTA/GFA files must not begin with a UTF-8 byte order mark")
    return content.splitlines(keepends=True)


def reference_header_lines(lines, prefix):
    in_header = True
    found = []
    for number, line in enumerate(lines, 1):
        if line.startswith(prefix):
            if not in_header:
                raise ValueError(
                    f"FHR header line after sequence data at line {number}"
                )
            found.append(line)
        elif in_header:
            if prefix == b";~":
                in_header = not line.startswith(b">")
            else:
                in_header = line.startswith(b"#") or not line.strip()
    return found


def reference_strip(content, prefix):
    lines = reference_lines(content)
    reference_header_lines(lines, prefix)
    return b"".join(line for line in lines if not line.startswith(prefix))


# FORMAT.md R4/R5, written independently of bioheaders.cli.CHECKSUM_LINE.
CHECKSUM_LINE = re.compile(
    rb" *checksum *: +(['\"]?)[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=\1 *"
)


def reference_checksum(content, prefix):
    pattern = re.compile(b"^" + re.escape(prefix) + rb"[ \t]*checksum[ \t]*:")
    lines = reference_lines(content)
    metadata_lines = reference_header_lines(lines, prefix)
    meaningful = [
        line[len(prefix) :]
        for line in metadata_lines
        if line[len(prefix) :].strip()
        and not line[len(prefix) :].lstrip().startswith(b"#")
        and not re.match(
            rb"^(?:%|---(?:[ \t]|$)|\.\.\.(?:[ \t]|$))",
            line[len(prefix) :].lstrip(b" \t"),
        )
    ]
    root = min((len(line) - len(line.lstrip(b" \t")) for line in meaningful), default=0)

    def is_checksum(line):
        yaml_line = line[len(prefix) :]
        return (
            bool(pattern.match(line))
            and len(yaml_line) - len(yaml_line.lstrip(b" \t")) == root
        )

    matches = [line for line in lines if is_checksum(line)]
    if len(matches) != 1:
        raise ValueError("Expected exactly one scalar checksum header line")
    header = load_yaml("\n".join(header_text(line, prefix) for line in metadata_lines))
    try:
        value = load_yaml(header_text(matches[0], prefix))
    except yaml.YAMLError:
        value = None
    if not (
        isinstance(value, dict)
        and list(value) == ["checksum"]
        and isinstance(value["checksum"], str)
        and value["checksum"]
        and isinstance(header, dict)
        and header.get("checksum") == value["checksum"]
    ):
        raise ValueError(
            "The checksum header line must contain the complete checksum value "
            "as a single-line scalar"
        )
    if not CHECKSUM_LINE.fullmatch(matches[0][len(prefix) :].rstrip(b"\r\n")):
        raise ValueError(
            "The checksum header line must hold only the checksum value: 44 "
            "canonical base64 characters, optionally quoted, with no comment, "
            "tag, tab or other text (FAIR-bioHeaders-Specification "
            "docs/FORMAT.md R4 and R5)"
        )
    digest = hashlib.new("sha512_256")
    for line in lines:
        if not is_checksum(line):
            digest.update(line)
    return base64.b64encode(digest.digest()).decode("ascii")


def outcome(action):
    try:
        return "ok", action()
    except (ValueError, yaml.YAMLError) as error:
        return type(error).__name__, str(error)


def chunks(content, size):
    if size is None:
        return read_chunks(io.BytesIO(content))
    return [content[start : start + size] for start in range(0, len(content), size)]


@pytest.fixture(scope="module")
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


BODIES = {
    "fasta": [
        b">ctg\nACGT\nAC\n>two\nGG\n",
        b">ctg\r\nACGT\r\nAC\r\n",
        b">ctg\rACGT\rAC\r",
        b">ctg\r\nACGT\nAC\r>two\n\rGG\r\n",
        b">ctg\nACGT",
        b">ctg\r\nACGT\r",
        b"; comment\n\n;\r\n>ctg\n; inner ;~ comment\nAC\n\n",
        b"",
        b"\n\r\n\r",
    ],
    "gfa": [
        b"H\tVN:Z:1.0\nS\tctg\tACGT\nL\tctg\t+\tctg\t+\t0M\n",
        b"H\tVN:Z:1.0\r\nS\tctg\tACGT\r\n",
        b"H\tVN:Z:1.0\rS\tctg\tACGT\r",
        b"# comment\r\n \t\n\r\nS\tctg\tACGT\nS\tx\tA",
        b"  \n\x0b\x0c\n  S\tctg\tACGT\n",
        b"",
    ],
}


def sequence_cases(metadata):
    cases = []
    for kind, bodies in BODIES.items():
        prefix = b";~" if kind == "fasta" else b"#~"
        comment = b";" if kind == "fasta" else b"#"
        for body in bodies:
            combined = combine(fhr(**metadata), body, kind)
            crlf = combined.replace(b"\n", b"\r\n")
            cases += [
                (kind, combined),
                (kind, crlf),
                (kind, combined.replace(b"\n", b"\r")),
                (kind, comment + b" lead\r\n\n" + combined),
                (kind, combined + prefix + b"late: 1\n"),
                (kind, combined + combined),
                (kind, crlf + crlf),
                (kind, combined.rstrip(b"\n")),
                (kind, b"\xef\xbb\xbf" + combined),
                (kind, combined.replace(b"ACGT", b"ACGA")),
            ]
        cases += [
            (kind, prefix + b"checksum: X\r" + b"\n" + prefix + b"a: 1\r\n"),
            (kind, prefix + b" a: 1\n" + prefix + b" checksum: X\n" + prefix + b"b:\n"),
            (kind, prefix + b"checksum: X\n" + prefix + b"checksum: Y\n"),
            (kind, prefix + b"  checksum: X\n" + prefix + b"a: 1\n"),
            (kind, prefix + b"checksum: >-\n" + prefix + b"  X\n"),
            (kind, prefix + b"checksum: X"),
            (kind, prefix),
            (kind, prefix[:1]),
            (kind, b""),
        ]
    return cases


@pytest.mark.parametrize("size", CHUNK_SIZES)
def test_chunked_processing_matches_whole_file_reference(metadata, size):
    for kind, content in sequence_cases(metadata):
        prefix = b";~" if kind == "fasta" else b"#~"
        expected = outcome(lambda: reference_checksum(content, prefix))
        assert outcome(lambda: checksum(content, kind)) == expected
        assert (
            outcome(lambda: SequenceScan(chunks(content, size), kind).checksum())
            == expected
        ), content
        expected = outcome(lambda: reference_strip(content, prefix))
        assert outcome(lambda: strip_header(content, kind)) == expected
        assert (
            outcome(lambda: b"".join(strip_parts(chunks(content, size), kind)))
            == expected
        ), content
        expected = outcome(
            lambda: reference_header_lines(reference_lines(content), prefix)
        )
        assert (
            outcome(
                lambda: [
                    data
                    for part, data in sequence_parts(chunks(content, size), prefix)
                    if part == "header"
                ]
            )
            == expected
        ), content


@pytest.mark.parametrize("size", CHUNK_SIZES)
def test_parts_preserve_every_byte(metadata, size):
    for kind, content in sequence_cases(metadata):
        prefix = b";~" if kind == "fasta" else b"#~"
        try:
            parts = list(sequence_parts(chunks(content, size), prefix))
        except ValueError:
            continue
        assert b"".join(data for _, data in parts) == content
        assert sum(part == "end" for part, _ in parts) <= 1


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_crlf_split_between_chunks_is_one_terminator(metadata, kind):
    prefix = b";~" if kind == "fasta" else b"#~"
    record = b">ctg" if kind == "fasta" else b"S\tctg\tACGT"
    combined = combine(fhr(**metadata), record + b"\nACGT\n", kind)
    crlf = combined.replace(b"\n", b"\r\n")
    # Split every \r\n between chunks, including the excluded checksum line's.
    pieces = re.split(b"(?<=\r)(?=\n)", crlf)
    assert len(pieces) == crlf.count(b"\r\n") + 1
    scan = SequenceScan(pieces, kind)
    assert scan.checksum() == reference_checksum(crlf, prefix)
    assert scan.checksum_line.startswith(prefix + b"checksum: ")
    assert scan.checksum_line.endswith(b"\r\n")
    assert b"".join(strip_parts(pieces, kind)) == record + b"\r\nACGT\r\n"
    with pytest.raises(ValueError, match="at line 2$"):
        list(sequence_parts([record + b"\r", b"\n" + prefix + b"x: 1\n"], prefix))
    with pytest.raises(ValueError, match="at line 3$"):
        list(sequence_parts([record + b"\r", b"\r", prefix + b"x\n"], prefix))
    with pytest.raises(ValueError, match="at line 2$"):
        list(sequence_parts([record + b"\n" + prefix[:1], prefix[1:]], prefix))


def test_input_methods_read_streams_in_chunks(metadata, monkeypatch):
    combined = combine(fhr(**metadata), b">ctg\r\nACGT\r\n", "fasta")
    monkeypatch.setattr(fhr_module, "CHUNK_SIZE", 3)
    for source in (
        io.BytesIO(combined),
        io.TextIOWrapper(io.BytesIO(combined), encoding="utf-8", newline=""),
        combined,
        combined.decode("utf-8"),
    ):
        loaded = fhr()
        loaded.input_fasta(source)
        assert loaded.checksum == checksum(combined, "fasta")
    assert list(read_chunks(io.BytesIO(b"abcdefg"), 3)) == [b"abc", b"def", b"g"]
    with pytest.raises(TypeError, match="readable stream"):
        fhr().input_fasta(42)


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_header_size_is_capped(metadata, monkeypatch, kind):
    prefix = b";~" if kind == "fasta" else b"#~"
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    combined = combine(fhr(**metadata), body, kind)
    huge = (
        prefix
        + b"documentation: "
        + b"x" * fhr_module.MAX_HEADER_BYTES
        + b"\n"
        + combined
    )
    for action in (
        lambda: checksum(huge, kind),
        lambda: strip_header(huge, kind),
        lambda: getattr(fhr(), "input_" + kind)(huge),
    ):
        with pytest.raises(ValueError, match="exceed the 1 MiB size limit"):
            action()
    # The cap counts FHR lines only, not comments or sequence data.
    comment = (b";" if kind == "fasta" else b"#") + b"y" * (17 * 2**20) + b"\n"
    assert strip_header(comment + combined, kind) == comment + body
    monkeypatch.setattr(fhr_module, "MAX_HEADER_BYTES", len(combined) - len(body))
    checksum(combined, kind)
    monkeypatch.setattr(fhr_module, "MAX_HEADER_BYTES", len(combined) - len(body) - 1)
    with pytest.raises(ValueError, match="size limit"):
        checksum(combined, kind)


def test_write_output_is_atomic(tmp_path):
    output = tmp_path / "output.fasta"

    def failing(stream):
        stream.write(b"partial")
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        write_output(output, failing)
    assert list(tmp_path.iterdir()) == []
    output.write_bytes(b"keep me")
    output.chmod(0o640)
    with pytest.raises(OSError, match="disk full"):
        write_output(output, failing)
    assert output.read_bytes() == b"keep me"
    assert list(tmp_path.iterdir()) == [output]
    write_output(output, lambda stream: stream.write(b"new"))
    assert output.read_bytes() == b"new"
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    link = tmp_path / "link.fasta"
    link.symlink_to(output.name)
    write_output(link, lambda stream: stream.write(b"through link"))
    assert link.is_symlink() and output.read_bytes() == b"through link"
    fresh = tmp_path / "fresh.fasta"
    write_output(fresh, lambda stream: stream.write(b"x"))
    umask = os.umask(0)
    os.umask(umask)
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o666 & ~umask
    with pytest.raises(FileNotFoundError, match="missing/output.fasta"):
        write_output(tmp_path / "missing/output.fasta", lambda stream: None)


def command(tmp_path, script, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / script), *map(str, args)],
        cwd=tmp_path,
        capture_output=True,
    )


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_cli_failures_leave_no_partial_output(metadata, tmp_path, kind):
    prefix = b";~" if kind == "fasta" else b"#~"
    body = b">ctg\nACGT\n" if kind == "fasta" else b"S\tctg\tACGT\n"
    source = tmp_path / "input.json"
    source.write_text(json.dumps(metadata))
    late = tmp_path / ("late." + kind)
    content = combine(fhr(**metadata), body * 1000, kind) + prefix + b"x: 1\n"
    late.write_bytes(content)
    _, message = outcome(lambda: reference_strip(content, prefix))
    stripped = tmp_path / ("stripped." + kind)
    combined = tmp_path / ("combined." + kind)
    for script, args in (
        (f"{kind}/fhr_{kind}_strip.py", [late, stripped]),
        (f"{kind}/fhr_{kind}_combine.py", [source, late, "-o", combined]),
        ("fhr_convert.py", [late, tmp_path / "output.json"]),
    ):
        result = command(tmp_path, script, *args)
        assert result.returncode == 1
        assert result.stderr.decode() == f"FHR: {message}\n"
        assert result.stdout == b""
    result = command(tmp_path, f"{kind}/fhr_{kind}_strip.py", late)
    assert result.returncode == 1 and result.stdout == b""
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "input.json",
        "late." + kind,
    ]


def _peak_rss_kb(arguments, cwd, stdin=None):
    """Run a command in a child process and return its peak RSS in KiB."""
    script = (
        "import resource, subprocess, sys\n"
        "result = subprocess.run(sys.argv[1:], stdout=subprocess.DEVNULL)\n"
        "assert result.returncode == 0, result\n"
        "print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)\n"
    )
    with open(stdin or os.devnull, "rb") as source:
        result = subprocess.run(
            [sys.executable, "-c", script, *map(str, arguments)],
            cwd=cwd,
            stdin=source,
            capture_output=True,
            text=True,
            check=True,
        )
    return int(result.stdout)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(2**20), b""):
            digest.update(chunk)
    return digest.hexdigest()


MEMORY_TEST = pytest.mark.skipif(
    os.environ.get("FHR_MEMORY_TEST") != "1",
    reason="set FHR_MEMORY_TEST=1 to run the large-file memory test",
)


def _write_large_fasta(stream, size):
    line = (b"ACGTTGCA" * 8)[:60] + b"\n"
    block = line * 10000
    written = 0
    while written < size:
        stream.write(b">chr%d\n" % written)
        stream.write(block)
        written += len(block)


@MEMORY_TEST
def test_large_fasta_memory_is_bounded(tmp_path):
    size = int(os.environ.get("FHR_MEMORY_TEST_MB", "300")) * 10**6
    raw = tmp_path / "raw.fasta"
    with open(raw, "wb") as stream:
        _write_large_fasta(stream, size)
    combined = tmp_path / "raw.fhr.fasta"
    stripped = tmp_path / "stripped.fasta"
    commands = {
        "combine": [
            "fasta/fhr_fasta_combine.py",
            ROOT / "examples/example.fhr.yaml",
            raw,
        ],
        "validate": ["fasta/fhr_fasta_validate.py", combined],
        "strip": ["fasta/fhr_fasta_strip.py", combined, stripped],
        "strip to stdout": ["fasta/fhr_fasta_strip.py", combined],
        "convert": ["fhr_convert.py", combined, tmp_path / "output.json"],
    }
    limit = 256 * 1024
    for name, (script, *args) in commands.items():
        peak = _peak_rss_kb([sys.executable, ROOT / script, *args], tmp_path)
        print(f"{name}: peak RSS {peak // 1024} MiB for {size // 10**6} MB")
        assert peak < limit, name
    assert _sha256(stripped) == _sha256(raw)


@MEMORY_TEST
def test_large_gzip_fasta_memory_is_bounded(tmp_path):
    size = int(os.environ.get("FHR_MEMORY_TEST_MB", "300")) * 10**6
    raw = tmp_path / "raw.fasta"
    with open(raw, "wb") as stream:
        _write_large_fasta(stream, size)
    compressed = tmp_path / "raw.fasta.gz"
    with gzip.open(compressed, "wb", compresslevel=1) as stream:
        _write_large_fasta(stream, size)
    combined = tmp_path / "raw.fhr.fasta.gz"
    stripped = tmp_path / "stripped.fasta"
    metadata = ROOT / "examples/example.fhr.yaml"
    commands = {
        "combine gz to BGZF": ["fasta/fhr_fasta_combine.py", metadata, compressed],
        "validate BGZF": ["fasta/fhr_fasta_validate.py", combined],
        "strip BGZF": ["fasta/fhr_fasta_strip.py", combined, stripped],
        "strip BGZF to stdout": ["fasta/fhr_fasta_strip.py", combined],
        "convert BGZF": ["fhr_convert.py", combined, tmp_path / "output.json"],
    }
    piped = {
        "validate BGZF from stdin": (["fasta/fhr_fasta_validate.py", "-"], combined),
        "strip BGZF from stdin": (["fasta/fhr_fasta_strip.py", "-"], combined),
        "combine gz from stdin": (
            ["fasta/fhr_fasta_combine.py", metadata, "-"],
            compressed,
        ),
    }
    limit = 256 * 1024
    runs = [(name, arguments, None) for name, arguments in commands.items()]
    runs += [(name, arguments, stdin) for name, (arguments, stdin) in piped.items()]
    for name, (script, *args), stdin in runs:
        peak = _peak_rss_kb([sys.executable, ROOT / script, *args], tmp_path, stdin)
        print(f"{name}: peak RSS {peak // 1024} MiB for {size // 10**6} MB")
        assert peak < limit, name
    assert _sha256(stripped) == _sha256(raw)
