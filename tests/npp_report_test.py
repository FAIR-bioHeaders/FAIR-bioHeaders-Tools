# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""NPP prototype report layer separation (FAIR-bioHeaders-Tools#169, PR-A).

Every check pins an acceptance behavior of the report, not a message: layers
are decided independently (tampering must fail integrity while schema stays
valid), unsupported contracts are refused explicitly, absent parent candidates
are reported as not-run and never as a pass, builds are deterministic, revision
binding survives an in-flight swap, and the profile constants carry the
maintainer's accepted version/commit pair from specification #249 — never
invented provenance. The review round (Copilot, 2026-11-27) added the last
group: unexpected verifier exits fail, compressed carriers scan, missing or
noncanonical checksums are layer outcomes not crashes, the selected schema is
hashed per-record, and --text escapes terminal controls.
"""

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from bioheaders import fhr, npp_report, selection
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


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _header_checksum(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith(";~checksum:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("no checksum line")


def test_layers_pass_and_parents_not_run(tmp_path):
    path = write_fhr(tmp_path)
    report = npp_report.build_report(path)
    assert report["layers"]["schema"]["outcome"] == "valid"
    assert report["layers"]["integrity"]["outcome"] == "pass"
    assert report["layers"]["parent_links"]["outcome"] == npp_report.NOT_RUN
    assert report["outcome"] == "pass-unchecked-parents"
    assert report["input"]["stable_during_report"] is True
    assert report["certification"].startswith("None implied")


def test_integrity_bound_to_exact_physical_bytes(tmp_path):
    path = write_fhr(tmp_path)
    report = npp_report.build_report(path)
    assert report["input"]["sha256_physical"] == _sha(path)
    assert report["input"]["bytes"] == path.stat().st_size
    assert (
        report["layers"]["integrity"]["recorded_checksum"]
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
    # are decided independently.
    path = write_fhr(tmp_path)
    raw = path.read_text()
    before = [line for line in raw.splitlines() if line.startswith(";~schema:")]
    assert before, "fixture header must carry a schema line"
    raw = raw.replace(
        before[0], ";~schema: https://w3id.org/fair-bioheaders/fhr/v9.9.9", 1
    )
    path.write_text(raw)
    report = npp_report.build_report(path)
    assert report["layers"]["schema"]["outcome"] == "refused-unsupported-schema"
    assert report["layers"]["integrity"]["outcome"] == "fail"
    assert report["outcome"] == "fail"
    assert "unsupported schema version" in report["layers"]["schema"]["detail"].lower()
    assert report["schema_provenance"]["resolved"] is None


def test_parent_mismatch_maps_to_documented_exit_3(tmp_path):
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


def test_unexpected_verifier_exit_fails_the_report(tmp_path, monkeypatch):
    # A signal-killed verify-links (negative return code) is not a completion:
    # anything outside the accepted {0} outcome must fail overall (review #2).
    path = write_fhr(tmp_path)

    class Dead:
        returncode = -9
        stdout = ""
        stderr = "killed"

    monkeypatch.setattr(npp_report.subprocess, "run", lambda *a, **k: Dead())
    report = npp_report.build_report(path, parents=[path])
    assert report["layers"]["parent_links"]["outcome"] == "error-exit--9"
    assert report["outcome"] == "fail"
    assert npp_report.outcome_exit_code(report) == 1


def test_revision_change_during_report_fails(tmp_path, monkeypatch):
    # If the bytes move between the bound digest and the final re-check, the
    # report must say so and fail - a digest may never certify another revision
    # than the one the parent verifier read (review #1).
    path = write_fhr(tmp_path)
    original = npp_report.subprocess.run

    def mutate_then_run(*args, **kwargs):
        path.write_bytes(path.read_bytes().replace(b"ACGTACGTAA", b"TTTTTTTTTT"))
        return original(*args, **kwargs)

    monkeypatch.setattr(npp_report.subprocess, "run", mutate_then_run)
    report = npp_report.build_report(path, parents=[path])
    assert report["input"]["stable_during_report"] is False
    assert report["failure"] == "input-changed-during-report"
    assert report["outcome"] == "fail"


def test_compressed_carrier_scans_and_binds_physical_bytes(tmp_path):
    # review #4: .gz must scan through the magic-aware reader like verify does,
    # while the bound sha256 stays the physical compressed bytes, explicitly.
    plain = write_fhr(tmp_path)
    gz_path = tmp_path / "book.fhr.fasta.gz"
    gz_path.write_bytes(gzip.compress(plain.read_bytes()))
    report = npp_report.build_report(gz_path)
    assert report["carrier"] == "fasta"
    assert report["layers"]["schema"]["outcome"] == "valid"
    assert report["layers"]["integrity"]["outcome"] == "pass"
    assert report["input"]["sha256_physical"] == _sha(gz_path)
    assert report["input"]["sha256_physical"] != _sha(plain)


def test_missing_checksum_is_an_absent_outcome_not_a_crash(tmp_path):
    # review #5: no checksum line => integrity reports absent; schema layer
    # still renders its own independent verdict; no AttributeError anywhere.
    path = write_fhr(tmp_path)
    kept = [
        line
        for line in path.read_text().splitlines(keepends=True)
        if not line.startswith(";~checksum:")
    ]
    path.write_text("".join(kept))
    report = npp_report.build_report(path)
    assert report["layers"]["integrity"]["outcome"] == "absent"
    assert report["layers"]["schema"]["outcome"] in ("valid", "invalid")
    assert report["outcome"] == "fail"


def test_provenance_hashes_the_selected_schema_not_the_registry(tmp_path):
    # review #6: citation, registry digest and selected-schema digest are three
    # separate facts; the resolved entry comes from record-aware selection.
    path = write_fhr(tmp_path)
    report = npp_report.build_report(path)
    prov = report["schema_provenance"]
    citation = prov["cited_contract"]
    kind, ref, filename = selection._file(citation)
    raw = selection.files(selection.__package__).joinpath(filename).read_bytes()
    assert prov["resolved"]["selected_schema_sha256"] == hashlib.sha256(raw).hexdigest()
    assert prov["resolved"]["header_type"] == kind
    assert prov["bundled_registry_sha256"] != prov["resolved"]["selected_schema_sha256"]


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


def test_text_output_escapes_terminal_controls(tmp_path):
    # review #7: a crafted filename must not reach a terminal raw through
    # --text; the escaped rendering never contains the ESC byte.
    evil = tmp_path / "esc\x1b[2Jbook.fhr.fasta"
    record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    evil.write_bytes(combine(fhr(**record), SEQ, "fasta"))
    report = npp_report.build_report(evil)
    text = npp_report.render_text(report)
    assert "\x1b" not in text
    assert "esc" in text  # the name still appears, neutralized
