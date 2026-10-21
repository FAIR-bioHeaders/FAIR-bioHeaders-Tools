# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Read the header region of a file and turn each line into evidence (R-02, R-15).

The header region is, per format:

- GFF3: lines before the first feature line, ending at ``##FASTA``;
- VCF: lines up to and including ``#CHROM``;
- GAF: leading ``!`` lines;
- FASTA: lines before the first ``>``, plus the first defline;
- GFA: leading ``#`` lines; unknown text: leading ``#``, ``!``, ``;``, ``%``
  or ``//`` lines.

At most ``MAX_HEADER_BYTES`` of header and ``MAX_LINE_BYTES`` per line are kept
(findings ``header-truncated`` and ``line-too-long``). After the header, up to
``record_limit`` records (and ``MAX_SAMPLE_BYTES``) are sampled for sequence
names and a parse check. FAIR-bioHeaders lines are found with
``bioheaders.header_lines``, the function that ``validate`` and ``verify`` use.
"""

import hashlib
import re
import shlex
from datetime import date, datetime

from .. import header_lines, header_text
from . import conformance as conformance_module
from .model import Finding, HeaderEvidence
from .synonyms import load as load_synonyms

MAX_LINE_BYTES = 2**20
# Header bytes kept for the assessment (all header lines, not only FHR lines).
MAX_HEADER_BYTES = 16 * 2**20
MAX_SAMPLE_BYTES = 16 * 2**20
CHUNK = 2**16
UNKNOWN_MARKERS = (b"#", b"!", b";", b"%", b"//")
GAF_SEPARATOR = re.compile(r"^\s*(=+\s*$|Header (from|copied from)\b)")
GFF3_STRANDS = {"+", "-", ".", "?"}
DATE_FORMATS = ("%a %b %d %H:%M:%S %Y", "%m/%d/%Y", "%Y%m%d", "%d/%m/%Y")
ENSEMBL_COORD = re.compile(
    r"(?:^|\s)(?:chromosome|scaffold|contig|supercontig|primary_assembly|plasmid)"
    r":([^:\s]+):"
)


class Line:
    __slots__ = ("number", "data", "terminator", "truncated")

    def __init__(self, number, data, terminator, truncated):
        self.number = number
        self.data = data
        self.terminator = terminator
        self.truncated = truncated

    @property
    def size(self):
        return len(self.data) + len(self.terminator)


TERMINATOR = re.compile(b"\r\n|\r|\n")


def iter_lines(stream):
    """Yield ``Line`` objects; lines end at LF, CRLF or CR (as bytes.splitlines).

    A line longer than ``MAX_LINE_BYTES`` keeps only its first part and is
    marked truncated; the rest is read and discarded.
    """
    buffer = b""
    number = 0
    eof = False
    kept = None  # First part of an over-long line being discarded.
    while True:
        match = TERMINATOR.search(buffer)
        if match and not (
            match.group() == b"\r" and match.end() == len(buffer) and not eof
        ):
            data, terminator = buffer[: match.start()], match.group()
            buffer = buffer[match.end() :]
            number += 1
            if kept is not None:
                yield Line(number, kept, terminator, True)
                kept = None
            else:
                yield Line(
                    number,
                    data[:MAX_LINE_BYTES],
                    terminator,
                    len(data) > MAX_LINE_BYTES,
                )
            continue
        if eof:
            if buffer or kept is not None:
                number += 1
                if kept is not None:
                    yield Line(number, kept, b"", True)
                else:
                    yield Line(
                        number,
                        buffer[:MAX_LINE_BYTES],
                        b"",
                        len(buffer) > MAX_LINE_BYTES,
                    )
            return
        if len(buffer) > MAX_LINE_BYTES + 1:
            if kept is None:
                kept = buffer[:MAX_LINE_BYTES]
            buffer = buffer[-1:]
        chunk = stream.read(CHUNK)
        if chunk:
            buffer += chunk
        else:
            eof = True


# Header region -------------------------------------------------------------


def _in_header(format_name, data, seen_defline):
    """Return (is header line, header ends after it)."""
    if format_name == "fasta":
        return True, data.startswith(b">")
    if not data.strip():
        return True, False
    if format_name == "gff3":
        return data.startswith(b"#"), data.startswith(b"##FASTA")
    if format_name == "vcf":
        return data.startswith(b"#"), data.startswith(b"#CHROM")
    if format_name == "gaf":
        return data.startswith(b"!"), False
    if format_name == "gfa":
        return data.startswith(b"#"), False
    return data.startswith(UNKNOWN_MARKERS), False


class Reading:
    """The header lines and record sample of one input."""

    def __init__(self):
        self.lines = []
        self.lines_read = 0
        self.truncated = False
        self.digest = hashlib.sha256()
        self.records = 0
        self.records_ok = True
        self.seqids = []
        self.fasta_body = False

    @property
    def header_sha256(self):
        return self.digest.hexdigest()


def read(stream, format_name, record_limit):
    """Read the header region and a record sample from a decompressed stream."""
    reading = Reading()
    total = 0
    pending = None  # The first line after the header.
    lines = iter_lines(stream)
    for line in lines:
        is_header, ends = _in_header(format_name, line.data, False)
        if not is_header:
            pending = line
            break
        total += line.size
        if total > MAX_HEADER_BYTES:
            reading.truncated = True
            break
        reading.lines.append(line)
        reading.lines_read += 1
        reading.digest.update(line.data + line.terminator)
        if ends:
            if line.data.startswith(b"##FASTA"):
                return reading
            break
    if reading.truncated or record_limit <= 0:
        return reading
    _sample(reading, format_name, pending, lines, record_limit)
    return reading


def _sample(reading, format_name, pending, lines, record_limit):
    seen = set()
    size = 0
    if format_name == "fasta":
        if reading.lines and reading.lines[-1].data.startswith(b">"):
            reading.records = 1
            residues = 0
            for line in _chain(pending, lines):
                size += line.size
                if line.data.startswith(b">"):
                    if residues == 0:
                        reading.records_ok = False
                    if reading.records >= record_limit or size > MAX_SAMPLE_BYTES:
                        return
                    reading.records += 1
                    residues = 0
                elif line.data.strip():
                    if not re.fullmatch(rb"[A-Za-z*.\-]+", line.data.strip()):
                        reading.records_ok = False
                    residues += 1
                if size > MAX_SAMPLE_BYTES:
                    return
            if residues == 0:
                reading.records_ok = False
        return
    if format_name not in ("gff3", "vcf", "gaf", "gfa"):
        return
    comment = b"!" if format_name == "gaf" else b"#"
    for line in _chain(pending, lines):
        size += line.size
        if size > MAX_SAMPLE_BYTES or reading.records >= record_limit:
            return
        data = line.data
        if format_name == "gff3" and data.startswith(b"##FASTA"):
            return
        if not data.strip() or data.startswith(comment):
            continue
        reading.records += 1
        try:
            fields = data.decode("utf-8").split("\t")
        except UnicodeDecodeError:
            reading.records_ok = False
            continue
        if not _record_parses(format_name, fields):
            reading.records_ok = False
        elif format_name in ("gff3", "vcf") and fields[0] not in seen:
            seen.add(fields[0])
            reading.seqids.append(fields[0])


def _chain(first, rest):
    if first is not None:
        yield first
    yield from rest


def _record_parses(format_name, fields):
    if format_name == "gff3":
        return (
            len(fields) == 9
            and fields[3].isdigit()
            and fields[4].isdigit()
            and int(fields[3]) <= int(fields[4])
            and fields[6] in GFF3_STRANDS
        )
    if format_name == "vcf":
        return len(fields) >= 8 and fields[1].isdigit()
    if format_name == "gaf":
        return len(fields) in (15, 16, 17)
    return len(fields[0]) == 1 and fields[0].isalpha() and len(fields) >= 2


# Evidence -----------------------------------------------------------------------


def _jsonable(value):
    """JSON form of a YAML value, without floats (reports carry none)."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _flatten(path, value, group=None):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(f"{path}.{key}", item, group)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _flatten(path, item, group if group else (path, index))
    elif value is not None:
        text = value if isinstance(value, str) else str(_jsonable(value))
        yield path, text, group


