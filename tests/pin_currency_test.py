# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Independent controls for advisory content currency, never automatic updates."""

import hashlib
import json
import socket
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from bioheaders import pin_audit
from bioheaders.pin_currency import DefaultContent, consumer_records, consumer_report

ROOT = Path(__file__).resolve().parents[1]
OWNER = "FAIR-bioHeaders/FHT-Specification"
OLD, TIP = "b" * 40, "a" * 40
RAW = (ROOT / "bioheaders/schemas/fht-draft.json").read_bytes()
DIGEST = hashlib.sha256(RAW).hexdigest()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("currency unit tests must not contact the network")

    monkeypatch.setattr(socket, "socket", forbidden)


def put(directory, repository, revision, path, raw):
    target = directory / (repository.rsplit("/", 1)[-1] + "@" + revision) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)


def setup(tmp_path, default=RAW):
    authority = tmp_path / "authority"
    authority.mkdir()
    put(authority, OWNER, OLD, "fht.json", RAW)
    if default is not None:
        put(authority, OWNER, TIP, "fht.json", default)
    (authority / "default-branches.json").write_text(
        json.dumps({OWNER: {"branch": "trunk", "commit": TIP}})
    )
    options = pin_audit.build_parser().parse_args(
        ["--fixture-dir", str(authority), "--no-conflicts"]
    )
    options.checkouts = {}
    options.current_release = "v0.6.0"
    auditor = pin_audit.Auditor(options, root=tmp_path)
    reference = {
        "id": "draft",
        "class": "draft-contract",
        "label": pin_audit.DRAFT_LABEL,
        "repository": OWNER,
        "revision": OLD,
        "revision_kind": "commit",
        "path": "fht.json",
        "sha256": DIGEST,
        "bytes": len(RAW),
        "local": None,
    }
    return authority, auditor, reference


def test_equal_content_at_different_commits_is_current(tmp_path):
    _, auditor, reference = setup(tmp_path)
    integrity = auditor.one(reference)
    result = DefaultContent(auditor).compare(reference, integrity)
    assert integrity["verdict"] == "FRESH"
    assert result["status"] == "CURRENT_CONTENT"
    assert result["recorded_revision"] != result["default_commit"]
    assert result["default_branch"] == "trunk"
    assert result["recorded_sha256"] == result["default_sha256"]


def test_changed_bytes_do_not_invalidate_an_honest_historical_pin(tmp_path):
    _, auditor, reference = setup(tmp_path, RAW + b"\n")
    integrity = auditor.one(reference)
    result = DefaultContent(auditor).compare(reference, integrity)
    assert integrity["verdict"] == "FRESH"
    assert result["status"] == "SUPERSEDED_CONTENT"
    assert result["default_sha256"] != result["recorded_sha256"]


def test_corrupt_record_withholds_currency_even_if_default_matches(
    tmp_path, monkeypatch
):
    _, auditor, reference = setup(tmp_path)
    reference["sha256"] = "0" * 64
    integrity = auditor.one(reference)
    assert integrity["verdict"] == "DRIFT"
    defaults = DefaultContent(auditor)
    monkeypatch.setattr(
        defaults, "read", lambda *args: pytest.fail("must not compare untrusted record")
    )
    result = defaults.compare(reference, integrity)
    assert result["status"] == "UNAVAILABLE"
    assert "withheld" in result["detail"]


@pytest.mark.parametrize("default", [None, b""])
def test_missing_or_empty_default_is_unavailable(tmp_path, default):
    _, auditor, reference = setup(tmp_path, default)
    result = DefaultContent(auditor).compare(reference, auditor.one(reference))
    assert result["status"] == "UNAVAILABLE"
    assert result["default_sha256"] is None


def test_permissive_default_backend_fails_its_negative_control(tmp_path):
    authority, auditor, reference = setup(tmp_path)
    put(authority, OWNER, TIP, pin_audit.CONTROL_NAME, RAW)
    result = DefaultContent(auditor).compare(reference, auditor.one(reference))
    assert result["status"] == "UNAVAILABLE"
    assert "control" in result["detail"]
    assert any(c["negative_control_ok"] is False for c in auditor.control_report())


@pytest.mark.parametrize(
    "response", [(b"{}", 200), (None, 301), (None, 500), (None, None)]
)
def test_metadata_backend_must_return_genuine_404(tmp_path, monkeypatch, response):
    _, auditor, _ = setup(tmp_path)
    auditor.options.fixture_dir = None
    defaults = DefaultContent(auditor)
    monkeypatch.setattr(defaults, "_api", lambda *args: response)
    assert defaults.snapshot(OWNER)["commit"] is None
    assert defaults.controls[0]["negative_control_ok"] is False


@pytest.mark.parametrize(
    "raw", [b"", b"{}", b"[]", b"not json", b'{"default_branch":""}']
)
def test_empty_or_malformed_metadata_is_not_a_default_snapshot(
    tmp_path, monkeypatch, raw
):
    _, auditor, _ = setup(tmp_path)
    auditor.options.fixture_dir = None
    defaults = DefaultContent(auditor)
    monkeypatch.setattr(
        defaults, "_api", lambda repo, suffix="": (None, 404) if suffix else (raw, 200)
    )
    assert defaults.snapshot(OWNER)["commit"] is None


