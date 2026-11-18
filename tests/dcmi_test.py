# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Independent RDF expectations and fail-closed preservation for mapping-v1."""

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, RDF, RDFS

from bioheaders.dcmi import export_assembly

FIXTURES = Path(__file__).parent / "fixtures/dcmi"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(
            "DCMI export and independent Turtle parsing must stay offline"
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def inputs(tmp_path, source=None, context=None):
    for name, value in (("source", source), ("context", context)):
        content = (FIXTURES / (name + ".json")).read_bytes()
        if value is not None:
            content = json.dumps(value, ensure_ascii=True).encode()
        (tmp_path / (name + ".json")).write_bytes(content)
    return tmp_path / "source.json", tmp_path / "context.json", tmp_path / "bundle"


def rich():
    return tuple(
        json.loads((FIXTURES / (name + ".json")).read_bytes())
        for name in ("source", "context")
    )


def graph(bundle):
    return Graph().parse(bundle / "qualified-dc.ttl", format="turtle")


@pytest.mark.parametrize("name", ["", "minimal"])
def test_independently_curated_graph_and_exact_preservation(tmp_path, name):
    fixture = FIXTURES / name
    source, context = fixture / "source.json", fixture / "context.json"
    bundle = tmp_path / "bundle"
    report = export_assembly(source, context, bundle)
    assert report["status"] == "exported" and report["errors"] == []
    expected = Graph().parse(fixture / "qualified-dc.ttl", format="turtle")
    assert isomorphic(graph(bundle), expected)
    for original in (source, context):
        preserved = bundle / original.name
        assert preserved.read_bytes() == original.read_bytes()
        assert (
            report["preserved_inputs"][original.stem]["sha256"]
            == hashlib.sha256(original.read_bytes()).hexdigest()
        )
    again = tmp_path / "again"
    export_assembly(source, context, again)
    assert {p.name: p.read_bytes() for p in bundle.iterdir()} == {
        p.name: p.read_bytes() for p in again.iterdir()
    }


def test_report_is_explicit_about_loss_optional_context_and_non_deposit(tmp_path):
    source, context, bundle = inputs(tmp_path)
    report = export_assembly(source, context, bundle)
    assert report["target"]["version"] == "2020-01-20"
    assert report["source_schema_version"] == "2.0"
    assert len(report["source_root_fields_not_projected"]) == 15
    assert "/checksum" in report["source_root_fields_not_projected"]
    assert report["not_supplied_context"] == ["resourceDOI"]
    assert any(e["path"] == "/publicationYear" for e in report["omissions"])
    assert report["registration_readiness"] == {
        "crossref": "not-assessed",
        "datacite": "not-assessed",
    }
    assert (
        "order" in report["limitations"][0] and "nameType" in report["limitations"][0]
    )


def test_order_and_author_classification_preserved_but_not_inferred(tmp_path):
    source, context = rich()
    source["assemblyAuthor"] = [
        {"name": "Group Z", "nameType": "Organizational"},
        {"name": "Person A", "nameType": "Personal"},
    ]
    paths = inputs(tmp_path, source, context)
    assert export_assembly(*paths)["status"] == "exported"
    g = graph(paths[2])
    assembly = URIRef(context["resourceIRI"])
    authors = list(g.objects(assembly, DCTERMS.creator))
    assert {str(g.value(a, RDFS.label)) for a in authors} == {"Group Z", "Person A"}
    assert all(set(g.objects(a, RDF.type)) == {DCTERMS.Agent} for a in authors)
    assert (
        json.loads((paths[2] / "source.json").read_bytes())["assemblyAuthor"]
        == source["assemblyAuthor"]
    )


def test_literal_and_iri_escaping_is_rdf_not_turtle_injection(tmp_path):
    source, context = rich()
    context["title"] = 'A "quoted" title\\path\nwith\ttabs 雪 😀 ; dc:evil "x"'
    source["reuseConditions"] = 'Rights\b\f\r\n\\"'
    # URI syntax permits apostrophes, Unicode and query punctuation; no fetch.
    context["resourceIRI"] = "https://example.org/%E9%9B%AA?q='quoted'&a=1"
    paths = inputs(tmp_path, source, context)
    assert export_assembly(*paths)["status"] == "exported"
    g = graph(paths[2])
    assert g.value(URIRef(context["resourceIRI"]), DCTERMS.title) == Literal(
        context["title"]
    )
    rights = g.value(URIRef(context["resourceIRI"]), DCTERMS.rights)
    assert g.value(rights, RDFS.label) == Literal(source["reuseConditions"])
    assert not any(str(p).endswith("evil") for _, p, _ in g)


@pytest.mark.parametrize(
    "case",
    [
        "date",
        "identity",
        "doi",
        "resolver",
        "missing-checksum",
        "type",
        "latest",
        "raw-main",
        "unknown-context",
        "surrogate",
        "incomplete",
        "list-schema",
    ],
)
def test_rejections_preserve_raw_inputs_without_turtle(tmp_path, case):
    source, context = rich()
    if case == "date":
        context["publicationYear"] = 2025
    elif case == "identity":
        context["metadataRecordIRI"] = context["resourceIRI"]
    elif case == "doi":
        context["resourceDOI"] = source["scholarlyArticle"].upper()
    elif case == "resolver":
        context["resourceIRI"] = "https://DX.DOI.ORG/10.1093%2Fbib%2Fbbae122"
    elif case == "missing-checksum":
        del source["checksum"]
    elif case == "type":
        source["schema"] = "https://w3id.org/fair-bioheaders/fhp/v0.4.0"
    elif case == "raw-main":
        source["schema"] = (
            "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/fhr.json"
        )
    elif case == "latest":
        source["schema"] = "https://w3id.org/fair-bioheaders/fhr/v0.6.0"
        source["schemaVersion"] = "2.1"
    elif case == "unknown-context":
        context["invented"] = "value"
    elif case == "surrogate":
        context["title"] = "bad\ud800"
    elif case == "list-schema":
        source["schema"] = []
    else:
        source = {"schema": source["schema"], "schemaVersion": "2.0"}
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected" and report["errors"]
    assert all(e["path"].startswith("/") and e["reason"] for e in report["errors"])
    assert not (paths[2] / "qualified-dc.ttl").exists()
    assert (paths[2] / "source.json").read_bytes() == paths[0].read_bytes()
    assert (paths[2] / "context.json").read_bytes() == paths[1].read_bytes()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"title":1,"title":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b"\xff",
        b"{",
        b"[]",
    ],
)
def test_invalid_raw_json_still_preserved(tmp_path, raw):
    paths = inputs(tmp_path)
    paths[1].write_bytes(raw)
    report = export_assembly(*paths)
    assert report["status"] == "rejected" and report["errors"]
    assert (paths[2] / "context.json").read_bytes() == raw
    assert not (paths[2] / "qualified-dc.ttl").exists()


