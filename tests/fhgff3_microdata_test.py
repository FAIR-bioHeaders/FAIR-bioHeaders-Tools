# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHGFF3 HTML microdata: the runtime binding (FAIR-bioHeaders-Tools#104).

The contract is FHGFF3 ``docs/FHGFF3-MICRODATA.md`` (rules H1 to H8) on top of
the shared ``docs/MICRODATA.md`` rules M1 to M5, named as the canonical FHGFF3
binding by that page's "Type-specific bindings" section (published through
FAIR-bioHeaders-Specification#216/#217, 2026-11-10). The conformance oracle is
the fixture set copied into ``examples/fhgff3/`` from the FHGFF3 repository
(commit recorded in ``examples/fhgff3/README.md``); this suite runs against
those packaged copies and never reads a sibling checkout, so the shipped
package verifies its own behavior.
"""

import copy
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path

import pytest
import yaml

from bioheaders import FHGFF3_SCHEMA, fhgff3_microdata, fhp_microdata, fhr

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
EXAMPLES = ROOT / "examples" / "fhgff3"
FHGFF3_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhgff3.json"
)
FHGFF3_ITEMTYPE_OLD_NAME = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHR-Specification/main/fhgff3.json"
)
FHR_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhr.json"
)
FHP_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhp.json"
)
RELEASE_040 = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/v0.4.0/fhgff3.json"
)
RELEASE_040_OLD_NAME = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHR-Specification/v0.4.0/fhgff3.json"
)
RELEASE_040_W3ID = "https://w3id.org/fair-bioheaders/fhgff3/v0.4.0"
RELEASE_050 = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/v0.5.0/fhgff3.json"
)
RELEASE_050_W3ID = "https://w3id.org/fair-bioheaders/fhgff3/v0.5.0"
CHECKSUM = "A" * 43 + "="

# The committed valid HTML fixtures and the canonical record each one pins.
VALID_FIXTURES = {
    "minimal-reference.microdata.fhgff3.html": "minimal-reference",
    "minimal-parent.microdata.fhgff3.html": "minimal-parent",
    "rich-microdata.microdata.fhgff3.html": "rich-microdata",
}
# Each negative fixture and a fragment of the readable rejection it must raise.
NEGATIVE_FIXTURES = {
    # H1: an FHR-itemtype document is not FHGFF3.
    "invalid-itemtype.microdata.fhgff3.html": "exactly one FHGFF3 item scope",
    # H2: a schemaVersion the selected schema does not accept.
    "invalid-unsupported-version.microdata.fhgff3.html": "schemaVersion",
    # H2/V4: a release the reader does not carry is rejected, not fetched.
    "invalid-unknown-release.microdata.fhgff3.html": "unsupported FHGFF3 schema",
    # The typed container of H3/M2: only itemprop=item is an array member.
    "invalid-malformed-nesting.microdata.fhgff3.html": "itemprop=item",
    # H7: a repeated single-valued property becomes a list and fails.
    "invalid-repeated-scalar.microdata.fhgff3.html": "annotation",
    # H7: repeated array containers stay nested and fail.
    "invalid-repeated-array.microdata.fhgff3.html": "metadataAuthor",
    # H6: metadata that exists only inside a script contributes nothing.
    "invalid-unsafe-content.microdata.fhgff3.html": "checksum",
    # H4: neither genome-link alternative.
    "invalid-no-genome-link.microdata.fhgff3.html": "genome link",
    # H4: at most one annotates relationship.
    "invalid-two-annotates.microdata.fhgff3.html": "annotates",
    # H4: an annotates parent must be an FHR genome.
    "invalid-annotates-non-fhr.microdata.fhgff3.html": "FHR",
}


def records():
    found = {}
    for path in sorted(EXAMPLES.glob("*.microdata.fhgff3.json")):
        stem = path.name[: -len(".microdata.fhgff3.json")]
        found[stem] = json.loads(path.read_text(encoding="utf-8"))
    return found


RECORDS = records()


def same_json(left, right):
    """JSON equality that keeps booleans, numbers, strings and containers apart."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            same_json(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(same_json, left, right))
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def loaded(record):
    """A record through the shipped dispatch: write as HTML, read back as metadata."""
    data = fhr()
    data.input_microdata(fhgff3_microdata.write_page(record))
    return data.__dict__


def minimal():
    return RECORDS["minimal-reference"]


def rich():
    return RECORDS["rich-microdata"]


# Packaged fixtures are the conformance oracle.


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_microdata_fixtures_extract_to_their_records(stem):
    data = fhr()
    data.input_microdata(
        (EXAMPLES / f"{stem}.microdata.fhgff3.html").read_text(encoding="utf-8")
    )
    assert same_json(data.__dict__, RECORDS[stem])


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_committed_html_is_the_writer_output(stem):
    expected = fhr(**RECORDS[stem]).output_microdata()
    committed = (EXAMPLES / f"{stem}.microdata.fhgff3.html").read_text(encoding="utf-8")
    assert committed == expected


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_committed_json_is_the_record_writer_output(stem):
    # The binding's canonical JSON (indent=2, non-ASCII literal, trailing
    # newline) is exactly the toolkit's output_json form.
    expected = fhr(**copy.deepcopy(RECORDS[stem])).output_json()
    committed = (EXAMPLES / f"{stem}.microdata.fhgff3.json").read_text(encoding="utf-8")
    assert committed == expected


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_committed_yaml_holds_the_same_values(stem):
    committed = (EXAMPLES / f"{stem}.microdata.fhgff3.yaml").read_text(encoding="utf-8")
    assert same_json(yaml.safe_load(committed), RECORDS[stem])


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_microdata_round_trips_every_example(stem):
    record = RECORDS[stem]
    assert same_json(loaded(record), record)


@pytest.mark.parametrize("stem", VALID_FIXTURES.values())
def test_readable_table_matches_the_embedded_metadata(stem):
    # H8: every row of the committed table equals a row built from the record,
    # so the presentation aid and the metadata cannot drift apart.
    page = (EXAMPLES / f"{stem}.microdata.fhgff3.html").read_text(encoding="utf-8")
    rows = fhgff3_microdata.read_table(page)
    assert rows == fhgff3_microdata.table_rows(RECORDS[stem])
    assert rows
    assert page.startswith('<!doctype html>\n<html lang="en">')
    assert page.endswith("</body></html>\n")
    assert "<caption>FHGFF3 metadata (human summary)</caption>" in page
    assert FHR_ITEMTYPE not in page
    assert FHP_ITEMTYPE not in page


