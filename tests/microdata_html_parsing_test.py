# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""HTML parsing details shared by the FHR, FHP and FHGFF3 microdata readers.

- Script and template contents are inert for every family (H6, M2): the FHR
  reader used to read properties and text inside them.
- Raw CR is normalised to LF and NUL is dropped from text (U+FFFD in attribute
  values), as HTML input preprocessing and tree construction do.
- Writers refuse values HTML cannot carry (NUL, lone surrogates, itemprop
  names that split), so every written page reads back as the same record.
- An FHGFF3 page is parsed once per self-closing policy, not three times, and
  the parser has a size cap for direct API calls.
"""

import json
import subprocess
import sys
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


# Writer -> reader parity (review of #190): a writer must not emit a value that
# HTML parsing changes, so each value either reads back unchanged or the writer
# refuses the record before a conversion succeeds.


def fhr_record():
    return record("example.fhr.json")


def write_fhr(data):
    writer = fhr()
    writer._input(data)
    return writer.output_microdata()


WRITERS = [
    (
        lambda data: fhp_microdata.write_page(data),
        lambda page: fhp_microdata.extract(page, FHP_SCHEMA),
        lambda: record("fhp/minimal-predicted.fhp.json"),
        "proteome",
    ),
    (
        lambda data: fhgff3_microdata.write_page(data),
        lambda page: fhgff3_microdata.extract(page, FHGFF3_SCHEMA),
        lambda: record("fhgff3/minimal-reference.microdata.fhgff3.json"),
        "annotation",
    ),
    (write_fhr, read_fhr, fhr_record, "funding"),
]
WRITER_IDS = ["FHP", "FHGFF3", "FHR"]


@pytest.mark.parametrize("write,read,load,field", WRITERS, ids=WRITER_IDS)
@pytest.mark.parametrize(
    "value",
    [
        "A\rB",
        "A\r\nB",
        "\r",
        " A\tB\n ",
        "A\x01\x7f\x80\x85\x9fB",
        "A\u2028\ufeff\ufffd\ufffeB",
        "A&#0;B<&>\"'",
        "\U0001f9ec",
    ],
)
def test_written_values_read_back_unchanged(write, read, load, field, value):
    data = load()
    data[field] = value
    assert read(write(data)) == data


@pytest.mark.parametrize("write,read,load,field", WRITERS, ids=WRITER_IDS)
@pytest.mark.parametrize("value", ["A\0B", "\0", "A\ud800B"])
def test_writer_refuses_values_html_cannot_carry(write, read, load, field, value):
    data = load()
    data[field] = value
    with pytest.raises(_microdata.MicrodataError, match=rf"\$\.{field}"):
        write(data)


def test_writer_names_the_nested_value_it_refuses():
    data = fhr_record()
    data["vitalStats"]["NUL\0"] = 1
    with pytest.raises(_microdata.MicrodataError, match="property name"):
        write_fhr(data)
    data = fhr_record()
    data["metadataAuthor"][0]["name"] = "a\0b"
    with pytest.raises(
        _microdata.MicrodataError, match=r"\$\.metadataAuthor\[0\]\.name"
    ):
        write_fhr(data)


@pytest.mark.parametrize("name", ["", "a b", "a\tb", "a\rb"])
def test_writer_refuses_property_names_itemprop_cannot_carry(name):
    with pytest.raises(_microdata.MicrodataError, match="property name"):
        _microdata.check_representable({"vitalStats": {name: 1}})


@pytest.mark.parametrize(
    "keyword", [{"itemtype": "https://example.org/\0"}, {"title": "a\0b"}]
)
def test_page_writers_refuse_unrepresentable_itemtype_and_title(keyword):
    data = record("fhp/minimal-predicted.fhp.json")
    with pytest.raises(_microdata.MicrodataError):
        fhp_microdata.write_page(data, **keyword)


def test_validated_record_with_nul_fails_conversion_instead_of_changing():
    # The reviewer's case: schema-valid, so validation alone does not stop it.
    data = record("fhp/minimal-predicted.fhp.json")
    data["proteome"] = "A\0B"
    fhp_microdata.validate_record(data, FHP_SCHEMA)
    with pytest.raises(_microdata.MicrodataError, match="NUL"):
        fhp_microdata.write_page(data)


def test_convert_to_html_fails_and_writes_nothing_for_a_nul_value(tmp_path):
    data = record("fhp/minimal-predicted.fhp.json")
    data["proteome"] = "A\0B"
    source, target = tmp_path / "in.json", tmp_path / "out.html"
    source.write_text(json.dumps(data))
    result = subprocess.run(
        [str(Path(sys.executable).parent / "bioheaders"), "convert", source, target],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FHP: cannot write $.proteome as HTML microdata" in result.stderr
    assert "NUL" in result.stderr
    assert not target.exists()
