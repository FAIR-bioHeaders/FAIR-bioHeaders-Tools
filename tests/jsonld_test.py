# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""JSON-LD writing and reading (FHR-Specification feature 011).

Writing and canonical reading need no JSON-LD processor. The general-path tests
(rules J3 to J5) need PyLD, the jsonld extra, and are skipped without it (on
Python 3.9 it is not installable). Everything runs with network access disabled
(tests/conftest.py).
"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from bioheaders import fhr, jsonld

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
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
ORCID = "https://orcid.org/0000-0002-1825-0097"  # ORCID's documented example iD.
ROR = "https://ror.org/05gq02987"  # Used only to test the typing rule.
EXPORT = {
    "id": "https://example.org/datasets/synthetic-human",
    "url": "https://example.org/genomes/synthetic-human",
    "keywords": ["genome assembly", "Homo sapiens"],
}
NEEDS_EXTRA = (
    "reading this JSON-LD form needs the jsonld extra: "
    'pip install "fair-bioheaders[jsonld]"'
)
# FHR-Specification conformance vectors of format jsonld, copied with their
# manifest entries; test_vectors_match_the_specification keeps them in step.
VECTORS = ROOT / "tests" / "fixtures" / "jsonld"
MANIFEST = json.loads((VECTORS / "manifest.json").read_text())["vectors"]


@pytest.fixture
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


def run(*args, stdin=b"", cwd=None):
    return subprocess.run(
        [str(arg) for arg in args], input=stdin, capture_output=True, cwd=cwd
    )


def bioheaders_command(*args, **options):
    return run(BIN / "bioheaders", *args, **options)


def written(metadata, **options):
    return json.loads(fhr(**metadata).output_jsonld(**options))


def read(document, **options):
    data = fhr()
    data.input_jsonld(json.dumps(document), **options)
    return data.__dict__


def test_examples_are_byte_identical(metadata):
    for stem in ("example", "minimal"):
        source = json.loads((ROOT / f"examples/{stem}.fhr.json").read_text())
        expected = (ROOT / f"examples/{stem}.fhr.jsonld").read_text(encoding="utf-8")
        assert fhr(**source).output_jsonld() == expected


def test_writer_layout(metadata):
    document = written(metadata)
    assert list(document)[:2] == ["@context", "@type"]
    assert document["@context"] == jsonld.CONTEXT["@context"]
    assert document["@type"] == "Dataset"
    assert list(document)[2:] == list(metadata)
    assert list(document["taxon"]) == ["@type", "name", "uri"]
    assert document["taxon"]["@type"] == "Taxon"
    assert document["accessionID"]["@type"] == "PropertyValue"
    assert document["vitalStats"]["@type"] == "VitalStats"
    assert document["assemblySoftware"][0]["@type"] == "SoftwareApplication"
    assert document["metadataAuthor"][0]["@type"] == "Person"
    text = fhr(**metadata).output_jsonld()
    assert text == json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def test_author_typing_from_identifier(metadata):
    metadata["assemblyAuthor"] = [
        {"name": "Josiah Carberry", "uri": ORCID},
        {"name": "Example organization", "uri": ROR},
        {"name": "Name only"},
        {"name": "Other identifier", "uri": "https://example.org/people/1"},
    ]
    types = [item["@type"] for item in jsonld.to_jsonld(metadata)["assemblyAuthor"]]
    assert types == ["Person", "Organization", "Agent", "Agent"]
    assert read(written(metadata)) == metadata


def test_author_typing_from_name_type(metadata):
    """Rule J7: an explicit nameType decides before the uri (FAIR-bioHeaders-Tools#74)."""
    metadata["assemblyAuthor"] = [
        {"name": "Person with a ROR ID", "uri": ROR, "nameType": "Personal"},
        {
            "name": "Organization with an ORCID iD",
            "uri": ORCID,
            "nameType": "Organizational",
        },
        {"name": "Other name type", "uri": ORCID, "nameType": "Unknown"},
    ]
    document = written(metadata)
    assert [item["@type"] for item in document["assemblyAuthor"]] == [
        "Person",
        "Organization",
        "Person",
    ]
    assert document["assemblyAuthor"][1]["nameType"] == "Organizational"
    assert read(document) == metadata


