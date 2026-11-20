# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Adopted shared #258/#267 runtime controls; immutable schemas are unchanged."""

import gzip
import io
import json
import struct
import zlib
from pathlib import Path

import pytest
from jsonschema import ValidationError

from bioheaders import fhr, load_yaml
from bioheaders.cli import _GzipStream
from bioheaders.schema_validator import check_fht_completeness

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "prefix",
    [
        "%YAML 1.1\n---\n",
        "%YAML 1.2\n---\n",
        "%TAG !e! tag:example.com,2000:\n---\n",
        "---\n",
    ],
)
def test_r12_directives_and_document_start_rejected(prefix):
    with pytest.raises(ValueError, match="R12"):
        # Parser errors inherit yaml.YAMLError rather than ValueError.
        try:
            load_yaml(prefix + "name: example\n")
        except Exception as exc:
            raise ValueError(str(exc)) from exc


def member(data, valid=True):
    # FNAME + FCOMMENT + FHCRC, all covered by the low 16 bits of CRC32.
    header = b"\x1f\x8b\x08\x1a\x00\x00\x00\x00\x00\xffname\x00comment\x00"
    crc = zlib.crc32(header) & 65535
    header += struct.pack("<H", crc if valid else crc ^ 1)
    compressed = zlib.compressobj(wbits=-15)
    return (
        header
        + compressed.compress(data)
        + compressed.flush()
        + struct.pack("<II", zlib.crc32(data), len(data))
    )


@pytest.mark.parametrize(
    "data",
    [
        gzip.compress(b"abc"),
        member(b"abc"),
        gzip.compress(b"a") + member(b"bc"),
        member(b"abc") + b"\0" * 16,
    ],
)
def test_r1_accepted_members(data):
    stream = _GzipStream(io.BytesIO(data), "control")
    assert b"".join(iter(lambda: stream.read(1), b"")) == b"abc"


@pytest.mark.parametrize(
    "data",
    [
        member(b"abc", False),
        gzip.compress(b"abc") + b"garbage",
        gzip.compress(b"abc") + b"\0garbage",
        gzip.compress(b"abc")[:-1],
    ],
)
def test_r1_rejected_members(data):
    with pytest.raises(ValueError, match="Invalid gzip"):
        _GzipStream(io.BytesIO(data), "control").read()


@pytest.mark.parametrize("nested", [False, True])
def test_r4_metadata_and_nested_checksum(nested):
    record = json.loads((ROOT / "examples/example.fhr.json").read_bytes())
    if nested:
        record["derivedFrom"] = [
            {
                "checksum": "A" * 42 + "B=",
                "headerType": "FHR",
                "relationship": "derivedFrom",
            }
        ]
    else:
        record["checksum"] = "A" * 42 + "B="
    with pytest.raises(ValidationError):
        fhr(**record).fhr_validate()


@pytest.mark.parametrize("total", [4, 6])
def test_fht_c1_both_arithmetic_directions(total):
    record = {
        "completeness": dict(
            completeSingle=2, completeDuplicated=1, fragmented=1, missing=1, total=total
        )
    }
    with pytest.raises(ValidationError, match="C1"):
        check_fht_completeness(record)


def test_fht_c1_missing_is_not_zero():
    check_fht_completeness({"completeness": {"completeSingle": 2, "total": 3}})


def test_large_gzip_read_appends_each_decoded_byte_once():
    """Observe bounded linear ingress rather than relying on a timing threshold."""

    class MeasuredBuffer(bytearray):
        appended = 0
        largest_chunk = 0
        calls = 0

        def extend(self, data):
            self.appended += len(data)
            self.largest_chunk = max(self.largest_chunk, len(data))
            self.calls += 1
            super().extend(data)

    payload = b"0123456789abcdef" * (2**21)  # 32 MiB, metadata-scale read.
    stream = _GzipStream(io.BytesIO(gzip.compress(payload)), "large-control")
    assert isinstance(stream.output, bytearray)
    buffer = MeasuredBuffer()
    stream.output = buffer
    result = stream.read(len(payload) + 1)
    assert isinstance(result, bytes)
    assert result == payload
    assert buffer.appended == len(payload)
    assert buffer.largest_chunk <= 65536
    assert buffer.calls >= len(payload) // 65536
    assert stream.output is buffer and not buffer
    assert stream.read() == b""


def test_gzip_partial_then_unbounded_reads_return_exact_bytes():
    payload = bytes(range(256)) * 32768
    stream = _GzipStream(io.BytesIO(gzip.compress(payload)), "partial-control")
    chunks = [stream.read(size) for size in (1, 65535, 131073, 7)]
    chunks.append(stream.read())
    assert all(isinstance(chunk, bytes) for chunk in chunks)
    assert b"".join(chunks) == payload
    assert stream.read(100) == b""
