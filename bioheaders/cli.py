"""Shared command implementations for FHR metadata and sequence files."""

import argparse
import base64
import gzip
import hashlib
import os
import re
import stat
import struct
import sys
import tempfile
import zlib
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from itertools import chain
from pathlib import Path

import yaml
from jsonschema.exceptions import ValidationError

from . import (
    DATA,
    END,
    GFF3_VERSION,
    HEADER,
    __version__,
    cross_check,
    fhr,
    gff3_directive,
    header_text,
    jsonld,
    load_yaml,
    read_chunks,
    selection,
    sequence_parts,
    validation_message,
)

FORMATS = {
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".fa": "fasta",
    ".fasta": "fasta",
    ".fna": "fasta",
    ".faa": "fasta",
    ".gfa": "gfa",
    ".gff3": "gff3",
    ".gff": "gff3",
    ".html": "microdata",
    ".jsonld": "jsonld",
}


# Output paths with these extensions are written as BGZF; input compression is
# detected from the gzip magic bytes, not the extension.
COMPRESSED_SUFFIXES = (".gz", ".bgz")
FORMAT_NAMES = {
    "json": "json",
    "yaml": "yaml",
    "fasta": "fasta",
    "gfa": "gfa",
    "gff3": "gff3",
    "html": "microdata",
    "jsonld": "jsonld",
}
GZIP_MAGIC = b"\x1f\x8b"
STANDARD_STREAM = "-"


def is_compressed_path(path):
    return Path(path).suffix.lower() in COMPRESSED_SUFFIXES


def _uncompressed_path(path):
    path = Path(path)
    return path.with_suffix("") if is_compressed_path(path) else path


def file_format(path):
    try:
        return FORMATS[_uncompressed_path(path).suffix.lower()]
    except KeyError:
        raise ValueError(f"Unsupported file extension: {path}") from None


class _PrefixedStream:
    """A readable stream that returns ``prefix`` before the rest of ``stream``."""

    def __init__(self, prefix, stream):
        self.prefix = prefix
        self.stream = stream

    def read(self, size=-1):
        if not self.prefix:
            return self.stream.read(size)
        if size is None or size < 0:
            data, self.prefix = self.prefix + self.stream.read(), b""
            return data
        data, self.prefix = self.prefix[:size], self.prefix[size:]
        if len(data) < size:
            data += self.stream.read(size - len(data)) or b""
        return data


class _GzipStream:
    """Decompress gzip or BGZF data, reporting corrupt input as ``ValueError``."""

    def __init__(self, stream, name):
        self.gzip = gzip.GzipFile(fileobj=stream, mode="rb")
        self.name = name

    def read(self, size=-1):
        try:
            return self.gzip.read(size)
        except (EOFError, zlib.error, gzip.BadGzipFile) as error:
            reason = str(error) or type(error).__name__
            raise ValueError(f"Invalid gzip input {self.name}: {reason}") from None


@contextmanager
def open_input(path):
    """Open ``path`` (``-`` for stdin) for reading bytes.

    Gzip and BGZF input, recognized by its magic bytes, is decompressed as it is
    read, so checksums cover the decompressed FASTA/GFA bytes.
    """
    if path == STANDARD_STREAM:
        stream, name = sys.stdin.buffer, "<stdin>"
        context = None
    else:
        stream = context = Path(path).open("rb")
        name = os.fspath(path)
    try:
        magic = b""
        while len(magic) < len(GZIP_MAGIC):
            data = stream.read(len(GZIP_MAGIC) - len(magic))
            if not data:
                break
            magic += data
        result = _PrefixedStream(magic, stream)
        yield _GzipStream(result, name) if magic == GZIP_MAGIC else result
    finally:
        if context is not None:
            context.close()


BGZF_BLOCK_SIZE = 0xFF00  # Uncompressed bytes per block, as in htslib.
BGZF_MAX_BLOCK = 0x10000  # Compressed block size limit, header and trailer included.
BGZF_EOF = bytes.fromhex("1f8b08040000000000ff0600424302001b0003000000000000000000")


class BgzfWriter:
    """Write BGZF (blocked gzip, as read by htslib and ``samtools faidx``).

    Each block of at most ``BGZF_BLOCK_SIZE`` bytes is a gzip member whose ``BC``
    extra subfield gives its total size minus one; the standard empty block
    marks the end of the file. ``close`` writes the remaining data and the end
    marker but does not close the underlying stream.
    """

    def __init__(self, stream, level=zlib.Z_DEFAULT_COMPRESSION):
        self.stream = stream
        self.level = level
        self.buffer = b""

    def write(self, data):
        size = len(data)
        data = bytes(data)
        if self.buffer:
            needed = BGZF_BLOCK_SIZE - len(self.buffer)
            self.buffer += data[:needed]
            data = data[needed:]
            if len(self.buffer) < BGZF_BLOCK_SIZE:
                return size
            self._block(self.buffer)
            self.buffer = b""
        start = 0
        while len(data) - start >= BGZF_BLOCK_SIZE:
            self._block(data[start : start + BGZF_BLOCK_SIZE])
            start += BGZF_BLOCK_SIZE
        self.buffer = data[start:]
        return size

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def _block(self, data):
        compressor = zlib.compressobj(self.level, zlib.DEFLATED, -15)
        compressed = compressor.compress(data) + compressor.flush()
        if 18 + len(compressed) + 8 > BGZF_MAX_BLOCK:  # Incompressible: split.
            half = len(data) // 2
            self._block(data[:half])
            self._block(data[half:])
            return
        header = struct.pack(
            "<4BI2BH2BHH",
            0x1F,
            0x8B,
            8,  # Deflate.
            4,  # FEXTRA.
            0,  # MTIME.
            0,
            0xFF,  # Unknown OS.
            6,  # XLEN.
            ord("B"),
            ord("C"),
            2,
            18 + len(compressed) + 8 - 1,  # BSIZE.
        )
        trailer = struct.pack("<II", zlib.crc32(data), len(data))
        self.stream.write(header + compressed + trailer)

    def close(self):
        if self.buffer:
            self._block(self.buffer)
            self.buffer = b""
        self.stream.write(BGZF_EOF)