def test_legacy_software_string_is_unchanged(metadata):
    metadata["assemblySoftware"] = "hifiasm"
    document = written(metadata)
    assert document["assemblySoftware"] == "hifiasm"
    assert read(document) == metadata


def test_documentation_text_or_url(metadata):
    assert "subjectOf" not in written(metadata)
    for value in ("https://example.org/genome/README", "ftp://example.org/readme.txt"):
        metadata["documentation"] = value
        document = written(metadata)
        assert "documentation" not in document
        assert document["subjectOf"] == value
        assert (
            list(document).index("subjectOf")
            == list(metadata).index("documentation") + 2
        )
        back = read(document)
        assert back == metadata and list(back) == list(metadata)
    for value in ("See https://example.org/readme", "example.org", "urn:x:readme"):
        metadata["documentation"] = value
        assert written(metadata)["documentation"] == value


def test_documentation_and_subject_of_together_are_rejected(metadata):
    document = written(metadata)
    document["subjectOf"] = "https://example.org/readme"
    with pytest.raises(ValueError, match="both documentation and subjectOf"):
        read(document)


def test_absent_optional_fields_stay_absent(metadata):
    minimal = json.loads((ROOT / "examples/minimal.fhr.json").read_text())
    document = written(minimal)
    assert set(document) - {"@context", "@type"} == set(minimal)
    assert "null" not in json.dumps(
        {k: v for k, v in document.items() if k != "@context"}
    )
    assert read(document) == minimal


def test_export_context(metadata):
    without = written(metadata)
    for key in ("@id", "keywords", "url", "conformsTo"):
        assert key not in without
    assert jsonld.bioschemas_missing(without) == ["@id", "keywords", "url"]
    document = written(metadata, export=EXPORT)
    assert list(document)[:3] == ["@context", "@type", "@id"]
    assert list(document)[-3:] == ["keywords", "url", "conformsTo"]
    assert document["conformsTo"] == jsonld.BIOSCHEMAS_DATASET_PROFILE
    assert document["conformsTo"].endswith("/Dataset/1.0-RELEASE")
    warnings = []
    data = fhr()
    data.input_jsonld(json.dumps(document), warn=warnings.append)
    assert data.__dict__ == metadata
    assert warnings == [
        f"JSON-LD: {key} is export metadata, not an FHR field; it was not kept"
        for key in ("@id", "keywords", "url", "conformsTo")
    ]


def test_incomplete_export_context_makes_no_claim(metadata):
    partial = {key: value for key, value in EXPORT.items() if key != "id"}
    document = written(metadata, export=partial)
    assert "conformsTo" not in document and "@id" not in document
    assert jsonld.bioschemas_missing(document) == ["@id"]
    del metadata["reuseConditions"]
    document = written(metadata, export=EXPORT)
    assert "conformsTo" not in document
    assert jsonld.bioschemas_missing(document) == ["license"]
    metadata["reuseConditions"] = "CC0-1.0"
    metadata["documentation"] = "https://example.org/readme"
    assert jsonld.bioschemas_missing(written(metadata, export=EXPORT)) == [
        "description"
    ]


@pytest.mark.parametrize(
    "export",
    [
        {"keyword": ["x"]},
        {"keywords": "genome"},
        {"keywords": []},
        {"keywords": [""]},
        {"url": "example.org"},
        {"id": 5},
        ["keywords"],
    ],
)
def test_export_context_is_validated(metadata, export):
    with pytest.raises(ValueError, match="export context"):
        jsonld.to_jsonld(metadata, export=export)


