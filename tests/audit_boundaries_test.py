# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Regression probes for confirmed Round 16 source audit boundaries."""

import gzip
import io
import os
import re
import subprocess
import sys
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import pytest

from bioheaders import cli, faidx, fhgm, gff3


def check_bounded_gzip_reads(monkeypatch, limit):
    original = cli._GzipStream.read

    def read(stream, size=-1):
        assert 0 < size <= limit, "gzip was read without a decompressed-byte bound"
        result = original(stream, size)
        assert len(result) <= limit
        return result

    monkeypatch.setattr(cli._GzipStream, "read", read)


def test_gzipped_fhgm_predecessor_is_bounded_before_model_evaluation(
    tmp_path, monkeypatch
):
    source = tmp_path / "predecessor.gff3.gz"
    source.write_bytes(gzip.compress(b"x" * 2**20))
    monkeypatch.setattr(cli.fhgm, "MAX_LANE_BYTES", 128)
    check_bounded_gzip_reads(monkeypatch, 129)

    def unexpected(*args, **kwargs):
        pytest.fail("oversized predecessor reached model checking")

    monkeypatch.setattr(cli.fhgm, "check_models", unexpected)
    with pytest.raises(ValueError, match="larger than.*memory"):
        cli._fhgm_report(SimpleNamespace(fhgm_predecessor=[source]), b"")


def test_gzipped_export_context_is_bounded_before_yaml(tmp_path, monkeypatch):
    source = tmp_path / "context.yaml.gz"
    source.write_bytes(gzip.compress(b"x" * 2**20))
    monkeypatch.setattr(cli, "MAX_METADATA_BYTES", 128)
    check_bounded_gzip_reads(monkeypatch, 129)
    with pytest.raises(ValueError, match="Export context.*size limit"):
        cli._read_export_context(source)


def test_prefixed_index_stream_preserves_bytes_for_full_and_mixed_reads():
    stream = faidx._Prefixed(b"ab", io.BytesIO(b"cdef"))
    assert stream.read(0) == b""
    assert stream.read(1) == b"a"
    assert stream.read(-1) == b"bcdef"
    assert stream.read() == b""


def test_broken_pipe_closes_the_temporary_devnull_descriptor(monkeypatch, capsys):
    closed = []
    duplicated = []

    def broken():
        raise BrokenPipeError("reader closed")

    with monkeypatch.context() as patch:
        patch.setattr(cli.os, "open", lambda *args: 987)
        patch.setattr(cli.os, "dup2", lambda source, target: duplicated.append(source))
        patch.setattr(cli.os, "close", closed.append)
        patch.setattr(cli.sys, "stdout", SimpleNamespace(fileno=lambda: 123))
        assert cli._run(broken) == 1
    assert duplicated == [987]
    assert closed == [987]
    assert "output pipe closed" in capsys.readouterr().err


def test_numeric_metadata_hint_does_not_become_a_genome_link_failure(tmp_path):
    fixture = (
        Path(__file__).parent
        / "fixtures/fhgff3/valid/fhgff3-minimal-reference-link.fhgff3.gff3"
    )
    raw, count = re.subn(
        rb"(?m)^(#~[ \t]*version[ \t]*:).*$", rb"\g<1> 1", fixture.read_bytes()
    )
    assert count == 1
    path = tmp_path / "numeric-version.gff3"
    path.write_bytes(raw)
    report = gff3.header_report(path)
    assert report["schema"]["ok"] is False
    assert "quote the value" in report["schema"]["message"]
    assert report["genome_link"]["ok"] is True


def test_fhgm_inventory_does_not_materialise_a_whole_comment_line_table():
    data = b"#a\n#a\r#a\r\n" * 10000 + b"chr1\tdemo\tgene\t1\t4\t.\t+\t.\tID=g1\r\n"
    tracemalloc.start()
    try:
        index = fhgm.RowIndex(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert index.rows[b"g1"] == [(b"gene", False)]
    assert peak < len(data) * 4


@pytest.mark.parametrize("value", ["256M", "0", "-1"])
def test_invalid_optional_fhgm_limit_does_not_break_package_import(value, tmp_path):
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["BIOHEADERS_FHGM_MAX_BYTES"] = value
    environment.pop("BIOHEADERS_EXPERIMENTAL_FHGM", None)
    script = (
        "import os, bioheaders; from bioheaders import fhgm; "
        "assert not fhgm.draft_support_enabled(); "
        "os.environ['BIOHEADERS_EXPERIMENTAL_FHGM']='1'; "
        "\ntry: fhgm.draft_support_enabled()"
        "\nexcept fhgm.FHGMLaneError as e: "
        "assert 'BIOHEADERS_FHGM_MAX_BYTES' in str(e); print(str(e))"
        "\nelse: raise AssertionError('invalid active-lane limit was accepted')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "positive integer byte count" in result.stdout
