"""FAIR-bioHeaders tools: FHR metadata parsing, serialization, and validation."""

import codecs
import json
import math
import re
from collections.abc import Hashable
from copy import deepcopy
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
from importlib.resources import files
from itertools import chain

import yaml
from jsonschema import Draft202012Validator, FormatChecker

__version__ = "0.8.1"
SCHEMA = json.loads(
    files(__package__).joinpath("fhr_schema.json").read_text(encoding="utf-8")
)
ITEM_TYPE = SCHEMA["$id"]
# Microdata written before the 0.7.0 repository rename names the old repository in
# itemtype; either raw-main fhr.json URL identifies an FHR item (SCHEMA-VERSIONS.md).
ITEM_TYPES = frozenset(
    {
        ITEM_TYPE,
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FHR-Specification/main/fhr.json",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/main/fhr.json",
    }
)
# The draft protein header FHP (FAIR-bioHeaders-Specification spec 006) and the draft GFF3
# annotation header FHGFF3 (spec 007). The header type and the schema come from the
# record's ``schema`` URL (FAIR-bioHeaders-Specification docs/SCHEMA-VERSIONS.md, ``selection``);
# a record whose ``schema`` is not a FAIR-bioHeaders schema URL is FHR.
FHP_SCHEMA = json.loads(
    files(__package__).joinpath("fhp_schema.json").read_text(encoding="utf-8")
)
FHGFF3_SCHEMA = json.loads(
    files(__package__).joinpath("fhgff3_schema.json").read_text(encoding="utf-8")
)
SCHEMAS = {"FHR": SCHEMA, "FHP": FHP_SCHEMA, "FHGFF3": FHGFF3_SCHEMA}

from . import selection  # noqa: E402  (needs the copies above for its cache)
from .selection import UnsupportedSchemaVersion  # noqa: E402,F401

for _kind, _name in selection.BUNDLED["current"]["files"].items():
    selection._CACHE[_name] = SCHEMAS[_kind]


def is_fhp_schema(value):
    """Whether ``value`` is an FHP schema URL."""
    return selection.parse(value) is not None and selection.header_type(value) == "FHP"


def is_fhgff3_schema(value):
    """Whether ``value`` is an FHGFF3 schema URL."""
    return (
        selection.parse(value) is not None and selection.header_type(value) == "FHGFF3"
    )


def header_type(metadata):
    """Return ``"FHGFF3"``, ``"FHP"`` or ``"FHR"`` for a metadata mapping, from its
    ``schema``."""
    return selection.header_type(metadata.get("schema"))


def schema_for(metadata):
    """The bundled JSON Schema that ``metadata`` is validated against.

    Raises :class:`UnsupportedSchemaVersion` when its ``schema`` URL names a
    version this package does not bundle (FAIR-bioHeaders-Specification rule V4)."""
    return selection.select(metadata.get("schema"))[2]


# YAML treats these as line breaks, but FASTA/GFA line splitting does not.
YAML_ONLY_LINE_BREAKS = "\x85\u2028\u2029"
# Characters at which kseq-based FASTA readers start a record anywhere in a line
# (FAIR-bioHeaders-Specification docs/FORMAT.md R11). FASTA header writers escape
# them in double-quoted YAML scalars; YAML readers return the characters.
RECORD_MARKERS = {">": "\\x3E", "@": "\\x40"}
# FASTA/GFA files are read in chunks; only FHR header lines are held whole.
CHUNK_SIZE = 2**20
# Limits that keep hostile input from exhausting memory or CPU. Real headers have
# a few kilobytes and some dozens of lines and YAML nodes.
MAX_HEADER_BYTES = 2**20
MAX_HEADER_LINES = 10_000
MAX_YAML_NODES = 20_000
MAX_YAML_DEPTH = 64
# Metadata files (JSON, YAML, JSON-LD, HTML) are read whole, after decompression.
MAX_METADATA_BYTES = 64 * 2**20
HEADER, DATA, END = "header", "data", "end"
_MAYBE_BLANK = "maybe blank"


def _read(stream):
    if not hasattr(stream, "read"):
        return stream
    value = stream.read(MAX_METADATA_BYTES + 1)
    if len(value) > MAX_METADATA_BYTES:
        raise ValueError(
            f"Metadata input exceeds the {MAX_METADATA_BYTES // 2**20} MiB size limit"
        )
    return value


def _text(stream):
    value = _read(stream)
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        raise TypeError("Expected text or a readable stream")
    # A UTF-8 byte order mark is an encoding signature, not metadata.
    return value[1:] if value.startswith("\ufeff") else value


def split_lines(content):
    """Split FASTA/GFA bytes into lines, keeping each original terminator."""
    if content.startswith(codecs.BOM_UTF8):
        raise ValueError("FASTA/GFA files must not begin with a UTF-8 byte order mark")
    return content.splitlines(keepends=True)


def _bytes(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes):
        raise TypeError("Expected bytes, text, or a readable stream")
    return value


def read_chunks(stream, size=CHUNK_SIZE):
    """Yield bytes chunks from bytes, text, or a readable stream."""
    if hasattr(stream, "read"):
        while True:
            chunk = stream.read(size)
            if not chunk:
                return
            yield _bytes(chunk)
    content = _bytes(stream)
    for start in range(0, len(content), size):
        yield content[start : start + size]