def test_unmapped_keys(metadata):
    assert jsonld.unmapped_keys(metadata) == []
    metadata["taxon"]["checksum"] = "nested"
    metadata["assemblyAuthor"][0]["affiliation"] = "Example institute"
    metadata["vitalStats"]["contigN50"] = 3
    assert jsonld.unmapped_keys(metadata) == [
        "taxon.checksum",
        "assemblyAuthor[0].affiliation",
        "vitalStats.contigN50",
    ]
    assert read(written(metadata)) == metadata


def test_keyword_like_keys_are_refused(metadata):
    metadata["taxon"]["@id"] = "https://example.org/taxon"
    with pytest.raises(ValueError, match=r"taxon\.@id"):
        jsonld.to_jsonld(metadata)


def test_canonical_reading_of_context_urls(metadata):
    assert jsonld.KNOWN_CONTEXT_URLS == (
        jsonld.RAW_MAIN_CONTEXT_URL,
        jsonld.RAW_MAIN_CONTEXT_URL.replace(
            "FHR-Specification", "FAIR-bioHeaders-Specification"
        ),
    )
    for url in jsonld.KNOWN_CONTEXT_URLS:
        document = dict(written(metadata), **{"@context": url})
        assert jsonld.is_canonical(document)
        assert read(document) == metadata


def test_canonical_reading_sets_types_aside_at_every_depth(metadata):
    document = written(metadata)
    document["@type"] = ["Dataset", "https://example.org/Extra"]
    document["vitalStats"]["@type"] = "Anything"
    del document["taxon"]["@type"]
    assert jsonld.is_canonical(document)
    assert read(document) == metadata


def test_canonical_reading_keeps_extra_nested_keys(metadata):
    metadata["taxon"]["checksum"] = "nested property"
    assert read(written(metadata)) == metadata


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update({"@context": [jsonld.RAW_MAIN_CONTEXT_URL]}),
        lambda d: d.update({"@context": [d["@context"]]}),
        lambda d: d.update({"@graph": []}),
        lambda d: d["taxon"].update({"@id": "https://identifiers.org/taxonomy:9606"}),
        lambda d: d.update({"@type": {"@id": "Dataset"}}),
        lambda d: d.update({"@id": 5}),
        lambda d: d.pop("@context"),
    ],
)
def test_non_canonical_documents_need_the_extra(metadata, change, monkeypatch):
    document = written(metadata)
    change(document)
    assert not jsonld.is_canonical(document)
    monkeypatch.setitem(sys.modules, "pyld", None)
    with pytest.raises(ValueError) as error:
        read(document)
    assert str(error.value) == NEEDS_EXTRA


def test_canonical_reading_does_not_import_pyld(metadata, monkeypatch):
    monkeypatch.setitem(sys.modules, "pyld", None)
    assert read(written(metadata)) == metadata


def test_non_object_documents_are_rejected():
    for text in ("[]", '"text"', "3"):
        with pytest.raises(ValueError):
            fhr().input_jsonld(text)
    with pytest.raises(ValueError, match="must be a JSON object or array"):
        fhr().input_jsonld('"text"')


def test_duplicate_keys_are_rejected(metadata):
    text = (
        fhr(**metadata)
        .output_jsonld()
        .replace('"genome": ', '"genome": "first", "genome": ', 1)
    )
    with pytest.raises(ValueError, match="Duplicate JSON object key"):
        fhr().input_jsonld(text)


def test_missing_checksum_fails_schema_validation(metadata):
    del metadata["checksum"]
    data = fhr()
    data.input_jsonld(fhr(**metadata).output_jsonld())
    with pytest.raises(ValidationError):
        data.fhr_validate()


def test_utf8_bom_and_bytes_are_accepted(metadata):
    text = fhr(**metadata).output_jsonld()
    data = fhr()
    data.input_jsonld(("﻿" + text).encode("utf-8"))
    assert data.__dict__ == metadata