def test_script_markup_in_a_fixture_is_escaped_data():
    page = (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    # The same escaped value appears in the readable table too, and the table
    # says asserted, not verified (H5/H8).
    assert page.count("&lt;script&gt;") >= 2
    assert "Genome reference (asserted)" in page
    assert "producer assertion" in page


@pytest.mark.parametrize("fixture,fragment", NEGATIVE_FIXTURES.items())
def test_negative_fixtures_are_rejected(fixture, fragment):
    page = (EXAMPLES / fixture).read_text(encoding="utf-8")
    with pytest.raises(fhgff3_microdata.MicrodataError) as error:
        fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert fragment in str(error.value)
    # The same rejection through the shipped dispatch (Metadata input).
    with pytest.raises(ValueError):
        fhr().input_microdata(page)


# Record scope and identity (H1): acceptance box 4's core check.


def test_record_scope_uses_the_fhgff3_itemtype():
    page = fhgff3_microdata.write_page(minimal())
    assert f'itemtype="{FHGFF3_ITEMTYPE}"' in page
    assert FHR_ITEMTYPE not in page
    assert FHP_ITEMTYPE not in page
    # The itemtype is the raw-main URL, distinct from the versioned `schema`
    # value the record itself carries (H1/H2).
    assert minimal()["schema"] != FHGFF3_ITEMTYPE


@pytest.mark.parametrize("itemtype", [FHR_ITEMTYPE, FHP_ITEMTYPE])
def test_foreign_itemtype_is_not_an_fhgff3_document(itemtype):
    page = fhgff3_microdata.write_page(minimal(), itemtype=itemtype)
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    # And it never silently reaches the FHGFF3 reader via dispatch.
    assert not fhgff3_microdata.has_fhgff3_scope(page)


def test_fhr_itemtype_with_an_fhgff3_schema_is_rejected_not_read():
    # The packaged invalid-itemtype fixture: FHR itemtype, FHGFF3 `schema`.
    page = (EXAMPLES / "invalid-itemtype.microdata.fhgff3.html").read_text(
        encoding="utf-8"
    )
    with pytest.raises(ValueError, match="FHGFF3 itemtype"):
        fhr().input_microdata(page)


def test_pre_rename_itemtype_is_the_same_identity():
    page = fhgff3_microdata.write_page(minimal(), itemtype=FHGFF3_ITEMTYPE_OLD_NAME)
    assert fhgff3_microdata.has_fhgff3_scope(page)
    assert same_json(fhgff3_microdata.read_page(page, FHGFF3_SCHEMA), minimal())


def test_fhgff3_scope_is_not_an_fhp_or_fhr_document():
    # An FHGFF3-itemtype page is never claimed by the other readers, and the
    # FHR/FHP writers never emit the FHGFF3 identity.
    page = fhr(**minimal()).output_microdata()
    assert not fhp_microdata.has_fhp_scope(page)
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.read_page(page, FHGFF3_SCHEMA)
    assert '<div itemscope itemtype="' in page


def test_two_fhgff3_scopes_are_rejected():
    page = fhgff3_microdata.write_page(minimal())
    scope = page[page.index("<div ") : page.index("</div>") + len("</div>")]
    page = page.replace("</body>", scope + "</body>", 1)
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    with pytest.raises(ValueError):
        fhr().input_microdata(page)


def test_nested_unrelated_scope_does_not_leak_properties():
    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<div itemscope><span itemprop="annotation">Leaked</span></div></div>',
        1,
    )
    assert same_json(fhgff3_microdata.read_page(page, FHGFF3_SCHEMA), minimal())


# Schema selection (H2 with the shared V1-V4 through `selection`).


@pytest.mark.parametrize(
    "selected,version",
    [
        (RELEASE_040, "1.0"),
        (RELEASE_040_OLD_NAME, "1.0"),
        (RELEASE_040_W3ID, "1.0"),
        (
            "https://raw.githubusercontent.com/FAIR-bioHeaders/"
            "FAIR-bioHeaders-Specification/v0.4.1/fhgff3.json",
            "1.0",
        ),
        (
            "https://raw.githubusercontent.com/FAIR-bioHeaders/"
            "FAIR-bioHeaders-Specification/v0.4.2/fhgff3.json",
            "1.0",
        ),
        (RELEASE_050, "1.1"),
        (RELEASE_050_W3ID, "1.1"),
    ],
)
def test_schema_property_selects_an_fhgff3_contract(selected, version):
    record = dict(minimal(), schema=selected, schemaVersion=version)
    assert same_json(loaded(record), record)
    assert same_json(
        fhgff3_microdata.extract(fhgff3_microdata.write_page(record), FHGFF3_SCHEMA),
        record,
    )


def test_raw_main_selects_the_bundled_current_schema():
    record = dict(minimal(), schema=FHGFF3_ITEMTYPE, schemaVersion="1.1")
    assert same_json(
        fhgff3_microdata.extract(fhgff3_microdata.write_page(record), FHGFF3_SCHEMA),
        record,
    )


@pytest.mark.parametrize(
    "schema",
    [
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/v9.9.9/fhgff3.json",
        "https://w3id.org/fair-bioheaders/fhgff3/v9.9.9",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/0123abc/fhgff3.json",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/refs/tags/v0.4.0/fhgff3.json",
        "https://w3id.org/fair-bioheaders/fhr/v0.4.0",
        "https://w3id.org/fair-bioheaders/fhp/v0.4.0",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/v0.4.0/fhr.json",
        FHR_ITEMTYPE,
        FHP_ITEMTYPE,
        "not-a-url",
        None,
    ],
)
def test_unsupported_or_foreign_schema_selection_is_rejected(schema):
    # Unsupported-version: rejected, never read against another schema and
    # never silently treated as FHR (H2, G3).
    record = dict(minimal(), schema=schema)
    page = fhgff3_microdata.write_page(record)
    with pytest.raises(fhgff3_microdata.MicrodataError, match="unsupported FHGFF3"):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)


