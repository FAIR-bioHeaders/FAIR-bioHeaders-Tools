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
import pathlib
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

CELL = re.compile(r"^([^\[]+)")
HEADING = re.compile(r"^### (FH[A-Z0-9]+) \u2014")
FOOTNOTE_USE = re.compile(r"\[\^([re][^\]]*)\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([re][^\]]*)\]:")
FOOTNOTE_BODY = re.compile(r"^\[\^([re][^\]]*)\]: (.*)$")
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


def test_every_footnote_used_is_defined_and_every_definition_is_used():
    content = "\n".join(
        line for line in TEXT.splitlines() if not FOOTNOTE_DEF.match(line)
    )
    used = set(FOOTNOTE_USE.findall(content))
    defined = {
        found.group(1)
        for line in TEXT.splitlines()
        if (found := FOOTNOTE_DEF.match(line))
    }
    assert not used - defined, f"markers with no footnote: {sorted(used - defined)[:6]}"
    assert not defined - used, f"footnotes no cell cites: {sorted(defined - used)[:6]}"


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


def defined_footnotes(text):
    """Every footnote definition in the document, as ``marker -> body``.

    Parsing is local on purpose: the generator owns how a footnote is written, and a
    test that imported its formatter could not notice the formatter going wrong.
    """
    bodies = {}
    for line in text.splitlines():
        found = FOOTNOTE_BODY.match(line)
        if found:
            bodies[found.group(1)] = found.group(2)
    return bodies


def test_the_ledger_names_the_runner_of_each_vendored_format():
    """A count without the test that produced it is not checkable.

    The runner may be printed as a footnote marker (it is, when the test can skip,
    because the marker is what carries the condition), so the marker is resolved to
    its definition rather than demanding the name inline.
    """
    bodies = defined_footnotes(TEXT)
    for row, runner in (
        ("| fhgff3 |", "tests/fhgff3_test.py::test_conformance_vector"),
        ("| fhp-fasta |", "tests/fhp_test.py::test_conformance_vector"),
        ("| jsonld |", "tests/jsonld_test.py::test_conformance_vectors"),
    ):
        line = next(item for item in TEXT.splitlines() if item.startswith(row + " "))
        resolved = " ".join(
            bodies.get(marker, "") for marker in FOOTNOTE_USE.findall(line)
        )
        assert runner in (
            line + " " + resolved
        ), f"{row} does not name its runner: {line!r}"
    for absent in ("| fasta |", "| gfa |", "| microdata |"):
        line = next(item for item in TEXT.splitlines() if item.startswith(absent + " "))
        assert "none:" in line, f"{absent} claims a runner it does not vendor: {line!r}"


def test_a_lane_dependent_count_says_which_lane_it_belongs_to():
    """`pyld` is 3.10 and later, so the by-id total is not the same number twice.

    The 3.9 lane skips all 37 JSON-LD vector cases, which is measured, not
    reasoned: ``SKIPPED [37] ... could not import 'pyld'``. The document states both
    counts; a reader comparing matrices across the federation needs to know which
    lane a figure came from.
    """
    assert "111 of 291" in TEXT
    assert "74 of 291" in TEXT, "the 3.9 consequence of the pyld marker is not stated"
    assert "could not import 'pyld'" in TEXT


def test_a_citation_that_can_skip_says_when_it_runs(generator):
    """The defect class this guard was written for.

    The evidence column once said, of every test it named, that ``poetry run
    pytest`` runs it. That is untrue for the draft lane's vector consumer (it needs
    the opt-in *and* a pinned FHT-Specification checkout), for the samtools and
    pysam comparisons, for the ``pyld`` JSON-LD cases on the 3.9 lane, and for the
    manifest-parity tests without a specification checkout. Naming such a test is
    legitimate; presenting it as a collected pass is not, so the footnote has to
    carry the condition - and a citation that has since become unconditional must
    not keep one.
    """
    bodies = defined_footnotes(TEXT)
    assert bodies, "no footnotes parsed; this test would pass vacuously"
    flagged = [key for key, body in bodies.items() if "conditional evidence:" in body]
    assert flagged, "no conditional evidence in the document: check the parser"
    for key, body in bodies.items():
        citations = TEST_CITATION.findall(body)
        if len(citations) != 1:
            continue
        citation = citations[0]
        conditional = generator.citation_is_conditional(citation)
        says = "conditional evidence:" in body
        assert conditional == says, (
            f"{key} cites {citation}: the file says conditional={conditional}, the "
            f"footnote says {says}"
        )
    # The specific over-claim, named so it cannot come back by editing one line.
    draft = next(
        body
        for body in bodies.values()
        if "tests/fht_conformance_test.py::test_vector_validity" in body
    )
    assert "conditional evidence:" in draft
    assert "BIOHEADERS_EXPERIMENTAL_FHT" in draft and "FHT_SPECIFICATION" in draft
    assert "75 passed, 62 skipped" in draft, "the opt-in run is not recorded"
    # A condition kept in the generator and never printed is the same over-claim
    # with better comments, so every declared condition must appear in the text.
    for name, condition in generator.GATED_TESTS.items():
        if name in " ".join(bodies.values()):
            assert (
                condition in TEXT
            ), f"{name} is cited but its condition is not printed"


def _table_citing_all_prose_names(generator):
    """A grid whose only citations are the ones the committed document already makes.

    `check_gating` reads the cells and the prose together; to make it fail for one
    named reason, the fixture has to cite everything else it would otherwise call
    stale. Every case below asserts the message, so a pass for the wrong reason is
    not a pass.
    """
    names = set(generator.TEST_CITATION.findall(TEXT))
    return {
        (f"X{i}", "read", "json"): ("yes", [("test", name)], None)
        for i, name in enumerate(sorted(names))
    }