def test_convert_rejects_nested_keys_without_terms(metadata, tmp_path):
    # From v0.4 (FHR schemaVersion 2.0) nested objects are closed, so a nested key
    # without a JSON-LD term is a schema error before anything is written.
    metadata["taxon"]["checksum"] = "nested property"
    source = tmp_path / "nested.json"
    source.write_text(json.dumps(metadata))
    output = tmp_path / "nested.jsonld"
    result = bioheaders_command("convert", source, output)
    assert result.returncode == 1
    assert b"$.taxon" in result.stderr and b"checksum" in result.stderr
    assert not output.exists()


def test_convert_with_export_context(metadata, tmp_path):
    source = ROOT / "examples/example.fhr.json"
    export = tmp_path / "export.yaml"
    export.write_text(
        "id: {id}\nurl: {url}\nkeywords:\n- genome assembly\n- Homo sapiens\n".format(
            **EXPORT
        )
    )
    output = tmp_path / "out.jsonld"
    result = bioheaders_command("convert", "--export-context", export, source, output)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    document = json.loads(output.read_text())
    assert document["conformsTo"] == jsonld.BIOSCHEMAS_DATASET_PROFILE
    back = tmp_path / "back.json"
    result = bioheaders_command("convert", output, back)
    assert result.returncode == 0
    assert result.stderr.decode().count("is export metadata") == 4
    assert json.loads(back.read_text()) == metadata

    export.write_text("keywords: [genome assembly]\n")
    result = bioheaders_command("convert", "--export-context", export, source, output)
    assert result.returncode == 0, result.stderr
    assert result.stderr.decode() == (
        "FHR: JSON-LD: not claiming Bioschemas Dataset conformance; missing: @id, url\n"
    )
    assert "conformsTo" not in json.loads(output.read_text())

    for content, message in (
        ("keywords: genome\n", "export context"),
        ("unknown: 1\n", "export context"),
    ):
        export.write_text(content)
        result = bioheaders_command(
            "convert", "--export-context", export, source, output
        )
        assert result.returncode == 1
        assert message in result.stderr.decode()
    result = bioheaders_command(
        "convert", "--export-context", export, source, tmp_path / "out.json"
    )
    assert result.returncode == 1
    assert b"--export-context applies only to JSON-LD output" in result.stderr


def test_validate_and_stdin(metadata, tmp_path):
    source = ROOT / "examples/example.fhr.jsonld"
    result = bioheaders_command("validate", source)
    assert result.returncode == 0 and result.stdout == b"FHR metadata is valid.\n"
    piped = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "jsonld",
        "--to",
        "json",
        stdin=source.read_bytes(),
    )
    assert piped.returncode == 0, piped.stderr
    assert json.loads(piped.stdout) == metadata
    piped = bioheaders_command(
        "convert",
        "-",
        "-",
        "--from",
        "json",
        "--to",
        "jsonld",
        stdin=(ROOT / "examples/example.fhr.json").read_bytes(),
    )
    assert piped.stdout == source.read_bytes()
    invalid = tmp_path / "invalid.jsonld"
    del metadata["checksum"]
    invalid.write_text(fhr(**metadata).output_jsonld())
    result = bioheaders_command("validate", invalid)
    assert result.returncode == 1
    assert b"schema validation failed" in result.stderr


def test_context_matches_the_specification():
    published = SPEC / "jsonld" / "fhr.context.jsonld"
    if not published.is_file():
        pytest.skip("FHR-Specification checkout with jsonld/ not found")
    bundled = ROOT / "bioheaders" / "fhr.context.jsonld"
    assert bundled.read_bytes() == published.read_bytes()
    for stem in ("example", "minimal"):
        name = f"examples/{stem}.fhr.jsonld"
        assert (ROOT / name).read_bytes() == (SPEC / name).read_bytes()


def test_vectors_match_the_specification():
    manifest = SPEC / "conformance" / "manifest.json"
    if not manifest.is_file():
        pytest.skip("FHR-Specification checkout not found")
    published = [
        v
        for v in json.loads(manifest.read_text())["vectors"]
        if v["format"] == "jsonld"
    ]
    assert published == MANIFEST
    for vector in MANIFEST:
        path = vector["file"]
        assert (VECTORS / path).read_bytes() == (
            SPEC / "conformance" / path
        ).read_bytes()