def test_unsupported_schema_version_is_rejected_by_the_selected_contract():
    record = dict(minimal(), schemaVersion="2.0")
    page = fhgff3_microdata.write_page(record)
    with pytest.raises(fhgff3_microdata.MicrodataError, match="not one of"):
        fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    with pytest.raises(ValueError):
        fhr().input_microdata(page)


def test_a_release_url_without_an_fhgff3_file_is_not_recognized():
    # The selection regexes name fhgff3.json: an FHR release URL never selects
    # the FHGFF3 reader's schema.
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.resolve_schema(
            "https://w3id.org/fair-bioheaders/fhr/v0.4.0", FHGFF3_SCHEMA
        )
    assert (
        fhgff3_microdata.resolve_schema(RELEASE_040, FHGFF3_SCHEMA) is not FHGFF3_SCHEMA
    )


# Data fidelity: ordered arrays, nesting, zeros, absence, escaping
# (H3, H5, H6; the rich fixture is the oracle).


def test_ordered_arrays_keep_their_order():
    rich_record = fhgff3_microdata.read_page(
        (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8"),
        FHGFF3_SCHEMA,
    )
    assert [author["name"] for author in rich_record["metadataAuthor"]] == [
        "Synthetic first author (placeholder)",
        "Synthetic second author (placeholder)",
    ]
    assert rich_record["annotationSoftware"][0]["commandLineOption"] == [
        "--species",
        "human",
        "--flag=<script>",
    ]
    assert [count["featureType"] for count in rich_record["featureCounts"]] == [
        "gene",
        "mRNA",
        "exon",
    ]
    assert [parent["headerType"] for parent in rich_record["derivedFrom"]] == [
        "FHR",
        "FHGFF3",
    ]
    assert list(rich_record) == list(rich())  # field order survives too


def test_nested_sources_parents_and_counts():
    rich_record = fhgff3_microdata.read_page(
        (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8"),
        FHGFF3_SCHEMA,
    )
    assert rich_record["derivedFrom"][1]["accessionID"] == {
        "name": "Synthetic source annotation (placeholder)"
    }
    assert rich_record["source"][0]["name"] == "Synthetic evidence set (placeholder)"
    assert rich_record["source"][0]["sequenceCount"] == 0
    assert rich_record["completeness"]["completeDuplicated"] == 0
    assert rich_record["completeness"]["fragmented"] == 0
    assert rich_record["genomeReference"] == {
        "accession": "SYNTHETIC_ASSEMBLY.1",
        "seqcol_id": "S" * 32,
        "assemblyName": "SyntheticAssembly1",
    }


def test_asserted_genome_and_checksum_parent_stay_separate():
    # H4: the asserted accession/SeqCol object and the checksum-linked FHR
    # parent are distinct properties; a reader never merges them.
    rich_record = loaded(rich())
    assert rich_record["genomeReference"]["accession"] == "SYNTHETIC_ASSEMBLY.1"
    annotates = [
        parent
        for parent in rich_record["derivedFrom"]
        if parent["relationship"] == "annotates"
    ]
    assert len(annotates) == 1
    assert annotates[0]["headerType"] == "FHR"
    assert annotates[0]["checksum"] != rich_record["genomeReference"]["seqcol_id"]
    assert "genomeReference" in RECORDS["minimal-reference"]
    assert "derivedFrom" not in RECORDS["minimal-reference"]
    assert "genomeReference" not in RECORDS["minimal-parent"]
    assert "derivedFrom" in RECORDS["minimal-parent"]


def test_feature_counts_with_a_zero_count_survive_every_form():
    # H5/H6: a zero count is a value. The rich fixture carries exon=0.
    page = (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8")
    assert '<span itemprop="count" data-fhr-type="integer">0</span>' in page
    rich_record = fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert rich_record["featureCounts"][2] == {"featureType": "exon", "count": 0}
    assert same_json(loaded(rich_record), rich_record)


def test_zero_is_a_value_and_absence_is_omission():
    # H6: present-with-0 and omitted are different, in both directions.
    rich_record = loaded(rich())
    assert rich_record["source"][0]["sequenceCount"] == 0
    assert "source" not in loaded(minimal())
    # An empty array is present and distinct from an omitted array.
    record = dict(minimal(), identifier=[])
    assert same_json(loaded(record), record)


def test_false_is_a_value_not_absence():
    # H6: FHGFF3 "1.0" defines no boolean property; the typed form keeps a
    # false value when one is added, and absence stays omission.
    assert fhgff3_microdata._parse_typed("false", "boolean") is False
    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<span itemprop="newFlag" data-fhr-type="boolean">false</span></div>',
        1,
    )
    assert fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)["newFlag"] is False
    round_tripped = fhgff3_microdata.read_page(
        fhgff3_microdata.write_page(dict(minimal(), newFlag=False)), FHGFF3_SCHEMA
    )
    assert round_tripped["newFlag"] is False
    assert "newFlag" not in fhgff3_microdata.read_page(
        fhgff3_microdata.write_page(minimal()), FHGFF3_SCHEMA
    )


def test_escaped_unicode_and_markup_round_trip_as_data():
    # H6 with M2/M3: text is escaped and decoded once; command-line strings are
    # data and are never executed (the rich fixture's --flag=<script>).
    rich_record = loaded(rich())
    assert same_json(rich_record, rich())
    assert "café" in rich_record["annotation"]
    assert "<script>alert(1)</script>" in rich_record["documentation"]
    assert "&" in rich_record["documentation"]
    assert '"double"' in rich_record["documentation"]
    assert "'single'" in rich_record["documentation"]
    assert "測試" in rich_record["documentation"]
    assert "🧬" in rich_record["documentation"]
    page = fhgff3_microdata.write_page(rich_record)
    assert "<script>alert(1)</script>" not in page
    assert "🧬" in page  # non-ASCII stays literal, not escaped away


def test_whitespace_and_numeric_strings_stay_strings():
    # M3: data-fhr-type keeps a number-like string a string.
    record = dict(minimal(), version="1.0", reuseConditions="2")
    assert same_json(loaded(record), record)
    padded = fhgff3_microdata.read_page(
        fhgff3_microdata.write_page(record).replace(
            '<span itemprop="documentation" data-fhr-type="string">',
            '<span itemprop="documentation" data-fhr-type="string">  spaced ',
            1,
        ),
        FHGFF3_SCHEMA,
    )
    assert padded["documentation"].startswith("  spaced ")


def test_untyped_reader_converts_schema_typed_numbers():
    # M3's untyped fallback: without data-fhr-type, schema-defined numeric
    # fields are read as numbers and strings stay strings.
    page = (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8")
    untyped = page.replace(' data-fhr-type="integer"', "")
    rich_record = fhgff3_microdata.read_page(untyped, FHGFF3_SCHEMA)
    assert rich_record["featureCounts"][0]["count"] == 2
    assert isinstance(rich_record["featureCounts"][0]["count"], int)
    assert rich_record["source"][0]["sequenceCount"] == 0
    assert rich_record["schemaVersion"] == "1.0"  # a string field stays a string
    assert isinstance(rich_record["schemaVersion"], str)


def test_typed_scalars_reject_wrong_json():
    page = fhgff3_microdata.write_page(minimal()).replace(
        '<span itemprop="version" data-fhr-type="string">1.0.0</span>',
        '<span itemprop="version" data-fhr-type="integer">not-a-number</span>',
        1,
    )
    with pytest.raises(fhgff3_microdata.MicrodataError, match="integer"):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)


# Repeated properties and containers (H7 with M4).


def test_repeated_scalar_becomes_a_list_and_is_rejected():
    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<span itemprop="annotation" data-fhr-type="string">Second</span></div>',
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert extracted["annotation"] == [minimal()["annotation"], "Second"]
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_repeated_array_container_is_not_flattened():
    page = fhgff3_microdata.write_page(minimal())
    start = page.index('<span itemprop="metadataAuthor"')
    end = page.index("</span></span></span>", start) + len("</span></span></span>")
    container = page[start:end]
    page = page.replace(container, container * 2, 1)
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert len(extracted["metadataAuthor"]) == 2
    assert all(isinstance(item, list) for item in extracted["metadataAuthor"])
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_repeated_single_object_is_invalid():
    # H7 names taxon, genomeReference and completeness among the properties
    # that must not repeat.
    page = fhgff3_microdata.write_page(minimal())
    start = page.index('<span itemprop="taxon"')
    end = page.index("</span></span>", start) + len("</span></span>")
    page = page.replace(page[start:end], page[start:end] * 2, 1)
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_ordinary_repeated_array_properties_form_a_flat_list():
    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<span itemprop="identifier">ex:one</span>'
        '<span itemprop="identifier">ex:two</span></div>',
        1,
    )
    extracted = fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert extracted["identifier"] == ["ex:one", "ex:two"]


