# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Scan a related FASTA, FHR FASTA or GFA file once (research R-07, R-08).

One streaming pass collects each sequence's name, length and MD5 (letters
upper-cased, whitespace removed, as VCF defines it), computes the FHR checksum
with the toolkit's own ``SequenceScan``, and reads the identity the file states
in an FHR header (checksum, seqcol_id, accessionID, identifier). Memory is
constant apart from the name table. Results are cached by path and size.
"""

import hashlib
import os
import re

import yaml

from .. import fhr, read_chunks
from ..cli import SequenceScan, open_input
from .sniff import read_head


class RelatedFile:
    def __init__(self, path):
        self.path = path
        self.kind = "fasta"
        self.names = {}  # name -> [length, md5 hex]
        self.computed_checksum = None
        self.stated = {}
        self.error = None


class _Sequences:
    """Incremental FASTA/GFA parser fed with byte chunks."""

    def __init__(self, kind, names):
        self.kind = kind
        self.names = names
        self.pending = b""
        self.current = None
        self.digest = None

    def feed(self, chunk):
        data = self.pending + chunk
        lines = re.split(rb"\r\n|\r|\n", data)
        self.pending = lines.pop()
        for line in lines:
            self._line(line)

    def close(self):
        if self.pending:
            self._line(self.pending)
        self._finish()

    def _finish(self):
        if self.current is not None and self.kind == "fasta":
            self.names[self.current][1] = self.digest.hexdigest()
        self.current = None

    def _line(self, line):
        if self.kind == "gfa":
            fields = line.split(b"\t")
            if fields[0] == b"S" and len(fields) >= 3:
                name = fields[1].decode("utf-8", "replace")
                sequence = fields[2]
                length = len(sequence)
                if sequence == b"*":
                    tag = [f for f in fields[3:] if f.startswith(b"LN:i:")]
                    length = int(tag[0][5:]) if tag else 0
                md5 = (
                    hashlib.md5(sequence.upper()).hexdigest()
                    if sequence != b"*"
                    else None
                )
                self.names.setdefault(name, [length, md5])
            return
        if line.startswith(b">"):
            self._finish()
            name = line[1:].split(None, 1)
            name = name[0].decode("utf-8", "replace") if name else ""
            self.current = name
            self.digest = hashlib.md5()
            self.names.setdefault(name, [0, None])
        elif line.startswith(b";") or self.current is None:
            return
        else:
            letters = re.sub(rb"\s", b"", line)
            self.names[self.current][0] += len(letters)
            self.digest.update(letters.upper())


def _computed_checksum(scan):
    try:
        return scan.checksum()
    except ValueError:
        return None


def _stated(scan):
    if not scan.header:
        return {}
    data = fhr()
    try:
        data._input_header_lines(scan.header, scan.prefix)
    except (ValueError, TypeError, yaml.YAMLError):
        return {}
    metadata = data.__dict__
    accession = metadata.get("accessionID")
    identifiers = metadata.get("identifier")
    names = [metadata.get(key) for key in ("genome", "version")]
    names += metadata.get("genomeSynonym") or []
    return {
        "checksum": metadata.get("checksum"),
        "seqcol_id": metadata.get("seqcol_id"),
        "accessions": [
            value
            for value in [
                accession.get("name") if isinstance(accession, dict) else None
            ]
            + (identifiers if isinstance(identifiers, list) else [])
            if isinstance(value, str)
        ],
        "urls": [
            value
            for value in (metadata.get("relatedLink") or [])
            + [accession.get("url") if isinstance(accession, dict) else None]
            if isinstance(value, str)
        ],
        "names": [value for value in names if isinstance(value, str)],
    }


def _scan(path):
    result = RelatedFile(os.fspath(path))
    try:
        with open_input(os.fspath(path)) as stream:
            head = read_head(stream, 4096)
        first = next(
            (
                line
                for line in head.splitlines()
                if line.strip() and not line.startswith(b"#")
            ),
            b"",
        )
        if first[:2] in (b"S\t", b"H\t", b"L\t"):
            result.kind = "gfa"
        parser = _Sequences(result.kind, result.names)
        with open_input(os.fspath(path)) as stream:

            def chunks():
                for chunk in read_chunks(stream):
                    parser.feed(chunk)
                    yield chunk

            scan = SequenceScan(chunks(), result.kind)
        parser.close()
        result.computed_checksum = _computed_checksum(scan)
        result.stated = _stated(scan)
    except (OSError, ValueError) as error:
        result.error = getattr(error, "strerror", None) or str(error)
        if isinstance(error, OSError) and error.strerror:
            result.error = f"{error.strerror}: {os.fspath(path)}"
    return result


_CACHE: dict[tuple[str, int], RelatedFile] = {}


def scan(path):
    """Return the RelatedFile for ``path``, scanning it at most once per process."""
    try:
        key = (os.path.realpath(path), os.stat(path).st_size)
    except OSError:
        return _scan(path)
    if key not in _CACHE:
        _CACHE[key] = _scan(path)
    return _CACHE[key]


def prime(path, related_file):
    """Store a RelatedFile scanned elsewhere (another process) in this cache."""
    try:
        key = (os.path.realpath(path), os.stat(path).st_size)
    except OSError:
        return
    _CACHE[key] = related_file


def clear_cache():
    _CACHE.clear()


def suggestion_values(related_file):
    """Values a suggestion may take from the related file."""
    if related_file is None or related_file.error or not related_file.names:
        return None
    name, (length, md5) = next(iter(related_file.names.items()))
    stated = related_file.stated
    return {
        "name": name,
        "length": length,
        "md5": md5,
        "checksum": related_file.computed_checksum or stated.get("checksum"),
        "seqcol_id": stated.get("seqcol_id"),
        "accession": (stated.get("accessions") or [None])[0],
    }
