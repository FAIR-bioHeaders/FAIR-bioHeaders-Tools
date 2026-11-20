# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Draft gene-model records FHGM (FAIR-bioHeaders-Tools#135) - PREP, gated.

Everything here pins the two halves of the lane contract:

- **Off is today.** Without ``BIOHEADERS_EXPERIMENTAL_FHGM`` a carrier whose
  FHGFF3 header holds ``x-fhgm-models`` is an ordinary released FHGFF3 file: the
  extension key is validated by the released contract's R15 rule, ``verify``
  prints ``Checksum verified.`` and nothing else, no FHGM warning is emitted, and
  the model rules are never read. Those are the published semantics, and the gate
  must never change them by default.
- **On is a preview.** With the opt-in the pinned development bytes
  (``schemas/fhgm-model-draft.json`` and ``schemas/fhgm-transport-draft.json``,
  status ``draft``, no release tag, no w3id alias, no ``schemaVersion``) are read,
  the K1-K6 rules run, and the result is printed as its own block, apart from the
  released FHGFF3 header verdict and apart from the GFF3 feature layer, which
  belongs to ``gff3-validator``.

The vectors themselves are consumed by ``tests/fhgm_conformance_test.py`` once an
``FHGM_SPECIFICATION`` checkout at the pinned suite revision is supplied. This
file builds its own synthetic carriers with ``combine`` so every rule is exercised
without any upstream fixture bytes.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import fhgm, fhr, jsonld, selection
from bioheaders.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
V050 = "https://w3id.org/fair-bioheaders/fhgff3/v0.5.0"
V060 = "https://w3id.org/fair-bioheaders/fhgff3/v0.6.0"
RAW_MAIN = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhgff3.json"
)
GFF3_LEAD = b"##gff-version 3\n"
ACCESSION = "SYNTHETIC_ASSEMBLY.1"
SEQCOL = "S" * 32
GENOME = {"accession": ACCESSION, "seqcol_id": SEQCOL}


def record(**overrides) -> dict:
    """One minimal valid record against the pinned draft contract (K2 requires
    ``modelId``, ``modelVersion``, ``featureId`` and ``reference``)."""
    base = {
        "modelId": "model-a",
        "modelVersion": "1",
        "featureId": "toy-a",
        "reference": {"genomeReference": dict(GENOME)},
    }
    base.update(overrides)
    return base


def header(records=None, schema=V060, version="1.2", **extra) -> dict:
    """A released FHGFF3 header, optionally carrying model records.

    Nothing is invented beyond synthetic names: the file-scope fields are the
    released contract's own required set."""
    metadata = {
        "schema": schema,
        "schemaVersion": version,
        "annotation": "Synthetic annotation for the FHGM draft lane tests",
        "taxon": {"name": "Tribolium castaneum"},
        "version": "1",
        "metadataAuthor": [{"name": "FHGM draft lane test author"}],
        "dateCreated": "2026-11-19",
        "genomeReference": dict(GENOME),
    }
    if records is not None:
        metadata[fhgm.MODELS] = records
    metadata.update(extra)
    return metadata


BODY = (
    b"##gff-version 3\n"
    b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy-a\n"
    b"toy\tsynthetic\tmRNA\t10\t30\t.\t+\t.\tID=toy-a-rna;Parent=toy-a\n"
    b"toy\tsynthetic\tgene\t60\t80\t.\t+\t.\tID=toy-b\n"
    b"##FASTA\n> toy-a synthetic transcript\nAUGCAAAAAAU\n"
)


def carrier(metadata, body=BODY) -> bytes:
    """The exact bytes of a carrier: header plus body, checksum computed."""
    return combine(fhr(**copy.deepcopy(metadata)), body, "gff3")


def forced(metadata, body=BODY) -> bytes:
    """Carrier bytes whose header is written without the released validation.

    ``combine`` refuses a record the released contract rejects - which is right for
    users and useless for testing what the lane does *above* that floor. This
    writes the same lines and recomputes the checksum, exactly as the suite's
    vectors were made, so a 1.0 carrier or a superseded citation can reach the
    lane and be reported by it.
    """
    data = fhr(**copy.deepcopy(metadata))
    data.checksum = "A" * 43 + "="
    preliminary = data.output_gff3().encode("utf-8")
    whole = GFF3_LEAD + preliminary + body[len(GFF3_LEAD) :]
    data.checksum = checksum(whole, "gff3")
    return GFF3_LEAD + data.output_gff3().encode("utf-8") + body[len(GFF3_LEAD) :]


