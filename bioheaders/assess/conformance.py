# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FAIR-bioHeaders schema conformance, reported apart from the checklist (FR-008).

The header type comes from the ``schema`` value, never from substrings of the URL
(FAIR-bioHeaders-Specification#44): a FAIR-bioHeaders schema URL (raw-main, a release's raw tag
or w3id URL of FHR, FHP or FHGFF3) or the FHT schema URL. Records whose ``schema``
is none of these are not assessed (``unsupported-header-type``); the checklist still
reads their fields. The schema follows FAIR-bioHeaders-Specification docs/SCHEMA-VERSIONS.md
(``bioheaders.selection``): raw-main selects the bundled current copy, a versioned URL
the bundled copy of that release, and a release this package does not bundle is
``unsupported-schema-version``. The cited schema URL is never fetched.
"""

import hashlib
from importlib.resources import files

import yaml
from jsonschema.exceptions import ValidationError

from .. import fhr, selection, validation_message
from .model import ConformanceResult

FHT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json"
)
RAW = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/"
FILES = {"FHR": "fhr.json", "FHP": "fhp.json", "FHGFF3": "fhgff3.json"}


def _schema_header_type(cited):
    if cited == FHT_URL:
        return "FHT"
    parsed = selection.parse(cited)
    return parsed[0] if parsed else None


def _bundled(cited):
    """Provenance of the bundled schema ``cited`` selects (canonical URL, SHA-256,
    schemaVersion)."""
    header_type, ref, schema = selection.select(cited)
    content = files("bioheaders").joinpath(selection.bundled_file(cited)).read_bytes()
    # v0.3 FHR schemas leave schemaVersion unrestricted; their contract is version 1.
    versions = schema["properties"]["schemaVersion"].get("enum", [1])
    return {
        "canonical_url": f"{RAW}{ref}/{FILES[header_type]}",
        "bundled_sha256": hashlib.sha256(content).hexdigest(),
        "version": ", ".join(str(value) for value in versions),
    }


def _version_text(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return repr(value)
    return str(value)


def check(lines, prefix):
    """Return (ConformanceResult, metadata or None) for FAIR-bioHeaders lines.

    ``metadata`` is the parsed header when its values may be used as evidence:
    ``None`` when the header cannot be read or is invalid.
    """
    data = fhr()
    try:
        data._input_header_lines(lines, prefix)
    except (ValueError, TypeError, yaml.YAMLError) as error:
        reason = " ".join(str(error).split())
        return (
            ConformanceResult(
                None, None, None, None, "invalid", reason or "unreadable"
            ),
            None,
        )
    metadata = data.__dict__
    schema = metadata.get("schema")
    cited = schema if isinstance(schema, str) else None
    version = metadata.get("schemaVersion")
    version_text = _version_text(version)
    header_type = _schema_header_type(cited)
    if header_type in (None, "FHT"):
        result = ConformanceResult(
            header_type,
            cited,
            version_text,
            None,
            "not_assessed",
            "unsupported-header-type",
        )
        return result, metadata
    try:
        used = _bundled(cited)
    except selection.UnsupportedSchemaVersion:
        result = ConformanceResult(
            header_type,
            cited,
            version_text,
            None,
            "not_assessed",
            "unsupported-schema-version",
        )
        return result, metadata
    try:
        data.fhr_validate()
    except ValidationError as error:
        reason = f"schema validation failed at {error.json_path}: {validation_message(error)}"
        result = ConformanceResult(
            header_type, cited, version_text, used, "invalid", reason
        )
        return result, None
    except ValueError as error:
        result = ConformanceResult(
            header_type,
            cited,
            version_text,
            used,
            "invalid",
            str(error),
        )
        return result, None
    return (
        ConformanceResult(header_type, cited, version_text, used, "valid"),
        metadata,
    )
