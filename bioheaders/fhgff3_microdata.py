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

import json
import re
from html import escape
from html.parser import HTMLParser

from jsonschema import Draft202012Validator, FormatChecker

from . import extensions, selection

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

# Elements whose end tag HTML implies (docs/MICRODATA.md M2). The values are
# the ancestors a start tag closes, and the scope its search must not cross.
_VOID = {
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
_BASE_SCOPE = {
    "applet",
    "caption",
    "html",
    "marquee",
    "object",
    "table",
    "td",
    "th",
    "template",
}
_BUTTON_SCOPE = _BASE_SCOPE | {"button"}
_LIST_SCOPE = _BASE_SCOPE | {"ol", "ul"}
_TABLE_SCOPE = {"html", "table", "template"}

# Start tags that close an open p in button scope.
_P_CLOSERS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "details",
    "dialog",
    "div",
    "dl",
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
    "main",
    "menu",
    "nav",
    "ol",
    "p",
    "pre",
    "search",
    "section",
    "table",
    "ul",
    "li",
    "dt",
    "dd",
    "tr",
    "td",
    "th",
    "tbody",
    "thead",
    "tfoot",
}
IMPLIED_BY_START = {
    "li": ({"li"}, _LIST_SCOPE),
    "dt": ({"dt", "dd"}, _BASE_SCOPE),
    "dd": ({"dt", "dd"}, _BASE_SCOPE),
    "option": ({"option"}, _BASE_SCOPE | {"select", "datalist"}),
    "optgroup": ({"option", "optgroup"}, _BASE_SCOPE | {"select"}),
    "tr": ({"tr"}, _TABLE_SCOPE),
    "td": ({"td", "th"}, _TABLE_SCOPE),
    "th": ({"td", "th"}, _TABLE_SCOPE),
    "tbody": ({"tbody", "thead", "tfoot"}, _TABLE_SCOPE),
    "thead": ({"tbody", "thead", "tfoot"}, _TABLE_SCOPE),
    "tfoot": ({"tbody", "thead", "tfoot"}, _TABLE_SCOPE),
    "colgroup": ({"colgroup"}, _TABLE_SCOPE),
}
# Elements whose defining attribute is the property value (docs/MICRODATA.md M2).
_VALUE_ATTRIBUTE = {
    "meta": "content",
    "a": "href",
    "area": "href",
    "link": "href",
    "audio": "src",
    "embed": "src",
    "iframe": "src",
    "img": "src",
    "source": "src",
    "track": "src",
    "video": "src",
    "object": "data",
    "data": "value",
    "meter": "value",
    "time": "datetime",
}
_TYPED = {"string", "integer", "number", "boolean", "null"}

# Subtrees whose contents are inert in HTML: they create no item scopes or
# properties and contribute no scalar text (H6, "a non-rendered place";
# docs/MICRODATA.md M2 parses the document as HTML).
_INERT_CONTENT = {"script", "template"}


class MicrodataError(ValueError):
    """The document is not valid FHGFF3 microdata."""


class _Node:
    __slots__ = (
        "tag",
        "attrs",
        "children",
        "itemscope",
        "itemtype",
        "itemprop",
        "datatype",
    )

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        self.itemscope = "itemscope" in attrs
        self.itemtype = attrs.get("itemtype", "").split()
        self.itemprop = attrs.get("itemprop", "").split()
        self.datatype = attrs.get("data-fhr-type")


