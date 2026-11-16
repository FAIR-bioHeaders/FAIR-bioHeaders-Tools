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
cell may show opt-in draft evidence, an operation refusal, or diagnostic observed
behavior; it never claims released capability.

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
import ast
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
    "observed": "observed only",
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
        "external samtools and pysam interoperability during rendering",
        "the native faidx tests cover FHR and FHP, plain and BGZF. Rendering "
        "checks those citations and recomputes index fields, but does not run "
        "the external tools; the native CI workflow installs them",
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
        "rendering uses one interpreter. The native pytest workflow covers both; "
        "the separate shared-conformance job uses Python 3.13 and requires all "
        "six formats. No interpreter-specific skipped-test count is inferred here",
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


def verify_tag_inputs(root, tag):
    """Read a clean release checkout, never silently label main as a tag."""
    commits = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD", f"{tag}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    values = commits.stdout.splitlines()
    if commits.returncode or len(values) != 2 or values[0] != values[1]:
        fail(f"specification checkout HEAD is not release tag {tag}")
    for relative in (
        "conformance/manifest.json",
        "schemas/versions.json",
        "fhr.json",
        "fhp.json",
        "fhgff3.json",
    ):
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{tag}:{relative}"],
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode or result.stdout != (root / relative).read_bytes():
            fail(f"specification input {relative} differs from tag {tag}")


