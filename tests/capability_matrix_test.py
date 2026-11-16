# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The capability matrix is generated, so it can be checked (#211 item 5).

Three kinds of test, in increasing cost:

1. **the published file against itself.** The grid digest at the bottom is
   recomputed from the tables above it, every footnote marker is matched to a
   definition, every ``tests/file.py::name`` it cites is found again, and the
   numbers in the suite ledger are read back out. These cost nothing and fail when
   a cell is edited by hand - the ordinary way a generated document starts lying.
2. **rule V7.** The draft families get no release-shaped word, and the vocabulary
   gate is proven non-vacuous in the same run by feeding it a sentence it must
   reject. A guard that cannot fail is decoration.
3. **the render itself.** The generator is run - probes and all - and compared
   with the committed bytes, then a cell is deliberately flipped and the render
   must differ. This needs a specification checkout at the tag the registry names,
   which ``pytest.yaml`` and ``capability-matrix.yml`` both provide; without one the
   two tests skip and say what they did not check.
"""

import hashlib
import importlib.util
import re
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

CELL = re.compile(r"^([^\[]+)")
HEADING = re.compile(r"^### (FH[A-Z0-9]+) \u2014")
FOOTNOTE_USE = re.compile(r"\[\^([re][^\]]*)\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([re][^\]]*)\]: (.*)$")
TEST_CITATION = re.compile(r"tests/[A-Za-z0-9_]+\.py::[A-Za-z0-9_\[\].\-]+")
DIGEST = re.compile(r"Digest of the grid: `([0-9a-f]{32})`")

# The labels the document publishes, and the mark each one stands for. Restated
# here on purpose: rename a label in one file and not the other and the digest test
# fails, rather than the two drifting into agreement about nothing.
LABELS = {
    "yes": "yes",
    "no": "no",
    "n/a": "na",
    "draft lane": "draft",
    "not here": "none",
    "partial": "partial",
    "not verified": "unverified",
    "observed only": "observed",
}


def load_generator():
    spec = importlib.util.spec_from_file_location("render_capability_matrix", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return load_generator()


def published_grid(text):
    """``{(type, operation, serialization): mark}`` read back out of the tables."""
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
                label = CELL.search(body)
                assert label is not None, f"{name}/{cells[0]}/{column}: no mark"
                assert (
                    label.group(1).strip() in LABELS
                ), f"{name}/{cells[0]}/{column}: unknown mark {label.group(1)!r}"
                rows[(name, cells[0], column)] = LABELS[label.group(1).strip()]
    return rows


def test_matrix_exists_and_declares_itself_generated():
    assert MATRIX.is_file(), "docs/CAPABILITY-MATRIX.md is missing"
    assert "Generated from" in TEXT
    assert "render_capability_matrix.py" in TEXT
    assert "--check" in TEXT


def test_the_grid_is_the_shape_it_claims():
    rows = published_grid(TEXT)
    assert set(rows) == {
        (a, b, c) for a in TYPES for b in OPERATIONS for c in SERIALIZATIONS
    }, "the published grids are not 5 types x 7 operations x 7 serializations"


def test_the_published_digest_matches_the_published_cells():
    """A cell edited by hand breaks this, with no re-render involved."""
    rows = published_grid(TEXT)
    digest = hashlib.sha256(
        "\n".join(
            f"{key[0]}/{key[1]}/{key[2]}={value}" for key, value in sorted(rows.items())
        ).encode("utf-8")
    ).hexdigest()[:32]
    found = DIGEST.search(TEXT)
    assert found is not None, "the document publishes no grid digest"
    assert found.group(1) == digest, (
        "a grid cell and the digest below the tables disagree: the document was "
        "edited by hand instead of regenerated"
    )


def assert_footnote_links(text):
    """Check references independently; a definition cannot cite itself."""
    content = "\n".join(
        line for line in text.splitlines() if not FOOTNOTE_DEF.match(line)
    )
    used = set(FOOTNOTE_USE.findall(content))
    defined = {
        found.group(1)
        for line in text.splitlines()
        if (found := FOOTNOTE_DEF.match(line))
    }
    assert not used - defined, f"markers with no footnote: {sorted(used - defined)[:6]}"
    assert not defined - used, f"footnotes no cell cites: {sorted(defined - used)[:6]}"


def test_every_footnote_used_is_defined_and_every_definition_is_used():
    assert_footnote_links(TEXT)


def test_orphaned_evidence_definition_is_rejected():
    key = next(key for key in defined_footnotes(TEXT) if key.startswith("e"))
    marker = f"[^{key}]"
    orphaned = "\n".join(
        line if FOOTNOTE_DEF.match(line) else line.replace(marker, "")
        for line in TEXT.splitlines()
    )
    assert orphaned != TEXT, "the orphan control removed no reference"
    assert key in defined_footnotes(orphaned), "the control removed the definition too"
    with pytest.raises(AssertionError, match="footnotes no cell cites"):
        assert_footnote_links(orphaned)


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


def test_draft_families_get_no_release_shaped_word(generator):
    assert generator.check_v7(TEXT) == []


def test_the_v7_gate_rejects_a_release_claim_about_a_draft(generator):
    """The guard has to bite, or the sentence above it means nothing."""
    widened = "### FHT is a released contract and FHGM is officially supported.\n"
    assert generator.check_v7(widened), "the vocabulary gate accepted a false claim"
    # Negated, it is the shape this document itself uses.
    assert generator.check_v7("### FHT is not a released contract.\n") == []


def test_no_alias_url_for_an_unreleased_family():
    for family in ("fht", "fhgm"):
        assert f"w3id.org/fair-bioheaders/{family}" not in TEXT


def test_the_suite_ledger_is_written_as_measured():
    """The numbers a reader will compare with the libraries' matrices."""
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
    assert sum(counts.values()) == 291
    assert "111 of 291" in TEXT, "the by-id ledger is not stated as measured"
    assert "228 pass / 63 not-run" in TEXT
    assert "property of the consumer" in TEXT, "the 228/63 split is not attributed"