GFF3_VERSION = b"##gff-version 3"
# FHGFF3 G1: line 1 is "##gff-version 3", optionally followed by ".x.y", then
# spaces or tabs. The line terminator (LF, CRLF or a lone CR) is not part of it.
GFF3_VERSION_LINE = re.compile(rb"##gff-version 3(?:\.\d+\.\d+)?[ \t]*$")
GFF3_FASTA = b"##FASTA"


def is_gff3_version_line(line):
    """Whether ``line`` is a G1 ``##gff-version`` line, ignoring its terminator."""
    return GFF3_VERSION_LINE.fullmatch(line.rstrip(b"\r\n")) is not None


def sequence_parts(chunks, prefix, gff3=False):
    """Yield ``(kind, bytes)`` parts of FASTA/GFA/GFF3 bytes given as chunks, in order.

    Lines are split as ``bytes.splitlines(keepends=True)`` splits the whole input.
    Each FHR line of the leading header block is one ``HEADER`` part; all other
    bytes are ``DATA`` parts of any size, and ``END`` (empty) marks the first
    record. The block ends at a FASTA ``>`` line, or a nonblank GFA line that is
    not a ``#`` comment; ordinary comments and blank lines may be mixed in. Later
    FHR lines are rejected. Only header lines are held whole, up to
    ``MAX_HEADER_BYTES`` in total.

    With ``gff3`` (FAIR-bioHeaders-Specification docs/FHGFF3.md G1), the block also ends at a
    ``##FASTA`` line, and header lines are allowed only after a first line that
    matches ``##gff-version 3`` with an optional ``.x.y`` version.
    """
    fasta = prefix == b";~"
    versioned = None  # GFF3: whether line 1 is ##gff-version 3 (None: unknown yet).
    pending = b""  # Unprocessed header block bytes: at most two.
    started = False
    in_header = True
    line = None  # Kind of the current header block line; None at a line start.
    first_line = bytearray()  # GFF3 line 1, which may span chunks.
    parts = []
    header_size = 0
    header_count = 0
    lines = 0  # Line terminators before the unprocessed bytes.
    tail = b""  # Last bytes after the header block, to find split prefixes.
    after_cr = False
    for chunk in chain(chunks, [None]):
        final = chunk is None
        if in_header:
            if final:
                data = pending
            elif pending:
                data = pending + chunk
            else:
                data = chunk
            if not started:
                if len(data) < len(codecs.BOM_UTF8) and not final:
                    pending = data
                    continue
                if data.startswith(codecs.BOM_UTF8):
                    raise ValueError(
                        "FASTA/GFA files must not begin with a UTF-8 byte order mark"
                    )
                started = True
            position, size = 0, len(data)
            # Next \n and \r at or after position, or size if there is none.
            newline = carriage_return = -1
            while position < size:
                if line is None:
                    if size - position < len(prefix) and not final:
                        break
                    if gff3 and lines:
                        if size - position < len(GFF3_FASTA) and not final:
                            break
                        if data.startswith(GFF3_FASTA, position):
                            in_header = False
                            break
                    if data.startswith(prefix, position):
                        if gff3 and not versioned:
                            raise ValueError(
                                "FHGFF3 header lines must follow ##gff-version 3 "
                                "on line 1"
                            )
                        line = HEADER
                    elif fasta and data.startswith(b">", position):
                        in_header = False
                        break
                    elif fasta or data.startswith(b"#", position):
                        line = DATA
                    else:
                        line = _MAYBE_BLANK
                if newline < position:
                    newline = data.find(b"\n", position)
                    newline = size if newline < 0 else newline
                if carriage_return < position:
                    carriage_return = data.find(b"\r", position)
                    carriage_return = size if carriage_return < 0 else carriage_return
                end = min(newline, carriage_return) + 1
                complete = end <= size
                if not complete:
                    end = size
                elif end - 1 == carriage_return:  # Perhaps \r\n.
                    if end < size:
                        end += data[end] == 10
                    elif not final:
                        end -= 1
                        complete = False
                piece = data[position:end]
                # A trailing CR may be the first byte of CRLF, so it is held for
                # the next chunk; the line content before it is already complete.
                held_cr = not complete and not final and data[end : end + 1] == b"\r"
                if gff3 and lines == 0 and versioned is None:
                    if line is HEADER:
                        raise ValueError(
                            "FHGFF3 header lines must follow ##gff-version 3 on line 1"
                        )
                    first_line.extend(piece)
                    text = bytes(first_line).rstrip(b"\r\n")
                    version_prefix = b"##gff-version"
                    looks_version = text.lstrip(b" \t").startswith(version_prefix)
                    if not (looks_version or version_prefix.startswith(text)):
                        # Plain GFF3 without an FHGFF3 header stays readable for
                        # strip and directive scanning; a later #~ line is rejected.
                        versioned = False
                    elif complete or final or held_cr:
                        if not is_gff3_version_line(text):
                            raise ValueError(
                                "GFF3 line 1 must be '##gff-version 3' with an "
                                "optional .x.y version (FAIR-bioHeaders-"
                                "Specification docs/FHGFF3.md G1)"
                            )
                        versioned = True
                    if len(first_line) > MAX_HEADER_BYTES:
                        raise ValueError(
                            "GFF3 line 1 is too long to be a ##gff-version line"
                        )
                if line is _MAYBE_BLANK and piece.strip():
                    in_header = False  # A GFA record line.
                    break
                if line is HEADER:
                    header_size += len(piece)
                    if header_size > MAX_HEADER_BYTES:
                        raise ValueError(
                            "FHR header lines exceed the "
                            f"{MAX_HEADER_BYTES // 2**20} MiB size limit"
                        )
                    parts.append(piece)
                elif piece:
                    yield DATA, piece
                position = end
                if not complete:
                    break
                lines += 1
                if line is HEADER:
                    header_count += 1
                    if header_count > MAX_HEADER_LINES:
                        raise ValueError(
                            f"FHR header lines exceed the {MAX_HEADER_LINES} line limit"
                        )
                    yield HEADER, b"".join(parts)
                    parts = []
                line = None
            if in_header:
                pending = data[position:]
                if final and line is HEADER:
                    yield HEADER, b"".join(parts)
                continue
            yield END, b""
            chunk = data[position:]
            pending = b""
        elif final:
            break
        if not chunk:
            continue
        # After the header block, a line starts after each \n or \r.
        late = [
            match - len(tail) + 1
            for match in (
                (tail + chunk[: len(prefix)]).find(b"\n" + prefix),
                (tail + chunk[: len(prefix)]).find(b"\r" + prefix),
            )
            if 0 <= match < len(tail)
        ]
        if prefix[-1:] in chunk:  # A fast check that is usually false.
            late += [
                match + 1
                for match in (chunk.find(b"\n" + prefix), chunk.find(b"\r" + prefix))
                if match >= 0
            ]
        if late:
            start = min(late)
            if start > 0:
                lines += _count_lines(chunk[:start], after_cr)
            raise ValueError(f"FHR header line after sequence data at line {lines + 1}")
        lines += _count_lines(chunk, after_cr)
        after_cr = chunk.endswith(b"\r")
        tail = (tail + chunk[-len(prefix) :])[-len(prefix) :]
        yield DATA, chunk