def test_parameterized_citations_keep_the_function_condition(generator, monkeypatch):
    base = "tests/fht_conformance_test.py::test_vector_validity"
    cited = base + "[fht-fasta-parent-mismatched]"
    assert generator.test_exists(cited)
    assert generator.citation_is_conditional(cited)
    table = _table_citing_all_prose_names(generator)
    table[("parameter", "read", "fasta")] = ("draft", [("test", cited)], None)
    generator.check_gating(table, TEXT.replace(base, cited))

    # The displayed citation retains its parameter, but its condition is the
    # same function-level condition used by the gating classification.
    renderer = object.__new__(generator.Renderer)
    renderer.used = []
    renderer.evidence = {("test", cited): 1}
    footnote = "\n".join(renderer.footnotes({}))
    assert f"`{cited}`" in footnote
    assert "conditional evidence: " + generator.GATED_TESTS[base] in footnote

    monkeypatch.delitem(generator.GATED_TESTS, base)
    with pytest.raises(SystemExit, match="can skip and declares no condition"):
        generator.check_gating(table, TEXT.replace(base, cited))


def test_the_gating_guard_rejects_an_undeclared_skip(generator):
    """And the guard above has to be able to fail, for the stated reason."""
    table = _table_citing_all_prose_names(generator)
    cited = next(
        name
        for name in generator.GATED_TESTS
        if name
        in {found for _, (_, evidence, _) in table.items() for _, found in evidence}
    )
    assert generator.citation_is_conditional(cited)
    declared = generator.GATED_TESTS.pop(cited)
    try:
        with pytest.raises(SystemExit) as raised:
            generator.check_gating(table, TEXT)
        assert "can skip and declares no condition" in str(raised.value)
        assert cited in str(raised.value)
    finally:
        generator.GATED_TESTS[cited] = declared

    # A citation that no longer skips must lose its condition too, or the
    # disclosure itself becomes the over-claim - in the other direction.
    plain = "tests/fht_test.py::test_gate_off_keeps_rule_v5"
    assert not generator.citation_is_conditional(plain)
    generator.GATED_TESTS[plain] = "a condition that is no longer true"
    try:
        with pytest.raises(SystemExit) as raised:
            generator.check_gating(
                {(0, "read", "json"): ("yes", [("test", plain)], None)}, ""
            )
        assert "is declared conditional and no longer is" in str(raised.value)
    finally:
        del generator.GATED_TESTS[plain]
    # And a declaration nobody cites is stale in the same way.
    with pytest.raises(SystemExit) as raised:
        generator.check_gating({}, "")
    assert "is declared and cited by nothing" in str(raised.value)
    generator.GATED_TESTS[cited] = declared


def test_the_index_evidence_includes_a_wrapped_record(generator):
    """Single-line records cannot separate the fourth and fifth ``.fai`` fields.

    htslib writes bases-per-line and first-line-plus-terminator. Every FASTA this
    repository vendors holds one sequence line per record, where an implementation
    that reported the *last* line's width instead is indistinguishable from the
    correct one: measured 2026-11-16, a scan written the wrong way produced
    ``seq4 6 6 4 5`` and ``short 2 21 2 3`` from the single-line examples - the
    same numbers - and only the wrapped record separated them
    (``faidx [('seq4', 6, 1564, 4, 5), …]`` against
    ``scan [('seq4', 6, 1564, 2, 3), …]``). So the wrapped probes are cited in the
    cells, and the rule they check was settled against htslib through pysam rather
    than argued.
    """
    for type_name in ("FHR", "FHP"):
        probe = f"index-wrapped-{type_name}"
        row = next(
            (line for line in TEXT.splitlines() if line.startswith(f"| `{probe}` | ")),
            None,
        )
        assert row is not None, f"{probe} is not in the executed-probe table"
        assert row.rstrip().endswith("| 0 |"), f"{probe} did not exit 0: {row!r}"
        footnote = next(
            line for line in TEXT.splitlines() if f"`{probe}` \u2014" in line
        )
        assert "expected exit 0, observed 0" in footnote, footnote[:160]
        body = generator.WRAPPED_BODY[type_name]
        rows = generator.fai_rows(_tmp_fasta(body))
        assert rows[0][3] != rows[0][4], (
            f"the {type_name} wrapped body does not separate the two fields: "
            f"{rows[0]}"
        )
        assert rows[0][4] == rows[0][3] + 1, f"not htslib's shape: {rows[0]}"


def _tmp_fasta(body):
    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False)
    handle.write(body)
    handle.close()
    return pathlib.Path(handle.name)


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
    # The probes measure *installed commands*, so the generator refuses an editable
    # checkout rather than publish a matrix about source files nobody installed.
    # Ask the same question here, from a directory that is not the repository -
    # from the root, `import bioheaders` finds the source tree and would answer
    # "installed" about a checkout that is not. Both CI workflows install a wheel
    # (`pytest.yaml` adds `pip install --no-deps .` after `poetry install`), so this
    # is about a developer's plain `poetry run pytest`: skip with the reason, do not
    # error and do not pass.
    where = subprocess.run(
        [sys.executable, "-c", "import bioheaders; print(bioheaders.__file__)"],
        capture_output=True,
        text=True,
        cwd=str(Path(sys.executable).parent),
        check=False,
    )
    if "site-packages" not in where.stdout:
        pytest.skip(
            "this checkout is installed editable; the render's probes measure "
            "installed commands, so `python -m pip install --no-deps .` first to "
            "run this check locally"
        )
    text, table, renderer, probes = generator.build()
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
