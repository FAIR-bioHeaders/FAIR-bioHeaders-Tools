# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The assessment data files: rubric, synonym table, reference tables (T004)."""

import json
import os
import re
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from bioheaders.assess import data

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "bioheaders" / "assess" / "data"
# A FAIR-bioHeaders-Specification checkout: $FHR_SPECIFICATION, or a sibling directory.
# The repository was renamed FAIR-bioHeaders-Specification (#108); an old-named
# checkout still works.
SPEC = Path(
    os.environ.get("FHR_SPECIFICATION")
    or next(
        (
            path
            for path in (
                ROOT.parent / "FAIR-bioHeaders-Specification",
                ROOT.parent / "FHR-Specification",
            )
            if path.exists()
        ),
        ROOT.parent / "FAIR-bioHeaders-Specification",
    )
)
CONTRACTS = SPEC / "specs" / "010-fair-header-assessment" / "contracts"

# RDA FAIR Data Maturity Model v1.0, Table 1 (doi:10.15497/rda00050).
RDA_IDS = [
    "RDA-F1-01M", "RDA-F1-01D", "RDA-F1-02M", "RDA-F1-02D", "RDA-F2-01M",
    "RDA-F3-01M", "RDA-F4-01M", "RDA-A1-01M", "RDA-A1-02M", "RDA-A1-02D",
    "RDA-A1-03M", "RDA-A1-03D", "RDA-A1-04M", "RDA-A1-04D", "RDA-A1-05D",
    "RDA-A1.1-01M", "RDA-A1.1-01D", "RDA-A1.2-01D", "RDA-A2-01M", "RDA-I1-01M",
    "RDA-I1-01D", "RDA-I1-02M", "RDA-I1-02D", "RDA-I2-01M", "RDA-I2-01D",
    "RDA-I3-01M", "RDA-I3-01D", "RDA-I3-02M", "RDA-I3-02D", "RDA-I3-03M",
    "RDA-I3-04M", "RDA-R1-01M", "RDA-R1.1-01M", "RDA-R1.1-02M", "RDA-R1.1-03M",
    "RDA-R1.2-01M", "RDA-R1.2-02M", "RDA-R1.3-01M", "RDA-R1.3-01D",
    "RDA-R1.3-02M", "RDA-R1.3-02D",
]  # fmt: skip
REFERENCE_ENTRY_KEYS = {
    "spdx-licenses": {"id", "url", "deprecated"},
    "id-schemes": {"prefix", "pattern", "persistent", "resolver"},
    "formats": {"format", "fairsharing", "version_directive", "versions"},
}


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rubric():
    return _json("rubric.json")


@pytest.fixture(scope="module")
def synonyms():
    return _json("synonyms.json")


def test_rubric_and_synonyms_validate_against_their_schemas(rubric, synonyms):
    Draft202012Validator(_json("rubric.schema.json")).validate(rubric)
    Draft202012Validator(_json("synonyms.schema.json")).validate(synonyms)


@pytest.mark.parametrize("table", sorted(REFERENCE_ENTRY_KEYS))
def test_reference_tables_have_the_documented_shape(table):
    content = _json(f"reference/{table}.json")
    assert set(content) == {"table", "version", "source", "retrieved", "entries"}
    assert content["table"] == table
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", content["retrieved"])
    assert content["entries"]
    for entry in content["entries"]:
        assert set(entry) == REFERENCE_ENTRY_KEYS[table]


def test_spdx_table_is_a_full_release():
    content = _json("reference/spdx-licenses.json")
    ids = {entry["id"] for entry in content["entries"]}
    assert len(ids) == len(content["entries"]) > 500
    assert {"CC-BY-4.0", "CC0-1.0", "MPL-2.0"} <= ids


def test_rubric_has_the_41_rda_indicators_in_table_order(rubric):
    ids = [indicator["id"] for indicator in rubric["indicators"]]
    assert ids == RDA_IDS
    counts = {}
    for indicator in rubric["indicators"]:
        counts[indicator["assessability"]] = (
            counts.get(indicator["assessability"], 0) + 1
        )
    assert counts == {"offline": 25, "online": 4, "not_applicable": 10, "deferred": 2}
    deferred = {
        i["id"]: i["reason"]
        for i in rubric["indicators"]
        if i["assessability"] == "deferred"
    }
    assert deferred == {
        "RDA-I3-01D": "deferred-data-body",
        "RDA-I3-02D": "deferred-data-body",
    }
    upgrades = {i["id"] for i in rubric["indicators"] if i.get("online_upgrade")}
    assert upgrades == {"RDA-F1-01D", "RDA-I2-01M", "RDA-R1.1-03M"}