def _subfields(text):
    """Parse ``k=v,k="v, w"`` of a VCF ``##KEY=<...>`` line into a dict."""
    result = {}
    position = 0
    pattern = re.compile(r'\s*([^=,]+)=("(?:[^"\\]|\\.)*"|[^,]*)\s*(?:,|$)')
    while position < len(text):
        match = pattern.match(text, position)
        if not match:
            break
        value = match.group(2)
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1].replace('\\"', '"')
        result[match.group(1).strip()] = value
        position = match.end()
    return result


def _defline(text):
    """Parse the first FASTA defline into an id and key/value pairs."""
    body = text[1:]
    parts = body.split(None, 1)
    value = {"id": parts[0] if parts else ""}
    rest = parts[1] if len(parts) > 1 else ""
    ensembl = ENSEMBL_COORD.search(" " + rest)
    if ensembl:
        value["ensembl-coord-assembly"] = ensembl.group(1)
        return value
    if "=" in rest:
        if ";" in rest:
            tokens = [token.strip() for token in rest.split(";")]
        else:
            try:
                tokens = shlex.split(rest)
            except ValueError:
                tokens = rest.split()
        for token in tokens:
            if "=" in token:
                key, item = token.split("=", 1)
                if key.strip() and key.strip() not in value:
                    value[key.strip()] = item.strip().strip('"')
    else:
        organism = re.search(r"\[([^\[\]]+)\]\s*$", rest)
        if organism:
            value["organism"] = organism.group(1)
    return value