def read_metadata(path, content=None, format_name=None, ignore_unknown_terms=False):
    """Read metadata in any format; ``ignore_unknown_terms`` applies to JSON-LD only."""
    format_name = format_name or file_format(path)
    data = fhr()
    read = getattr(data, "input_" + format_name)
    if format_name == "jsonld":
        read = partial(read, ignore_unknown_terms=ignore_unknown_terms)
    if content is None:
        with open_input(path) as stream:
            read(stream)
    else:
        read(content)
    return data


def write_metadata(data, path, format_name=None, **options):
    content = getattr(data, "output_" + (format_name or file_format(path)))(**options)
    if path == STANDARD_STREAM or is_compressed_path(path):
        write_to(path, lambda output: output.write(content.encode("utf-8")))
    else:
        write_output(path, lambda output: output.write(content), "w", encoding="utf-8")


def write_to(path, write):
    """Call ``write`` with a binary file object for ``path`` (``-`` for stdout).

    Paths ending in ``.gz`` or ``.bgz`` receive BGZF and other paths plain bytes,
    written atomically by ``write_output``. Stdout is never compressed.
    """
    if path == STANDARD_STREAM:
        write(sys.stdout.buffer)
        sys.stdout.buffer.flush()
    elif is_compressed_path(path):

        def compressed(output):
            stream = BgzfWriter(output)
            write(stream)
            stream.close()

        write_output(path, compressed)
    else:
        write_output(path, write)


def write_output(path, write, mode="wb", **options):
    """Call ``write`` with a file object, then atomically replace ``path``.

    A temporary file in the destination directory receives the output and only
    replaces the destination once ``write`` has succeeded, so a failure never
    leaves partial output. Existing non-regular files such as ``/dev/null`` are
    written directly.
    """
    target = os.path.realpath(path)
    try:
        status = os.stat(target)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        permissions = 0o666 & ~umask
    else:
        if not stat.S_ISREG(status.st_mode):
            with open(path, mode, **options) as output:
                write(output)
            return
        permissions = stat.S_IMODE(status.st_mode)
    directory, name = os.path.split(target)
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{name}.", suffix=".tmp", dir=directory
        )
    except OSError as error:
        # Report the requested path, as a direct write would.
        raise type(error)(error.errno, error.strerror, os.fspath(path)) from None
    try:
        with os.fdopen(descriptor, mode, **options) as output:
            os.chmod(temporary, permissions)
            write(output)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _output_is_input(output, inputs):
    if output == STANDARD_STREAM:
        return False
    output = Path(output)
    inputs = [Path(path) for path in inputs if path != STANDARD_STREAM]
    if any(output.resolve() == path.resolve() for path in inputs):
        return True
    return output.exists() and any(
        output.samefile(path) for path in inputs if path.exists()
    )


def _prefix(kind):
    return b";~" if kind == "fasta" else b"#~"


def _parts(chunks, kind):
    """``sequence_parts`` for a sequence kind (``fasta``, ``gfa`` or ``gff3``)."""
    return sequence_parts(chunks, _prefix(kind), gff3=kind == "gff3")


def strip_parts(chunks, kind):
    """Yield the bytes of FASTA/GFA/GFF3 chunks except FHR header lines."""
    for part, data in _parts(chunks, kind):
        if part is DATA:
            yield data


def _stripped(path, kind):
    with open_input(path) as stream:
        yield from strip_parts(read_chunks(stream), kind)


def _drain(parts):
    for _ in parts:
        pass


def strip_header(content, kind):
    return b"".join(strip_parts(read_chunks(content), kind))


