"""Write samtools-compatible ``.fai`` and ``.gzi`` indexes for FASTA files.

htslib rejects a FASTA file whose first line starts with ``;``, so it cannot
build an index for a file with a FAIR-bioHeaders header, but it uses an
existing ``.fai`` (and, for BGZF, ``.gzi``) without rebuilding it. This module
writes those indexes. The leading header block is identified by
:func:`bioheaders.sequence_parts`, the same reader that ``strip`` and ``verify``
use; every later byte is indexed with the rules of htslib's ``fai_build_core``
(``faidx.c``), and offsets count every byte of the original (decompressed) file,
header included. For a file without a header the index is byte-identical to the
one ``samtools faidx`` writes.

Two deliberate differences from htslib, both for input it cannot index usefully:
a duplicate sequence name is an error (htslib warns and keeps the first), and so
is a name too long for htslib to read back from a ``.fai`` line. Records without
sequence are omitted from the index, as htslib does, with a warning. Ordinary
``;`` comment lines and blank lines in the leading header block are skipped with
the header. FASTQ is not supported.
"""

import re
import struct
import zlib
from itertools import chain
from typing import Iterable, Iterator, List, NoReturn, Optional, Protocol, Tuple

from . import DATA, END, HEADER, read_chunks, sequence_parts


class Readable(Protocol):
    def read(self, size: int, /) -> bytes: ...


GZIP_MAGIC = b"\x1f\x8b"
GZIP_ERROR = "Cannot index files compressed with gzip, please use bgzip"
# htslib reads .fai lines into a 64 KiB buffer (fai_read): a longer line, which
# only a longer sequence name can make, would give an index it cannot read.
MAX_FAI_LINE = 0xFFFF
BGZF_HEADER = 18
BGZF_MAX_UNCOMPRESSED = 0x10000

# C-locale isgraph() and isspace(), as used by fai_build_core.
_GRAPH = bytes(range(0x21, 0x7F))
_SPACE = b" \t\n\v\f\r"
_LEADING_SPACE = re.compile(rb"[ \t\v\f\r]*")
_NAME = re.compile(rb"[^ \t\n\v\f\r]*")

# Parser states, following fai_build_core.
_OUT_READ = 0  # Between records, at a line start.
_CR = 1  # Between records after \r, which must be followed by \n.
_COMMENT = 2  # In a ; comment line of the leading header block.
_IN_NAME = 3  # After >, reading the name.
_NAME_REST = 4  # After the name, skipping the rest of the > line.
_IN_SEQ = 5  # In a record, at a line start.
_SEQ_LINE = 6  # In a sequence line.


def _printable(byte: int) -> str:
    return f'"{chr(byte)}"' if 0x20 <= byte < 0x7F else "character"