def _iso_hint(value):
    for pattern in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value.strip(), pattern)
        except ValueError:
            continue
        if parsed.hour or parsed.minute or parsed.second:
            return parsed.isoformat()
        return parsed.date().isoformat()
    return None


class Builder:
    """Turn header lines into HeaderEvidence and findings."""

    def __init__(self, format_name):
        self.format = format_name
        self.synonyms = load_synonyms()
        self.evidence = []
        self.findings = []  # (kind, [line numbers], message)
        self.gaf_upstream = False

    def add(self, line, raw, convention, key=None, value=None, items=(), scope=None):
        if scope is None:
            scope = "file"
            if convention == "fasta-defline":
                scope = "first-record"
            elif self.gaf_upstream:
                scope = "upstream-provenance"
        items = list(items)
        concepts = []
        forms = []
        for item in items:
            if item.concept not in concepts:
                concepts.append(item.concept)
            forms += [form for form in item.forms if form not in forms]
        evidence = HeaderEvidence(
            id=f"e{len(self.evidence) + 1}",
            line=line,
            convention=convention,
            raw=raw,
            key=key,
            normalised_key=self.synonyms_normalise(key),
            value=value,
            concepts=concepts,
            scope=scope,
            value_forms=forms,
            items=items,
        )
        self.evidence.append(evidence)
        for item in items:
            if item.status == "malformed":
                self.finding(
                    "malformed",
                    [line],
                    f"line {line}: the value {item.value!r} of {key or item.key} is not "
                    f"a well-formed {', '.join(self.synonyms.concepts[item.concept].get('forms', []))}",
                )
            elif item.status == "irregular":
                hint = _iso_hint(item.value)
                self.finding(
                    "format-irregularity",
                    [line],
                    f"line {line}: the date {item.value!r} is not in ISO 8601 form"
                    + (f" (as ISO 8601: {hint})" if hint else ""),
                )
        return evidence

    @staticmethod
    def synonyms_normalise(key):
        from .synonyms import normalise

        return normalise(key) if key is not None else None

    def finding(self, kind, lines, message):
        self.findings.append((kind, list(lines), message))

    def resolve(self, convention, key, value, extra=None):
        return self.synonyms.resolve(convention, key, value, extra)

    def free_text(self, line, text, credited=()):
        found = [
            (form, value)
            for form, value in self.synonyms.identifiers_in(text)
            if value not in credited
        ]
        if found:
            listed = ", ".join(value for _, value in found)
            self.finding(
                "identifier-in-free-text",
                [line],
                f"line {line}: {listed} looks like an identifier but is not under a key "
                "that says what it identifies; it is not credited",
            )

    def unrecognised(self, line, raw):
        self.add(line, raw, "unrecognised")
        self.finding(
            "unrecognised-comment",
            [line],
            f"line {line}: a comment line in no recognised header convention",
        )
        self.free_text(line, raw)

    # Conventions ------------------------------------------------------------

    def gff3(self, line, text):
        if text.startswith("##"):
            rest = text[2:]
            parts = rest.split(None, 1)
            key = parts[0] if parts else ""
            value = parts[1].strip() if len(parts) > 1 else ""
            items = self.resolve("gff3-directive", key, value)
            shown = value
            if key == "sequence-region":
                fields = value.split()
                if len(fields) == 3 and fields[1].isdigit() and fields[2].isdigit():
                    shown = {
                        "seqid": fields[0],
                        "start": int(fields[1]),
                        "end": int(fields[2]),
                    }
            evidence = self.add(line, text, "gff3-directive", key, shown, items)
            self._keyed_free_text(evidence, value)
        elif text.startswith("#!"):
            rest = text[2:].strip()
            parts = rest.split(None, 1)
            key = parts[0] if parts else ""
            value = parts[1].strip() if len(parts) > 1 else ""
            if not value and ":" in key[:-1]:
                key, value = key.split(":", 1)
                key += ":"
            items = self.resolve("gff3-pragma", key, value)
            evidence = self.add(line, text, "gff3-pragma", key, value, items)
            self._keyed_free_text(evidence, value)
        else:
            self.unrecognised(line, text)

    def _keyed_free_text(self, evidence, value):
        if not isinstance(value, str) or not value:
            return
        structural = {"field-definition", "structural"}
        if structural & set(evidence.concepts):
            return
        credited = {item.value for item in evidence.items}
        self.free_text(evidence.line, value, credited)

    def vcf(self, line, text):
        if text.startswith("#CHROM"):
            self.add(line, text, "vcf-meta")
            return
        match = re.match(r"^##([^=]+)=(.*)$", text)
        if not match:
            self.unrecognised(line, text)
            return
        key, value = match.group(1), match.group(2)
        if value.startswith("<") and value.endswith(">"):
            fields = _subfields(value[1:-1])
            items = self.resolve("vcf-meta", key, value)
            if key == "contig":
                name = fields.get("ID")
                for sub in ("assembly", "md5", "species", "URL"):
                    if sub in fields:
                        items += self.resolve(
                            "vcf-contig", sub, fields[sub], {"name": name}
                        )
            self.add(line, text, "vcf-meta", key, fields, items)
            return
        if key == "source" and ";" in value:
            parts = value.split(";")
            fields = {"source": parts[0]}
            for part in parts[1:]:
                if "=" in part:
                    sub, item = part.split("=", 1)
                    fields[sub.strip()] = item.strip()
            items = []
            for sub, item in fields.items():
                items += self.resolve("vcf-meta", sub, item)
            self.add(line, text, "vcf-meta", key, fields, items)
            return
        items = self.resolve("vcf-meta", key, value)
        evidence = self.add(line, text, "vcf-meta", key, value, items)
        self._keyed_free_text(evidence, value)
        if key == "fileDate" and not re.fullmatch(r"\d{8}", value.strip()):
            self.finding(
                "format-irregularity",
                [line],
                f"line {line}: VCF fileDate {value!r} is not in the YYYYMMDD form the "
                "VCF specification uses",
            )

    def gaf(self, line, text):
        content = text[1:]
        if GAF_SEPARATOR.match(content):
            self.gaf_upstream = True
            self.add(line, text, "gaf")
            return
        match = re.match(
            r"^\s*([A-Za-z][A-Za-z0-9 _.\-]*?)\s*:(?:\s+(.*)|\s*)$", content
        )
        if match:
            key, value = match.group(1), (match.group(2) or "").strip()
        elif content.startswith("Created on "):
            key, value = "Created on", content[len("Created on ") :].strip()
        else:
            self.unrecognised(line, text)
            return
        evidence = self.add(
            line, text, "gaf", key, value, self.resolve("gaf", key, value)
        )
        self._keyed_free_text(evidence, value)

    def defline(self, line, text):
        value = _defline(text)
        items = []
        for key, item in value.items():
            if key != "id":
                items += self.resolve("fasta-defline", key, item)
        self.add(line, text, "fasta-defline", None, value, items)