# Structure, safety and HTML parsing (M1 to M3, H6).


def test_malformed_array_child_is_rejected():
    page = fhgff3_microdata.write_page(minimal()).replace(
        'itemprop="item" itemscope', 'itemprop="author" itemscope', 1
    )
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)


def test_object_without_itemscope_is_rejected():
    page = fhgff3_microdata.write_page(minimal()).replace(
        '<span itemprop="genomeReference" itemscope',
        '<span itemprop="genomeReference"',
        1,
    )
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)


def test_array_container_with_stray_text_is_rejected():
    page = fhgff3_microdata.write_page(minimal()).replace(
        '<span itemprop="metadataAuthor" data-fhr-type="array">',
        '<span itemprop="metadataAuthor" data-fhr-type="array">text',
        1,
    )
    with pytest.raises(fhgff3_microdata.MicrodataError, match="stray text"):
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)


def test_rejects_an_unclosed_root_scope():
    page = fhgff3_microdata.write_page(minimal())
    truncated = page[: page.rindex("</div>")]
    assert fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    with pytest.raises(fhgff3_microdata.MicrodataError, match="not closed"):
        fhgff3_microdata.read_page(truncated, FHGFF3_SCHEMA)


def test_applies_implied_end_tags():
    page = fhgff3_microdata.write_page(minimal())
    version = '<span itemprop="version" data-fhr-type="string">1.0.0</span>'
    omitted = (
        '<ul><li itemprop="version" data-fhr-type="string">1.0.0'
        '<li itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</ul>'
    )
    extracted = fhgff3_microdata.read_page(
        page.replace(version, omitted, 1), FHGFF3_SCHEMA
    )
    assert extracted["version"] == "1.0.0"
    assert extracted["reuseConditions"] == "CC0-1.0"


