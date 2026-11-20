# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Published native model against preserved owning cases and recorded 1.2 twins.

Fixture derivation reuses the owning runner, whose bytes are provenance-pinned;
this file neither copies fixtures nor implements a second model validator.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from bioheaders import fhgm, selection

ENTRY = selection.BUNDLED.get("modelContracts", {}).get("FHGM", {})
SPEC = Path(os.environ.get("FHGM_SPECIFICATION", "/nonexistent"))
MANIFEST = SPEC / "development/conformance/manifest.json"
HAVE_SUITE = MANIFEST.is_file()
native_only = pytest.mark.skipif(
    not ENTRY or not HAVE_SUITE,
    reason="published native FHGM contract and pinned FHGM_SPECIFICATION are required",
)
VECTORS = json.loads(MANIFEST.read_bytes())["vectors"] if HAVE_SUITE else []
VECTORS = [v for v in VECTORS if not v.get("retired")]


@pytest.fixture(autouse=True)
def native_contract(monkeypatch):
    monkeypatch.setenv(fhgm.DRAFT_ENV, "1")
    monkeypatch.setenv(fhgm.CONTRACT_ENV, "0.1")


@pytest.fixture(scope="module")
def source():
    pin = ENTRY["suite"]
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == pin["sha256"]
    runner = SPEC / "development/conformance/run_conformance.py"
    matrix = SPEC / "development/conformance/base_matrix.json"
    assert hashlib.sha256(runner.read_bytes()).hexdigest() == pin["runnerSha256"]
    assert hashlib.sha256(matrix.read_bytes()).hexdigest() == pin["matrixSha256"]
    module_spec = importlib.util.spec_from_file_location("fhgm_twin_authority", runner)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module, {v["id"]: v for v in json.loads(matrix.read_bytes())["vectors"]}


def fixture_bytes(relative):
    path = (SPEC / "development/conformance" / relative).resolve()
    assert path.is_relative_to(SPEC.resolve()), "fixture escaped its pinned source"
    return path.read_bytes()


@native_only
@pytest.mark.parametrize("lane", ("sealed", "matrix"))
@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["id"])
def test_published_native_case_layers(vector, lane, source):
    runner, matrix = source
    data = fixture_bytes(vector["file"])
    assert hashlib.sha256(data).hexdigest() == vector["bytes"]["sha256"]
    expected = vector["layers"]
    if lane == "matrix":
        data, _method = runner.twin_bytes(data, expected["checksum"])
        twin = matrix[vector["id"]]
        assert hashlib.sha256(data).hexdigest() == twin["twin"]["sha256"]
        expected = twin["layers"]
    prior = [
        fixture_bytes(p) for p in vector.get("context", {}).get("predecessors", [])
    ]
    report = fhgm.check_models(data, predecessors=prior)
    expected_model = (
        "not-run"
        if vector["id"] == "pointer-into-ambiguous-history"
        else expected["model"]
    )
    assert report.model == expected_model, report.text()
    if vector["expected"] == "invalid":
        assert vector["reason"] in report.text()
    assert report.checksum == expected["checksum"]
    assert report.feature == "not-run"
    assert report.contract["status"] == "released"
    assert report.contract["modelContractVersion"] == "0.1"
    assert report.contract["record"]["sha256"] == ENTRY["files"]["record"]["sha256"]
    assert report.label == "FHGM model 0.1"
    assert "development bytes" not in report.disclosure


def test_native_suite_is_required_when_ci_requests_it():
    if os.environ.get("FHGM_REQUIRE_SUITE"):
        assert ENTRY and HAVE_SUITE
    if not ENTRY or not HAVE_SUITE:
        pytest.skip("published contract or owning suite not configured")
    assert len(VECTORS) == 92