def _first_wins(attrs):
    """R9: the first of repeated attributes applies."""
    result = {}
    for name, value in attrs:
        if name not in result:
            result[name] = "" if value is None else value
    return result


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {})
        self.stack = [self.root]

    def _pop_through(self, targets, boundaries):
        """Close the nearest target ancestor and everything above it.

        The search skips inline descendants but stops at the scope boundary
        the HTML rule names, so an open span does not hide the p or table cell
        that the start tag has to close (docs/MICRODATA.md M2).
        """
        for index in range(len(self.stack) - 1, 0, -1):
            node = self.stack[index]
            if node.tag in targets:
                del self.stack[index:]
                return True
            if node.tag in boundaries:
                return False
        return False

    def _close_implied(self, tag):
        if tag in _P_CLOSERS:
            self._pop_through({"p"}, _BUTTON_SCOPE)
        rule = IMPLIED_BY_START.get(tag)
        if rule:
            self._pop_through(*rule)

    def handle_starttag(self, tag, attrs):
        self._close_implied(tag)
        node = _Node(tag, _first_wins(attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        # In HTML the self-closing slash does not close a non-void element:
        # ``<span .../>text</span>`` is a span containing that text, not an
        # empty span (M2; the binding's self-closing test case). ``handle_starttag``
        # already keeps genuine void elements out of the stack.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return
            if self.stack[index].tag == "template":
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def unclosed_scopes(self):
        """Item scopes still open at end of input, ignoring inert subtrees."""
        open_scopes = []
        inert = False
        for node in self.stack[1:]:
            if node.tag in _INERT_CONTENT:
                inert = True
            elif node.itemscope and not inert:
                open_scopes.append(node)
        return open_scopes


def _nodes(node):
    for child in node.children:
        if isinstance(child, _Node):
            if child.tag in _INERT_CONTENT:
                continue
            yield child
            yield from _nodes(child)


def _text(node):
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag not in _INERT_CONTENT:
            parts.append(_text(child))
    return "".join(parts)


def _value_of(element):
    attribute = _VALUE_ATTRIBUTE.get(element.tag)
    if attribute and attribute in element.attrs:
        return element.attrs[attribute]
    return _text(element)


def _resolve(root, subschema):
    while isinstance(subschema, dict) and "$ref" in subschema:
        reference = subschema["$ref"]
        if not reference.startswith("#/$defs/"):
            raise MicrodataError(f"unsupported $ref {reference!r}")
        subschema = root["$defs"][reference.rsplit("/", 1)[-1]]
    return subschema


def _json_type(root, subschema):
    resolved = _resolve(root, subschema)
    if "type" in resolved:
        return resolved["type"]
    branches = resolved.get("anyOf") or resolved.get("oneOf")
    if branches:
        types = {_json_type(root, branch) for branch in branches}
        if len(types) == 1:
            return types.pop()
    return None


def _subschema(root, parent, name):
    return _resolve(root, parent).get("properties", {}).get(name, {})


def _parse_typed(raw, datatype):
    if datatype == "string":
        return raw
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise MicrodataError(f"{datatype} value is not JSON: {raw!r}") from error
    if datatype == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise MicrodataError(f"integer value is not an integer: {raw!r}")
    elif datatype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MicrodataError(f"number value is not a number: {raw!r}")
    elif datatype == "boolean":
        if not isinstance(value, bool):
            raise MicrodataError(f"boolean value is not a boolean: {raw!r}")
    elif datatype == "null":
        if value is not None:
            raise MicrodataError(f"null value is not null: {raw!r}")
    else:
        raise MicrodataError(f"unknown data-fhr-type {datatype!r}")
    return value


def _convert_untyped(raw, root, subschema):
    kind = _json_type(root, subschema)
    if kind in ("integer", "number", "boolean"):
        return _parse_typed(raw, kind)
    return raw


def _property_elements(scope):
    """Yield (element, property name) for the item's own properties (M1/H1)."""

    def walk(node):
        for child in node.children:
            if not isinstance(child, _Node):
                continue
            if child.tag in _INERT_CONTENT:
                continue  # H6: script and template contents never contribute metadata.
            if child.datatype in ("array", "object"):
                # A typed container's children are the container's own values,
                # not properties of the enclosing item.
                if child.itemprop:
                    for name in child.itemprop:
                        yield child, name
                continue
            if child.itemprop:
                for name in child.itemprop:
                    yield child, name
                if child.itemscope:
                    continue  # A nested item; its properties are not the parent's.
                # An ordinary property element can contain further properties;
                # they still belong to the enclosing item (M1).
                yield from walk(child)
            elif child.itemscope:
                continue  # A separate item; its properties are not the parent's.
            else:
                yield from walk(child)

    yield from walk(scope)


def _item_subschema(root, subschema):
    """The schema for one occurrence of a field, using an array's items."""
    resolved = _resolve(root, subschema)
    if _json_type(root, subschema) == "array":
        return resolved.get("items", {})
    return subschema


def _read_value(element, root, subschema):
    datatype = element.datatype
    if datatype == "array":
        items = []
        for child in element.children:
            if isinstance(child, str):
                if child.strip():
                    raise MicrodataError("array container has stray text")
                continue
            if child.tag in _INERT_CONTENT:
                continue  # H6: inert content never contributes array items either.
            if "item" not in child.itemprop:
                raise MicrodataError("array container child is not itemprop=item")
            items.append(
                _read_value(child, root, _resolve(root, subschema).get("items", {}))
            )
        return items
    # An array field may also appear as an ordinary occurrence (an untyped
    # item scope, or an explicitly typed object scope). Read it against the
    # item schema, not the array schema (M3).
    item_schema = _item_subschema(root, subschema)
    if datatype == "object":
        if not element.itemscope:
            raise MicrodataError("data-fhr-type=object without itemscope")
        return _read_scope(element, root, item_schema)
    if datatype in _TYPED:
        return _parse_typed(_value_of(element), datatype)
    if datatype is not None:
        raise MicrodataError(f"unknown data-fhr-type {datatype!r}")
    if element.itemscope:
        return _read_scope(element, root, item_schema)
    return _convert_untyped(_value_of(element), root, item_schema)


def _read_scope(scope, root, subschema):
    occurrences = {}
    for element, name in _property_elements(scope):
        value = _read_value(element, root, _subschema(root, subschema, name))
        occurrences.setdefault(name, []).append(value)
    record = {}
    for name, values in occurrences.items():
        field = _subschema(root, subschema, name)
        if _json_type(root, field) == "array":
            if len(values) == 1 and isinstance(values[0], list):
                # A single array container is unwrapped. Repeated containers
                # stay as nested lists, so schema validation rejects them
                # (docs/FHGFF3-MICRODATA.md H7).
                record[name] = values[0]
            else:
                # Ordinary repeated properties form one flat list (M4).
                record[name] = values
        elif len(values) == 1:
            record[name] = values[0]
        else:
            record[name] = values  # M4/H7: a repeated property becomes a list.
    return record


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
    raw = FHGFF3_SCHEMA_URL.match(selection_value)
    if raw:
        release = raw.group(2)
        return schema if release == "main" else _release_schema(release)
    w3id = FHGFF3_W3ID_URL.match(selection_value)
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


def _write_property(name, value):
    prop = escape(name, quote=True)
    if isinstance(value, dict):
        content = "".join(_write_property(key, item) for key, item in value.items())
        return (
            f'<span itemprop="{prop}" itemscope data-fhr-type="object">{content}</span>'
        )
    if isinstance(value, list):
        content = "".join(_write_property("item", item) for item in value)
        return f'<span itemprop="{prop}" data-fhr-type="array">{content}</span>'
    if value is None:
        datatype, text = "null", "null"
    elif isinstance(value, bool):
        datatype, text = "boolean", json.dumps(value)
    elif isinstance(value, int):
        datatype, text = "integer", json.dumps(value)
    elif isinstance(value, float):
        datatype, text = "number", json.dumps(value)
    else:
        datatype, text = "string", value
    return f'<span itemprop="{prop}" data-fhr-type="{datatype}">{escape(text)}</span>'


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
