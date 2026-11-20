# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Installed FHT typed HTML: reviewed owning binding, explicit draft gate."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import fhr

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/fht-microdata"


@pytest.fixture(autouse=True)
def draft(monkeypatch):
    monkeypatch.setenv("BIOHEADERS_EXPERIMENTAL_FHT", "1")


@pytest.fixture
def record():
    return json.loads((FIXTURES / "minimal-de-novo.fht.json").read_bytes())


def test_fixtures_at_accepted_owning_digest():
    provenance = json.loads((FIXTURES / "provenance.json").read_bytes())
    for name, digest in provenance["files"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("source", sorted(FIXTURES.glob("*.json"))[:-1])
def test_owning_examples_round_trip(source):
    value = json.loads(source.read_bytes())
    page = fhr(**value).output_microdata()
    result = fhr()
    result.input_microdata(page)
    assert result.__dict__ == value
    assert list(result.__dict__) == list(value)


def test_all_fields_and_zero_round_trip():
    from bioheaders import load_yaml

    raw = (FIXTURES / "fht-fasta-rich.fht.fasta").read_text()
    value = load_yaml(
        "\n".join(line[2:] for line in raw.splitlines() if line.startswith(";~"))
    )
    value = {k: v for k, v in value.items() if not k.startswith("x-")}
    value["documentation"] = 'A <script> & "quoted"\r\ntext'
    value["completeness"].update(
        completeSingle=0, completeDuplicated=0, fragmented=0, missing=1, total=1
    )
    page = fhr(**value).output_microdata()
    assert "<script>" not in page
    read = fhr()
    read.input_microdata(page)
    assert read.__dict__ == value
    assert isinstance(read.completeness["total"], int)
    assert not isinstance(read.completeness["total"], bool)
    assert read.completeness["completeSingle"] == 0
    assert "voucherSpecimen" in read.__dict__


def test_installed_html_commands(record, tmp_path):
    binary = Path(sys.executable).parent / "bioheaders"
    source = tmp_path / "source.json"
    source.write_text(json.dumps(record))
    page = tmp_path / "record.html"
    target = tmp_path / "back.json"
    for args in [
        ("convert", source, page),
        ("validate", page),
        ("convert", page, target),
    ]:
        result = subprocess.run(
            [str(binary), *map(str, args)], cwd=tmp_path, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(target.read_bytes()) == record
    closed = dict(os.environ)
    closed.pop("BIOHEADERS_EXPERIMENTAL_FHT", None)
    result = subprocess.run(
        [str(binary), "validate", str(page)],
        cwd=tmp_path,
        env=closed,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "BIOHEADERS_EXPERIMENTAL_FHT" in result.stderr


@pytest.mark.parametrize(
    "mutation",
    [
        lambda page: page.replace("<table itemscope", "<table hidden itemscope"),
        lambda page: page.replace(
            "<table itemscope", '<table style="display:none" itemscope'
        ),
        lambda page: page.replace(
            'data-fhr-type="string"', 'data-fhr-type="boolean"', 1
        ),
        lambda page: page.replace('itemprop="schema"', 'itemprop="schema schema"', 1),
        lambda page: page.replace(
            "</tbody>", '<tr><td itemprop="schema">wrong</td></tr></tbody>'
        ),
    ],
)
def test_hidden_and_malformed_shapes_rejected(record, mutation):
    with pytest.raises(ValueError):
        fhr().input_microdata(mutation(fhr(**record).output_microdata()))


def test_inert_scope_does_not_override_real_record(record):
    page = fhr(**record).output_microdata()
    injected = "<script>" + page + "</script><template>" + page + "</template>"
    read = fhr()
    read.input_microdata(injected + page)
    assert read.__dict__ == record


@pytest.mark.parametrize(
    "selector",
    ["https://w3id.org/fair-bioheaders/fht/v99.0.0", "https://example.org/fht.json"],
)
def test_unbundled_fixed_and_unknown_selectors_refused(record, selector):
    page = fhr(**record).output_microdata().replace(record["schema"], selector)
    with pytest.raises(ValueError):
        fhr().input_microdata(page)


def test_extension_omission_and_absence(record):
    value = copy.deepcopy(record)
    value["x-unrenderable"] = {"checksum": "opaque", "value": "\0"}
    with pytest.warns(UserWarning, match="omitted"):
        page = fhr(**value).output_microdata()
    read = fhr()
    read.input_microdata(page)
    assert read.__dict__ == record
    assert "documentation" not in read.__dict__
