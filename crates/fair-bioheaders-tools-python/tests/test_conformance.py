# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""L2/L3: the pinned corpora through the installed binding, decided against
the specification manifests (never against Rust or Python output)."""

from collections import defaultdict

import pytest
from conftest import load_pinned, write_receipt

OUTSIDE = {"jsonld", "microdata"}
CONTAINERS = {
    "fasta": "fasta",
    "fhp-fasta": "fhp-fasta",
    "gfa": "gfa",
    "fhgff3": "gff3",
}


def number_equal(left, right):
    from decimal import Decimal

    numeric = (int, float, Decimal)
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, numeric) and isinstance(right, numeric):
        return Decimal(str(left)) == Decimal(str(right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            number_equal(left[k], right[k]) for k in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            number_equal(a, b) for a, b in zip(left, right)
        )
    return type(left) is type(right) and left == right


def check(engine, root, vector):
    data = (root / "conformance" / vector["file"]).read_bytes()
    report = engine.verify(data, container=CONTAINERS[vector["format"]])
    if vector["expected"] == "valid":
        if report.outcome != "valid":
            return (
                f"expected valid, got {report.outcome} [{report.first_error()}]",
                report,
            )
        if "checksum" in vector and report.checksum.computed != vector["checksum"]:
            return f"checksum {report.checksum.computed}", report
        for key, value in vector.get("metadata", {}).items():
            if not number_equal(report.metadata.get(key), value):
                return (
                    f"metadata {key}: {report.metadata.get(key)!r} != {value!r}",
                    report,
                )
        for rule in vector.get("warnings", []):
            if not any(d.rule == rule for d in report.warnings()):
                return f"no warning under {rule}", report
        return None, report
    want = "unsupported" if vector.get("result") == "unsupported-version" else "invalid"
    if report.outcome != want:
        return f"expected {want}, got {report.outcome}", report
    return None, report


def run_suite(engine, label, retired=None):
    root, manifest = load_pinned(label)
    if root is None:
        return None
    tally = defaultdict(
        lambda: {
            "total": 0,
            "run": 0,
            "passed": 0,
            "failed": 0,
            "notRun": {},
            "superseded": 0,
        }
    )
    failures, superseded, executed, declared = [], [], [], []
    for vector in manifest["vectors"]:
        fmt = vector["format"]
        t = tally[fmt]
        t["total"] += 1
        if fmt in OUTSIDE:
            reason = f"outside-engine-scope:{fmt}"
            t["notRun"][reason] = t["notRun"].get(reason, 0) + 1
            declared.append(vector["id"])
            continue
        t["run"] += 1
        executed.append(vector["id"])
        problem, report = check(engine, root, vector)
        if problem and retired and vector["id"] in retired:
            expected, rule = retired[vector["id"]]
            first = report.first_error()
            if (
                expected == vector["expected"]
                and rule == "R4"
                and first
                and first.code == "R4.non-canonical-checksum"
            ):
                t["superseded"] += 1
                superseded.append(vector["id"])
                continue
        if problem:
            t["failed"] += 1
            failures.append(f"{vector['id']}: {problem}")
        else:
            t["passed"] += 1
    receipt = write_receipt(
        label,
        dict(tally),
        {
            "failures": failures,
            "supersededByCrosswalk": {"count": len(superseded), "ids": superseded},
        },
    )
    assert len(executed) + len(declared) == len(
        manifest["vectors"]
    ), "two-way accounting"
    assert executed, "zero vectors executed"
    return receipt, failures, superseded


def test_frozen_v060_suite(engine):
    root, crosswalk = load_pinned("C-HIST")
    retired = {c["id"]: (c["expected"], c.get("rule")) for c in crosswalk["cases"]}
    receipt, failures, superseded = run_suite(engine, "C-FROZEN", retired)
    assert not failures, "\n".join(failures)
    totals = receipt["totals"]
    assert totals["run"] == 228 and totals["total"] == 291
    assert totals["passed"] + len(superseded) == 228
    assert len(superseded) <= 30


def test_current_34bbe21a_suite(engine):
    receipt, failures, superseded = run_suite(engine, "C-SOURCE")
    assert not failures, "\n".join(failures)
    assert not superseded
    assert receipt["totals"] == {"total": 319, "run": 254, "passed": 254, "failed": 0}


def test_reader_policy_cases(engine):
    import hashlib

    root, cases = load_pinned("C-POLICY")
    base = root / "conformance" / "reader-policy"
    tally = defaultdict(lambda: {"total": 0, "run": 0, "passed": 0, "failed": 0})
    failures = []
    for case in cases["cases"]:
        t = tally[case["format"]]
        t["total"] += 1
        t["run"] += 1
        data = (base / case["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == case["sha256"], case["id"]
        if case["operation"] == "metadata":
            container = (
                "metadata-json" if case["file"].endswith(".json") else "metadata-yaml"
            )
            report = fht.Engine().validate(data, container=container)
        else:
            report = engine.verify(data, container=CONTAINERS[case["format"]])
        want = {"valid": "valid", "unsupported-version": "unsupported"}.get(
            case["expected"], "invalid"
        )
        if report.outcome == want:
            t["passed"] += 1
        else:
            t["failed"] += 1
            failures.append(f"{case['id']}: expected {want}, got {report.outcome}")
    write_receipt("C-POLICY", dict(tally), {"failures": failures})
    assert not failures, "\n".join(failures)
    assert sum(t["passed"] for t in tally.values()) == 64


import fair_bioheaders_tools as fht  # noqa: E402  (used by the policy test)

pytestmark = pytest.mark.filterwarnings("error")
