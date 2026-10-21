"""Limits and guards for hostile input (security advisory, fair-bioheaders 0.8.1)."""

import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

import fhr as fhr_module
from fhr import fhr, load_yaml
from fhr.cli import checksum, combine, run
from bioheaders.assess import batch, online

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


def test_header_line_count_is_capped(metadata):
    combined = combine(fhr(**metadata), b">ctg\nACGT\n", "fasta")
    many = b";~#\n" * (fhr_module.MAX_HEADER_LINES + 1) + combined
    with pytest.raises(ValueError, match="line limit"):
        checksum(many, "fasta")


def test_yaml_node_count_and_depth_are_capped():
    with pytest.raises(yaml.YAMLError, match="YAML nodes"):
        load_yaml("a: [" + ",".join(["1"] * (fhr_module.MAX_YAML_NODES + 1)) + "]")
    with pytest.raises(yaml.YAMLError, match="nested too deeply"):
        load_yaml("a: " + "[" * (fhr_module.MAX_YAML_DEPTH + 1))
    assert load_yaml("a: " + "[" * 10 + "]" * 10) == {"a": [[[[[[[[[[]]]]]]]]]]}


def test_metadata_input_size_is_capped(monkeypatch):
    monkeypatch.setattr(fhr_module, "MAX_METADATA_BYTES", 100)
    with pytest.raises(ValueError, match="size limit"):
        fhr().input_json(io.BytesIO(b'{"genome": "' + b"x" * 200 + b'"}'))
    fhr().input_json(io.BytesIO(b'{"genome": "x"}'))


def test_gzip_bomb_metadata_is_refused(tmp_path, monkeypatch):
    import gzip

    monkeypatch.setattr(fhr_module, "MAX_METADATA_BYTES", 2**16)
    source = tmp_path / "bomb.json.gz"
    source.write_bytes(gzip.compress(b'{"genome": "' + b" " * 2**20 + b'"}'))
    result = subprocess.run(
        [sys.executable, "-c",
         "import bioheaders, sys; bioheaders.MAX_METADATA_BYTES = 2**16;"
         "from bioheaders.cli import main; sys.argv = sys.argv[1:]; sys.exit(main())",
         "bioheaders", "convert", "--from", "json", "--to", "yaml", str(source), "-"],
        capture_output=True,
    )
    assert result.returncode == 1
    assert b"size limit" in result.stderr and b"Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("error", "message"),
    [(MemoryError(), "out of memory"), (KeyError("x"), "unexpected error (KeyError)")],
)
def test_unexpected_errors_are_reported_without_traceback(capsys, error, message):
    def fail():
        raise error

    assert run(fail) == 1
    assert message in capsys.readouterr().err


def test_malformed_jsonld_context_is_a_clean_error():
    pytest.importorskip("pyld")
    with pytest.raises(ValueError, match="invalid JSON-LD"):
        fhr().input_jsonld('{"@context": {"@language": null}, "genome": "x"}')


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
@pytest.mark.parametrize("command", ["combine", "strip"])
def test_non_regular_input_is_read_once(tmp_path, metadata, command):
    plain = b">ctg\nACGT\nACGT\n"
    source = combine(fhr(**metadata), plain, "fasta") if command == "strip" else plain
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    fifo = tmp_path / "input.fa"
    os.mkfifo(fifo)
    output = tmp_path / "output.fa"

    def feed():
        with open(fifo, "wb") as stream:
            stream.write(source)

    writer = threading.Thread(target=feed)
    writer.start()
    arguments = (
        ["combine", "--type", "fasta", "-o", str(output), str(tmp_path / "metadata.json")]
        if command == "combine"
        else ["strip", "--type", "fasta"]
    )
    if command == "combine":
        arguments.append(str(fifo))
    else:
        arguments += [str(fifo), str(output)]
    result = subprocess.run(
        [sys.executable, "-m", "bioheaders", *arguments], capture_output=True, timeout=60
    )
    writer.join(5)
    assert result.returncode == 0, result.stderr
    written = output.read_bytes()
    assert written.endswith(plain)
    if command == "combine":
        checksum(written, "fasta")


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("8.8.8.8", True),
        ("2001:4860:4860::8888", True),
        ("64:ff9b::808:808", True),
        ("100.64.0.1", False),
        ("100.100.100.200", False),
        ("fec0::1", False),
        ("::ffff:100.100.100.200", False),
        ("::ffff:127.0.0.1", False),
        ("2002:6464:64c8::1", False),
        ("64:ff9b::a9fe:a9fe", False),
        ("169.254.169.254", False),
        ("192.0.0.1", False),
        ("fd00::1", False),
        ("ff02::1", False),
    ],
)
def test_public_address(address, public):
    assert online.public_address(address) is public


def test_request_deadline_covers_slow_responses(monkeypatch):
    monkeypatch.setattr(online, "ALLOW_PRIVATE_ADDRESSES_FOR_TESTS", True)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    stop = threading.Event()

    def drip():
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(b"HTTP/1.1 200 OK\r\n")
            while not stop.is_set():
                try:
                    connection.sendall(b"X")  # One header byte at a time.
                except OSError:
                    return
                time.sleep(0.05)

    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    resolver = online.Resolver(timeout=0.3)
    start = time.monotonic()
    status, _final, outcome = resolver._request(f"http://127.0.0.1:{port}/", "HEAD")
    elapsed = time.monotonic() - start
    stop.set()
    server.close()
    assert outcome == "unavailable" and status is None
    assert elapsed < online.REQUEST_DEADLINE_FACTOR * 0.3 + 1.0


def test_batch_summary_escapes_paths():
    summary = {
        "online_checks": "not_requested",
        "root": "<b>root</b>",
        "tool": {"version": "0"},
        "rubric_version": "0",
        "synonyms_version": "0",
        "indicator_counts": {},
        "attribution": "",
        "files": [
            {
                "path": name,
                "format": "fasta",
                "scope": "assessed",
                "pair_classification": None,
                "statuses": {},
            }
            for name in ("<img src=x onerror=alert(1)>.fa", "javascript:alert(1).fa",
                         "a`b`[x](javascript:y).fa")
        ],
        "errors": [{"path": "<script>.fa", "message": "<script>alert(1)</script>"}],
    }
    text = batch.to_markdown(summary, indicators=[])
    assert "<img" not in text and "<script" not in text and "<b>" not in text
    assert not re.search(r"(?<!\\)\]\(javascript:", text)
    assert "[report](./javascript%3Aalert%281%29.fa.assessment.md)" in text


@pytest.mark.parametrize("bad", ["../outside.fa", "/etc/passwd", "a/../../x.fa"])
def test_pairs_paths_stay_inside_the_root(tmp_path, bad):
    pairs = tmp_path / "pairs.tsv"
    pairs.write_text(f"derived.fa\t{bad}\n")
    with pytest.raises(batch.UsageError, match="relative path"):
        batch.read_pairs(pairs)
    pairs.write_text("derived.fa\tsub/related.fa\n")
    assert batch.read_pairs(pairs) == {"derived.fa": "sub/related.fa"}