def test_snapshot_is_captured_once_and_uses_full_commit(tmp_path, monkeypatch):
    _, auditor, _ = setup(tmp_path)
    auditor.options.fixture_dir = None
    defaults = DefaultContent(auditor)
    calls = []

    def api(repo, suffix=""):
        calls.append(suffix)
        if suffix.endswith(pin_audit.CONTROL_NAME):
            return None, 404
        return (
            json.dumps(
                {"sha": TIP} if suffix else {"default_branch": "release/next"}
            ).encode(),
            200,
        )

    monkeypatch.setattr(defaults, "_api", api)
    first = defaults.snapshot(OWNER)
    assert first["branch"] == "release/next" and first["commit"] == TIP
    assert defaults.snapshot(OWNER) == first and len(calls) == 3
    assert calls[-1] == "/commits/release%2Fnext"


def test_offline_does_not_probe_metadata(tmp_path, monkeypatch):
    _, auditor, reference = setup(tmp_path)
    auditor.options.fixture_dir = None
    auditor.options.offline = True
    defaults = DefaultContent(auditor)
    monkeypatch.setattr(
        defaults, "_api", lambda *args: pytest.fail("offline must not probe")
    )
    assert defaults.compare(reference, {"verdict": "FRESH"})["status"] == "UNAVAILABLE"
    assert defaults.controls == []


def test_checkout_uses_remote_default_not_task_branch_or_working_bytes(tmp_path):
    _, auditor, _ = setup(tmp_path)
    checkout = tmp_path / "repo"
    checkout.mkdir()

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(checkout), *args], stderr=subprocess.STDOUT, text=True
        ).strip()

    git("init", "-b", "trunk")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (checkout / "fht.json").write_bytes(RAW)
    git("add", "fht.json")
    git("commit", "-m", "default bytes")
    commit = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/trunk", commit)
    git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    git("checkout", "-b", "task")
    (checkout / "fht.json").write_bytes(b"modified working bytes")
    auditor.options.fixture_dir = None
    auditor.checkouts[OWNER] = str(checkout)
    raw, snapshot, _ = DefaultContent(auditor).read(OWNER, "fht.json")
    assert snapshot["commit"] == commit and snapshot["branch"] == "trunk"
    assert raw == RAW


@pytest.mark.parametrize("consumer", ["JavaScript", "Julia", "Java", "R", "Tools"])
def test_existing_registry_adapters_preserve_recorded_commit_meaning(consumer):
    entry = {
        "commit": OLD,
        "sha256": DIGEST,
        "sourcePath": "fht.json",
        "suiteCommit": TIP,
        "suiteManifestSha256": DIGEST,
        "suiteVectors": 72,
    }
    if consumer == "R":
        doc = {
            "files": [{"kind": "draft-contract", "header_type": "FHT", **entry}],
            "draft_vectors": {"commit": TIP, "manifest_sha256": DIGEST, "vectors": 72},
        }
    elif consumer == "Tools":
        doc = {
            "drafts": {
                "FHT": {
                    "revision": OLD,
                    "sha256": DIGEST,
                    "suite": {"revision": TIP, "sha256": DIGEST, "fhtFastaVectors": 68},
                }
            }
        }
    else:
        if consumer == "Java":
            entry = {
                **entry,
                "artifacts": [
                    {"sourcePath": "fht.json", "commit": OLD, "sha256": DIGEST}
                ],
            }
        doc = {"drafts": {"FHT": entry}}
    before = deepcopy(doc)
    rows = consumer_records(consumer, doc)
    assert rows[0]["revision"] == OLD and rows[1]["revision"] == TIP
    assert rows[0]["sha256"] == DIGEST and rows[1]["sha256"] == DIGEST
    assert rows[2]["revision"] is None and rows[3]["revision"] is None
    assert doc == before


def test_consumer_disagreement_and_same_digest_groups_are_explicit(tmp_path):
    authority, auditor, _ = setup(tmp_path)
    branch_map = json.loads((authority / "default-branches.json").read_text())
    from bioheaders.pin_currency import CONSUMERS

    for consumer, path in CONSUMERS.items():
        repo = "FAIR-bioHeaders/FAIR-bioHeaders-Tools-" + consumer
        branch_map[repo] = {"branch": "trunk", "commit": TIP}
        if consumer == "R":
            doc = {
                "files": [
                    {
                        "kind": "draft-contract",
                        "header_type": "FHT",
                        "commit": OLD,
                        "sha256": DIGEST,
                    }
                ],
                "draft_vectors": {},
            }
        else:
            doc = {
                "drafts": {
                    "FHT": {"commit": TIP, "sha256": DIGEST, "sourcePath": "fht.json"}
                }
            }
        put(authority, repo, TIP, path, json.dumps(doc).encode())
    (authority / "default-branches.json").write_text(json.dumps(branch_map))
    runtime = {"drafts": {"FHT": {"revision": OLD, "sha256": DIGEST}}}
    report = consumer_report(DefaultContent(auditor), runtime)
    group = report["verified_digest_groups"]["FHT:contract:" + DIGEST]
    assert {r["consumer"] for r in group} == {
        "Tools",
        "Java",
        "JavaScript",
        "Julia",
        "R",
    }
    assert {r["revision"] for r in group} == {OLD, TIP}
    assert all(
        row["status"] == "NOT_RECORDED"
        for row in report["rows"]
        if row.get("logical_reference", "").startswith("FHGM")
    )
    assert all(row["label"] == pin_audit.DRAFT_LABEL for row in report["rows"])


