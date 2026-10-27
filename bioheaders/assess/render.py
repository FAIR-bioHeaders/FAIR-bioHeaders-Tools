# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Serialise assessment reports (contracts/cli.md "Outputs", research R-12)."""

import json

from jsonschema import Draft202012Validator, FormatChecker

from .. import selection
from . import data


def _check_no_floats(value, path="$"):
    if isinstance(value, float):
        raise ValueError(f"assessment report contains a float at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _check_no_floats(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_floats(item, f"{path}[{index}]")


def validate_report(report):
    """Raise ``ValueError`` unless ``report`` conforms to the report schema."""
    schema = data.load().report_schema
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            report
        ),
        key=lambda error: error.json_path,
    )
    if errors:
        error = errors[0]
        raise ValueError(
            f"assessment report does not conform at {error.json_path}: {error.message}"
        )
    _check_no_floats(report)


def to_json(report):
    """Return the report as JSON text: sorted keys, UTF-8, LF, trailing newline."""
    validate_report(report)
    return json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


# Human-readable forms -------------------------------------------------------

GROUPS = (
    ("F", "Findable"),
    ("A", "Accessible"),
    ("I", "Interoperable"),
    ("R", "Reusable"),
)
STATUS_LABELS = {
    "evidenced": "evidenced",
    "partially_evidenced": "partially evidenced",
    "not_evidenced": "not evidenced",
    "not_applicable": "not applicable",
    "not_assessed": "not assessed",
}
MAX_SHOWN = 160
_MARKDOWN = str.maketrans(
    {
        "\\": "\\\\",
        "`": "\\`",
        "*": "\\*",
        "_": "\\_",
        "[": "\\[",
        "]": "\\]",
        "|": "\\|",
        "<": "&lt;",
        ">": "&gt;",
    }
)


def shorten(text):
    """Cited lines are shown up to MAX_SHOWN characters; JSON keeps them whole."""
    return text if len(text) <= MAX_SHOWN else text[: MAX_SHOWN - 3] + "..."


def escape_markdown(text):
    return text.replace("&", "&amp;").translate(_MARKDOWN)


def _titles():
    return {i["id"]: i["title"] for i in data.load().indicators}


def _status(result):
    label = STATUS_LABELS[result["status"]]
    if result["reason"]:
        label += f" ({result['reason']})"
    return label


def _link_line(link, lines):
    value = link["value"]
    if isinstance(value, dict):
        value = ", ".join(f"{name}={digest}" for name, digest in sorted(value.items()))
    cited = ", ".join(str(lines[e]) for e in link["evidence"])
    detail = f"line {cited}" + (
        f", {link['relationship']}" if link["relationship"] else ""
    )
    if not link["well_formed"]:
        detail += ", malformed"
    verification = link["verification"]
    if verification is None:
        verdict = "not verified: no related file given"
    else:
        verdict = verification["verdict"]
        if verification["reason"]:
            verdict += f" ({verification['reason']})"
        if verification["method"] != "none":
            verdict += f" by {verification['method']}"
        for hint in verification["hints"]:
            verdict += f"; hint: {hint}"
    return f"{link['kind']}  {value}  ({detail})  {verdict}"


def _input_lines(report):
    item = report["input"]
    lines = [
        f"FAIR header assessment: {item['path']} ({item['format']}, "
        f"{item['compression']})",
        f"Input: {item['scope'].replace('_', ' ')}; format from {item['format_source']};"
        f" header lines read: {item['header_lines_read']};"
        f" records sampled: {item['records_sampled']}",
    ]
    if "header_sha256" in item:
        lines.append(f"Header SHA-256: {item['header_sha256']}")
    if "file_sha256" in item:
        lines.append(f"File SHA-256: {item['file_sha256']}")
    if "error" in item:
        lines.append(f"Error: {item['error']}")
    lines.append(
        "Online checks: "
        + ("ran" if report["online_checks"] == "ran" else "not requested")
    )
    lines.append(
        f"Rubric {report['rubric_version']}, synonyms {report['synonyms_version']}, "
        + ", ".join(f"{k} {v}" for k, v in sorted(report["reference_versions"].items()))
        + f"; {report['tool']['name']} {report['tool']['version']}"
    )
    return lines


def _conformance_lines(conformance):
    lines = [
        f"header type: {conformance['header_type'] or 'not on the schema allow-list'}",
        f"cited schema: {conformance['cited_schema'] or 'none'}"
        + (
            f" (schemaVersion {conformance['cited_schema_version']})"
            if conformance["cited_schema_version"]
            else ""
        ),
    ]
    used = conformance["schema_used"]
    if used:
        lines.append(
            f"validated against: {used['canonical_url']} (bundled copy, SHA-256 "
            f"{used['bundled_sha256']}, schemaVersion {used['version']})"
        )
        if selection.parse(conformance["cited_schema"]) == ("FHR", "main") and (
            f"/{selection.FHR1_RELEASE}/" in used["canonical_url"]
        ):
            lines.append(f"warning: {selection.FHR1_WARNING}")  # rule V6
    result = conformance["result"].replace("_", " ")
    if conformance["reason"]:
        result += f": {conformance['reason']}"
    lines.append(f"result: {result}")
    return lines


def _circumstantial_lines(check):
    missing = ", ".join(check["missing_from_related"]) or "none"
    lengths = (
        ", ".join(
            f"{m['name']} declared {m['declared']}, actual {m['actual']}"
            for m in check["length_mismatches"]
        )
        or "none"
    )
    return [
        f"source: {check['source']}  related file: {check['related_path']}",
        f"names compared: {check['names_compared']}  lengths compared: "
        f"{check['lengths_compared']}  not declared: {check['not_declared_count']}",
        f"missing from the related file: {missing}",
        f"length differences: {lengths}",
        f"verdict: {check['verdict']}",
    ]


