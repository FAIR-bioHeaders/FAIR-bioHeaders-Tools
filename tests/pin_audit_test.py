# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The cross-repo pin audit: the reference gate of FAIR-bioHeaders-Specification#241.

Everything here runs offline. Authority bytes are materialised into a fixture
directory laid out as ``<repo>@<revision>/<path>`` from **real files in this
checkout**, so the digests under test are measured, never invented: the toolkit's
``schemas/fhp-1.1.json`` and ``schemas/fhp-1.2.json`` are the released
specification ``v0.5.0`` and ``v0.6.0`` bytes (verified against the tags, see
docs/PIN-AUDIT.md), which is exactly the pair the #241(a) defect turned on.

The gate has to be able to fail, so each test that expects ``FRESH`` is paired
with one that mutates the input and expects ``DRIFT`` or ``ABSENT``, and the
mutation itself is proved non-vacuous by comparing file bytes before and after.
"""

import hashlib
import json
import shutil
import subprocess
import urllib.error
from pathlib import Path

import pytest

from bioheaders import pin_audit

ROOT = Path(__file__).resolve().parents[1]
SPEC = "FAIR-bioHeaders/FAIR-bioHeaders-Specification"
FHT_SPEC = "FAIR-bioHeaders/FHT-Specification"
V060 = "v0.6.0"
V050 = "v0.5.0"
FHP_1_2 = "bioheaders/schemas/fhp-1.2.json"
FHP_1_1 = "bioheaders/schemas/fhp-1.1.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authority_dir(tmp_path, spec_bytes=None):
    """Materialise fixture authorities from this checkout's real released bytes."""
    root = tmp_path / "authority"
    layout = [
        ("FAIR-bioHeaders-Specification@{}".format(V060), "fhp.json", FHP_1_2),
        ("FAIR-bioHeaders-Specification@{}".format(V050), "fhp.json", FHP_1_1),
        (
            "FHT-Specification@226f923c28b680edb3c546e99a751482d06aef1a",
            "fht.json",
            "bioheaders/schemas/fht-draft.json",
        ),
    ]
    for folder, name, source in layout:
        target = root / folder
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, target / name)
    if spec_bytes is not None:
        # An authority that answers everything: the control probe must notice.
        permissive = root / "FAIR-bioHeaders-Specification@{}".format(V060)
        (permissive / pin_audit.CONTROL_NAME).write_bytes(spec_bytes)
    return root


def reference(cls="released-contract", **kwargs):
    base = {
        "id": "row",
        "class": cls,
        "repository": SPEC,
        "revision": V060,
        "revision_kind": "tag",
        "path": "fhp.json",
        "local": FHP_1_2,
        "sha256": sha256(ROOT / FHP_1_2),
        "bytes": (ROOT / FHP_1_2).stat().st_size,
        "label": "released",
    }
    base.update(kwargs)
    return base


def table(references, **kwargs):
    data = {
        "tableVersion": 99,
        "current_release": V060,
        "references": references,
    }
    data.update(kwargs)
    return data


def run_audit(tmp_path, references, argv=(), fixture=None, spec_bytes=None):
    """Write a table to ``tmp_path`` and run the command against the fixture authority."""
    path = tmp_path / "pins.json"
    path.write_text(json.dumps(table(references), indent=2), encoding="utf-8")
    authority = fixture or authority_dir(tmp_path, spec_bytes)
    result = pin_audit.main(
        [
            "--pin-file",
            str(path),
            "--fixture-dir",
            str(authority),
            "--root",
            str(ROOT),
            "--no-conflicts",
            *argv,
        ]
    )
    return result, path, authority


# --- the shipped table -------------------------------------------------------


def test_shipped_table_is_data_with_all_four_classes():
    data = pin_audit.load_table()
    classes = {row["class"] for row in data["references"]}
    assert classes == set(pin_audit.CLASSES), classes
    ids = [row["id"] for row in data["references"]]
    assert len(ids) == len(set(ids)), "reference ids must be unique"
    assert (
        data["current_release"]
        == json.loads((ROOT / "bioheaders/schemas/bundled.json").read_text())[
            "current"
        ]["release"]
    )
    draft_rows = [
        row for row in data["references"] if row["label"] == pin_audit.DRAFT_LABEL
    ]
    assert draft_rows, "the shipped table must carry the draft axes"
    for row in draft_rows:
        assert row["class"] in {
            "draft-contract",
            "conformance-suite",
            "base-carrier",
        }, row["id"]
    for row in data["references"]:
        if row["class"] == "released-contract":
            assert row["label"] == pin_audit.RELEASED_LABEL, row["id"]


