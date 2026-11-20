#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Audit Tools' actual current cross-repository declarations without writing any pin."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = "FAIR-bioHeaders/FAIR-bioHeaders-Tools"
AUTHORITY = "FAIR-bioHeaders/FAIR-bioHeaders-Specification"
RECORD = "bioheaders/pins.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    item = PurePosixPath(value)
    if not value or item.is_absolute() or ".." in item.parts:
        raise ValueError("unsafe declaration path")
    return str(item)


def inventory(root=ROOT):
    raw = (root / RECORD).read_bytes()
    record = json.loads(raw)
    rows = []
    gaps = []
    for pin in record["references"]:
        item = {"path": pin.get("path"), "sha256": pin.get("sha256")}
        if pin.get("local") and not pin.get("relationship"):
            item["local"] = relative(pin["local"])
        row = {
            "id": pin["id"],
            "consumer": CONSUMER,
            "record": RECORD,
            "class": pin["class"],
            "repository": pin["repository"],
            "revision": pin.get("revision"),
            "revisionKind": pin.get("revision_kind"),
            "commit": pin.get("commit")
            or (pin.get("revision") if pin.get("revision_kind") == "commit" else None),
            "files": [item],
        }
        if pin["class"] == "copied-tree":
            row["materialStatus"] = (
                "draft" if pin.get("label", "").startswith("draft") else "released"
            )
            # An absent copied-tree provenance record remains an actual gap;
            # do not fabricate a file-set declaration from today's contents.
            row["files"] = []
        if pin.get("relationship"):
            # The local manifest is a filtered projection, not a byte copy.
            # Native tests retain exact per-fixture and transform evidence.
            item["sha256"] = pin["relationship"].get("source_sha256")
            gaps.append(
                {
                    "id": pin["id"],
                    "disposition": "Upstream manifest audited here; filtered local projection/fixtures remain checked by native pin-audit transform and shared fixture-parity tests.",
                }
            )
        if (
            not item.get("sha256")
            or not pin.get("commit")
            and pin.get("revision_kind") == "tag"
        ):
            gaps.append(
                {
                    "id": pin["id"],
                    "disposition": pin.get(
                        "no_pin_detail",
                        "Missing recorded dereferenced tag commit/digest; ABSENT is not FRESH.",
                    ),
                }
            )
        rows.append(row)
    declarations = [{"path": RECORD, "sha256": digest(raw)}]
    cross_path = root / "tests/fixtures/r4-crosswalk.json"
    cross_raw = cross_path.read_bytes()
    cross = json.loads(cross_raw)
    declarations.append(
        {"path": "tests/fixtures/r4-crosswalk.json", "sha256": digest(cross_raw)}
    )
    rows.append(
        {
            "id": "r4-current-counterparts",
            "consumer": CONSUMER,
            "class": "conformance-suite",
            "repository": cross["repository"],
            "revision": cross["commit"],
            "revisionKind": "commit",
            "files": [{"path": cross["source"], "sha256": cross["sourceSha256"]}]
            + [
                {
                    "path": "conformance/"
                    + row["new"]["file"].removeprefix("r4-current/"),
                    "local": "tests/fixtures/"
                    + row["family"]
                    + "/"
                    + row["new"]["file"],
                    "sha256": row["newSha256"],
                }
                for row in cross["cases"]
            ],
        }
    )
    html_path = root / "tests/fixtures/fht-microdata/provenance.json"
    html_raw = html_path.read_bytes()
    html = json.loads(html_raw)
    declarations.append(
        {
            "path": "tests/fixtures/fht-microdata/provenance.json",
            "sha256": digest(html_raw),
        }
    )
    rows.append(
        {
            "id": "fht-html-owning-inputs",
            "consumer": CONSUMER,
            "class": "conformance-suite",
            "repository": html["repository"],
            "revision": html["revision"],
            "revisionKind": "commit",
            "files": [
                {
                    "path": (
                        "conformance/valid/" if name.endswith(".fasta") else "examples/"
                    )
                    + name,
                    "local": "tests/fixtures/fht-microdata/" + name,
                    "sha256": sha,
                }
                for name, sha in html["files"].items()
            ],
        }
    )
    candidate_path = "tests/fixtures/fht-publication/provenance.json"
    candidate_raw = (root / candidate_path).read_bytes()
    candidate = json.loads(candidate_raw)
    declarations.append({"path": candidate_path, "sha256": digest(candidate_raw)})
    rows.append(
        {
            "id": "fht-shared-publication-inputs",
            "consumer": CONSUMER,
            "class": "conformance-suite",
            "repository": candidate["repository"],
            "revision": candidate["commit"],
            "revisionKind": "commit",
            "materialStatus": "released",
            "files": candidate["files"],
        }
    )
    rows.append(
        {
            "id": "fht-shared-publication-contract",
            "consumer": CONSUMER,
            "class": "released-contract",
            "repository": candidate["repository"],
            "revision": candidate["revision"],
            "revisionKind": "tag",
            "commit": candidate["commit"],
            "files": [
                {
                    "path": "fht.json",
                    "local": "bioheaders/schemas/fht-1.0.json",
                    "sha256": candidate["schemaSha256"],
                }
            ],
        }
    )
    return {
        "inventoryVersion": 1,
        "advisory": True,
        "declarationRecords": declarations,
        "references": rows,
        "coverageGaps": gaps,
    }


