"""FHGFF3 header results for a GFF3 file, for the gff3-validator (HDR-004 to HDR-010).

FAIR-bioHeaders-Specification spec 007, contracts/cli.md ("Library") and contracts/validator.md.
``header_report`` reads the file once more than the feature checks do and never
writes. Every result is ``{"ok": bool, "message": str}``; a check that could not
run because an earlier one failed is ``{"ok": None, "message": ...}``.
"""

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from . import UnsupportedSchemaVersion, fhr, schema_for, validation_message
from .cli import (
    SequenceScan,
    _parent,
    directive_warnings,
    genome_reference_result,
    open_input,
    read_chunks,
)

LINK_VALIDATORS = {"anyOf", "not"}


def _result(ok, message=""):
    return {"ok": ok, "message": message}


def _skipped(reason):
    return _result(None, f"not checked: {reason}")


def _is_link_error(error):
    message = validation_message(error)
    return message != error.message or (
        error.validator in LINK_VALIDATORS
        and "genomeReference" in str(error.validator_value)
    )


def _link_form(metadata):
    checksum = any(
        isinstance(item, dict)
        and item.get("relationship") == "annotates"
        and item.get("headerType") == "FHR"
        for item in metadata.get("derivedFrom") or []
    )
    reference = isinstance(metadata.get("genomeReference"), dict)
    return {
        (True, True): "both",
        (True, False): "checksum",
        (False, True): "reference",
    }.get((checksum, reference))


def header_report(path, genome=None):
    """Return the FHGFF3 header results of the GFF3 file ``path``.

    Keys: ``present`` (any ``#~`` lines), ``header_type``, ``placement``,
    ``yaml``, ``checksum``, ``schema``, ``genome_link``, ``genome_match``
    (``"matched"``, ``"not matched"``, ``"not checked"`` or ``None`` without
    ``genome``), ``genome_detail`` and ``warnings`` (directive disagreements).
    """
    report = {
        "present": False,
        "header_type": None,
        "placement": _skipped("no header"),
        "yaml": _skipped("no header"),
        "checksum": _skipped("no header"),
        "schema": _skipped("no header"),
        "genome_link": _skipped("no header"),
        "genome_match": None,
        "genome_detail": "",
        "warnings": [],
    }
    try:
        with open_input(path) as stream:
            scan = SequenceScan(read_chunks(stream), "gff3")
    except ValueError as error:
        report["present"] = True
        report["placement"] = _result(False, str(error))
        for key in ("yaml", "checksum", "schema", "genome_link"):
            report[key] = _skipped("the header block is not well placed")
        return report
    if not scan.header:
        return report
    report["present"] = True
    report["placement"] = _result(True)
    data = fhr()
    try:
        data._input_header_lines(scan.header, scan.prefix)
    except (ValueError, TypeError, yaml.YAMLError) as error:
        report["yaml"] = _result(False, " ".join(str(error).split()))
        for key in ("checksum", "schema", "genome_link"):
            report[key] = _skipped("the header cannot be read")
        return report
    report["yaml"] = _result(True)
    metadata = data.__dict__
    report["header_type"] = data.header_type()
    try:
        computed = scan.checksum()
    except ValueError as error:
        report["checksum"] = _result(False, str(error))
    else:
        if metadata.get("checksum") == computed:
            report["checksum"] = _result(True)
        else:
            report["checksum"] = _result(
                False, f"recorded {metadata.get('checksum')}, computed {computed}"
            )
    try:
        schema = schema_for(metadata)
    except UnsupportedSchemaVersion as error:
        # FHR-Specification rule V4: no other schema is substituted.
        report["schema"] = _result(False, str(error))
        report["genome_link"] = _skipped("the schema version is unsupported")
        report["warnings"] = directive_warnings(data, scan, "gff3")
        return report
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(metadata), key=lambda e: list(e.absolute_path)
    )
    link_errors = [e for e in errors if _is_link_error(e)]
    other = [e for e in errors if e not in link_errors]
    report["schema"] = (
        _result(
            False,
            "; ".join(f"{e.json_path}: {validation_message(e)}" for e in other[:5]),
        )
        if other
        else _result(True, f"valid against the bundled {report['header_type']} schema")
    )
    if report["header_type"] != "FHGFF3":
        report["genome_link"] = _skipped(
            f"the header is {report['header_type']}, not FHGFF3"
        )
    elif link_errors:
        report["genome_link"] = _result(
            False, "; ".join(validation_message(e) for e in link_errors)
        )
    else:
        report["genome_link"] = _result(True, f"genome link by {_link_form(metadata)}")
    report["warnings"] = directive_warnings(data, scan, "gff3")
    if genome is not None and report["genome_link"]["ok"]:
        status, detail = _genome_match(metadata, genome)
        report["genome_match"], report["genome_detail"] = status, detail
    return report


def _genome_match(metadata, genome):
    """Compare the genome link with ``genome`` (spec 007 D-03, D-08)."""
    parent = (genome,) + _parent(genome)
    annotates = [
        item
        for item in metadata.get("derivedFrom") or []
        if item.get("relationship") == "annotates"
    ]
    if annotates:  # The checksum is authoritative when both forms are given.
        if parent[1] is None:
            return "not checked", f"{genome}: {parent[3]}"
        if parent[1] == annotates[0]["checksum"]:
            return "matched", f"{genome} has the recorded FHR checksum"
        return "not matched", f"{genome} has checksum {parent[1]}"
    status, detail, _ = genome_reference_result(metadata["genomeReference"], [parent])
    return status, detail