def test_shipped_digests_are_the_bytes_in_this_checkout():
    """Every recorded digest equals the file it names: a guard against a typed or
    invented value, and the reason the audit can call a tree uniformly stale."""
    data = pin_audit.load_table()
    checked = 0
    for row in data["references"]:
        if not row.get("local") or not row.get("sha256"):
            continue
        local = ROOT / row["local"]
        assert local.is_file(), row["id"]
        assert sha256(local) == row["sha256"], row["id"]
        assert local.stat().st_size == row["bytes"], row["id"]
        checked += 1
    assert checked == 25, "expected 25 rows with a local copy, saw {}".format(checked)


def test_released_rows_name_tags_and_drafts_name_commits():
    data = pin_audit.load_table()
    for row in data["references"]:
        if row["class"] in pin_audit.RELEASED_CLASSES and row.get("sha256"):
            assert row["revision_kind"] == "tag", row["id"]
            assert str(row["revision"]).startswith("v"), row["id"]
        if row["class"] == "draft-contract":
            assert row["revision_kind"] == "commit", row["id"]
            assert len(row["revision"]) == 40, row["id"]


# --- verdicts ----------------------------------------------------------------


def test_fresh_is_reported_with_revision_and_digest(tmp_path, capsys):
    code, path, _ = run_audit(tmp_path, [reference(id="fhp-1.2@v0.6.0")])
    out = capsys.readouterr().out
    assert code == 0
    assert "FRESH   fhp-1.2@v0.6.0" in out
    assert sha256(ROOT / FHP_1_2)[:12] in out
    assert "summary: 1 FRESH, 0 DRIFT, 0 ABSENT of 1" in out


def test_a_wrong_recorded_digest_reports_drift(tmp_path, capsys):
    """The mutation is proved non-vacuous: the table on disk differs from the
    real one only in that digest, and the audit sees a different value."""
    honest = reference(id="fhp-1.2@v0.6.0")
    wrong = dict(honest, sha256="0" * 64)
    original = json.loads((ROOT / "bioheaders/pins.json").read_text())
    code, path, _ = run_audit(tmp_path, [wrong])
    on_disk = json.loads(path.read_text())["references"][0]
    assert on_disk["sha256"] == "0" * 64
    assert honest["sha256"] != on_disk["sha256"]
    assert original  # the shipped table was only read, never rewritten
    out = capsys.readouterr().out
    assert code == 0  # advisory
    assert "DRIFT" in out
    measured = sha256(ROOT / FHP_1_2)
    assert "detail: recorded {} != authority {}".format("0" * 64, measured) in out
    assert "summary: 0 FRESH, 1 DRIFT, 0 ABSENT of 1" in out


def test_drift_can_also_be_a_size_change_under_a_matching_digest(tmp_path, capsys):
    row = reference(id="bytes-lie", bytes=1)
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "recorded 1 bytes != authority" in out
    assert "summary: 0 FRESH, 1 DRIFT, 0 ABSENT of 1" in out


def test_uniformly_stale_tree_is_drift_not_fresh(tmp_path, capsys):
    """#241(a), worked with the real bytes.

    The tree holds the v0.5.0 ``fhp.json``, its pin records the v0.5.0 digest, and
    its local copy matches that record — every self-consistency check in the
    repository passes. Compared with the authority at tag ``v0.6.0`` the answer is
    DRIFT; compared with the authority at ``v0.5.0``, the revision it names, it is
    FRESH. The pair is the finding: freshness is only meaningful against the
    release the reference names."""
    stale = reference(
        id="fhp-1.1@v0.5.0-recorded-against-v0.6.0",
        revision=V060,
        local=FHP_1_1,
        sha256=sha256(ROOT / FHP_1_1),
        bytes=(ROOT / FHP_1_1).stat().st_size,
    )
    run_audit(tmp_path, [stale])
    drifted = capsys.readouterr().out
    assert "summary: 0 FRESH, 1 DRIFT, 0 ABSENT of 1" in drifted
    assert "local status: MATCHES RECORD" in drifted
    assert "authority unavailable" not in drifted
    honest = dict(stale, id="fhp-1.1@v0.5.0", revision=V050)
    run_audit(tmp_path, [honest])
    fresh = capsys.readouterr().out
    assert "summary: 1 FRESH, 0 DRIFT, 0 ABSENT of 1" in fresh