class SequenceScan:
    """FHR header lines and checksum state of FASTA/GFA bytes read in one pass.

    Every byte is hashed as it streams except the scalar checksum line: the root
    indentation of header lines can only decrease as lines arrive, so at most one
    candidate checksum line stays valid, and a digest copied before it excludes it.
    """

    def __init__(self, chunks, kind):
        self.prefix = _prefix(kind)
        # GFF3: the first value of each compared native directive in the
        # leading block (docs/FHGFF3.md, "Native directives").
        self.directives = {}
        in_block = True
        self.pattern = re.compile(
            b"^" + re.escape(self.prefix) + rb"[ \t]*checksum[ \t]*:"
        )
        self.header = []
        self.root_indent = None
        self.matches = 0
        self.checksum_line = None
        self.excluded = None
        try:
            self.digest = hashlib.new("sha512_256")
        except ValueError:
            self.digest = None
        self.hash_available = self.digest is not None
        for part, data in _parts(chunks, kind):
            if part is HEADER:
                self._header_line(data)
            elif part is END:
                in_block = False
                # No more header lines: keep only the digest that can be used.
                self.digest = None
                if self.matches != 1:
                    self.excluded = None
            else:
                if in_block and kind == "gff3" and data.startswith(b"#"):
                    found = gff3_directive(data)
                    if found and found[0] not in self.directives:
                        self.directives[found[0]] = found[1]
                self._update(data)

    def _update(self, data):
        if self.digest is not None:
            self.digest.update(data)
        if self.excluded is not None:
            self.excluded.update(data)

    def _header_line(self, line):
        self.header.append(line)
        metadata = line[len(self.prefix) :]
        if (
            metadata.strip()
            and not metadata.lstrip().startswith(b"#")
            and not re.match(
                rb"^(?:%|---(?:[ \t]|$)|\.\.\.(?:[ \t]|$))",
                metadata.lstrip(b" \t"),
            )
        ):
            indent = len(metadata) - len(metadata.lstrip(b" \t"))
            if self.root_indent is None or indent < self.root_indent:
                self.root_indent = indent
                self.matches = 0
                self.excluded = None
            if indent == self.root_indent and self.pattern.match(line):
                self.matches += 1
                self.checksum_line = line
                self.excluded = None
                if self.matches == 1 and self.digest is not None:
                    self.excluded = self.digest.copy()
                if self.digest is not None:
                    self.digest.update(line)
                return
        self._update(line)

    def checksum(self):
        """Return the FHR checksum after checking the checksum header line."""
        if self.matches != 1:
            raise ValueError("Expected exactly one scalar checksum header line")
        prefix = self.prefix
        # Decode and parse exactly as input_fasta/input_gfa would.
        header = load_yaml("\n".join(header_text(line, prefix) for line in self.header))
        # The excluded line must hold the whole value; continuation lines are hashed.
        try:
            value = load_yaml(header_text(self.checksum_line, prefix))
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
        if not self.hash_available:
            raise ValueError(
                "SHA-512/256 is unavailable in this Python build; "
                "use a Python distribution with OpenSSL support"
            )
        return base64.b64encode(self.excluded.digest()).decode("ascii")


def checksum(content, kind):
    """Hash all original bytes except the one scalar checksum metadata line."""
    return SequenceScan(read_chunks(content), kind).checksum()


def combined_header(data, body, kind, lead=b""):
    """Return the header that combines ``data`` with stripped ``body`` chunks.

    ``lead`` is written before the header: a GFF3 file's ``##gff-version`` line
    (docs/FHGFF3.md G1), which ``body`` then does not include.
    """
    data = fhr(**deepcopy(data.__dict__))
    data.checksum = "A" * 43 + "="
    preliminary = getattr(data, "output_" + kind)().encode("utf-8")
    data.checksum = SequenceScan(chain([lead, preliminary], body), kind).checksum()
    data.fhr_validate()
    return getattr(data, "output_" + kind)().encode("utf-8")


def split_lead(chunks, kind):
    """Return ``(lead, rest)``: the GFF3 version line and the remaining chunks.

    Other kinds have no lead. A GFF3 body must start with ``##gff-version 3``.
    """
    chunks = iter(chunks)
    if kind != "gff3":
        return b"", chunks
    first = b""
    for chunk in chunks:
        first += chunk
        end = min(
            (i for i in (first.find(b"\n"), first.find(b"\r")) if i >= 0), default=-1
        )
        if end >= 0:
            if first[end : end + 2] == b"\r\n":
                end += 1
            break
    else:
        end = len(first) - 1
    lead, rest = first[: end + 1], first[end + 1 :]
    if not lead.startswith(GFF3_VERSION):
        raise ValueError("GFF3 must begin with ##gff-version 3")
    return lead, chain([rest], chunks)


def combine(data, content, kind):
    body = strip_header(content, kind)
    lead, rest = split_lead([body], kind)
    rest = b"".join(rest)
    return lead + combined_header(data, [rest], kind, lead) + rest


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--version", action="version", version=__version__)
    return result


def run(action):
    try:
        return action() or 0
    except ValidationError as error:
        print(
            f"FHR: schema validation failed at {error.json_path}: "
            f"{validation_message(error)}",
            file=sys.stderr,
        )
        return 1
    except RecursionError:
        print("FHR: metadata is nested too deeply", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # The reader of stdout exited; avoid another error when Python exits.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        print("FHR: output pipe closed", file=sys.stderr)
        return 1
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        yaml.YAMLError,
    ) as error:
        print(f"FHR: {error}", file=sys.stderr)
        return 1


def _format_option(args_parser, flag, dest, description):
    args_parser.add_argument(
        flag,
        dest=dest,
        choices=sorted(FORMAT_NAMES),
        help=description + " (default: from the file extension; required for -)",
    )


def _format(path, name):
    if name:
        return FORMAT_NAMES[name]
    if path == STANDARD_STREAM:
        raise ValueError("Give the format of - with --from or --to")
    return file_format(path)


def _check_sequence_path(path, kind, what):
    if path != STANDARD_STREAM and file_format(path) != kind:
        raise ValueError(f"Expected a {kind.upper()} {what}")


# Each command is an ``add_arguments(parser)`` function and an action taking the
# parsed arguments; sequence actions also take the kind (``fasta`` or ``gfa``).
# The ``fhr-*`` commands and the ``bioheaders`` subcommands share them.


