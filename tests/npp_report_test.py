# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""NPP prototype report layer separation (FAIR-bioHeaders-Tools#169, PR-A).

Every check here pins an acceptance behavior of the report, not a message:
layers are decided independently (tampering must fail integrity while schema
stays valid), unsupported contracts are refused explicitly, absent parent
candidates are reported as not-run and never as a pass, builds are
deterministic, and the profile constants carry the maintainer's accepted
version/commit pair from specification #249 — never invented provenance.
"""

import json
import subprocess
import sys
from pathlib import Path

from bioheaders import fhr, npp_report
from bioheaders.cli import combine

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
SEQ = b">chr1\nACGTACGTAA\n"


def write_fhr(tmp_path, **over):
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    record.update(over)
    path = tmp_path / "book.fhr.fasta"
    path.write_bytes(combine(fhr(**record), SEQ, "fasta"))
    return path


def test_layers_pass_and_parents_not_run(tmp_path):
    path = write_fhr(tmp_path)
    report = npp_report.build_report(path)
    assert report["layers"]["schema"]["outcome"] == "valid"
    assert report["layers"]["integrity"]["outcome"] == "pass"
    assert report["layers"]["parent_links"]["outcome"] == npp_report.NOT_RUN
    assert report["outcome"] == "pass-unchecked-parents"
    assert report["certification"].startswith("None implied")


def test_integrity_bound_to_exact_bytes(tmp_path):
    path = write_fhr(tmp_path)
    report = npp_report.build_report(path)
    assert report["input"]["sha256"] == _sha(path)
    assert (
        report["input"]["recorded_checksum"]
        == report["layers"]["integrity"]["recomputed_sha512_256"]
    )


def test_tampering_fails_integrity_only(tmp_path):
    path = write_fhr(tmp_path)
    good = path.read_bytes()
    path.write_bytes(good.replace(b"ACGTACGTAA", b"ACGTACGTAU"))
    report = npp_report.build_report(path)
    assert report["layers"]["schema"]["outcome"] == "valid"  # header untouched
    assert report["layers"]["integrity"]["outcome"] == "fail"
    assert report["outcome"] == "fail"
    assert npp_report.outcome_exit_code(report) == 1


def test_unsupported_schema_is_refused_not_certified(tmp_path):
    # A contract URL the bundled selection cannot serve must surface as its own
    # outcome; the report never validates against a guessed schema. The file is
    # built valid, then the schema line is rewritten to the unsupportable tag —
    # which also breaks the header checksum, demonstrating that the two layers
    # are decided independently (schema refused, integrity fails on its own
    # recomputation, neither outcome is inferred from the other).
    path = write_fhr(tmp_path)
    raw = path.read_text()
    before = [line for line in raw.splitlines() if line.startswith(";~schema:")]
    assert before, "fixture header must carry a schema line"
    raw = raw.replace(
        before[0], ";~schema: https://w3id.org/fair-bioheaders/fhr/v9.9.9", 1
    )
    path.write_text(raw)
    report = npp_report.build_report(path)
    assert report["layers"]["integrity"]["outcome"] == "fail"
    assert report["layers"]["schema"]["outcome"] == "refused-unsupported-schema"
    assert report["outcome"] == "fail"
    assert "unsupported schema version" in report["layers"]["schema"]["detail"].lower()


def test_parent_mismatch_maps_to_documented_exit_3(tmp_path):
    # An FHP whose recorded FHR parent (placeholder checksum) does not match the
    # supplied genome file: require-all turns the non-match into the exit-3
    # contract; the report carries the code, and message text is data only.
    parent = ROOT / "examples/fhgff3/genome.fhr.fasta"
    record = json.loads((ROOT / "examples/fhp/rich-microdata.fhp.json").read_text())
    record["schema"] = "https://w3id.org/fair-bioheaders/fhp/v0.8.0"
    wrong = list(_header_checksum(parent))
    wrong[0] = "B" if wrong[0] != "B" else "C"
    record["derivedFrom"] = [
        {
            "headerType": "FHR",
            "relationship": "translatedFrom",
            "checksum": "".join(wrong),
        }
    ]
    path = tmp_path / "prot.fhp.fasta"
    path.write_bytes(combine(fhr(**record), b">NP_001\nMKVLAAAA\n", "fasta"))
    report = npp_report.build_report(path, parents=[parent], require_all=True)
    links = report["layers"]["parent_links"]
    assert links["exit_code"] == 3
    assert links["outcome"] == "mismatch-or-unchecked"
    assert report["outcome"] == "fail"


def test_matched_parent_passes(tmp_path):
    parent = write_fhr(tmp_path)
    record = json.loads((ROOT / "examples/fhp/rich-microdata.fhp.json").read_text())
    record["schema"] = "https://w3id.org/fair-bioheaders/fhp/v0.8.0"
    record["derivedFrom"] = [
        {
            "headerType": "FHR",
            "relationship": "translatedFrom",
            "checksum": _header_checksum(parent),
        }
    ]
    child = tmp_path / "child.fhp.fasta"
    child.write_bytes(combine(fhr(**record), b">NP_002\nMKT\n", "fasta"))
    report = npp_report.build_report(child, parents=[parent])
    assert report["layers"]["parent_links"]["outcome"] == "pass"
    assert report["outcome"] == "pass"


def test_report_is_deterministic(tmp_path):
    path = write_fhr(tmp_path)
    a = json.dumps(npp_report.build_report(path), sort_keys=True)
    b = json.dumps(npp_report.build_report(path), sort_keys=True)
    assert a == b  # no clocks, no temp paths, no live services


def test_profile_constants_are_the_accepted_pair():
    # The pairing is the maintainer's dated acceptance (specification #249);
    # changing either value without a new acceptance is a defect, not a bump.
    assert npp_report.PROFILE_NAME == "npp-fhr-publication"
    assert npp_report.PROFILE_VERSION == "0.1.0-draft.2"
    assert len(npp_report.PROFILE_COMMIT) == 40
    assert "#issuecomment-" in npp_report.PROFILE_DECISION


def test_cli_json_contract(tmp_path):
    path = write_fhr(tmp_path)
    done = subprocess.run(
        [str(BIN / "bioheaders"), "npp", str(path)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)  # stdout stays pure JSON
    assert report["profile"]["profile_version"] == npp_report.PROFILE_VERSION
    assert report["tool"]["name"] == "fair-bioheaders"
    assert "jats_projection" in report["not_run"]


def test_cli_text_and_missing_input(tmp_path):
    done = subprocess.run(
        [str(BIN / "bioheaders"), "npp", str(tmp_path / "nope.fasta"), "--text"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 1
    assert "not a readable file" in done.stderr


def _sha(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _header_checksum(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith(";~checksum:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("no checksum line")