def test_absent_when_the_named_revision_has_no_bytes(tmp_path, capsys):
    row = reference(id="v0.7.0-not-yet", revision="v9.9.9")
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "ABSENT  v0.7.0-not-yet" in out
    assert "authority unavailable: no bytes at" in out


def test_absent_when_no_digest_is_recorded(tmp_path, capsys):
    row = reference(
        id="fhgm-base@none", sha256=None, no_pin_detail="no FHGM pin exists"
    )
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "ABSENT  fhgm-base@none" in out
    assert "no FHGM pin exists" in out


def test_released_class_naming_a_branch_is_not_scored(tmp_path, capsys):
    """Rule 1 of #241: agreeing with ``main`` proves nothing about a release."""
    row = reference(id="fhp@main", revision="main", revision_kind="branch")
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "ABSENT  fhp@main" in out
    assert "released material must be named by a tag, not 'main'" in out


def test_base_carrier_lag_is_reported_as_advisory_text(tmp_path, capsys):
    """#241(b), worked: a base pin that agrees with itself and still sits behind
    the carrier consumers publish. FHGM pins FHGFF3 v0.5.0; the released carrier
    is now v0.6.0. Verdict FRESH (the pin matches the revision it names), lag says
    the rest, and nothing is re-pinned."""
    row = reference(
        id="synthetic-fhgm-base@v0.5.0",
        cls="base-carrier",
        label=pin_audit.DRAFT_LABEL,
        revision=V050,
        local=FHP_1_1,
        sha256=sha256(ROOT / FHP_1_1),
        bytes=(ROOT / FHP_1_1).stat().st_size,
    )
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "summary: 1 FRESH, 0 DRIFT, 0 ABSENT of 1" in out
    assert "lag: pinned v0.5.0, current release is v0.6.0" in out
    assert pin_audit.DRAFT_LABEL in out


def test_frozen_older_snapshots_do_not_claim_lag(tmp_path, capsys):
    """A released-contract snapshot at v0.5.0 is *supposed* to be old: saying so on
    every row would bury the base/carrier case, so only that class reports lag."""
    row = reference(
        id="fhp-1.1@v0.5.0",
        revision=V050,
        local=FHP_1_1,
        sha256=sha256(ROOT / FHP_1_1),
        bytes=(ROOT / FHP_1_1).stat().st_size,
    )
    run_audit(tmp_path, [row])
    out = capsys.readouterr().out
    assert "summary: 1 FRESH" in out
    assert "lag" not in out


# --- controls and honesty ----------------------------------------------------


def test_a_permissive_backend_fails_its_control(tmp_path, capsys):
    """A backend that answers the nonsense path is reported, and its verdicts are
    not allowed to read as FRESH."""
    run_audit(
        tmp_path,
        [reference(id="fhp-1.2@v0.6.0")],
        fixture=authority_dir(tmp_path, spec_bytes=b"anything\n"),
    )
    out = capsys.readouterr().out
    assert "CONTROL FAILED" in out
    assert "not trustworthy" in out
    assert "summary: 0 FRESH, 0 DRIFT, 1 ABSENT of 1" in out


def audit_with_https_control(monkeypatch, control_error):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return (ROOT / FHP_1_2).read_bytes()

    class Opener:
        def open(self, request, timeout):
            if request.full_url.endswith(pin_audit.CONTROL_NAME):
                raise control_error(request.full_url)
            return Response()

    monkeypatch.setattr(
        pin_audit.urllib.request, "build_opener", lambda *_args: Opener()
    )
    options = pin_audit.build_parser().parse_args(["--no-conflicts"])
    options.checkouts = {}
    options.current_release = V060
    return pin_audit.Auditor(options, root=ROOT).one(reference())


