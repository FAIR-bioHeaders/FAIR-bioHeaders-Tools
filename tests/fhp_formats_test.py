# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHP canonical JSON-LD and HTML microdata (FAIR-bioHeaders-Tools#58).

The contracts are FHP-Specification ``docs/FHP.md`` (JSON-LD) and
``docs/FHP-MICRODATA.md`` (microdata). Everything here is self-contained: the
fixtures live under ``examples/fhp/`` and never read a sibling checkout, and no
context is fetched.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import FHP_SCHEMA, fhp_microdata, fhr, jsonld

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
EXAMPLES = ROOT / "examples" / "fhp"
FHP_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhp.json"
)
FHR_ITEMTYPE = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/main/fhr.json"
)
RELEASE_040 = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/v0.4.0/fhp.json"
)
RELEASE_040_W3ID = "https://w3id.org/fair-bioheaders/fhp/v0.4.0"
RELEASE_041 = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FAIR-bioHeaders-Specification/v0.4.1/fhp.json"
)
VALID_HTML = {
    "minimal-predicted.microdata.fhp.html": "minimal-predicted",
    "rich-microdata.microdata.fhp.html": "rich-microdata",
}


def records():
    found = {}
    for path in sorted(EXAMPLES.iterdir()):
        if path.name.endswith(".fhp.json"):
            stem = path.name[: -len(".fhp.json")]
            found[stem] = json.loads(path.read_text(encoding="utf-8"))
        elif path.name.endswith(".fhp.yaml"):
            stem = path.name[: -len(".fhp.yaml")]
            found[stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return found


RECORDS = records()


def run(*args, stdin=None, cwd=None):
    return subprocess.run(
        [str(arg) for arg in args],
        input=stdin,
        capture_output=True,
        cwd=cwd,
        text=True,
    )


def bioheaders_command(*args, **options):
    return run(BIN / "bioheaders", *args, **options)


def loaded(record):
    data = fhr()
    data.input_microdata(fhp_microdata.write_page(record))
    return data.__dict__


# JSON-LD writing.


def test_bundled_fhp_context_and_schema_provenance():
    """Pin the reviewed context and FHP 1.0 schema bytes used by the writers."""
    import hashlib

    context = (ROOT / "bioheaders" / "fhp.context.jsonld").read_bytes()
    schema = (ROOT / "bioheaders" / "fhp_schema.json").read_bytes()
    assert (
        hashlib.sha256(context).hexdigest()
        == "cb0b91c6bd55ff6026f0a3e7a30524c3a1d800922dbbf7117f6fe79c7760a984"
    )
    assert (
        hashlib.sha256(schema).hexdigest()
        == "e3f8f45260b833f931644e87ff7530cb9b4151e67094023dd96edde9a1d90366"
    )


def test_jsonld_fixtures_are_writer_output():
    for stem, record in RECORDS.items():
        expected = (EXAMPLES / f"{stem}.fhp.jsonld").read_text(encoding="utf-8")
        assert fhr(**copy.deepcopy(record)).output_jsonld() == expected


def test_jsonld_writer_layout_and_ordered_lists():
    record = RECORDS["rich-microdata"]
    document = jsonld.fhp_to_jsonld(record)
    assert list(document)[:2] == ["@context", "@type"]
    assert document["@context"] == jsonld.FHP_CONTEXT["@context"]
    assert document["@type"] == "Dataset"
    assert list(document)[2:] == list(record)
    # Order-sensitive arrays use @list in the context, including nested software
    # arguments; identifier and relatedLink are sets.
    context = jsonld.FHP_CONTEXT["@context"]
    for key in ("metadataAuthor", "source", "derivedFrom", "predictionSoftware"):
        assert context[key]["@container"] == "@list"
    assert (
        context["predictionSoftware"]["@context"][1]["commandLineOption"]["@container"]
        == "@list"
    )
    assert context["identifier"]["@container"] == "@set"
    assert context["relatedLink"]["@container"] == "@set"
    # Nested object typing, recursively.
    assert document["taxon"]["@type"] == "Taxon"
    assert document["accessionID"]["@type"] == "PropertyValue"
    assert document["sequenceStats"]["@type"] == "SequenceStats"
    assert document["completeness"]["@type"] == "Completeness"
    assert [item["@type"] for item in document["source"]] == ["Source"]
    assert [item["@type"] for item in document["derivedFrom"]] == [
        "DerivedFrom",
        "DerivedFrom",
    ]
    assert document["derivedFrom"][1]["accessionID"]["@type"] == "PropertyValue"
    assert [item["@type"] for item in document["predictionSoftware"]] == [
        "SoftwareApplication"
    ]


def test_jsonld_canonical_round_trips_through_the_library():
    for stem, record in RECORDS.items():
        data = fhr(**copy.deepcopy(record))
        text = data.output_jsonld()
        back = fhr()
        back.input_jsonld(text)
        assert back.__dict__ == record, stem


def test_jsonld_scalars_keep_their_types():
    record = RECORDS["rich-microdata"]
    document = json.loads(fhr(**record).output_jsonld())
    assert document["schemaVersion"] == "1.0"
    assert isinstance(document["schemaVersion"], str)
    assert isinstance(document["geneticCode"], int)
    assert isinstance(document["sequenceStats"]["sequenceCount"], int)
    assert isinstance(document["completeness"]["completeDuplicated"], int)
    back = jsonld.fhp_canonical_record(document)
    assert back["schemaVersion"] == "1.0"
    assert isinstance(back["geneticCode"], int)
    assert isinstance(back["sequenceStats"]["sequenceCount"], int)


def test_jsonld_absent_optional_fields_stay_absent():
    minimal = RECORDS["minimal-predicted"]
    document = jsonld.fhp_to_jsonld(minimal)
    assert set(document) - {"@context", "@type"} == set(minimal)
    for key in ("source", "derivedFrom", "sequenceStats", "completeness"):
        assert key not in document


def test_jsonld_author_typing_prefers_name_type_then_identifier():
    record = copy.deepcopy(RECORDS["minimal-predicted"])
    record["metadataAuthor"] = [
        {"name": "A person", "nameType": "Personal"},
        {"name": "An organization", "nameType": "Organizational"},
        {"name": "ORCID", "uri": "https://orcid.org/0000-0002-1825-0097"},
        {"name": "ROR", "uri": "https://ror.org/05gq02987"},
        {"name": "Unclassified"},
        {
            "name": "Explicit wins",
            "nameType": "Organizational",
            "uri": "https://orcid.org/0000-0002-1825-0097",
        },
    ]
    document = jsonld.fhp_to_jsonld(record)
    assert [item["@type"] for item in document["metadataAuthor"]] == [
        "Person",
        "Organization",
        "Person",
        "Organization",
        "Agent",
        "Organization",
    ]
    back = jsonld.fhp_canonical_record(json.loads(json.dumps(document)))
    assert back == record


def test_jsonld_documentation_url_becomes_subject_of():
    record = dict(
        RECORDS["minimal-predicted"],
        documentation="https://example.org/proteome/README",
    )
    document = jsonld.fhp_to_jsonld(record)
    assert "documentation" not in document
    assert document["subjectOf"] == record["documentation"]
    assert jsonld.fhp_canonical_record(document) == record


def test_jsonld_known_context_urls_are_served_offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the FHP reader must not use the network")

    monkeypatch.setattr("socket.socket.connect", refuse)
    document = jsonld.fhp_to_jsonld(RECORDS["minimal-predicted"])
    for url in jsonld.FHP_KNOWN_CONTEXT_URLS:
        by_url = dict(document, **{"@context": url})
        assert jsonld.fhp_is_canonical(by_url)
        assert jsonld.fhp_canonical_record(by_url) == RECORDS["minimal-predicted"]


@pytest.mark.parametrize(
    "context",
    [
        "https://schema.org/",
        "https://example.org/unknown.jsonld",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/main/jsonld/fhr.context.jsonld",
    ],
)
def test_jsonld_unknown_context_is_rejected(context):
    document = dict(jsonld.fhp_to_jsonld(RECORDS["minimal-predicted"]))
    document["@context"] = context
    with pytest.raises(ValueError, match="FHP"):
        jsonld.fhp_canonical_record(document)
    with pytest.raises(ValueError, match="FHP"):
        fhr().input_jsonld(json.dumps(document))


def test_jsonld_embedded_fhr_context_is_rejected():
    document = dict(jsonld.fhp_to_jsonld(RECORDS["minimal-predicted"]))
    document["@context"] = jsonld.CONTEXT["@context"]
    with pytest.raises(ValueError, match="canonical FHP"):
        fhr().input_jsonld(json.dumps(document))


@pytest.mark.parametrize("version", [1.0, 2.0, "1.1"])
def test_jsonld_unsupported_version_is_rejected(version):
    document = dict(jsonld.fhp_to_jsonld(RECORDS["minimal-predicted"]))
    context = {**document["@context"], "@version": version}
    document["@context"] = context
    with pytest.raises(ValueError, match="@version"):
        fhr().input_jsonld(json.dumps(document))


def test_jsonld_malformed_author_typing_is_rejected():
    document = jsonld.fhp_to_jsonld(RECORDS["rich-predicted"])
    document["metadataAuthor"][0] = {
        **document["metadataAuthor"][0],
        "@type": "Organization",
    }
    with pytest.raises(ValueError, match=r"metadataAuthor\[0\].*derives Person"):
        jsonld.fhp_canonical_record(document)
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    del document["metadataAuthor"][0]["@type"]
    with pytest.raises(ValueError, match="no @type"):
        jsonld.fhp_canonical_record(document)


@pytest.mark.parametrize(
    "path, value, message",
    [
        (("taxon",), "Source", "taxon"),
        (("derivedFrom", 0), "Source", r"derivedFrom\[0\]"),
        (("source", 0), "Taxon", r"source\[0\]"),
        (("sequenceStats",), "Taxon", "sequenceStats"),
        (("completeness",), "Taxon", "completeness"),
    ],
)
def test_jsonld_wrong_nested_type_is_rejected(path, value, message):
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    target = document
    for part in path[:-1]:
        target = target[part]
    target[path[-1]]["@type"] = value
    with pytest.raises(ValueError, match=message):
        jsonld.fhp_canonical_record(document)


def test_jsonld_type_namespace_must_match_the_context():
    """A local name from the wrong namespace is not the expected class (#98 review)."""
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    document["@type"] = "fhr:Dataset"
    with pytest.raises(ValueError, match="the record"):
        jsonld.fhp_canonical_record(document)
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    document["@type"] = "schema:Dataset"
    with pytest.raises(ValueError, match="the record"):
        jsonld.fhp_canonical_record(document)
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    document["source"][0]["@type"] = "sdo:Source"
    with pytest.raises(ValueError, match=r"source\[0\]"):
        jsonld.fhp_canonical_record(document)


def test_jsonld_expanded_type_iris_are_accepted():
    """Expanded and compact IRIs for the context's own classes still round trip."""
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    document["@type"] = "http://schema.org/Dataset"
    document["source"][0]["@type"] = "https://w3id.org/fair-bioheaders/terms#Source"
    document["metadataAuthor"][1]["@type"] = "sdo:Person"
    assert jsonld.fhp_canonical_record(document) == RECORDS["rich-microdata"]


def test_jsonld_parent_accession_type_is_checked():
    document = jsonld.fhp_to_jsonld(RECORDS["rich-microdata"])
    document["derivedFrom"][1]["accessionID"]["@type"] = "Taxon"
    with pytest.raises(ValueError, match=r"derivedFrom\[1\]\.accessionID"):
        jsonld.fhp_canonical_record(document)


def test_jsonld_export_profile_does_not_exist_for_fhp():
    data = fhr(**RECORDS["minimal-predicted"])
    with pytest.raises(ValueError, match="FHP supports canonical JSON-LD only"):
        data.output_jsonld(profile="export")
    with pytest.raises(ValueError, match="FHP supports canonical JSON-LD only"):
        data.output_jsonld(export={"id": "https://example.org/set"})


def test_jsonld_cli_works_outside_the_checkout(tmp_path):
    record = RECORDS["minimal-predicted"]
    source = tmp_path / "metadata.json"
    source.write_text(json.dumps(record), encoding="utf-8")
    document = tmp_path / "metadata.fhp.jsonld"
    result = bioheaders_command("convert", source, document, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    back = tmp_path / "back.json"
    result = bioheaders_command("convert", document, back, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(back.read_text(encoding="utf-8")) == record
    # stdin/stdout with explicit formats.
    piped = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "json",
        "--to",
        "jsonld",
        stdin=json.dumps(record),
        cwd=tmp_path,
    )
    assert piped.returncode == 0, piped.stderr
    assert piped.stdout == document.read_text(encoding="utf-8")
    piped_back = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "jsonld",
        "--to",
        "json",
        stdin=piped.stdout,
        cwd=tmp_path,
    )
    assert piped_back.returncode == 0, piped_back.stderr
    assert json.loads(piped_back.stdout) == record


def test_jsonld_cli_refuses_the_export_profile_for_fhp(tmp_path):
    source = tmp_path / "metadata.json"
    source.write_text(json.dumps(RECORDS["minimal-predicted"]), encoding="utf-8")
    output = tmp_path / "out.jsonld"
    result = bioheaders_command(
        "convert",
        source,
        output,
        "--jsonld-profile",
        "export",
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "FHP supports canonical JSON-LD only" in result.stderr
    assert not output.exists()


# HTML microdata.


def test_microdata_fixtures_extract_to_their_records():
    for fixture, stem in VALID_HTML.items():
        data = fhr()
        data.input_microdata((EXAMPLES / fixture).read_text(encoding="utf-8"))
        assert data.__dict__ == RECORDS[stem]


def test_microdata_fixtures_are_writer_output():
    for fixture, stem in VALID_HTML.items():
        expected = fhr(**RECORDS[stem]).output_microdata()
        assert (EXAMPLES / fixture).read_text(encoding="utf-8") == expected


def test_microdata_round_trips_every_example():
    for stem, record in RECORDS.items():
        assert loaded(copy.deepcopy(record)) == record, stem


def test_microdata_output_is_standalone_and_has_a_readable_table():
    record = RECORDS["rich-microdata"]
    page = fhr(**record).output_microdata()
    assert page.startswith('<!doctype html>\n<html lang="en">')
    assert page.endswith("</body></html>\n")
    assert f'itemtype="{FHP_ITEMTYPE}"' in page
    assert FHR_ITEMTYPE not in page
    assert "<caption>FHP metadata</caption>" in page
    # Both the metadata block and the table carry the same escaped value.
    assert page.count("Synthetic predicted proteome caf") >= 2


def test_microdata_uses_the_fhp_itemtype_not_the_fhr_one():
    record = RECORDS["minimal-predicted"]
    page = fhp_microdata.write_page(record, itemtype=FHR_ITEMTYPE)
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.read_page(page, FHP_SCHEMA)
    with pytest.raises(ValueError, match="FHP itemtype"):
        fhr().input_microdata(page)


def test_microdata_rejects_two_fhp_scopes():
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"])
    scope = page[page.index("<div ") : page.index("</div>") + len("</div>")]
    page = page.replace("</body>", scope + "</body>", 1)
    with pytest.raises(fhp_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_microdata_schema_selection_supports_fixed_releases():
    record = dict(RECORDS["minimal-predicted"], schema=RELEASE_040)
    assert loaded(record) == record
    record["schema"] = RELEASE_040_W3ID
    assert loaded(record) == record
    record["schema"] = RELEASE_041
    assert loaded(record) == record


def test_microdata_rejects_unsupported_or_foreign_schemas():
    for schema in (
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/v999.0.0/fhp.json",
        "https://raw.githubusercontent.com/FAIR-bioHeaders/"
        "FAIR-bioHeaders-Specification/0123abc/fhp.json",
        "https://w3id.org/fair-bioheaders/fhr/v0.4.0",
        FHR_ITEMTYPE,
        None,
    ):
        record = dict(RECORDS["minimal-predicted"], schema=schema)
        page = fhp_microdata.write_page(record)
        with pytest.raises(fhp_microdata.MicrodataError):
            fhp_microdata.extract(page, FHP_SCHEMA)


def test_microdata_rejects_an_unreleased_schema_version():
    record = dict(RECORDS["minimal-predicted"], schemaVersion=2)
    page = fhp_microdata.write_page(record)
    # Structurally readable, but validation rejects it against the FHP 1.0 contract.
    with pytest.raises(fhp_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_microdata_zero_is_a_value_and_absence_is_omission():
    rich = loaded(RECORDS["rich-microdata"])
    assert rich["source"][0]["sequenceCount"] == 0
    assert rich["completeness"]["completeDuplicated"] == 0
    assert "source" not in loaded(RECORDS["minimal-predicted"])
    # An empty array is present and distinct from an omitted array.
    record = dict(RECORDS["minimal-predicted"], identifier=[])
    assert loaded(record) == record


def test_microdata_false_is_retained_when_present():
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"]).replace(
        "</div>",
        '<span itemprop="newFlag" data-fhr-type="boolean">false</span></div>',
        1,
    )
    assert fhp_microdata.read_page(page, FHP_SCHEMA)["newFlag"] is False


def test_microdata_applies_implied_end_tags():
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"])
    version = '<span itemprop="version" data-fhr-type="string">1.0</span>'
    omitted = (
        '<ul><li itemprop="version" data-fhr-type="string">1.0'
        '<li itemprop="reuseConditions" data-fhr-type="string">public domain</ul>'
    )
    data = fhr()
    data.input_microdata(page.replace(version, omitted, 1))
    assert data.version == "1.0"
    assert data.reuseConditions == "public domain"


def test_microdata_repeated_scalar_becomes_a_list_and_is_rejected():
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"]).replace(
        "</div>",
        '<span itemprop="proteome" data-fhr-type="string">Second</span></div>',
        1,
    )
    extracted = fhp_microdata.read_page(page, FHP_SCHEMA)
    assert extracted["proteome"] == [RECORDS["minimal-predicted"]["proteome"], "Second"]
    with pytest.raises(fhp_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_microdata_repeated_array_container_is_not_flattened():
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"])
    start = page.index('<span itemprop="metadataAuthor"')
    end = page.index("</span></span></span>", start) + len("</span></span></span>")
    container = page[start:end]
    page = page.replace(container, container * 2, 1)
    extracted = fhp_microdata.read_page(page, FHP_SCHEMA)
    assert len(extracted["metadataAuthor"]) == 2
    assert all(isinstance(item, list) for item in extracted["metadataAuthor"])
    with pytest.raises(fhp_microdata.MicrodataError):
        fhr().input_microdata(page)


def test_microdata_malicious_content_is_escaped_and_inert():
    record = dict(
        RECORDS["minimal-predicted"],
        documentation=(
            '<script>alert("x")</script> & "double" and \'single\', '
            "café, 測試 and 🧬 </span><img src=x onerror=alert(1)>"
        ),
        accessionID={
            "name": '<script>alert("name")</script>',
            "url": "https://example.org/?a=1&b=%3Ctag%3E",
        },
    )
    page = fhr(**record).output_microdata()
    assert "<script>alert" not in page
    assert "onerror=alert(1)>" not in page
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in page
    # The same value appears in the readable table, escaped once.
    assert page.count("&lt;script&gt;") >= 2
    assert loaded(record) == record


def test_microdata_script_and_template_content_is_inert():
    schema = FHP_SCHEMA
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"])
    checksum = (
        '<span itemprop="checksum" data-fhr-type="string">'
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</span>"
    )
    scripted = page.replace(
        checksum,
        '<script itemprop="checksum" data-fhr-type="string">'
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</script>",
        1,
    )
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.extract(scripted, schema)
    wrapped = "<template>" + page + "</template>"
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.read_page(wrapped, schema)
    with pytest.raises(ValueError):
        fhr().input_microdata(wrapped)
    # A template inside a property contributes no text.
    inside = page.replace(
        "</div>",
        '<span itemprop="documentation" data-fhr-type="string">before'
        "<template>hidden</template>after</span></div>",
        1,
    )
    assert fhp_microdata.read_page(inside, schema)["documentation"] == "beforeafter"


def test_microdata_typed_arrays_ignore_inert_children():
    """F7 applies inside typed arrays: script/template items are not metadata."""
    schema = FHP_SCHEMA
    record = dict(RECORDS["minimal-predicted"], identifier=["example:hidden"])
    page = fhp_microdata.write_page(record)
    item = '<span itemprop="item" data-fhr-type="string">example:hidden</span>'
    assert item in page
    for inert in ("script", "template"):
        wrapped = item.replace("span", inert)
        page_inert = page.replace(item, wrapped, 1)
        extracted = fhp_microdata.read_page(page_inert, schema)
        assert "example:hidden" not in json.dumps(extracted), extracted
        assert not extracted.get("identifier"), extracted


def test_microdata_rejects_an_unclosed_root_scope():
    """A truncated document does not get to keep its readable properties."""
    schema = FHP_SCHEMA
    page = fhp_microdata.write_page(RECORDS["minimal-predicted"])
    truncated = page[: page.rindex("</div>")]
    assert fhp_microdata.extract(page, schema)
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.read_page(truncated, schema)
    with pytest.raises(fhp_microdata.MicrodataError):
        fhp_microdata.extract(truncated, schema)


def test_microdata_cli_works_outside_the_checkout(tmp_path):
    record = RECORDS["rich-microdata"]
    source = tmp_path / "metadata.json"
    source.write_text(json.dumps(record), encoding="utf-8")
    page = tmp_path / "metadata.fhp.html"
    result = bioheaders_command("convert", source, page, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "<caption>FHP metadata</caption>" in page.read_text(encoding="utf-8")
    back = tmp_path / "back.json"
    result = bioheaders_command("convert", page, back, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(back.read_text(encoding="utf-8")) == record
    piped = bioheaders_command(
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
    assert piped.returncode == 0, piped.stderr
    assert piped.stdout == page.read_text(encoding="utf-8")