def build_evidence(reading, format_name):
    """Return (evidence, findings, conformance, credited FHR) for a reading."""
    builder = Builder(format_name)
    prefix = {"fasta": b";~", "gff3": b"#~", "gfa": b"#~", "unknown-text": b"#~"}.get(
        format_name
    )
    region = [line.data + line.terminator for line in reading.lines]
    fhr_lines = []
    if prefix:
        try:
            fhr_lines = header_lines([b"".join(region)], prefix)
        except ValueError:
            fhr_lines = [
                line.data for line in reading.lines if line.data.startswith(prefix)
            ]
    result, metadata = None, None
    if fhr_lines:
        result, metadata = conformance_module.check(fhr_lines, prefix)
    first = True
    for line in reading.lines:
        data = line.data
        if first and data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        if not data.strip():
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raw = data.decode("utf-8", errors="replace")
            builder.add(line.number, raw, "unrecognised")
            builder.finding(
                "undecodable-line",
                [line.number],
                f"line {line.number}: not valid UTF-8; the line is not interpreted",
            )
            continue
        if line.truncated:
            builder.finding(
                "line-too-long",
                [line.number],
                f"line {line.number}: longer than {MAX_LINE_BYTES} bytes; only the "
                "first part is kept",
            )
        if prefix and data.startswith(prefix):
            _fhr_line(builder, line.number, text, prefix, metadata)
        elif format_name == "gff3":
            builder.gff3(line.number, text)
        elif format_name == "vcf":
            builder.vcf(line.number, text)
        elif format_name == "gaf":
            if text.strip() == "!":
                continue
            builder.gaf(line.number, text)
        elif format_name == "fasta" and text.startswith(">"):
            builder.defline(line.number, text)
        else:
            builder.unrecognised(line.number, text)
        first = False
    _declaration_order(builder, format_name)
    if reading.truncated:
        builder.finding(
            "header-truncated",
            [],
            f"the header is longer than {MAX_HEADER_BYTES // 2**20} MiB; later header "
            "lines were not read, so indicators that are not evidenced may be "
            "evidenced further on",
        )
    findings = _findings(builder)
    return builder.evidence, findings, result, metadata