def test_unprojected_context_never_becomes_new_graph_mapping(tmp_path):
    source, context = rich()
    del context["publicationDate"]
    context["resourceDOI"] = "10.1234/assembly"
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "exported"
    g = graph(paths[2])
    assembly = URIRef(context["resourceIRI"])
    assert not list(g.objects(assembly, DCTERMS.issued))
    assert list(g.objects(assembly, DCTERMS.identifier)) == [
        Literal(context["resourceIRI"])
    ]
    assert {e["path"] for e in report["omissions"]} >= {
        "/publicationYear",
        "/resourceDOI",
    }


@pytest.mark.parametrize("target", ["directory", "file", "symlink"])
def test_existing_output_and_inputs_never_overwritten(tmp_path, target):
    paths = inputs(tmp_path)
    if target == "directory":
        paths[2].mkdir()
        (paths[2] / "sentinel").write_text("keep")
    elif target == "file":
        paths[2].write_text("keep")
    else:
        paths[2].symlink_to(tmp_path, target_is_directory=True)
    before = paths[0].read_bytes()
    with pytest.raises(FileExistsError):
        export_assembly(*paths)
    assert paths[0].read_bytes() == before
    assert not (tmp_path / "report.json").exists()


def test_installed_cli_outside_checkout(tmp_path):
    """CI installs a noneditable wheel before pytest; verify imported artifact."""
    cli = str(Path(sys.executable).with_name("bioheaders"))
    assert Path(cli).is_file()
    assert cli
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    paths = inputs(tmp_path)
    result = subprocess.run(
        [cli, "export-dcmi", *map(str, paths)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert isomorphic(
        graph(paths[2]), Graph().parse(FIXTURES / "qualified-dc.ttl", format="turtle")
    )
    rejected = tmp_path / "rejected"
    paths[1].write_bytes(b"bad json")
    result = subprocess.run(
        [cli, "export-dcmi", str(paths[0]), str(paths[1]), str(rejected)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
    )
    assert result.returncode == 1
    assert (rejected / "context.json").read_bytes() == b"bad json"
    assert not (rejected / "qualified-dc.ttl").exists()
    artifact = subprocess.run(
        [
            sys.executable,
            "-c",
            "import bioheaders.dcmi; print(bioheaders.dcmi.__file__)",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    installed = Path(artifact.stdout.strip())
    assert "site-packages" in installed.parts
    assert (
        installed.read_bytes()
        == (Path(__file__).parents[1] / "bioheaders/dcmi.py").read_bytes()
    )


def test_independent_comparison_detects_wrong_creator_subject_and_date(tmp_path):
    paths = inputs(tmp_path)
    export_assembly(*paths)
    actual = graph(paths[2])
    for fault in ("creator", "date", "subject"):
        wrong = Graph().parse(FIXTURES / "qualified-dc.ttl", format="turtle")
        assembly = URIRef("https://example.org/assemblies/synthetic-v1")
        record = URIRef("https://example.org/metadata/synthetic-v1")
        if fault == "date":
            wrong.remove((assembly, DCTERMS.created, None))
            wrong.add((assembly, DCTERMS.created, Literal("2026-02-02")))
        elif fault == "creator":
            creator = wrong.value(assembly, DCTERMS.creator)
            wrong.remove((assembly, DCTERMS.creator, creator))
            wrong.add((record, DCTERMS.creator, creator))
        else:
            wrong.remove((record, DCTERMS.subject, assembly))
            wrong.add((assembly, DCTERMS.subject, record))
        assert not isomorphic(actual, wrong), fault


@pytest.mark.parametrize("article", ["10.1/example", "10.1234.567/example"])
def test_otherwise_source_valid_article_without_safe_doi_is_omitted(tmp_path, article):
    source, context = rich()
    source["scholarlyArticle"] = article
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "exported"
    assert any(e["path"] == "/scholarlyArticle" for e in report["omissions"])
    assert not any(
        str(o).startswith("https://doi.org/")
        for o in graph(paths[2]).objects(None, DCTERMS.relation)
    )


def test_article_doi_with_a_trailing_newline_fails_the_source_schema(tmp_path):
    # The schema's DOI pattern ends in $, which matches only at the end of the
    # value (ECMA-262), not before a final newline as Python's $ does.
    source, context = rich()
    source["scholarlyArticle"] = "10.1093/bib/bbae122\n"
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    assert [e["path"] for e in report["errors"]] == ["/scholarlyArticle"]
    assert not (paths[2] / "qualified-dc.ttl").exists()


def test_packaged_assets_match_reviewed_bytes(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    code = "from importlib.resources import files; import hashlib,json; print(json.dumps({n:hashlib.sha256(files('bioheaders').joinpath('mappings/'+n).read_bytes()).hexdigest() for n in ['assembly-export-context.schema.json','loss-notes.json']}))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__).parents[1] / "bioheaders/mappings").glob("*.json")
    }


def test_failed_graph_write_cannot_leave_a_success_report(tmp_path, monkeypatch):
    paths = inputs(tmp_path)
    original_write = Path.write_text

    def fail_graph(self, *args, **kwargs):
        if self.name == "qualified-dc.ttl":
            raise OSError("deliberate graph write failure")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_graph)
    with pytest.raises(OSError, match="deliberate graph write failure"):
        export_assembly(*paths)
    assert not (paths[2] / "report.json").exists()
    assert (paths[2] / "source.json").read_bytes() == paths[0].read_bytes()
    assert (paths[2] / "context.json").read_bytes() == paths[1].read_bytes()
    with pytest.raises(FileExistsError):
        export_assembly(*paths)


@pytest.mark.parametrize(
    "doi, expected",
    [
        ("10.1234/foo>bar", "https://doi.org/10.1234/foo%3Ebar"),
        ("10.1234/foo?bar#tail", "https://doi.org/10.1234/foo%3Fbar%23tail"),
        ("10.1234/50%", "https://doi.org/10.1234/50%25"),
        ("10.1234/雪", "https://doi.org/10.1234/%E9%9B%AA"),
    ],
)
def test_article_doi_characters_stay_in_resolver_path(tmp_path, doi, expected):
    source, context = rich()
    source["scholarlyArticle"] = doi
    paths = inputs(tmp_path, source, context)
    assert export_assembly(*paths)["status"] == "exported"
    relations = set(
        graph(paths[2]).objects(URIRef(context["resourceIRI"]), DCTERMS.relation)
    )
    assert URIRef(expected) in relations
    assert (
        json.loads((paths[2] / "source.json").read_bytes())["scholarlyArticle"] == doi
    )


def test_encoded_article_resolver_is_still_not_an_assembly_identity(tmp_path):
    source, context = rich()
    source["scholarlyArticle"] = "10.1234/foo?bar#tail"
    context["resourceIRI"] = "https://doi.org/10.1234/foo%3Fbar%23tail"
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    assert any(e["path"] == "/resourceIRI" for e in report["errors"])
    assert not (paths[2] / "qualified-dc.ttl").exists()


def test_mutating_returned_report_does_not_change_the_next_export(tmp_path):
    paths = inputs(tmp_path)
    report = export_assembly(*paths)
    first = (paths[2] / "report.json").read_bytes()
    report["limitations"].append("Caller annotation, not a module-wide policy")
    second = tmp_path / "second-bundle"
    export_assembly(paths[0], paths[1], second)
    assert (second / "report.json").read_bytes() == first


@pytest.mark.parametrize(
    "article, record_iri",
    [
        ("10.1093/bib/bbae122", "https://doi.org/10.1093/bib/bbae122"),
        ("10.1093/bib/bbae122", "http://DX.DOI.ORG/10.1093%2Fbib%2FBBAE122"),
        ("10.1234/foo?bar#tail", "https://doi.org/10.1234/foo%3Fbar%23tail"),
    ],
)
def test_article_cannot_be_the_metadata_record(tmp_path, article, record_iri):
    source, context = rich()
    source["scholarlyArticle"] = article
    context["metadataRecordIRI"] = record_iri
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    assert any(e["path"] == "/metadataRecordIRI" for e in report["errors"])
    assert not (paths[2] / "qualified-dc.ttl").exists()
    assert (paths[2] / "source.json").read_bytes() == paths[0].read_bytes()
    assert (paths[2] / "context.json").read_bytes() == paths[1].read_bytes()


@pytest.mark.parametrize(
    "resource_iri, resource_doi, record_iri",
    [
        (
            "https://doi.org/10.1234/assembly",
            None,
            "http://DX.DOI.ORG/10.1234%2FASSEMBLY",
        ),
        (
            "https://example.org/assembly",
            "10.1234/assembly",
            "https://doi.org/10.1234/ASSEMBLY",
        ),
    ],
)
def test_doi_alias_cannot_merge_assembly_and_metadata_record(
    tmp_path, resource_iri, resource_doi, record_iri
):
    source, context = rich()
    context["resourceIRI"] = resource_iri
    context["metadataRecordIRI"] = record_iri
    if resource_doi is None:
        context.pop("resourceDOI", None)
    else:
        context["resourceDOI"] = resource_doi
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    assert any(e["path"] == "/metadataRecordIRI" for e in report["errors"])
    assert not (paths[2] / "qualified-dc.ttl").exists()
    assert (paths[2] / "source.json").read_bytes() == paths[0].read_bytes()
    assert (paths[2] / "context.json").read_bytes() == paths[1].read_bytes()


@pytest.mark.parametrize(
    "where, path, value",
    [
        ("source", "/relatedLink/0", "javascript:alert(1)"),
        ("source", "/relatedLink/0", "https://example.org/x\n"),
        ("source", "/assemblyProtocol", "data:text/html,<script>"),
        ("source", "/assemblyProtocol", "https://example.org/‮evil"),
        ("source", "/taxon/uri", "file:///etc/passwd"),
        ("context", "/metadataRecordIRI", "https://example.org/rec\x00ord"),
        ("context", "/metadataRecordIRI", "https://example.org/a b"),
    ],
)
def test_every_iri_passes_the_r14_link_check(tmp_path, where, path, value):
    """No input value becomes an IRI unless jsonld.link_problem accepts it, and
    a JSON Schema ``$`` pattern's trailing newline is not let through."""
    source, context = rich()
    target = source if where == "source" else context
    if path == "/relatedLink/0":
        target["relatedLink"] = [value]
    elif path == "/taxon/uri":
        target["taxon"]["uri"] = value
    else:
        target[path[1:]] = value
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    # The schema's own format and pattern checks already refuse some of these.
    assert (where, path) in {(e["input"], e["path"]) for e in report["errors"]}
    assert not (paths[2] / "qualified-dc.ttl").exists()
    assert (paths[2] / "source.json").read_bytes() == paths[0].read_bytes()


@pytest.mark.parametrize(
    "where, path, value",
    [
        ("source", "/relatedLink/0", "javascript:alert(1)"),
        ("source", "/relatedLink/0", "https://example.org/x\n"),
    ],
)
def test_link_check_is_what_refuses_values_the_schema_admits(
    tmp_path, where, path, value
):
    source, context = rich()
    if where == "source":
        source["relatedLink"] = [value]
    else:
        context["resourceIRI"] = value
    report = export_assembly(*inputs(tmp_path, source, context))
    assert [(e["input"], e["path"]) for e in report["errors"]] == [(where, path)]
    assert "R14" in report["errors"][0]["reason"]


def test_context_iri_trailing_newline_is_refused_by_ecma_pattern(tmp_path):
    source, context = rich()
    context["resourceIRI"] += "\n"
    paths = inputs(tmp_path, source, context)
    report = export_assembly(*paths)
    assert report["status"] == "rejected"
    assert [(e["input"], e["path"]) for e in report["errors"]] == [
        ("context", "/resourceIRI")
    ]
    assert "does not match" in report["errors"][0]["reason"]
    assert not (paths[2] / "qualified-dc.ttl").exists()
    assert (paths[2] / "context.json").read_bytes() == paths[1].read_bytes()


@pytest.mark.parametrize("depth", [100_000, 2_000])
def test_deeply_nested_json_gives_a_rejected_report(tmp_path, depth):
    paths = inputs(tmp_path)
    raw = b'{"x":' + b"[" * depth + b"]" * depth + b"}"
    paths[0].write_bytes(raw)
    report = export_assembly(*paths)
    assert report["status"] == "rejected" and report["errors"]
    assert (paths[2] / "source.json").read_bytes() == raw
    assert not (paths[2] / "qualified-dc.ttl").exists()


def test_deeply_nested_json_cli_writes_the_rejected_bundle(tmp_path):
    paths = inputs(tmp_path)
    paths[0].write_bytes(b'{"x":' + b"[" * 100_000 + b"]" * 100_000 + b"}")
    result = subprocess.run(
        [str(Path(sys.executable).parent / "bioheaders"), "export-dcmi", *paths],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert (
        "nested too deeply"
        in json.loads((paths[2] / "report.json").read_text())["errors"][0]["reason"]
    )
