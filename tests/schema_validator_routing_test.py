# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Guard: the stock ``jsonschema`` validator may not be reached by accident.

``bioheaders.schema_validator`` (added in FAIR-bioHeaders-Tools#189) is the
only place a ``Draft202012Validator`` may be built for header-shaped data: it
reads ``pattern`` as ECMA-262 and ``format: date`` as RFC 3339 ``full-date``,
both of which the stock validator gets wrong. The assessment lane
deliberately still validates its own data and report files with the stock
validator; that exception is recorded below and must not widen silently. A
new module that imports ``Draft202012Validator`` or builds a bare
``FormatChecker()`` fails here, so the tool cannot start contradicting
``bioheaders validate`` by accident again.

The scan parses each module with ``ast``, so an aliased import
(``from jsonschema import Draft202012Validator as V``), an attribute access
(``jsonschema.Draft202012Validator(...)``) and a re-export
(``from bioheaders.schema_validator import Draft202012Validator``) are all
caught; a grep for the constructor call is defeated by every one of them.
Deliberate string obfuscation is out of scope. This test file itself imports
the stock names on purpose — to probe the recorded divergence — and is
therefore outside the scanned tree (``bioheaders/`` only).
"""

import ast
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from bioheaders import schema_validator

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "bioheaders"

# The one module allowed to build the (corrected) validator from stock parts.
SOURCE_MODULE = "schema_validator.py"

# Modules that deliberately still use the stock validator. Decision from the
# FAIR-bioHeaders-Tools#189 review: the assessment lane stays on the stock
# jsonschema validator for now, and the schema_validator module docstring
# names these same two sites. assess/render.py additionally builds a bare
# FormatChecker(), which drops the RFC 3339 full-date tightening; the probe in
# test_stock_date_divergence_is_recorded pins that consequence. Adding a
# module here is a maintainer decision that must be recorded in an issue, and
# an entry may not outlive its use: test_allowlist_entries_are_not_dead fails
# when an allowlisted module stops referencing the stock validator, so a
# routed-away module cannot linger as dead permission.
STOCK_VALIDATOR_ALLOWLIST = (
    "assess/data.py",  # validates the bundled assessment data files
    "assess/render.py",  # validates assessment reports before rendering
)

STOCK_NAMES = ("Draft202012Validator", "FormatChecker")

REMEDIATION = (
    "Build the validator with bioheaders.schema_validator.validator(schema) "
    "(corrected ECMA-262 pattern and RFC 3339 date rules) instead of touching "
    "jsonschema.Draft202012Validator or a bare FormatChecker() directly. If "
    "this site genuinely belongs in the assessment exception, that is a "
    "maintainer decision: record it in an issue, then add the module to "
    "STOCK_VALIDATOR_ALLOWLIST in this test naming the issue. "
    "Refs FAIR-bioHeaders-Tools#189."
)


def _package_modules():
    """Every scanned module, as paths relative to the package directory."""
    return sorted(p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob("*.py"))


def _stock_reference_rows(source, name, imports_only=False):
    """Lines in ``source`` where the stock ``name`` is referenced.

    Counts an ``import``/``from`` of that name (alias included), a star import
    from ``jsonschema`` (which could bind either name), and — unless
    ``imports_only`` — an attribute access such as ``jsonschema.<name>`` or a
    bare name reference. An import of the name from anywhere else, including
    a re-export out of schema_validator, counts too.
    """
    rows = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.name == name or (
                    alias.name == "*"
                    and node.module is not None
                    and node.module.rsplit(".", 1)[-1] == "jsonschema"
                )
                if bound:
                    rows.add(node.lineno)
        elif not imports_only and isinstance(node, (ast.Name, ast.Attribute)):
            identifier = node.id if isinstance(node, ast.Name) else node.attr
            if identifier == name:
                rows.add(node.lineno)
    return sorted(rows)


def _violations(name, allowed):
    """``(module, line)`` for every stock-``name`` reference outside ``allowed``."""
    found = []
    for rel in _package_modules():
        if rel in allowed:
            continue
        rows = _stock_reference_rows((PACKAGE / rel).read_text(), name)
        found.extend((rel, row) for row in rows)
    return found


def _fail(violations, name):
    listing = "\n".join(
        f"  bioheaders/{rel}:{row} references {name}" for rel, row in violations
    )
    pytest.fail(
        f"{len(violations)} un-sanctioned stock-validator reference(s):\n{listing}\n\n{REMEDIATION}"
    )


def test_scanned_paths_exist():
    """A wrong allow-list path must read as failure, not as silence."""
    assert (PACKAGE / SOURCE_MODULE).is_file(), f"{SOURCE_MODULE} is missing"
    for rel in STOCK_VALIDATOR_ALLOWLIST:
        assert (PACKAGE / rel).is_file(), (
            f"allow-listed module bioheaders/{rel} does not exist at this "
            "revision; fix the path or drop the stale entry"
        )


def test_draft_validator_only_in_sanctioned_modules():
    allowed = {SOURCE_MODULE, *STOCK_VALIDATOR_ALLOWLIST}
    violations = _violations("Draft202012Validator", allowed)
    if violations:
        _fail(violations, "Draft202012Validator")


def test_format_checker_only_in_sanctioned_modules():
    allowed = {SOURCE_MODULE, *STOCK_VALIDATOR_ALLOWLIST}
    violations = _violations("FormatChecker", allowed)
    if violations:
        _fail(violations, "FormatChecker")


@pytest.mark.parametrize("rel", STOCK_VALIDATOR_ALLOWLIST)
def test_allowlist_entries_are_not_dead(rel):
    """Every allowlisted module must still import its exception."""
    source = (PACKAGE / rel).read_text()
    if _stock_reference_rows(source, "Draft202012Validator", imports_only=True):
        return
    pytest.fail(
        f"bioheaders/{rel} no longer imports Draft202012Validator, so its "
        "entry in STOCK_VALIDATOR_ALLOWLIST is dead permission: route the "
        "module through schema_validator.validator(schema) in full, remove "
        "the entry from this test, and narrow the exception. "
        "Refs FAIR-bioHeaders-Tools#189."
    )


def test_stock_date_divergence_is_recorded():
    """Pin the exact cost of the assess/render.py FormatChecker() exception.

    The bare FormatChecker() at assess/render.py refuses year-0 dates that
    RFC 3339 full-date admits, while schema_validator.FORMAT_CHECKER accepts
    them. If the two ever agree, the recorded consequence is stale: either
    the jsonschema date check changed or the exception can be removed, and
    this test must fail loudly so both get re-audited.
    """
    schema = {"type": "string", "format": "date"}
    value = "0000-01-01"
    stock_rejects = bool(
        list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
                value
            )
        )
    )
    corrected_accepts = not list(schema_validator.validator(schema).iter_errors(value))
    assert stock_rejects and corrected_accepts, (
        "the stock FormatChecker() and schema_validator.FORMAT_CHECKER no "
        f"longer disagree on {value!r} (stock_rejects={stock_rejects}, "
        f"corrected_accepts={corrected_accepts}): re-audit the assess/render.py "
        "entry in STOCK_VALIDATOR_ALLOWLIST and this recorded divergence. "
        "Refs FAIR-bioHeaders-Tools#189."
    )