def _count_lines(data, after_cr):
    """Count line terminators, given whether the previous byte was \\r."""
    count = data.count(b"\n")
    if b"\r" in data:
        count += data.count(b"\r") - data.count(b"\r\n")
    if after_cr and data.startswith(b"\n"):
        count -= 1  # The second byte of a \r\n split between chunks.
    return count


def header_lines(lines, prefix):
    """Return the FHR lines of the leading header block, rejecting any later ones.

    The block ends at the first record: a FASTA ``>`` line, or a nonblank GFA line
    that is not a ``#`` comment. Ordinary comments and blank lines may be mixed in.
    """
    return [part for kind, part in sequence_parts(lines, prefix) if kind is HEADER]


def header_text(line, prefix):
    """Return the YAML text of one FHR header line given as bytes."""
    text = line[len(prefix) :].rstrip(b"\r\n").decode("utf-8")
    if any(char in text for char in YAML_ONLY_LINE_BREAKS):
        raise ValueError("FHR header lines must not contain U+0085, U+2028, or U+2029")
    return text


# YAML 1.2 core-schema types of plain scalars (FORMAT.md R12); anything else is a
# string. YAML 1.1 types come from PyYAML's resolver, plus y/n as booleans.
_YAML12_TYPES = [
    ("tag:yaml.org,2002:null", re.compile(r"~|null|Null|NULL|")),
    ("tag:yaml.org,2002:bool", re.compile(r"true|True|TRUE|false|False|FALSE")),
    ("tag:yaml.org,2002:int", re.compile(r"[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+")),
    (
        "tag:yaml.org,2002:float",
        re.compile(
            r"[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
            r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)"
        ),
    ),
]
_YAML11 = yaml.resolver.Resolver()
_STR_TAG = "tag:yaml.org,2002:str"


def _yaml12_tag(value):
    for tag, pattern in _YAML12_TYPES:
        if pattern.fullmatch(value):
            return tag
    return _STR_TAG


def _yaml11_tag(value):
    if value in {"y", "Y", "n", "N"}:
        return "tag:yaml.org,2002:bool"
    tag = _YAML11.resolve(yaml.ScalarNode, value, (True, False))
    # Dates and times stay strings, as written (R12).
    return _STR_TAG if tag == "tag:yaml.org,2002:timestamp" else tag


def portable_plain_tag(value):
    """The tag of a plain scalar, or ``None`` if YAML 1.1 and 1.2 disagree (R12)."""
    tag = _yaml12_tag(value)
    if tag != _yaml11_tag(value):
        return None
    if tag == "tag:yaml.org,2002:int":
        digits = value.lstrip("+-")
        if len(digits) > 1 and digits[0] == "0" and digits[1] not in "xX":
            return None  # YAML 1.1 reads a leading zero as octal.
    return tag


