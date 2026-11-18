# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""HTML parsing details shared by the FHR, FHP and FHGFF3 microdata readers.

- Script and template contents are inert for every family (H6, M2): the FHR
  reader used to read properties and text inside them.
- Raw CR is normalised to LF and NUL is dropped from text (U+FFFD in attribute
  values), as HTML input preprocessing and tree construction do.
- An FHGFF3 page is parsed once per self-closing policy, not three times, and
  the parser has a size cap for direct API calls.
"""

import json
from pathlib import Path

import pytest

from bioheaders import (
    FHGFF3_SCHEMA,
    FHP_SCHEMA,
    _microdata,
    fhgff3_microdata,
    fhp_microdata,
    fhr,
)

ROOT = Path(__file__).resolve().parents[1]
FHR_PAGE = (ROOT / "examples/example.microdata.fhr.html").read_text()
pytestmark = pytest.mark.filterwarnings("ignore:FHGFF3 HTML microdata is experimental")


def record(path):
    return json.loads((ROOT / "examples" / path).read_text())


def read_fhr(page):
    data = fhr()
    data.input_microdata(page)
    return json.loads(data.output_json())


EXPECTED_FHR = read_fhr(FHR_PAGE)
FUNDING = '<span itemprop="funding" data-fhr-type="string">funding</span>'


@pytest.mark.parametrize(
    "inert",
    [
        '<template><span itemprop="funding" data-fhr-type="string">x</span></template>',
        '<template></span></div><span itemprop="masking">x</span></template>',
        '<script>document.write("<span itemprop=funding>x</span>")</script>',
    ],
)
def test_fhr_reader_ignores_script_and_template_content(inert):
    assert FUNDING in FHR_PAGE
    assert read_fhr(FHR_PAGE.replace(FUNDING, FUNDING + inert)) == EXPECTED_FHR


def test_fhr_reader_ignores_script_text_inside_a_value():
    page = FHR_PAGE.replace(">funding<", ">fund<script>EVIL</script>ing<")
    assert read_fhr(page) == EXPECTED_FHR


def test_fhr_and_fhp_readers_agree_on_template_content():
    data = record("fhp/minimal-predicted.fhp.json")
    page = fhp_microdata.write_page(data)
    hidden = '<template><span itemprop="version">9.9</span></template>'
    page = page.replace(
        'data-fhr-type="string">1.0</span>',
        'data-fhr-type="string">1.0</span>' + hidden,
        1,
    )
    assert hidden in page
    assert fhp_microdata.extract(page, FHP_SCHEMA) == data


CASES = [
    (fhp_microdata, FHP_SCHEMA, "fhp/minimal-predicted.fhp.json", "proteome"),
    (
        fhgff3_microdata,
        FHGFF3_SCHEMA,
        "fhgff3/minimal-reference.microdata.fhgff3.json",
        "annotation",
    ),
]


@pytest.mark.parametrize("module,schema,path,field", CASES)
@pytest.mark.parametrize(
    "raw,expected",
    [("A\r\nB\rC", "A\nB\nC"), ("A\0B", "AB"), ("A&#13;B", "A\rB")],
)
def test_raw_cr_and_nul_in_values_read_as_html(
    module, schema, path, field, raw, expected
):
    data = record(path)
    data[field] = "PLACEHOLDER"
    page = module.write_page(data).replace("PLACEHOLDER", raw)
    assert module.extract(page, schema)[field] == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("A\r\nB\rC", "A\nB\nC"), ("A\0B", "AB"), ("A&#13;B", "A\rB")],
)
def test_fhr_reader_reads_raw_cr_and_nul_the_same_way(raw, expected):
    page = FHR_PAGE.replace(">funding<", f">{raw}<")
    assert read_fhr(page)["funding"] == expected


def test_nul_in_an_attribute_value_reads_as_replacement_character():
    node = _microdata._TreeBuilder()
    node.feed('<span itemprop="a\0b"></span>')
    assert node.root.children[0].itemprop == ["a�b"]


@pytest.mark.parametrize(
    "module,family", [(fhp_microdata, "FHP"), (fhgff3_microdata, "FHGFF3")]
)
def test_unsupported_release_message_names_main(module, family):
    with pytest.raises(module.MicrodataError) as error:
        module._release_schema("v9.9.9")
    assert f"this reader has {family} schemas for main and releases v0.4.0" in str(
        error.value
    )


def test_an_fhgff3_page_is_parsed_once_per_policy(monkeypatch):
    page = fhgff3_microdata.write_page(
        record("fhgff3/minimal-reference.microdata.fhgff3.json")
    )
    feeds = []
    original = _microdata._TreeBuilder.feed

    def counted(self, text):
        feeds.append(self.legacy_self_closing)
        return original(self, text)

    monkeypatch.setattr(_microdata._TreeBuilder, "feed", counted)
    _microdata.parse.cache_clear()
    data = fhr()
    data.input_microdata(page)
    assert sorted(feeds) == [False, True]


def test_html_size_cap(monkeypatch):
    monkeypatch.setattr(_microdata, "MAX_HTML_CHARS", 100)
    _microdata.parse.cache_clear()
    with pytest.raises(_microdata.MicrodataError, match="size limit"):
        _microdata.document_families("<p>" + "x" * 100)
    assert _microdata.document_families("<p>x</p>") == set()


@pytest.mark.parametrize("module,schema,path,field", CASES)
def test_writers_refuse_nul_in_valid_metadata_instead_of_losing_it(
    module, schema, path, field
):
    data = record(path)
    data[field] = "A\0B"
    module.validate_record(data, schema)
    with pytest.raises(ValueError, match="NUL text.*losslessly"):
        module.write_page(data)


def test_fhr_writer_refuses_nul_in_nested_string_array():
    data = dict(EXPECTED_FHR)
    data["assemblySoftware"] = [{"name": "example", "commandLineOption": ["A\0B"]}]
    header = fhr(**data)
    header.fhr_validate()
    with pytest.raises(ValueError, match="NUL text.*losslessly"):
        header.output_microdata()


def test_writer_preserves_representable_carriage_returns():
    data = record("fhp/minimal-predicted.fhp.json")
    data["proteome"] = "A\r\nB"
    page = fhp_microdata.write_page(data)
    assert "A&#13;\nB" in page
    assert fhp_microdata.extract(page, FHP_SCHEMA) == data