def test_rubric_references_known_concepts_forms_and_conditions(rubric, synonyms):
    for indicator in rubric["indicators"]:
        ids = set()
        for condition in indicator.get("conditions", []):
            assert condition["concept"] in synonyms["concepts"], indicator["id"]
            if "form" in condition:
                assert condition["form"] in synonyms["forms"], indicator["id"]
            ids.add(condition["id"])
        for rule in ("evidenced_when", "partial_when"):
            value = indicator.get(rule)
            if isinstance(value, dict):
                named = value.get("any_of", value.get("all_of", []))
                assert set(named) <= ids, (indicator["id"], rule)
                if "min" in value:
                    assert value["min"] <= len(ids)
        if indicator["assessability"] in {"offline", "online"}:
            assert indicator["interpretation"].startswith("Adapted")
    for concept in synonyms["concepts"].values():
        for form in concept.get("forms", []):
            assert form in synonyms["forms"]


def test_form_patterns_compile(synonyms):
    for form in synonyms["forms"].values():
        re.compile(form["pattern"])


# A labelled placeholder is <text with a space>; VCF <ID=...> structures have none.
PLACEHOLDER = re.compile(r"<[^<>\s]*\s[^<>]*>")
TEMPLATE_TOKEN = re.compile(
    r"\{(value|related\.(name|length|md5|checksum|seqcol_id|accession))\}"
)
LITERALS = [
    re.compile(r"GC[AF]_\d{9}"),  # assembly accessions
    re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]"),  # ORCID
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # dates
    re.compile(r"\b(CC-BY|CC0|MIT|Apache-2\.0|MPL-2\.0|GPL)"),  # SPDX ids
]


def test_suggestion_templates_use_only_values_related_fields_or_placeholders(rubric):
    for indicator in rubric["indicators"]:
        for convention, template in indicator.get("suggestions", {}).items():
            line = template["line"]
            outside = PLACEHOLDER.sub("", line)
            for token in re.findall(r"\{[^{}\s]*\}", outside):
                assert TEMPLATE_TOKEN.fullmatch(token), (indicator["id"], token)
            for literal in LITERALS:
                assert not literal.search(outside), (indicator["id"], convention, line)
            for placeholder in PLACEHOLDER.findall(line):
                assert "e.g. " in placeholder, (indicator["id"], placeholder)


def test_suggestion_texts_name_their_guideline_item(rubric):
    """Each suggestion points to the item of docs/FAIR_HEADER_GUIDELINE.md (010 T046)."""
    for indicator in rubric["indicators"]:
        for convention, template in (indicator.get("suggestions") or {}).items():
            assert (
                f"(see guideline {indicator['guideline_item']})" in template["text"]
            ), (
                indicator["id"],
                convention,
            )


def test_rubric_attribution(rubric):
    assert re.search(r"10\.15497/rda00050", rubric["attribution"])
    assert "CC BY 4.0" in rubric["attribution"]
    assert rubric["source"]["doi"] == "10.15497/rda00050"


def test_loader_validates_and_reports_versions():
    loaded = data.load()
    assert loaded is data.load()  # cached per process
    assert loaded.rubric_version == "1.1.0"
    assert loaded.synonyms_version == "1.0.0"
    assert set(loaded.reference_versions) == set(REFERENCE_ENTRY_KEYS)
    assert loaded.report_schema["properties"]["report_version"] == {"const": "1.0.0"}


def test_loader_fails_loudly_on_an_invalid_file(monkeypatch):
    original = data._read_json

    def broken(name):
        content = original(name)
        if name == "synonyms.json":
            content = dict(content, synonyms_version="one")
        return content

    monkeypatch.setattr(data, "_read_json", broken)
    with pytest.raises(ValueError, match="synonyms.json"):
        data.load(cache=False)


def test_data_files_are_package_resources():
    root = files("bioheaders.assess").joinpath("data")
    assert root.joinpath("rubric.json").is_file()
    assert root.joinpath("reference").joinpath("formats.json").is_file()


@pytest.mark.parametrize(
    "name",
    ["assessment-report.schema.json", "rubric.schema.json", "synonyms.schema.json"],
)
def test_schemas_are_byte_identical_to_the_specification(name):
    if not CONTRACTS.is_dir():
        pytest.skip("FHR-Specification checkout not found beside this repository")
    assert (DATA / name).read_bytes() == (CONTRACTS / name).read_bytes()