def _ignore_unknown_terms_option(args_parser):
    args_parser.add_argument(
        "--ignore-unknown-terms",
        action="store_true",
        help="JSON-LD input only: report terms that do not map to an FHR field as "
        "warnings instead of errors",
    )


def _convert_arguments(args_parser):
    args_parser.add_argument("input", help="input file, or - for stdin")
    args_parser.add_argument("output", help="output file, or - for stdout")
    _format_option(args_parser, "--from", "input_format", "input format")
    _format_option(args_parser, "--to", "output_format", "output format")
    _ignore_unknown_terms_option(args_parser)
    args_parser.add_argument(
        "--export-context",
        metavar="FILE",
        help="JSON-LD output only: YAML or JSON file with the dataset's id, url and "
        "keywords, which are not FHR fields; Bioschemas Dataset conformance is "
        "claimed only when every minimum property is present (provisional)",
    )
    args_parser.add_argument(
        "--jsonld-profile",
        choices=("canonical", "export"),
        default="canonical",
        help="JSON-LD output only: canonical (default) writes the round-trip form; "
        "export writes the one-way schema.org graph of FAIR-bioHeaders-Specification "
        "docs/SCHEMAORG-EXPORT.md, which cannot be read back (provisional)",
    )


def _read_export_context(path):
    with open_input(path) as stream:
        return load_yaml(stream.read().decode("utf-8"))


# Formats whose writers follow the FHR schema only (FAIR-bioHeaders-Specification spec 006,
# follow-ups F-01 and F-02).
FHR_ONLY_FORMATS = ("jsonld", "microdata")


def _convert(args):
    input_format = _format(args.input, args.input_format)
    output_format = _format(args.output, args.output_format)
    if args.export_context and output_format != "jsonld":
        raise ValueError("--export-context applies only to JSON-LD output")
    if args.jsonld_profile != "canonical" and output_format != "jsonld":
        raise ValueError("--jsonld-profile applies only to JSON-LD output")
    if _output_is_input(args.output, [args.input]):
        raise ValueError("Output must differ from the input file")
    options = {}
    if args.export_context:
        options["export"] = jsonld.check_export(
            _read_export_context(args.export_context)
        )
    data = read_metadata(
        args.input,
        format_name=input_format,
        ignore_unknown_terms=args.ignore_unknown_terms,
    )
    data.fhr_validate()
    if output_format in FHR_ONLY_FORMATS and data.header_type() != "FHR":
        raise ValueError(
            "JSON-LD and HTML microdata output are not available for "
            f"{data.header_type()} metadata yet"
        )
    if output_format == "jsonld" and args.jsonld_profile == "export":
        options["profile"] = "export"
        for path in jsonld.export_unmapped_keys(data.__dict__):
            print(
                f"FHR: JSON-LD export: {path} has no export target; it was left out",
                file=sys.stderr,
            )
    elif output_format == "jsonld":
        for path in jsonld.unmapped_keys(data.__dict__):
            print(
                f"FHR: JSON-LD: {path} has no JSON-LD term; linked-data consumers "
                "will ignore it",
                file=sys.stderr,
            )
        if "export" in options:
            missing = jsonld.bioschemas_missing(
                jsonld.to_jsonld(data.__dict__, export=options["export"])
            )
            if missing:
                print(
                    "FHR: JSON-LD: not claiming Bioschemas Dataset conformance; "
                    f"missing: {', '.join(missing)}",
                    file=sys.stderr,
                )
    write_metadata(data, args.output, output_format, **options)


def _validate_arguments(args_parser):
    args_parser.add_argument("input", help="input file, or - for stdin")
    _format_option(args_parser, "--from", "input_format", "input format")
    _ignore_unknown_terms_option(args_parser)


def _validate(args):
    input_format = _format(args.input, args.input_format)
    data = read_metadata(
        args.input,
        format_name=input_format,
        ignore_unknown_terms=args.ignore_unknown_terms,
    )
    data.fhr_validate()
    print(f"{data.header_type()} metadata is valid.")


def _default_combine_output(sequence, kind, header="FHR"):
    if sequence == STANDARD_STREAM:
        return STANDARD_STREAM
    path = Path(sequence)
    output = _uncompressed_path(path).with_suffix(f".{header.lower()}.{kind}")
    if is_compressed_path(path):
        output = output.with_name(output.name + path.suffix)
    return str(output)


def _combine_arguments(args_parser):
    args_parser.add_argument("metadata")
    args_parser.add_argument("sequence", help="sequence file, or - for stdin")
    args_parser.add_argument("-o", "--output", help="output file, or - for stdout")


def _combine(args, kind):
    data = None
    output = args.output
    if output is None:
        # The default name follows the header type (X.fhr.fasta, X.fhp.fasta).
        data = read_metadata(args.metadata)
        output = _default_combine_output(args.sequence, kind, data.header_type())
    if _output_is_input(output, [args.sequence, args.metadata]):
        raise ValueError("Output must differ from the input files")
    if data is None:
        data = read_metadata(args.metadata)
    if args.sequence != STANDARD_STREAM:
        # Hash the stripped sequence, then read it again to write it.
        lead, rest = split_lead(_stripped(args.sequence, kind), kind)
        header = combined_header(data, rest, kind, lead)

        def write(output):
            lead, rest = split_lead(_stripped(args.sequence, kind), kind)
            output.write(lead)
            output.write(header)
            output.writelines(rest)

        write_to(output, write)
        return
    # Stdin can be read only once: spool the stripped sequence while hashing.
    with tempfile.TemporaryFile() as spool:

        def spooled():
            for data in _stripped(STANDARD_STREAM, kind):
                spool.write(data)
                yield data

        lead, rest = split_lead(spooled(), kind)
        header = combined_header(data, rest, kind, lead)
        spool.seek(0)

        def write(output):
            lead, rest = split_lead(read_chunks(spool), kind)
            output.write(lead)
            output.write(header)
            output.writelines(rest)

        write_to(output, write)


