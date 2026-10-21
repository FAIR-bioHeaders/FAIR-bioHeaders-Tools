# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Load and validate the versioned assessment data files.

The rubric, the synonym table and the three pinned reference tables ship in
``bioheaders/assess/data``. Each is validated against its JSON Schema when it is
loaded; an invalid file raises ``ValueError`` naming it. The result is cached
per process.
"""

import json
from importlib.resources import files

from jsonschema import Draft202012Validator

REFERENCE_TABLES = ("spdx-licenses", "id-schemes", "formats")

_ENTRY = {
    "spdx-licenses": {
        "id": {"type": "string", "minLength": 1},
        "url": {"type": "string"},
        "deprecated": {"type": "boolean"},
    },
    "id-schemes": {
        "prefix": {"type": "string", "minLength": 1},
        "pattern": {"type": "string", "minLength": 1},
        "persistent": {"type": "boolean"},
        "resolver": {"type": "string"},
    },
    "formats": {
        "format": {"type": "string", "minLength": 1},
        "fairsharing": {"type": ["string", "null"]},
        "version_directive": {"type": ["string", "null"]},
        "versions": {"type": "array", "items": {"type": "string"}},
    },
}


def _reference_schema(table):
    """The shape of a reference table (contracts/data-files.md §3)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["table", "version", "source", "retrieved", "entries"],
        "properties": {
            "table": {"const": table},
            "version": {"type": "string", "minLength": 1},
            "source": {"type": "string", "minLength": 1},
            "retrieved": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "entries": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": sorted(_ENTRY[table]),
                    "properties": _ENTRY[table],
                },
            },
        },
    }


def _read_json(name):
    path = files(__package__).joinpath("data")
    for part in name.split("/"):
        path = path.joinpath(part)
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(name, content, schema):
    errors = sorted(
        Draft202012Validator(schema).iter_errors(content), key=lambda e: e.json_path
    )
    if errors:
        error = errors[0]
        raise ValueError(
            f"Invalid assessment data file {name} at {error.json_path}: {error.message}"
        )


class AssessmentData:
    """The loaded data files and their versions."""

    def __init__(self):
        self.report_schema = _read_json("assessment-report.schema.json")
        self.rubric = _read_json("rubric.json")
        _validate("rubric.json", self.rubric, _read_json("rubric.schema.json"))
        self.synonyms = _read_json("synonyms.json")
        _validate("synonyms.json", self.synonyms, _read_json("synonyms.schema.json"))
        self.reference = {}
        for table in REFERENCE_TABLES:
            name = f"reference/{table}.json"
            content = _read_json(name)
            _validate(name, content, _reference_schema(table))
            self.reference[table] = content
        self._check_references()
        self.indicators = self.rubric["indicators"]
        self.rubric_version = self.rubric["rubric_version"]
        self.synonyms_version = self.synonyms["synonyms_version"]
        self.reference_versions = {
            table: content["version"] for table, content in self.reference.items()
        }
        self.attribution = self.rubric["attribution"]

    def _check_references(self):
        concepts = self.synonyms["concepts"]
        forms = self.synonyms["forms"]
        for indicator in self.rubric["indicators"]:
            for condition in indicator.get("conditions", []):
                if condition["concept"] not in concepts or (
                    "form" in condition and condition["form"] not in forms
                ):
                    raise ValueError(
                        f"Invalid assessment data file rubric.json: {indicator['id']} "
                        f"condition {condition['id']} names an unknown concept or form"
                    )


_CACHE: list[AssessmentData] = []


def load(cache=True):
    """Return the validated data files, loading them once per process."""
    if cache and _CACHE:
        return _CACHE[0]
    loaded = AssessmentData()
    if cache:
        _CACHE.append(loaded)
    return loaded
