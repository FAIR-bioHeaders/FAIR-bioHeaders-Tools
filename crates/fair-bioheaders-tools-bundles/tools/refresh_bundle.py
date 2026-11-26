#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Regenerate data/bundle.json and data/schemas/ from the toolkit's pinned copies.

A maintenance helper, not an acceptance check: the Rust tests verify every
file against the digests recorded here, and those digests against the
toolkit's pins.json while both live in this repository. Run from the
repository root: python3 crates/fair-bioheaders-tools-bundles/tools/refresh_bundle.py
"""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLKIT = ROOT / "bioheaders"
DATA = ROOT / "crates" / "fair-bioheaders-tools-bundles" / "data"


def main():
    bundled = json.loads((TOOLKIT / "schemas" / "bundled.json").read_text())
    pins = json.loads((TOOLKIT / "pins.json").read_text())
    by_local = {}
    for row in pins["references"]:
        by_local.setdefault(row.get("local"), row)

    schema_dir = TOOLKIT / "schemas"
    by_digest = {
        hashlib.sha256(f.read_bytes()).hexdigest(): f.name
        for f in sorted(schema_dir.glob("*.json"))
    }

    def name(path):
        # Current copies (bioheaders/fhr_schema.json, ...) are byte-identical to
        # a versioned file under schemas/; name them by that file.
        source = TOOLKIT / path
        return by_digest[hashlib.sha256(source.read_bytes()).hexdigest()]

    used = set()
    current = {kind: name(path) for kind, path in bundled["current"]["files"].items()}
    releases = {
        tag: {kind: name(p) for kind, p in row.items()}
        for tag, row in bundled["releases"].items()
    }
    used.update(current.values())
    for row in releases.values():
        used.update(row.values())
    drafts = {}
    for kind, entry in bundled.get("drafts", {}).items():
        if "file" not in entry:
            continue  # FHGM model drafts: model layer, outside the Phase 1 engine.
        drafts[kind] = {
            k: v
            for k, v in entry.items()
            if k
            in (
                "status",
                "schemaVersion",
                "citation",
                "revision",
                "sha256",
                "retrieved",
            )
        }
        drafts[kind]["file"] = name(entry["file"])
        used.add(drafts[kind]["file"])
    files = {}
    (DATA / "schemas").mkdir(parents=True, exist_ok=True)
    for file_name in sorted(used):
        source = TOOLKIT / "schemas" / file_name
        raw = source.read_bytes()
        shutil.copyfile(source, DATA / "schemas" / file_name)
        pin = by_local.get(f"bioheaders/schemas/{file_name}") or {}
        files[file_name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "repository": pin.get("repository"),
            "revision": pin.get("revision"),
            "commit": pin.get("commit"),
            "path": pin.get("path"),
            "label": pin.get("label"),
        }
    publication = bundled.get("publication", {})
    bundle = {
        "bundleVersion": 1,
        "note": "Digest-pinned schema bytes and the V1-V7 selection table, copied from the "
        "FAIR-bioHeaders toolkit 0.13.1 bundle (bioheaders/schemas/bundled.json, pins.json). "
        "Regenerate with tools/refresh_bundle.py; never edit schema bytes by hand.",
        "currentRelease": bundled["current"]["release"],
        "specCommit": publication.get(bundled["current"]["release"], {}).get("commit"),
        "current": current,
        "releases": releases,
        "drafts": drafts,
        "files": files,
    }
    (DATA / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")


if __name__ == "__main__":
    main()
