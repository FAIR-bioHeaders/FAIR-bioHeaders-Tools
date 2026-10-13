# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FAIR-bioHeaders schema conformance, reported apart from the checklist (FR-008).

The header type comes from the ``schema`` value against an allow-list, never
from substrings of the URL (FHR-Specification#44); FHP and FHGFF3 use the
whole-value pattern of their bundled schemas. FHR and the drafts FHP and FHGFF3
are validated with the toolkit's own reader and validator against the bundled
``fhr_schema.json``, ``fhp_schema.json`` and ``fhgff3_schema.json``, for the
schema versions they bundle; the cited schema URL is never fetched.
"""

import hashlib
from importlib.resources import files

import yaml
from jsonschema.exceptions import ValidationError

from .. import fhr, is_fhgff3_schema, is_fhp_schema, validation_message
from .model import ConformanceResult

FHR_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhr.json"
)
FHT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json"
)
FHP_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhp.json"
)
FHGFF3_URL = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhgff3.json"
# Exact schema values -> header type; FHP and FHGFF3 also accept any
# FHR-Specification ref (is_fhp_schema, is_fhgff3_schema).
HEADER_TYPES = {FHR_URL: "FHR", FHT_URL: "FHT"}
# Header types whose schema is bundled, with the schemaVersion values it covers.
BUNDLED_VERSIONS = {"FHR": {1}, "FHP": {1}, "FHGFF3": {1}}
BUNDLED_FILES = {
    "FHR": ("fhr_schema.json", FHR_URL),
    "FHP": ("fhp_schema.json", FHP_URL),
    "FHGFF3": ("fhgff3_schema.json", FHGFF3_URL),
}


def _schema_header_type(cited):
    if cited in HEADER_TYPES:
        return HEADER_TYPES[cited]
    if is_fhgff3_schema(cited):
        return "FHGFF3"
    return "FHP" if is_fhp_schema(cited) else None


def _bundled(header_type="FHR"):
    name, url = BUNDLED_FILES[header_type]
    content = files("bioheaders").joinpath(name).read_bytes()
    return {
        "canonical_url": url,
        "bundled_sha256": hashlib.sha256(content).hexdigest(),
        "version": "1",
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
    if header_type not in BUNDLED_VERSIONS:
        result = ConformanceResult(
            header_type,
            cited,
            version_text,
            None,
            "not_assessed",
            "unsupported-header-type",
        )
        return result, metadata
    numeric = isinstance(version, (int, float)) and not isinstance(version, bool)
    # A missing or non-numeric schemaVersion is a validation error, not a version.
    if numeric and version not in BUNDLED_VERSIONS[header_type]:
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
            header_type, cited, version_text, _bundled(header_type), "invalid", reason
        )
        return result, None
    except ValueError as error:
        result = ConformanceResult(
            header_type,
            cited,
            version_text,
            _bundled(header_type),
            "invalid",
            str(error),
        )
        return result, None
    return (
        ConformanceResult(
            header_type, cited, version_text, _bundled(header_type), "valid"
        ),
        metadata,
    )