# Author keys in the vector forms: canonical, compacted and expanded.
VECTOR_AUTHOR_KEYS = {
    "metadataAuthor": (
        "metadataAuthor",
        "fhr:metadataAuthor",
        "https://w3id.org/fair-bioheaders/terms#metadataAuthor",
    ),
    "assemblyAuthor": (
        "assemblyAuthor",
        "creator",
        "http://schema.org/creator",
    ),
}


def vector_author_types(node, keys):
    for key in keys:
        value = node.get(key)
        if value is None:
            continue
        kinds = []
        for item in value if isinstance(value, list) else [value]:
            kind = item.get("@type")
            if isinstance(kind, list):
                kind = kind[0]
            kinds.append(kind.rsplit("#", 1)[-1].rsplit("/", 1)[-1].rsplit(":", 1)[-1])
        return kinds
    return None


# Vectors with links that writers refuse (R14 warnings) are not writer output.
VALID_VECTORS = [
    v
    for v in MANIFEST
    if v["expected"] == "valid" and "R14" not in v.get("warnings", ())
]


@pytest.mark.parametrize("vector", VALID_VECTORS, ids=[v["id"] for v in VALID_VECTORS])
def test_writer_types_authors_like_the_vectors(vector):
    """The writer gives each author node the @type that the vector states."""
    document = json.loads(vector_bytes(vector))
    node = document[0] if isinstance(document, list) else document
    if "@graph" in node:
        node = node["@graph"][0]
    written_document = jsonld.to_jsonld(vector["metadata"])
    for field, keys in VECTOR_AUTHOR_KEYS.items():
        expected = vector_author_types(node, keys)
        assert expected is not None, f"{vector['id']} states no {field}"
        actual = [item["@type"] for item in written_document[field]]
        assert actual == expected, f"{vector['id']}: {field}"


# The general path (rules J3 to J5).