def suite_dir():
    """The specification's ``conformance/`` directory, from the tag checkout."""
    override = os.environ.get("CAPABILITY_SUITE")
    if override:
        candidate = Path(override)
        return (
            candidate / "conformance"
            if (candidate / "conformance/manifest.json").is_file()
            else candidate
        )
    clone = os.environ.get("FHR_SPECIFICATION")
    if clone and (Path(clone) / "conformance" / "manifest.json").is_file():
        return Path(clone) / "conformance"
    if clone:
        return None
    sibling = ROOT.parent / "FAIR-bioHeaders-Specification"
    if (sibling / "conformance" / "manifest.json").is_file():
        return sibling / "conformance"
    return None


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
    line *without* the terminator and the fifth is that same first line
    *with* it. LF and CRLF widths differ; htslib counts a synthetic LF when
    the first sequence line ends at EOF without a terminator.
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
        line_width = 0
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
                line_width = term - walk + (1 if nxt == -1 else 0)
            walk = term
        rows.append((name, length, start, line_bytes, line_width))
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
        self.env = dict(os.environ)
        self.env.pop("PYTHONPATH", None)
        self.env.pop("BIOHEADERS_EXPERIMENTAL_FHT", None)
        imported = subprocess.run(
            [sys.executable, "-c", "import bioheaders; print(bioheaders.__file__)"],
            cwd=self.tmp,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        installed = Path(imported.stdout.strip())
        if "site-packages" not in installed.parts:
            fail(
                "install this checkout non-editably before rendering; got "
                + str(installed)
            )
        if installed.read_bytes() != (ROOT / "bioheaders/__init__.py").read_bytes():
            fail(
                "installed package differs from this checkout; reinstall before rendering"
            )
        for source in (ROOT / "bioheaders").rglob("*"):
            if not source.is_file() or source.suffix not in (
                ".py",
                ".json",
                ".jsonld",
                ".yaml",
                ".yml",
            ):
                continue
            packaged = installed.parent / source.relative_to(ROOT / "bioheaders")
            if not packaged.is_file() or packaged.read_bytes() != source.read_bytes():
                fail(
                    f"installed package file differs or is missing: {source.relative_to(ROOT)}"
                )

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
            cwd=self.tmp,
            check=False,
            env=self.env,
            timeout=60,
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
            parts,
            capture_output=True,
            text=True,
            cwd=self.tmp,
            check=False,
            env=self.env,
            timeout=60,
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
            "display": (
                (
                    "BIOHEADERS_EXPERIMENTAL_FHT=1 "
                    if self.env.get("BIOHEADERS_EXPERIMENTAL_FHT")
                    else ""
                )
                + self.display(parts)
            ),
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


def carrier_check(path, kind, expected_body):
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
        payload = b"".join(
            line
            for line in data.splitlines(keepends=True)
            if not line.startswith((b";~", b"#~"))
        )
        if payload != Path(expected_body).read_bytes():
            return f"{Path(path).name} changed the supplied payload bytes"
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


def report_check(
    directory, header_type=None, bare_document=False, expected_result="valid"
):
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
        if conformance.get("result") != expected_result:
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
        verify_tag_inputs(self.suite.parent, self.tag)
        self.registry = read_json(self.suite.parent / "schemas" / "versions.json")
        self.contract_files = {}
        for name in sorted(self.bundled["current"]["files"]):
            path = self.suite.parent / f"{name.lower()}.json"
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
                    output = probes.out(
                        f"write-{type_name}-{serialization}." + suffix_of(serialization)
                    )
                    probes.run(
                        f"write-{type_name}-{serialization}",
                        [
                            cli,
                            "convert",
                            probes.source(SOURCE_DOCUMENT[type_name]),
                            output,
                        ],
                        0,
                        check=written_document(output, type_name.lower()),
                    )
                    probes.run(
                        f"readback-{type_name}-{serialization}",
                        [cli, "validate", output],
                        0,
                        expect_stdout=f"{type_name} metadata is valid.",
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
                expected_body = probes.out(f"expected-body-{type_name}-{serialization}")
                Path(expected_body).write_bytes(
                    b"".join(
                        line
                        for line in Path(source).read_bytes().splitlines(keepends=True)
                        if not line.startswith((b";~", b"#~"))
                    )
                )
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
                    check=bytes_equal(
                        probes.out(
                            f"strip-{type_name}-{serialization}."
                            + suffix_of(serialization)
                        ),
                        expected_body,
                    ),
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
                    check=carrier_check(written_carrier, serialization, expected_body),
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

        self.run_cross_carrier_probes(cli)

    def run_cross_carrier_probes(self, cli):
        """Measure commands on unsupported pairings without borrowing convert's gate.

        Synthetic diagnostic inputs are not new conformance fixtures or supported
        bindings. Their checksums are computed by the toolkit. FHT metadata reuses
        the existing native test's literal fixture.
        """
        from bioheaders import fhr
        from bioheaders.cli import checksum

        probes = self.probes
        bodies = {
            "fasta": b">probe\nACGT\n",
            "gfa": b"H\tVN:Z:1.0\nS\tprobe\tACGT\n",
            "gff3": b"##gff-version 3\nprobe\t.\tgene\t1\t4\t.\t+\t.\tID=probe\n",
        }
        pairs = [(name, form) for name, form in REFUSALS if form in CARRIERS]
        pairs += [("FHT", "gfa"), ("FHT", "gff3")]
        for name, form in pairs:
            if name == "FHT":
                tree = ast.parse((ROOT / "tests/fht_test.py").read_text())
                fixture = next(
                    node
                    for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "minimal"
                )
                value = next(
                    node.value for node in fixture.body if isinstance(node, ast.Return)
                )
                record = {
                    ast.literal_eval(key): (
                        self.draft["citation"]
                        if isinstance(item, ast.Name) and item.id == "FHT_URL"
                        else ast.literal_eval(item)
                    )
                    for key, item in zip(value.keys, value.values)
                }
            else:
                record = read_json(ROOT / SOURCE_DOCUMENT[name])
            data = fhr(**record)
            data.checksum = "A" * 43 + "="
            body = bodies[form]

            def carrier():
                header = getattr(data, "output_" + form)().encode()
                if form == "gff3":
                    lead, rest = body.split(b"\n", 1)
                    return lead + b"\n" + header + rest
                return header + body

            data.checksum = checksum(carrier(), form)
            source = probes.out(f"cross-{name}.{suffix_of(form)}")
            Path(source).write_bytes(carrier())
            expected = probes.out(f"cross-body-{name}-{form}")
            Path(expected).write_bytes(body)
            old_env = probes.env
            if name == "FHT":
                probes.env = dict(old_env, **{self.draft["env"]: "1"})
            try:
                prefix = f"cross-{name}-{form}"
                probes.run(
                    prefix + "-read",
                    [cli, "validate", source],
                    0,
                    expect_stdout=f"{name} metadata is valid.",
                )
                target = probes.out(prefix + "-stripped")
                probes.run(
                    prefix + "-strip",
                    [cli, "strip", source, target],
                    0,
                    check=bytes_equal(target, expected),
                )
                probes.run(
                    prefix + "-verify",
                    [cli, "verify", source],
                    1,
                    expect_stderr=f"{name} metadata is incompatible with {form.upper()}",
                )
                probes.run(prefix + "-links", [cli, "verify-links", source], 0)
                output = probes.out(prefix + "-assessment")
                probes.run(
                    prefix + "-assess",
                    [cli, "assess", source, "--format", "json", "--output", output],
                    0,
                    check=report_check(
                        output,
                        header_type=name,
                        expected_result="not_assessed" if name == "FHT" else "valid",
                    ),
                )
                index = probes.out(prefix + ".fai")
                probes.run(
                    prefix + "-index",
                    [cli, "faidx", source, "-o", index],
                    0 if form == "fasta" else 1,
                    check=index_check(index, source) if form == "fasta" else None,
                )
                if name == "FHT":
                    metadata = probes.out(prefix + ".json")
                    Path(metadata).write_text(json.dumps(data.__dict__))
                    probes.run(
                        prefix + "-write",
                        [
                            cli,
                            "convert",
                            metadata,
                            probes.out(prefix + "-output." + suffix_of(form)),
                        ],
                        1,
                        expect_stderr=f"FHT metadata is incompatible with {form.upper()}",
                    )
            finally:
                probes.env = old_env

    def cross_carrier_cell(self, name, operation, form):
        probe = f"cross-{name}-{form}-{operation}"
        if operation == "write" and name != "FHT":
            probe = f"refuse-{name}-{form}"
        if operation in ("write", "verify"):
            return "no", [("probe", probe)], "family-gate"
        if operation == "index" and form != "fasta":
            return "no", [("probe", probe)], "index-fasta-only"
        return "observed", [("probe", probe)], "unbound-operation"

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
            # A missing binding is not proof that every command refuses it.
            probe = f"refuse-{type_name}-{serialization}"
            if not probes.have(probe):
                fail(f"{type_name} x {serialization}: no fixture, no refusal probe")
            if operation == "write":
                evidence = [("probe", probe)]
                declared = source_limit(type_name, serialization)
                if declared is not None:
                    evidence.append(("source", declared))
                return "no", evidence, "no-binding"
            if operation in ("verify", "strip", "links"):
                return (
                    "na",
                    [("probe", f"{operation}-doc-FHR-{serialization}")],
                    "no-checksum-in-document",
                )
            if operation == "assess":
                return "na", [("probe", "assess-doc-FHR")], "assess-documents"
            if operation == "index":
                return (
                    "no",
                    [("probe", f"index-reject-{serialization}")],
                    "index-fasta-only",
                )
            return "unverified", [], "unbound-reader"
        if carrier:
            refused = f"refuse-{type_name}-{serialization}"
            admitted = gate_allows(self.axes, serialization, type_name)
            if probes.have(refused):
                if admitted:
                    fail(
                        f"{type_name} x {serialization}: convert refuses it while "
                        "validate_header_family admits it"
                    )
                return self.cross_carrier_cell(type_name, operation, serialization)
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
                evidence = [("probe", probe)]
                if operation == "links":
                    schema = read_json(
                        ROOT
                        / "bioheaders"
                        / self.bundled["current"]["files"][type_name]
                    )
                    if not {"derivedFrom", "genomeReference"}.intersection(
                        schema["properties"]
                    ):
                        return "na", evidence, "links-no-parent-fields"
                    references = {
                        "FHP": (
                            "tests/fhp_test.py::test_links_matched_and_not_checked",
                            "tests/fhp_test.py::test_links_not_matched",
                        ),
                        "FHGFF3": (
                            "tests/fhgff3_test.py::test_links_matched_and_stale",
                        ),
                    }
                    evidence += [("test", item) for item in references[type_name]]
                reason = "links-verdicts" if operation == "links" else None
                if operation == "verify" and serialization == "gff3":
                    reason = "verify-directives"
                return "yes", evidence, reason
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
                    return (
                        "yes",
                        [
                            ("probe", probe),
                            (
                                "test",
                                "tests/faidx_test.py::test_samtools_regions_on_headed_files_match_the_stripped_file",
                            ),
                            (
                                "test",
                                "tests/faidx_test.py::test_pysam_fetch_on_headed_files_matches_the_stripped_file",
                            ),
                        ],
                        None,
                    )
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
                return self.cross_carrier_cell(type_name, operation, serialization)
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
                    ("test", "tests/fht_conformance_test.py::test_vector_validity"),
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
            return (
                "na",
                [("probe", f"verify-doc-FHR-{serialization}")],
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
            "unbound-reader": (
                "no reader binding or representative input is established for this "
                "pair. The writer's refusal does not establish reader behavior"
            ),
            "unbound-operation": (
                "the command accepts this diagnostic input, but the header-type/carrier "
                "pair has no supported binding. This is observed command behavior only, "
                "not contract support. A permissive strip or metadata reader is not a "
                "writer or verifier: each operation has its own probe"
            ),
            "family-gate": (
                "this operation refuses the header-type/carrier pair through "
                "`validate_header_family` in `bioheaders/cli.py`. Its own CLI probe "
                "records the refusal; other operations have separate probes"
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
                "these render probes supply no parent files, so they do not earn "
                "matched/stale-parent verdicts. The cited native tests exercise those "
                "comparisons. Supplied parent files are rehashed and verified before "
                "comparison with the child's recorded digest; the command does not "
                "invent a recorded parent identity or a SeqCol identifier"
            ),
            "links-no-parent-fields": (
                "the current contract has neither derivedFrom nor genomeReference "
                "parent fields. verify-links accepts the file but reports no parent "
                "files recorded; it makes no parent comparison"
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
                "the binding itself is not adopted or released (`EXPERIMENTAL = True` in "
                "`bioheaders/fhgff3_microdata.py`, which warns on every read and "
                "write; merged FHGFF3#16 recorded canonical documentation only): "
                "implemented and measured here, not a "
                "published serialization"
            ),
            "fhgm-scope": (
                f"this artifact has no model implementation: no vendored draft "
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
                    cells.append(text)
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
            "A `draft lane` mark cites existing native tests of the opt-in path. "
            "Rendering checks those citations but does not execute the draft suite. "
            "It does not claim released support."
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
        push(
            "`export-dcmi` is a separate one-way descriptive assembly projection, "
            "not a whole-header serialization in the grids: complete FHR v0.4.0 "
            "JSON plus mapping-v1 context yields Turtle, a loss/error report and "
            "byte-preserved inputs. It supports no other type/version and performs "
            "no deposit or file-checksum verification. Independent graph and installed "
            "artifact evidence: `tests/dcmi_test.py::test_independently_curated_graph_and_exact_preservation` "
            "and `tests/dcmi_test.py::test_installed_cli_outside_checkout`."
        )
        push("")
        return lines

    def version_section(self):
        lines = [
            "## Bundled contract versions",
            "",
            "Every listed citation is selected by a CLI validation probe.",
            "Wrong-version and unknown-release probes must reject. Pin rows are",
            "recorded provenance, not a live freshness verdict.",
            "",
            "| type | specification tag | schemaVersion | bundled file |",
            "| --- | --- | --- | --- |",
        ]
        for name in self.released_types():
            for tag, files in sorted(self.bundled["releases"].items()):
                if name in files:
                    value = self.registry["releases"][tag][name]
                    lines.append(
                        f"| {name} | `{tag}` | `{value!r}` | `{files[name]}` |"
                    )
        lines += [
            "",
            f"Release inputs are byte-checked against git tag `{self.tag}`.",
            "The generator refuses a modified manifest, registry or root contract.",
            "Released contracts are root files; `schemas/fhp.json` is not the contract path.",
            "",
        ]
        return lines

    def suite_section(self):
        ledger = self.ledger
        lines = [
            "## Shared conformance scope",
            "",
            f"Manifest: `{ledger['tag']}`, {ledger['total']} vectors, SHA-256",
            f"`{ledger['sha256']}`.",
            "",
            "Counts below are read from manifests; rendering does not execute the",
            "normative suite. The CI checker separately runs all six formats against",
            "installed commands and fails if any format is unsupported.",
            "",
            "| format | shared vectors | valid / invalid | gzip / BGZF | vendored by ID here |",
            "| --- | --- | --- | --- | --- |",
        ]
        for name, row in sorted(ledger["formats"].items()):
            lines.append(
                f"| {name} | {row['total']} | {row['valid']} / {row['invalid']} | "
                f"{row['gzip']} / {row['bgzf']} | {row['run_by_id']} |"
            )
        by_id = sum(row["run_by_id"] for row in ledger["formats"].values())
        lines += [
            "",
            f"Vendored by ID: {by_id} of {ledger['total']} vectors (manifest counts, not interpreter-specific test outcomes).",
            "Per-format executability is a property of the consumer.",
            "The toolkit implements JSON-LD and microdata readers. The native",
            "libraries' 228 pass / 63 not-run ledger therefore cannot describe this",
            "consumer. Missing vendored formats are exercised by the shared checker,",
            "alongside existing native regression tests. Manifest parity is checked by:",
        ]
        lines += [f"- `{entry['parity']}`" for entry in self.vendored.values()]
        lines += [
            "",
            "The matrix probes separately exercise strip payload equality, writing,",
            "parent-link handling, assessment and indexing. A successful validation",
            "vector alone does not establish these operations.",
            "",
        ]
        return lines

    def compression_section(self):
        lines = [
            "## Compression by operation",
            "",
            "Checksums cover decompressed exact bytes. Compression is detected from",
            "gzip magic bytes; output to .gz/.bgz uses BGZF. The shared manifest",
            "contains 11 gzip/BGZF vectors, shown by format above.",
            "",
            "| operation | evidence and limits |",
            "| --- | --- |",
            "| read/validate | shared compressed vectors; native compression tests |",
            "| verify | gzip probe per implemented released carrier; shared gzip/BGZF vectors |",
            "| strip | gzip input to plain output per released carrier; payload bytes compared |",
            "| combine | FHR FASTA/GFA input/output: `tests/compression_test.py::test_combine_to_gz_then_validate_and_strip`; other types not verified here |",
            "| convert | JSON metadata to BGZF output per implemented released carrier; magic checked |",
            "| verify-links | compressed input not verified by this generator |",
            "| assess | compressed input not verified by this generator |",
            "| faidx | FHR/FHP plain and BGZF interoperability: `tests/faidx_test.py::test_samtools_regions_on_headed_files_match_the_stripped_file` and `tests/faidx_test.py::test_pysam_fetch_on_headed_files_matches_the_stripped_file`; FHT compressed indexing not verified here |",
            "| FHT draft | declared pinned suite only; rendering does not execute that suite |",
            "",
            "Executed compression probes:",
        ]
        lines += [
            f"- `{name}`" for name in self.probes.results if name.startswith("gzip-")
        ]
        lines += [
            "",
            "FHR gzip JSON-LD and microdata input is probed. Other compressed",
            "metadata-document operations are not verified by this generator.",
            "`tests/compression_test.py::test_stdin_and_stdout` covers pipes for",
            "FHR FASTA/GFA. It does not establish pipe parity for every type.",
            "",
        ]
        return lines

    def draft_section(self):
        lines = []
        push = lines.append
        draft = self.draft
        push("## The draft lane is opt-in and is never a claim")
        push("")
        push(f"`{draft['env']}` is read by `bioheaders/selection.py`. Unset - the")
        push("default - a record citing")
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
        row = self.pin("fhgm")
        audit = self.pin("fht-manifest")
        return [
            "## Scope and existing provenance gaps",
            "",
            "- FHGM model validation is unimplemented in this toolkit (#135). Its",
            f"  audit row `{row['id']}` is absent by declared scope. Parsing an",
            "  FHGFF3 extension does not evaluate FHGM model rules.",
            "- FHT has two different existing suite records. Runtime registry",
            f"  `bundled.json`: `{self.draft['suite_revision']}`,",
            f"  SHA-256 `{self.draft['suite_sha256']}`, {self.draft['suite_vectors']} vectors.",
            f"  Advisory `pins.json` row `{audit['id']}`: `{audit['revision']}`,",
            f"  SHA-256 `{audit['sha256']}`. This matrix follows the runtime",
            "  registry. Neither record is changed; #167 owns the reporting follow-up.",
            "- Filtered fixture manifests are derived subsets, not byte copies of",
            "  the whole shared manifest. Their parity tests are named above.",
            "- `assess` reports bare metadata documents as unknown-text, without",
            "  a header-conformance verdict. Exit zero does not establish assessment.",
            "- FHGFF3 microdata is implemented with an experimental binding warning;",
            "  its status is separate from the released FHGFF3 header contract.",
            "- FHP JSON-LD is canonical only. Its schema.org export profile is refused.",
            "",
        ]

    def appendix(self, table):
        return (
            [
                "## Executed probes",
                "",
                "Each probe must meet its expected exit status and any output/byte checks.",
                "A failed probe aborts before the document is written.",
                "",
                "| probe | command | exit (expected = observed) |",
                "| --- | --- | --- |",
            ]
            + [
                f"| `{r['id']}` | `{r['display']}` | {r['exit']} |"
                for r in sorted(self.probes.results.values(), key=lambda r: r["id"])
            ]
            + [""]
        )

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
                    f"run by `poetry run pytest`"
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
        current = self.registry["releases"][self.registry["current"]]
        return [
            "# Capability matrix",
            "",
            "Generated from package registries, CLI probes and cited native tests.",
            f"Toolkit version: `{self.axes['version']}` in this checkout. Main may run",
            "ahead of the published package with the same version number.",
            f"Released baseline: `{self.tag}`; "
            + ", ".join(f"{name} `{current[name]}`" for name in self.released_types())
            + ".",
            "",
            "Regenerate with `FHR_SPECIFICATION=/path/to/specification-at-tag python",
            "scripts/render_capability_matrix.py`; add `--check --self-test` to verify",
            "drift and deliberate failure controls. CI installs this checkout, checks",
            "the matrix, then executes all six shared-suite formats independently.",
            "",
            "| mark | meaning |",
            "| --- | --- |",
            "| yes | implemented; cited CLI probe or native test |",
            "| no | refused or unimplemented; reason cited |",
            "| n/a | operation does not apply to this representation |",
            "| draft lane | explicit opt-in against pinned development bytes, never released support |",
            "| partial | implemented with a named evidence limit |",
            "| not here | FHGM runtime work remains in #135 |",
            "| not verified | no positive or refusal evidence here |",
            "| observed only | command accepts a diagnostic input with an unsupported binding; not a support claim |",
            "",
            "`read` means validate; `write` covers combine/convert. `verify` checks",
            "file integrity; `links` checks supplied parent identity; `index` is faidx.",
            "The matrix records representative paths, not every option combination.",
            "Evidence footnotes distinguish probes executed during rendering from",
            "tests checked for existence. A cited test is not rerun by rendering.",
            "",
        ]

    def check_marks(self, table):
        check_cells(self, table)

    def document(self, table):
        # Multiple renders must not retain evidence/footnotes from earlier grids.
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
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name.split("[")[0]
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8")))
    )


def check_citations(table):
    missing = sorted(
        {
            name
            for (_, _, _), (_, evidence, _) in table.items()
            for kind, name in evidence
            if kind == "test" and not test_exists(name)
        }
    )
    if missing:
        fail("cited tests are not in the tree any more: " + ", ".join(missing))


def check_cells(renderer, table):
    """Every supported cell needs actual evidence; draft cells cannot claim release."""
    types = renderer.released_types() + renderer.draft_types() + renderer.unheld_types()
    expected = {
        (t, op, form) for t in types for op, _ in OPERATIONS for form in SERIALIZATIONS
    }
    if set(table) != expected:
        fail("missing or unexpected matrix cells")
    for key, (mark, evidence, reason) in table.items():
        if mark not in MARKS or (not evidence and mark != "unverified"):
            fail(f"{key}: blank/invalid mark or missing evidence")
        if reason is not None and reason not in renderer.reasons:
            fail(f"{key}: unknown reason {reason}")
        if key[0] in (
            set(renderer.draft_types()) | set(renderer.unheld_types())
        ) and mark in ("yes", "partial"):
            fail(f"{key}: draft type marked as released capability")
        for kind, name in evidence:
            if kind == "probe" and name not in renderer.probes.results:
                fail(f"{key}: probe {name} never ran")
            if kind not in ("probe", "test", "pin", "source"):
                fail(f"{key}: unknown evidence kind {kind}")
    check_citations(table)


def check_document(actual, expected):
    if actual != expected:
        fail("docs/CAPABILITY-MATRIX.md differs from the measured render")


SAMPLE_CELL = ("FHR", "read", "jsonld")


def self_test(renderer, text, table):
    """Mutate meaningful claims without touching the source or committed document."""
    cases = []
    for newline, width in ((b"\n", 5), (b"\r\n", 6)):
        fasta = renderer.probes.tmp / "short-final-line.fasta"
        fasta.write_bytes(newline.join((b">x", b"AAAA", b"AA", b"")))
        expected = [("x", 6, 2 + len(newline), 4, width)]
        if fai_rows(fasta) != expected:
            fail("index control misreads a short terminal sequence line")
    fasta = renderer.probes.tmp / "unterminated.fasta"
    fasta.write_bytes(b">x\nAAAA")
    if fai_rows(fasta) != [("x", 4, 3, 4, 5)]:
        fail("index control omits htslib's synthetic newline at EOF")
    wrong = dict(table)
    key = ("FHGM", "read", "gff3")
    wrong[key] = ("yes", table[key][1], None)
    cases.append(("draft promoted to released", lambda: check_cells(renderer, wrong)))
    missing = dict(table)
    missing.pop(("FHR", "read", "fasta"))
    cases.append(("missing cell", lambda: check_cells(renderer, missing)))
    uncited = dict(table)
    uncited[("FHR", "read", "fasta")] = ("yes", [], None)
    cases.append(("uncited support", lambda: check_cells(renderer, uncited)))
    invented = dict(table)
    invented[("FHR", "read", "fasta")] = ("yes", [("probe", "fabricated")], None)
    cases.append(("probe never executed", lambda: check_cells(renderer, invented)))
    changed = text.replace("| read | yes", "| read | no", 1)
    if changed == text:
        fail("wrong-cell control changed no bytes")
    cases.append(("wrong rendered cell", lambda: check_document(changed, text)))
    unearned = dict(table)
    unearned[("FHR", "index", "fasta")] = ("unverified", [], "index-no-evidence")
    cases.append(
        (
            "measured cell replaced by an unearned one",
            lambda: check_document(renderer.document(unearned), text),
        )
    )
    dropped = {key: value for key, value in table.items() if key[1] != "index"}
    cases.append(
        ("whole operation row dropped", lambda: check_cells(renderer, dropped))
    )
    cases.append(
        (
            "probe expects the wrong exit status",
            lambda: renderer.probes.run(
                "self-test-lie",
                [str(renderer.probes.bin / "bioheaders"), "--version"],
                1,
            ),
        )
    )
    if not check_v7(
        "### FHT is a released contract and FHGM is officially supported.\n"
    ):
        fail("self-test accepted a release-shaped draft sentence")
    print("self-test caught: release-shaped draft sentence")
    for label, action in cases:
        try:
            action()
        except SystemExit:
            print(f"self-test caught: {label}")
        else:
            fail(f"self-test accepted: {label}")
        finally:
            renderer.probes.results.pop("self-test-lie", None)
    check_document(renderer.document(dict(table)), text)
    total = len(cases) + 1
    print(f"self-test: {total}/{total} deliberate defects rejected")


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


def build(run_self_test=False):
    if suite_dir() is None:
        fail(
            "no specification checkout. The suite ledger and the version axis are "
            "read from the release tag, so set FHR_SPECIFICATION (or --suite) to a "
            "checkout of FAIR-bioHeaders-Specification at the release "
            "bioheaders/schemas/bundled.json names, as "
            ".github/workflows/capability-matrix.yml does"
        )
    probes = Probes()
    try:
        renderer = Renderer(probes)
        renderer.run_probes()
        table = renderer.cells()
        check_cells(renderer, table)
        text = renderer.document(table)
        check_prose(text)
        problems = renderer.check_v7(text)
        if problems:
            raise SystemExit(
                "capability-matrix: rule V7 violations (a draft type quoted with "
                "release-shaped words and no negation):\n  " + "\n  ".join(problems)
            )
        if run_self_test:
            self_test(renderer, text, table)
        return text, table, renderer, probes
    except BaseException:
        probes.close()
        raise


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
        help="prove deliberate matrix, vocabulary and probe defects are rejected",
    )
    parser.add_argument(
        "--suite",
        type=Path,
        help="a specification checkout or conformance directory; the default is "
        "$FHR_SPECIFICATION/conformance",
    )
    args = parser.parse_args()
    if args.suite:
        os.environ["CAPABILITY_SUITE"] = str(args.suite)
    text, table, renderer, probes = build(run_self_test=args.self_test)
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
        try:
            check_document(committed, text)
        except SystemExit:
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
    if args.self_test:
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(
        f"wrote {TARGET.relative_to(ROOT)}: {len(table)} cells, "
        f"{len(probes.results)} probes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