def _online_lines(report):
    lines = []
    for check in report["online"]["checks"]:
        status = (
            f"HTTP {check['http_status']}"
            if check["http_status"] is not None
            else "no HTTP status"
        )
        final = f" -> {check['final_url']}" if check["final_url"] else ""
        lines.append(
            f"{check['target']}: {check['outcome'].replace('_', ' ')}, {status}, "
            f"at {check['checked_at']} ({check['request_url']}{final})"
        )
    return lines or ["no identifier or URL in the header could be resolved"]


ONLINE_HEADING = "Online checks (time-dependent; not part of the reproducible report)"


def to_text(report):
    """The terminal report (contracts/cli.md "Outputs")."""
    titles = _titles()
    lines_of = {item["id"]: item for item in report["evidence"]}
    out = _input_lines(report)
    if report.get("conformance"):
        out += ["", "FAIR-bioHeaders conformance (separate from the checklist)"]
        out += ["  " + line for line in _conformance_lines(report["conformance"])]
    for letter, name in GROUPS:
        out += ["", name]
        for result in report["results"]:
            if result["indicator"].split("-")[1][0] != letter:
                continue
            out.append(
                f"  {result['indicator']:<13} {_status(result):<22} "
                f"{titles[result['indicator']]}"
            )
            for evidence in result["evidence"]:
                item = lines_of[evidence]
                out.append(f"      line {item['line']}: {shorten(item['raw'])}")
            for finding in result["findings"]:
                out.append(f"      finding ({finding['kind']}): {finding['message']}")
            for note in result.get("notes", []):
                out.append(f"      note: {note}")
            suggestion = result["suggestion"]
            if suggestion:
                out.append(f"      suggestion: {suggestion['text']}")
                out.append(f"        {suggestion['line']}")
    if report.get("online"):
        out += ["", ONLINE_HEADING]
        out += ["  " + line for line in _online_lines(report)]
    out += ["", "Recorded links"]
    lines = {item["id"]: item["line"] for item in report["evidence"]}
    if report.get("links"):
        out += ["  " + _link_line(link, lines) for link in report["links"]]
    else:
        out.append("  none recorded in the header")
    if report.get("circumstantial"):
        out += ["", "Circumstantial evidence (not a recorded link)"]
        out += ["  " + line for line in _circumstantial_lines(report["circumstantial"])]
    if report.get("pair_classification"):
        out += ["", f"Pair: {report['pair_classification']}"]
    out += ["", "Findings"]
    if report["findings"]:
        for finding in report["findings"]:
            out.append(f"  {finding['kind']}: {finding['message']}")
    else:
        out.append("  none")
    out += ["", report["attribution"], ""]
    return "\n".join(out)


def _cell(text):
    return escape_markdown(text).replace("\n", " ")


def to_markdown(report):
    """The Markdown report, with every cited line escaped."""
    titles = _titles()
    lines_of = {item["id"]: item for item in report["evidence"]}
    head = _input_lines(report)
    out = [f"# {_cell(head[0])}", ""]
    out += [f"- {_cell(line)}" for line in head[1:]]
    if report.get("conformance"):
        out += ["", "## FAIR-bioHeaders conformance (separate from the checklist)", ""]
        out += [
            f"- {_cell(line)}" for line in _conformance_lines(report["conformance"])
        ]
    for letter, name in GROUPS:
        out += [
            "",
            f"## {name}",
            "",
            "| Indicator | Status | Evidence | Suggestion |",
            "|---|---|---|---|",
        ]
        for result in report["results"]:
            if result["indicator"].split("-")[1][0] != letter:
                continue
            evidence = "<br>".join(
                f"line {lines_of[e]['line']}: {shorten(escape_markdown(lines_of[e]['raw']))}"
                for e in result["evidence"]
            )
            notes = [f"{f['kind']}: {f['message']}" for f in result["findings"]]
            notes += result.get("notes", [])
            if notes:
                evidence += ("<br>" if evidence else "") + "<br>".join(
                    _cell(note) for note in notes
                )
            suggestion = result["suggestion"]
            proposal = (
                f"{_cell(suggestion['text'])}<br>{_cell(suggestion['line'])}"
                if suggestion
                else ""
            )
            out.append(
                f"| {result['indicator']} {_cell(titles[result['indicator']])} "
                f"| {_cell(_status(result))} | {evidence} | {proposal} |"
            )
    if report.get("online"):
        out += ["", f"## {ONLINE_HEADING}", ""]
        out += [f"- {_cell(line)}" for line in _online_lines(report)]
    lines = {item["id"]: item["line"] for item in report["evidence"]}
    out += ["", "## Recorded links", ""]
    if report.get("links"):
        out += [f"- {_cell(_link_line(link, lines))}" for link in report["links"]]
    else:
        out.append("- none recorded in the header")
    if report.get("circumstantial"):
        out += ["", "## Circumstantial evidence (not a recorded link)", ""]
        out += [
            f"- {_cell(line)}"
            for line in _circumstantial_lines(report["circumstantial"])
        ]
    if report.get("pair_classification"):
        out += ["", f"Pair: {_cell(report['pair_classification'])}"]
    out += ["", "## Findings", ""]
    if report["findings"]:
        out += [
            f"- {_cell(f['kind'])}: {_cell(f['message'])}" for f in report["findings"]
        ]
    else:
        out.append("- none")
    out += ["", _cell(report["attribution"]), ""]
    return "\n".join(out)
