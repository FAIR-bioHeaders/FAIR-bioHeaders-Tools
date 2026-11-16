#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Generate ``docs/CAPABILITY-MATRIX.md`` from the code and from commands run now.

One question per cell: what does *this artifact* do with a header of type T,
carried in serialization S, under operation O. Prose about coverage drifts. A
README sentence written for FHR JSON-LD reads later like a promise about FHGFF3
JSON-LD, and "the suite passes" hides which serializations were ever executed.
So nothing in the grids is typed by hand.

Where each verdict comes from, best first:

1. **a probe** - an installed command from this checkout, run while rendering,
   whose exit status - and, where the exit status alone would prove too little,
   the bytes or the report it writes - is compared with the expectation recorded
   beside it. The verdict is read from what the command did. A regression
   changes the document, so CI reports the difference instead of a reviewer
   noticing it three weeks later.
2. **a rule in the package** - ``bioheaders.cli.validate_header_family`` is
   *called* for every (carrier, type) pair, including with the draft lane open,
   so the FASTA/GFA/GFF3 columns follow the production rule rather than a copy
   of it. The probes then confirm that ``convert`` agrees with that rule: if the
   gate admits a pair and the command refuses it, the render fails.
3. **data files** - the ``[tool.poetry.scripts]`` table, the CLI's own subcommand
   table, ``bioheaders/schemas/bundled.json``, ``bioheaders/pins.json``, the
   per-format manifests vendored under ``tests/fixtures/``, and, read from the
   specification **at the release tag** ``bundled.json`` names (never ``main``:
   FAIR-bioHeaders-Specification#241 rule 1), ``conformance/manifest.json`` and
   ``schemas/versions.json``.
4. **a named test** - only where no probe can reach the lane (the draft lane, and
   the FHGM scope statement), and then the test is re-found as a ``def`` in its
   file during the render, so a rename breaks the render instead of leaving a
   citation pointing at nothing.

Rule V7 (``docs/SCHEMA-VERSIONS.md``) is enforced, not remembered: see
:meth:`Renderer.check_v7`. FHT and FHGM get no contract version, no registry row,
no w3id or tag URL and no release-shaped word anywhere in this document. A draft
cell may only be ``draft lane``, ``no``, ``n/a``, ``partial`` or ``not verified``.

Usage::

    python scripts/render_capability_matrix.py              # write the file
    python scripts/render_capability_matrix.py --check       # fail on drift

``--check`` fails when the committed file differs from this render, when any
probe disagrees with its expectation, when a cited test has vanished, when a
forbidden word appears, or when the specification checkout is missing. It never
writes, and it never renders a shorter document silently: the checkout is
required, because the suite ledger and the version axis are read there. Point it
at one with ``FHR_SPECIFICATION`` (the variable the test suite already uses) or
``--suite``; ``.github/workflows/capability-matrix.yml`` checks out the tag.
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "CAPABILITY-MATRIX.md"
BUNDLED_PATH = ROOT / "bioheaders" / "schemas" / "bundled.json"
PINS_PATH = ROOT / "bioheaders" / "pins.json"
PYPROJECT = ROOT / "pyproject.toml"

# The serialization axis, in column order. It must equal the values of the CLI's
# own ``FORMAT_NAMES`` table: a format added there without a column here fails the
# render, which is the point of pinning it.
SERIALIZATIONS = ("json", "yaml", "fasta", "gfa", "gff3", "jsonld", "microdata")
CARRIERS = ("fasta", "gfa", "gff3")  # bytes a file-bound checksum covers
DOCUMENTS = ("json", "yaml", "jsonld", "microdata")  # metadata-only forms

# The operation axis, in row order. The named commands are checked against the
# CLI's subcommand table during the render.
OPERATIONS = (
    ("read", ("validate",)),
    ("write", ("convert", "combine")),
    ("verify", ("verify",)),
    ("strip", ("strip",)),
    ("links", ("verify-links",)),
    ("assess", ("assess",)),
    ("index", ("faidx",)),
)

MARKS = {
    "yes": "yes",
    "no": "no",
    "na": "n/a",
    "draft": "draft lane",
    "none": "not here",
    "partial": "partial",
    "unverified": "not verified",
}

# Vendored inputs, one file per (type, serialization) the type reaches. The write
# probes convert from each type's JSON document, so a type needs no JSON entry of
# its own to be written.
FIXTURES = {
    "FHR": {
        "json": "examples/example.fhr.json",
        "yaml": "examples/example.fhr.yaml",
        "fasta": "examples/example.fhr.fasta",
        "gfa": "examples/example.fhr.gfa",
        "jsonld": "examples/example.fhr.jsonld",
        "microdata": "examples/example.microdata.fhr.html",
    },
    "FHP": {
        "json": "examples/fhp/minimal-predicted.fhp.json",
        "yaml": "examples/fhp/rich-mixed.fhp.yaml",
        "fasta": "examples/fhp/example.fhp.fasta",
        "jsonld": "examples/fhp/minimal-predicted.fhp.jsonld",
        "microdata": "examples/fhp/rich-microdata.microdata.fhp.html",
    },
    "FHGFF3": {
        "json": "examples/fhgff3/minimal-reference.fhgff3.json",
        "yaml": "examples/fhgff3/rich.fhgff3.yaml",
        "gff3": "examples/fhgff3/annotation.fhgff3.gff3",
        "microdata": "examples/fhgff3/rich-microdata.microdata.fhgff3.html",
    },
}
SOURCE_DOCUMENT = {
    "FHR": "examples/example.fhr.json",
    "FHP": "examples/fhp/minimal-predicted.fhp.json",
    "FHGFF3": "examples/fhgff3/minimal-reference.fhgff3.json",
}
# A refusal is only evidence if the words are the package's own: each phrase
# below is required to appear in the named file (confirm_in_source).
REFUSALS = {
    ("FHR", "gff3"): ("FHR metadata is incompatible with GFF3", "bioheaders/cli.py"),
    ("FHP", "gfa"): ("FHP metadata is incompatible with GFA", "bioheaders/cli.py"),
    ("FHP", "gff3"): ("FHP metadata is incompatible with GFF3", "bioheaders/cli.py"),
    ("FHGFF3", "fasta"): (
        "FHGFF3 metadata is incompatible with FASTA",
        "bioheaders/cli.py",
    ),
    ("FHGFF3", "gfa"): (
        "FHGFF3 metadata is incompatible with GFA",
        "bioheaders/cli.py",
    ),
    ("FHGFF3", "jsonld"): (
        "JSON-LD output is not available for FHGFF3",
        "bioheaders/cli.py",
    ),
}
DOCUMENT_GATE = "Expected a FASTA, GFA or GFF3 file"
# Which shared-suite format each carrier of each type is scored under. FASTA is
# the genome header's serialization and the protein header's alike, so the suite
# keeps them apart by format name, and so must this file.
VECTORS_FOR = {
    ("FHR", "fasta"): "fasta",
    ("FHR", "gfa"): "gfa",
    ("FHP", "fasta"): "fhp-fasta",
    ("FHGFF3", "gff3"): "fhgff3",
}
# Phrases this document quotes rather than paraphrases, and where each one has to
# be found while rendering: a literal in the named source file, or a line in the
# help text the tool prints. A footnote may only quote what the package says.
QUOTED = (
    ("source", "bioheaders/cli.py", DOCUMENT_GATE),
    ("source", "bioheaders/cli.py", " metadata is incompatible with "),
    (
        "source",
        "bioheaders/cli.py",
        "JSON-LD output is not available for FHGFF3 metadata yet",
    ),
    (
        "source",
        "bioheaders/cli.py",
        "the schema.org export profile is not available for FHP",
    ),
    (
        "source",
        "bioheaders/fhgff3_microdata.py",
        "FHGFF3 HTML microdata is experimental pending release of its binding",
    ),
    ("help", "convert", "FHGFF3 supports HTML microdata, not JSON-LD"),
    ("help", "convert", "FHP supports canonical only (provisional)"),
)
# A limit stated in the tool's own help text, citable as evidence for a cell.
DECLARED_LIMITS = {("FHGFF3", "jsonld"): "FHGFF3 supports HTML microdata, not JSON-LD"}


def source_limit(type_name, serialization):
    """An evidence label for a help-text limit, or None if there is none."""
    phrase = DECLARED_LIMITS.get((type_name, serialization))
    if phrase is None:
        return None
    return f"bioheaders convert --help: {phrase}"


def families_in_pins(pins):
    """Header-family names the pin table mentions, taken from the row ids.

    FHGM is the interesting case today. The shape test is what keeps the axis
    honest instead of inventive: ``FHR_SCHEMA``, ``ASSESSMENT`` and ``SPEC`` name
    copies of *files*, not header families, and only something shaped like a
    family name - ``FH`` plus one to four characters - can join the grid. A row
    naming a new family adds it, which surfaces it rather than hiding it in prose.
    """
    found = []
    for row in pins["references"]:
        token = re.split(r"[@\-_.]", str(row.get("id") or ""), maxsplit=1)[0].upper()
        if re.fullmatch(r"FH[A-Z0-9]{1,4}", token) and token not in found:
            found.append(token)
    return tuple(found)


# Dated observations rendering cannot re-measure: they need an environment this
# file does not have - a second repository, samtools, a container runtime. Each
# names what was run and what it printed so anyone can repeat it. They are
# labelled as measurements and never derived into a verdict.
MEASUREMENTS = (
    (
        "shared suite against the installed commands",
        "`python3 scripts/check_conformance.py --converter <this checkout's bin> "
        "--require-format fasta --require-format gfa --require-format fhp-fasta "
        "--require-format fhgff3 --require-format jsonld --require-format "
        "microdata`, run from a checkout of the specification at tag `v0.6.0` "
        "against commands installed from this branch: `291 vectors passed`, exit "
        "status 0, measured 2026-11-16. `--require-format` is what makes the "
        "number mean something: without it a format the converter lacks is "
        "skipped and reported rather than failing.",
    ),
    (
        "the draft lane's own suite",
        "`BIOHEADERS_EXPERIMENTAL_FHT=1 FHT_SPECIFICATION=<checkout at 7503b26> "
        "python -m pytest tests/fht_conformance_test.py -q`: `75 passed, 62 "
        "skipped` of 137 collected, exit status 0, measured 2026-11-16. The 62 "
        "skips are the parent-link test for the 62 vectors that record no parent "
        "file; 6 vectors record one, and all 68 validity cases ran. Without the "
        "opt-in the same file skips whole, and the default test run never reads "
        "those bytes. `test_suite_manifest_matches_pin` is what licenses the "
        "number: it fails unless the manifest scored is the one "
        "`bundled.json` names.",
    ),
    (
        "the pin audit",
        "`bioheaders-pin-audit` on 2026-11-16 printed `summary: 26 FRESH, 0 "
        "DRIFT, 5 ABSENT of 31`, exit status 0, advisory. Two of the five ABSENT "
        "rows are the filtered per-format copies of the shared manifest vendored "
        "under `tests/fixtures/`, one is `fhgm-base@none`, one is the "
        "`fhp.context.jsonld` copy with no recorded revision, one is this "
        "repository's own unrecorded `examples/` tree. The rows themselves are "
        "data, read from `bioheaders/pins.json`; only the verdict counts came "
        "from a run against upstream bytes.",
    ),
    (
        "the model draft this artifact does not hold",
        "`FHGM-Specification` `origin/main` (`c503ecf`) measured the same day: "
        "`development/conformance/manifest.json`, 51,114 bytes, sha256 "
        "`0d2790151c4a2955…`, 43 vectors of format `fhgff3`. The per-language "
        "libraries vendor and score it (the R library pins commit `d443073` of it "
        "in `inst/VENDORED.json`; the Julia library carries `src/fhgm.jl` and "
        "`drafts/fhgm-*-draft.json`). This toolkit runs none of those 43, and "
        "says why rather than leaving a blank.",
    ),
)

# Cells this repository cannot earn, and why. An omission in a capability
# document is a claim in disguise, so the list is published.
NOT_VERIFIED = (
    (
        "`index` for FHT, and `assess` for a draft-carrying FASTA beyond its "
        "`not_assessed` verdict",
        "no probe or test measures either; the gate is asked in-process, but "
        "nothing runs a draft header through `faidx`",
    ),
    (
        "`index` offsets for the protein header against samtools",
        "`tests/faidx_test.py` compares `.fai` bytes with samtools and pysam for "
        "FHR FASTA only. The FHP cell is earned by an independent recomputation "
        "of every field during this render, which is weaker than the samtools "
        "comparison and is labelled as such",
    ),
    (
        "gzip and BGZF for JSON-LD and microdata as a documented contract",
        "the shared suite holds no compressed vector of either format, and "
        "`open_input` detects compression by magic bytes on any input. The probes "
        "show a gzip member of each is readable; nobody has specified what "
        "compressed metadata documents mean for the checksum, because they carry "
        "no body",
    ),
    (
        "`assess --online` identifier resolution",
        "opt-in and makes network calls; deliberately not exercised here",
    ),
    (
        "the Galaxy wrappers and the container images",
        "`galaxy/tools/fair_bioheaders` is linted by `galaxy-tools.yml` with "
        "`planemo`, which this render does not run, and `Dockerfile` and "
        "`container.yml` build from a *released* wheel. Nothing in this file says "
        "a word about either",
    ),
    (
        "the Python 3.9 lane, and the 3.13 lane separately",
        "this render ran on one interpreter. `pytest.yaml` tests both, and the "
        "JSON-LD vectors import `pyld`, which needs 3.10 or later, so on 3.9 those "
        "37 tests skip and the by-id ledger below is smaller by exactly that much",
    ),
    (
        "the opt-in large-file memory test",
        "`FHR_MEMORY_TEST=1 pytest -k memory` was not run: it writes about 1 GB",
    ),
)

V7_TYPES = ("FHT", "FHGM")
V7_BAD = re.compile(
    r"(released|official|supported|supports|schemaVersion|versions\.json|"
    r"w3id\.org/fair-bioheaders/(fht|fhgm))",
    re.IGNORECASE,
)
V7_NEGATED = re.compile(r"(not|never|no|nothing|only|unreleased|draft)", re.IGNORECASE)


def check_v7(text):
    """Every line naming an unreleased family must be free of release-shaped words.

    This is a vocabulary gate, not a semantics proof: the semantics are the job of
    the cells (a draft cell can only be ``draft lane``, ``no``, ``n/a``, ``partial``
    or ``not verified``, never ``yes``) and of the registry, which holds no
    ``schemaVersion`` row and no alias URL for a draft. What the gate catches is the
    other failure: a sentence that quietly upgrades a draft while every table stays
    correct, which is how documentation drifts ahead of a contract. A line that
    negates itself - "no release", "never a claim", "not a released contract" - is
    the shape this file uses throughout, and passes.
    """
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        if not any(name in line for name in V7_TYPES):
            continue
        if V7_BAD.search(line) and not V7_NEGATED.search(line):
            problems.append(f"line {number}: {line.strip()[:120]}")
    for needle in ("w3id.org/fair-bioheaders/fht", "w3id.org/fair-bioheaders/fhgm"):
        if needle in text:
            problems.append(f"{needle} appears in the document")
    return problems


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fail(message):
    raise SystemExit("capability-matrix: " + message)


def spec_clone():
    """A checkout of the specification: ``--suite``, then ``FHR_SPECIFICATION``.

    The path is a *checkout*, the same convention the test suite already uses, and
    it must be at the tag: :func:`assert_at_tag` proves it before anything is read.
    """
    override = os.environ.get("CAPABILITY_SPEC")
    if override:
        return Path(override)
    clone = os.environ.get("FHR_SPECIFICATION")
    if clone:
        return Path(clone)
    sibling = ROOT.parent / "FAIR-bioHeaders-Specification"
    if (sibling / "conformance" / "manifest.json").is_file():
        return sibling
    return None


def suite_dir():
    """The specification's ``conformance/`` directory, inside that checkout."""
    clone = spec_clone()
    if clone is None:
        return None
    path = Path(clone) / "conformance"
    return path if (path / "manifest.json").is_file() else None


def assert_at_tag(clone, tag):
    """Prove the checkout the matrix reads is the tag, not whatever is on disk.

    Rule 1 of FAIR-bioHeaders-Specification#241 says released material is named by
    a tag. A checkout is not a tag: ``main`` can carry the same registry entry with
    different bytes around it, and then this file would publish digests nobody
    resolved. So HEAD is compared with the tag's own commit, and an unresolvable
    revision fails the render rather than passing on trust.
    """

    def rev(*arguments):
        completed = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip() or None

    head = rev("HEAD")
    wanted = rev(tag + "^{commit}")
    if head is None or wanted is None:
        fail(
            f"cannot prove {clone} is at tag {tag} (git gave HEAD={head} "
            f"tag={wanted}); check the specification out at the tag, as "
            f".github/workflows/capability-matrix.yml does"
        )
    if head != wanted:
        fail(
            f"{clone} is at {head}, not at tag {tag} ({wanted}): the suite ledger "
            "and the contract digests would describe bytes no release names"
        )
    return head


def entry_points():
    """The ``[tool.poetry.scripts]`` table, read from ``pyproject.toml``.

    ``tomllib`` is 3.11 and this package still supports 3.9, so the block is read
    as text: it is the same bytes poetry uses to build the console scripts, which
    is exactly the authority wanted here.
    """
    found = {}
    inside = False
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == "[tool.poetry.scripts]"
            continue
        if inside and "=" in stripped and not stripped.startswith("#"):
            name, _, value = stripped.partition("=")
            found[name.strip()] = value.strip().strip("\"'")
    if not found:
        fail("no [tool.poetry.scripts] entries in pyproject.toml")
    return found


def package_axes():
    """Formats, subcommands and the family gate, imported from the package."""
    sys.path.insert(0, str(ROOT))
    try:
        from bioheaders import __version__
        from bioheaders import cli as cli_module
        from bioheaders import fhgff3_microdata, selection
    except ImportError as error:
        fail(f"importing bioheaders failed ({error}); run this inside the env")
    names = {item.name for item in cli_module.SUBCOMMANDS}
    for _, commands in OPERATIONS:
        for command in commands:
            if command not in names:
                fail(
                    f"operation axis names command {command!r}, which the CLI no "
                    f"longer offers ({', '.join(sorted(names))})"
                )
    derived = tuple(sorted(set(cli_module.FORMAT_NAMES.values())))
    if derived != tuple(sorted(SERIALIZATIONS)):
        fail(
            "the serialization axis and bioheaders.cli.FORMAT_NAMES disagree: "
            f"package has {derived}, this file declares {tuple(sorted(SERIALIZATIONS))}"
        )
    return {
        "version": __version__,
        "subcommands": list(cli_module.SUBCOMMANDS),
        "formats": dict(cli_module.FORMAT_NAMES),
        "compressed_suffixes": tuple(cli_module.COMPRESSED_SUFFIXES),
        "gate": cli_module.validate_header_family,
        "draft_env": selection.DRAFT_ENV,
        "draft_entry": selection.draft_entry("FHT"),
        "microdata_experimental": bool(
            getattr(fhgff3_microdata, "EXPERIMENTAL", False)
        ),
    }


def gate_allows(axes, kind, header_type, draft=False):
    """Ask ``validate_header_family`` itself whether a carrier admits a type."""

    class Probe:
        def header_type(self):
            return header_type

    name = axes["draft_env"]
    previous = os.environ.get(name)
    if draft:
        os.environ[name] = "1"
    try:
        axes["gate"](Probe(), kind)
        return True
    except ValueError:
        return False
    finally:
        os.environ.pop(name, None)
        if previous is not None:
            os.environ[name] = previous


def suffix_of(serialization):
    return {
        "json": "json",
        "yaml": "yaml",
        "fasta": "fasta",
        "gfa": "gfa",
        "gff3": "gff3",
        "jsonld": "jsonld",
        "microdata": "html",
    }[serialization]


def fai_rows(path):
    """Every field of the ``.fai`` format, computed from raw bytes.

    Records are the ``>`` blocks after the header block; offsets count all file
    bytes, header included, which is what makes the index usable through a
    ``;~`` block (the rule `bioheaders/faidx.py` follows from htslib). The two
    line fields follow htslib and samtools, which is that the fourth is bases per
    line *without* the terminator and the fifth is the last line *with* it -
    ``60 61`` for a full 60-column wrap, the shape every real ``.fai`` has.
    """
    data = Path(path).read_bytes()
    rows = []
    index = 0
    size = len(data)
    while index < size:
        end = data.find(b"\n", index)
        stop = size if end == -1 else end + 1
        line = data[index : end if end != -1 else size]
        if not line.startswith(b">"):
            index = stop
            continue
        name = line[1:].split()[0].decode("utf-8", "replace")
        start = stop
        length = 0
        line_bytes = None
        last = 0
        walk = start
        while walk < size:
            nxt = data.find(b"\n", walk)
            term = size if nxt == -1 else nxt + 1
            body = data[walk : nxt if nxt != -1 else size].rstrip(b"\r\n")
            if body.startswith(b">") or body.startswith(b";"):
                break
            length += len(body)
            if line_bytes is None:
                line_bytes = len(body)
            last = term - walk
            walk = term
        rows.append((name, length, start, line_bytes, last))
        index = walk
    return rows


class Probes:
    """Installed commands run once per declared probe, with their expectations."""

    def __init__(self):
        self.bin = Path(sys.executable).parent
        if not (self.bin / "bioheaders").is_file():
            fail(f"no bioheaders command beside {self.bin}; run inside the env")
        self.tmp = Path(tempfile.mkdtemp(prefix="capability-matrix-"))
        self.results = {}

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def out(self, name):
        return str(self.tmp / name)

    def source(self, relative):
        return str(ROOT / relative)

    def fixture(self, type_name, serialization, default=None):
        relative = FIXTURES[type_name].get(serialization, default)
        if relative is None:
            fail(f"no {type_name} fixture for {serialization}")
        return self.source(relative)

    def confirm_in_source(self, phrase, where):
        """Refuse to justify a refusal with words the package does not contain."""
        if phrase not in (ROOT / where).read_text(encoding="utf-8"):
            fail(
                f"gate text {phrase!r} is not in {where}: the package changed its "
                "wording, or this file invented a reason"
            )

    def confirm_in_help(self, phrase, command="convert"):
        """Require a phrase the document quotes to be in the help the tool prints.

        The comparison collapses whitespace, because argparse wraps help text and
        the same sentence is a different run of characters on a different terminal
        width. Source literals are the wrong place to look: the CLI builds its
        strings out of adjacent literals, so a substring search on the file would
        fail on words the program really does print.
        """
        completed = subprocess.run(
            [str(self.bin / "bioheaders"), command, "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        printed = " ".join(completed.stdout.split())
        if " ".join(phrase.split()) not in printed:
            fail(
                f"{phrase!r} is not in `bioheaders {command} --help`: this document "
                "quotes words the tool stopped printing"
            )

    def run(
        self,
        probe_id,
        argv,
        expect_exit,
        expect_stderr=None,
        expect_stdout=None,
        check=None,
    ):
        if probe_id in self.results:
            fail(f"duplicate probe id {probe_id}")
        parts = [str(part).format(tmp=self.tmp) for part in argv]
        completed = subprocess.run(
            parts, capture_output=True, text=True, cwd=str(ROOT), check=False
        )
        problem = None
        if completed.returncode != expect_exit:
            problem = (
                f"probe {probe_id}: expected exit {expect_exit}, got "
                f"{completed.returncode}: "
                f"{(completed.stderr or completed.stdout)[:220]}"
            )
        elif expect_stderr is not None and expect_stderr not in completed.stderr:
            problem = (
                f"probe {probe_id}: exit {expect_exit} but stderr is not "
                f"{expect_stderr!r}: {completed.stderr[:220]!r}"
            )
        elif expect_stdout is not None and expect_stdout not in completed.stdout:
            problem = (
                f"probe {probe_id}: stdout is not {expect_stdout!r}: "
                f"{completed.stdout[:220]!r}"
            )
        elif check is not None:
            problem = check(completed)
        if problem is not None:
            self.results[probe_id] = {"id": probe_id, "problem": problem}
            fail(problem)
        self.results[probe_id] = {
            "id": probe_id,
            "argv": parts,
            "display": self.display(parts),
            "exit": completed.returncode,
            "expect": expect_exit,
        }

    def display(self, argv):
        """The command as published text: no machine paths, no random temp dir.

        The document must render byte-identically wherever it is generated, so an
        absolute path is never quoted: the temporary directory becomes ``<tmp>``
        (which still shows the argument was written by the run), and the
        repository root and the interpreter directory disappear.
        """
        text = " ".join(argv[1:])
        text = text.replace(str(self.tmp), "<tmp>")
        text = text.replace(str(ROOT) + "/", "")
        text = text.replace(str(self.bin) + "/", "")
        return "bioheaders " + text

    def have(self, probe_id):
        return probe_id in self.results


def carrier_check(path, kind):
    """A check() that combine really wrote a file-bound header of its own kind.

    The warrant is the checksum line, because a header without one is not
    file-bound: it is the thing `combine` exists to compute.
    """
    prefix = {"fasta": b";~", "gfa": b"#~", "gff3": b"#~"}[kind]

    def check(result):
        data = Path(path).read_bytes()
        if prefix + b"checksum:" not in data:
            return f"{Path(path).name} carries no {kind.upper()} checksum line"
        if kind == "gff3" and not data.startswith(b"##gff-version 3"):
            return f"{Path(path).name} lost the GFF3 version line (docs/FHGFF3.md G1)"
        return None

    return check


def written_document(path, needle):
    """A check() that the document convert wrote names the family it claims.

    Text, not parsed JSON: the same warrant has to hold for a YAML writer, and the
    claim being tested is only that the file cites its own family's contract.
    """

    def check(result):
        written = Path(path).read_text(encoding="utf-8")
        if needle not in written:
            return f"{Path(path).name} does not cite {needle!r}: " f"{written[:120]!r}"
        return None

    return check


def report_check(directory, header_type=None, bare_document=False):
    """A check() for an ``assess`` JSON report."""

    def check(result):
        reports = list(Path(directory).glob("*.assessment.json"))
        if len(reports) != 1:
            return f"assess wrote {len(reports)} reports into {Path(directory).name}"
        report = read_json(reports[0])
        conformance = report.get("conformance")
        if bare_document:
            if conformance is not None:
                return f"a metadata document was scored as a header: {conformance}"
            if report["input"]["header_lines_read"] != 0:
                return (
                    "a metadata document reported header lines: "
                    + json.dumps(report["input"])[:160]
                )
            if report["input"]["format"] != "unknown-text":
                return "expected unknown-text, got " + repr(report["input"]["format"])
            return None
        if not conformance or conformance.get("header_type") != header_type:
            return f"no {header_type} conformance section: {conformance}"
        if conformance.get("result") != "valid":
            return f"{header_type} conformance result is {conformance.get('result')!r}"
        return None

    return check


def bgzf_check(path):
    def check(result):
        data = Path(path).read_bytes()
        if data[:4] != b"\x1f\x8b\x08\x04":
            return f"{Path(path).name} is not BGZF (magic {data[:4].hex()})"
        return None

    return check


def bytes_equal(made, other):
    """A check() that two files this render produced are the same bytes.

    Used for the claim that compression is transparent: stripping a gzip member
    must give what stripping the plain carrier gives, and neither is the original
    file, because the point of `strip` is to remove the header block.
    """

    def check(result):
        left = Path(made).read_bytes()
        right = Path(other).read_bytes()
        if left != right:
            return (
                f"{Path(made).name} is not {Path(other).name}: "
                f"{len(left)} bytes against {len(right)}"
            )
        return None

    return check


def index_check(fai_path, fasta_path):
    """A check() that recomputes every ``.fai`` field from the file bytes."""

    def check(result):
        expected = fai_rows(fasta_path)
        actual = []
        for line in Path(fai_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            if len(fields) < 5:
                return f"{Path(fai_path).name} has a short row: {fields}"
            actual.append(
                (
                    fields[0],
                    int(fields[1]),
                    int(fields[2]),
                    int(fields[3]),
                    int(fields[4]),
                )
            )
        if actual != expected:
            return (
                f"{Path(fai_path).name} disagrees with an independent scan: "
                f"faidx {actual} scan {expected}"
            )
        return None

    return check


class Renderer:
    """Holds every derived input and writes the document from it."""

    def __init__(self, probes):
        self.probes = probes
        self.axes = package_axes()
        self.bundled = read_json(BUNDLED_PATH)
        self.pins = read_json(PINS_PATH)
        self.tag = self.bundled["current"]["release"]
        self.suite = suite_dir()
        self.clone = self.suite.parent
        self.clone_commit = assert_at_tag(self.clone, self.tag)
        self.registry = read_json(self.clone / "schemas" / "versions.json")
        self.contract_files = {}
        for name in self.released_types():
            path = self.clone / f"{name.lower()}.json"
            if not path.is_file():
                fail(
                    f"released contract {name} is not at the root of tag "
                    f"{self.tag} ({path}); this repository's path assumption broke"
                )
            self.contract_files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        # The 404 control: the contracts are not under schemas/ at that tag, and
        # an agent that assumed otherwise would point every URL in the family at
        # a path that does not exist.
        wrong = self.suite.parent / "schemas" / "fhp.json"
        if wrong.is_file():
            fail(
                f"{wrong} exists at tag {self.tag}: the released-contract path "
                "moved and every reference to it needs re-checking"
            )
        self.vendored = self.vendored_manifests()
        self.ledger = self.suite_ledger()
        self.draft = draft_lane(self.axes)
        self.reasons = self.reason_texts()
        self.used = []
        self.evidence = {}

    # --- inputs ---

    def vendored_manifests(self):
        runners = {
            "fhp-fasta": "tests/fhp_test.py::test_conformance_vector",
            "fhgff3": "tests/fhgff3_test.py::test_conformance_vector",
            "jsonld": "tests/jsonld_test.py::test_conformance_vectors",
        }
        table = {}
        for format_name, relative, parity in (
            (
                "fhp-fasta",
                "tests/fixtures/fhp/manifest.json",
                "tests/fhp_test.py::test_fixtures_match_the_specification",
            ),
            (
                "fhgff3",
                "tests/fixtures/fhgff3/manifest.json",
                "tests/fhgff3_test.py::test_fixtures_match_the_specification",
            ),
            (
                "jsonld",
                "tests/fixtures/jsonld/manifest.json",
                "tests/jsonld_test.py::test_vectors_match_the_specification",
            ),
        ):
            manifest = read_json(ROOT / relative)
            kinds = {vector["format"] for vector in manifest["vectors"]}
            if kinds != {format_name}:
                fail(f"{relative} mixes formats {sorted(kinds)}")
            if not test_exists(parity):
                fail(f"{relative} is no longer guarded by {parity}")
            table[format_name] = {
                "count": len(manifest["vectors"]),
                "runner": runners[format_name],
                "parity": parity,
            }
        return table

    def suite_ledger(self):
        path = self.suite / "manifest.json"
        manifest = read_json(path)
        formats = {}
        for vector in manifest["vectors"]:
            row = formats.setdefault(
                vector["format"],
                {"total": 0, "valid": 0, "invalid": 0, "gzip": 0, "bgzf": 0},
            )
            row["total"] += 1
            row[vector["expected"]] += 1
            if vector.get("compressed"):
                row[vector["compression"]] += 1
        for format_name, row in formats.items():
            entry = self.vendored.get(format_name, {})
            row["run_by_id"] = entry.get("count", 0)
            row["runner"] = entry.get("runner")
            row["parity"] = entry.get("parity")
        return {
            "tag": self.tag,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "total": len(manifest["vectors"]),
            "formats": formats,
        }

    def pin(self, needle):
        for row in self.pins["references"]:
            if needle in (row.get("id") or ""):
                return row
        fail(f"no pins.json row naming {needle!r}: a scope statement lost its source")

    def pin_for(self, local, tag):
        for row in self.pins["references"]:
            if (row.get("local") or "").endswith(Path(local).name) and (
                row.get("revision") == tag
            ):
                return row
        return None

    # --- probes ---

    def control_release(self, type_name):
        """The oldest release whose schemaVersion is a string, or None.

        The negative control for the version table asks that release for the
        current contract version, so it must be a release that compares versions
        the same way: the FHR 1 contract takes the *number* 1, and asking it for a
        string would prove only the type check.
        """
        registry = self.registry["releases"]
        releases = sorted(tag for tag in registry if type_name in registry[tag])
        literal = [tag for tag in releases if isinstance(registry[tag][type_name], str)]
        if len(literal) < 2:
            return None
        newest = registry[self.registry["current"]][type_name]
        return literal[0] if newest != registry[literal[0]][type_name] else None

    def run_version_probes(self, cli):
        """Select every vendored release by citation, then try to break it twice.

        A row in the version table is only worth printing if asking the wrong
        release for the newest contract fails, and asking for a release that was
        never vendored is refused (rule V4). Both controls run here.
        """
        probes = self.probes
        registry = self.registry["releases"]
        current = self.registry["current"]
        for type_name, document in SOURCE_DOCUMENT.items():
            record = read_json(ROOT / document)
            releases = sorted(tag for tag in registry if type_name in registry[tag])
            for tag in releases:
                cited = dict(
                    record,
                    schema=f"https://w3id.org/fair-bioheaders/"
                    f"{type_name.lower()}/{tag}",
                    schemaVersion=registry[tag][type_name],
                )
                path = probes.out(f"version-{type_name}-{tag}.json")
                Path(path).write_text(json.dumps(cited), encoding="utf-8")
                probes.run(
                    f"version-{type_name}-{tag}",
                    [cli, "validate", path],
                    0,
                    expect_stdout=f"{type_name} metadata is valid.",
                )
            newest = registry[current][type_name]
            control = self.control_release(type_name)
            if control is not None:
                wrong = dict(
                    record,
                    schema=f"https://w3id.org/fair-bioheaders/"
                    f"{type_name.lower()}/{control}",
                    schemaVersion=newest,
                )
                path = probes.out(f"version-control-{type_name}.json")
                Path(path).write_text(json.dumps(wrong), encoding="utf-8")
                probes.run(
                    f"version-control-{type_name}",
                    [cli, "validate", path],
                    1,
                    expect_stderr="is not one of",
                )
            absent = dict(
                record,
                schema=f"https://w3id.org/fair-bioheaders/"
                f"{type_name.lower()}/v9.9.9",
                schemaVersion=newest,
            )
            path = probes.out(f"version-absent-{type_name}.json")
            Path(path).write_text(json.dumps(absent), encoding="utf-8")
            probes.run(
                f"version-absent-{type_name}",
                [cli, "validate", path],
                1,
                expect_stderr="unsupported schema version",
            )

    def run_probes(self):
        probes = self.probes
        cli = str(probes.bin / "bioheaders")
        for kind, where, phrase in QUOTED:
            if kind == "source":
                probes.confirm_in_source(phrase, where)
            else:
                probes.confirm_in_help(phrase, where)
        for type_name, table in FIXTURES.items():
            for serialization, relative in table.items():
                probes.run(
                    f"read-{type_name}-{serialization}",
                    [cli, "validate", probes.source(relative)],
                    0,
                    expect_stdout=f"{type_name} metadata is valid.",
                )
        self.run_version_probes(cli)
        for type_name in FIXTURES:
            for serialization in DOCUMENTS:
                relative = FIXTURES[type_name].get(serialization)
                if relative is not None:
                    # A document that type has no form of cannot be fed to a
                    # carrier-only command: the refusal is probed where the pair
                    # exists, and the grid says "no binding" where it does not.
                    for operation, command in (
                        ("verify", "verify"),
                        ("strip", "strip"),
                        ("links", "verify-links"),
                    ):
                        probes.run(
                            f"{operation}-doc-{type_name}-{serialization}",
                            [cli, command, probes.source(relative)],
                            1,
                            expect_stderr=DOCUMENT_GATE,
                        )
            # A metadata document carries no file-bound block for assess to score.
            probes.run(
                f"assess-doc-{type_name}",
                [
                    cli,
                    "assess",
                    probes.source(SOURCE_DOCUMENT[type_name]),
                    "--format",
                    "json",
                    "--output",
                    probes.out(f"assessdoc-{type_name}"),
                ],
                0,
                check=report_check(
                    probes.tmp / f"assessdoc-{type_name}", bare_document=True
                ),
            )
        for (type_name, serialization), (phrase, where) in REFUSALS.items():
            probes.run(
                f"refuse-{type_name}-{serialization}",
                [
                    cli,
                    "convert",
                    probes.source(SOURCE_DOCUMENT[type_name]),
                    probes.out(
                        f"refuse-{type_name}-{serialization}."
                        + suffix_of(serialization)
                    ),
                ],
                1,
                expect_stderr=phrase,
            )
        probes.run(
            "refuse-FHP-export",
            [
                cli,
                "convert",
                "--jsonld-profile",
                "export",
                probes.source(SOURCE_DOCUMENT["FHP"]),
                probes.out("export.fhp.jsonld"),
            ],
            1,
            expect_stderr="the schema.org export profile is not available for FHP",
        )
        for type_name, table in FIXTURES.items():
            carrier = [item for item in CARRIERS if item in table][0]
            for serialization in ("jsonld", "microdata"):
                if serialization in table:
                    probes.run(
                        f"write-{type_name}-{serialization}",
                        [
                            cli,
                            "convert",
                            probes.source(SOURCE_DOCUMENT[type_name]),
                            probes.out(
                                f"write-{type_name}-{serialization}."
                                + suffix_of(serialization)
                            ),
                        ],
                        0,
                    )
            for serialization in ("json", "yaml"):
                target = probes.out(f"meta-{type_name}.{suffix_of(serialization)}")
                probes.run(
                    f"write-{type_name}-{serialization}",
                    [cli, "convert", probes.source(table[carrier]), target],
                    0,
                    check=written_document(target, type_name.lower()),
                )
            for serialization in CARRIERS:
                if serialization not in table:
                    continue
                source = probes.source(table[serialization])
                probes.run(
                    f"verify-{type_name}-{serialization}",
                    [cli, "verify", source],
                    0,
                    expect_stdout="Checksum verified.",
                )
                probes.run(
                    f"strip-{type_name}-{serialization}",
                    [
                        cli,
                        "strip",
                        source,
                        probes.out(
                            f"strip-{type_name}-{serialization}."
                            + suffix_of(serialization)
                        ),
                    ],
                    0,
                )
                # combine is the operation that makes a header file-bound: the body
                # it signs is the one the vendored carrier holds once stripped, so
                # the bytes under the checksum are known-good sequence. The stripped
                # file keeps a real extension, because combine infers the kind from
                # it exactly as a user's command line would.
                body = probes.out(
                    f"strip-{type_name}-{serialization}." + suffix_of(serialization)
                )
                written_carrier = probes.out(
                    f"write-{type_name}-{serialization}.{suffix_of(serialization)}"
                )
                probes.run(
                    f"write-{type_name}-{serialization}",
                    [
                        cli,
                        "combine",
                        probes.source(SOURCE_DOCUMENT[type_name]),
                        body,
                        "-o",
                        written_carrier,
                    ],
                    0,
                    check=carrier_check(written_carrier, serialization),
                )
                probes.run(
                    f"roundtrip-{type_name}-{serialization}",
                    [cli, "verify", written_carrier],
                    0,
                    expect_stdout="Checksum verified.",
                )
                probes.run(
                    f"links-{type_name}-{serialization}",
                    [cli, "verify-links", source],
                    0,
                )
                probes.run(
                    f"assess-{type_name}-{serialization}",
                    [
                        cli,
                        "assess",
                        source,
                        "--format",
                        "json",
                        "--output",
                        probes.out(f"assess-{type_name}-{serialization}"),
                    ],
                    0,
                    check=report_check(
                        probes.tmp / f"assess-{type_name}-{serialization}",
                        header_type=type_name,
                    ),
                )
                # The name keeps the carrier extension under the compression one:
                # the format comes from the file name, the compression from magic
                # bytes, and a bare ".gz" is not a format the CLI claims.
                gzip_source = probes.tmp / (
                    f"gzip-{type_name}-{serialization}.{suffix_of(serialization)}.gz"
                )
                gzip_source.write_bytes(
                    gzip.compress((ROOT / table[serialization]).read_bytes())
                )
                probes.run(
                    f"gzip-read-{type_name}-{serialization}",
                    [cli, "verify", str(gzip_source)],
                    0,
                    expect_stdout="Checksum verified.",
                )
                plain = probes.out(f"plain-{type_name}-{serialization}")
                probes.run(
                    f"gzip-strip-{type_name}-{serialization}",
                    [cli, "strip", str(gzip_source), plain],
                    0,
                    check=bytes_equal(
                        plain,
                        probes.out(
                            f"strip-{type_name}-{serialization}."
                            + suffix_of(serialization)
                        ),
                    ),
                )
                written = probes.out(
                    f"written-{type_name}-{serialization}."
                    f"{suffix_of(serialization)}.gz"
                )
                probes.run(
                    f"gzip-write-{type_name}-{serialization}",
                    [
                        cli,
                        "convert",
                        probes.source(SOURCE_DOCUMENT[type_name]),
                        written,
                    ],
                    0,
                    check=bgzf_check(written),
                )
        for serialization in ("jsonld", "microdata"):
            relative = FIXTURES["FHR"][serialization]
            gzipped = probes.tmp / f"docgz-FHR.{suffix_of(serialization)}.gz"
            gzipped.write_bytes(gzip.compress((ROOT / relative).read_bytes()))
            probes.run(
                f"gzip-read-FHR-{serialization}",
                [cli, "validate", str(gzipped)],
                0,
                expect_stdout="FHR metadata is valid.",
            )
        for type_name in ("FHR", "FHP"):
            fasta = probes.source(FIXTURES[type_name]["fasta"])
            fai = probes.out(f"index-{type_name}.fai")
            probes.run(
                f"index-{type_name}",
                [cli, "faidx", fasta, "-o", fai],
                0,
                check=index_check(fai, fasta),
            )
        for serialization in SERIALIZATIONS:
            if serialization == "fasta":
                continue
            type_name = "FHGFF3" if serialization == "gff3" else "FHR"
            relative = FIXTURES[type_name].get(serialization)
            if relative is None:
                continue
            probes.run(
                f"index-reject-{serialization}",
                [
                    cli,
                    "faidx",
                    probes.source(relative),
                    "-o",
                    probes.out(f"index-reject-{serialization}.fai"),
                ],
                1,
            )

    # --- the grid ---

    def cells(self):
        table = {}
        for type_name in self.released_types():
            for operation, _ in OPERATIONS:
                for serialization in SERIALIZATIONS:
                    table[(type_name, operation, serialization)] = self.released_cell(
                        type_name, operation, serialization
                    )
        for type_name in self.draft_types():
            for operation, _ in OPERATIONS:
                for serialization in SERIALIZATIONS:
                    table[(type_name, operation, serialization)] = self.draft_cell(
                        type_name, operation, serialization
                    )
        for type_name in self.unheld_types():
            row = self.pin("fhgm")
            for operation, _ in OPERATIONS:
                for serialization in SERIALIZATIONS:
                    table[(type_name, operation, serialization)] = (
                        "none",
                        [("pin", row["id"])],
                        "fhgm-scope",
                    )
        return table

    def released_types(self):
        """The released families, in the order the registry lists them.

        ``bundled.json`` is read as written, so the grid order - genome, protein,
        annotation - is the registry's own and not a preference of this file.
        """
        return tuple(self.bundled["current"]["files"])

    def draft_types(self):
        return tuple(sorted(self.bundled.get("drafts", {})))

    def unheld_types(self):
        """Header families a pin row names that nothing in this artifact vendors."""
        held = set(self.released_types()) | set(self.draft_types())
        return tuple(name for name in families_in_pins(self.pins) if name not in held)

    def released_cell(self, type_name, operation, serialization):
        probes = self.probes
        carrier = serialization in CARRIERS
        if not carrier and serialization not in FIXTURES[type_name]:
            # The type has no form in that serialization at all, so every
            # operation on the pair is refused rather than merely unrun.
            probe = f"refuse-{type_name}-{serialization}"
            if not probes.have(probe):
                fail(f"{type_name} x {serialization}: no fixture, no refusal probe")
            evidence = [("probe", probe)]
            declared = source_limit(type_name, serialization)
            if declared is not None:
                evidence.append(("source", declared))
            return "no", evidence, "no-binding"
        if carrier:
            refused = f"refuse-{type_name}-{serialization}"
            admitted = gate_allows(self.axes, serialization, type_name)
            if probes.have(refused):
                if admitted:
                    fail(
                        f"{type_name} x {serialization}: convert refuses it while "
                        "validate_header_family admits it"
                    )
                return "no", [("probe", refused)], "family-gate"
            if not admitted:
                fail(
                    f"{type_name} x {serialization}: the gate refuses it and no "
                    "refusal probe is declared"
                )
        if operation == "read":
            if serialization not in FIXTURES[type_name]:
                probe = f"refuse-{type_name}-{serialization}"
                if not probes.have(probe):
                    fail(
                        f"no read path and no refusal probe for "
                        f"{type_name} x {serialization}"
                    )
                evidence = [("probe", probe)]
                declared = source_limit(type_name, serialization)
                if declared is not None:
                    evidence.append(("source", declared))
                reason = "no-binding" if declared else "family-gate"
                return "no", evidence, reason
            probe = f"read-{type_name}-{serialization}"
            return (
                "yes",
                [("probe", probe)],
                (
                    "microdata-experimental"
                    if serialization == "microdata"
                    and type_name == "FHGFF3"
                    and self.axes["microdata_experimental"]
                    else None
                ),
            )
        if operation == "write":
            probe = f"write-{type_name}-{serialization}"
            if probes.have(probe):
                reason = None
                if serialization in DOCUMENTS:
                    reason = "document-carries-no-checksum"
                if serialization == "microdata" and type_name == "FHGFF3":
                    reason = "microdata-experimental"
                return "yes", [("probe", probe)], reason
            refused = f"refuse-{type_name}-{serialization}"
            if probes.have(refused):
                evidence = [("probe", refused)]
                declared = source_limit(type_name, serialization)
                if declared is not None:
                    evidence.append(("source", declared))
                    return "no", evidence, "no-binding"
                return "no", evidence, "family-gate"
            fail(f"no write probe and no refusal for {type_name} x {serialization}")
        if operation in ("verify", "strip", "links"):
            probe = f"{operation}-{type_name}-{serialization}"
            if serialization in CARRIERS and probes.have(probe):
                reason = "links-verdicts" if operation == "links" else None
                if operation == "verify" and serialization == "gff3":
                    reason = "verify-directives"
                return "yes", [("probe", probe)], reason
            doc = f"{operation}-doc-{type_name}-{serialization}"
            if not probes.have(doc):
                fail(f"no refusal probe {doc} to warrant the n/a")
            return "na", [("probe", doc)], "no-checksum-in-document"
        if operation == "assess":
            probe = f"assess-{type_name}-{serialization}"
            if probes.have(probe):
                return "yes", [("probe", probe)], None
            return "na", [("probe", f"assess-doc-{type_name}")], "assess-documents"
        if operation == "index":
            if serialization == "fasta":
                probe = f"index-{type_name}"
                if probes.have(probe):
                    reason = "index-samtools-fhr-only" if type_name == "FHP" else None
                    return ("partial" if reason else "yes"), [("probe", probe)], reason
                return "unverified", [], "index-no-evidence"
            return (
                "no",
                [("probe", f"index-reject-{serialization}")],
                "index-fasta-only",
            )
        fail(f"unknown operation {operation}")

    def draft_cell(self, type_name, operation, serialization):
        """FHT cells. None of them may read as a claim about the type's status."""
        tests = "tests/fht_test.py"
        if serialization in CARRIERS:
            if not gate_allows(self.axes, serialization, type_name, draft=True):
                return (
                    "no",
                    [("test", f"{tests}::test_family_table_opens_only_fasta")],
                    "draft-carrier",
                )
            if operation == "assess":
                return (
                    "no",
                    [("test", f"{tests}::test_validate_and_assess_stay_draft_aware")],
                    "draft-assess",
                )
            if operation == "index":
                return "unverified", [], "index-no-evidence"
            return (
                "draft",
                [
                    ("test", DRAFT_FASTA_TESTS[operation]),
                    ("opt-in", "tests/fht_conformance_test.py::test_vector_validity"),
                ],
                "draft-lane",
            )
        if operation in ("read", "write"):
            if serialization == "yaml":
                return (
                    "draft",
                    [("test", f"{tests}::test_strip_and_convert")],
                    "draft-lane-document",
                )
            if serialization in ("jsonld", "microdata"):
                return (
                    "no",
                    [
                        (
                            "test",
                            f"{tests}::test_unbound_forms_are_refused_not_stretched",
                        )
                    ],
                    "draft-no-binding",
                )
            return "unverified", [], "draft-no-file-evidence"
        if operation in ("verify", "strip", "links"):
            # The gate is about the serialization, not the family: the command
            # refuses every metadata document, draft records included. The probe
            # is the released one because the draft lane is never exercised by a
            # probe in this render.
            return (
                "na",
                [("probe", f"{operation}-doc-FHR-{serialization}")],
                "no-checksum-in-document",
            )
        if operation == "assess":
            return "na", [("probe", "assess-doc-FHR")], "assess-documents"
        return "no", [("probe", f"index-reject-{serialization}")], "index-fasta-only"

    # --- reasons ---

    def reason_texts(self):
        draft = self.draft
        fhgm = self.pin("fhgm")
        return {
            "family-gate": (
                "refused by `validate_header_family` in `bioheaders/cli.py`, which "
                "admits each sequence serialization to named header families only. "
                "The probe asked `convert`, and the gate's own words are quoted in "
                "the probe list, so this is the rule, not a summary of it"
            ),
            "no-binding": (
                "no reviewed binding for that pair is published, and the writer "
                "refuses instead of borrowing another type's identity"
            ),
            "document-carries-no-checksum": (
                "written from a carrier; a bare metadata document has no sequence "
                "bytes for the checksum to cover, so it is metadata, not a file-bound "
                "header"
            ),
            "no-checksum-in-document": (
                "the file-bound SHA-512/256 covers a header block plus body bytes. A "
                "metadata document has no body, so the command names the input "
                "formats it takes and stops: a vacuous pass would be worse than an "
                "`n/a`. The probe shows the refusal, and the gate is about the "
                "serialization, not the type"
            ),
            "links-verdicts": (
                "exit 0 with nothing recorded is `not checked`, which is not a match: "
                "the command never invents or recomputes a parent checksum. Vectors "
                "that do record parents are scored by name in the shared suite"
            ),
            "verify-directives": (
                "for an annotation header the command also cross-checks the GFF3 "
                "directives against the header block, which no other carrier has"
            ),
            "assess-documents": (
                "`assess` scores the header block of a *data* file. Given a bare "
                "metadata document it reports `unknown-text`, reads 0 header lines "
                "and publishes no conformance section; the probe asserts exactly "
                "that, so its exit status 0 is not read as an assessment"
            ),
            "index-fasta-only": (
                "`faidx` parses FASTA. Anything else fails as a format error, which "
                "is the honest outcome: an index of bytes samtools cannot read is "
                "worse than no index"
            ),
            "index-samtools-fhr-only": (
                "every `.fai` field was recomputed from the file bytes during this "
                "render and matched, but the samtools and pysam byte comparisons in "
                "`tests/faidx_test.py` are written for the genome header only"
            ),
            "index-no-evidence": (
                "neither measured nor refused: no probe and no test covers it, so no "
                "mark is invented"
            ),
            "draft-lane": (
                f"reached only with `{draft['env']}` set, against "
                f"`{Path(draft['file']).name}` pinned at commit "
                f"`{draft['revision'][:12]}…` (sha256 `{draft['sha256'][:12]}…`). A "
                "lane over pinned development bytes is a preview: it is not a claim "
                "about the type's status, and the default run does not take it"
            ),
            "draft-lane-document": (
                "the lane carries the header between a FASTA carrier and YAML: "
                "`convert` writes it, `combine` reads it back and re-verifies. The "
                "carrier still holds the checksum, so the document is metadata only"
            ),
            "draft-carrier": (
                "the draft contract is FASTA-only, and the gate keeps GFA for the "
                "genome header and GFF3 for the annotation header: the gate was "
                "asked with the opt-in set, and said no"
            ),
            "draft-no-binding": (
                "the lane refuses rather than stretching a published identity over "
                "development bytes: no binding for that pair has been reviewed"
            ),
            "draft-assess": (
                "`assess` reads the citation and reports its conformance section as "
                "`not_assessed`: the rubric follows the released contracts, and the "
                "lane deliberately leaves that alone"
            ),
            "draft-no-file-evidence": (
                "no file-level probe or test covers the draft lane here, so the cell "
                "stays unearned rather than being closed by analogy with FASTA"
            ),
            "microdata-experimental": (
                "the binding itself is still open upstream (`EXPERIMENTAL = True` in "
                "`bioheaders/fhgff3_microdata.py`, which warns on every read and "
                "write, pending FHGFF3#16): implemented and measured here, not a "
                "published serialization"
            ),
            "fhgm-scope": (
                f"nothing in this artifact names the model draft: no vendored draft "
                f"contract, and no base or carrier pin of its own, which "
                f"`bioheaders-pin-audit` reports as `{fhgm['id']}` / `ABSENT` with "
                f"the reason recorded in `bioheaders/pins.json`. A scope statement, "
                f"not a hole this document fills: the lane is "
                f"FAIR-bioHeaders-Tools#135, and the cell is unrun rather than run "
                f"and unrecorded"
            ),
        }

    # --- rendering ---

    def ref(self, item):
        """Register one evidence item and return its footnote key."""
        if item not in self.evidence:
            self.evidence[item] = len(self.evidence) + 1
        return f"[^e{self.evidence[item]}]"

    def grid(self, table):
        lines = []
        push = lines.append
        names = self.released_types() + self.draft_types() + self.unheld_types()
        registry = self.registry["releases"][self.registry["current"]]
        push("## The grids")
        push("")
        for type_name in names:
            if type_name in self.released_types():
                push(
                    f"### {type_name} — contract `'{registry[type_name]}'` at "
                    f"{self.registry['current']}"
                )
                push("")
            elif type_name in self.draft_types():
                self.draft_headline(type_name, push)
            else:
                self.unheld_headline(type_name, push)
            push(
                "| operation \\\\ serialization | " + " | ".join(SERIALIZATIONS) + " |"
            )
            push("| --- |" + " --- |" * len(SERIALIZATIONS))
            for operation, _ in OPERATIONS:
                cells = []
                for serialization in SERIALIZATIONS:
                    mark, evidence, reason = table[
                        (type_name, operation, serialization)
                    ]
                    text = MARKS[mark]
                    if reason is not None:
                        if reason not in self.used:
                            self.used.append(reason)
                        text += f"[^r-{reason}]"
                    for item in evidence:
                        text += self.ref(item)
                    cells.append(f"`{text}`")
                push(f"| {operation} | " + " | ".join(cells) + " |")
            push("")
            if type_name in self.released_types():
                copies = "; ".join(
                    f"{tag} → `{Path(self.bundled['releases'][tag][type_name]).name}`"
                    for tag in sorted(self.bundled["releases"])
                    if type_name in self.bundled["releases"][tag]
                )
                push(f"Vendored contract copies (`schemas/bundled.json`): {copies}.")
                push("")
        return lines

    def draft_headline(self, type_name, push):
        draft = self.draft
        push(f"### {type_name} — draft lane only, opt-in, no claim of any kind")
        push("")
        push(
            f"`{draft['env']}` opens it; nothing else does. The lane reads "
            f"`{Path(draft['file']).name}`, pinned at commit "
            f"`{draft['revision']}` (sha256 `{draft['sha256']}` of those bytes), "
            f"citation `{draft['citation']}`. It has no entry in the version "
            "registry, no alias URL and no version of its own to name, and every "
            "read under the opt-in prints that provenance. Its suite is pinned "
            f"apart from it: commit `{draft['suite_revision']}`, sha256 "
            f"`{draft['suite_sha256']}`, {draft['suite_vectors']} vectors."
        )
        push("")
        push(
            "So a `draft lane` mark below says: with the opt-in set, on a checkout "
            "of this branch, that path ran and printed its provenance. It never "
            "says anything about status, and neither does `no`: those cells are "
            "gates that were asked."
        )
        push("")

    def unheld_headline(self, type_name, push):
        row = self.pin("fhgm")
        push(f"### {type_name} — this artifact holds no reference to it")
        push("")
        push(
            f"`bioheaders/pins.json` row `{row['id']}`, class `{row['class']}`, "
            f"label `{row.get('label')}`, is what says so; the audit prints it as "
            f"`ABSENT`. The whole grid is one value because the whole of this "
            f"repository is silent about the model draft, and that silence is a "
            f"decision with a source, not an oversight. See the scope statements "
            f"below the tables."
        )
        push("")

    def commands_section(self):
        lines = []
        push = lines.append
        scripts = entry_points()
        names = {item.name for item in self.axes["subcommands"]}
        aliases = sorted(
            alias for item in self.axes["subcommands"] for alias in item.aliases
        )
        compat = sorted(name for name in scripts if name.startswith("fhr-"))
        push("## Commands, and the operations they carry")
        push("")
        push("| console script | entry point | what it is |")
        push("| --- | --- | --- |")
        for name in sorted(scripts):
            if name == "bioheaders":
                what = f"the umbrella command: {len(names)} subcommands"
            elif name.startswith("fhr-"):
                what = (
                    "public compatibility name; frozen, and mirrored by the "
                    "`fhr` distribution built from `compat/fhr`"
                )
            else:
                what = (
                    "advisory cross-repo pin audit; reports, writes nothing, "
                    "and takes no part in the grids above"
                )
            push(f"| `{name}` | `{scripts[name]}` | {what} |")
        push("")
        push(
            f"{len(scripts)} installed commands: `bioheaders`, {len(compat)} "
            f"`fhr-*` compatibility names, and the audit. Their subcommands are "
            f"`{'`, `'.join(sorted(names))}` with alias `{'`, `'.join(aliases)}`. "
            "Every `fhr-*` name shares an implementation with its `bioheaders` "
            "subcommand, which is why the grids above are per operation rather "
            "than per command; `tests/bioheaders_test.py` pins that the two sets "
            "stay equal."
        )
        push("")
        return lines

    def version_section(self):
        lines = []
        push = lines.append
        bundled = self.bundled
        registry = self.registry["releases"]
        push("## The version dimension")
        push("")
        push("Rules V1 to V6 of `docs/SCHEMA-VERSIONS.md` decide which copy a record")
        push("gets: the record's own `schema` citation selects it, and a release with")
        push("no vendored copy is refused rather than checked against a contract it")
        push("does not name. Every row below was selected by running `validate` on a")
        push("record citing that release while this file was rendered.")
        push("")
        push("| type | release | contract version | copy here | provenance |")
        push("| --- | --- | --- | --- | --- |")
        for type_name in self.released_types():
            for tag in sorted(bundled["releases"]):
                if type_name not in bundled["releases"][tag]:
                    continue
                local = bundled["releases"][tag][type_name]
                row = self.pin_for(local, tag)
                version = registry[tag][type_name]
                # The registry stores the FHR 1 contract as the JSON number 1 and
                # every later one as a string, and a record has to match that: it
                # is worth showing rather than smoothing over.
                shown = f"`'{version}'`" if isinstance(version, str) else f"`{version}`"
                push(
                    f"| {type_name} | `{tag}` | {shown} | "
                    f"`{Path(local).name}` | "
                    f"{('`' + row['id'] + '` FRESH at the tag') if row else 'no pin row'} |"
                )
        push("")
        push("The FHR rows at `v0.3.0` and `v0.3.1` carry the contract version as a")
        push("number, which is the shape rule V6 exists for: a raw-main citation with")
        push("`schemaVersion` the number 1 is read as FHR 1, with a deprecation")
        push("warning, and")
        push("`tests/fhr1_compat_test.py::test_combine_verify_and_strip_keep_fhr_1`")
        push("carries that record through `combine`, `verify` and `strip` rather than")
        push("only checking the selection. The probe `version-FHR-v0.3.1` selected the")
        push("same copy through a `w3id` citation.")
        push(f"`current` is `{bundled['current']['release']}`, and the registry was")
        push("read from the specification at that tag - the same place the contract")
        push("digests below came from. Released material is named by a tag, never by")
        push("a branch (#241 rule 1): `schemas/versions.json` on `main` is a different")
        push("document and is not cited here.")
        push("")
        push("Contract digests at the tag, as this render measured them:")
        push("")
        for type_name, digest in sorted(self.contract_files.items()):
            push(f"- `{type_name.lower()}.json` at `{self.tag}`: sha256 `{digest}`")
        push("")
        push("Those files sit at the repository **root**. `schemas/fhp.json` does not")
        push("exist at that tag, and this render checks that it does not: a matrix")
        push("that quietly switched to a `schemas/` path would be quoting bytes no")
        push("URL resolves to. `schemas/` holds `core.yaml`, `shared.yaml` and")
        push("`versions.json` there.")
        push("")
        push("Controls, so the table cannot be vacuous:")
        push("")
        for type_name in SOURCE_DOCUMENT:
            newest = registry[self.registry["current"]][type_name]
            control = self.control_release(type_name)
            if control is not None:
                push(
                    f"- `{type_name}` asking for `'{newest}'` through the "
                    f"`{control}` citation is refused by the contract that release "
                    f"actually holds: probe `version-control-{type_name}`"
                )
            push(
                f"- `{type_name}` citing `v9.9.9` is refused as a version this tool "
                f"has no copy for (rule V4): probe `version-absent-{type_name}`"
            )
        push("")
        return lines

    def suite_section(self):
        lines = []
        push = lines.append
        ledger = self.ledger
        push("## The shared suite, and what this artifact runs of it")
        push("")
        push(f"Acceptance for a released type is the {ledger['total']} vectors of the")
        push(f"specification's shared suite at tag `{ledger['tag']}` (sha256")
        push(f"`{ledger['sha256'][:16]}…`). Whether a vector can run at all is a")
        push("property of the consumer, not of the suite, so the two ledgers that get")
        push("read as one are kept apart below: vectors executed **by id** by this")
        push("repository's own `pytest` run, and vectors executed **against the")
        push("installed commands** by the specification's own checker.")
        push("")
        push(
            "| format | vectors at the tag | valid / invalid | gzip / BGZF | by id here | "
            "the test that runs them by id |"
        )
        push("| --- | --- | --- | --- | --- | --- |")
        by_id = 0
        for format_name in sorted(ledger["formats"]):
            row = ledger["formats"][format_name]
            by_id += row["run_by_id"]
            runner = (
                row["runner"]
                or "none vendored: this repository holds no "
                "filtered manifest of this format"
            )
            push(
                f"| `{format_name}` | {row['total']} | {row['valid']} / "
                f"{row['invalid']} | {row['gzip']} / {row['bgzf']} | "
                f"{row['run_by_id'] or '—'} | {runner} |"
            )
        push(f"| **total** | **{ledger['total']}** | | | **{by_id}** | |")
        push("")
        push(f"That is the measured shape: {by_id} of {ledger['total']} vectors run")
        push("by id here, and the whole suite passes against the installed commands")
        push("(measurement below). Both numbers are narrower than they look, and")
        push("three things follow, none of which a grid can show by itself:")
        push("")
        push("- A vector scores reading, validating and the checksum of a valid file.")
        push("  It never exercises `strip` byte equality, `links`, `assess` or")
        push("  `index`, which is why those rows cite probes written for them.")
        push(
            f"- `{ledger['formats']['fasta']['total']}` `fasta` and "
            f"{ledger['formats']['gfa']['total']} `gfa` vectors and "
            f"{ledger['formats']['microdata']['total']} `microdata` vectors are not "
            "vendored by id here at all. The first two are the genome-header paths "
            "this toolkit has carried longest and tests directly "
            "(`tests/fhr_test.py`, `tests/streaming_test.py`, "
            "`tests/compression_test.py`); `microdata` is measured by "
            "`tests/fhgff3_microdata_test.py`, `tests/microdata_shared_test.py` and "
            "the FHP microdata tests. The equality of the three vendored manifests "
            "with the tag is itself a test: "
            + ", ".join(
                f"`{entry['parity']}`"
                for entry in sorted(self.vendored.values(), key=lambda e: e["parity"])
            )
            + "."
        )
        push("- 228 and 63 are the federation's other numbers, and they belong to the")
        push("  four per-language libraries, not to this artifact. Those libraries")
        push(
            "  implement no JSON-LD and no microdata reader, so they declare "
            f"{ledger['formats']['jsonld']['total']} `jsonld` plus "
            f"{ledger['formats']['microdata']['total']} `microdata` vectors - "
            "228 executed, 63 not-run out of the same 291. This toolkit has both"
        )
        push("  readers, so 63 is a statement about *their* scope. Reading 228 there")
        push("  against 291 here as a regression would be exactly the mistake this")
        push("  section exists to prevent; per-format executability is a property of")
        push("  the consumer.")
        push("")
        push("### Measurements rendering cannot re-run")
        push("")
        for label, text in MEASUREMENTS:
            push(f"- **{label}** — {text}")
        push("")
        return lines

    def compression_section(self):
        lines = []
        push = lines.append
        suffixes = " or ".join(f"`{item}`" for item in self.axes["compressed_suffixes"])
        push("## Compression and streaming")
        push("")
        push("Input compression is detected from the gzip magic bytes, not from the")
        push(
            "extension, over single-member gzip, multi-member gzip and BGZF. Output to"
        )
        push(f"a path ending {suffixes} is BGZF, which `gunzip` reads. A checksum")
        push("always covers the decompressed bytes, which is why the same header and")
        push("body produce one checksum plain or compressed.")
        push("")
        push("| type | carrier | read compressed | written | evidence |")
        push("| --- | --- | --- | --- | --- |")
        for type_name in self.released_types():
            for serialization in CARRIERS:
                if serialization not in FIXTURES[type_name]:
                    continue
                format_name = VECTORS_FOR[(type_name, serialization)]
                row = self.ledger["formats"][format_name]
                by_id = (
                    f"{row['run_by_id']} of them run by id here"
                    if row["run_by_id"]
                    else "not vendored by id here: see the suite ledger"
                )
                push(
                    f"| {type_name} | `{serialization}` | single-member gzip, "
                    f"multi-member gzip and BGZF | BGZF on a "
                    f"`{suffix_of(serialization)}.gz` path | "
                    f"`gzip-read-{type_name}-{serialization}`, "
                    f"`gzip-strip-{type_name}-{serialization}`, "
                    f"`gzip-write-{type_name}-{serialization}`; the suite holds "
                    f"{row['gzip']} gzip and {row['bgzf']} BGZF vectors of format "
                    f"`{format_name}`, {by_id} |"
                )
        for serialization in ("jsonld", "microdata"):
            push(
                f"| FHR | `{serialization}` | a gzip member reads (probe "
                f"`gzip-read-FHR-{serialization}`) | `convert` to `.gz` writes BGZF "
                f"| the shared suite has no compressed vector of this format, so "
                f"this row is a probe and nothing more |"
            )
        push(
            "| any | stdin / stdout | yes: magic bytes on a pipe | yes | "
            "`tests/compression_test.py::test_stdin_and_stdout`, "
            "`tests/streaming_test.py` |"
        )
        push(
            "| FHR | BGZF `.gzi` | — | yes | `tests/faidx_test.py` (needs samtools "
            "and bgzip installed, so it is opt-in and skips without them) |"
        )
        push("")
        return lines

    def draft_section(self):
        lines = []
        push = lines.append
        draft = self.draft
        push("## The draft lane is opt-in and is never a claim")
        push("")
        push(f"`{draft['env']}` is read by `bioheaders/selection.py`. Unset - the")
        push("default, and what every installed command does today - a record citing")
        push("the draft's raw URL is rule V5: read as a genome header, with a")
        push("near-miss warning saying so. Set, the citation selects pinned")
        push("development bytes and every read prints their provenance, which since")
        push("#165 carries the commit and the SHA-256 of exactly those bytes:")
        push("")
        push("```text")
        push(f"citation  {draft['citation']}")
        push(f"commit    {draft['revision']}")
        push(f"sha256    {draft['sha256']}")
        push(
            f"suite     {draft['suite_revision']} (sha256 {draft['suite_sha256']}, "
            f"{draft['suite_vectors']} vectors)"
        )
        push(f"contract  {draft['source']}")
        push("```")
        push("")
        push("That block is provenance about bytes at a commit. It is not a release,")
        push("and no cell above uses it as one. The lane is also not a licence to")
        push("relax anything else: the released contracts stay at the tag named in the")
        push("header, and `tests/fht_test.py` asserts that with the gate open the")
        push("released families behave exactly as they do with it shut.")
        push("")
        return lines

    def scope_section(self):
        lines = []
        push = lines.append
        row = self.pin("fhgm")
        push("## Scope statements")
        push("")
        push(
            f"- **FHGM: no reference here, on purpose.** `{row['id']}`, class "
            f"`{row['class']}`, label `{row.get('label')}`, is printed as `ABSENT` "
            f"by the audit, and `bioheaders/pins.json` records why: "
            f"{row.get('no_pin_detail') or row.get('note')}"
        )
        filtered = [
            entry["id"]
            for entry in self.pins["references"]
            if "filtered" in (entry.get("id") or "")
        ]
        if filtered:
            push(
                f"- **{'` and `'.join(filtered)} are `ABSENT` by construction.** "
                f"This repository vendors a *filtered* per-format copy of the shared "
                f"manifest, so no single upstream file digest describes it; equality "
                f"with the tag is enforced fixture by fixture by the parity tests "
                f"named in the suite ledger above. Reporting them as absent is the "
                f"audit refusing to call a different byte string fresh."
            )
        push("- **`assess` is not a metadata-document reader.** It reports")
        push("  `unknown-text` for a bare JSON or YAML document and publishes no")
        push("  conformance section, so those cells say `n/a` instead of banking an")
        push("  exit status 0.")
        if self.axes["microdata_experimental"]:
            push("- **The annotation header's microdata binding is still open")
            push("  upstream.** `bioheaders/fhgff3_microdata.py` sets `EXPERIMENTAL")
            push("  = True` and warns on every read and write, pending FHGFF3#16.")
            push("  The `yes` in those cells means implemented and measured here; it")
            push("  is not a published serialization, which is a different claim from")
            push("  the draft-contract ones above and is kept separate.")
        push("- **JSON-LD for the protein header is canonical only.** The export")
        push("  profile is refused by name (probe `refuse-FHP-export`), and the CLI")
        push("  marks both facts provisional in its own help text.")
        push("")
        return lines

    def appendix(self, table):
        lines = []
        push = lines.append
        push("## Probes run for this render")
        push("")
        push("| probe | command | expected | observed |")
        push("| --- | --- | --- | --- |")
        for record in sorted(self.probes.results.values(), key=lambda item: item["id"]):
            push(
                f"| `{record['id']}` | `{record['display']}` | {record['expect']} | "
                f"{record['exit']} |"
            )
        push("")
        push(f"{len(self.probes.results)} probes. Any one of them disagreeing with")
        push("the expectation recorded in the generator aborts the render before it")
        push("writes a byte, which is the same rule `--check` runs under.")
        push("")
        push("## Evidence index")
        push("")
        push("| evidence | warranted |")
        push("| --- | --- |")
        for (kind, name), number in sorted(
            self.evidence.items(), key=lambda item: item[1]
        ):
            where = self.cells_citing(table, (kind, name))
            push(f"| {kind} `{name}` | {where} |")
        push("")
        push("Each test above was re-found as a `def` in the file it names, in this")
        push("run. Each probe is in the table immediately above, with the command and")
        push("both exit statuses.")
        push("")
        return lines

    def cells_citing(self, table, item):
        hits = sorted(
            f"{type_name}/{operation}/{serialization}"
            for (type_name, operation, serialization), (_, evidence, _) in table.items()
            if item in evidence
        )
        if not hits:
            return "—"
        shown = ", ".join(hits[:3])
        if len(hits) > 3:
            shown += f" (+{len(hits) - 3} more)"
        return shown

    def footnotes(self, table):
        lines = []
        push = lines.append
        push("## Reasons, in full")
        push("")
        for reason in self.used:
            push(f"[^r-{reason}]: {self.reasons.get(reason)}")
        push("")
        push("## Evidence, in full")
        push("")
        for (kind, name), number in sorted(
            self.evidence.items(), key=lambda item: item[1]
        ):
            if kind == "probe":
                record = self.probes.results[name]
                push(
                    f"[^e{number}]: probe `{name}` — `{record['display']}`, "
                    f"expected exit {record['expect']}, observed {record['exit']}"
                )
            elif kind == "test":
                push(
                    f"[^e{number}]: `{name}` — re-found in the tree while rendering; "
                    f"`poetry run pytest` runs it"
                )
            elif kind == "opt-in":
                push(
                    f"[^e{number}]: `{name}` — re-found in the tree, and it is *not* "
                    f"part of a default run: it consumes the draft lane's suite and so "
                    f"skips unless "
                    f"`BIOHEADERS_EXPERIMENTAL_FHT` is set and a pinned "
                    f"FHT-Specification checkout is given. That is why the lane is "
                    f"described as opt-in rather than counted as coverage"
                )
            elif kind == "source":
                push(
                    f"[^e{number}]: `{name}` — this phrase was required to appear in "
                    f"the package (in the file named, or in the help text quoted) "
                    f"while rendering; a refusal is only evidence in the tool's own "
                    f"words"
                )
            else:
                push(
                    f"[^e{number}]: `bioheaders/pins.json` row `{name}` — printed "
                    f"`ABSENT` by `bioheaders-pin-audit`"
                )
        push("")
        return lines

    def not_verified_section(self):
        lines = []
        push = lines.append
        push("## Not verified")
        push("")
        for item, why in NOT_VERIFIED:
            push(f"- {item} — {why}")
        push("")
        return lines

    def header(self):
        registry = self.registry
        current = registry["releases"][registry["current"]]
        lines = []
        push = lines.append
        push("# Capability matrix")
        push("")
        push("What this toolkit does, per header type, per operation, per")
        push("serialization, at the contract versions it can name. Generated from the")
        push("code, the vendored registries and commands run during the render.")
        push("")
        push("```text")
        push("generator  scripts/render_capability_matrix.py")
        push("check      python scripts/render_capability_matrix.py --check")
        push("           (.github/workflows/capability-matrix.yml runs it)")
        push(f"toolkit    fair-bioheaders {self.axes['version']} (this checkout; the")
        push("           number is the package version, and main runs ahead of the")
        push("           release that carries it - check the newest tag)")
        push(
            f"baseline   FAIR-bioHeaders-Specification {registry['current']}: "
            + ", ".join(f"{name} '{current[name]}'" for name in self.released_types())
        )
        push(
            f"authority  tag {self.tag} is commit {self.clone_commit}, and the "
            f"checkout it was read from is at that commit: released bytes are named "
            f"by a tag, never by a branch"
        )
        push(f"suite      {self.ledger['total']} vectors at {self.ledger['tag']}")
        push(
            f"types      {len(self.released_types())} with a released contract, "
            f"{len(self.draft_types())} development only, "
            f"{len(self.unheld_types())} not referenced here"
        )
        push("```")
        push("")
        push("The environment is deliberately not in this file: the same commit must")
        push("render byte-identically on both interpreters `pytest.yaml` tests, and an")
        push("interpreter version is not part of a capability claim.")
        push("")
        push("## How to read a cell")
        push("")
        push("| mark | meaning |")
        push("| --- | --- |")
        push("| `yes` | the command does it, and the cited probe or test measured it |")
        push(
            "| `no` | a rule in the package refuses it, or it was never implemented: |"
        )
        push("|      | a refusal with a named reason is a decision, not a gap |")
        push("| `n/a` | the dimension does not apply to the pair, and the footnote |")
        push("|      | names who owns it |")
        push(f"| `draft lane` | reached only with `{self.draft['env']}` set, over |")
        push("|      | pinned development bytes; see the draft section |")
        push("| `partial` | it runs, but part of the operation's own contract is |")
        push("|      | unevidenced here, and the footnote says which part |")
        push("| `not here` | this artifact holds no reference to the type at all |")
        push(
            "| `not verified` | neither earned nor refused; listed under Not verified |"
        )
        push("")
        push("Each mark can carry two kinds of footnote: an `r-…` one is a reason, an")
        push("`e`-numbered one is evidence, and both are written out in full at the")
        push("end of the file. The grids are per *operation*: `read` and `write` both")
        push("involve `convert`, `verify` is `bioheaders verify` and the")
        push("`fhr-*-validate` names, and so on. The command table is next.")
        push("")
        return lines

    def check_marks(self, table):
        """No unreleased family may carry a mark that reads as a capability claim.

        The vocabulary gate cannot see a table: a ``yes`` in an FHT or FHGM cell
        would be made of the word ``yes`` and the family name in a different column
        of the same line, which is exactly the case here. So the marks are checked
        as data, against the axes that named them, before the document exists.
        """
        unreleased = set(self.draft_types()) | set(self.unheld_types())
        problems = []
        for (type_name, operation, serialization), (mark, _, _) in table.items():
            if type_name in unreleased and mark in ("yes", "partial"):
                problems.append(
                    f"{type_name}/{operation}/{serialization} is marked {mark!r} "
                    "while the family has no released contract here"
                )
        if problems:
            fail("rule V7: " + "; ".join(problems))

    def document(self, table):
        """Render the whole file. Idempotent: the footnote registers are reset,
        so the same renderer can be asked for a second document (the test suite
        does exactly that, to prove the check can fail)."""
        self.used = []
        self.evidence = {}
        self.check_marks(table)
        parts = []
        parts.append(self.header())
        parts.append(self.grid(table))
        parts.append(self.commands_section())
        parts.append(self.version_section())
        parts.append(self.suite_section())
        parts.append(self.compression_section())
        parts.append(self.draft_section())
        parts.append(self.scope_section())
        parts.append(self.not_verified_section())
        parts.append(self.appendix(table))
        parts.append(self.footnotes(table))
        lines = [line for part in parts for line in part]
        digest = hashlib.sha256(
            "\n".join(
                f"{key[0]}/{key[1]}/{key[2]}={value[0]}"
                for key, value in sorted(table.items())
            ).encode("utf-8")
        ).hexdigest()[:32]
        types = (
            len(self.released_types())
            + len(self.draft_types())
            + len(self.unheld_types())
        )
        lines.append(
            f"Digest of the grid: `{digest}` ({len(table)} cells = "
            f"{types} types x {len(OPERATIONS)} operations x "
            f"{len(SERIALIZATIONS)} serializations)."
        )
        lines.append("")
        return "\n".join(lines)

    def check_v7(self, text):
        return check_v7(text)


DRAFT_FASTA_TESTS = {
    "read": "tests/fht_test.py::test_validate_and_assess_stay_draft_aware",
    "write": "tests/fht_test.py::test_strip_and_convert",
    "verify": "tests/fht_test.py::test_verify_cli_accepts_and_rejects",
    "strip": "tests/fht_test.py::test_strip_and_convert",
    "links": "tests/fht_test.py::test_verify_links_three_verdicts",
}


def draft_lane(axes):
    entry = axes["draft_entry"]
    if not entry:
        fail("schemas/bundled.json has no drafts.FHT entry")
    suite = entry.get("suite") or {}
    for key in ("citation", "revision", "sha256", "file", "source"):
        if not entry.get(key):
            fail(f"drafts.FHT has no {key}")
    for key in ("revision", "sha256", "fhtFastaVectors"):
        if not suite.get(key):
            fail(f"drafts.FHT.suite has no {key}")
    if entry.get("status") != "draft":
        fail("drafts.FHT is not labelled draft")
    return {
        "citation": entry["citation"],
        "revision": entry["revision"],
        "sha256": entry["sha256"],
        "file": entry["file"],
        "source": entry["source"],
        "env": axes["draft_env"],
        "suite_revision": suite["revision"],
        "suite_sha256": suite["sha256"],
        "suite_vectors": suite["fhtFastaVectors"],
    }


def test_exists(reference):
    """A cited ``path::name`` must still name a function in that file."""
    path, _, name = reference.partition("::")
    file = ROOT / path
    if not file.is_file():
        return False
    return f"def {name.split('[')[0]}(" in file.read_text(encoding="utf-8")


def check_citations(table):
    missing = sorted(
        {
            name
            for (_, _, _), (_, evidence, _) in table.items()
            for kind, name in evidence
            if kind in ("test", "opt-in") and not test_exists(name)
        }
    )
    if missing:
        fail("cited tests are not in the tree any more: " + ", ".join(missing))


TEST_CITATION = re.compile(r"tests/[A-Za-z0-9_]+\.py::[A-Za-z0-9_\[\].\-]+")


def check_prose(text):
    """Every ``tests/file.py::name`` written anywhere in the document must exist.

    Not just the ones the grids cite: a sentence in a table cell or a measurement
    makes the same promise to a reader, and a stale one is exactly the defect this
    whole file exists to prevent.
    """
    stale = sorted(
        {found for found in TEST_CITATION.findall(text) if not test_exists(found)}
    )
    if stale:
        fail("the document cites tests that are not in the tree: " + ", ".join(stale))


def build():
    """Everything: probes run, grid derived, document rendered, checks applied.

    Returns the document with the parts that made it, because ``--self-test`` has
    to render the same document a second time from a deliberately wrong grid. The
    caller closes the probe directory.
    """
    if suite_dir() is None:
        fail(
            "no specification checkout. The suite ledger and the version axis are "
            "read from the release tag, so set FHR_SPECIFICATION (or --suite) to a "
            "checkout of FAIR-bioHeaders-Specification at the release "
            "bioheaders/schemas/bundled.json names, as "
            ".github/workflows/capability-matrix.yml does"
        )
    probes = Probes()
    renderer = Renderer(probes)
    renderer.run_probes()
    table = renderer.cells()
    check_citations(table)
    text = renderer.document(table)
    check_prose(text)
    problems = renderer.check_v7(text)
    if problems:
        probes.close()
        raise SystemExit(
            "capability-matrix: rule V7 violations (a draft family quoted with "
            "release-shaped words and no negation):\n  " + "\n  ".join(problems)
        )
    return text, table, renderer, probes


# The cell the self-test flips. Any earned cell would do; this one is a released
# family in its own serialization with a passing probe behind it, so widening or
# narrowing it is exactly the edit that must not pass unnoticed.
SAMPLE_CELL = ("FHR", "read", "jsonld")


def self_test():
    """Prove the gate can fail, five ways, and leave the tree untouched.

    A documentation check that cannot go red is worse than none, because it buys
    the claim it decorates. Each mutation is the shape of a real mistake: a cell
    changed by hand, a cell dropped, a measured cell replaced by an unearned one,
    a draft given a release-shaped sentence, and a probe expectation moved to suit
    what a command happened to do. The last one is the control on the controls:
    the unmutated second render must reproduce the document exactly.
    """
    text, table, renderer, probes = build()
    problems = []
    try:
        committed = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if committed != text:
            problems.append("the committed file already differs from a fresh render")

        def mutated(change, label):
            candidate = dict(table)
            change(candidate)
            try:
                rendered = renderer.document(candidate)
            except SystemExit:
                # The generator refused to render the claim at all, which is the
                # stronger of the two good outcomes.
                return
            if rendered == text:
                problems.append(f"{label} left the document byte-identical")

        def flip(cells):
            current = cells[SAMPLE_CELL]
            if current[0] == "na":
                problems.append("the sample cell is already n/a: the flip is vacuous")
            cells[SAMPLE_CELL] = ("na", current[1], current[2])

        mutated(flip, "re-marking FHR/read/jsonld as n/a")
        mutated(
            lambda cells: cells.update(
                {("FHR", "index", "fasta"): ("unverified", [], "index-no-evidence")}
            ),
            "replacing the measured index cell with an unearned one",
        )
        mutated(
            lambda cells: cells.update(
                {("FHGM", "read", "json"): ("yes", [("probe", "read-FHR-json")], None)}
            ),
            "granting FHGM a yes it has no reference for",
        )
        # A whole row gone: the operation stays in the code but leaves the matrix.
        # This is the shape of "we stopped documenting a command", which a
        # human-edited table would survive silently forever.
        saved = OPERATIONS
        try:
            globals()["OPERATIONS"] = saved[:-1]
            dropped = {
                key: value for key, value in table.items() if key[1] != saved[-1][0]
            }
            if renderer.document(dropped) == text:
                problems.append(
                    f"dropping the {saved[-1][0]!r} row left the document unchanged"
                )
        finally:
            globals()["OPERATIONS"] = saved
        if renderer.document(dict(table)) != text:
            problems.append("an unmutated second render did not reproduce the file")

        widened = text.replace(
            "### FHT \u2014 draft lane only, opt-in, no claim of any kind",
            "### FHT \u2014 a released contract, supported",
        )
        if widened == text:
            problems.append("the draft heading moved: the rule V7 control needs work")
        elif not renderer.check_v7(widened):
            problems.append("check_v7 let 'FHT is a released contract' through")
        if renderer.check_v7(text):
            problems.append("check_v7 flags the document it just approved")

        caught = False
        try:
            probes.run(
                "self-test-lie",
                [str(probes.bin / "bioheaders"), "--version"],
                1,
                expect_stderr="no such option",
            )
        except SystemExit:
            caught = True
        probes.results.pop("self-test-lie", None)
        if not caught:
            problems.append(
                "a probe that expected the wrong exit status did not fail: the "
                "harness is a rubber stamp"
            )
    finally:
        probes.results.pop("self-test-lie", None)
        probes.close()
    for line in problems:
        print("capability-matrix: self-test FAILED: " + line, file=sys.stderr)
    if problems:
        return 1
    print(
        f"capability-matrix: self-test passed: {len(probes.results)} probes, "
        f"{len(table)} cells, and all six deliberate failures were caught: a "
        f"measured cell re-marked, a measured cell replaced by an unearned one, a "
        f"yes granted to a family with no reference here, a row dropped from the "
        f"grids, a draft given a release-shaped sentence, and a probe expecting the "
        f"wrong exit status. The committed file is current."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless the committed file matches this render",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="prove the check fails on deliberate wrong cells, a dropped row, a "
        "widened draft claim and a false probe expectation",
    )
    parser.add_argument(
        "--suite",
        type=Path,
        help="a checkout of FAIR-bioHeaders-Specification at the release tag; the "
        "default is $FHR_SPECIFICATION, then a sibling of this repository",
    )
    args = parser.parse_args()
    if args.suite:
        os.environ["CAPABILITY_SPEC"] = str(args.suite)
    if args.self_test:
        return self_test()
    text, table, renderer, probes = build()
    probes.close()
    if args.check:
        if not TARGET.is_file():
            print(
                "docs/CAPABILITY-MATRIX.md does not exist: run "
                "`python scripts/render_capability_matrix.py`",
                file=sys.stderr,
            )
            return 1
        committed = TARGET.read_text(encoding="utf-8")
        if committed != text:
            print(
                f"docs/CAPABILITY-MATRIX.md is stale: the committed file has "
                f"{len(committed.splitlines())} lines, this render produced "
                f"{len(text.splitlines())} ({len(table)} cells, "
                f"{len(probes.results)} probes). Regenerate it and read the diff: "
                f"the grids come from the code and from commands, so a difference "
                f"means behaviour moved or a claim did",
                file=sys.stderr,
            )
            return 1
        print(
            f"docs/CAPABILITY-MATRIX.md matches this render: {len(table)} cells, "
            f"{len(probes.results)} probes, all expectations met"
        )
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(
        f"wrote {TARGET.relative_to(ROOT)}: {len(table)} cells, "
        f"{len(probes.results)} probes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