def _strip_arguments(args_parser):
    args_parser.add_argument("input", help="input file, or - for stdin")
    args_parser.add_argument(
        "output", nargs="?", help="output file, or - for stdout (the default)"
    )


def _strip(args, kind):
    output = args.output or STANDARD_STREAM
    if _output_is_input(output, [args.input]):
        _drain(_stripped(args.input, kind))  # Report input errors first.
        raise ValueError("Output must differ from the input file")
    if output == STANDARD_STREAM and args.input != STANDARD_STREAM:
        # Find input errors before writing anything to stdout.
        _drain(_stripped(args.input, kind))
    write_to(output, lambda stream: stream.writelines(_stripped(args.input, kind)))


def _verify_arguments(args_parser):
    args_parser.add_argument("input", help="input file, or - for stdin")


def directive_warnings(data, scan, kind):
    """Cross-check warnings for a GFF3 file's FHGFF3 header (never errors)."""
    if kind != "gff3" or data.header_type() != "FHGFF3":
        return []
    return cross_check(data.__dict__, scan.directives)


def _verify(args, kind):
    with open_input(args.input) as stream:
        scan = SequenceScan(read_chunks(stream), kind)
    data = fhr()
    data._input_header_lines(scan.header, scan.prefix)
    data.fhr_validate()
    if data.checksum != scan.checksum():
        raise ValueError("Checksum verification failed")
    for warning in directive_warnings(data, scan, kind):
        print(f"FHR: warning: {warning}", file=sys.stderr)
    print("Checksum verified.")


IDENTITY_NOTICE = (
    "A match confirms file identity only, not that the translations are correct."
)
# FHGFF3 files (FAIR-bioHeaders-Specification spec 007 contracts/cli.md) get a wider notice.
ANNOTATION_NOTICE = (
    "A match confirms file identity only, not that the annotation or translations "
    "are correct."
)


def _links_arguments(args_parser):
    args_parser.add_argument(
        "input", help="FASTA, GFA or GFF3 file whose header records its parent files"
    )
    args_parser.add_argument(
        "parents",
        nargs="*",
        metavar="PARENT",
        help="candidate parent files (FASTA, GFA or GFF3, plain or gzip/BGZF)",
    )
    args_parser.add_argument(
        "--require-all",
        action="store_true",
        help="also fail when a recorded parent could not be checked",
    )


def _parent(path):
    """Return (computed checksum, header type, reason, metadata) for a candidate.

    The checksum is computed from the file's bytes (FAIR-bioHeaders-Specification R1 to R4).
    The header type comes from a FAIR-bioHeaders schema URL (FAIR-bioHeaders-Specification
    docs/SCHEMA-VERSIONS.md), or is FHR for another URL ending in /fhr.json, and is
    otherwise unknown (``None``). When no checksum can be
    computed, the checksum and metadata are ``None`` and ``reason`` says why.
    """
    suffix = _uncompressed_path(Path(path)).suffix.lower()
    kind = FORMATS.get(suffix)
    if kind not in SEQUENCE_KINDS:
        return None, None, "unsupported file type", None
    with open_input(path) as stream:
        scan = SequenceScan(read_chunks(stream), kind)
    data = fhr()
    try:
        data._input_header_lines(scan.header, scan.prefix)
        computed = scan.checksum()
    except ValueError as error:
        return None, None, str(error), None
    schema = data.__dict__.get("schema")
    if selection.parse(schema) is not None:
        found = selection.header_type(schema)
    elif isinstance(schema, str) and schema.endswith("/fhr.json"):
        found = "FHR"
    else:
        found = None
    return computed, found, None, data.__dict__


def genome_reference_result(reference, parents):
    """Compare a ``genomeReference`` with supplied FHR genomes (spec 007 D-08).

    Returns ``(status, detail, matched paths)``. Only an FHR genome whose own
    header records a SeqCol digest can be compared; no digest is computed.
    """
    genomes = [p for p in parents if p[1] is not None and p[2] == "FHR"]
    if not genomes:
        return "not checked", "no FHR genome supplied", []
    recorded = [p for p in genomes if isinstance(p[4].get("seqcol_id"), str)]
    if not recorded:
        names = ", ".join(p[0] for p in genomes)
        return "not checked", f"{names}: no seqcol_id recorded", []
    matched, different = [], []
    for path, _, _, _, metadata in recorded:
        accession = (metadata.get("accessionID") or {}).get("name")
        same = metadata["seqcol_id"] == reference.get("seqcol_id") and (
            accession is None or accession == reference.get("accession")
        )
        (matched if same else different).append(path)
    if matched:
        return "matched", ", ".join(matched), matched
    return (
        "not matched",
        "; ".join(
            f"{path} records seqcol_id {meta['seqcol_id']}"
            for path, _, _, _, meta in recorded
        ),
        [],
    )


