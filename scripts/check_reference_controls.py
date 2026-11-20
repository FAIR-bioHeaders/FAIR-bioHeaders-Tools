#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Prove a changed declaration cannot report FRESH; offline, never repins."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from audit_declared_references import ROOT, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker-root", type=Path, required=True)
    parser.add_argument("--checkout", action="append", required=True)
    args = parser.parse_args()
    mappings = args.checkout
    baseline, _ = audit(args.checker_root, mappings)
    selected = next(
        row
        for row in baseline["references"]
        if row["verdict"] == "FRESH" and row["localComparison"] == "performed"
    )
    original = (ROOT / "bioheaders/pins.json").read_bytes()
    table = json.loads(original)
    target = next(row for row in table["references"] if row["id"] == selected["id"])
    old = target["sha256"]
    target["sha256"] = ("0" if old[0] != "0" else "1") + old[1:]
    changed = (json.dumps(table, indent=2) + "\n").encode()
    assert changed != original and target["sha256"] != old
    with tempfile.TemporaryDirectory(prefix="tools-reference-control-") as temp:
        root = Path(temp)
        (root / "bioheaders").mkdir()
        (root / "references").mkdir()
        (root / "bioheaders/pins.json").write_bytes(changed)
        shutil.copytree(ROOT / "tests/fixtures", root / "tests/fixtures")
        (root / "references/checker.json").write_bytes(
            (ROOT / "references/checker.json").read_bytes()
        )
        # Compare genuine existing local bytes without copying a whole checkout.
        for row in table["references"]:
            if row.get("local"):
                source = ROOT / row["local"]
                if source.is_file():
                    dest = root / row["local"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(source.read_bytes())
        mutated, code = audit(args.checker_root, mappings, root=root, strict=True)
        result = next(
            row for row in mutated["references"] if row["id"] == selected["id"]
        )
        assert result["verdict"] == "DRIFT", result
        assert code == 1
        # An unavailable tag commit is an ABSENT declaration, never a current
        # resolver lookup silently substituted into provenance.
        target["sha256"] = old
        target.pop("commit", None)
        (root / "bioheaders/pins.json").write_text(json.dumps(table))
        missing, _ = audit(args.checker_root, mappings, root=root)
        absent = next(
            row for row in missing["references"] if row["id"] == selected["id"]
        )
        assert absent["verdict"] == "ABSENT", absent
    assert (ROOT / "bioheaders/pins.json").read_bytes() == original
    print(
        json.dumps(
            {
                "controls": [
                    "changed recorded digest -> DRIFT",
                    "missing recorded tag commit -> ABSENT",
                ],
                "baseline": {
                    s: sum(r["verdict"] == s for r in baseline["references"])
                    for s in ["FRESH", "DRIFT", "ABSENT", "QUERY_FAILED"]
                },
                "wrote": [],
            }
        )
    )


if __name__ == "__main__":
    main()