def verify_checker(checkout, metadata):
    checkout = checkout.resolve()
    if (
        metadata["repository"] != AUTHORITY
        or metadata["path"] != "scripts/check_references.py"
        or not re.fullmatch(r"[0-9a-f]{40}", metadata["commit"])
        or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
    ):
        raise ValueError("invalid checker source pin")
    environment = {
        **os.environ,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    head = (
        subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], env=environment
        )
        .decode()
        .strip()
    )
    if head != metadata["commit"]:
        raise ValueError(
            "checker checkout HEAD does not match the declared source commit"
        )
    name = relative(metadata["path"])
    source = checkout / name
    if source.resolve() != source:
        raise ValueError("checker source path must not traverse symlinks")
    raw = source.read_bytes()
    immutable = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{head}:{name}"], env=environment
    )
    if source.is_symlink() or raw != immutable or digest(raw) != metadata["sha256"]:
        raise ValueError("checker file does not match its immutable source/digest")
    return immutable


def audit(checkout, mappings=(), root=ROOT, strict=False):
    metadata = json.loads((root / "references/checker.json").read_text())
    checker_bytes = verify_checker(checkout, metadata)
    table = inventory(root)
    with tempfile.TemporaryDirectory(prefix="tools-declared-references-") as work:
        generated = Path(work) / "inventory.json"
        generated.write_text(json.dumps(table, indent=2) + "\n")
        checker = Path(work) / "verified_check_references.py"
        checker.write_bytes(checker_bytes)
        checker.chmod(0o400)
        command = [
            sys.executable,
            "-I",
            str(checker),
            "--inventory",
            str(generated),
            "--consumer",
            CONSUMER,
            "--consumer-root",
            str(root.resolve()),
        ]
        for mapping in mappings:
            command.extend(["--checkout", mapping])
        # Isolated Python does not import neighboring unverified helper modules.
        result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError(
            "verified checker failed to produce an advisory report: "
            + result.stderr.strip()
        )
    report = json.loads(result.stdout)
    if len(report.get("references", [])) != len(table["references"]):
        raise RuntimeError("checker did not report every declared reference group")
    report.update(
        consumer=CONSUMER,
        checkerSource=metadata,
        declarationRecords=table["declarationRecords"],
    )
    return report, int(
        strict and any(row["verdict"] != "FRESH" for row in report["references"])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checker-root", type=Path, required=True)
    parser.add_argument(
        "--checkout", action="append", default=[], metavar="OWNER/REPO=PATH"
    )
    parser.add_argument(
        "--exit-on-findings",
        action="store_true",
        help="controlled offline check; scheduled audit stays advisory",
    )
    parser.add_argument(
        "--report-output", type=Path, help="atomic report outside the source checkout"
    )
    args = parser.parse_args()
    if args.report_output:
        if args.report_output.resolve().is_relative_to(ROOT.resolve()):
            parser.error("report output must remain outside the source checkout")
        args.report_output.unlink(missing_ok=True)
    try:
        report, status = audit(
            args.checker_root, args.checkout, strict=args.exit_on_findings
        )
    except FileNotFoundError as exc:
        missing_declaration = (
            bool(exc.filename)
            and Path(exc.filename).resolve() == (ROOT / RECORD).resolve()
        )
        report = {
            "advisory": True,
            "wrote": [],
            "references": [
                {
                    "id": "tools-declarations",
                    "verdict": "ABSENT" if missing_declaration else "QUERY_FAILED",
                    "localComparison": "not-run",
                    "reason": str(exc),
                }
            ],
        }
        status = int(args.exit_on_findings) if missing_declaration else 1
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
        subprocess.SubprocessError,
        RuntimeError,
    ) as exc:
        report = {
            "advisory": True,
            "wrote": [],
            "references": [
                {
                    "id": "fht-audit-bootstrap",
                    "verdict": "QUERY_FAILED",
                    "localComparison": "not-run",
                    "reason": str(exc),
                }
            ],
        }
        status = 1
    text = json.dumps(report, indent=2) + "\n"
    if args.report_output:
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=args.report_output.parent, delete=False
        ) as stream:
            stream.write(text)
            temporary = Path(stream.name)
        temporary.replace(args.report_output)
    print(text, end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
