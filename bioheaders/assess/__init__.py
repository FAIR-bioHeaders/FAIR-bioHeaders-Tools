# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FAIR header assessment (FAIR-bioHeaders-Specification specs/010-fair-header-assessment).

``assess_file`` reads the header of one file, offline, and returns a report
that conforms to ``data/assessment-report.schema.json``: one result for each
of the 41 RDA FAIR Data Maturity Model indicators, with the cited header lines
and a suggestion for each gap. ``assess_release`` assesses many files (batch
mode) and writes per-file reports and a release summary. There is no score.

This Python API is provisional until version 1.0 of the report format is
confirmed by provider feedback; the command ``bioheaders assess`` is the
supported interface.
"""

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .. import __version__

STANDARD_STREAM = "-"


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(2**20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assess_file(
    path,
    related=None,
    online=False,
    record_limit=1000,
    hash_inputs=False,
    type_option=None,
    display_path=None,
    related_display=None,
    online_timeout=None,
):
    """Assess one file (``-`` for stdin) and return the report as a plain dict.

    With ``online=True`` the identifiers and URLs in the header are resolved
    (research R-10; ``online_timeout`` seconds per request, default 10); file
    contents are never sent. ``display_path`` and ``related_display`` replace
    the paths written into the report (batch mode writes paths relative to the
    release root).
    """
    online = (online_timeout or 10.0) if online else None
    if path == STANDARD_STREAM:
        with tempfile.TemporaryDirectory() as directory:
            spool = Path(directory) / "stdin"
            with spool.open("wb") as output:
                shutil.copyfileobj(sys.stdin.buffer, output)
            return _assess(
                spool,
                STANDARD_STREAM,
                related,
                record_limit,
                hash_inputs,
                type_option,
                related_display,
                online,
            )
    return _assess(
        path,
        display_path or os.fspath(path),
        related,
        record_limit,
        hash_inputs,
        type_option,
        related_display,
        online,
    )


def assess_release(
    paths,
    output_dir,
    pairs=None,
    jobs=None,
    online=False,
    **options,
):
    """Assess many files and write per-file reports and summaries to ``output_dir``.

    ``paths`` are files and directories (directories are walked recursively).
    ``pairs`` is a pairs TSV path or a mapping of derived to related paths,
    relative to the single directory given. Other keyword options: ``related``,
    ``include``, ``exclude``, ``record_limit``, ``hash_inputs``,
    ``type_option``. Returns the release summary (``summary.json``) as a dict.
    Raises ``ValueError`` for a usage error.
    """
    from . import batch

    summary, _mismatch = batch.run(
        paths,
        output_dir,
        pairs=pairs,
        jobs=jobs,
        online=online,
        recursive=True,
        **options,
    )
    return summary


def _assess(
    path,
    shown,
    related,
    record_limit,
    hash_inputs,
    type_option,
    related_display=None,
    online=None,
):
    from ..cli import _PrefixedStream, open_input
    from . import conventions, data, links, render, rubric, suggestions
    from .model import AssessmentReport, IndicatorResult, InputFile
    from .sniff import classify, compression_of, read_head

    loaded = data.load()
    stdin = shown == STANDARD_STREAM
    size = None
    compression = "none"
    try:
        if not stdin:
            size = os.stat(path).st_size
        with open(path, "rb") as raw:
            compression = compression_of(raw.read(18))
        with open_input(os.fspath(path)) as stream:
            head = read_head(stream)
            format_name, source, scope = classify(
                head, None if stdin else shown, compression, type_option
            )
            reading = None
            if scope == "assessed":
                reading = conventions.read(
                    _PrefixedStream(head, stream), format_name, record_limit
                )
        error = None
    except (OSError, ValueError) as problem:
        format_name, source, scope = "unknown-text", "content", "error"
        reading, error = None, str(problem)
        if isinstance(problem, OSError) and problem.strerror:
            error = f"{problem.strerror}: {shown}"
    evidence, findings, conformance, link_list, conflicting = [], [], None, [], set()
    if reading is not None:
        evidence, findings, conformance, _metadata = conventions.build_evidence(
            reading, format_name
        )
        link_list, link_findings, conflicting = links.extract(evidence)
        findings = sorted(
            findings + link_findings,
            key=lambda f: (int(f.evidence[0][1:]) if f.evidence else 0, f.kind),
        )
    file_sha256 = None
    if hash_inputs and scope != "error":
        file_sha256 = _file_sha256(path)
    input_file = InputFile(
        path=shown,
        size=size,
        compression=compression,
        format=format_name,
        format_source=source,
        scope=scope,
        header_lines_read=reading.lines_read if reading else 0,
        records_sampled=reading.records if reading else 0,
        header_sha256=reading.header_sha256 if reading else None,
        file_sha256=file_sha256,
        error=error,
    )
    formats = {
        entry["format"]: entry for entry in loaded.reference["formats"]["entries"]
    }
    context = rubric.Context(
        scope=scope,
        format=format_name,
        evidence=evidence,
        findings=findings,
        conformance=conformance,
        links=link_list,
        conflicting=conflicting,
        records=reading.records if reading else 0,
        records_ok=reading.records_ok if reading else False,
        truncated=reading.truncated if reading else False,
        formats=formats,
    )
    online_checks = None
    if online is not None:
        from . import online as online_module

        outcomes, online_checks = ({}, [])
        if scope == "assessed":
            outcomes, online_checks = online_module.run(evidence, timeout=online)
        context.online = True
        context.online_outcomes = outcomes
    context.file_name = None if shown == STANDARD_STREAM else Path(shown).name
    context.related_values = None
    check, pair = None, None
    if related is not None and scope == "assessed":
        from . import circumstantial
        from . import related as related_module

        related_path = related_display or os.fspath(related)
        related_file = related_module.scan(related)
        for link in link_list:
            link.verification = links.verify(link, related_file, related_path)
        check = circumstantial.check(
            evidence, reading.seqids, related_file, related_path
        )
        pair = circumstantial.classify(
            [link.verification.verdict for link in link_list], check.verdict
        )
        if pair == "recorded-match" and check.verdict != "consistent":
            from .model import Finding

            findings.append(
                Finding(
                    "format-irregularity",
                    "a recorded link matches the related file, but the declared "
                    f"sequence names or lengths disagree with it ({check.verdict})",
                )
            )
        context.related_values = related_module.suggestion_values(related_file)
    indicators = {indicator["id"]: indicator for indicator in loaded.indicators}
    results = []
    for indicator in loaded.indicators:
        outcome = rubric.evaluate(indicator, context)
        satisfied = outcome.pop("satisfied", set())
        suggestion = None
        if outcome["status"] in ("partially_evidenced", "not_evidenced"):
            suggestion = suggestions.suggest(
                indicator, dict(outcome, satisfied=satisfied), context, indicators
            )
        notes = []
        if (
            indicator["id"] == "RDA-I3-04M"
            and format_name == "gaf"
            and outcome["status"] == "not_evidenced"
        ):
            notes.append(
                "A GAF header links to a gene set or ontology release, not to a genome;"
                " see RDA-I3-02M for the ontology release."
            )
        if online_checks and indicator.get("online_upgrade"):
            notes += _online_notes(outcome, evidence, context.online_outcomes)
        results.append(IndicatorResult(suggestion=suggestion, notes=notes, **outcome))
    report = AssessmentReport(
        tool_version=__version__,
        rubric_version=loaded.rubric_version,
        synonyms_version=loaded.synonyms_version,
        reference_versions=loaded.reference_versions,
        attribution=loaded.attribution,
        input=input_file,
        evidence=evidence,
        results=results,
        conformance=conformance,
        links=link_list,
        circumstantial=check,
        pair_classification=pair,
        findings=findings,
        online=online_checks,
    ).to_json()
    render.validate_report(report)
    return report


ONLINE_WORDS = {
    "resolved": "resolved",
    "not_found": "was not found",
    "unavailable": "could not be checked",
    "refused": "was not requested (refused by the online-check rules)",
}


def _online_notes(outcome, evidence, outcomes):
    """Resolution notes; an online result never changes an offline status."""
    cited = set(outcome.get("evidence", []))
    notes = []
    for line in evidence:
        if line.id not in cited:
            continue
        for item in line.items:
            value = item.value.strip() if isinstance(item.value, str) else None
            if value in outcomes:
                note = f"Online check: {value} {ONLINE_WORDS[outcomes[value]]}."
                if note not in notes:
                    notes.append(note)
    return notes