def _fhr_line(builder, number, text, prefix, metadata):
    body = header_text(text.encode("utf-8"), prefix)
    root = re.match(r"^([^\s#\-][^:]*?)\s*:(\s|$)", body)
    if metadata is None:
        evidence = builder.add(number, text, "fair-bioheaders")
        evidence.concepts = ["fair-bioheaders-invalid"]
        if root:
            evidence.key = root.group(1)
            evidence.normalised_key = builder.synonyms_normalise(evidence.key)
        return
    key = root.group(1).strip("'\"") if root else None
    if key not in metadata:
        builder.add(number, text, "fair-bioheaders")
        return
    value = _jsonable(metadata[key])
    if value is not None and not isinstance(value, (str, dict, list)):
        value = str(value).lower() if isinstance(value, bool) else str(value)
    items = []
    groups = {}
    flat = list(_flatten(key, metadata[key]))
    for path, item, group in flat:
        if path == "derivedFrom.relationship":
            groups[group] = item
    for path, item, group in flat:
        extra = {"group": group, "relationship": groups.get(group)} if group else {}
        items += builder.resolve("fair-bioheaders", path, item, extra)
    builder.add(number, text, "fair-bioheaders", key, value, items)


def _declaration_order(builder, format_name):
    """A format declaration that is not the first header line is irregular."""
    keys = {"gff3": "gff-version", "vcf": "fileformat", "gaf": "gaf-version"}
    key = keys.get(format_name)
    if not key or not builder.evidence:
        return
    declared = [e for e in builder.evidence if e.key == key]
    if declared and builder.evidence[0] is not declared[0]:
        before = [e.line for e in builder.evidence if e.line < declared[0].line]
        builder.finding(
            "format-irregularity",
            before,
            f"line {before[0]} comes before the format declaration on line "
            f"{declared[0].line}, which the format specification requires first",
        )


def _findings(builder):
    by_line = {}
    for evidence in builder.evidence:
        by_line.setdefault(evidence.line, evidence.id)
    return [
        Finding(kind, message, [by_line[n] for n in lines if n in by_line])
        for kind, lines, message in builder.findings
    ]
