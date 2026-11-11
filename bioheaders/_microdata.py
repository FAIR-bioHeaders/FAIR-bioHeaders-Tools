# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Shared bounded HTML tree and typed microdata machinery (M1-M5, R9).

FHP and FHGFF3 retain their own identities, schema selection and readable tables.
The released FHP self-closing policy is explicit; FHGFF3 follows HTML M2.
"""

import json
from html import escape as _escape
from html.parser import HTMLParser


def escape(value, quote=True):
    """Preserve carriage returns through browser HTML input preprocessing."""
    return _escape(value, quote=quote).replace("\r", "&#13;")


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
    """The document is not valid FAIR-bioHeaders microdata."""


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


# Bound stack scans as well as recursive value extraction before either becomes
# expensive. This is a parser resource limit, not a metadata schema constraint.
MAX_DEPTH = 128


class _TreeBuilder(HTMLParser):
    def __init__(self, *, legacy_self_closing=False):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {})
        self.stack = [self.root]
        self.legacy_self_closing = legacy_self_closing

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
        if len(self.stack) > MAX_DEPTH:
            raise RecursionError("HTML microdata nested too deeply")
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
        if self.legacy_self_closing:
            # Preserve released FHP behavior until the shared binding decides M2
            # compatibility; FHGFF3 uses HTML's non-void start-tag behavior.
            self.stack[-1].children.append(_Node(tag, _first_wins(attrs)))
        else:
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
                if not child.itemprop:
                    raise MicrodataError(
                        f"data-fhr-type={child.datatype} without itemprop"
                    )
                if child.datatype == "object" and not child.itemscope:
                    raise MicrodataError("data-fhr-type=object without itemscope")
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


FAMILY_ITEMTYPES = {
    family: {
        f"https://raw.githubusercontent.com/FAIR-bioHeaders/{repo}/main/{family.lower()}.json"
        for repo in ("FHR-Specification", "FAIR-bioHeaders-Specification")
    }
    for family in ("FHR", "FHP", "FHGFF3")
}


def family_scopes(root):
    families = {
        family
        for node in _nodes(root)
        if node.itemscope
        for family, itemtypes in FAMILY_ITEMTYPES.items()
        if itemtypes.intersection(node.itemtype)
    }
    if len(families) > 1:
        raise MicrodataError(
            "mixed-family microdata item scopes: " + ", ".join(sorted(families))
        )
    return families


def document_families(text):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return family_scopes(builder.root)