def test_omitted_end_tags_match_explicit_end_tags():
    # M2: end tags implied by HTML (p, li, dt/dd, tr, td, th, option) behave
    # exactly like the explicit form (the binding's table of cases).
    page = fhgff3_microdata.write_page(minimal())
    version = '<span itemprop="version" data-fhr-type="string">1.0.0</span>'
    expected_with_conditions = dict(minimal(), reuseConditions="CC0-1.0")
    cases = [
        (
            "p",
            '<p itemprop="version" data-fhr-type="string">1.0.0<span></span>'
            "<div></div>",
            '<p itemprop="version" data-fhr-type="string">1.0.0</p>'
            "<span></span></p><div></div>",
            minimal(),
        ),
        (
            "li",
            '<ul><li itemprop="version" data-fhr-type="string">1.0.0'
            '<li itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</ul>',
            '<ul><li itemprop="version" data-fhr-type="string">1.0.0</li>'
            '<li itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</li></ul>',
            expected_with_conditions,
        ),
        (
            "dt/dd",
            '<dl><dt itemprop="version" data-fhr-type="string">1.0.0'
            '<dd itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</dl>',
            '<dl><dt itemprop="version" data-fhr-type="string">1.0.0</dt>'
            '<dd itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</dd></dl>',
            expected_with_conditions,
        ),
        (
            "tr",
            '<table><tr><td itemprop="version" data-fhr-type="string">1.0.0'
            '<tr><td itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</table>',
            '<table><tr><td itemprop="version" data-fhr-type="string">1.0.0</td></tr>'
            '<tr><td itemprop="reuseConditions" data-fhr-type="string">CC0-1.0'
            "</td></tr></table>",
            expected_with_conditions,
        ),
        (
            "td",
            '<table><tr><td itemprop="version" data-fhr-type="string">1.0.0'
            '<td itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</table>',
            '<table><tr><td itemprop="version" data-fhr-type="string">1.0.0</td>'
            '<td itemprop="reuseConditions" data-fhr-type="string">CC0-1.0'
            "</td></tr></table>",
            expected_with_conditions,
        ),
        (
            "th",
            '<table><tr><th itemprop="version" data-fhr-type="string">1.0.0'
            '<th itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</table>',
            '<table><tr><th itemprop="version" data-fhr-type="string">1.0.0</th>'
            '<th itemprop="reuseConditions" data-fhr-type="string">CC0-1.0'
            "</th></tr></table>",
            expected_with_conditions,
        ),
        (
            "option",
            '<select><option itemprop="version" data-fhr-type="string">1.0.0'
            '<option itemprop="reuseConditions" data-fhr-type="string">CC0-1.0</select>',
            '<select><option itemprop="version" data-fhr-type="string">1.0.0</option>'
            '<option itemprop="reuseConditions" data-fhr-type="string">CC0-1.0'
            "</option></select>",
            expected_with_conditions,
        ),
    ]
    for label, omitted, explicit, expected in cases:
        assert version in page
        omitted_record = fhgff3_microdata.read_page(
            page.replace(version, omitted, 1), FHGFF3_SCHEMA
        )
        explicit_record = fhgff3_microdata.read_page(
            page.replace(version, explicit, 1), FHGFF3_SCHEMA
        )
        assert same_json(omitted_record, expected), label
        assert same_json(explicit_record, expected), label


def test_self_closing_syntax_on_non_void_is_a_start_tag():
    # M2 as the binding applies it: the slash on <span/> is ignored; the
    # element stays open and the following text belongs to it.
    page = fhgff3_microdata.write_page(minimal()).replace(
        '<span itemprop="annotation" data-fhr-type="string">',
        '<span itemprop="annotation" data-fhr-type="string"/>',
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert extracted["annotation"] == minimal()["annotation"]
    fhgff3_microdata.validate_record(extracted, FHGFF3_SCHEMA)

    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<ul itemprop="identifier" data-fhr-type="array">'
        '<li itemprop="item" data-fhr-type="string"/>ex:one'
        '<li itemprop="item" data-fhr-type="string">ex:two</ul></div>',
        1,
    )
    extracted = fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert extracted["identifier"] == ["ex:one", "ex:two"]


def test_genuine_void_elements_are_self_closing():
    documentation = fhgff3_microdata._write_property(
        "documentation", minimal()["documentation"]
    )
    content = escape(minimal()["documentation"], quote=True)

    page = fhgff3_microdata.write_page(minimal()).replace(
        documentation,
        f'<meta itemprop="documentation" content="{content}"/>',
        1,
    )
    assert (
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)["documentation"]
        == minimal()["documentation"]
    )

    page = fhgff3_microdata.write_page(minimal()).replace(
        documentation,
        '<span itemprop="documentation" data-fhr-type="string">'
        "before<br/>after</span>",
        1,
    )
    assert (
        fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)["documentation"]
        == "beforeafter"
    )

    page = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<span itemprop="relatedLink" data-fhr-type="array">'
        '<img itemprop="item" src="https://example.org/synthetic.png"/></span></div>',
        1,
    )
    extracted = fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert extracted["relatedLink"] == ["https://example.org/synthetic.png"]