def test_the_thirteen_commands_are_all_named():
    names = (
        "bioheaders",
        "bioheaders-pin-audit",
        "fhr-convert",
        "fhr-validate",
        "fhr-fasta-strip",
        "fhr-fasta-combine",
        "fhr-fasta-validate",
        "fhr-gfa-strip",
        "fhr-gfa-combine",
        "fhr-gfa-validate",
        "fhr-gff3-strip",
        "fhr-gff3-combine",
        "fhr-gff3-validate",
    )
    for name in names:
        assert f"`{name}`" in TEXT, f"{name} is missing from the command table"


def test_the_out_of_scope_families_are_stated_with_their_sources():
    assert "fhgm-base@none" in TEXT
    assert "FAIR-bioHeaders-Tools#135" in TEXT
    assert (
        "not adopted or released" in TEXT
    ), "the experimental binding is not disclosed"


def test_the_matrix_is_discoverable():
    places = [
        "README.md",
        "CHANGELOG.md",
        "docs/PIN-AUDIT.md",
        "docs/FHT-SELECTION-DESIGN.md",
        "AGENTS.md",
    ]
    for relative in places:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "CAPABILITY-MATRIX.md" in text, f"{relative} does not link the matrix"


def test_the_released_contracts_are_cited_at_the_tag():
    for name, version in (("FHR", "2.1"), ("FHP", "1.2"), ("FHGFF3", "1.2")):
        assert f"| {name} | `v0.6.0` | `'{version}'` |" in TEXT
    assert "schemas/fhp.json" in TEXT, "the missing schemas/ path is not named"


def test_the_draft_lane_is_described_as_opt_in_only():
    assert "BIOHEADERS_EXPERIMENTAL_FHT" in TEXT
    for fragment in ("commit", "sha256"):
        assert fragment in TEXT, f"the draft disclosure names no {fragment}"
    assert "never a claim" in TEXT or "no claim of any kind" in TEXT


