# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Build FHR metadata from typed values and compute ``vitalStats`` from FASTA.

``bioheaders metadata`` (FAIR-bioHeaders-Tools#171, specs/004-bioheaders-metadata).
Nothing here invents a required value: what the schema requires and only the
user can know must be supplied. The record carries no ``checksum``; a checksum
covers file bytes, and ``bioheaders combine`` computes and writes it.

Statistics (plan.md, "Statistics definitions"): every FASTA record with at least
one base is a scaffold; contigs are the maximal runs of non-``N`` bases inside a
scaffold, split at every run of one or more ``N``/``n``; leading and trailing
``N`` runs belong to no contig. The specification defines N50/L50/N90/L90 as
contig statistics and the ``scaffold*`` fields as scaffold statistics, but no
gap rule, so this one is stated here and in the README.
"""

import re
import unicodedata
from array import array
from datetime import date

from . import (
    MAX_HEADER_BYTES,
    MAX_HEADER_LINES,
    SCHEMA,
    fhr,
    link_scheme_warnings,
    selection,
)
from .extensions import is_extension_key

# Header types the command line names. Only FHR is implemented; the others are
# recognized so that adding them later does not change the option.
TYPES = ("fhr", "fhp", "fhgff3")
SUPPORTED_TYPES = ("fhr",)

# A syntactic stand-in used only to validate the record in memory, as combine does
# before it hashes; it is never written.
_STAND_IN_CHECKSUM = "A" * 43 + "="

MASKING = tuple(
    SCHEMA["properties"]["masking"]["pattern"].strip("^$()").split("|")
)  # not-masked, hard-masked, soft-masked, repeat-masked, unknown
VITAL_STATS = SCHEMA["properties"]["vitalStats"]["properties"]

ORCID = re.compile(
    SCHEMA["definitions"]["orcidUri"]["pattern"]
)  # ^https://orcid\.org/0000-0000-0000-000X$
_AUTHOR = re.compile(r"(?P<name>.*?)\s*<(?P<uri>[^<>]*)>\s*")
_TAXON_ID = re.compile(r"[0-9]+")
_INTEGER = re.compile(r"[0-9]+")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# vitalStats fields --stats-from can compute: --stat may not give them with it.
COMPUTED_STATS = (
    "totalBasePairs",
    "numberContigs",
    "numberScaffolds",
    "N50",
    "L50",
    "N90",
    "L90",
    "scaffoldN50",
    "scaffoldL50",
    "scaffoldN90",
    "scaffoldL90",
    "gcContent",
)
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Unicode line breaks that are not category Cc (FORMAT.md R6).
_LINE_BREAKS = "  "


def current_fhr():
    """``(schema URL, schemaVersion)`` of the toolkit's current FHR release.

    The URL is the w3id alias of the bundled current release; the version is the
    highest ``schemaVersion`` that release's schema accepts."""
    url = selection.current_fhr_url()
    if url is None:  # main ahead of every release: nothing citable to write
        raise ValueError("the bundled FHR schema belongs to no release")
    versions = SCHEMA["properties"]["schemaVersion"]["enum"]
    version = max(versions, key=lambda text: tuple(int(p) for p in text.split(".")))
    return url, version


class MetadataError(ValueError):
    """A supplied value that cannot be written; the message names the option."""


def text(value, option):
    """``value`` as metadata text: non-empty, without line breaks or other control
    characters except tab. YAML would escape them, but in a genome name or an
    author they are almost always a pasting mistake, so they are refused."""
    if value is None:
        return None
    if not value.strip():
        raise MetadataError(f"{option}: the value is empty")
    bad = [
        char
        for char in value
        if (unicodedata.category(char) == "Cc" and char != "\t") or char in _LINE_BREAKS
    ]
    if bad:
        raise MetadataError(
            f"{option}: control or line-break character {bad[0]!r} is not allowed"
        )
    return value


def orcid_check_digit(digits):
    """The ISO 7064 11,2 check character of the first 15 ORCID digits."""
    total = 0
    for digit in digits:
        total = (total + int(digit)) * 2
    result = (12 - total % 11) % 11
    return "X" if result == 10 else str(result)


def author(value, option):
    """``Name`` or ``Name <https://orcid.org/XXXX-XXXX-XXXX-XXXX>``."""
    value = text(value, option)
    match = _AUTHOR.fullmatch(value)
    if match is None:
        if "<" in value:
            raise MetadataError(
                f"{option}: {value!r} is neither 'Name' nor "
                "'Name <https://orcid.org/XXXX-XXXX-XXXX-XXXX>'"
            )
        return {"name": value.strip()}
    name, uri = match.group("name").strip(), match.group("uri").strip()
    if not name:
        raise MetadataError(f"{option}: {value!r} has no name before <...>")
    if not ORCID.fullmatch(uri):
        raise MetadataError(
            f"{option}: {uri!r} is not an ORCID URI; write "
            "'Name <https://orcid.org/0000-0000-0000-0000>'"
        )
    digits = uri.rsplit("/", 1)[1].replace("-", "")
    if orcid_check_digit(digits[:15]) != digits[15]:
        raise MetadataError(
            f"{option}: {uri} fails the ORCID check digit; check for a typo"
        )
    return {"name": name, "uri": uri}


def taxon_uri(value):
    value = value.strip()
    if not _TAXON_ID.fullmatch(value):
        raise MetadataError(
            f"--taxon-id: {value!r} is not an NCBI taxonomy id (digits only, "
            "e.g. 9606)"
        )
    return f"https://identifiers.org/taxonomy:{int(value)}"


def iso_date(value):
    if not _ISO_DATE.fullmatch(value):
        raise MetadataError(
            f"--date-created: {value!r} is not an ISO date (YYYY-MM-DD)"
        )
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise MetadataError(f"--date-created: {value!r} is not a date ({error})")
    return value


def software(value):
    """``NAME``, ``NAME=VERSION`` or ``NAME=VERSION=URI`` (``NAME==URI`` without a
    version); the URI may itself hold ``=``. Only the name is required."""
    parts = value.split("=", 2)
    if not parts[0].strip() or (len(parts) == 2 and not parts[1].strip()):
        raise MetadataError(
            f"--assembly-software: {value!r} is not NAME, NAME=VERSION or "
            "NAME=VERSION=URI"
        )
    item = {"name": text(parts[0], "--assembly-software")}
    if len(parts) > 1 and parts[1]:
        item["version"] = text(parts[1], "--assembly-software")
    if len(parts) == 3:
        item["uri"] = text(parts[2], "--assembly-software")
    return item


def extra(value):
    """``x-key=value`` (FORMAT.md R15); the value is a string."""
    key, sep, item = value.partition("=")
    if not sep:
        raise MetadataError(f"--extra: {value!r} is not x-KEY=VALUE")
    if not is_extension_key(key):
        raise MetadataError(
            f"--extra: {key!r} is not an extension key: x- followed by an ASCII "
            "letter or digit, then letters, digits, '_', '.' or '-' "
            "(docs/FORMAT.md R15)"
        )
    return key, text(item, f"--extra {key}")


def stat(value):
    """``KEY=VALUE`` for one ``vitalStats`` field, typed by the schema."""
    key, sep, item = value.partition("=")
    if not sep or key not in VITAL_STATS:
        raise MetadataError(
            f"--stat: {value!r} is not KEY=VALUE with KEY one of "
            f"{', '.join(VITAL_STATS)}"
        )
    kind = VITAL_STATS[key]["type"]
    if kind == "string":
        return key, text(item, f"--stat {key}")
    pattern = _INTEGER if kind == "integer" else _NUMBER
    if not pattern.fullmatch(item):
        raise MetadataError(
            f"--stat {key}: {item!r} is not a non-negative {kind} in decimal digits"
        )
    number = int(item) if kind == "integer" else float(item)
    if number in (float("inf"), float("-inf")):
        raise MetadataError(f"--stat {key}: {item!r} is not a finite number (R13)")
    return key, number


# The options for the values the schema requires and only the user can know, with
# their argparse attribute names (schema, schemaVersion: the command; checksum:
# combine).
REQUIRED = (
    ("--genome", "genome"),
    ("--taxon-name", "taxon_name"),
    ("--taxon-id", "taxon_id"),
    ("--version", "assembly_version"),
    ("--metadata-author", "metadata_author"),
    ("--assembly-author", "assembly_author"),
    ("--date-created", "date_created"),
    ("--masking", "masking"),
)


def missing_required(args):
    return [option for option, name in REQUIRED if not getattr(args, name)]


def require(args):
    """Raise ``MetadataError`` listing every missing required option."""
    missing = missing_required(args)
    if missing:
        raise MetadataError(
            f"missing required value{'s' if len(missing) > 1 else ''}: "
            f"{', '.join(missing)} (FHR metadata never invents them)"
        )


def build_record(args, vital_stats=None):
    """The FHR record for parsed ``args`` (an ``argparse.Namespace``).

    ``vital_stats`` holds statistics computed from a FASTA. Raises
    ``MetadataError`` for a missing or malformed value."""
    require(args)
    url, version = current_fhr()
    record = {"schema": url, "schemaVersion": version}
    record["genome"] = text(args.genome, "--genome")
    if args.genome_synonym:
        record["genomeSynonym"] = [
            text(item, "--genome-synonym") for item in args.genome_synonym
        ]
    record["taxon"] = {
        "name": text(args.taxon_name, "--taxon-name"),
        "uri": taxon_uri(args.taxon_id),
    }
    record["version"] = text(args.assembly_version, "--version")
    record["metadataAuthor"] = [
        author(item, "--metadata-author") for item in args.metadata_author
    ]
    record["assemblyAuthor"] = [
        author(item, "--assembly-author") for item in args.assembly_author
    ]
    record["dateCreated"] = iso_date(args.date_created)
    if args.voucher_specimen is not None:
        record["voucherSpecimen"] = text(args.voucher_specimen, "--voucher-specimen")
    if args.accession is not None:
        record["accessionID"] = {"name": text(args.accession, "--accession")}
        if args.accession_url is not None:
            record["accessionID"]["url"] = text(args.accession_url, "--accession-url")
    elif args.accession_url is not None:
        raise MetadataError("--accession-url needs --accession")
    if args.instrument:
        record["instrument"] = [text(item, "--instrument") for item in args.instrument]
    if args.scholarly_article is not None:
        record["scholarlyArticle"] = text(args.scholarly_article, "--scholarly-article")
    if args.documentation is not None:
        record["documentation"] = text(args.documentation, "--documentation")
    if args.identifier:
        record["identifier"] = [text(item, "--identifier") for item in args.identifier]
    if args.related_link:
        record["relatedLink"] = [
            text(item, "--related-link") for item in args.related_link
        ]
    if args.funding is not None:
        record["funding"] = text(args.funding, "--funding")
    if args.reuse_conditions is not None:
        record["reuseConditions"] = text(args.reuse_conditions, "--reuse-conditions")
    if args.masking not in MASKING:
        raise MetadataError(
            f"--masking: {args.masking!r} is not one of {', '.join(MASKING)}"
        )
    record["masking"] = args.masking
    stats = dict(vital_stats or {})
    for key, value in (stat(item) for item in args.stat or ()):
        if getattr(args, "stats_from", None) is not None and key in COMPUTED_STATS:
            raise MetadataError(
                f"--stat {key}: --stats-from computes this value; give one or the "
                "other"
            )
        if key in stats:
            raise MetadataError(f"--stat {key}: given more than once")
        stats[key] = value
    if stats:
        record["vitalStats"] = {key: stats[key] for key in VITAL_STATS if key in stats}
    if args.assembly_software:
        record["assemblySoftware"] = [software(item) for item in args.assembly_software]
    if args.assembly_protocol is not None:
        record["assemblyProtocol"] = text(args.assembly_protocol, "--assembly-protocol")
    if args.seqcol_id is not None:
        record["seqcol_id"] = text(args.seqcol_id, "--seqcol-id")
    for key, value in (extra(item) for item in args.extra or ()):
        if key in record:
            raise MetadataError(f"--extra: {key} given more than once")
        record[key] = value
    return record


def check_record(record):
    """Validate ``record`` (no checksum) against its bundled schema.

    The checksum requirement is set aside by validating a copy with a stand-in
    value; R14 link schemes, which the schema only warns about, are refused, and
    the FASTA header rendering must stay within the reader limits."""
    if "checksum" in record:
        raise ValueError("metadata written by this command carries no checksum")
    data = fhr(**record, checksum=_STAND_IN_CHECKSUM)
    data.fhr_validate()
    problems = link_scheme_warnings(data.__dict__)
    if problems:
        raise MetadataError("; ".join(problems))
    # Measured with the checksum line combine adds, so combine cannot fail later.
    header = data.output_fasta().encode("utf-8")
    if len(header) > MAX_HEADER_BYTES or header.count(b"\n") > MAX_HEADER_LINES:
        raise MetadataError(
            "the metadata exceeds the header limits readers may enforce (1 MiB, "
            "10,000 lines; docs/FORMAT.md)"
        )


def render(record, format_name):
    """YAML (R11, R12, R13: safe to embed as header lines) or JSON text."""
    data = fhr(**record)
    if format_name == "json":
        return data.output_json()
    # The FASTA rendering is R12 YAML with R11 escapes; drop its ";~" prefix.
    return "".join(line[2:] + "\n" for line in data.output_fasta().splitlines() if line)


# ---------------------------------------------------------------------------
# Statistics

_WHITESPACE = b" \t\r\n\x0b\x0c"
_NUCLEOTIDES = b"ACGTUNRYSWKMBDHVacgtunryswkmbdhv"
_GAP = re.compile(rb"[Nn]+")
# A line that starts a record or a comment (one search: two finds that each scan
# to the end of the chunk would make many short records quadratic).
_LINE_MARK = re.compile(rb"\n[>;]")


class FastaStats:
    """Streaming assembly statistics over FASTA bytes without the FHR header.

    Feed the bytes in chunks of any size, then call ``result()``. Memory grows
    with the number of contigs and scaffolds only."""

    def __init__(self):
        self.contigs = array("Q")
        self.scaffolds = array("Q")
        self.gc = 0
        self.acgt = 0
        self.records = 0
        self.empty_records = 0
        self.empty_names = []
        self.line_start = True
        self.in_line = None  # None, "name" or "comment": skipping to a line end
        self.in_record = False
        self.name = bytearray()
        self.length = 0  # bases in the current record
        self.contig = 0  # length of the open contig

    def _close_contig(self):
        if self.contig:
            self.contigs.append(self.contig)
            self.contig = 0

    def _close_record(self):
        if not self.in_record:
            return
        self._close_contig()
        if self.length:
            self.scaffolds.append(self.length)
        else:
            self.empty_records += 1
            if len(self.empty_names) < 5:
                self.empty_names.append(self._label())
        self.in_record = False

    def _sequence(self, data):
        data = data.translate(None, _WHITESPACE)
        if not data:
            return
        if not self.in_record:
            raise ValueError("--stats-from: sequence data before the first '>' record")
        stray = data.translate(None, _NUCLEOTIDES)
        if stray:
            raise ValueError(
                f"--stats-from: record {self._label()} holds {chr(stray[0])!r}, "
                "which is not an IUPAC nucleotide code; vitalStats are computed "
                "for nucleotide FASTA only"
            )
        self.length += len(data)
        upper = data.upper()
        gc = upper.count(b"G") + upper.count(b"C")
        self.gc += gc
        self.acgt += gc + upper.count(b"A") + upper.count(b"T") + upper.count(b"U")
        position = 0
        for gap in _GAP.finditer(data):
            self.contig += gap.start() - position
            self._close_contig()
            position = gap.end()
        self.contig += len(data) - position

    def _label(self):
        name = bytes(self.name[:80]).split(maxsplit=1)
        return repr(name[0].decode("utf-8", "replace")) if name else "(unnamed)"

    def feed(self, chunk):
        chunk = chunk.replace(b"\r", b"\n")
        position, size = 0, len(chunk)
        while position < size:
            if self.in_line is not None:
                end = chunk.find(b"\n", position)
                stop = size if end < 0 else end
                if self.in_line == "name" and len(self.name) < 256:
                    self.name += chunk[position : min(stop, position + 256)]
                if end < 0:
                    return
                self.in_line, self.line_start = None, True
                position = end + 1
                continue
            if self.line_start and chunk[position] in b">;":
                if chunk[position] == ord(">"):
                    self._close_record()
                    self.records += 1
                    self.in_record, self.length = True, 0
                    self.name = bytearray()
                    self.in_line = "name"
                else:
                    self.in_line = "comment"
                position += 1
                continue
            # Sequence up to the next line that starts a record or a comment.
            found = _LINE_MARK.search(chunk, position)
            end = -1 if found is None else found.start()
            if end < 0:
                self._sequence(chunk[position:])
                self.line_start = chunk.endswith(b"\n")
                return
            self._sequence(chunk[position : end + 1])
            self.line_start = True
            position = end + 1

    def result(self):
        """The ``vitalStats`` object; raises ``ValueError`` without sequence."""
        self._close_record()
        if not self.records:
            raise ValueError("--stats-from: the FASTA holds no '>' records")
        if not self.scaffolds:
            raise ValueError("--stats-from: the FASTA records hold no bases")
        total = sum(self.scaffolds)
        stats = {"totalBasePairs": total}
        stats["numberContigs"] = len(self.contigs)
        stats["numberScaffolds"] = len(self.scaffolds)
        if self.contigs:
            n50, l50, n90, l90 = nx_lx(self.contigs)
            stats.update(N50=n50, L50=l50, N90=n90, L90=l90)
        n50, l50, n90, l90 = nx_lx(self.scaffolds)
        stats.update(scaffoldN50=n50, scaffoldL50=l50, scaffoldN90=n90, scaffoldL90=l90)
        if self.acgt:
            stats["gcContent"] = round(100 * self.gc / self.acgt, 2)
        return stats

    def warnings(self):
        if not self.empty_records:
            return []
        more = self.empty_records - len(self.empty_names)
        names = ", ".join(self.empty_names) + (f" and {more} more" if more else "")
        return [
            f"--stats-from: {self.empty_records} record(s) without bases are not "
            f"counted as scaffolds: {names}"
        ]


def nx_lx(lengths):
    """``(N50, L50, N90, L90)`` of ``lengths`` (exact integer thresholds)."""
    ordered = sorted(lengths, reverse=True)
    total = sum(ordered)
    result = {}
    cumulative = 0
    wanted = [50, 90]
    for count, length in enumerate(ordered, 1):
        cumulative += length
        while wanted and cumulative * 100 >= wanted[0] * total:
            result[wanted.pop(0)] = (length, count)
        if not wanted:
            break
    return result[50][0], result[50][1], result[90][0], result[90][1]


def fasta_stats(chunks):
    """``(vitalStats, warnings)`` for FASTA chunks without the FHR header."""
    stats = FastaStats()
    for chunk in chunks:
        stats.feed(chunk)
    return stats.result(), stats.warnings()