def derived(tmp_path):
    authority, auditor, _ = setup(tmp_path)
    repository = "FAIR-bioHeaders/FAIR-bioHeaders-Specification"
    vectors = [
        {"id": "one", "format": "fhp-fasta", "metadata": {"ordered": ["z", "a"]}},
        {"id": "other", "format": "fhgff3"},
    ]
    raw = json.dumps({"vectors": vectors}).encode()
    put(authority, repository, "v0.6.0", "conformance/manifest.json", raw)
    (tmp_path / "local.json").write_text(
        json.dumps({"source": "local annotation", "vectors": vectors[:1]})
    )
    row = {
        "id": "subset",
        "class": "conformance-suite",
        "repository": repository,
        "revision": "v0.6.0",
        "revision_kind": "tag",
        "label": "released",
        "path": "conformance/manifest.json",
        "local": "local.json",
        "sha256": None,
        "relationship": {
            "kind": "derived-subset",
            "filter": {"format": "fhp-fasta"},
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
        },
    }
    return auditor, row


def test_derived_subset_checks_whole_parent_and_declared_filter(tmp_path):
    auditor, row = derived(tmp_path)
    before = (tmp_path / "local.json").read_bytes()
    result = auditor.one(row)
    assert (
        result["verdict"] == "NOT_A_FILE_PIN" and result["transform_status"] == "MATCH"
    )
    assert result["source_vectors"] == 2 and result["selected_vectors"] == 1
    assert result["fixture_files_checked"] is False
    assert (tmp_path / "local.json").read_bytes() == before
    assert DefaultContent(auditor).compare(row, result)["status"] == "NOT_APPLICABLE"


@pytest.mark.parametrize(
    "mutation", ["digest", "predicate", "content", "missing", "malformed"]
)
def test_derived_relationship_cannot_hide_a_bad_parent_or_transform(tmp_path, mutation):
    auditor, row = derived(tmp_path)
    if mutation == "digest":
        row["relationship"]["source_sha256"] = "0" * 64
    elif mutation == "predicate":
        row["relationship"]["filter"] = {"invented": "field"}
    elif mutation == "content":
        p = tmp_path / "local.json"
        doc = json.loads(p.read_text())
        doc["vectors"][0]["metadata"]["ordered"].reverse()
        p.write_text(json.dumps(doc))
    elif mutation == "missing":
        (tmp_path / "local.json").unlink()
    else:
        row["relationship"]["source_sha256"] = None
    result = auditor.one(row)
    assert result["verdict"] == "NOT_A_FILE_PIN"
    assert result["transform_status"] != "MATCH"
    assert result["detail"]


def test_cli_is_advisory_preserves_all_inputs_and_reports_missing_consumers(
    tmp_path, capsys
):
    authority, _, reference = setup(tmp_path)
    table = tmp_path / "table.json"
    table.write_text(json.dumps({"tableVersion": 1, "references": [reference]}))
    runtime = tmp_path / "bioheaders/schemas/bundled.json"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        json.dumps({"drafts": {"FHT": {"revision": OLD, "sha256": DIGEST}}})
    )
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    args = [
        "--pin-file",
        str(table),
        "--root",
        str(tmp_path),
        "--fixture-dir",
        str(authority),
        "--against-default",
        "--consumers",
        "--no-conflicts",
        "--json",
    ]
    assert pin_audit.main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["wrote"] == [] and report["advisory"] is True
    assert report["default_content"][0]["status"] == "CURRENT_CONTENT"
    assert (
        sum(row["status"] == "UNAVAILABLE" for row in report["consumers"]["rows"]) == 4
    )
    after = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert after == before
    reference["sha256"] = "0" * 64
    table.write_text(json.dumps({"tableVersion": 1, "references": [reference]}))
    assert pin_audit.main(args) == 0  # currency findings never enable a gate
    report = json.loads(capsys.readouterr().out)
    assert report["references"][0]["verdict"] == "DRIFT"
    assert report["default_content"][0]["status"] == "UNAVAILABLE"
    assert pin_audit.main(args + ["--exit-on-drift"]) == 1
    capsys.readouterr()


def test_text_accounts_for_relationships_without_claiming_file_freshness(tmp_path):
    auditor, reference = derived(tmp_path)
    result = auditor.one(reference)
    text = pin_audit.format_text(
        {"tableVersion": 1}, [result], [], auditor.control_report()
    )
    assert "1 NOT_A_FILE_PIN of 1" in text
    assert "fixture payload bytes not checked" in text