class FaiBuilder:
    """Build ``.fai`` records from FASTA bytes fed in order, in bounded memory.

    ``feed`` takes consecutive bytes of the file and their offset; ``leading``
    marks bytes of the leading header block other than FHR lines, where ``;``
    comment lines are also allowed. ``skip`` passes over FHR header lines.
    """

    def __init__(self) -> None:
        self.records: List[bytes] = []
        self.warnings: List[str] = []
        self._names: set = set()
        self._state = _OUT_READ
        self._line = 1
        self._name = bytearray()
        self._name_begun = False
        self._record: Optional[bytes] = None  # Name of the open record.
        self._record_line = 0
        self._read_done = False
        self._seq_offset = 0
        self._seq_len = 0
        self._line_len = 0
        self._char_len = 0
        self._ll = 0
        self._cl = 0
        self._slow_until = 0  # Offset before which lines are read one by one.

    def end_leading(self) -> None:
        """Mark the end of the leading header block (the first record)."""
        if self._state == _COMMENT:  # A comment line ended by a lone \r.
            self._state = _OUT_READ

    def skip(self, data: bytes) -> None:
        """Pass over FHR header lines, counting their lines."""
        self._line += data.count(b"\n")

    def feed(self, data: bytes, offset: int, leading: bool = False) -> None:
        position, size = 0, len(data)
        while position < size:
            state = self._state
            if state == _SEQ_LINE:
                newline = data.find(b"\n", position)
                end = size if newline < 0 else newline
                piece = data[position:end]
                self._ll += len(piece)
                self._cl += len(piece) - len(piece.translate(None, _GRAPH))
                if newline < 0:
                    return
                self._ll += 1
                position = newline + 1
                self._end_line()
            elif state == _IN_SEQ:
                byte = data[position]
                if byte == 10:  # A blank line ends the record.
                    self._state = _OUT_READ
                    self._line += 1
                    position += 1
                elif byte == 62:  # ">"
                    self._start_name()
                    position += 1
                else:
                    length = self._line_len
                    if length and offset + position >= self._slow_until:
                        # Lines up to the next record or blank line, which
                        # usually all have the record's width: check them at
                        # once instead of line by line.
                        stop = size
                        for boundary in (b"\n>", b"\n\n"):
                            found = data.find(boundary, position, stop)
                            if found >= 0:
                                stop = found + 1
                        count = (stop - position) // length
                        end = position + count * length
                        if (
                            count
                            and data.count(b"\n", position, end) == count
                            and data[position + length - 1 : end : length]
                            == b"\n" * count
                            and b">" not in data[position:end:length]
                        ):
                            block = data[position:end]
                            self._seq_len += len(block) - len(
                                block.translate(None, _GRAPH)
                            )
                            self._read_done = True
                            self._line += count
                            position = end
                            continue
                        # Irregular lines: read them one at a time up to there.
                        self._slow_until = offset + stop
                    self._state = _SEQ_LINE
                    self._read_done = True
                    self._ll = self._cl = 0
            elif state == _OUT_READ:
                byte = data[position]
                position += 1
                if byte == 62:  # ">"
                    self._start_name()
                elif byte == 10:
                    self._line += 1
                elif byte == 13:
                    self._state = _CR
                elif byte == 59 and leading:  # ";": an ordinary comment line.
                    self._state = _COMMENT
                elif byte == 64:  # "@"
                    raise ValueError(
                        f"Found '@' at line {self._line}: FASTQ is not supported; "
                        "bioheaders faidx indexes FASTA"
                    )
                else:
                    raise ValueError(
                        f"Format error, unexpected {_printable(byte)} at line "
                        f"{self._line}"
                    )
            elif state == _CR:
                if data[position] != 10:
                    self._cr_error()
                self._state = _OUT_READ
                self._line += 1
                position += 1
            elif state == _COMMENT:
                newline = data.find(b"\n", position)
                if newline < 0:
                    return
                position = newline + 1
                self._line += 1
                self._state = _OUT_READ
            elif state == _IN_NAME:
                if not self._name_begun:
                    self._begin_name()
                if not self._name:
                    space = _LEADING_SPACE.match(data, position)
                    assert space is not None  # The pattern matches "" too.
                    position = space.end()
                    if position == size:
                        return
                match = _NAME.match(data, position)
                assert match is not None
                if len(self._name) + match.end() - position > MAX_FAI_LINE:
                    self._long_name(self._line)
                self._name += data[position : match.end()]
                position = match.end()
                if position == size:
                    return
                if data[position] == 10:
                    position += 1
                    self._start_sequence(offset + position)
                else:
                    self._state = _NAME_REST
            else:  # _NAME_REST
                newline = data.find(b"\n", position)
                if newline < 0:
                    return
                position = newline + 1
                self._start_sequence(offset + position)

    def _long_name(self, line: int) -> NoReturn:
        raise ValueError(
            f"Sequence name at line {line} is too long for a .fai index (htslib "
            f"reads index lines of up to {MAX_FAI_LINE} bytes)"
        )

    def _cr_error(self) -> NoReturn:
        raise ValueError(
            "Format error, carriage return not followed by new line at line "
            f"{self._line}"
        )

    def _start_name(self) -> None:
        self._state = _IN_NAME
        self._name_begun = False

    def _begin_name(self) -> None:
        # Like fai_build_core, finish the previous record at the first byte
        # after ">", so a lone ">" at the end of the file is ignored.
        self._name_begun = True
        if self._read_done:
            self._insert()
        elif self._record is not None:
            self.warnings.append(
                f"Record '{self._record.decode('utf-8', 'replace')}' at line "
                f"{self._record_line} has no sequence; it is omitted from the "
                "index, as samtools does"
            )
        self._read_done = False
        self._record = None
        self._name = bytearray()
        self._record_line = self._line

    def _start_sequence(self, offset: int) -> None:
        self._record = bytes(self._name)
        self._state = _IN_SEQ
        self._seq_len = self._line_len = self._char_len = 0
        self._seq_offset = offset
        self._line += 1

    def _end_line(self) -> None:
        self._seq_len += self._cl
        if self._line_len == 0:
            self._line_len = self._ll
            self._char_len = self._cl
            self._state = _IN_SEQ
        elif self._line_len > self._ll:
            # A shorter line ends the record: only a new record or a blank
            # line may follow.
            self._state = _OUT_READ
        elif self._line_len < self._ll:
            name = (self._record or b"").decode("utf-8", "replace")
            raise ValueError(
                f"Different line length in sequence '{name}' at line {self._line}"
            )
        else:
            self._state = _IN_SEQ
        self._line += 1

    def _insert(self) -> None:
        name = self._record if self._record is not None else b""
        if name in self._names:
            raise ValueError(
                f"Duplicate sequence name '{name.decode('utf-8', 'replace')}' at "
                f"line {self._record_line}; htslib would index only the first"
            )
        self._names.add(name)
        record = name + b"\t%d\t%d\t%d\t%d\n" % (
            self._seq_len,
            self._seq_offset,
            self._char_len,
            self._line_len,
        )
        if len(record) > MAX_FAI_LINE:
            self._long_name(self._record_line)
        self.records.append(record)

    def finish(self) -> bytes:
        """Return the ``.fai`` bytes after the last fed byte."""
        state = self._state
        if state == _SEQ_LINE:  # A last line without a terminator.
            self._ll += 1
            self._end_line()
        elif state == _CR:
            self._cr_error()
        elif state == _IN_NAME and self._name_begun:
            raise ValueError(
                f"The last entry '{self._name.decode('utf-8', 'replace')}' has no "
                f"sequence at line {self._line}"
            )
        elif state == _NAME_REST:
            self._record = bytes(self._name)
        if self._read_done:
            self._insert()
            self._read_done = False
        elif self._record is not None or state == _NAME_REST:
            name = (self._record or b"").decode("utf-8", "replace")
            raise ValueError(
                f"File truncated at line {self._line}: the last record '{name}' "
                "has no sequence"
            )
        if not self.records:
            raise ValueError("No FASTA records to index")
        return b"".join(self.records)