def run(*args, env=None, data=None):
    environment = dict(os.environ)
    if env is not None:
        if env:
            environment[fhgm.DRAFT_ENV] = "1"
        else:
            environment.pop(fhgm.DRAFT_ENV, None)
    return subprocess.run(
        [str(BIN / "bioheaders"), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        env=environment,
        input=data,
    )


@pytest.fixture()
def lane(monkeypatch):
    """Open the FHGM draft lane for this test only."""
    monkeypatch.setenv(fhgm.DRAFT_ENV, "1")
    return True


def verdict(data, predecessors=()):
    """The lane over one carrier's exact bytes (the CLI calls the same entry)."""
    return fhgm.check_models(data, predecessors=predecessors)


# --- the gate itself: off is today -------------------------------------------


def test_gate_off_reads_no_draft_bytes(monkeypatch):
    monkeypatch.delenv(fhgm.DRAFT_ENV, raising=False)
    assert not fhgm.draft_support_enabled()


def test_gate_values_match_the_fht_lane_vocabulary(monkeypatch):
    # One vocabulary for both lanes: a value that opens FHT opens FHGM, and a
    # value that opens neither cannot quietly differ.
    for value, enabled in (
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        (" 1 ", True),
        ("", False),
        ("0", False),
        ("off", False),
        ("yesplease", False),
    ):
        monkeypatch.setenv(fhgm.DRAFT_ENV, value)
        monkeypatch.setenv(selection.DRAFT_ENV, value)
        assert fhgm.draft_support_enabled() is enabled, value
        assert selection.draft_support_enabled() is enabled, value


def test_gates_are_independent(monkeypatch):
    monkeypatch.setenv(fhgm.DRAFT_ENV, "1")
    monkeypatch.delenv(selection.DRAFT_ENV, raising=False)
    assert fhgm.draft_support_enabled()
    assert not selection.draft_support_enabled()
    monkeypatch.delenv(fhgm.DRAFT_ENV)
    monkeypatch.setenv(selection.DRAFT_ENV, "1")
    assert selection.draft_support_enabled()
    assert not fhgm.draft_support_enabled()


def test_verify_with_the_gate_closed_says_nothing_about_models(tmp_path):
    data = carrier(header([record()]))
    path = tmp_path / "closed.fhgff3.gff3"
    path.write_bytes(data)
    result = run("verify", path, env=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Checksum verified.\n"
    assert "FHGM" not in result.stdout and "FHGM" not in result.stderr
    # The released FHGFF3 verdict is unchanged by the presence of the extension.
    checked = run("validate", path, env=False)
    assert checked.returncode == 0 and "FHGFF3 metadata is valid." in checked.stdout
    assert "FHGM" not in checked.stdout + checked.stderr


def test_carries_models_only_when_the_key_is_present():
    assert fhgm.carries_models(header([record()]))
    assert not fhgm.carries_models(header())  # a plain released FHGFF3 header
    assert not fhgm.carries_models("text")
    assert not fhgm.carries_models(None)


def test_library_refuses_to_run_with_the_lane_closed(monkeypatch):
    monkeypatch.delenv(fhgm.DRAFT_ENV, raising=False)
    with pytest.raises(fhgm.FHGMLaneError, match="lane is closed"):
        fhgm.check_models(carrier(header([record()])))


# --- the registry: pinned bytes, no release shape ----------------------------


def test_bundled_draft_provenance():
    entry = fhgm.draft_entry()
    assert entry["status"] == "draft"
    assert entry["carrier"] == "FHGFF3"
    assert fhgm.DRAFT_ENV in entry["enable"]
    for kind in ("record", "transport"):
        row = entry["files"][kind]
        assert len(row["revision"]) == 40 and len(row["retrieved"]) == 10
        assert row["repository"] == fhgm.REPOSITORY
        assert row["path"].startswith("development/model/")
        assert "retrieval" in row, f"drafts.FHGM.files.{kind} records no retrieval"
        content = (ROOT / "bioheaders" / row["file"]).read_bytes()
        assert len(content) == row["bytes"], kind
        assert hashlib.sha256(content).hexdigest() == row["sha256"], kind
    suite = entry["suite"]
    assert suite["status"] == "draft, not acceptance"  # rule V7: no release shape
    assert suite["revision"] == "d9d131a02b042023f4784d842a874232fc891069"
    assert suite["fhgmVectors"] == 92
    assert suite["checker"]["path"] == "development/model/validate_fhgm.py"
    registry = entry["registry"]
    assert registry["path"] == "development/model/base-schemas.json"
    assert len(registry["sha256"]) == 64


def test_pinned_bytes_are_the_recorded_commit():
    """The digests are checked, and so is what they belong to.

    ``FHGM_SPECIFICATION`` is an optional checkout, exactly as the FHT lane's
    ``FHT_SPECIFICATION`` is: when it is present the vendored bytes must equal the
    pinned revision's bytes, so a wrong commit sha recorded in good faith fails
    instead of quietly shipping other bytes."""
    spec = os.environ.get("FHGM_SPECIFICATION")
    if not spec or not (Path(spec) / ".git").exists():
        pytest.skip(
            "FHGM_SPECIFICATION names no checkout; the digest pair in "
            "schemas/bundled.json is still verified against the vendored bytes"
        )
    entry = fhgm.draft_entry()
    for kind, row in entry["files"].items():
        result = subprocess.run(
            ["git", "-C", spec, "show", f"{row['revision']}:{row['path']}"],
            capture_output=True,
        )
        assert (
            result.returncode == 0
        ), f"could not read {row['path']} at {row['revision']} from {spec}"
        assert result.stdout == (ROOT / "bioheaders" / row["file"]).read_bytes(), kind
    for base in entry["bases"]:
        result = subprocess.run(
            [
                "git",
                "-C",
                spec,
                "show",
                f"{entry['registry']['revision']}:{entry['registry']['path']}",
            ],
            capture_output=True,
        )
        registry = json.loads(result.stdout)
        rows = {row["ref"]: row for row in registry["bases"]}
        assert rows[base["ref"]]["sha256"] == base["sha256"]
        assert rows[base["ref"]]["schemaUrls"] == base["schemaUrls"]
        assert set(rows) == {row["ref"] for row in entry["bases"]}


def test_base_rows_are_the_bundled_released_snapshots():
    # The base registry names released FHGFF3 bytes; this package already ships
    # them. If the two ever disagree, the lane must refuse rather than judge a
    # carrier by bytes neither authority names.
    bundled = selection.BUNDLED["releases"]
    for row in fhgm.base_registry():
        assert bundled[row["ref"]]["FHGFF3"] == row["file"]
        raw = (ROOT / "bioheaders" / row["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        assert len(raw) == row["bytes"]


def test_lane_has_no_release_shape():
    # Rule V7, checked as data: FHGM is not a header type, is not in the release
    # registry, and gets no version, alias URL or citation form of its own.
    assert "FHGM" not in selection.BUNDLED["current"]["files"]
    assert all("FHGM" not in types for types in selection.BUNDLED["releases"].values())
    text = (ROOT / "bioheaders" / "schemas" / "bundled.json").read_text()
    drafts = json.loads(text)["drafts"]
    assert "schemaVersion" not in drafts["FHGM"]
    assert "citation" not in drafts["FHGM"]
    assert "w3id.org/fair-bioheaders/fhgm" not in text
    assert selection.parse(V060) == ("FHGFF3", "v0.6.0")  # the carrier is FHGFF3
    assert selection.header_type(V060) == "FHGFF3"


def test_draft_warning_names_every_pinned_artifact(lane):
    message = fhgm.draft_warning()
    entry = fhgm.draft_entry()
    assert message is not None
    for row in entry["files"].values():
        assert f"commit {row['revision']}" in message
        assert f"sha256 {row['sha256']} of those bytes" in message
    assert entry["suite"]["revision"] in message
    for banned in ("versions.json", "w3id.org/fair-bioheaders/fhgm"):
        assert banned not in message


def test_digest_drift_is_refused_not_reported(lane, monkeypatch):
    # The guard is proved non-vacuous: with a registry row pointing at a digest
    # that is not the shipped bytes, the lane refuses and warns.
    entry = copy.deepcopy(fhgm.draft_entry())
    entry["files"]["record"]["sha256"] = "0" * 64
    monkeypatch.setattr(fhgm, "draft_entry", lambda: entry)
    with pytest.warns(fhgm.FHGMDraftWarning, match="do not describe these bytes"):
        with pytest.raises(fhgm.FHGMLaneError, match="do not match their recorded"):
            fhgm.pinned("record")


def test_base_digest_drift_is_refused(lane, monkeypatch):
    # Every registered base is corrupted, so whichever one the citation selects,
    # the lane refuses: a base whose shipped bytes disagree with the registry is
    # not the release the carrier was written against.
    rows = copy.deepcopy(fhgm.base_registry())
    for row in rows:
        row["sha256"] = "0" * 64
    monkeypatch.setattr(fhgm, "base_registry", lambda: rows)
    with pytest.raises(fhgm.FHGMLaneError, match="not the bytes that release names"):
        fhgm.check_models(carrier(header([record()])))


# --- K1: transport and base selection ---------------------------------------


@pytest.mark.parametrize(
    "schema,version,ref",
    [
        (V050, "1.1", "v0.5.0"),
        (V060, "1.2", "v0.6.0"),
        (V060, "1.1", "v0.6.0"),  # the v0.6.0 release admits 1.1 carriers (dual base)
        (
            "https://raw.githubusercontent.com/FAIR-bioHeaders/"
            "FAIR-bioHeaders-Specification/v0.5.0/fhgff3.json",
            "1.1",
            "v0.5.0",
        ),
        (
            "https://raw.githubusercontent.com/FAIR-bioHeaders/"
            "FHR-Specification/v0.6.0/fhgff3.json",
            "1.2",
            "v0.6.0",
        ),
    ],
)
def test_registered_citations_select_their_own_bytes(lane, schema, version, ref):
    report = verdict(carrier(header([record()], schema=schema, version=version)))
    assert report.model == fhgm.PASS, report.reason
    assert report.base.endswith(f"@{ref}")
    assert report.header == fhgm.PASS


def test_both_bases_report_the_release_that_judged_them(lane):
    old = verdict(carrier(header([record()], schema=V050, version="1.1")))
    new = verdict(carrier(header([record()], schema=V060, version="1.2")))
    assert old.base_sha256 != new.base_sha256, "one digest produced both verdicts"
    assert old.base_sha256.startswith("20ce320f")
    assert new.base_sha256.startswith("1942be4c")


def test_raw_main_citation_is_refused(lane):
    # Raw main is a moving contract, not a release: K1 refuses it even though
    # rules V1-V3 read it as the current FHGFF3 schema elsewhere.
    report = verdict(carrier(header([record()], schema=RAW_MAIN, version="1.1")))
    assert report.model == fhgm.REJECT
    assert report.rule == "K1"
    assert "which no registered FHGFF3 base release answers to" in report.reason


def test_superseded_release_citation_is_refused(lane):
    report = verdict(
        forced(
            header(
                [record()],
                schema="https://w3id.org/fair-bioheaders/fhgff3/v0.4.0",
                version="1.0",
            )
        )
    )
    assert report.model == fhgm.REJECT
    assert "which no registered FHGFF3 base release answers to" in report.reason


def test_missing_schema_citation_is_refused(lane):
    # A carrier with no citation at all selects no base, so nothing is judged by
    # borrowed bytes: the released layer reads it as FHR (rule V5) and refuses it,
    # and the model layer refuses under K1 rather than picking a release anyway.
    metadata = header([record()])
    del metadata["schema"]
    report = verdict(forced(metadata))
    assert report.model == fhgm.REJECT
    assert report.rule == "K1"
    assert "states no schema URL" in report.reason
    assert report.header == fhgm.REJECT


def test_empty_model_array_is_refused(lane):
    report = verdict(carrier(header([])))
    assert report.model == fhgm.REJECT and report.rule == "K1"
    assert "should be non-empty" in report.reason


def test_version_one_carrier_cannot_hold_the_extension(lane):
    # docs/FORMAT.md R15 admits x- keys from 1.1: the released base rejects it and
    # the transport overlay refuses it, so the floor is observed at both layers.
    report = verdict(forced(header([record()], schema=V050, version="1.0")))
    assert report.header == fhgm.REJECT
    assert report.model == fhgm.REJECT
    assert "x-fhgm-models" in report.reason


# --- K2: whole-record shape, before anything reads a field -------------------


@pytest.mark.parametrize(
    "broken,reason",
    [
        ({"modelVersion": 1}, "is not of type 'string'"),
        ({"reference": "not-an-object"}, "is not of type"),
        ({"zzz": 1}, "Additional properties are not allowed"),
        ({"modelId": "model-a "}, "should not be valid under"),
        ({"featureId": ""}, ""),
        (
            {"evidence": [{"description": "d", "uri": "not a uri"}]},
            "is not a 'uri'",
        ),
        (
            {"evidence": [{"description": "d", "uri": "javascript:void(0)"}]},
            "does not match",
        ),
        (
            {"evidence": [{"description": "d", "uri": "https://user@/"}]},
            "does not match",
        ),
        ({"publication": {"article": "not-a-doi"}}, "does not match"),
    ],
)
def test_record_shape_is_checked_whole(lane, broken, reason):
    fields = dict(record())
    for key, value in broken.items():
        if value is None:
            del fields[key]
        else:
            fields[key] = value
    report = verdict(carrier(header([fields])))
    assert report.model == fhgm.REJECT, fields
    assert report.rule == "K2", report.reason
    if reason:
        assert reason in report.reason


def test_missing_reference_is_k2_even_though_k5_would_agree(lane):
    # Deviation D1: a record without a reference has no shape, so it is K2. K5
    # would find nothing comparable and is never reached.
    fields = record()
    del fields["reference"]
    report = verdict(carrier(header([fields])))
    assert report.rule == "K2" and "'reference' is a required property" in report.reason


# --- K3: identity first ------------------------------------------------------


def test_duplicate_model_ids_are_ambiguous(lane):
    report = verdict(
        carrier(header([record(modelId="model-a"), record(modelId="model-a")]))
    )
    assert report.model == fhgm.REJECT and report.rule == "K3"
    assert "Ambiguous model ID 'model-a'" in report.reason
    assert "NFC normalisation" not in report.reason  # one spelling here


def test_canonically_equal_spellings_collide(lane):
    # A combining accent is equal to its precomposed form under NFC, so two
    # visibly-similar IDs cannot both exist in one snapshot.
    report = verdict(
        carrier(
            header(
                [
                    record(modelId="cafe\u0301-a"),
                    record(modelId="caf\u00e9-a"),
                ]
            )
        )
    )
    assert report.rule == "K3"
    assert "equal under NFC normalisation" in report.reason


def test_identity_is_checked_before_any_record_rule(lane):
    # The ordering guard, exercised: this snapshot is wrong twice over - the two
    # records share an ID (K3) and each targets a transcript row (K4). Only the
    # identity defect may be reported, because a duplicate makes every later
    # per-record verdict unselectable.
    pair = [
        record(modelId="model-a", featureId="toy-a-rna"),
        record(modelId="model-a", featureId="toy-a-rna", modelVersion="2"),
    ]
    report = verdict(carrier(header(pair)))
    assert report.rule == "K3", report.reason
    assert "Ambiguous model ID" in report.reason


def test_shape_precedes_identity(lane):
    # And the other direction: a duplicate whose records are also malformed
    # reports the shape defect first (K2 before K3).
    pair = [
        record(modelId="model-a", modelVersion=1),
        record(modelId="model-a"),
    ]
    report = verdict(carrier(header(pair)))
    assert report.rule == "K2", report.reason


# --- K4: the feature row the record points at --------------------------------


def test_target_must_exist(lane):
    report = verdict(carrier(header([record(featureId="absent")])))
    assert report.rule == "K4" and "must target one local gene row" in report.reason


def test_transcript_row_is_not_a_gene_row(lane):
    report = verdict(carrier(header([record(featureId="toy-a-rna")])))
    assert report.rule == "K4" and "must target one local gene row" in report.reason


def test_gene_row_with_parent_is_not_a_root(lane):
    body = (
        b"##gff-version 3\n"
        b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy-a;Parent=toy-rna\n"
        b"toy\tsynthetic\tmRNA\t10\t30\t.\t+\t.\tID=toy-rna\n"
    )
    report = verdict(carrier(header([record()]), body=body))
    assert report.rule == "K4"
    assert "has a Parent attribute, so it is not a root gene row" in report.reason


def test_duplicate_rows_cannot_be_resolved_once(lane):
    body = (
        b"##gff-version 3\n"
        b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy-a\n"
        b"toy\tsynthetic\tgene\t60\t80\t.\t+\t.\tID=toy-a\n"
    )
    report = verdict(carrier(header([record()]), body=body))
    assert report.rule == "K4" and "must target one local gene row" in report.reason


def test_so_gene_type_resolves(lane):
    body = (
        b"##gff-version 3\n" b"toy\tsynthetic\tSO:0000704\t10\t30\t.\t+\t.\tID=toy-a\n"
    )
    assert verdict(carrier(header([record()]), body=body)).model == fhgm.PASS


def test_percent_encoded_row_id_resolves(lane):
    # The row declares ID=toy%2Da; the decoded value is the identity, so a record
    # naming "toy-a" resolves and one naming the raw spelling does not.
    body = b"##gff-version 3\n" b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy%2Da\n"
    assert verdict(carrier(header([record()]), body=body)).model == fhgm.PASS
    raw = verdict(carrier(header([record(featureId="toy%2Da")]), body=body))
    assert (
        raw.rule == "K4" and "must target one local gene row: 'toy%2Da'" in raw.reason
    )


def test_attribute_key_with_space_declares_no_id(lane):
    body = (
        b"##gff-version 3\n"
        b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tName=x; ID=toy-a\n"
    )
    report = verdict(carrier(header([record()]), body=body))
    assert report.model == fhgm.NOT_RUN
    assert report.rule == "K4" and "untrustworthy feature inventory" in report.reason


def test_empty_parent_refuses_an_indeterminate_root(lane):
    # Deliberately stricter than the pinned reference, which ignores a bare
    # ``Parent=`` and so would call this row a root: an attribute that says
    # "Parent" and names nothing cannot establish either reading. No vector in the
    # pinned suite exercises it, so the 62 recorded outcomes are unaffected.
    body = (
        b"##gff-version 3\n"
        b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy-a;Parent=\n"
    )
    report = verdict(carrier(header([record()]), body=body))
    assert report.model == fhgm.REJECT
    assert report.rule == "K4" and "not a root gene row" in report.reason


def test_truncated_percent_escape_is_refused_not_guessed(lane):
    body = b"##gff-version 3\n" b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy%2\n"
    report = verdict(carrier(header([record()]), body=body))
    assert report.rule == "K4" and "percent escape" in report.reason


def test_undecodable_row_id_is_refused_never_substituted(lane):
    # %FF is not valid UTF-8 on its own. Reading it with errors="replace" would
    # yield U+FFFD, and a record written with that same replacement character
    # would then "resolve" to a row nobody named. The lane refuses instead.
    body = b"##gff-version 3\n" b"toy\tsynthetic\tgene\t10\t30\t.\t+\t.\tID=toy%FF-a\n"
    report = verdict(carrier(header([record(featureId="\ufffd")]), body=body))
    assert report.rule == "K4"
    assert "not valid UTF-8" in report.reason


def test_rows_after_fasta_are_not_features(lane):
    body = b"##gff-version 3\n" b"##FASTA\n" b">toy-a\nACGT\n"
    report = verdict(carrier(header([record()]), body=body))
    assert report.rule == "K4" and "must target one local gene row" in report.reason


def test_malformed_feature_row_is_refused(lane):
    body = b"##gff-version 3\ntoy\tsynthetic\tgene\t10\t30\t.\t+\tID=toy-a\n"
    report = verdict(carrier(header([record()]), body=body))
    assert report.rule == "K4" and "nine columns" in report.reason


# --- K5: the record reference against the file genome link -------------------


def test_contradicting_reference_is_rejected(lane):
    other = {"genomeReference": {"accession": "OTHER.1", "seqcol_id": SEQCOL}}
    report = verdict(carrier(header([record(reference=other)])))
    assert report.rule == "K5" and "contradicts the file genome link" in report.reason


def test_incomparable_reference_forms_are_rejected(lane):
    # An FHR-checksum record in a file linked by accession+digest: never inferred
    # from one another, so this is a rejection, not a fallback.
    linked = header(
        [record(reference={"annotates": "B" * 43 + "="})],
        schema=V050,
        version="1.1",
    )
    report = verdict(carrier(linked))
    assert report.rule == "K5"
    assert "no reference form comparable with the file genome link" in report.reason


def test_fhr_parent_link_and_annotates_agree(lane):
    parent = carrier(header(None))
    metadata = header(
        [record(reference={"annotates": checksum(parent, "gff3")})],
        schema=V050,
        version="1.1",
    )
    del metadata["genomeReference"]
    metadata["derivedFrom"] = [
        {"headerType": "FHR", "relationship": "annotates", "checksum": "A" * 43 + "="}
    ]
    # combine recomputes only the carrier's own checksum; the parent value above
    # is the recorded link this lane compares against, never a substitute for it.
    metadata["derivedFrom"][0]["checksum"] = checksum(parent, "gff3")
    report = verdict(combine(fhr(**metadata), BODY, "gff3"))
    assert report.model == fhgm.PASS, report.reason


# --- K6: a pointer resolves against supplied history only --------------------


def test_pointer_without_supplied_history_is_unresolvable(lane):
    pointer = {
        "annotationChecksum": "m" * 43 + "=",
        "modelId": "model-a",
        "modelVersion": "1",
    }
    report = verdict(carrier(header([record(modelVersion="2", predecessor=pointer)])))
    assert report.rule == "K6"
    assert "the predecessor snapshot is the current file or was not supplied" in (
        report.reason
    )
    assert report.pointers[0]["verdict"] == fhgm.UNRESOLVABLE


def test_pointer_resolves_against_supplied_history(lane):
    prior = [record(modelVersion="1")]
    old = carrier(header(prior, schema=V050, version="1.1"))
    pointer = {
        "annotationChecksum": checksum(old, "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    new = carrier(
        header(
            [record(modelVersion="2", predecessor=pointer)], schema=V050, version="1.1"
        )
    )
    report = verdict(new, predecessors=[old])
    assert report.model == fhgm.PASS, report.reason
    assert report.pointers == [
        {
            "modelId": "model-a",
            "verdict": fhgm.RESOLVABLE,
            "detail": report.pointers[0]["detail"],
        }
    ]
    assert report.pointers[0]["detail"].startswith(
        f"predecessor {checksum(old, 'gff3')[:8]}... version '1'"
    )
    assert report.history == 1
    text = report.text()
    assert "never asserts curator acceptance" in text


def test_pointer_naming_another_model_is_d2(lane):
    old = carrier(header([record(modelVersion="1")], schema=V050, version="1.1"))
    pointer = {
        "annotationChecksum": checksum(old, "gff3"),
        "modelId": "model-b",  # deviation D2: a rename is not admissible in v0.x
        "modelVersion": "1",
    }
    new = carrier(
        header(
            [record(modelVersion="2", predecessor=pointer)], schema=V050, version="1.1"
        )
    )
    report = verdict(new, predecessors=[old])
    assert "the pointer names another model ID 'model-b'" in report.reason


def test_pointer_version_must_match_the_recorded_one(lane):
    old = carrier(header([record(modelVersion="1")], schema=V050, version="1.1"))
    pointer = {
        "annotationChecksum": checksum(old, "gff3"),
        "modelId": "model-a",
        "modelVersion": "9",
    }
    new = carrier(
        header(
            [record(modelVersion="2", predecessor=pointer)], schema=V050, version="1.1"
        )
    )
    report = verdict(new, predecessors=[old])
    assert "the predecessor records version '1', not '9'" in report.reason


def test_revision_reusing_the_predecessor_version(lane):
    old = carrier(header([record(modelVersion="1")], schema=V050, version="1.1"))
    pointer = {
        "annotationChecksum": checksum(old, "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    new = carrier(
        header(
            [record(modelVersion="1", predecessor=pointer)], schema=V050, version="1.1"
        )
    )
    report = verdict(new, predecessors=[old])
    assert "reuses the predecessor model version" in report.reason


def test_pointer_to_the_current_file_is_unresolvable(lane):
    data = carrier(header(None))  # no records: a header used only as its own digest
    pointer = {
        "annotationChecksum": checksum(data, "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    report = verdict(carrier(header([record(predecessor=pointer)])))
    assert "the predecessor snapshot is the current file or was not supplied" in (
        report.reason
    )


def test_history_that_is_itself_ambiguous_rejects_before_resolution(lane):
    old = carrier(
        header(
            [record(modelVersion="1"), record(modelVersion="1")],
            schema=V050,
            version="1.1",
        )
    )
    pointer = {
        "annotationChecksum": checksum(old, "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    new = carrier(
        header(
            [record(modelVersion="2", predecessor=pointer)], schema=V050, version="1.1"
        )
    )
    report = verdict(new, predecessors=[old])
    assert report.rule == "K3" and "Ambiguous model ID" in report.reason


# --- the layers stay apart ---------------------------------------------------


def test_model_rejection_does_not_rewrite_the_released_verdict(tmp_path):
    data = carrier(header([record(featureId="absent")]))
    path = tmp_path / "reject.fhgff3.gff3"
    path.write_bytes(data)
    result = run("verify", path, env=True)
    assert result.returncode == 1
    assert "Checksum verified." in result.stdout  # the released line stands
    assert any(
        line.startswith("FHGM draft lane:") for line in result.stdout.splitlines()
    )
    assert not any(line.startswith("FHGFF3:") for line in result.stdout.splitlines())
    assert "FHGM draft lane: model result: reject (K4)" in result.stdout


def test_feature_layer_is_never_claimed(lane):
    report = verdict(carrier(header([record()])))
    assert report.layers()["feature"] == fhgm.NOT_RUN
    assert "gff3-validator" in report.layers()["feature_reason"]
    assert "gff3-validator" in report.text()


def test_stale_bytes_reject_under_the_boundary_not_as_a_model_gap(lane):
    # The suite records this case as B1: the released schema accepts the header and
    # only the digest says the bytes changed. It is reported as a rejection of the
    # model layer under B1, never as a K-rule finding.
    text = carrier(header([record()]))
    broken = text.replace(b"ID=toy-a", b"ID=toy-z")
    assert broken != text, "the edit changed no bytes: the test proves nothing"
    report = verdict(broken)
    assert report.checksum == "stale"
    assert report.model == fhgm.REJECT and report.rule == "B1"
    assert "File checksum mismatch" in report.reason


def test_oversized_carrier_reports_not_run(lane, tmp_path, monkeypatch):
    # The bound is behaviour: past it the released verdict still runs and the
    # model layer says what was not done, instead of an unbounded read. The CLI
    # shrinks it the way a memory-limited run would, through the environment.
    path = tmp_path / "big.fhgff3.gff3"
    path.write_bytes(carrier(header([record()])))
    environment = dict(
        os.environ, **{fhgm.DRAFT_ENV: "1", "BIOHEADERS_FHGM_MAX_BYTES": "200"}
    )
    result = subprocess.run(
        [str(BIN / "bioheaders"), "verify", str(path)],
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert "Checksum verified." in result.stdout
    assert "model result: not-run" in result.stdout
    closed = run("verify", path, env=True)  # the default bound reads this file fine
    assert "model result: pass" in closed.stdout


def test_predecessor_option_needs_the_lane(tmp_path):
    old = tmp_path / "old.fhgff3.gff3"
    old.write_bytes(carrier(header([record()], schema=V050, version="1.1")))
    new = tmp_path / "new.fhgff3.gff3"
    pointer = {
        "annotationChecksum": checksum(old.read_bytes(), "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    new.write_bytes(
        carrier(header([record(modelVersion="2", predecessor=pointer)], V050, "1.1"))
    )
    closed = run("verify", new, "--fhgm-predecessor", old, env=False)
    assert closed.returncode == 1
    assert "needs the FHGM draft lane" in closed.stderr
    wrong = run("validate", new, "--fhgm-predecessor", old, env=True)
    assert wrong.returncode == 2 or "unrecognized arguments" in wrong.stderr


def test_predecessor_chain_resolves_from_the_cli(tmp_path):
    old = tmp_path / "v1.fhgff3.gff3"
    old.write_bytes(carrier(header([record()], schema=V050, version="1.1")))
    new = tmp_path / "v2.fhgff3.gff3"
    pointer = {
        "annotationChecksum": checksum(old.read_bytes(), "gff3"),
        "modelId": "model-a",
        "modelVersion": "1",
    }
    new.write_bytes(
        carrier(header([record(modelVersion="2", predecessor=pointer)], V050, "1.1"))
    )
    alone = run("verify", new, env=True)
    assert alone.returncode == 1 and "was not supplied" in alone.stdout
    chained = run("verify", new, "--fhgm-predecessor", old, env=True)
    assert chained.returncode == 0, chained.stderr
    assert "model result: pass" in chained.stdout
    assert "predecessor is resolvable" in chained.stdout


def test_draft_warning_is_labelled_fhgm_and_not_fhgff3(tmp_path):
    path = tmp_path / "warn.fhgff3.gff3"
    path.write_bytes(carrier(header([record()])))
    result = run("verify", path, env=True)
    assert result.returncode == 0, result.stderr
    assert any(
        line.startswith("FHGM: warning:") for line in result.stderr.splitlines()
    ), result.stderr
    assert not any(
        line.startswith("FHT: warning:") for line in result.stderr.splitlines()
    )
    assert not any(line.startswith("FHR:") for line in result.stderr.splitlines())


def test_released_types_unaffected_by_the_open_lane(tmp_path):
    genome = json.loads((ROOT / "examples" / "example.fhr.json").read_text())
    path = tmp_path / "g.fhr.fasta"
    path.write_bytes(combine(fhr(**genome), b">chr1\nACGTACGT\n", "fasta"))
    result = run("verify", path, env=True)
    assert result.returncode == 0, result.stderr
    assert "FHGM" not in result.stdout + result.stderr
    annotation = tmp_path / "a.fhgff3.gff3"
    plain = header(None)  # released FHGFF3, no model records
    annotation.write_bytes(carrier(plain))
    checked = run("verify", annotation, env=True)
    assert checked.returncode == 0 and checked.stdout == "Checksum verified.\n"


def test_validate_reports_no_model_block(tmp_path):
    # The lane lives in `verify`, which reads the whole carrier. `validate` reads
    # the header block, where K4 has no feature rows to resolve, so it must say
    # nothing about models rather than half an answer: this is the evidence behind
    # the matrix cell that marks (FHGM, read) as not the lane's input.
    path = tmp_path / "v.fhgff3.gff3"
    path.write_bytes(carrier(header([record(featureId="absent")])))
    result = run("validate", path, env=True)
    assert result.returncode == 0, result.stderr
    assert "FHGFF3 metadata is valid." in result.stdout
    assert "FHGM" not in result.stdout + result.stderr


def test_documents_are_not_the_lanes_input(tmp_path):
    # A metadata document can carry the extension key, and the released contract
    # admits it; the lane still does not read it, because a document has no feature
    # rows and no file-bound checksum to compare against.
    metadata = header([record(featureId="absent")])
    metadata["checksum"] = checksum(carrier(metadata), "gff3")
    document = tmp_path / "meta.json"
    document.write_text(json.dumps(metadata), "utf-8")
    result = run("validate", document, env=True)
    assert result.returncode == 0, result.stderr
    assert "FHGM" not in result.stdout + result.stderr


def test_verify_links_makes_no_model_comparison(tmp_path):
    # A predecessor pointer is not a parent link. verify-links answers derivedFrom
    # and genomeReference against files on disk; it must not read the model array as
    # a parent claim, and it must not resolve one either.
    pointer = {
        "annotationChecksum": "m" * 43 + "=",
        "modelId": "model-a",
        "modelVersion": "1",
    }
    path = tmp_path / "linked.fhgff3.gff3"
    path.write_bytes(carrier(header([record(modelVersion="2", predecessor=pointer)])))
    result = run("verify-links", path, env=True)
    assert result.returncode == 0, result.stderr
    assert "FHGM" not in result.stdout + result.stderr


def test_assess_does_not_score_model_records(tmp_path):
    # `assess` scores the released header. The model lane is separate, so an
    # assessment of the same carrier must not contain an FHGM section.
    path = tmp_path / "a.fhgff3.gff3"
    path.write_bytes(carrier(header([record()])))
    result = run("assess", path, "--format", "text", env=True)
    assert result.returncode == 0, result.stderr
    assert "FHGM" not in result.stdout + result.stderr


# --- the extension data and the FHGFF3 identity survive round trips ---------


def test_records_survive_json_and_yaml_documents(lane, tmp_path):
    data = carrier(header([record(), record(modelId="model-b", featureId="toy-b")]))
    source = tmp_path / "round.fhgff3.gff3"
    source.write_bytes(data)
    as_json = tmp_path / "meta.json"
    as_yaml = tmp_path / "meta.yaml"
    assert run("convert", source, as_json, env=True).returncode == 0
    assert run("convert", source, as_yaml, env=True).returncode == 0
    kept = json.loads(as_json.read_text())
    assert (
        kept[fhgm.MODELS]
        == yaml.safe_load(as_yaml.read_text(encoding="utf-8"))[fhgm.MODELS]
    )
    assert kept[fhgm.MODELS][1]["modelId"] == "model-b"
    # The identity the released contract carries does not move either.
    assert kept["schema"] == V060 and kept["schemaVersion"] == "1.2"
    body = strip_header(data, "gff3")
    again = tmp_path / "again.fhgff3.gff3"
    assert (
        run(
            "combine", as_json, body_path(source, tmp_path), "-o", again, env=True
        ).returncode
        == 0
    )
    rechecked = run("verify", again, env=True)
    assert rechecked.returncode == 0, rechecked.stderr
    assert "model result: pass" in rechecked.stdout
    assert run("strip", again, tmp_path / "payload.gff3", env=True).returncode == 0
    assert (tmp_path / "payload.gff3").read_bytes() == body


def body_path(source, tmp_path):
    payload = tmp_path / f"payload-{source.stat().st_ino}.gff3"
    payload.write_bytes(strip_header(source.read_bytes(), "gff3"))
    return payload


def test_microdata_and_jsonld_carry_no_model_records(lane, tmp_path):
    # The M5/J9 boundary, as measured output rather than a promise: an extension
    # field is left out of every JSON-LD and microdata form, so an FHGM record can
    # never reach a schema.org or microdata consumer under FHGFF3's identity.
    source = tmp_path / "carrier.fhgff3.gff3"
    source.write_bytes(carrier(header([record()])))
    page = tmp_path / "page.html"
    written = run("convert", source, page, env=True)
    assert written.returncode == 0, written.stderr
    assert "extension fields are not written to HTML microdata: x-fhgm-models" in (
        written.stderr
    )
    text = page.read_text(encoding="utf-8")
    assert "x-fhgm-models" not in text and "model-a" not in text
    refused = tmp_path / "out.jsonld"
    rejected = run("convert", source, refused, env=True)
    assert rejected.returncode == 1
    assert "JSON-LD output is not available for FHGFF3" in rejected.stderr
    assert not refused.exists()
    # And the reader side: the key is refused on the way in, never dropped in
    # silence, so a microdata page cannot smuggle model records into a header that
    # claims to carry none.
    released = json.loads(
        (
            ROOT / "examples/r4-current" / "fhgff3" / "minimal-reference.fhgff3.json"
        ).read_text()
    )
    page = fhr(**released).output_microdata()
    smuggled = page.replace(
        "</div>",
        f'<span itemprop="{fhgm.MODELS}" data-fhr-type="string">[]</span></div>',
        1,
    )
    assert (
        smuggled != page
    ), "the injected key changed no bytes: the test proves nothing"
    with pytest.raises(ValueError, match="M5"):
        fhr().input_microdata(smuggled)


def test_fhr_jsonld_omits_the_model_records_it_was_handed(lane):
    # The same boundary on the FHR side: a top-level x- key never reaches JSON-LD,
    # even when its value would be valid FHGFF3 model data.
    genome = json.loads((ROOT / "examples" / "example.fhr.json").read_text())
    document = fhr(**genome, **{fhgm.MODELS: [record()]})
    document.fhr_validate()
    written = json.loads(document.output_jsonld())
    assert fhgm.MODELS not in json.dumps(written)
    assert fhgm.MODELS in json.dumps(document.__dict__)
    assert jsonld.CONTEXT  # the FHR context is unchanged by the draft lane