def _verify_links(args, kind):
    """Compare recorded derivedFrom parents with files; never write anything."""
    with open_input(args.input) as stream:
        scan = SequenceScan(read_chunks(stream), kind)
    data = fhr()
    data._input_header_lines(scan.header, scan.prefix)
    data.fhr_validate()
    if data.checksum != scan.checksum():
        raise ValueError("Checksum verification failed")
    parents = [(path,) + _parent(path) for path in args.parents]
    entries = data.__dict__.get("derivedFrom") or []
    reference = data.__dict__.get("genomeReference")
    used, explained = set(), set()
    mismatch = unchecked = False
    if not entries and not reference:
        print("no parent files recorded")
    for index, entry in enumerate(entries):
        label = f"derivedFrom[{index}] {entry['headerType']} {entry['relationship']}"
        matches = [p for p in parents if p[1] is not None and p[1] == entry["checksum"]]
        if matches:
            used.update(p[0] for p in matches)
            print(f"{label}: matched ({', '.join(p[0] for p in matches)})")
            continue
        same_type = [
            p for p in parents if p[1] is not None and p[2] == entry["headerType"]
        ]
        if same_type:
            mismatch = True
            detail = "; ".join(f"{p[0]} has checksum {p[1]}" for p in same_type)
            print(f"{label}: not matched ({detail})")
            continue
        unchecked = True
        unsupported = [
            p for p in parents if p[1] is None and p[2] == entry["headerType"]
        ]
        explained.update(p[0] for p in unsupported)
        reason = (
            "; ".join(f"{p[0]}: {p[3]}" for p in unsupported)
            or "no supplied file of that header type"
        )
        print(f"{label}: not checked ({reason})")
    if reference:
        status, detail, matched = genome_reference_result(reference, parents)
        used.update(matched)
        mismatch = mismatch or status == "not matched"
        unchecked = unchecked or status == "not checked"
        print(f"genomeReference {reference.get('accession')}: {status} ({detail})")
    for path, computed, _, reason, _ in parents:
        if computed is not None and path not in used:
            print(f"{path}: not a recorded parent")
        elif computed is None and path not in explained:
            print(f"{path}: not checked ({reason})")
    for warning in directive_warnings(data, scan, kind):
        print(f"warning: {warning}")
    print(ANNOTATION_NOTICE if data.header_type() == "FHGFF3" else IDENTITY_NOTICE)
    if mismatch or (args.require_all and unchecked):
        return 3
    return 0


def _command(description, add_arguments, perform):
    def action():
        args_parser = parser(description)
        add_arguments(args_parser)
        return perform(args_parser.parse_args())

    return run(action)


def _sequence_command(description, add_arguments, perform, kind, path, what):
    def checked(args):
        _check_sequence_path(getattr(args, path), kind, what)
        return perform(args, kind)

    return _command(description, add_arguments, checked)


def convert_main():
    return _command(
        "Convert FHR metadata between JSON, YAML, JSON-LD, FASTA, GFA, and HTML",
        _convert_arguments,
        _convert,
    )


def validate_main():
    return _command(
        "Validate FHR metadata against the bundled schema",
        _validate_arguments,
        _validate,
    )


def combine_main(kind):
    return _sequence_command(
        f"Combine metadata with {kind.upper()} and calculate its FHR checksum",
        _combine_arguments,
        _combine,
        kind,
        "sequence",
        "sequence file",
    )


def strip_main(kind):
    return _sequence_command(
        f"Strip FHR metadata from {kind.upper()} without changing other bytes",
        _strip_arguments,
        _strip,
        kind,
        "input",
        "file",
    )


def checksum_main(kind):
    return _sequence_command(
        f"Validate {kind.upper()} metadata and its FHR checksum",
        _verify_arguments,
        _verify,
        kind,
        "input",
        "file",
    )


def fasta_combine_main():
    return combine_main("fasta")


def fasta_strip_main():
    return strip_main("fasta")


def fasta_validate_main():
    return checksum_main("fasta")


def gfa_combine_main():
    return combine_main("gfa")


def gfa_strip_main():
    return strip_main("gfa")


def gfa_validate_main():
    return checksum_main("gfa")


def gff3_combine_main():
    return combine_main("gff3")


def gff3_strip_main():
    return strip_main("gff3")


def gff3_validate_main():
    return checksum_main("gff3")


SEQUENCE_KINDS = ("fasta", "gfa", "gff3")


class Subcommand:
    """A ``bioheaders`` subcommand.

    ``sequence`` names the FASTA/GFA path argument of commands that take a
    ``--type``; their action receives the kind given or detected from it.
    """

    def __init__(self, name, summary, description, add_arguments, perform, **options):
        self.name = name
        self.summary = summary
        self.description = description
        self.add_arguments = add_arguments
        self.perform = perform
        self.aliases = options.get("aliases", ())
        self.sequence = options.get("sequence")
        self.epilog = options.get("epilog")

    def add_to(self, subparsers):
        extra = {}
        if self.epilog:
            extra = {
                "epilog": self.epilog,
                "formatter_class": argparse.RawDescriptionHelpFormatter,
            }
        args_parser = subparsers.add_parser(
            self.name,
            aliases=list(self.aliases),
            help=self.summary,
            description=self.description,
            **extra,
        )
        self.add_arguments(args_parser)
        if self.sequence:
            args_parser.add_argument(
                "--type",
                dest="sequence_type",
                choices=SEQUENCE_KINDS,
                help="sequence file type (default: from the file extension, "
                "ignoring .gz or .bgz; required for -)",
            )
        args_parser.set_defaults(subcommand=self)

    def __call__(self, args):
        if not self.sequence:
            return self.perform(args)
        path = getattr(args, self.sequence)
        return self.perform(args, sequence_kind(path, args.sequence_type))