def _read_exact(stream: Readable, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def bgzf_blocks(stream: Readable, name: str) -> Iterator[Tuple[int, bytes]]:
    """Yield ``(compressed offset, data)`` for each block of a BGZF stream.

    Each block is checked (header, size, CRC-32 and length) and decompressed to
    at most 64 KiB. Gzip data that is not BGZF is an error, as in htslib.
    """
    address = 0
    while True:
        header = _read_exact(stream, BGZF_HEADER)
        if not header:
            return
        if len(header) < BGZF_HEADER or header[:3] != b"\x1f\x8b\x08":
            raise ValueError(f"Invalid BGZF header at offset {address} in {name}")
        if not (
            header[3] & 4
            and header[10:12] == b"\x06\x00"
            and header[12:16] == b"BC\x02\x00"
        ):
            raise ValueError(GZIP_ERROR)
        size = struct.unpack("<H", header[16:18])[0] + 1
        if size < BGZF_HEADER + 8:
            raise ValueError(f"Invalid BGZF block size at offset {address} in {name}")
        rest = _read_exact(stream, size - BGZF_HEADER)
        if len(rest) < size - BGZF_HEADER:
            raise ValueError(f"Truncated BGZF block at offset {address} in {name}")
        crc, length = struct.unpack("<II", rest[-8:])
        decompressor = zlib.decompressobj(-15)
        try:
            data = decompressor.decompress(rest[:-8], BGZF_MAX_UNCOMPRESSED + 1)
        except zlib.error as error:
            raise ValueError(
                f"Invalid BGZF block at offset {address} in {name}: {error}"
            ) from None
        if (
            not decompressor.eof
            or decompressor.unconsumed_tail
            or len(data) > BGZF_MAX_UNCOMPRESSED
            or len(data) != length
            or zlib.crc32(data) != crc
        ):
            raise ValueError(f"Invalid BGZF block at offset {address} in {name}")
        yield address, data
        address += size


class _Blocks:
    """Decompressed bytes of BGZF blocks, recording the ``.gzi`` entries."""

    def __init__(self, stream: Readable, name: str) -> None:
        self.blocks = bgzf_blocks(stream, name)
        self.entries: List[Tuple[int, int]] = []
        self.uncompressed = 0

    def __iter__(self) -> Iterator[bytes]:
        for address, data in self.blocks:
            if data:  # htslib skips empty blocks, such as the end marker.
                self.entries.append((address, self.uncompressed))
                self.uncompressed += len(data)
                yield data

    def gzi(self) -> bytes:
        # bgzf_index_dump: the count, then every block after the first.
        entries = self.entries[1:]
        return struct.pack("<Q", len(entries)) + b"".join(
            struct.pack("<QQ", *entry) for entry in entries
        )


def build_fai(chunks: Iterable[bytes]) -> Tuple[bytes, List[str]]:
    """Return the ``.fai`` bytes and warnings for FASTA bytes given as chunks.

    FHR header lines of the leading block are skipped exactly as ``strip``
    removes them; offsets still count them.
    """
    builder = FaiBuilder()
    offset = 0
    leading = True
    for part, data in sequence_parts(chunks, b";~"):
        if part is HEADER:
            builder.skip(data)
        elif part is DATA:
            builder.feed(data, offset, leading)
        elif part is END:
            leading = False
            builder.end_leading()
        offset += len(data)
    return builder.finish(), builder.warnings


def build_index(
    stream: Readable, name: str = "<input>"
) -> Tuple[bytes, Optional[bytes], List[str]]:
    """Return ``(fai, gzi, warnings)`` for a FASTA stream, plain or BGZF.

    ``gzi`` is None for plain input. Gzip input that is not BGZF is an error.
    """
    magic = _read_exact(stream, len(GZIP_MAGIC))
    if magic != GZIP_MAGIC:
        fai, warnings = build_fai(chain([magic], read_chunks(stream)))
        return fai, None, warnings
    blocks = _Blocks(_Prefixed(magic, stream), name)
    fai, warnings = build_fai(blocks)
    return fai, blocks.gzi(), warnings


class _Prefixed:
    """A stream that returns ``prefix`` before the rest of ``stream``."""

    def __init__(self, prefix: bytes, stream: Readable) -> None:
        self.prefix = prefix
        self.stream = stream

    def read(self, size: int) -> bytes:
        data, self.prefix = self.prefix[:size], self.prefix[size:]
        if len(data) < size:
            data += self.stream.read(size - len(data)) or b""
        return data
