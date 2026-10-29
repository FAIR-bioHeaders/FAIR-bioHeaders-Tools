# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Detect the compression, format and scope of an input (research R-02, R-15).

Compression comes from the magic bytes: gzip, or BGZF when the first gzip
member carries the ``BC`` extra subfield. The format comes from the content
first, then the file name (``.gz``/``.bgz`` ignored); ``--type`` overrides both.
At most ``SNIFF_BYTES`` decompressed bytes are read.
"""

import os
import sys
from collections import namedtuple
from pathlib import Path

from ..cli import STANDARD_STREAM, open_input

SNIFF_BYTES = 64 * 1024
FORMATS = ("fasta", "gff3", "gaf", "vcf", "gfa")
EXTENSIONS = {
    ".fa": "fasta",
    ".fasta": "fasta",
    ".fna": "fasta",
    ".faa": "fasta",
    ".ffn": "fasta",
    ".fas": "fasta",
    ".frn": "fasta",
    ".fsa": "fasta",
    ".mpfa": "fasta",
    ".gff": "gff3",
    ".gff3": "gff3",
    ".gaf": "gaf",
    ".vcf": "vcf",
    ".gfa": "gfa",
}
BINARY_MAGIC = (
    b"BAM\x01",
    b"CRAM",
    bytes.fromhex("26fc8f88"),  # BigWig 0x888FFC26, little-endian
    bytes.fromhex("888ffc26"),
    bytes.fromhex("ebf28987"),  # BigBed 0x8789F2EB, little-endian
    bytes.fromhex("8789f2eb"),
)
UNKNOWN_COMMENT_MARKERS = (b"#", b"!", b";", b"%", b"//")

Sniff = namedtuple(
    "Sniff",
    "compression format format_source scope error bytes_read head",
)


def compression_of(raw):
    """Return ``none``, ``gzip`` or ``bgzf`` from the first raw bytes."""
    if raw[:2] != b"\x1f\x8b":
        return "none"
    # FEXTRA set, and the first extra subfield is BC (SAM/BAM specification §4.1).
    if len(raw) >= 14 and raw[3] & 4 and raw[12:14] == b"BC":
        return "bgzf"
    return "gzip"


def _raw_head(path):
    if path == STANDARD_STREAM:
        peek = getattr(sys.stdin.buffer, "peek", None)
        return peek(18)[:18] if peek else b""
    with Path(path).open("rb") as stream:
        return stream.read(18)


def _lines(head):
    return head.splitlines()


def format_from_content(head):
    """Return the format the decompressed ``head`` declares, or None."""
    for line in _lines(head):
        if not line.strip():
            continue
        if line.startswith(b"##gff-version"):
            return "gff3"
        if line.startswith(b"##fileformat=VCF"):
            return "vcf"
        if line.startswith(b"!gaf-version"):
            return "gaf"
        if line.startswith(b">"):
            return "fasta"
        if line.startswith(b";"):  # FASTA comments, including ;~ FHR lines.
            continue
        if line.startswith(b"#"):
            continue
        if line.startswith(b"!"):
            continue
        if line[:2] in (b"H\t", b"S\t", b"L\t", b"P\t", b"W\t"):
            return "gfa"
        return None
    return None


def format_from_name(path):
    if path == STANDARD_STREAM:
        return None
    name = Path(path).name.lower()
    for suffix in (".gz", ".bgz"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return EXTENSIONS.get(os.path.splitext(name)[1])


def classify(head, path, compression, type_option=None):
    """Return ``(format, format_source, scope)`` for a decompressed head."""
    if type_option and type_option != "auto":
        return type_option, "option", "assessed"
    if len(head) > 262 and head[257:262] == b"ustar":
        return "archive", "content", "out_of_scope"
    if head.startswith(BINARY_MAGIC) or b"\x00" in head[:SNIFF_BYTES]:
        return "binary", "content", "out_of_scope"
    detected = format_from_content(head)
    if detected:
        return detected, "content", "assessed"
    named = format_from_name(path)
    if named:
        return named, "extension", "assessed"
    return "unknown-text", "content", "assessed"


def read_head(stream, limit=SNIFF_BYTES):
    head = b""
    while len(head) < limit:
        data = stream.read(limit - len(head))
        if not data:
            break
        head += data
    return head


def sniff(path, type_option=None):
    """Sniff ``path`` (``-`` for stdin) without reading past ``SNIFF_BYTES``."""
    path = os.fspath(path) if path != STANDARD_STREAM else path
    compression = compression_of(_raw_head(path))
    try:
        with open_input(path) as stream:
            head = read_head(stream)
    except ValueError as error:
        return Sniff(
            compression, "unknown-text", "content", "error", str(error), 0, b""
        )
    format_name, source, scope = classify(head, path, compression, type_option)
    return Sniff(compression, format_name, source, scope, None, len(head), head)
