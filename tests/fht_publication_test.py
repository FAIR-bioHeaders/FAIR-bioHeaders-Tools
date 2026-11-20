# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Published shared FHT: immutable release inputs and normal default selection."""

import copy
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import fhr, selection
from bioheaders.cli import combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/fht-publication"
EXAMPLES = FIXTURES / "examples/fht"
CONFORMANCE = FIXTURES / "conformance/fht-v0.7.0"
MANIFEST = json.loads((CONFORMANCE / "manifest.json").read_bytes())
BIN = Path(sys.executable).parent
SHARED = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/"
)
W3 = "https://w3id.org/fair-bioheaders/fht/v0.7.0"
OWNING = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json"
)


@pytest.fixture(autouse=True)
def normal_support(monkeypatch):
    monkeypatch.delenv("BIOHEADERS_CANDIDATE_FHT", raising=False)
    monkeypatch.delenv(selection.DRAFT_ENV, raising=False)
    monkeypatch.delenv("BIOHEADERS_EXPERIMENTAL_FHGM", raising=False)


def run(*args, cwd=None, env=None, input=None):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        input=input,
    )


def test_actual_released_registry_and_independent_alias_publication():
    table = selection.BUNDLED
    assert table["current"]["release"] == "v0.7.0"
    assert table["releases"]["v0.6.1"] == table["releases"]["v0.6.0"]
    assert "FHT" not in table["releases"]["v0.6.1"]
    assert table["releases"]["v0.7.0"]["FHT"] == "schemas/fht-1.0.json"
    published = table["publication"]["v0.7.0"]
    assert published["commit"] == "623c79fe58edeb238a20fb6de518c62dd69b92bc"
    assert published["archive_identifier"] == "10.5281/zenodo.24385024"
    assert not selection.draft_support_enabled()
    assert selection.parse(W3) == ("FHT", "v0.7.0")
    assert selection.parse(SHARED + "main/fht.json") == ("FHT", "main")