class _Loader(yaml.SafeLoader):
    """Load JSON-compatible YAML without aliases, merge keys, or duplicate keys.

    Plain scalars get YAML 1.2 core-schema types and must read the same under
    YAML 1.1; explicit tags are rejected (FORMAT.md R12).
    """

    def compose_node(self, parent, index):
        self._nodes = getattr(self, "_nodes", 0) + 1
        if self._nodes > MAX_YAML_NODES:
            raise yaml.composer.ComposerError(
                None, None, f"FHR metadata exceeds {MAX_YAML_NODES} YAML nodes", None
            )
        depth = getattr(self, "_depth", 0)
        if depth >= MAX_YAML_DEPTH:
            raise yaml.composer.ComposerError(
                None, None, "metadata is nested too deeply", None
            )
        self._depth = depth + 1
        try:
            return self._compose_checked(parent, index)
        finally:
            self._depth = depth

    def _compose_checked(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise yaml.composer.ComposerError(
                None,
                None,
                "YAML anchors and aliases are not allowed in FHR metadata",
                event.start_mark,
            )
        if getattr(event, "tag", None) is not None:
            raise yaml.composer.ComposerError(
                None,
                None,
                f"YAML tags such as {event.tag} are not allowed in FHR metadata",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def resolve(self, kind, value, implicit):
        if kind is yaml.ScalarNode and implicit[0] and value != "<<":
            tag = portable_plain_tag(value)
            if tag is None:
                raise yaml.composer.ComposerError(
                    None,
                    None,
                    f"the plain YAML value {value!r} is read differently by YAML 1.1 "
                    "and YAML 1.2 readers; quote it",
                    None,
                )
            return tag
        return super().resolve(kind, value, implicit)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise yaml.constructor.ConstructorError(
                        None,
                        None,
                        "YAML merge keys are not allowed in FHR metadata",
                        key_node.start_mark,
                    )
                key = self.construct_object(key_node, deep=True)
                if not isinstance(key, Hashable):
                    continue  # SafeConstructor reports unhashable keys.
                if key in keys:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key {key!r}",
                        key_node.start_mark,
                    )
                keys.add(key)
        return super().construct_mapping(node, deep=deep)


def load_yaml(text):
    try:
        return yaml.load(text, Loader=_Loader)
    except RecursionError:
        raise ValueError("metadata is nested too deeply") from None


class _Dumper(yaml.SafeDumper):
    """Escape characters that YAML, but not FASTA/GFA, reads as line breaks.

    Strings that YAML 1.1 or YAML 1.2 would read as another type are quoted
    (FORMAT.md R12).
    """

    def resolve(self, kind, value, implicit):
        tag = super().resolve(kind, value, implicit)
        if kind is yaml.ScalarNode and implicit[0] and tag == _STR_TAG:
            plain = portable_plain_tag(value)
            if plain != _STR_TAG:
                return plain or "tag:yaml.org,2002:int"  # Any tag but str: quote it.
        return tag

    def represent_str(self, data):
        if any(char in data for char in YAML_ONLY_LINE_BREAKS):
            return self.represent_scalar("tag:yaml.org,2002:str", data, style='"')
        return super().represent_str(data)


_Dumper.add_representer(str, _Dumper.represent_str)


class _FastaDumper(_Dumper):
    """Also double-quote strings with a FASTA record marker (FORMAT.md R11)."""

    def represent_str(self, data):
        if any(char in data for char in RECORD_MARKERS):
            return self.represent_scalar("tag:yaml.org,2002:str", data, style='"')
        return super().represent_str(data)


_FastaDumper.add_representer(str, _FastaDumper.represent_str)


def record_marker_warnings(lines, prefix):
    """Warnings for FASTA FHR header lines (bytes) holding a raw ``>`` or ``@``."""
    warnings = []
    for number, line in enumerate(lines, 1):
        found = [
            char for char in RECORD_MARKERS if char.encode() in line[len(prefix) :]
        ]
        if found:
            raw = " and ".join(f"'{char}'" for char in found)
            escaped = " and ".join(RECORD_MARKERS[char] for char in found)
            warnings.append(
                f"FHR header line {number} contains a raw {raw}: kseq-based FASTA "
                f"readers start a record there; write {escaped} in a double-quoted "
                "value instead (FAIR-bioHeaders-Specification docs/FORMAT.md R11)"
            )
    return warnings


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Metadata object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _nonfinite_paths(value, path=""):
    """Yield the dotted path of each NaN or infinity in ``value``."""
    if isinstance(value, float) and not math.isfinite(value):
        yield path
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _nonfinite_paths(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _nonfinite_paths(item, f"{path}[{index}]")


class NonFiniteValueError(ValueError):
    """A metadata value is NaN or an infinity (FAIR-bioHeaders-Specification R13)."""


def check_finite(metadata):
    """Reject NaN and infinities (FAIR-bioHeaders-Specification FORMAT.md R13).

    Schema ``minimum`` and ``maximum`` do not catch them, and JSON serialisation
    would otherwise report a generic out-of-range error. ``metadata`` may be a
    mapping or an :class:`fhr` instance.
    """
    data = metadata.__dict__ if isinstance(metadata, fhr) else metadata
    kind = header_type(data) if isinstance(data, dict) else "FHR"
    for path in _nonfinite_paths(data):
        raise NonFiniteValueError(
            f"{kind}: {path} is not a finite number (FORMAT.md R13)"
        )


def _has_value(value):
    """Whether a required value is present and non-empty."""
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def _resolve_schema(schema, root):
    """Resolve local ``$ref`` values in ``schema`` against ``root``."""
    seen = set()
    while isinstance(schema, dict) and "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/") or reference in seen:
            break
        seen.add(reference)
        target = root
        for part in reference[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        schema = target
    return schema


def _schema_kind(schema):
    """A rough JSON Schema type for choosing branches, or ``None``."""
    kind = schema.get("type")
    if isinstance(kind, str):
        return kind
    if "properties" in schema or "required" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return None


def _value_kind(value):
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return None


def _required_value_messages(value, schema, path, root, messages):
    """Collect empty required values, following the schema's nested requirements."""
    schema = _resolve_schema(schema, root)
    if not isinstance(schema, dict):
        return
    kind = _schema_kind(schema)
    value_kind = _value_kind(value)
    if isinstance(value, dict):
        if kind not in (None, "object"):
            return
        for key in schema.get("required", ()):
            if key not in value:
                continue  # A missing required value is a schema error, not a warning.
            item_path = f"{path}.{key}" if path else key
            if not _has_value(value[key]):
                messages.append(f"required value {item_path} is empty")
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, item in value.items():
                if key in properties:
                    _required_value_messages(
                        item,
                        properties[key],
                        f"{path}.{key}" if path else key,
                        root,
                        messages,
                    )
    elif isinstance(value, list):
        if kind not in (None, "array"):
            return
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _required_value_messages(
                    item, items, f"{path}[{index}]", root, messages
                )
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if not isinstance(branches, list):
            continue
        for branch in branches:
            branch = _resolve_schema(branch, root)
            if not isinstance(branch, dict):
                continue
            nested = any(
                name in branch
                for name in ("properties", "items", "allOf", "anyOf", "oneOf")
            )
            branch_kind = _schema_kind(branch)
            if nested and (branch_kind is None or branch_kind == value_kind):
                _required_value_messages(value, branch, path, root, messages)


def _author_fields(schema):
    """Required author-array fields (``metadataAuthor``, ``assemblyAuthor``)."""
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return ()
    return tuple(
        field for field in ("metadataAuthor", "assemblyAuthor") if field in properties
    )


def required_value_warnings(metadata):
    """Warnings for required values that are empty (schema-valid, not conforming).

    The bundled schema says which values are required: this walks its ``required``
    arrays (including nested objects and list items) and adds the author-name and
    taxon rules the schemas cannot express. Messages omit the header-type prefix;
    the CLI prints ``TYPE: warning: <message>``.
    """
    data = metadata.__dict__ if isinstance(metadata, fhr) else metadata
    if not isinstance(data, dict):
        return []
    schema = schema_for(data)
    messages = []
    _required_value_messages(data, schema, "", schema, messages)
    for field in _author_fields(schema):
        authors = data.get(field)
        if not isinstance(authors, list):
            continue
        for index, author in enumerate(authors):
            if isinstance(author, dict) and not _has_value(author.get("name")):
                messages.append(f"required value {field}[{index}].name is empty")
    taxon = data.get("taxon")
    if isinstance(taxon, dict) and taxon:
        if not _has_value(taxon.get("name")) and not _has_value(taxon.get("uri")):
            messages.append("required value taxon has neither name nor uri")
    # A schema may reach the same value by more than one path (anyOf/allOf).
    return list(dict.fromkeys(messages))


_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
# Elements that stop the HTML search for an element to close implicitly.
_HTML_SCOPE = {
    "applet",
    "button",
    "caption",
    "html",
    "marquee",
    "object",
    "table",
    "td",
    "template",
    "th",
}
_CLOSES_P = {
    "address",
    "article",
    "aside",
    "blockquote",
    "center",
    "dd",
    "details",
    "dialog",
    "dir",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hgroup",
    "hr",
    "li",
    "listing",
    "main",
    "menu",
    "nav",
    "ol",
    "p",
    "pre",
    "search",
    "section",
    "summary",
    "table",
    "ul",
    "xmp",
}
_TABLE_SECTIONS = {"tbody", "tfoot", "thead"}
# Start tag -> (open elements it implicitly closes, elements bounding the search).
_IMPLIED_END_TAGS = {
    "li": ({"li"}, {"ol", "ul"}),
    "dd": ({"dd", "dt"}, {"dl"}),
    "dt": ({"dd", "dt"}, {"dl"}),
    "option": ({"option"}, {"datalist", "optgroup", "select"}),
    "optgroup": ({"optgroup", "option"}, {"datalist", "select"}),
    "tr": ({"td", "th", "tr"}, _TABLE_SECTIONS),
    "td": ({"td", "th"}, {"tr"}),
    "th": ({"td", "th"}, {"tr"}),
    **{tag: (_TABLE_SECTIONS | {"td", "th", "tr"}, set()) for tag in _TABLE_SECTIONS},
}
_MICRODATA_ATTRIBUTES = {
    "meta": "content",
    "audio": "src",
    "embed": "src",
    "iframe": "src",
    "img": "src",
    "source": "src",
    "track": "src",
    "video": "src",
    "a": "href",
    "area": "href",
    "link": "href",
    "object": "data",
    "data": "value",
    "meter": "value",
    "time": "datetime",
}
_JSON_TYPES = {
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float))
    and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


def _tokens(value):
    """Split an HTML attribute on ASCII whitespace."""
    return re.findall(r"[^\t\n\f\r ]+", value or "")


def _attributes(pairs):
    """Keep the first of duplicate attributes, as HTML parsers do."""
    result = {}
    for name, value in pairs:
        result.setdefault(name, value)
    return result


class _MetadataHTML(HTMLParser):
    """Parse the FHR item scope, using explicit JSON types for lossless values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        # Every open element; only "active" ones are inside the FHR item scope.
        self.stack = []
        self.result = None

    def handle_starttag(self, tag, attrs):
        self._imply_end_tags(tag)
        attrs = _attributes(attrs)
        if tag in _VOID_ELEMENTS:
            self._leaf(tag, attrs)
            return
        root = "itemscope" in attrs and not ITEM_TYPES.isdisjoint(
            _tokens(attrs.get("itemtype"))
        )
        active = bool(self.stack) and self.stack[-1]["active"]
        if root and (self.result is not None or active):
            raise ValueError("Multiple FHR item scopes found")
        self.stack.append(
            {
                "tag": tag,
                "attrs": attrs,
                "active": root or active,
                "text": [],
                "values": {},
            }
        )

    def handle_startendtag(self, tag, attrs):
        self._imply_end_tags(tag)
        self._leaf(tag, _attributes(attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                self._close(index)
                return

    def handle_data(self, text):
        if self.stack and self.stack[-1]["active"]:
            self.stack[-1]["text"].append(text)

    def _imply_end_tags(self, tag):
        rules = []
        if tag in _IMPLIED_END_TAGS:
            rules.append(_IMPLIED_END_TAGS[tag])
        if tag in _CLOSES_P:
            rules.append(({"p"}, set()))
        for closes, bounds in rules:
            for index in range(len(self.stack) - 1, -1, -1):
                name = self.stack[index]["tag"]
                if name in closes:
                    self._close(index)
                    break
                if name in bounds or name in _HTML_SCOPE:
                    break

    def _close(self, index):
        while len(self.stack) > index:
            self._finish(self.stack.pop())

    def _leaf(self, tag, attrs):
        if self.stack and self.stack[-1]["active"]:
            value = attrs.get(_MICRODATA_ATTRIBUTES.get(tag, ""))
            for name in _tokens(attrs.get("itemprop")):
                self._attach(self.stack[-1], name, value or "")

    @staticmethod
    def _attach(node, key, value):
        node["values"].setdefault(key, []).append(value)

    @staticmethod
    def _object(values):
        return {
            key: items[0] if len(items) == 1 else items for key, items in values.items()
        }

    def _finish(self, node):
        if not node["active"]:
            return
        tag, attrs = node["tag"], node["attrs"]
        kind = attrs.get("data-fhr-type")
        text = attrs.get(_MICRODATA_ATTRIBUTES.get(tag, ""))
        if text is None:
            text = "".join(node["text"])
        if kind != "string":
            text = text.strip()
        if kind == "array":
            value = node["values"].get("item", [])
        elif kind == "object" or "itemscope" in attrs or node["values"]:
            value = self._object(node["values"])
        elif kind in _JSON_TYPES:
            value = json.loads(text)
            if not _JSON_TYPES[kind](value):
                raise ValueError(f"Microdata value {text!r} is not a JSON {kind}")
        else:
            value = text
        parent = self.stack[-1] if self.stack and self.stack[-1]["active"] else None
        if parent is None:
            self.result = value
        elif _tokens(attrs.get("itemprop")):
            for name in _tokens(attrs.get("itemprop")):
                self._attach(parent, name, value)
        elif "itemscope" not in attrs:
            parent["text"].extend(node["text"])
            for key, items in node["values"].items():
                parent["values"].setdefault(key, []).extend(items)

    def close(self):
        super().close()
        if any(node["active"] for node in self.stack):
            raise ValueError("No complete FHR microdata item scope found")


def _html_value(key, value):
    prop = escape(key, quote=True)
    if isinstance(value, dict):
        content = "".join(_html_value(k, v) for k, v in value.items())
        return (
            f'<span itemprop="{prop}" itemscope data-fhr-type="object">{content}</span>'
        )
    if isinstance(value, list):
        content = "".join(_html_value("item", v) for v in value)
        return f'<span itemprop="{prop}" data-fhr-type="array">{content}</span>'
    kind = "string"
    if value is None:
        kind = "null"
    elif isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    elif isinstance(value, float):
        kind = "number"
    content = value if isinstance(value, str) else json.dumps(value)
    return f'<span itemprop="{prop}" data-fhr-type="{kind}">{escape(content)}</span>'


class fhr:
    """A metadata mapping. Optional fields are absent until explicitly supplied."""

    def __init__(self, **metadata):
        self.__dict__.update(deepcopy(metadata))

    def _input(self, data):
        if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
            raise ValueError("FHR metadata must be an object with string keys")
        normalized = _json_value(data)
        check_finite(normalized)
        json.dumps(normalized, allow_nan=False)
        self.__dict__.clear()
        self.__dict__.update(deepcopy(normalized))

    def input_yaml(self, stream):
        self._input(load_yaml(_text(stream)))

    def output_yaml(self):
        return yaml.dump(
            self.__dict__, Dumper=_Dumper, sort_keys=False, allow_unicode=True
        )

    def input_json(self, stream):
        self._input(json.loads(_text(stream), object_pairs_hook=_unique_object))

    def output_json(self):
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2) + "\n"

    def input_jsonld(self, stream, ignore_unknown_terms=False, warn=None):
        """Read FHR JSON-LD (FAIR-bioHeaders-Specification docs/JSONLD.md).

        Canonical documents (rule J1) need only the standard library; other forms
        (rules J3 to J5) need the ``jsonld`` extra. ``ignore_unknown_terms``
        reports terms without an FHR field through ``warn`` instead of failing.
        """
        from . import jsonld

        document = json.loads(_text(stream), object_pairs_hook=_unique_object)
        self._input(
            jsonld.from_jsonld(
                document, ignore_unknown_terms=ignore_unknown_terms, warn=warn
            )
        )

    def output_jsonld(self, export=None, profile="canonical"):
        """Write JSON-LD: the metadata with an embedded context and typed nodes.

        ``export`` is an optional export context with ``id``, ``url`` and
        ``keywords`` (see ``bioheaders.jsonld.to_jsonld``). ``profile="export"``
        writes the one-way schema.org export instead
        (``bioheaders.jsonld.to_export``), which cannot be read back.
        """
        from . import jsonld

        if profile == "export":
            return jsonld.export_text(self.__dict__, export=export)
        if profile != "canonical":
            raise ValueError(f"Unknown JSON-LD profile: {profile}")
        document = jsonld.to_jsonld(self.__dict__, export=export)
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    def _input_header(self, stream, prefix, gff3=False):
        # Match checksum line handling: split bytes, decode only header lines.
        marker = prefix.encode("ascii")
        self._input_header_lines(
            [
                line
                for kind, line in sequence_parts(read_chunks(stream), marker, gff3)
                if kind is HEADER
            ],
            marker,
        )

    def _input_header_lines(self, lines, prefix):
        """Load metadata from FHR header lines given as bytes with ``prefix``."""
        if not lines:
            raise ValueError(f"No {prefix.decode('ascii')} FHR metadata header found")
        self._input(load_yaml("\n".join(header_text(line, prefix) for line in lines)))

    def _output_header(self, prefix, text=None):
        lines = (self.output_yaml() if text is None else text).split("\n")
        if lines[-1] == "":
            lines.pop()
        return "".join(prefix + line + "\n" for line in lines)

    def input_fasta(self, stream):
        self._input_header(stream, ";~")

    def output_fasta(self):
        # R11: every '>' or '@' is inside a double-quoted scalar here (strings that
        # contain one are double-quoted, and no other YAML token holds one), so
        # writing the YAML escape instead keeps the metadata unchanged.
        text = yaml.dump(
            self.__dict__, Dumper=_FastaDumper, sort_keys=False, allow_unicode=True
        )
        for char, escaped in RECORD_MARKERS.items():
            text = text.replace(char, escaped)
        return self._output_header(";~", text)

    def input_gfa(self, stream):
        self._input_header(stream, "#~")

    def output_gfa(self):
        return self._output_header("#~")

    def input_gff3(self, stream):
        self._input_header(stream, "#~", gff3=True)

    def output_gff3(self):
        return self._output_header("#~")

    def input_microdata(self, stream):
        parser = _MetadataHTML()
        parser.feed(_text(stream))
        parser.close()
        if parser.result is None:
            raise ValueError("No complete FHR microdata item scope found")
        data = parser.result
        # Standard microdata scalar values are strings; restore schema-defined types.
        for key, definition in SCHEMA["properties"].items():
            if key not in data:
                continue
            if definition.get("type") == "array" and not isinstance(data[key], list):
                data[key] = [data[key]]
            if definition.get("type") in {"number", "integer"} and isinstance(
                data[key], str
            ):
                data[key] = json.loads(data[key])
        if isinstance(data.get("assemblySoftware"), dict):
            data["assemblySoftware"] = [data["assemblySoftware"]]
        if isinstance(data.get("assemblySoftware"), list):
            for software in data["assemblySoftware"]:
                if isinstance(software, dict) and isinstance(
                    software.get("commandLineOption"), str
                ):
                    software["commandLineOption"] = [software["commandLineOption"]]
        if isinstance(data.get("vitalStats"), dict):
            for key, value in data["vitalStats"].items():
                kind = (
                    SCHEMA["properties"]["vitalStats"]["properties"]
                    .get(key, {})
                    .get("type")
                )
                if kind in {"number", "integer"} and isinstance(value, str):
                    data["vitalStats"][key] = json.loads(value)
        self._input(data)

    def output_microdata(self):
        content = "".join(
            _html_value(key, value) for key, value in self.__dict__.items()
        )
        return f'<div itemscope itemtype="{ITEM_TYPE}">{content}</div>\n'

    def header_type(self):
        """``"FHGFF3"``, ``"FHP"`` or ``"FHR"``, from the ``schema`` value."""
        return header_type(self.__dict__)

    def fhr_validate(self):
        """Validate against the bundled schema of the record's header type."""
        check_finite(self.__dict__)
        json.dumps(self.__dict__, allow_nan=False)
        Draft202012Validator(
            schema_for(self.__dict__), format_checker=FormatChecker()
        ).validate(self.__dict__)


GENOME_LINK_MISSING = (
    "no genome link: give a derivedFrom item with headerType FHR and relationship "
    "annotates, or a genomeReference with accession and seqcol_id "
    "(FAIR-bioHeaders-Specification docs/FHGFF3.md G2)"
)


def validation_message(error):
    """A readable message for a schema ValidationError.

    The FHGFF3 genome-link rule (FAIR-bioHeaders-Specification spec 007 D-03) is written with
    anyOf, not and if/then, whose default messages repeat the whole record.
    """
    rule = json.dumps(error.validator_value, sort_keys=True)
    path = list(error.absolute_path)
    if error.validator == "anyOf" and "genomeReference" in rule:
        return GENOME_LINK_MISSING
    if error.validator == "not" and "Annotates" in rule:
        return "more than one derivedFrom item has the relationship annotates"
    if (
        error.validator == "const"
        and path[:1] == ["derivedFrom"]
        and path[-1:] == ["headerType"]
        and error.validator_value == "FHR"
    ):
        return (
            "a derivedFrom item that annotates must name an FHR genome (headerType FHR)"
        )
    return error.message


# Native GFF3 directives compared with an FHGFF3 header (FAIR-bioHeaders-Specification
# docs/FHGFF3.md, "Native directives"; spec 007 research D-07).
GFF3_DIRECTIVES = (
    b"##species",
    b"##genome-build",
    b"#!genome-build-accession",
    b"#!genome-build",
)
_TAXON_ID = re.compile(r"(?:taxonomy:|[?&]id=|/)(\d+)/?$")
_ACCESSION_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9_]*:(?=\S)")