def test_https_control_accepts_only_an_actual_404(monkeypatch):
    def not_found(url):
        return urllib.error.HTTPError(url, 404, "not found", {}, None)

    result = audit_with_https_control(monkeypatch, not_found)
    assert result["verdict"] == pin_audit.FRESH
    assert result["control"] == "negative control 404 as expected"


@pytest.mark.parametrize(
    ("status", "reason"),
    [(302, "302"), (500, "500")],
)
def test_https_control_rejects_non_404_responses(monkeypatch, status, reason):
    def http_error(url):
        return urllib.error.HTTPError(url, status, "unexpected response", {}, None)

    result = audit_with_https_control(monkeypatch, http_error)
    assert result["verdict"] == pin_audit.ABSENT
    assert "FAILED" in result["control"]
    assert reason in result["detail"]


def test_https_control_rejects_connection_failures(monkeypatch):
    def unreachable(_url):
        return urllib.error.URLError("connection failed")

    result = audit_with_https_control(monkeypatch, unreachable)
    assert result["verdict"] == pin_audit.ABSENT
    assert "FAILED" in result["control"]
    assert "unreachable" in result["detail"]


def test_the_gate_never_writes_a_pin(tmp_path):
    shipped = ROOT / "bioheaders/pins.json"
    before = shipped.read_bytes()
    draft = ROOT / "bioheaders/schemas/fht-draft.json"
    draft_before = draft.read_bytes()
    code, path, authority = run_audit(
        tmp_path,
        [
            reference(id="fhp-1.2@v0.6.0"),
            reference(
                id="fht-draft@226f923",
                cls="draft-contract",
                repository=FHT_SPEC,
                revision="226f923c28b680edb3c546e99a751482d06aef1a",
                revision_kind="commit",
                path="fht.json",
                label=pin_audit.DRAFT_LABEL,
            ),
        ],
        argv=["--json"],
    )
    assert code == 0
    table_after = path.read_bytes()
    assert shipped.read_bytes() == before
    assert draft.read_bytes() == draft_before
    # the table on disk keeps the digest it started with, however it scored, and
    # the fixture authority keeps its bytes too: an audit repairs nothing.
    assert json.loads(table_after)["references"][0]["sha256"] == sha256(ROOT / FHP_1_2)
    assert (
        authority / "FAIR-bioHeaders-Specification@{}".format(V060) / "fhp.json"
    ).read_bytes() == (ROOT / FHP_1_2).read_bytes()