# --- the expensive checks, run where a tag checkout exists -------------------


@pytest.fixture(scope="module")
def render(generator):
    """One live render, shared by the two tests that need it.

    Building means running every probe, so it happens once per session; the second
    test mutates a copy of the grid the renderer already derived.
    """
    if generator.suite_dir() is None:
        pytest.skip(
            "no FAIR-bioHeaders-Specification checkout at the release tag: set "
            "FHR_SPECIFICATION (pytest.yaml and capability-matrix.yml both do) to "
            "re-check the document against a live render"
        )
    text, table, renderer, probes = generator.build(run_self_test=True)
    try:
        yield text, table, renderer, probes
    finally:
        probes.close()


def test_committed_matrix_matches_a_fresh_render(render):
    text, table, renderer, probes = render
    assert not renderer.check_v7(text)
    assert len(table) == 245
    assert len(probes.results) > 100, "a render with almost no probes proves little"
    assert text == TEXT, (
        "docs/CAPABILITY-MATRIX.md differs from a fresh render: regenerate with "
        "`python scripts/render_capability_matrix.py` and read the diff"
    )


def test_the_gate_fails_on_a_wrong_cell(render, generator):
    """Proved to bite here, on the real render, without touching the tree."""
    text, table, renderer, probes = render
    key = generator.SAMPLE_CELL
    flipped = dict(table)
    mark, evidence, reason = flipped[key]
    flipped[key] = ("na", evidence, reason)
    assert mark != "na", "the sample cell must be an earned one to flip"
    assert (
        renderer.document(flipped) != text
    ), "re-marking a measured cell changed nothing: the check is vacuous"
    granted = dict(table)
    granted[("FHGM", "read", "json")] = ("yes", evidence, None)
    with pytest.raises(SystemExit):
        # Not merely a different document: the render refuses to write a yes for a
        # family this artifact holds no reference to.
        renderer.document(granted)
    assert (
        renderer.document(dict(table)) == text
    ), "an unmutated re-render did not reproduce the document"


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


def test_every_reason_marker_names_a_reason_in_the_text():
    for key, body in defined_footnotes(TEXT).items():
        if not key.startswith("r-"):
            continue
        assert len(body) > 40, f"reason {key} is not explained: {body[:60]!r}"


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


def test_the_index_cells_cite_a_wrapped_record(generator):
    """A short final line exposes first-line versus last-line width mistakes.

    The vendored examples are all single-line records, so an index check written
    against them alone cannot expose incorrectly using the last line's width. The wrapped probes exist to make
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


def test_the_readme_does_not_call_the_experimental_binding_supported():
    """README and the matrix must not disagree about the annotation microdata."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "FHGFF3 HTML microdata is supported" not in readme
    assert "EXPERIMENTAL = True" in TEXT or "microdata-experimental" in TEXT


def test_prose_citations_publish_their_conditions(generator):
    for citation in (
        "tests/fhp_test.py::test_fixtures_match_the_specification",
        "tests/fhgff3_test.py::test_fixtures_match_the_specification",
        "tests/jsonld_test.py::test_vectors_match_the_specification",
        "tests/jsonld_test.py::test_conformance_vectors",
    ):
        lines = [line for line in TEXT.splitlines() if f"`{citation}`" in line]
        assert any(
            f"conditional evidence: {generator.GATED_TESTS[citation]}" in line
            for line in lines
        ), citation


def test_removed_prose_disclosure_is_rejected(generator):
    citation = "tests/fhp_test.py::test_fixtures_match_the_specification"
    condition = generator.GATED_TESTS[citation]
    broken = TEXT.replace(condition, "condition deliberately removed")
    assert broken != TEXT, "the negative control removed no published condition"
    with pytest.raises(SystemExit, match="no published condition"):
        generator.check_gating({}, broken)