def test_first_attribute_wins():
    # R9: the first of repeated attributes applies.
    page = fhgff3_microdata.write_page(minimal()).replace(
        '<span itemprop="annotation" data-fhr-type="string">',
        '<span itemprop="annotation" itemprop="notAField" data-fhr-type="string">',
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert "notAField" not in extracted
    assert extracted["annotation"] == minimal()["annotation"]


def test_script_and_handler_content_is_never_metadata():
    # H6: the document stays readable, the script contributes nothing, and a
    # record whose metadata lives only in a script fails validation.
    checksum = '<span itemprop="checksum" data-fhr-type="string">' f"{CHECKSUM}</span>"
    page = fhgff3_microdata.write_page(minimal()).replace(
        checksum,
        '<script>document.getElementById("x").textContent="A";</script>',
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert "checksum" not in extracted
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.validate_record(extracted, FHGFF3_SCHEMA)
    with_handler = fhgff3_microdata.write_page(minimal()).replace(
        "<div itemscope", '<div onclick="run()" itemscope', 1
    )
    assert same_json(fhgff3_microdata.read_page(with_handler, FHGFF3_SCHEMA), minimal())


def test_script_with_itemprop_is_not_a_property():
    checksum = '<span itemprop="checksum" data-fhr-type="string">' f"{CHECKSUM}</span>"
    page = fhgff3_microdata.write_page(minimal()).replace(
        checksum,
        '<script itemprop="checksum" data-fhr-type="string">' f"{CHECKSUM}</script>",
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert "checksum" not in extracted
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    # A property and its descendants inside a script are still inert.
    page = fhgff3_microdata.write_page(minimal()).replace(
        checksum,
        '<script itemprop="voucherSpecimen"><span itemprop="checksum" '
        f'data-fhr-type="string">{CHECKSUM}</span></script>',
        1,
    )
    extracted = fhgff3_microdata.read_page(page, FHGFF3_SCHEMA)
    assert "checksum" not in extracted
    assert "voucherSpecimen" not in extracted


def test_script_and_template_content_is_inert():
    page = fhgff3_microdata.write_page(minimal())
    wrapped = "<template>" + page + "</template>"
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.read_page(wrapped, FHGFF3_SCHEMA)
    with pytest.raises(ValueError):
        fhr().input_microdata(wrapped)
    # A template inside a property contributes no text.
    inside = page.replace(
        "</div>",
        '<span itemprop="reuseConditions" data-fhr-type="string">before'
        "<template>hidden</template>after</span></div>",
        1,
    )
    assert (
        fhgff3_microdata.read_page(inside, FHGFF3_SCHEMA)["reuseConditions"]
        == "beforeafter"
    )


def test_typed_arrays_ignore_inert_children():
    # H6 applies inside typed arrays: script/template items are not metadata.
    record = dict(minimal(), identifier=["example:hidden"])
    page = fhgff3_microdata.write_page(record)
    item = '<span itemprop="item" data-fhr-type="string">example:hidden</span>'
    assert item in page
    for inert in ("script", "template"):
        wrapped = item.replace("span", inert)
        extracted = fhgff3_microdata.read_page(
            page.replace(item, wrapped, 1), FHGFF3_SCHEMA
        )
        assert "example:hidden" not in json.dumps(extracted)
        assert not extracted.get("identifier"), extracted


def test_property_inside_ordinary_property_is_read():
    # M1: a property element that does not open a scope passes its own
    # descendants to the enclosing item.
    documentation = fhgff3_microdata._write_property(
        "documentation", minimal()["documentation"]
    )
    checksum = '<span itemprop="checksum" data-fhr-type="string">' f"{CHECKSUM}</span>"
    page = fhgff3_microdata.write_page(minimal()).replace(checksum, "", 1)
    page = page.replace(
        documentation,
        f'<span itemprop="documentation" data-fhr-type="string">{checksum}</span>',
        1,
    )
    extracted = fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
    assert extracted["checksum"] == CHECKSUM
    assert extracted["documentation"] == CHECKSUM


def test_writer_output_never_executes_data():
    # H6: command-line strings and markup are data; the writer escapes them in
    # the metadata block and the table alike.
    record = dict(
        minimal(),
        documentation='Notes with <script>alert(1)</script> & "quotes".',
        annotationSoftware=[
            {
                "name": "Synthetic tool (placeholder)",
                "commandLineOption": ["--x=<script>alert(1)</script>", "--y='q'"],
            }
        ],
    )
    page = fhr(**record).output_microdata()
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("&lt;script&gt;") >= 2
    assert same_json(loaded(record), record)
    # The readable table presents the same metadata (H8).
    assert fhgff3_microdata.read_table(page) == fhgff3_microdata.table_rows(record)


# The genome link and count assertions are the schema's, not the HTML's (H4/H5).


def test_genome_link_alternatives_are_enforced():
    no_link = {k: v for k, v in minimal().items() if k != "genomeReference"}
    with pytest.raises(fhgff3_microdata.MicrodataError, match="genome link"):
        fhgff3_microdata.validate_record(no_link, FHGFF3_SCHEMA)
    with_reference = dict(
        no_link, genomeReference={"accession": "SYNTHETIC.1", "seqcol_id": "S" * 32}
    )
    assert fhgff3_microdata.validate_record(with_reference, FHGFF3_SCHEMA)
    with_parent = dict(
        no_link,
        derivedFrom=[
            {
                "headerType": "FHR",
                "checksum": "B" * 43 + "=",
                "relationship": "annotates",
            }
        ],
    )
    assert fhgff3_microdata.validate_record(with_parent, FHGFF3_SCHEMA)


def test_annotates_relationship_rules():
    two = dict(
        minimal(),
        derivedFrom=[
            {
                "headerType": "FHR",
                "checksum": "B" * 43 + "=",
                "relationship": "annotates",
            },
            {
                "headerType": "FHR",
                "checksum": "C" * 43 + "=",
                "relationship": "annotates",
            },
        ],
    )
    with pytest.raises(fhgff3_microdata.MicrodataError, match="annotates"):
        fhgff3_microdata.validate_record(two, FHGFF3_SCHEMA)
    non_fhr = dict(
        minimal(),
        derivedFrom=[
            {
                "headerType": "FHGFF3",
                "checksum": "C" * 43 + "=",
                "relationship": "annotates",
            }
        ],
    )
    with pytest.raises(fhgff3_microdata.MicrodataError, match="FHR"):
        fhgff3_microdata.validate_record(non_fhr, FHGFF3_SCHEMA)


def test_negative_feature_count_is_rejected_zero_is_kept():
    # H5: counts are producer assertions bounded only at zero; nothing here
    # reads a GFF3 body.
    negative = dict(minimal(), featureCounts=[{"featureType": "gene", "count": -1}])
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.validate_record(negative, FHGFF3_SCHEMA)
    zero = dict(minimal(), featureCounts=[{"featureType": "gene", "count": 0}])
    assert fhgff3_microdata.validate_record(zero, FHGFF3_SCHEMA)


def test_repeated_completeness_is_rejected():
    # H5: completeness is a single BUSCO object; repeating it is invalid.
    record = dict(minimal(), completeness=rich()["completeness"])
    page = fhgff3_microdata.write_page(record)
    start = page.index('<span itemprop="completeness"')
    end = page.index("</span></span>", start) + len("</span></span>")
    block = page[start:end]
    assert block.endswith('data-fhr-type="integer">3</span></span>')
    page = page.replace(block, block * 2, 1)
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_fhr_only_fields_fail_against_the_fhgff3_schema():
    # H1: genome-only FHR fields are not FHGFF3 properties at all, so an
    # FHGFF3 scope that carries them fails validation against fhgff3.json.
    record = dict(minimal(), genome="Synthetic genome (placeholder)")
    page = fhgff3_microdata.write_page(record)
    with pytest.raises(fhgff3_microdata.MicrodataError):
        fhgff3_microdata.extract(page, FHGFF3_SCHEMA)


def test_reading_establishes_no_checksum_or_link_verification():
    # H6/"Validity and verification": a wrong-but-well-formed checksum reads
    # fine; verification is verify/verify-links, separate toolkit actions.
    record = dict(minimal(), checksum="B" * 43 + "=")
    assert same_json(loaded(record), record)
    # And an fhgff3 `seqcol_id` is not a file checksum the tools recompute;
    # reading never opens a genome or GFF3 file. (There is nothing to open:
    # read_page takes text alone.)


# Microdata carries no extension fields (M5).


def test_microdata_rejects_extension_fields():
    page = fhgff3_microdata.write_page(
        dict(minimal(), **{"x-refget-commonName": "human"})
    )
    assert "x-refget" not in page  # the writer leaves them out (M5)
    extended = fhgff3_microdata.write_page(minimal()).replace(
        "</div>",
        '<span itemprop="x-refget-commonName" data-fhr-type="string">human</span></div>',
        1,
    )
    with pytest.raises(fhgff3_microdata.MicrodataError, match="M5"):
        fhgff3_microdata.read_page(extended, FHGFF3_SCHEMA)
    with pytest.raises(ValueError):
        fhr().input_microdata(extended)


# Hostile input stays bounded (workspace hardening; mirrors the FHP runtime).


def test_hostile_nesting_is_refused_without_crashing():
    # A nesting bomb of nested FHGFF3 object scopes: the bounded recursion
    # fails cleanly (RecursionError in process; the CLI prints its depth
    # message) and never returns metadata.
    depth = 20_000
    scope = (
        '<!doctype html>\n<html lang="en"><body>\n'
        '<div itemscope itemtype="' + FHGFF3_ITEMTYPE + '">'
        '<span itemprop="schema" data-fhr-type="string">'
        "https://w3id.org/fair-bioheaders/fhgff3/v0.4.0</span>"
    )
    scope += '<span itemprop="annotation" itemscope data-fhr-type="object">' * depth
    scope += "</span>" * depth + "</div>\n</body></html>\n"
    with pytest.raises(RecursionError):
        fhgff3_microdata.read_page(scope, FHGFF3_SCHEMA)
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", "-", "--from", "html"],
        input=scope,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "nested too deeply" in result.stderr


# CLI end to end (mirrors the FHP HTML UX).


def bioheaders_command(*args, stdin=None, cwd=None):
    return subprocess.run(
        [str(BIN / "bioheaders"), *[str(arg) for arg in args]],
        input=stdin,
        capture_output=True,
        cwd=cwd,
        text=True,
    )


def test_cli_gff3_to_html_and_back(tmp_path):
    source = EXAMPLES / "annotation.fhgff3.gff3"
    page = tmp_path / "annotation.fhgff3.html"
    result = bioheaders_command("convert", source, page, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    html = page.read_text(encoding="utf-8")
    assert f'itemtype="{FHGFF3_ITEMTYPE}"' in html
    assert FHR_ITEMTYPE not in html
    back = tmp_path / "back.yaml"
    result = bioheaders_command("convert", page, back, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    original = fhr()
    original.input_gff3(source.read_bytes().decode("utf-8"))
    assert same_json(
        yaml.safe_load(back.read_text(encoding="utf-8")), original.__dict__
    )
    forward = tmp_path / "forward.gff3"
    result = bioheaders_command("convert", back, forward, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    reread = fhr()
    reread.input_gff3(forward.read_bytes().decode("utf-8"))
    assert same_json(reread.__dict__, original.__dict__)


def test_cli_record_to_html_round_trips(tmp_path):
    for stem in VALID_FIXTURES.values():
        source = tmp_path / f"{stem}.json"
        source.write_text(
            (EXAMPLES / f"{stem}.microdata.fhgff3.json").read_text("utf-8"), "utf-8"
        )
        page = tmp_path / f"{stem}.html"
        result = bioheaders_command("convert", source, page, cwd=tmp_path)
        assert result.returncode == 0, f"{stem}: {result.stderr}"
        assert page.read_text(encoding="utf-8") == (
            EXAMPLES / f"{stem}.microdata.fhgff3.html"
        ).read_text(encoding="utf-8")
        back = tmp_path / f"{stem}.back.json"
        result = bioheaders_command("convert", page, back, cwd=tmp_path)
        assert result.returncode == 0, f"{stem}: {result.stderr}"
        assert json.loads(back.read_text(encoding="utf-8")) == RECORDS[stem]


def test_cli_validate_accepts_and_rejects_the_fixtures(tmp_path):
    for stem in VALID_FIXTURES.values():
        result = bioheaders_command(
            "validate", EXAMPLES / f"{stem}.microdata.fhgff3.html", cwd=tmp_path
        )
        assert result.returncode == 0, f"{stem}: {result.stderr}"
    for fixture in NEGATIVE_FIXTURES:
        result = bioheaders_command("validate", EXAMPLES / fixture, cwd=tmp_path)
        assert result.returncode == 1, fixture
        assert "FHR: " in result.stderr  # the readable MicrodataError surfaces


def test_cli_jsonld_output_stays_refused(tmp_path):
    # No reviewed FHGFF3 JSON-LD binding exists; this issue does not change
    # that (acceptance box: JSON-LD unsupported).
    for target in ("x.jsonld",):
        result = bioheaders_command(
            "convert", EXAMPLES / "rich.fhgff3.yaml", tmp_path / target, cwd=tmp_path
        )
        assert result.returncode == 1
        assert "not available for FHGFF3 metadata yet" in result.stderr
        assert not (tmp_path / target).exists()
    # The HTML input path refuses JSON-LD output too.
    result = bioheaders_command(
        "convert",
        EXAMPLES / "rich-microdata.microdata.fhgff3.html",
        tmp_path / "y.jsonld",
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "not available for FHGFF3 metadata yet" in result.stderr


def test_cli_streams_html_over_stdin(tmp_path):
    record = rich()
    piped = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "html",
        "--to",
        "json",
        stdin=(EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text("utf-8"),
        cwd=tmp_path,
    )
    assert piped.returncode == 0, piped.stderr
    assert json.loads(piped.stdout) == record
    out = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "json",
        "--to",
        "html",
        stdin=json.dumps(record),
        cwd=tmp_path,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout == (EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_text(
        encoding="utf-8"
    )


def test_cli_gzipped_html_round_trips(tmp_path):
    import gzip

    source = tmp_path / "metadata.fhgff3.html"
    source.write_bytes((EXAMPLES / "rich-microdata.microdata.fhgff3.html").read_bytes())
    zipped = tmp_path / "metadata.fhgff3.html.gz"
    zipped.write_bytes(gzip.compress(source.read_bytes()))
    back = tmp_path / "back.json"
    result = bioheaders_command("convert", zipped, back, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(back.read_text(encoding="utf-8")) == rich()


def test_cli_html_works_outside_the_checkout(tmp_path):
    record = rich()
    source = tmp_path / "metadata.json"
    source.write_text(json.dumps(record), encoding="utf-8")
    page = tmp_path / "metadata.fhgff3.html"
    result = bioheaders_command("convert", source, page, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "<caption>FHGFF3 metadata (human summary)</caption>" in page.read_text(
        encoding="utf-8"
    )
    back = tmp_path / "back.json"
    result = bioheaders_command("convert", page, back, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(back.read_text(encoding="utf-8")) == record
    # GFF3 in, HTML out, and validation of the HTML, away from the checkout.
    result = bioheaders_command(
        "convert",
        EXAMPLES / "annotation.fhgff3.gff3",
        tmp_path / "page.html",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    result = bioheaders_command("validate", tmp_path / "page.html", cwd=tmp_path)
    assert result.returncode == 0, result.stderr


def test_installed_distribution_round_trip(tmp_path):
    """Build the wheel and run the runtime from a clean environment.

    Mirrors release.yml's "Check the built wheels install and run outside the
    checkout" step, so the packaged module and bundled schemas — not the
    checkout — are what answers. Skipped when the build frontend is absent.
    """
    import importlib.util
    import shutil
    import venv

    def available(name):
        try:
            return importlib.util.find_spec(name) is not None
        except ImportError:
            return False

    if not (available("build") or shutil.which("poetry")):
        pytest.skip("no wheel build frontend (build or poetry) available")
    dist = tmp_path / "dist"
    dist.mkdir()
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(dist),
            str(ROOT),
        ],
        capture_output=True,
        text=True,
    )
    if built.returncode != 0:
        built = subprocess.run(
            ["poetry", "build", "--format", "wheel", "-o", str(dist)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
    assert built.returncode == 0, built.stderr + built.stdout
    wheels = sorted(dist.glob("*.whl"))
    assert wheels
    env = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(str(env))
    installed = subprocess.run(
        [str(env / "bin" / "pip"), "install", "--no-deps", "--quiet", str(wheels[-1])],
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    # The parent environment's third-party dependencies (PyYAML, jsonschema,
    # rdflib) are reachable; `bioheaders` itself resolves from the freshly
    # installed wheel, not the checkout or the editable path (the child
    # venv's site-packages precedes PYTHONPATH in sys.path only for
    # installed packages: the editable checkout lives behind a .pth file
    # that PYTHONPATH does not process).
    import sysconfig

    parent_sites = sysconfig.get_paths()["purelib"]
    run_env = dict(os.environ, PYTHONPATH=parent_sites)
    work = tmp_path / "work"
    work.mkdir()
    record_path = work / "record.json"
    record_path.write_text(json.dumps(rich()), encoding="utf-8")
    page = work / "record.html"
    result = subprocess.run(
        [str(env / "bin" / "bioheaders"), "convert", record_path, page],
        capture_output=True,
        text=True,
        cwd=str(work),
        env=run_env,
    )
    assert result.returncode == 0, result.stderr
    assert page.read_text(encoding="utf-8") == (
        EXAMPLES / "rich-microdata.microdata.fhgff3.html"
    ).read_text(encoding="utf-8")
    back = work / "back.yaml"
    result = subprocess.run(
        [str(env / "bin" / "bioheaders"), "convert", page, back],
        capture_output=True,
        text=True,
        cwd=str(work),
        env=run_env,
    )
    assert result.returncode == 0, result.stderr
    assert yaml.safe_load(back.read_text(encoding="utf-8")) == rich()
    rejected = subprocess.run(
        [
            str(env / "bin" / "bioheaders"),
            "validate",
            EXAMPLES / "invalid-unknown-release.microdata.fhgff3.html",
        ],
        capture_output=True,
        text=True,
        cwd=str(work),
        env=run_env,
    )
    assert rejected.returncode == 1
    assert "unsupported FHGFF3 schema version" in rejected.stderr
    # Guard the sys.path assumption: the answered module is the installed one.
    probe = subprocess.run(
        [
            str(env / "bin" / "python"),
            "-c",
            "import json; import bioheaders.fhgff3_microdata as m; "
            'print(json.dumps({"file": m.__file__, "itemtype": m.FHGFF3_ITEMTYPE}))',
        ],
        capture_output=True,
        text=True,
        cwd=str(work),
        env=run_env,
    )
    answer = json.loads(probe.stdout.strip().splitlines()[-1])
    assert str(env) in answer["file"], answer
    assert answer["itemtype"] == FHGFF3_ITEMTYPE


# Selection-layer integration (shared V1-V6 stay single-sourced).


def test_microdata_release_map_matches_the_bundled_registry():
    # The reader's own map and the bundled schema registry cannot drift apart
    # silently: the map names exactly the bundled releases that carry FHGFF3,
    # and every one resolves through `selection` to the FHGFF3 copy of that
    # release, not the current schema and not a fallback (mirrors
    # fhp_microdata and docs/SCHEMA-VERSIONS.md V2 to V4).
    from bioheaders import selection as selection_module

    assert set(fhgff3_microdata.SUPPORTED_RELEASES) == {
        tag
        for tag, types in selection_module.BUNDLED["releases"].items()
        if "FHGFF3" in types
    }
    for release in fhgff3_microdata.SUPPORTED_RELEASES:
        schema = fhgff3_microdata.resolve_schema(
            f"https://w3id.org/fair-bioheaders/fhgff3/{release}", FHGFF3_SCHEMA
        )
        assert (
            schema
            is selection_module.select(
                f"https://w3id.org/fair-bioheaders/fhgff3/{release}"
            )[2]
        )
        accepted = schema["properties"]["schemaVersion"]["enum"]
        assert "1.0" in accepted  # the released contract the binding names
    assert (
        fhgff3_microdata.resolve_schema(FHGFF3_ITEMTYPE, FHGFF3_SCHEMA) is FHGFF3_SCHEMA
    )


def test_selection_rules_are_reused_not_reimplemented():
    # The bundled copies come from the registry: a released schema the reader
    # lists is the frozen bundled file, identical under both paths.
    from bioheaders import selection as selection_module

    kind, ref, schema = selection_module.select(RELEASE_040)
    assert (kind, ref) == ("FHGFF3", "v0.4.0")
    assert schema is fhgff3_microdata.resolve_schema(RELEASE_040, FHGFF3_SCHEMA)
    assert schema["properties"]["schemaVersion"]["enum"] == ["1.0"]