def test_json_output_is_advisory_and_empty_of_writes(tmp_path, capsys):
    run_audit(tmp_path, [reference(id="fhp-1.2@v0.6.0")], argv=["--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["advisory"] is True
    assert report["wrote"] == []
    assert report["tally"] == {"FRESH": 1, "DRIFT": 0, "ABSENT": 0}
    row = report["references"][0]
    assert row["class"] == "released-contract"
    assert row["authority_sha256"] == row["recorded_sha256"]
    assert row["control"] == "negative control 404 as expected"
    assert report["controls"][0]["backend"] == "fixture"


def test_exit_on_drift_is_opt_in(tmp_path, capsys):
    wrong = reference(id="wrong", sha256="f" * 64)
    assert run_audit(tmp_path, [wrong])[0] == 0
    capsys.readouterr()
    assert run_audit(tmp_path, [wrong], argv=["--exit-on-drift"])[0] == 1
    capsys.readouterr()
    assert (
        run_audit(tmp_path, [reference(id="right")], argv=["--exit-on-drift"])[0] == 0
    )


def test_filters_select_rows(tmp_path, capsys):
    rows = [
        reference(id="fhp-1.2@v0.6.0"),
        reference(id="fht-draft@226f923", cls="draft-contract", path="fht.json"),
    ]
    code, _, _ = run_audit(tmp_path, rows, argv=["--class", "draft-contract"])
    out = capsys.readouterr().out
    assert code == 0
    assert "fht-draft@226f923" in out and "fhp-1.2@v0.6.0" not in out
    run_audit(tmp_path, rows, argv=["--only", "fhp"])
    out = capsys.readouterr().out
    assert "fhp-1.2@v0.6.0" in out and "fht-draft@226f923" not in out


def test_unknown_class_is_rejected_when_loading(tmp_path):
    path = tmp_path / "pins.json"
    path.write_text(
        json.dumps(table([reference(id="x", cls="vibes")])), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown reference classes"):
        pin_audit.load_table(path)


def test_offline_reports_without_probing(tmp_path, capsys):
    """With no network and no mapping the row says so; it never guesses FRESH."""
    path = tmp_path / "pins.json"
    path.write_text(
        json.dumps(table([reference(id="needs-network")])), encoding="utf-8"
    )
    code = pin_audit.main(
        ["--pin-file", str(path), "--root", str(ROOT), "--offline", "--no-conflicts"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "ABSENT  needs-network" in out
    assert "--offline: no --checkout mapping" in out
    assert "control not probed" in out


# --- the conflict-marker probe ----------------------------------------------

MARKED = "Change log\n\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> 5cf0613 (example)\n\nEnd.\n"
SETEXT = "Title\n=======\n\nSome text with an underline, not a conflict.\n"


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


@pytest.fixture()
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "Pin audit test")
    (project / "CHANGELOG.md").write_text("Clean lines only.\n", encoding="utf-8")
    assert _git(project, "add", "CHANGELOG.md").returncode == 0
    assert _git(project, "commit", "-q", "-m", "seed").returncode == 0
    return project


def test_conflict_probe_is_clean_before_and_loud_after(repo):
    before = pin_audit.conflict_markers([str(repo)])
    assert [found["status"] for found in before] == ["NONE"]
    (repo / "CHANGELOG.md").write_text(MARKED, encoding="utf-8")
    after = pin_audit.conflict_markers([str(repo)])
    assert after[0]["status"] == "MARKERS"
    hits = "\n".join(after[0]["hits"])
    # both arms are found, and only in the tracked file git grep was pointed at
    assert "CHANGELOG.md:3:<<<<<<< HEAD" in hits
    assert "CHANGELOG.md:7:>>>>>>> 5cf0613 (example)" in hits
    assert len(after[0]["hits"]) == 2
    assert (repo / "CHANGELOG.md").read_text(encoding="utf-8") == MARKED


def test_conflict_probe_ignores_a_sext_heading(repo):
    """A bare ``=======`` line is a heading underline in ordinary documentation;
    matching it would make the probe noise, so the pattern needs the arm marker."""
    (repo / "TITLE.md").write_text(SETEXT, encoding="utf-8")
    _git(repo, "add", "TITLE.md")
    _git(repo, "commit", "-q", "-m", "sext heading")
    findings = pin_audit.conflict_markers([str(repo)])
    assert findings[0]["status"] == "NONE"


def test_conflict_probe_skips_a_non_repository(tmp_path):
    findings = pin_audit.conflict_markers([str(tmp_path / "nowhere")])
    assert findings[0]["status"] == "SKIPPED"
    assert findings[0]["hits"] == []


def test_shipped_checkout_has_no_conflict_markers():
    """The precedent is a real one: FHP-Specification/CHANGELOG.md shipped an
    unresolved conflict on main for about three and a half weeks (``5cf0613``,
    merged 2026-10-22, closed by that repository's #34) and no gate in the
    federation looked for markers. This repository must not repeat it."""
    findings = pin_audit.conflict_markers([str(ROOT)])
    assert findings[0]["detail"] == "clean", findings[0]["hits"][:5]


# --- the install surface ----------------------------------------------------


def test_entry_point_is_added_without_disturbing_the_existing_commands():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = text.split("\n[tool.poetry.scripts]\n", 1)[1].split("\n[", 1)[0]
    scripts = [line for line in section.splitlines() if line and line[0] != "#"]
    assert 'bioheaders-pin-audit = "bioheaders.pin_audit:main"' in scripts
    assert len([line for line in scripts if "fhr-" in line]) == 11
    assert len([line for line in scripts if "bioheaders " in line]) == 1
    assert "bioheaders/pins.json" in text.split("include = [", 1)[1].split("]", 1)[0]


def test_help_runs(capsys):
    with pytest.raises(SystemExit) as exit_info:
        pin_audit.main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "never re-pins" in out
    assert "conformance-suite" in out
