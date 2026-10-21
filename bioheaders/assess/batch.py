# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Batch mode: assess a release (research R-14, R-16; contracts/cli.md).

Files are collected in sorted order (``--include``/``--exclude`` globs against
paths relative to the root; hidden files only when an include names them).
Each related file of the pairs is scanned once, then the files are assessed in
a process pool whose workers start with those scans. Reports are written in
sorted path order, with paths relative to the root, so the output does not
depend on ``--jobs``, on scheduling or on where the release is stored.

The summaries count statuses per indicator. There is no per-file total.
"""

import fnmatch
import json
import os
import posixpath
import urllib.parse
from concurrent.futures import ProcessPoolExecutor

from .. import __version__
from .render import escape_markdown

STATUSES = (
    "evidenced",
    "partially_evidenced",
    "not_evidenced",
    "not_applicable",
    "not_assessed",
)
SYMBOLS = {
    "evidenced": "E",
    "partially_evidenced": "P",
    "not_evidenced": "N",
    "not_applicable": "NA",
    "not_assessed": "NAS",
}
HEADINGS = (
    "Evidenced",
    "Partially evidenced",
    "Not evidenced",
    "Not applicable",
    "Not assessed",
)
MAX_JOBS = 8


class UsageError(ValueError):
    """A batch-mode usage error (exit 2)."""


def default_jobs():
    return max(1, min(os.cpu_count() or 1, MAX_JOBS))


def read_pairs(path):
    """Parse a pairs TSV (data-files.md §5) into {derived: related}."""
    pairs = {}
    with open(path, encoding="utf-8", newline="") as stream:
        for number, line in enumerate(stream, 1):
            line = line.rstrip("\r\n")
            if not line.strip() or line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) != 2 or not all(c.strip() for c in columns):
                raise UsageError(
                    f"{path}: line {number}: expected derived<TAB>related paths"
                )
            derived, related = (_normal(c) for c in columns)
            for shown in (derived, related):
                if _escapes(shown):
                    raise UsageError(
                        f"{path}: line {number}: {shown} must be a relative path "
                        "inside the assessed directory"
                    )
            if derived in pairs:
                raise UsageError(
                    f"{path}: line {number}: derived path {derived} appears twice"
                )
            pairs[derived] = related
    return pairs


def _normal(path):
    return posixpath.normpath(path.strip().replace(os.sep, "/"))


def _escapes(relative):
    """True if a normalized pairs-file path is absolute or leaves the root."""
    return (
        posixpath.isabs(relative)
        or relative == ".."
        or relative.startswith("../")
        or bool(os.path.splitdrive(relative)[0])
    )


def _hidden(relative):
    return any(part.startswith(".") for part in relative.split("/"))


def _selected(relative, include, exclude):
    if include:
        matched = [p for p in include if fnmatch.fnmatchcase(relative, p)]
        if not matched:
            return False
        if _hidden(relative) and not any(_hidden(p) for p in matched):
            return False
    elif _hidden(relative):
        return False
    return not any(fnmatch.fnmatchcase(relative, p) for p in exclude)


def collect(paths, recursive, include, exclude, output_dir):
    """Return (root or None, [(relative path, path)]) in sorted order."""
    output_real = os.path.realpath(output_dir)
    found = {}
    directories = [p for p in paths if os.path.isdir(p)]
    if directories and not recursive:
        raise UsageError(f"{directories[0]} is a directory: give --recursive")
    for path in paths:
        path = os.fspath(path)
        if not os.path.isdir(path):
            relative = os.path.basename(os.path.normpath(path)) or path
            _add(found, relative, path)
            continue
        for directory, names, files in os.walk(path):
            names[:] = sorted(
                n
                for n in names
                if os.path.realpath(os.path.join(directory, n)) != output_real
            )
            for name in sorted(files):
                full = os.path.join(directory, name)
                relative = os.path.relpath(full, path).replace(os.sep, "/")
                if _selected(relative, include, exclude):
                    _add(found, relative, full)
    root = os.fspath(paths[0]) if len(paths) == 1 and directories else None
    return root, sorted(found.items())


def _add(found, relative, path):
    if relative in found:
        raise UsageError(f"two inputs have the same report path {relative}")
    found[relative] = path


def _scan(path):
    from . import related

    return path, related.scan(path)


def _seed(scanned):
    from . import related

    for path, related_file in scanned:
        related.prime(path, related_file)


def _assess(task):
    from . import assess_file

    path, relative, related, related_shown, options = task
    return assess_file(
        path,
        related=related,
        display_path=relative,
        related_display=related_shown,
        **options,
    )


def _map(function, items, jobs, scanned=()):
    if jobs <= 1 or len(items) <= 1:
        _seed(scanned)
        return [function(item) for item in items]
    with ProcessPoolExecutor(
        max_workers=min(jobs, len(items)), initializer=_seed, initargs=(scanned,)
    ) as pool:
        return list(pool.map(function, items))


def run(
    paths,
    output_dir,
    pairs=None,
    jobs=None,
    online=False,
    related=None,
    include=(),
    exclude=(),
    recursive=False,
    record_limit=1000,
    hash_inputs=False,
    type_option=None,
    online_timeout=None,
    progress=None,
):
    """Assess ``paths`` into ``output_dir``; return (summary, any link mismatch)."""
    from ..cli import write_output
    from . import data, render

    if pairs is not None and related is not None:
        raise UsageError("give --pairs or --related, not both")
    if output_dir is None:
        raise UsageError("batch mode needs --output DIR")
    paths = [os.fspath(p) for p in paths]
    if not paths:
        raise UsageError("give at least one PATH")
    if "-" in paths:
        raise UsageError("- (stdin) cannot be used in batch mode")
    jobs = default_jobs() if jobs is None else jobs
    if jobs < 1:
        raise UsageError("--jobs must be 1 or more")
    root, files = collect(paths, recursive, list(include), list(exclude), output_dir)
    if pairs is not None and not isinstance(pairs, dict):
        pairs = read_pairs(pairs)
    if pairs is not None and root is None:
        raise UsageError("--pairs needs exactly one directory PATH")
    pairs = {_normal(k): _normal(v) for k, v in (pairs or {}).items()}
    tasks, related_paths = [], {}
    options = dict(
        record_limit=record_limit,
        hash_inputs=hash_inputs,
        type_option=type_option,
        online=online,
        online_timeout=online_timeout,
    )
    for relative, path in files:
        related_path = related_shown = None
        if relative in pairs:
            related_shown = pairs[relative]
            related_path = os.path.join(root, *related_shown.split("/"))
        elif related is not None and os.path.realpath(path) != os.path.realpath(
            related
        ):
            related_shown, related_path = os.fspath(related), os.fspath(related)
        if related_path is not None:
            related_paths[related_path] = related_shown
        tasks.append((path, relative, related_path, related_shown, options))
    errors = {}
    scanned = _map(_scan, sorted(related_paths), jobs)
    for path, related_file in scanned:
        if related_file.error:
            errors[related_paths[path]] = f"related file: {related_file.error}"
    # Online checks run in one process, so that requests are made one at a
    # time and de-duplicated across the whole run (research R-10).
    reports = _map(_assess, tasks, 1 if online else jobs, scanned)
    loaded = data.load()
    summary_files, mismatch = [], False
    os.makedirs(output_dir, exist_ok=True)
    for (path, relative, *_rest), report in zip(tasks, reports):
        if report["input"]["scope"] == "error":
            errors[relative] = report["input"]["error"]
        mismatch = mismatch or any(
            (link.get("verification") or {}).get("verdict") == "mismatch"
            for link in report["links"]
        )
        base = os.path.join(output_dir, *relative.split("/")) + ".assessment"
        os.makedirs(os.path.dirname(base), exist_ok=True)
        _write(write_output, base + ".json", render.to_json(report))
        _write(write_output, base + ".md", render.to_markdown(report))
        summary_files.append(
            {
                "path": relative,
                "format": report["input"]["format"],
                "scope": report["input"]["scope"],
                "statuses": {r["indicator"]: r["status"] for r in report["results"]},
                "pair_classification": report["pair_classification"],
            }
        )
        if progress is not None:
            progress(f"{relative}: {report['input']['scope'].replace('_', ' ')}")
    indicators = [indicator["id"] for indicator in loaded.indicators]
    counts = {i: {status: 0 for status in STATUSES} for i in indicators}
    for entry in summary_files:
        for indicator, status in entry["statuses"].items():
            counts[indicator][status] += 1
    summary = {
        "report_version": "1.0.0",
        "tool": {"name": "bioheaders assess", "version": __version__},
        "rubric_version": loaded.rubric_version,
        "synonyms_version": loaded.synonyms_version,
        "reference_versions": dict(loaded.reference_versions),
        "attribution": loaded.attribution,
        "online_checks": "ran" if online else "not_requested",
        "root": root,
        "files": summary_files,
        "indicator_counts": counts,
        "errors": [
            {"path": path, "message": message}
            for path, message in sorted(errors.items())
        ],
    }
    _write(
        write_output,
        os.path.join(output_dir, "summary.json"),
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    _write(write_output, os.path.join(output_dir, "summary.tsv"), to_tsv(summary))
    _write(
        write_output,
        os.path.join(output_dir, "summary.md"),
        to_markdown(summary, indicators),
    )
    return summary, mismatch


def _write(write_output, path, text):
    write_output(path, lambda out: out.write(text), "w", encoding="utf-8", newline="\n")


def to_tsv(summary):
    indicators = list(summary["indicator_counts"])
    rows = ["\t".join(["path", "format", "scope", "pair_classification"] + indicators)]
    for entry in summary["files"]:
        cells = [
            _tsv_cell(entry["path"]),
            entry["format"],
            entry["scope"],
            entry["pair_classification"] or "",
        ]
        cells += [SYMBOLS[entry["statuses"][i]] for i in indicators]
        rows.append("\t".join(cells))
    return "\n".join(rows) + "\n"


def _tsv_cell(text):
    return text.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _md(text):
    """File names and messages as inert Markdown text (no HTML, links or code)."""
    return escape_markdown(_tsv_cell(text))


def _report_link(path):
    """A relative link to a file's report that no Markdown renderer reads as a
    URL scheme or as HTML."""
    return "./" + urllib.parse.quote(path + ".assessment.md", safe="/")


def counts_table(summary, indicators=None):
    indicators = indicators or list(summary["indicator_counts"])
    lines = [
        "| Indicator | " + " | ".join(HEADINGS) + " |",
        "|---" * (len(HEADINGS) + 1) + "|",
    ]
    for indicator in indicators:
        by_status = summary["indicator_counts"][indicator]
        lines.append(
            f"| {indicator} | " + " | ".join(str(by_status[s]) for s in STATUSES) + " |"
        )
    return "\n".join(lines) + "\n"


def to_markdown(summary, indicators=None):
    files = summary["files"]
    online = "ran" if summary["online_checks"] == "ran" else "not requested"
    parts = [
        "# FAIR header assessment: release summary\n",
        f"Root: {_md(summary['root']) if summary['root'] else '(several paths)'}  ",
        f"Files: {len(files)}  ",
        f"Tool: bioheaders assess {summary['tool']['version']}, rubric "
        f"{summary['rubric_version']}, synonyms {summary['synonyms_version']}  ",
        f"Online checks: {online}\n",
        "Each row counts, for one RDA indicator, the files with each status. This "
        "is a checklist per indicator: it does not add up to a grade for a file "
        "or for the release. See each file's report for the cited header lines "
        "and suggestions.\n",
        counts_table(summary, indicators),
        "## Files\n",
        "| File | Format | Scope | Pair classification | Report |",
        "|---|---|---|---|---|",
    ]
    for entry in files:
        link = _report_link(entry["path"])
        parts.append(
            f"| {_md(entry['path'])} | {entry['format']} | {entry['scope']} | "
            f"{entry['pair_classification'] or ''} | [report]({link}) |"
        )
    parts.append("\n## Inputs that could not be assessed\n")
    if summary["errors"]:
        parts += [f"- {_md(e['path'])}: {_md(e['message'])}" for e in summary["errors"]]
    else:
        parts.append("None.")
    parts.append("\n" + summary["attribution"])
    return "\n".join(parts) + "\n"
