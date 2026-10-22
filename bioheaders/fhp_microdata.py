# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHP HTML microdata reader and writer.

Implements the binding in FHP-Specification ``docs/FHP-MICRODATA.md`` on top of
the shared rules M1 to M4 and R9 in ``docs/MICRODATA.md``. It is standard-library
only (``html.parser``) apart from the JSON Schema validation of extracted
records. The writer emits a standalone document with the typed metadata block and
a readable table built from the same record; text and attributes are escaped and
the document contains no script, handler or other executable content.

The reader accepts the typed serialization and the untyped fallback: without
``data-fhr-type`` it converts values using the selected JSON Schema's types, as
rule M3 requires. The record's ``schema`` property selects the contract before
any conversion or validation (F2). Nothing is fetched.
"""

import json
import re
from html import escape
from html.parser import HTMLParser

from jsonschema import Draft202012Validator, FormatChecker

from . import selection

# The raw-main FHP schema URL is the record's itemtype identity
# (docs/SCHEMA-VERSIONS.md; docs/MICRODATA.md M1). The pre-rename repository
# name is the same file and the same item type.
FHP_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhp.json"
)
FHP_ITEMTYPE_OLD_NAME = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHR-Specification/main/fhp.json"
)
FHP_ITEMTYPES = {FHP_ITEMTYPE, FHP_ITEMTYPE_OLD_NAME}

# The `schema` itemprop selects the contract version. It is an FHP schema URL:
# a raw GitHub URL naming `main` or a release tag, or a w3id release URL
# (docs/SCHEMA-VERSIONS.md V1 to V4). Any other ref is unsupported-version.
FHP_SCHEMA_URL = re.compile(
    r"^https://raw\.githubusercontent\.com/FAIR-bioHeaders/"
    r"(FHR|FAIR-bioHeaders)-Specification/(main|v[0-9]+\.[0-9]+\.[0-9]+)/fhp\.json$"
)
FHP_W3ID_URL = re.compile(
    r"^https://w3id\.org/fair-bioheaders/fhp/v[0-9]+\.[0-9]+\.[0-9]+/?$"
)

# Fixed releases this reader carries. They are copies of released schemas, not
# fetched at run time (docs/SCHEMA-VERSIONS.md V2 to V4). v0.4.1 carries the
# same FHP schema contract as v0.4.0. `selection` maps both to the bundled copy.
SUPPORTED_RELEASES = ("v0.4.0", "v0.4.1")

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
_IMPLIED_BY_START = {
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
# properties and contribute no scalar text (docs/FHP-MICRODATA.md F7).
_INERT_CONTENT = {"script", "template"}


class MicrodataError(ValueError):
    """The document is not valid FHP microdata."""


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
        rule = _IMPLIED_BY_START.get(tag)
        if rule:
            self._pop_through(*rule)

    def handle_starttag(self, tag, attrs):
        self._close_implied(tag)
        node = _Node(tag, _first_wins(attrs))
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, _first_wins(attrs)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


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
    """Yield (element, property name) for the item's own properties (M1)."""

    def walk(node):
        for child in node.children:
            if not isinstance(child, _Node):
                continue
            if child.tag in _INERT_CONTENT:
                continue  # Script and template contents never contribute metadata.
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
                # (docs/FHP-MICRODATA.md "Repeated properties").
                record[name] = values[0]
            else:
                # Ordinary repeated properties form one flat list (M4).
                record[name] = values
        elif len(values) == 1:
            record[name] = values[0]
        else:
            record[name] = values  # M4: a repeated property becomes a list.
    return record


def _release_schema(release):
    if release not in SUPPORTED_RELEASES:
        supported = ", ".join(SUPPORTED_RELEASES)
        raise MicrodataError(
            f"unsupported FHP schema version: {release} "
            f"(this reader has FHP releases {supported})"
        )
    return selection.select(f"https://w3id.org/fair-bioheaders/fhp/{release}")[2]


def resolve_schema(selection_value, schema):
    """Resolve the FHP contract a record's ``schema`` value selects (F2).

    ``schema`` is the reader's current (``main``) schema. A released URL
    selects a fixed supported release; an unknown release or any other value
    is unsupported-version and is rejected before extraction or validation.
    """
    if not isinstance(selection_value, str):
        raise MicrodataError(f"unsupported FHP schema selection: {selection_value!r}")
    raw = FHP_SCHEMA_URL.match(selection_value)
    if raw:
        release = raw.group(2)
        return schema if release == "main" else _release_schema(release)
    w3id = FHP_W3ID_URL.match(selection_value)
    if w3id:
        return _release_schema(w3id.group(0).rstrip("/").rsplit("/", 1)[-1])
    raise MicrodataError(f"unsupported FHP schema selection: {selection_value!r}")


def _selected_schema(scope, schema):
    for element, name in _property_elements(scope):
        if name == "schema":
            return resolve_schema(_value_of(element), schema)
    raise MicrodataError("FHP item scope has no schema property")


def _tree(text):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def has_fhp_scope(text):
    """Whether an HTML document contains an FHP item scope (used for dispatch)."""
    return any(
        FHP_ITEMTYPES & set(node.itemtype)
        for node in _nodes(_tree(text))
        if node.itemscope
    )


def read_page(text, schema):
    """Extract one FHP record from an HTML document.

    ``schema`` is the parsed current FHP JSON Schema, used for the untyped
    fallback (M3). The record's ``schema`` value selects the contract first:
    ``main`` uses ``schema``, a supported release uses its released schema, and
    an unavailable release is rejected. Raises :class:`MicrodataError` for a
    document that is not a single, structurally valid FHP item scope.
    """
    scopes = [node for node in _nodes(_tree(text)) if node.itemscope]
    fhp_scopes = [node for node in scopes if FHP_ITEMTYPES & set(node.itemtype)]
    if len(fhp_scopes) != 1:
        raise MicrodataError(
            f"expected exactly one FHP item scope, found {len(fhp_scopes)}"
        )
    selected = _selected_schema(fhp_scopes[0], schema)
    return _read_scope(fhp_scopes[0], selected, selected)


def validate_record(record, schema):
    """Validate an extracted record against the schema its ``schema`` selects."""
    selected = resolve_schema(record.get("schema"), schema)
    errors = list(
        Draft202012Validator(selected, format_checker=FormatChecker()).iter_errors(
            record
        )
    )
    if errors:
        raise MicrodataError(f"{errors[0].json_path}: {errors[0].message}")
    return record


def extract(text, schema):
    """Read a document and reject it unless it matches its selected FHP schema."""
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


def _table_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _readable_table(record):
    """A human-readable table built from the same record as the metadata block."""
    rows = "".join(
        f'<tr><th scope="row">{escape(name)}</th>'
        f"<td>{escape(_table_text(value))}</td></tr>"
        for name, value in record.items()
    )
    return (
        "<table>\n"
        "<caption>FHP metadata</caption>\n"
        '<thead><tr><th scope="col">Field</th><th scope="col">Value</th></tr></thead>\n'
        f"<tbody>{rows}</tbody>\n"
        "</table>"
    )


def write_page(record, itemtype=FHP_ITEMTYPE, title="FHP microdata example"):
    """Write one record as a standalone HTML document (typed serialization).

    The metadata block is the lossless typed form. The readable table below it
    presents the same values; both are escaped, and neither contains script or
    event-handler content.
    """
    content = "".join(_write_property(name, value) for name, value in record.items())
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title></head><body>\n"
        f'<div itemscope itemtype="{escape(itemtype, quote=True)}">{content}</div>\n'
        f"{_readable_table(record)}\n"
        "</body></html>\n"
    )
