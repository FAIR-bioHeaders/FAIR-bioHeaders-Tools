# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHGFF3 HTML microdata reader and writer.

Implements the reviewed binding in FHGFF3 ``docs/FHGFF3-MICRODATA.md`` (rules
H1 to H8, named as the canonical FHGFF3 binding by the shared
``docs/MICRODATA.md`` "Type-specific bindings" section, published through
FAIR-bioHeaders-Specification#216/#217) on top of the shared rules M1 to M5
and R9. Where the type-specific and shared rules could be read differently,
the shared rules win; the itemtype (H1 replaces M1) and the schema selection
and validation (H2 replaces the ``fhr.json`` half of M4) are FHGFF3's own. An
FHR-itemtype document is never an FHGFF3 record and this module never emits
the FHR or FHP identity. Like the FHP module it is standard-library only
(``html.parser``) apart from the JSON Schema validation of extracted records.
The writer emits a standalone document with the typed metadata block and the
readable annotation table of H8, built from the same record; text and
attributes are escaped and the document contains no script, handler or other
executable content. Script and template subtrees are inert (H6, with M2's
HTML parsing): a reader never takes metadata from them.

The reader accepts the typed serialization and the untyped fallback: without
``data-fhr-type`` it converts values using the selected FHGFF3 JSON Schema's
types, as rule M3 requires. The record's ``schema`` property selects the
contract before any conversion or validation (H2). Nothing is fetched. The
genome link alternatives (a complete ``genomeReference`` or an ``annotates``
``derivedFrom`` parent, H4) and the feature-count and completeness assertions
(H5) are the selected FHGFF3 schema's own rules; reading validates structure
and schema only, never a checksum or a parent file. That is what
``bioheaders verify`` and ``bioheaders verify-links`` do, separately.
"""

import re
import warnings

from jsonschema import Draft202012Validator, FormatChecker

from . import extensions, selection
from ._microdata import MicrodataError as MicrodataError
from ._microdata import _Node as _Node
from ._microdata import _nodes as _nodes
from ._microdata import _parse_typed as _parse_typed
from ._microdata import _property_elements as _property_elements
from ._microdata import _read_scope as _read_scope
from ._microdata import _resolve as _resolve
from ._microdata import _text as _text
from ._microdata import _TreeBuilder as _TreeBuilder
from ._microdata import _value_of as _value_of
from ._microdata import _write_property as _write_property
from ._microdata import escape as escape
from ._microdata import family_scopes as family_scopes

# The binding remains draft pending FHGFF3#16. Runtime support is experimental,
# not a claim that the binding or toolkit implementation has been released.
EXPERIMENTAL = True


class ExperimentalMicrodataWarning(UserWarning):
    """FHGFF3 microdata follows a draft binding and may change before release."""


def _warn_experimental():
    warnings.warn(
        "FHGFF3 HTML microdata is experimental pending release of its binding "
        "(FHGFF3#16); the draft serialization may change",
        ExperimentalMicrodataWarning,
        stacklevel=3,
    )


# The raw-main FHGFF3 schema URL is the record's itemtype identity
# (docs/SCHEMA-VERSIONS.md; FHGFF3 docs/FHGFF3-MICRODATA.md H1). The pre-rename
# repository name is the same file and the same item type.
FHGFF3_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhgff3.json"
)
FHGFF3_ITEMTYPE_OLD_NAME = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHR-Specification/main/fhgff3.json"
)
FHGFF3_ITEMTYPES = {FHGFF3_ITEMTYPE, FHGFF3_ITEMTYPE_OLD_NAME}

# The `schema` itemprop selects the contract version. It is an FHGFF3 schema
# URL: a raw GitHub URL naming `main` or a release tag, or a w3id release URL
# (H2, docs/SCHEMA-VERSIONS.md V1 to V4). Any other value, including an FHR or
# FHP schema URL, is unsupported-version and is rejected, never read against
# another schema (H1/H2; FHGFF3.md G3).
FHGFF3_SCHEMA_URL = re.compile(
    r"^https://raw\.githubusercontent\.com/FAIR-bioHeaders/"
    r"(FHR|FAIR-bioHeaders)-Specification/(main|v[0-9]+\.[0-9]+\.[0-9]+)/fhgff3\.json$"
)
FHGFF3_W3ID_URL = re.compile(
    r"^https://w3id\.org/fair-bioheaders/fhgff3/v[0-9]+\.[0-9]+\.[0-9]+/?$"
)

# Fixed releases this reader carries. They are copies of released schemas, not
# fetched at run time (docs/SCHEMA-VERSIONS.md V2 to V4). v0.4.1 and v0.4.2
# carry the same FHGFF3 schema contract as v0.4.0 (FHGFF3 1.0); v0.5.0 carries
# FHGFF3 1.1 (extension fields, which microdata itself never carries, M5).
# `selection` maps them to the bundled copies; a release not listed here is
# rejected instead of falling back to the local copy (H2).
SUPPORTED_RELEASES = ("v0.4.0", "v0.4.1", "v0.4.2", "v0.5.0")


def _release_schema(release):
    if release not in SUPPORTED_RELEASES:
        supported = ", ".join(SUPPORTED_RELEASES)
        raise MicrodataError(
            f"unsupported FHGFF3 schema version: {release} "
            f"(this reader has FHGFF3 releases {supported})"
        )
    return selection.select(f"https://w3id.org/fair-bioheaders/fhgff3/{release}")[2]


def resolve_schema(selection_value, schema):
    """Resolve the FHGFF3 contract a record's ``schema`` value selects (H2).

    ``schema`` is the reader's current (``main``) schema. A released URL
    selects a fixed supported release; an unknown release, a raw URL with any
    other ref, or any value that is not an FHGFF3 schema URL — an FHR or FHP
    URL included — is unsupported-version and is rejected before extraction or
    validation. The record is never silently treated as FHR (H1/H2, G3).
    """
    if not isinstance(selection_value, str):
        raise MicrodataError(
            f"unsupported FHGFF3 schema selection: {selection_value!r}"
        )
    raw = FHGFF3_SCHEMA_URL.fullmatch(selection_value)
    if raw:
        release = raw.group(2)
        return schema if release == "main" else _release_schema(release)
    w3id = FHGFF3_W3ID_URL.fullmatch(selection_value)
    if w3id:
        return _release_schema(w3id.group(0).rstrip("/").rsplit("/", 1)[-1])
    raise MicrodataError(f"unsupported FHGFF3 schema selection: {selection_value!r}")


def _selected_schema(scope, schema):
    for element, name in _property_elements(scope):
        if name == "schema":
            return resolve_schema(_value_of(element), schema)
    raise MicrodataError("FHGFF3 item scope has no schema property")


def _tree(text, check=False):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    if check and builder.unclosed_scopes():
        raise MicrodataError(
            "FHGFF3 item scope is not closed before the end of the document"
        )
    family_scopes(builder.root)
    return builder.root


def has_fhgff3_scope(text):
    """Whether an HTML document contains an FHGFF3 item scope (used for dispatch)."""
    return any(
        FHGFF3_ITEMTYPES & set(node.itemtype)
        for node in _nodes(_tree(text))
        if node.itemscope
    )


def read_page(text, schema):
    """Extract one FHGFF3 record from an HTML document.

    ``schema`` is the parsed current FHGFF3 JSON Schema, used for the untyped
    fallback (M3). The record's ``schema`` value selects the contract first
    (H2). Raises :class:`MicrodataError` for a document that is not a single,
    structurally valid FHGFF3 item scope. The asserted ``genomeReference`` and
    a checksum-linked parent stay separate properties (H4); nothing here
    computes or verifies either.
    """
    _warn_experimental()
    scopes = [node for node in _nodes(_tree(text, check=True)) if node.itemscope]
    fhgff3_scopes = [node for node in scopes if FHGFF3_ITEMTYPES & set(node.itemtype)]
    if len(fhgff3_scopes) != 1:
        raise MicrodataError(
            f"expected exactly one FHGFF3 item scope, found {len(fhgff3_scopes)}"
        )
    selected = _selected_schema(fhgff3_scopes[0], schema)
    record = _read_scope(fhgff3_scopes[0], selected, selected)
    # Microdata carries no extension fields (docs/MICRODATA.md M5).
    try:
        extensions.reject(record, "microdata", "docs/MICRODATA.md M5")
    except ValueError as error:
        raise MicrodataError(str(error)) from None
    return record


def validate_record(record, schema):
    """Validate an extracted record against the schema its ``schema`` selects.

    FHGFF3 requiredness is the FHGFF3 contract: ``annotation``, the genome
    link (H4) and the shared core fields, never FHR's genome fields; a
    ``schemaVersion`` the selected schema does not accept (H2) and a repeated
    single-valued property (H7) fail here with readable messages.
    """
    selected = resolve_schema(record.get("schema"), schema)
    errors = list(
        Draft202012Validator(selected, format_checker=FormatChecker()).iter_errors(
            record
        )
    )
    if errors:
        from . import validation_message

        raise MicrodataError(f"{errors[0].json_path}: {validation_message(errors[0])}")
    return record


def extract(text, schema):
    """Read a document and reject it unless it matches its selected FHGFF3 schema."""
    return validate_record(read_page(text, schema), schema)


def table_rows(record):
    """The readable-table rows for a record, as (label, value) strings (H8).

    The table is a presentation aid: it repeats values that are also in the
    embedded microdata so the two can be compared, adds no metadata and is
    never read back as metadata. The wording names the ``genomeReference`` and
    the feature counts as producer assertions, never as verified results.
    """
    rows = [
        ("Annotation", str(record["annotation"])),
        ("Version", str(record["version"])),
    ]
    taxon = record.get("taxon")
    if taxon:
        rows.append(("Taxon", f'{taxon.get("name", "")} ({taxon.get("uri", "")})'))
    reference = record.get("genomeReference")
    if reference:
        parts = [str(reference.get("accession", ""))]
        if "seqcol_id" in reference:
            parts.append("seqcol=" + str(reference["seqcol_id"]))
        if "assemblyName" in reference:
            parts.append("assembly=" + str(reference["assemblyName"]))
        rows.append(("Genome reference (asserted)", " ".join(p for p in parts if p)))
    parents = record.get("derivedFrom", [])
    annotates = [p for p in parents if p.get("relationship") == "annotates"]
    if annotates:
        parent = annotates[0]
        rows.append(
            (
                "Annotated genome parent (FHR checksum)",
                f'{parent.get("headerType", "")} {parent.get("checksum", "")}'.strip(),
            )
        )
    others = [p for p in parents if p.get("relationship") != "annotates"]
    if others:
        rows.append(
            (
                "Other parents",
                "; ".join(
                    f'{p.get("headerType", "")}:{p.get("relationship", "")}'
                    for p in others
                ),
            )
        )
    authors = record.get("metadataAuthor", [])
    if authors:
        rows.append(("Metadata authors", "; ".join(a.get("name", "") for a in authors)))
    software = record.get("annotationSoftware", [])
    if software:
        rows.append(
            (
                "Annotation software",
                "; ".join(
                    f'{s.get("name", "")} {s.get("version", "")}'.strip()
                    for s in software
                ),
            )
        )
    counts = record.get("featureCounts", [])
    if counts:
        rows.append(
            (
                "Feature counts (producer assertion)",
                "; ".join(f'{c["featureType"]}={c["count"]}' for c in counts),
            )
        )
    completeness = record.get("completeness")
    if completeness:
        rows.append(
            (
                "Completeness (BUSCO counts)",
                "S:{completeSingle} D:{completeDuplicated} F:{fragmented} "
                "M:{missing} n:{total}".format(**completeness),
            )
        )
    if "documentation" in record:
        rows.append(("Documentation", str(record["documentation"])))
    rows.append(
        ("Checksum (ordinary value; not verified here)", str(record["checksum"]))
    )
    return rows


def _readable_table(record):
    """The H8 readable table, built from the same record as the metadata block."""
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in table_rows(record)
    )
    return (
        "<table><caption>FHGFF3 metadata (human summary)</caption>"
        "<tr><th>Property</th><th>Value</th></tr>" + rows + "</table>"
    )


def write_page(record, itemtype=FHGFF3_ITEMTYPE, title="FHGFF3 microdata example"):
    """Write one record as a standalone HTML document (typed serialization).

    The metadata block is the lossless typed form. The readable table below it
    presents the same values (H8); both are escaped, and neither contains
    script or event-handler content. The itemtype is the FHGFF3 identity (H1):
    callers pass no other itemtype in supported paths, and the reader rejects
    the FHR and FHP itemtypes for FHGFF3 records.
    """
    _warn_experimental()
    record = extensions.without_extensions(record)  # Rule M5.
    content = "".join(_write_property(name, value) for name, value in record.items())
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title></head><body>\n"
        f'<div itemscope itemtype="{escape(itemtype, quote=True)}">{content}</div>\n'
        f"{_readable_table(record)}\n"
        "</body></html>\n"
    )


def read_table(text):
    """Extract the readable table's (label, value) rows from a document.

    Only the first table's two-cell data rows are returned; the header row and
    any caption are ignored. This is a consumer and test helper for the H8
    consistency check, never a metadata reader: the table adds no metadata.
    """
    for node in _nodes(_tree(text)):
        if node.tag != "table":
            continue
        rows = []
        for row in _nodes(node):
            if row.tag != "tr":
                continue
            cells = [
                child
                for child in row.children
                if isinstance(child, _Node) and child.tag in ("td", "th")
            ]
            if len(cells) == 2 and cells[0].tag == "td" and cells[1].tag == "td":
                rows.append((_text(cells[0]), _text(cells[1])))
        return rows
    return []