def test_publication_fixture_provenance_is_exact():
    provenance = json.loads((FIXTURES / "provenance.json").read_bytes())
    assert provenance["sourceCount"] == 93 and provenance["exampleTriples"] == 7
    for row in provenance["files"]:
        raw = (ROOT / row["local"]).read_bytes()
        assert raw and hashlib.sha256(raw).hexdigest() == row["sha256"], row["local"]
    raw = (ROOT / "bioheaders/schemas/fht-1.0.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance["schemaSha256"]


@pytest.mark.parametrize(
    "selector", [SHARED + "main/fht.json", SHARED + "v0.7.0/fht.json", W3, W3 + "/"]
)
def test_shared_forms_select_exact_released_contract(selector):
    kind, ref, schema = selection.select(selector)
    assert kind == "FHT" and schema["$id"] == W3


@pytest.mark.parametrize(
    "selector",
    [
        W3.replace("v0.7.0", "v99.0.0"),
        W3.replace("v0.7.0", "v0.6.0"),
        SHARED + "v0.6.0/fht.json",
        SHARED + "refs/tags/v0.7.0/fht.json",
        SHARED + "other-branch/fht.json",
    ],
)
def test_v4_unknown_or_version_without_fht_is_explicit(selector):
    assert selection.parse(selector)[0] == "FHT"
    with pytest.raises(selection.UnsupportedSchemaVersion):
        selection.select(selector)


def test_no_invented_legacy_repo_alias_and_v7_stays_distinct(monkeypatch):
    assert (
        selection.parse(
            "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fht.json"
        )
        is None
    )
    assert selection.parse(OWNING) is None
    monkeypatch.setenv(selection.DRAFT_ENV, "1")
    with pytest.warns(selection.ExperimentalDraftWarning):
        old = selection.select(OWNING)[2]
    new = selection.select(W3)[2]
    assert old["$id"] == OWNING and new["$id"] == W3
    assert old != new


@pytest.mark.parametrize(
    "source", sorted(EXAMPLES.glob("*.fht.json")), ids=lambda p: p.name
)
def test_seven_shared_triples_and_installed_commands(source, tmp_path):
    record = json.loads(source.read_bytes())
    original = fhr()
    original.input_fasta(source.with_suffix(".fasta").read_bytes())
    assert original.__dict__ == record
    original.input_microdata(source.with_suffix(".html").read_text())
    assert original.__dict__ == record
    generated = fhr(**record).output_microdata()
    assert 'itemtype="' + W3 + '"' in generated
    assert "FHT-Specification/main/fht.json" not in generated
    assert "FHT released" in generated
    read = fhr()
    read.input_microdata(generated)
    assert read.__dict__ == record
    fasta = source.with_suffix(".fasta")
    for operation in ["validate", "verify"]:
        result = run(operation, fasta, cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert b"unpublished" not in result.stderr
    for form in ["json", "yaml", "html"]:
        output = tmp_path / ("converted." + form)
        result = run("convert", fasta, output, cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        back = tmp_path / ("back-" + form + ".json")
        result = run("convert", output, back, cwd=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(back.read_bytes()) == record
    body = tmp_path / "stripped.fa"
    result = run("strip", fasta, body, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert body.read_bytes() == strip_header(fasta.read_bytes(), "fasta")
    combined = tmp_path / "combined.fa"
    result = run("combine", source, body, "-o", combined, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert run("verify", combined, cwd=tmp_path).returncode == 0
    assert strip_header(combined.read_bytes(), "fasta") == body.read_bytes()
    streamed = run(
        "verify",
        "-",
        "--type",
        "fasta",
        input=gzip.compress(fasta.read_bytes()),
        cwd=tmp_path,
    )
    assert streamed.returncode == 0, streamed.stderr


@pytest.mark.parametrize("vector", MANIFEST["vectors"], ids=lambda v: v["id"])
def test_all_93_shared_counterparts_are_actually_scored(vector, tmp_path):
    source = CONFORMANCE / vector["file"]
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == vector["sha256"]
    path = tmp_path / source.name
    path.write_bytes(raw)
    result = run("verify", path, cwd=tmp_path)
    link_failure = any(
        link["result"] == "checked-fail" for link in vector.get("parentLink", [])
    )
    assert b"Traceback" not in result.stderr, result.stderr
    if vector["sourceId"] in (
        "fht-fasta-completeness-sum-exceeds-total",
        "fht-fasta-completeness-sum-below-total",
    ):
        assert b"C1" in result.stderr and b"must sum to total" in result.stderr
    if vector["expected"] == "valid" or link_failure:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode == 1, result.stdout + result.stderr
    if vector.get("parentLink"):
        # Frozen historical parents keep owning V7 citations. This explicitly
        # opens that independent lane only for the supplied history receipt.
        environment = dict(os.environ)
        environment[selection.DRAFT_ENV] = "1"
        parents = []
        for link in vector["parentLink"]:
            if link.get("file"):
                parent = FIXTURES / "parents" / link["file"]
                target = tmp_path / parent.name
                target.write_bytes(parent.read_bytes())
                parents.append(target)
        links = run("verify-links", path, *parents, cwd=tmp_path, env=environment)
        assert links.returncode == (3 if link_failure else 0), (
            links.stdout + links.stderr
        )


def test_synthetic_normal_fht_parent_links_without_v7(tmp_path):
    record = json.loads((EXAMPLES / "minimal-de-novo.fht.json").read_bytes())
    parent = tmp_path / "parent.fa"
    parent.write_bytes(combine(fhr(**record), b">p\nACGU\n", "fasta"))
    parsed = fhr()
    parsed.input_fasta(parent.read_bytes())
    child_meta = copy.deepcopy(record)
    child_meta["derivedFrom"] = [
        {
            "headerType": "FHT",
            "relationship": "filteredFrom",
            "checksum": parsed.checksum,
        }
    ]
    child = tmp_path / "child.fa"
    child.write_bytes(combine(fhr(**child_meta), b">c\nAC\n", "fasta"))
    result = run("verify-links", child, parent, cwd=tmp_path)
    assert result.returncode == 0 and b"matched (" in result.stdout, (
        result.stdout + result.stderr
    )
    assert not selection.draft_support_enabled()


@pytest.mark.parametrize(
    "alias", [SHARED + "main/fht.json", SHARED + "v0.7.0/fht.json", W3, W3 + "/"]
)
def test_html_formal_shared_aliases(alias):
    record = json.loads((EXAMPLES / "minimal-de-novo.fht.json").read_bytes())
    page = (
        fhr(**record)
        .output_microdata()
        .replace('itemtype="' + W3 + '"', 'itemtype="' + alias + '"')
    )
    result = fhr()
    result.input_microdata(page)
    assert result.__dict__ == record


@pytest.mark.parametrize(
    "alias",
    [
        SHARED + "v0.6.0/fht.json",
        SHARED + "v9.9.9/fht.json",
        "https://w3id.org/fair-bioheaders/fht/v9.9.9",
        OWNING,
    ],
)
@pytest.mark.parametrize("separate_scope", [False, True])
def test_html_unknown_or_mixed_alias_cannot_hide(alias, separate_scope):
    record = json.loads((EXAMPLES / "minimal-de-novo.fht.json").read_bytes())
    page = fhr(**record).output_microdata()
    if separate_scope:
        page += '<div itemscope itemtype="' + alias + '"></div>'
    else:
        page = page.replace(
            'itemtype="' + W3 + '"', 'itemtype="' + W3 + " " + alias + '"'
        )
    with pytest.raises(ValueError):
        fhr().input_microdata(page)


def test_repeated_family_row_keeps_contract_itemtype(monkeypatch):
    # Synthetic repeat only: this does not assert that v0.8.0 has published.
    table = copy.deepcopy(selection.BUNDLED)
    table["releases"]["v0.8.0"] = copy.deepcopy(table["releases"]["v0.7.0"])
    table["current"]["release"] = "v0.8.0"
    monkeypatch.setattr(selection, "BUNDLED", table)
    record = json.loads((EXAMPLES / "minimal-de-novo.fht.json").read_bytes())
    record["schema"] = W3.replace("v0.7.0", "v0.8.0")
    page = fhr(**record).output_microdata()
    assert 'itemtype="' + W3 + '"' in page
    assert 'itemtype="' + record["schema"] + '"' not in page
    parsed = fhr()
    parsed.input_microdata(page)
    assert parsed.__dict__ == record