def equal(left, right):
    """data-model section 8: key order ignored; array order and JSON types kept."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            equal(left[k], right[k]) for k in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(equal, left, right))
    return type(left) is type(right) and left == right


def vector_bytes(vector):
    return (VECTORS / vector["file"]).read_bytes()


@pytest.mark.parametrize("vector", MANIFEST, ids=[v["id"] for v in MANIFEST])
def test_conformance_vectors(vector):
    pytest.importorskip("pyld")
    data = fhr()
    if vector["expected"] == "valid":
        data.input_jsonld(vector_bytes(vector), warn=lambda message: None)
        data.fhr_validate()
        assert equal(data.__dict__, vector["metadata"])
    else:
        with pytest.raises((ValueError, ValidationError)):
            data.input_jsonld(vector_bytes(vector), warn=lambda message: None)
            data.fhr_validate()


def expanded(document):
    from pyld import jsonld as pyld

    return pyld.expand(document, {"documentLoader": jsonld._document_loader([])})


def test_examples_read_back_from_expanded_form():
    pytest.importorskip("pyld")
    for stem in ("example", "minimal"):
        source = json.loads((ROOT / f"examples/{stem}.fhr.json").read_text())
        document = expanded(
            json.loads((ROOT / f"examples/{stem}.fhr.jsonld").read_text())
        )
        assert not jsonld.is_canonical(document)
        assert equal(jsonld.from_jsonld(document), source)


def test_general_reader_keeps_document_order_and_legacy_strings(metadata):
    pytest.importorskip("pyld")
    metadata["assemblySoftware"] = "synthetic-assembler"
    back = jsonld.from_jsonld(expanded(written(metadata)))
    assert list(back) == sorted(metadata, key=jsonld.KEY_ORDER.__getitem__)
    assert back["assemblySoftware"] == "synthetic-assembler"
    assert equal(back, metadata)


def test_reverse_map_covers_every_field_path():
    """All 51 property paths of fhr.json (data-model section 4; 45 before v0.4 added
    the scaffold statistics and author nameType)."""

    def paths(scope, prefix=""):
        reverse, id_key = scope
        found = {prefix + id_key} if id_key else set()
        for key, _, _, child in reverse.values():
            found.add(prefix + key)
            if child is not None:
                found |= paths(child, f"{prefix}{key}.")
        return found

    schema = json.loads((ROOT / "bioheaders/fhr_schema.json").read_text())

    def schema_paths(node, prefix=""):
        if "$ref" in node:
            node = schema["definitions"][node["$ref"].rsplit("/", 1)[-1]]
        found = set()
        for option in node.get("anyOf", []) + node.get("oneOf", []):
            found |= schema_paths(option, prefix)
        if "items" in node:
            found |= schema_paths(node["items"], prefix)
        for key, child in node.get("properties", {}).items():
            found.add(prefix + key)
            found |= schema_paths(child, f"{prefix}{key}.")
        return found

    expected = schema_paths(schema)
    assert len(expected) == 51
    assert paths(jsonld.REVERSE_MAP) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://schema.org/",
        "https://example.org/context.jsonld",
        "https://w3id.org/fair-bioheaders/fhr/v9.9.9/jsonld/fhr.context.jsonld",
    ],
)
def test_loader_serves_only_bundled_contexts(url):
    pyld = pytest.importorskip("pyld.jsonld")
    refused = []
    load = jsonld._document_loader(refused)
    with pytest.raises(pyld.JsonLdError) as error:
        load(url)
    assert error.value.code == "loading document failed"
    assert refused == [url]
    served = load(jsonld.RAW_MAIN_CONTEXT_URL)
    assert served["document"] == jsonld.CONTEXT
    with pytest.raises(ValueError) as error:
        jsonld.from_jsonld({"@context": url, "name": "x"})
    assert str(error.value) == f"JSON-LD context is not available offline: {url}"


def open_object_vector():
    """The taxon.checksum vector, made non-canonical by moving it into @graph."""
    vector = next(v for v in MANIFEST if v["id"] == "jsonld-nested-extra-key")
    document = json.loads(vector_bytes(vector))
    context = document.pop("@context")
    return {"@context": context, "@graph": [document]}, vector["metadata"]


def test_nested_key_without_a_term_is_an_unknown_term():
    pytest.importorskip("pyld")
    document, metadata = open_object_vector()
    with pytest.raises(ValueError) as error:
        jsonld.from_jsonld(document)
    assert str(error.value) == (
        "JSON-LD term not in the FHR mapping: checksum "
        "(dropped by JSON-LD expansion: it has no IRI)"
    )
    messages = []
    back = jsonld.from_jsonld(document, ignore_unknown_terms=True, warn=messages.append)
    assert messages == [
        "warning: JSON-LD term not in the FHR mapping: checksum "
        "(dropped by JSON-LD expansion: it has no IRI)"
    ]
    expected = copy.deepcopy(metadata)
    del expected["taxon"]["checksum"]
    assert equal(back, expected)


def test_unknown_terms_print_warnings_with_the_option(tmp_path):
    pytest.importorskip("pyld")
    vector = next(v for v in MANIFEST if v["id"] == "jsonld-unknown-term")
    source = tmp_path / "in.jsonld"
    source.write_bytes(vector_bytes(vector))
    failed = bioheaders_command("validate", source)
    assert failed.returncode == 1
    assert failed.stderr == (
        b"FHR: JSON-LD term not in the FHR mapping: http://schema.org/keywords "
        b"(at the record)\n"
    )
    for command in (("validate", source), ("convert", source, tmp_path / "out.json")):
        result = bioheaders_command(command[0], "--ignore-unknown-terms", *command[1:])
        assert result.returncode == 0, result.stderr
        assert result.stderr == (
            b"FHR: warning: JSON-LD term not in the FHR mapping: "
            b"http://schema.org/keywords (at the record)\n"
        )
    assert "keywords" not in json.loads((tmp_path / "out.json").read_text())


def test_ignore_unknown_terms_does_not_hide_other_errors(tmp_path):
    pytest.importorskip("pyld")
    vector = next(v for v in MANIFEST if v["id"] == "jsonld-two-nodes")
    source = tmp_path / "in.jsonld"
    source.write_bytes(vector_bytes(vector))
    result = bioheaders_command("validate", "--ignore-unknown-terms", source)
    assert result.returncode == 1
    assert result.stderr == (
        b"FHR: JSON-LD must describe exactly one FHR record (found 2 nodes)\n"
    )


def test_malformed_context_reports_a_clean_error(tmp_path):
    pytest.importorskip("pyld")
    with pytest.raises(ValueError) as error:
        jsonld.expand({"@context": {"@language": None}})
    assert str(error.value).startswith("invalid JSON-LD: ")
    # A reader refuses such a context (J3) before PyLD sees it.
    source = tmp_path / "lang.jsonld"
    source.write_text('{"@context": {"@language": null}}')
    result = bioheaders_command("validate", source)
    assert result.returncode == 1
    assert result.stderr.startswith(
        b"FHR: JSON-LD: the @context is an embedded context that is not the FHR context"
    )
    assert b"Traceback" not in result.stderr
    # PyLD's errors inside a document that passes J3 are reported cleanly too.
    source.write_text(
        json.dumps({"@context": jsonld.RAW_MAIN_CONTEXT_URL, "@graph": {"@value": 1}})
    )
    result = bioheaders_command("validate", source)
    assert result.returncode == 1
    assert result.stderr.startswith(b"FHR: ")
    assert b"Traceback" not in result.stderr


@pytest.mark.parametrize(
    "name, message",
    [
        (
            "jsonld-two-nodes",
            "JSON-LD must describe exactly one FHR record (found 2 nodes)",
        ),
        (
            "jsonld-two-genome-values",
            "JSON-LD gives 2 values for single-valued field genome",
        ),
        (
            "jsonld-remote-context",
            "JSON-LD context is not available offline: https://schema.org/",
        ),
        ("jsonld-root-id", "JSON-LD term not in the FHR mapping: @id (at the record)"),
        (
            "jsonld-datetime-datecreated",
            "JSON-LD gives field dateCreated the datatype "
            "http://www.w3.org/2001/XMLSchema#dateTime; allowed: only xsd:date or no datatype",
        ),
        (
            "jsonld-flattened",
            "JSON-LD gives field taxon only as a reference to "
            "https://identifiers.org/taxonomy:9606 (flattened form), which is not supported",
        ),
    ],
)
def test_error_messages(name, message):
    pytest.importorskip("pyld")
    vector = next(v for v in MANIFEST if v["id"] == name)
    with pytest.raises(ValueError) as error:
        jsonld.from_jsonld(json.loads(vector_bytes(vector)))
    assert str(error.value) == message


@pytest.mark.parametrize(
    "value, message",
    [
        ({"@value": "x", "@language": "en"}, "language-tagged value for field genome"),
        (
            {"@value": "1", "@type": "http://www.w3.org/2001/XMLSchema#string"},
            "datatype",
        ),
        ({"@id": "https://example.org/x"}, "a node for field genome"),
    ],
)
def test_value_rules(metadata, value, message):
    pytest.importorskip("pyld")
    document = expanded(written(metadata))
    document[0]["http://schema.org/name"] = [value]
    with pytest.raises(ValueError, match=message):
        jsonld.from_jsonld(document)


def test_iri_field_accepts_id_or_string(metadata):
    pytest.importorskip("pyld")
    document = expanded(written(metadata))
    link = "https://w3id.org/fair-bioheaders/terms#relatedLink"
    document[0][link] = [
        {"@value": "https://example.org/a"},
        {"@id": "https://example.org/b"},
    ]
    back = jsonld.from_jsonld(document)
    assert back["relatedLink"] == ["https://example.org/a", "https://example.org/b"]