def gff3_directive(line):
    """Return ``(name, value)`` for a compared native directive line, else None."""
    text = line.rstrip(b"\r\n")
    for name in GFF3_DIRECTIVES:
        if text.startswith(name) and (
            len(text) == len(name) or text[len(name)] in b" \t"
        ):
            value = text[len(name) :].strip().decode("utf-8", "replace")
            return name.decode("ascii"), value
    return None


def _taxon_id(value):
    match = _TAXON_ID.search(value.strip()) if isinstance(value, str) else None
    return match.group(1) if match else None


def cross_check(metadata, directives):
    """Warnings where an FHGFF3 header and native directives disagree.

    ``directives`` maps a directive name (``##species``, ``##genome-build``,
    ``#!genome-build``, ``#!genome-build-accession``) to its first value in the
    leading block. Values missing on either side are not compared; nothing is
    rewritten and a disagreement never makes the file invalid.
    """
    warnings = []
    taxon = metadata.get("taxon")
    species = directives.get("##species")
    if isinstance(taxon, dict) and species is not None:
        header_id, native_id = _taxon_id(taxon.get("uri")), _taxon_id(species)
        if header_id is None or native_id is None:
            warnings.append(
                f"taxon not compared with ##species {species} "
                "(no NCBI Taxonomy ID found in one of them)"
            )
        elif header_id != native_id:
            warnings.append(
                f"taxon {taxon.get('uri')} (taxonomy ID {header_id}) differs from "
                f"##species {species} (taxonomy ID {native_id})"
            )
    reference = metadata.get("genomeReference")
    reference = reference if isinstance(reference, dict) else {}
    accession = reference.get("accession")
    if accession is None:
        annotates = [
            item
            for item in metadata.get("derivedFrom") or []
            if isinstance(item, dict) and item.get("relationship") == "annotates"
        ]
        # Invalid metadata can hold several; prefer the first with a checksum.
        with_checksum = [item for item in annotates if item.get("checksum") is not None]
        for item in with_checksum or annotates:
            accession_id = item.get("accessionID")
            name = accession_id.get("name") if isinstance(accession_id, dict) else None
            if isinstance(name, str):
                accession = name
                break
    native = directives.get("#!genome-build-accession")
    if accession is not None and native is not None:
        native_accession = _ACCESSION_PREFIX.sub("", native)
        if native_accession != accession:
            warnings.append(
                f"genome accession {accession} differs from "
                f"#!genome-build-accession {native}"
            )
    name = reference.get("assemblyName")
    if name is not None:
        for directive in ("##genome-build", "#!genome-build"):
            value = directives.get(directive)
            if value is None:
                continue
            build = value.split()[-1] if value.split() else ""
            if build != name:
                warnings.append(f"assemblyName {name} differs from {directive} {value}")
    return warnings
