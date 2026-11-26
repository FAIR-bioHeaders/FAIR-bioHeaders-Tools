# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Python-native acceptance guards (Tools#208 section 6, native-language CI rule).

- The package must be the installed wheel, never the source tree.
- A pinned corpus must be present and match its SHA-256 and count before use;
  a missing corpus fails unless FH_ALLOW_MISSING_CORPUS=1 outside CI.
- Any skipped test fails the session (no silent skips), and zero collected
  tests fail it too.
- A receipt is written for each corpus run (FH_RECEIPT_DIR, default ./receipts).
"""

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import pytest

import fair_bioheaders_tools as fht

REPO = Path(__file__).resolve().parents[3]

PINS = {
    "C-FROZEN": ("FH_SPEC_V060", "conformance/manifest.json",
                 "cdbb79b1fbfda52b27a9f54b73d3bae1efb662efcbb4c41ba02b9e3be40a51e1", 291,
                 "0ae18b00ee4bd71ab2dc28bae706b0f9d195076b"),
    "C-SOURCE": ("FH_SPEC_34BBE21A", "conformance/manifest.json",
                 "7c10fb83bbac5c5739240bff695e5469730ac26a066a51a44d5275598b2df3f6", 319,
                 "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b"),
    "C-POLICY": ("FH_SPEC_34BBE21A", "conformance/reader-policy/cases.json",
                 "b42d9c545d47ff9654f72b38a294f08640ed0e42aa4ff7fc756b0c33217db7c7", 64,
                 "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b"),
    "C-HIST": ("FH_SPEC_34BBE21A", "conformance/reader-policy/retirement-crosswalk.json",
               "c648601b6dc7589fa3efd40e870cc053385636e0f58ac6a73f429ff6abaabc4b", 78,
               "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b"),
}


def pytest_configure(config):
    location = Path(fht.__file__).resolve()
    if REPO in location.parents:
        raise pytest.UsageError(
            f"fair_bioheaders_tools was imported from the source tree ({location}); "
            "acceptance runs against the installed wheel only"
        )


@pytest.fixture(scope="session")
def engine():
    return fht.Engine()


def load_pinned(label):
    """(root, manifest JSON) for a pinned corpus, verified; fails when missing."""
    env, relative, digest, count, commit = PINS[label]
    root = os.environ.get(env)
    if not root:
        if os.environ.get("FH_ALLOW_MISSING_CORPUS") == "1" and not os.environ.get("CI"):
            return None, None
        pytest.fail(f"{label}: set {env} to a specification checkout at {commit} "
                    "(a missing corpus is a failure)")
    data = (Path(root) / relative).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, f"{label}: manifest digest is not the pinned one"
    manifest = json.loads(data)
    entries = manifest.get("vectors") or manifest.get("cases")
    assert len(entries) == count, f"{label}: manifest count differs from the pin"
    return Path(root), manifest


def write_receipt(label, tally, extra=None):
    env, relative, digest, count, commit = PINS[label]
    directory = Path(os.environ.get("FH_RECEIPT_DIR", "receipts"))
    directory.mkdir(parents=True, exist_ok=True)
    totals = {k: sum(t[k] for t in tally.values()) for k in ("total", "run", "passed", "failed")}
    receipt = {
        "corpus": label,
        "manifest": relative,
        "manifestSha256": digest,
        "specCommit": commit,
        "engineVersion": fht.ENGINE_VERSION,
        "abiVersion": fht.ABI_VERSION,
        "packageVersion": fht.__version__,
        "python": sys.version.split()[0],
        "platform": f"{platform.machine()}-{sys.platform}",
        "bundleId": fht.Engine().provenance["bundle_id"],
        "profileId": "python",
        "totals": totals,
        "perFormat": tally,
        "runner": {"harness": "pytest (installed wheel)"},
        "ciRunId": os.environ.get("GITHUB_RUN_ID"),
    }
    receipt.update(extra or {})
    path = directory / f"python-{label}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


_SKIPPED = []


def pytest_runtest_logreport(report):
    if report.skipped:
        _SKIPPED.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if _SKIPPED:
        print(f"\nFAIL: {len(_SKIPPED)} skipped test(s) are failures here: {_SKIPPED}", file=sys.stderr)
        session.exitstatus = 1
    if session.testscollected == 0:
        print("\nFAIL: zero tests collected", file=sys.stderr)
        session.exitstatus = 1
