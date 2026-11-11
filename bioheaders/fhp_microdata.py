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
# fetched at run time (docs/SCHEMA-VERSIONS.md V2 to V4). v0.4.1 and v0.4.2
# carry the same FHP schema contract as v0.4.0 (FHP 1.0); v0.5.0 carries FHP 1.1
# (extension fields). `selection` maps them to the bundled copies.
SUPPORTED_RELEASES = ("v0.4.0", "v0.4.1", "v0.4.2", "v0.5.0")


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
    raw = FHP_SCHEMA_URL.fullmatch(selection_value)
    if raw:
        release = raw.group(2)
        return schema if release == "main" else _release_schema(release)
    w3id = FHP_W3ID_URL.fullmatch(selection_value)
    if w3id:
        return _release_schema(w3id.group(0).rstrip("/").rsplit("/", 1)[-1])
    raise MicrodataError(f"unsupported FHP schema selection: {selection_value!r}")


def _selected_schema(scope, schema):
    for element, name in _property_elements(scope):
        if name == "schema":
            return resolve_schema(_value_of(element), schema)
    raise MicrodataError("FHP item scope has no schema property")


def _tree(text, check=False):
    builder = _TreeBuilder(legacy_self_closing=True)
    builder.feed(text)
    builder.close()
    if check and builder.unclosed_scopes():
        raise MicrodataError(
            "FHP item scope is not closed before the end of the document"
        )
    family_scopes(builder.root)
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
    scopes = [node for node in _nodes(_tree(text, check=True)) if node.itemscope]
    fhp_scopes = [node for node in scopes if FHP_ITEMTYPES & set(node.itemtype)]
    if len(fhp_scopes) != 1:
        raise MicrodataError(
            f"expected exactly one FHP item scope, found {len(fhp_scopes)}"
        )
    selected = _selected_schema(fhp_scopes[0], schema)
    record = _read_scope(fhp_scopes[0], selected, selected)
    # Microdata carries no extension fields (FAIR-bioHeaders-Specification M5).
    try:
        extensions.reject(record, "microdata", "docs/MICRODATA.md M5")
    except ValueError as error:
        raise MicrodataError(str(error)) from None
    return record


def validate_record(record, schema):
    """Validate an extracted record against the schema its ``schema`` selects."""
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
    """Read a document and reject it unless it matches its selected FHP schema."""
    return validate_record(read_page(text, schema), schema)


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
    record = extensions.without_extensions(record)  # Rule M5.
    content = "".join(_write_property(name, value) for name, value in record.items())
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title></head><body>\n"
        f'<div itemscope itemtype="{escape(itemtype, quote=True)}">{content}</div>\n'
        f"{_readable_table(record)}\n"
        "</body></html>\n"
    )
