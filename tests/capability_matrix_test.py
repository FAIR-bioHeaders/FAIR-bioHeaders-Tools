# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""``docs/CAPABILITY-MATRIX.md`` is generated, so ``pytest`` can hold it to account.

The matrix already has its own CI job, which renders it and runs the generator's
deliberate-defect controls. That job is enough to stop a stale file reaching
``main``, and not enough to stop two other things, which is what this file is for:

* **a hand-edited cell.** The document publishes a digest of its own grid. These
  tests recompute that digest from the tables as printed, with no render and no
  second checkout, so editing one mark in the Markdown fails the ordinary
  ``poetry run pytest`` in well under a second. The same recomputation is used
  against a deliberately flipped copy, which is the control that proves the
  assertion can fail.
* **an evidence citation that over-claims.** A footnote that says a test runs in
  the default suite, about a test that skips unless an environment variable and a
  second checkout are supplied, is the same class of defect the matrix exists to
  catch - it just hides in the evidence column. Here, every citation the document
  makes is classified from the test file it names, and a conditional one has to
  carry its condition in the footnote that cites it.

The expensive check - render again and compare bytes - runs only where it can be
run honestly: the generator insists this checkout is installed non-editably,
because its probes measure *installed commands*. ``pytest.yaml`` installs editable,
so there the test skips and says so; ``capability-matrix.yml`` installs a wheel and
so it executes.
"""

import hashlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "CAPABILITY-MATRIX.md"
GENERATOR = ROOT / "scripts" / "render_capability_matrix.py"

TEXT = MATRIX.read_text(encoding="utf-8") if MATRIX.is_file() else ""

TYPES = ("FHR", "FHP", "FHGFF3", "FHT", "FHGM")
OPERATIONS = ("read", "write", "verify", "strip", "links", "assess", "index")
SERIALIZATIONS = ("json", "yaml", "fasta", "gfa", "gff3", "jsonld", "microdata")

HEADING = re.compile(r"^### (FH[A-Z0-9]+) \u2014")
FOOTNOTE_USE = re.compile(r"\[\^([re][^\]]*)\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([re][^\]]*)\]: (.*)$")
TEST_CITATION = re.compile(r"tests/[A-Za-z0-9_]+\.py::[A-Za-z0-9_\[\].\-]+")
DIGEST = re.compile(r"Digest of the grid: `([0-9a-f]{32})`")


def load_generator():
    spec = importlib.util.spec_from_file_location("render_capability_matrix", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return load_generator()


def parse_rows(text):
    """``{(type, operation, serialization): printed mark}`` from the grids."""
    lines = text.splitlines()
    starts = {}
    for number, line in enumerate(lines):
        found = HEADING.match(line)
        if found and found.group(1) not in starts:
            starts[found.group(1)] = number
    rows = {}
    for name in TYPES:
        assert name in starts, f"the document has no grid heading for {name}"
        columns = None
        for line in lines[starts[name] + 1 :]:
            if line.startswith("#"):
                break
            if line.startswith("| operation"):
                columns = [item.strip() for item in line.split("|")[2:-1]]
                continue
            if not columns or not line.startswith("| "):
                continue
            cells = [item.strip() for item in line.split("|")[1:-1]]
            if len(cells) != len(columns) + 1 or cells[0] not in OPERATIONS:
                continue
            for column, body in zip(columns, cells[1:]):
                mark = body.split("[^")[0].strip()
                assert mark, f"{name}/{cells[0]}/{column}: empty cell"
                rows[(name, cells[0], column)] = mark
    return rows


def defined_footnotes(text):
    return {
        found.group(1): found.group(2)
        for line in text.splitlines()
        if (found := FOOTNOTE_DEF.match(line))
    }


def digest_of(rows, keys):
    """The document's own digest formula, applied to parsed rows."""
    payload = "\n".join(
        f"{key[0]}/{key[1]}/{key[2]}={keys[value]}"
        for key, value in sorted(rows.items())
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


# --- the published file against itself --------------------------------------


def test_matrix_exists_and_declares_itself_generated():
    assert MATRIX.is_file(), "docs/CAPABILITY-MATRIX.md is missing"
    assert "Generated from" in TEXT
    assert "render_capability_matrix.py" in TEXT
    assert "--check" in TEXT


def test_the_grid_is_the_shape_it_claims():
    assert set(parse_rows(TEXT)) == {
        (a, b, c) for a in TYPES for b in OPERATIONS for c in SERIALIZATIONS
    }, "the published grids are not 5 types x 7 operations x 7 serializations"


def test_the_published_digest_matches_the_published_cells(generator):
    """Edit one mark in the Markdown and this fails, with nothing re-rendered."""
    rows = parse_rows(TEXT)
    keys = {label: mark for mark, label in generator.MARKS.items()}
    unknown = {label for label in rows.values() if label not in keys}
    assert not unknown, f"marks this test does not know: {sorted(unknown)}"
    found = DIGEST.search(TEXT)
    assert found is not None, "the document publishes no grid digest"
    assert found.group(1) == digest_of(rows, keys), (
        "a grid cell and the digest below the tables disagree: the document was "
        "edited by hand instead of regenerated"
    )


def test_the_digest_control_is_not_vacuous(generator):
    """The assertion above has to be able to fail, so make it fail on a copy."""
    rows = parse_rows(TEXT)
    keys = {label: mark for mark, label in generator.MARKS.items()}
    good = digest_of(rows, keys)
    flipped = dict(rows)
    victim = ("FHR", "read", "jsonld")
    flipped[victim] = "no" if rows[victim] != "no" else "yes"
    assert digest_of(flipped, keys) != good, (
        "flipping one published cell left the digest alone: the check measures "
        "nothing"
    )


def test_draft_families_are_never_marked_as_earning_support(generator):
    """The mark rule for FHT and FHGM, read off the printed tables."""
    rows = parse_rows(TEXT)
    earned = {generator.MARKS["yes"], generator.MARKS["partial"]}
    bad = sorted(
        f"{name}/{operation}/{serialization}={mark}"
        for (name, operation, serialization), mark in rows.items()
        if name in ("FHT", "FHGM") and mark in earned
    )
    assert not bad, f"an unreleased family is marked as support: {bad}"


def test_every_footnote_used_is_defined(generator):
    used = {
        marker
        for line in TEXT.splitlines()
        if not FOOTNOTE_DEF.match(line)
        for marker in FOOTNOTE_USE.findall(line)
    }
    defined = set(defined_footnotes(TEXT))
    assert not used - defined, f"markers with no footnote: {sorted(used - defined)[:6]}"
    assert not defined - used, f"footnotes nothing cites: {sorted(defined - used)[:6]}"


def test_every_reason_marker_names_a_reason_in_the_text():
    for key, body in defined_footnotes(TEXT).items():
        if not key.startswith("r-"):
            continue
        assert len(body) > 40, f"reason {key} is not explained: {body[:60]!r}"


# --- the evidence column -----------------------------------------------------


def test_every_cited_test_still_exists():
    missing = []
    for citation in sorted(set(TEST_CITATION.findall(TEXT))):
        path, _, name = citation.partition("::")
        file = ROOT / path
        if not file.is_file():
            missing.append(f"{citation} (no such file)")
        elif f"def {name.split('[')[0]}(" not in file.read_text(encoding="utf-8"):
            missing.append(f"{citation} (no such function)")
    assert not missing, f"stale citations: {missing}"


def test_conditional_citations_carry_their_condition(generator):
    """The defect class this file was written for.

    ``tests/fht_conformance_test.py`` consumes the draft lane's vectors and skips
    unless both the opt-in and a pinned FHT-Specification checkout are supplied; a
    footnote that quietly says "run by pytest" about it - or about the samtools,
    pysam, ``pyld`` and second-checkout comparisons - would publish a coverage
    claim that no default run supports. So each citation is classified from the
    file it names, and a conditional one must say so where it is defined.
    """
    bodies = defined_footnotes(TEXT)
    problems = []
    for key, body in bodies.items():
        citations = TEST_CITATION.findall(body)
        if len(citations) != 1:
            continue  # prose lines cite several names; only footnote bodies are ruled
        citation = citations[0]
        conditional = generator.citation_is_conditional(citation)
        says_conditional = "conditional evidence:" in body
        if conditional and not says_conditional:
            problems.append(
                f"{key} cites {citation}, which can skip, without saying so"
            )
        if says_conditional and not conditional:
            problems.append(f"{key} calls {citation} conditional and it is not")
    assert not problems, "; ".join(problems)


def test_the_gating_map_is_neither_empty_nor_stale(generator):
    bodies = TEXT
    assert generator.GATED_TESTS, "the generator declares no conditional citations"
    for citation, condition in generator.GATED_TESTS.items():
        assert citation in bodies, f"{citation} is declared and never cited"
        assert len(condition) > 40, f"{citation} has a placeholder condition"


def test_the_draft_lane_citation_is_declared_conditional(generator):
    """The specific over-claim, named, so it cannot come back by editing one line."""
    citation = "tests/fht_conformance_test.py::test_vector_validity"
    assert citation in generator.GATED_TESTS
    body = next(
        (text for key, text in defined_footnotes(TEXT).items() if citation in text),
        None,
    )
    assert body is not None, f"the document no longer cites {citation}"
    assert "BIOHEADERS_EXPERIMENTAL_FHT" in body
    assert "FHT_SPECIFICATION" in body


def test_the_dated_measurements_are_present_and_attributed():
    for fragment in (
        "## Dated measurements",
        "75 passed, 62 skipped",
        "byte-identical documents",
        "SKIPPED [37]",
        "2026-11-16",
    ):
        assert fragment in TEXT, f"no measurement for {fragment!r}"


# --- the axes and the numbers a reader compares ------------------------------


def test_the_suite_ledger_is_written_as_measured():
    counts = {
        "fasta": 98,
        "gfa": 56,
        "fhp-fasta": 36,
        "fhgff3": 38,
        "jsonld": 37,
        "microdata": 26,
    }
    for format_name, total in counts.items():
        row = next(
            (
                line
                for line in TEXT.splitlines()
                if line.startswith(f"| {format_name} | ")
            ),
            None,
        )
        assert row is not None, f"no ledger row for {format_name}"
        assert f"| {total} | " in row, f"{format_name} ledger says {row!r}"
    assert "291 vectors" in TEXT
    assert "| 37 | 17 / 20 | 0 / 0 | 37 |" in TEXT, "jsonld is not credited as vendored"
    assert "228 pass / 63 not-run" in TEXT, "the libraries' ledger is not attributed"


def test_the_index_cells_cite_a_wrapped_record(generator):
    """One line per record cannot separate the fourth and fifth ``.fai`` fields.

    The vendored examples are all single-line records, so an index check written
    against them alone cannot tell "bases per line, plus the first line's
    terminator" from "whatever the last line was". The wrapped probes exist to make
    that cell falsifiable, and they must be cited where the mark is earned.
    """
    for type_name in ("FHR", "FHP"):
        probe = f"index-wrapped-{type_name}"
        assert f"`{probe}`" in TEXT, f"no wrapped index probe cited for {type_name}"
        row = next(
            line for line in TEXT.splitlines() if line.startswith(f"| `{probe}` | ")
        )
        assert row.rstrip().endswith("| 0 |"), f"{probe} row says {row!r}"
        footnote = next(line for line in TEXT.splitlines() if f"`{probe}` —" in line)
        assert "expected exit 0, observed 0" in footnote, footnote[:160]


def test_the_command_table_lists_every_installed_command(generator):
    """Read from the table the document itself reads: pyproject's scripts block.

    Not `tomllib`, which is 3.11 and later while this package still tests on 3.9 -
    the generator parses the same block for the same reason.
    """
    names = sorted(generator.entry_points())
    assert len(names) == 13, names
    for name in names:
        assert f"`{name}`" in TEXT, f"{name} is missing from the command table"


def test_rule_v7_holds_in_the_published_text(generator):
    assert generator.check_v7(TEXT) == []


def test_the_rule_v7_gate_still_bites(generator):
    widened = "### FHT is a released contract and FHGM is officially supported.\n"
    assert generator.check_v7(widened), "the vocabulary gate accepted a false claim"
    assert generator.check_v7("### FHT is not a released contract.\n") == []


def test_no_alias_url_for_an_unreleased_family():
    for family in ("fht", "fhgm"):
        assert f"w3id.org/fair-bioheaders/{family}" not in TEXT


def test_the_released_baseline_and_the_missing_path_are_both_named():
    for name, version in (("FHR", "2.1"), ("FHP", "1.2"), ("FHGFF3", "1.2")):
        assert f"{name} `{version}`" in TEXT or f"{name} '{version}'" in TEXT
    assert "schemas/fhp.json" in TEXT, "the absent schemas/ path is not recorded"


def test_the_matrix_is_discoverable():
    for relative in (
        "README.md",
        "CHANGELOG.md",
        "AGENTS.md",
        "docs/PIN-AUDIT.md",
        "docs/FHT-SELECTION-DESIGN.md",
        ".github/workflows/capability-matrix.yml",
        "tests/capability_matrix_test.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "CAPABILITY-MATRIX.md" in text, f"{relative} does not link the matrix"


def test_the_readme_does_not_call_the_experimental_binding_supported():
    """README and the matrix must not disagree about the annotation microdata."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "FHGFF3 HTML microdata is supported" not in readme
    assert "EXPERIMENTAL = True" in TEXT or "microdata-experimental" in TEXT


# --- the expensive comparison, where it can be run honestly ------------------


def _renderable(generator):
    """A live render needs a tag checkout and an installed (not editable) copy."""
    if generator.suite_dir() is None:
        return "no FAIR-bioHeaders-Specification checkout at the release tag"
    probe = subprocess.run(
        [sys.executable, "-c", "import bioheaders; print(bioheaders.__file__)"],
        capture_output=True,
        text=True,
        # Not ROOT: from the repository root a `-c` import finds the source tree,
        # which is exactly the editable layout this guard exists to detect.
        cwd=str(Path(sys.executable).parent),
        check=False,
    )
    if "site-packages" not in probe.stdout:
        return (
            "this checkout is installed editable, and the generator's probes measure "
            "installed commands: capability-matrix.yml installs a wheel"
        )
    return None


def test_committed_matrix_matches_a_fresh_render(generator):
    reason = _renderable(generator)
    if reason:
        pytest.skip(reason)
    text, table, probes = generator.build(run_self_test=True)
    assert len(table) == 245
    assert probes.results, "the render executed no probes"
    assert text == TEXT, (
        "docs/CAPABILITY-MATRIX.md differs from a fresh render: regenerate with "
        "`python scripts/render_capability_matrix.py` and read the diff"
    )
