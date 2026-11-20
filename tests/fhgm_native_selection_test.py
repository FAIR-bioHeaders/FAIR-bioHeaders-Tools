# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Native model selection and historical V7 are distinct from header selection."""

import copy

import pytest

from bioheaders import fhgm, selection


@pytest.fixture()
def synthetic_native(monkeypatch):
    """Synthetic registry authority: never presented as a published artifact."""
    entry = copy.deepcopy(fhgm.draft_entry())
    entry.update(
        status="released",
        modelContractVersion="0.1",
        release="v0.8.0",
        identifier="https://w3id.org/fair-bioheaders/model-contracts/fhgm/0.1",
    )
    monkeypatch.setitem(selection.BUNDLED, "modelContracts", {"FHGM": entry})
    monkeypatch.delenv(fhgm.CONTRACT_ENV, raising=False)
    return entry


def test_native_model_does_not_change_header_registry(synthetic_native):
    assert fhgm.active_entry() is synthetic_native
    assert "FHGM" not in selection.BUNDLED["current"]["files"]
    assert fhgm.lane_label() == "FHGM model 0.1"
    assert "native FHGM model contract 0.1" in fhgm.draft_warning()
    assert "development bytes" not in fhgm.draft_warning()


def test_explicit_historical_snapshot_keeps_v7_disclosure(
    monkeypatch, synthetic_native
):
    monkeypatch.setenv(fhgm.CONTRACT_ENV, "draft")
    assert fhgm.active_entry() is fhgm.draft_entry()
    assert fhgm.lane_label() == "FHGM draft lane"
    assert "development bytes" in fhgm.draft_warning()


def test_unknown_model_contract_is_not_substituted(monkeypatch, synthetic_native):
    monkeypatch.setenv(fhgm.CONTRACT_ENV, "0.2")
    with pytest.raises(fhgm.FHGMLaneError, match="unsupported FHGM model contract"):
        fhgm.active_entry()


def test_explicit_native_requires_bundled_authority(monkeypatch):
    monkeypatch.setitem(selection.BUNDLED, "modelContracts", {})
    monkeypatch.setenv(fhgm.CONTRACT_ENV, "0.1")
    with pytest.raises(fhgm.FHGMLaneError, match="not bundled"):
        fhgm.active_entry()


def test_native_publication_does_not_open_implementation_gate(
    monkeypatch, synthetic_native
):
    monkeypatch.delenv(fhgm.DRAFT_ENV, raising=False)
    assert not fhgm.draft_support_enabled()
    with pytest.raises(fhgm.FHGMLaneError, match="is closed"):
        fhgm.check_models(b"")


def test_model_report_keeps_unrun_feature_layer(synthetic_native):
    report = fhgm.FHGMReport()
    assert report.layers()["model"] == fhgm.NOT_RUN
    assert report.layers()["feature"] == fhgm.NOT_RUN
    assert all(line.startswith("FHGM model 0.1:") for line in report.lines())
    assert "not-run" in report.text()


def test_published_native_bytes_and_provenance_are_separate_from_v7(monkeypatch):
    import hashlib
    import json

    native = selection.BUNDLED.get("modelContracts", {}).get("FHGM")
    if not native:
        pytest.skip("native publication has not yet been deliberately bundled")
    monkeypatch.setenv(fhgm.CONTRACT_ENV, "0.1")
    _name, raw, row = fhgm.pinned("record")
    assert (
        hashlib.sha256(raw).hexdigest()
        == "56c0a5a91e9e56c50c0919a375505c01f52bce5f1792841c40b87b1cd18e9336"
    )
    assert json.loads(raw)["$id"] == native["identifier"]
    assert row["release"] == native["release"] == "v0.8.0"
    assert row["revision"] == selection.BUNDLED["publication"]["v0.8.0"]["commit"]
    assert (
        native["files"]["record"]["file"]
        != fhgm.draft_entry()["files"]["record"]["file"]
    )
    assert (
        native["files"]["record"]["sha256"]
        != fhgm.draft_entry()["files"]["record"]["sha256"]
    )
    assert set(selection.BUNDLED["current"]["files"]) == {"FHR", "FHP", "FHGFF3", "FHT"}
    assert (
        selection.BUNDLED["releases"]["v0.8.0"]
        == selection.BUNDLED["releases"]["v0.7.0"]
    )