def sequence_kind(path, name=None):
    """Return ``name``, or the FASTA/GFA kind of ``path`` from its extension."""
    if name:
        return name
    if path == STANDARD_STREAM:
        raise ValueError("Give the type of - with --type fasta, gfa or gff3")
    kind = file_format(path)
    if kind not in SEQUENCE_KINDS:
        raise ValueError(f"Expected a FASTA, GFA or GFF3 file: {path}")
    return kind


ASSESS_TYPES = ("auto", "fasta", "gff3", "gaf", "vcf", "gfa")
ASSESS_EPILOG = """\
Reports, for each of the 41 RDA FAIR Data Maturity Model indicators, a status
with the header lines it rests on and a suggestion for each gap. There is no
score. No network access is made unless --online is given; then only the
identifiers and URLs in the header are resolved (through doi.org,
identifiers.org or the URL itself), never file contents. Exit codes:
0 assessed (any statuses), 1 an input could not be read, 2 usage error,
3 --fail-on-mismatch and a recorded link did not match the related file.

Indicator identifiers and titles from: FAIR Data Maturity Model Working Group
(2020). FAIR Data Maturity Model. Specification and Guidelines. Research Data
Alliance. doi:10.15497/rda00050. Licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). File-header interpretations
are adaptations by FAIR-bioHeaders and are not endorsed by the RDA."""


def _non_negative(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def _positive_seconds(text):
    value = float(text)
    if not value > 0 or value == float("inf"):
        raise argparse.ArgumentTypeError("must be a positive number of seconds")
    return value


def _positive(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _assess_arguments(args_parser):
    args_parser.add_argument(
        "inputs",
        nargs="+",
        metavar="PATH",
        help="file to assess, or - for stdin; several files, or a directory with "
        "--recursive, run batch mode",
    )
    args_parser.add_argument(
        "--type",
        dest="assess_type",
        choices=ASSESS_TYPES,
        default="auto",
        help="input format (default: auto, from the content, then the file name; "
        "required for -)",
    )
    args_parser.add_argument(
        "--format",
        dest="report_format",
        choices=("text", "markdown", "json"),
        default="text",
        help="report format written to stdout (default: text)",
    )
    args_parser.add_argument(
        "--output",
        metavar="DIR",
        help="write NAME.assessment.json and NAME.assessment.md to DIR instead "
        "(batch mode: per-file reports mirroring the input tree, plus summary.json, "
        "summary.md and summary.tsv; required)",
    )
    args_parser.add_argument(
        "--recursive",
        action="store_true",
        help="descend into directories given as PATH (batch mode)",
    )
    args_parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="batch mode: assess only paths (relative to the directory) matching "
        "GLOB; repeatable. Hidden files are assessed only when a GLOB names them",
    )
    args_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="batch mode: skip paths matching GLOB; repeatable",
    )
    args_parser.add_argument(
        "--jobs",
        type=_positive,
        metavar="N",
        help="batch mode: files assessed in parallel (default: CPU count, at most 8); "
        "the output does not depend on N",
    )
    args_parser.add_argument(
        "--pairs",
        metavar="TSV",
        help="batch mode: derived<TAB>related paths, relative to the directory; "
        "cannot be combined with --related",
    )
    args_parser.add_argument(
        "--record-limit",
        type=_non_negative,
        default=1000,
        metavar="N",
        help="data records sampled after the header (default: 1000; 0: header only)",
    )
    args_parser.add_argument(
        "--hash-inputs",
        action="store_true",
        help="add the SHA-256 of the whole input file (costs a full read)",
    )
    args_parser.add_argument(
        "--related",
        metavar="FILE",
        help="related file (usually the genome FASTA): verify the recorded links "
        "and compare sequence names and lengths",
    )
    args_parser.add_argument(
        "--online",
        action="store_true",
        help="resolve the identifiers and URLs in the header (opt-in; only those "
        "values are sent, never file contents; private addresses are refused)",
    )
    args_parser.add_argument(
        "--online-timeout",
        type=_positive_seconds,
        metavar="SECONDS",
        help="per-request timeout for --online (default: 10)",
    )
    args_parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="exit 3 if a recorded link does not match the related file",
    )


def _assess_batch(args):
    from .assess import batch

    try:
        summary, mismatch = batch.run(
            args.inputs,
            args.output,
            pairs=args.pairs,
            jobs=args.jobs,
            related=args.related,
            include=args.include,
            exclude=args.exclude,
            recursive=args.recursive,
            record_limit=args.record_limit,
            hash_inputs=args.hash_inputs,
            type_option=None if args.assess_type == "auto" else args.assess_type,
            online=args.online,
            online_timeout=args.online_timeout,
            progress=print,
        )
    except batch.UsageError as error:
        print(f"FHR: {error}", file=sys.stderr)
        return 2
    print()
    print(batch.counts_table(summary), end="")
    print(f"\nSummary: {os.path.join(args.output, 'summary.md')}")
    for error in summary["errors"]:
        print(f"FHR: {error['path']}: {error['message']}", file=sys.stderr)
    if summary["errors"]:
        return 1
    return 3 if args.fail_on_mismatch and mismatch else 0


