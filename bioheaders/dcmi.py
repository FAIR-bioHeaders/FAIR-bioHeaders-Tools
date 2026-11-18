# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Offline, one-way adopted mapping-v1 assembly projection (specification #56).

This is not a header serialization, deposit adapter or checksum verification.
The complete original input bytes, including invalid JSON, stay in the bundle.
"""

import hashlib
import json
import math
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from . import schema_validator
from .jsonld import STRICT_DOI, link_problem

PROFILE = "0.1.0-draft.1"
CONTRACT = "https://w3id.org/fair-bioheaders/fhr/v0.4.0"
SOURCE_ALIASES = {
    CONTRACT,
    CONTRACT + "/",
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/v0.4.0/fhr.json",
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/v0.4.0/fhr.json",
}
PROJECTED = {
    "schema",
    "taxon",
    "metadataAuthor",
    "assemblyAuthor",
    "dateCreated",
    "scholarlyArticle",
    "relatedLink",
    "reuseConditions",
    "assemblyProtocol",
}
OPTIONAL_CONTEXT = ("publisher", "publicationDate", "publicationYear", "resourceDOI")
LIMITATIONS = [
    "RDF links do not retain author/link array order, nameType or complete nested source structures; retain source.json and context.json.",
    "Resource version literals do not establish version relationships; unsupported fields remain in source.json.",
    "Rights text is a RightsStatement label, not a standardized license assertion.",
    "No sequence/checksum verification, identifier resolution, DOI registration, deposit validation or reverse conversion was performed.",
]


NESTED = "JSON is nested too deeply to read; original inputs preserved."


def _load(raw: bytes) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON property: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"non-JSON numeric constant: {value}")

    def finite(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"non-finite JSON number: {value}")
        return result

    return json.loads(
        raw.decode("utf-8-sig"),
        object_pairs_hook=unique,
        parse_constant=constant,
        parse_float=finite,
    )


def _pointer(parts) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _issue(input_name: str, path: str, message: str) -> dict:
    return {"input": input_name, "path": path, "reason": message}


def _doi(iri: str):
    try:
        parts = urlsplit(iri)
        if parts.scheme.casefold() in {"http", "https"} and parts.hostname in {
            "doi.org",
            "dx.doi.org",
        }:
            return unquote(parts.path.lstrip("/")).casefold()
    except ValueError:
        pass
    return None


def _validate(source: Any, context: Any) -> list:
    errors = []
    for name, value, location in (
        ("source", source, "schemas/fhr-2.0.json"),
        ("context", context, "mappings/assembly-export-context.schema.json"),
    ):
        schema = json.loads(
            files("bioheaders").joinpath(location).read_text(encoding="utf-8")
        )
        validator = schema_validator.validator(schema)
        for error in validator.iter_errors(value):
            errors.append(_issue(name, _pointer(error.absolute_path), error.message))
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("schema"), str)
        or source.get("schema") not in SOURCE_ALIASES
        or source.get("schemaVersion") != "2.0"
    ):
        errors.append(
            _issue(
                "source",
                "/schema",
                "Only fixed FHR v0.4.0 / schemaVersion 2.0 is supported.",
            )
        )
    if not errors:
        errors = _link_errors(source, context)
    if errors:
        return sorted(errors, key=lambda e: (e["input"], e["path"], e["reason"]))
    record_doi = _doi(context["metadataRecordIRI"])
    resource_dois = {
        _doi(context["resourceIRI"]),
        context.get("resourceDOI", "").casefold(),
    }
    if context["resourceIRI"] == context["metadataRecordIRI"] or (
        record_doi is not None and record_doi in resource_dois
    ):
        errors.append(
            _issue(
                "context",
                "/metadataRecordIRI",
                "Assembly and metadata record must have distinct identities.",
            )
        )
    if (
        "publicationDate" in context
        and "publicationYear" in context
        and int(context["publicationDate"][:4]) != context["publicationYear"]
    ):
        errors.append(
            _issue(
                "context",
                "/publicationYear",
                "publicationDate and publicationYear conflict; neither takes precedence.",
            )
        )
    article = source.get("scholarlyArticle", "").casefold()
    if article:
        if context.get("resourceDOI", "").casefold() == article:
            errors.append(
                _issue(
                    "context",
                    "/resourceDOI",
                    "Assembly DOI must not be the related article DOI.",
                )
            )
        if _doi(context["resourceIRI"]) == article:
            errors.append(
                _issue(
                    "context",
                    "/resourceIRI",
                    "Assembly IRI must not identify the related article.",
                )
            )
        if _doi(context["metadataRecordIRI"]) == article:
            errors.append(
                _issue(
                    "context",
                    "/metadataRecordIRI",
                    "Metadata record IRI must not identify the related article.",
                )
            )
    return errors


def _literal(value: str) -> str:
    # JSON and Turtle share these quoted-string/control escapes.
    # Reject surrogate code points before RDF output.
    value.encode("utf-8")
    return json.dumps(value, ensure_ascii=False)


def _iri_fields(source: dict, context: dict):
    """Every input value the projection writes as an IRI, with its location."""
    taxon = source.get("taxon")
    if isinstance(taxon, dict) and "uri" in taxon:
        yield "source", "/taxon/uri", taxon["uri"]
    links = source.get("relatedLink")
    for index, link in enumerate(links if isinstance(links, list) else []):
        yield "source", f"/relatedLink/{index}", link
    if "assemblyProtocol" in source:
        yield "source", "/assemblyProtocol", source["assemblyProtocol"]
    for key in ("resourceIRI", "metadataRecordIRI"):
        if key in context:
            yield "context", "/" + key, context[key]


def _link_errors(source: dict, context: dict) -> list:
    """Refuse IRIs outside FORMAT.md R14's schemes, or with whitespace or control
    characters (a JSON Schema ``$`` pattern lets a trailing newline through)."""
    errors = []
    for name, path, value in _iri_fields(source, context):
        problem = link_problem(value) if isinstance(value, str) else "is not a string"
        if problem is not None:
            errors.append(
                _issue(
                    name,
                    path,
                    f"{problem}; not written as an IRI (allowed: absolute "
                    "http, https, ftp, urn, doi or info URIs without whitespace or "
                    "control characters; FAIR-bioHeaders-Specification "
                    "docs/FORMAT.md R14).",
                )
            )
    return errors


def _iri(value: str) -> str:
    value.encode("utf-8")
    if link_problem(value) is not None:  # backstop: inputs passed _link_errors
        raise ValueError(f"refusing to write {value!r} as an IRI")
    return (
        "<"
        + "".join(
            f"\\u{ord(c):04X}" if ord(c) <= 32 or c in '<>"{}|^`\\' else c
            for c in value
        )
        + ">"
    )


def _agent(value: dict) -> str:
    parts = ["a dc:Agent"]
    if "name" in value:
        parts.append("rdfs:label " + _literal(value["name"]))
    if "uri" in value:
        parts.append("dc:identifier " + _literal(value["uri"]))
    return "[ " + " ; ".join(parts) + " ]"


def _project(source: dict, context: dict) -> tuple:
    omissions = []
    resource = [
        "a type:Dataset",
        "dc:title " + _literal(context["title"]),
        "dc:identifier " + _literal(context["resourceIRI"]),
    ]
    resource.extend("dc:creator " + _agent(a) for a in source["assemblyAuthor"])
    if "publisher" in context:
        resource.append("dc:publisher " + _agent(context["publisher"]))
    if "dateCreated" in source:
        resource.append("dc:created " + _literal(source["dateCreated"]) + "^^xsd:date")
    if "publicationDate" in context:
        resource.append(
            "dc:issued " + _literal(context["publicationDate"]) + "^^xsd:date"
        )
    if "uri" in source["taxon"]:
        resource.append("dc:subject " + _iri(source["taxon"]["uri"]))
    else:
        omissions.append(
            _issue(
                "source",
                "/taxon",
                "No taxonomy IRI supplied; no subject inferred from taxon name.",
            )
        )
    if "scholarlyArticle" in source:
        if STRICT_DOI.fullmatch(source["scholarlyArticle"]):
            resource.append(
                "dc:relation "
                + _iri("https://doi.org/" + quote(source["scholarlyArticle"], safe="/"))
            )
        else:
            omissions.append(
                _issue(
                    "source",
                    "/scholarlyArticle",
                    "No syntactically valid DOI; preserve value without a related-resource assertion.",
                )
            )
    resource.extend(
        "dc:relation " + _iri(link) for link in source.get("relatedLink", [])
    )
    if "assemblyProtocol" in source:
        resource.append("dc:relation " + _iri(source["assemblyProtocol"]))
    if "reuseConditions" in source:
        resource.append(
            "dc:rights [ a dc:RightsStatement ; rdfs:label "
            + _literal(source["reuseConditions"])
            + " ]"
        )
    record = [
        "a type:Text",
        "dc:subject " + _iri(context["resourceIRI"]),
        "dc:conformsTo " + _iri(source["schema"]),
    ]
    record.extend("dc:creator " + _agent(a) for a in source["metadataAuthor"])
    for key in ("publicationYear", "resourceDOI"):
        if key in context:
            omissions.append(
                _issue(
                    "context",
                    "/" + key,
                    "Used for agreement/identity conflict checks only; this profile defines no graph projection.",
                )
            )
    text = (
        "@prefix dc: <http://purl.org/dc/terms/> .\n"
        "@prefix type: <http://purl.org/dc/dcmitype/> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n"
    )
    for subject, predicates in (
        (context["resourceIRI"], resource),
        (context["metadataRecordIRI"], record),
    ):
        text += _iri(subject) + "\n  " + " ;\n  ".join(predicates) + " .\n\n"
    return text, omissions


def export_assembly(source_path, context_path, output_dir) -> dict:
    """Write a new directory bundle, returning its report (status exported/rejected).

    Paths are local files. Existing directories/files are never overwritten.
    Unreadable inputs or filesystem failures raise OSError before/in writing the
    bundle. Invalid readable inputs produce a rejected report and original bytes,
    with no Turtle. Successful export does not imply registration readiness.
    """
    source_raw = Path(source_path).read_bytes()
    context_raw = Path(context_path).read_bytes()
    report: dict[str, Any] = {
        "profileVersion": PROFILE,
        "source_contract": CONTRACT,
        "source_schema_version": "2.0",
        "target": {
            "vocabulary": "http://purl.org/dc/terms/",
            "version": "2020-01-20",
            "reference": "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/2020-01-20/",
        },
        "status": "rejected",
        "errors": [],
        "omissions": [],
        "source_root_fields_not_projected": [],
        "not_supplied_context": [],
        "unprojected_field_details": [],
        "limitations": list(LIMITATIONS),
        "registration_readiness": {
            "datacite": "not-assessed",
            "crossref": "not-assessed",
        },
        "preserved_inputs": {
            name: {
                "file": name + ".json",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for name, raw in (("source", source_raw), ("context", context_raw))
        },
    }
    parsed = {}
    errors = []
    for name, raw in (("source", source_raw), ("context", context_raw)):
        try:
            parsed[name] = _load(raw)
        except (ValueError, UnicodeError) as error:
            errors.append(_issue(name, "/", str(error)))
        except RecursionError:
            errors.append(_issue(name, "/", NESTED))
    turtle = None
    if not errors:
        source, context = parsed["source"], parsed["context"]
        try:
            errors = _validate(source, context)
        except RecursionError:
            errors = [_issue("inputs", "/", NESTED)]
        if not errors:
            try:
                turtle, omissions = _project(source, context)
                report["omissions"] = omissions
                report["source_root_fields_not_projected"] = sorted(
                    _pointer([key]) for key in source if key not in PROJECTED
                )
                report["not_supplied_context"] = [
                    key for key in OPTIONAL_CONTEXT if key not in context
                ]
                notes = json.loads(
                    files("bioheaders")
                    .joinpath("mappings/loss-notes.json")
                    .read_text(encoding="utf-8")
                )
                report["unprojected_field_details"] = [
                    _issue(
                        "source",
                        path,
                        notes.get(
                            path,
                            "No adopted mapping for this field; preserved unchanged in source.json.",
                        ),
                    )
                    for path in report["source_root_fields_not_projected"]
                ]
                report["status"] = "exported"
            except UnicodeError:
                errors.append(
                    _issue(
                        "inputs",
                        "/",
                        "Surrogate code points cannot be represented in RDF; original inputs preserved.",
                    )
                )
            except ValueError as error:
                errors.append(
                    _issue("inputs", "/", f"{error}; original inputs preserved.")
                )
    report["errors"] = errors
    output = Path(output_dir)
    output.mkdir()  # Exclusive creation: never overwrite files or follow a symlink.
    (output / "source.json").write_bytes(source_raw)
    (output / "context.json").write_bytes(context_raw)
    if turtle is not None:
        (output / "qualified-dc.ttl").write_text(turtle, encoding="utf-8")
    # A success report is the last completed artifact. Filesystem failures can
    # leave a partial directory, but never a success report without its graph.
    temporary_report = output / "report.json.tmp"
    temporary_report.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_report.replace(output / "report.json")
    return report