def _assess(args):
    from .assess import assess_file, render

    if args.pairs and args.related:
        print("FHR: give --pairs or --related, not both", file=sys.stderr)
        return 2
    if args.online_timeout is not None and not args.online:
        print("FHR: --online-timeout needs --online", file=sys.stderr)
        return 2
    if (
        len(args.inputs) > 1
        or args.recursive
        and any(os.path.isdir(path) for path in args.inputs)
    ):
        return _assess_batch(args)
    (args.input,) = args.inputs
    if os.path.isdir(args.input):
        print(f"FHR: {args.input} is a directory: give --recursive", file=sys.stderr)
        return 2
    if args.pairs:
        print(
            "FHR: --pairs needs batch mode (a directory or several files)",
            file=sys.stderr,
        )
        return 2
    if args.input == STANDARD_STREAM and args.assess_type == "auto":
        print("FHR: give the format of - with --type", file=sys.stderr)
        return 2
    status = 0
    if args.related:
        from .assess import related

        scanned = related.scan(args.related)
        if scanned.error:
            print(f"FHR: related file: {scanned.error}", file=sys.stderr)
            status = 1
    report = assess_file(
        args.input,
        related=args.related,
        record_limit=args.record_limit,
        hash_inputs=args.hash_inputs,
        type_option=None if args.assess_type == "auto" else args.assess_type,
        online=args.online,
        online_timeout=args.online_timeout,
    )
    if report["input"]["scope"] == "error":
        print(f"FHR: {report['input']['error']}", file=sys.stderr)
        status = 1
    mismatch = any(
        (link.get("verification") or {}).get("verdict") == "mismatch"
        for link in report["links"]
    )
    if status == 0 and args.fail_on_mismatch and mismatch:
        status = 3
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        name = "stdin" if args.input == STANDARD_STREAM else Path(args.input).name
        base = os.path.join(args.output, name + ".assessment")
        json_text = render.to_json(report)
        markdown = render.to_markdown(report)
        write_output(
            base + ".json",
            lambda out: out.write(json_text),
            "w",
            encoding="utf-8",
            newline="\n",
        )
        write_output(
            base + ".md",
            lambda out: out.write(markdown),
            "w",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"{args.input}: {report['input']['scope'].replace('_', ' ')}; report {base}.json"
        )
        return status
    render_format = {
        "text": render.to_text,
        "markdown": render.to_markdown,
        "json": render.to_json,
    }[args.report_format]
    sys.stdout.buffer.write(render_format(report).encode("utf-8"))
    sys.stdout.buffer.flush()
    return status


# FHR (reference genome) commands. Commands for other header types can be added
# as further subcommands or a separate list without changing these.
SUBCOMMANDS = (
    Subcommand(
        "convert",
        "convert metadata between JSON, YAML, JSON-LD, FASTA, GFA, and HTML",
        "Convert FHR metadata between JSON, YAML, JSON-LD, FASTA, GFA, and HTML",
        _convert_arguments,
        _convert,
    ),
    Subcommand(
        "validate",
        "validate metadata against the bundled schema",
        "Validate FHR metadata against the bundled schema",
        _validate_arguments,
        _validate,
    ),
    Subcommand(
        "combine",
        "combine metadata with FASTA or GFA and calculate its checksum",
        "Combine metadata with FASTA or GFA and calculate its FHR checksum",
        _combine_arguments,
        _combine,
        sequence="sequence",
    ),
    Subcommand(
        "strip",
        "strip metadata from FASTA or GFA without changing other bytes",
        "Strip FHR metadata from FASTA or GFA without changing other bytes",
        _strip_arguments,
        _strip,
        sequence="input",
    ),
    Subcommand(
        "verify",
        "validate FASTA or GFA metadata and verify its checksum",
        "Validate FASTA or GFA metadata and its FHR checksum",
        _verify_arguments,
        _verify,
        aliases=("checksum",),
        sequence="input",
    ),
    Subcommand(
        "verify-links",
        "check recorded parent files (derivedFrom) against files on disk",
        "Check the parent files recorded in a FASTA or GFA header's derivedFrom "
        "against candidate files by their FAIR-bioHeaders checksums; nothing is "
        "written. Exit codes: 0 no recorded parent failed to match, 1 an input "
        "could not be read or validated, 2 usage error, 3 a recorded parent did "
        "not match (or, with --require-all, could not be checked).",
        _links_arguments,
        _verify_links,
        sequence="input",
    ),
    Subcommand(
        "assess",
        "assess how FAIR the header of a data file is (offline by default)",
        "Assess the header of a FASTA, GFF3, GAF, VCF, GFA or other text file "
        "against the RDA FAIR Data Maturity Model indicators, offline by default",
        _assess_arguments,
        _assess,
        epilog=ASSESS_EPILOG,
    ),
)


def main():
    """Run the ``bioheaders`` command."""

    def action():
        args_parser = parser(
            "Convert, validate, combine, strip, and verify FAIR-bioHeaders (FHR) "
            "metadata in JSON, YAML, JSON-LD, FASTA, GFA, and HTML"
        )
        subparsers = args_parser.add_subparsers(
            title="commands", dest="command", metavar="COMMAND"
        )
        subparsers.required = True
        for subcommand in SUBCOMMANDS:
            subcommand.add_to(subparsers)
        args = args_parser.parse_args()
        return args.subcommand(args)

    return run(action)
