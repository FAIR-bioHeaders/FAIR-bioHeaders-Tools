# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""JSON-LD contexts (J3), link schemes (R14) and HTML embedding (J8).

FAIR-bioHeaders-Specification docs/JSONLD.md and docs/FORMAT.md. A document read
by expansion may use only the FHR context; IRI-valued fields are written as
links only with an accepted scheme, and validators warn about others; JSON-LD
inside a script element and microdata text keep hostile values inert.
"""

import copy
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from bioheaders import fhr, jsonld, link_scheme_warnings

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
# Values that end or re-open an HTML script element, or a CDATA section, unless
# escaped, and the line and paragraph separators.
HOSTILE = [
    "</script>",
    "<!--<script>",
    "</SCRIPT >",
    "]]>",
    "a & b < c > d",
    "\"quoted\" 'single'",
    "x y z",
    "&lt;already escaped&gt;",
]
OTHER_SCHEMES = [
    "javascript:void(0)",
    "JavaScript:void(0)",
    " javascript:void(0)",
    "java\tscript:void(0)",
    "data:text/plain,x",
    "vbscript:x",
    "file:///etc/hosts",
    "https:/example.org/one-slash",
    "https:///no-host",
    " https://example.org/padded",
    "https://example.org/a b",
    "\uff4aavascript:void(0)",  # A fullwidth j.
    "https://example.org/\u202eevil",  # A bidirectional override (RFC 3987 4.1).
    "https://example.org/\x85next-line",
]
ACCEPTED = [
    "https://example.org/a",
    "HTTPS://EXAMPLE.ORG/B",
    "http://example.org/c",
    "ftp://ftp.example.org/genomes/x.fa.gz",
    "urn:uuid:6e8bc430-9c3a-11d9-9669-0800200c9a66",
    "doi:10.1000/182",
    "info:doi/10.1000/182",
]


def load(path):
    return json.loads((ROOT / path).read_text())


@pytest.fixture
def metadata():
    return load("examples/example.fhr.json")


def bioheaders(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], capture_output=True, text=True
    )


# J3: only the FHR context.


def remapped(context, *pairs):
    body = copy.deepcopy(context)
    for left, right in pairs:
        body[left], body[right] = body[right], body[left]
    return body


def hostile_contexts(document):
    context = document["@context"]
    body = {k: v for k, v in document.items() if k != "@context"}
    url = jsonld.RAW_MAIN_CONTEXT_URL
    swapped = remapped(context, ("genome", "documentation"))
    return {
        "remapped": {"@context": swapped, **body},
        "remapped-in-array": {"@context": [swapped], **body},
        "url-plus-local": {
            "@context": [url, {"title": "http://schema.org/name"}],
            **body,
        },
        "local-plus-url": {"@context": [{"@vocab": "http://schema.org/"}, url], **body},
        "import": {
            "@context": {
                "@version": 1.1,
                "@import": url,
                "genome": {"@id": "sdo:description"},
                "documentation": {"@id": "sdo:name"},
            },
            **body,
        },
        "vocab": {"@context": {"@vocab": "http://schema.org/"}, **body},
        "base": {
            "@context": dict(context, **{"@base": "https://example.org/"}),
            **body,
        },
        "protected-false": {"@context": dict(context, **{"@protected": False}), **body},
        "protected-one": {"@context": dict(context, **{"@protected": 1}), **body},
        "version-string": {"@context": dict(context, **{"@version": "1.1"}), **body},
        "null": {"@context": None, **body},
        "empty": {"@context": {}, **body},
        "two-urls": {"@context": [url, url], **body},
        "nested-taxon": {
            "@context": url,
            **dict(body, taxon=dict(body["taxon"], **{"@context": {"name": "@id"}})),
        },
        "nested-graph": {
            "@context": url,
            "@graph": [{"@context": {"@vocab": "http://schema.org/"}, **body}],
        },
        "nested-fhr-copy": {
            "@context": url,
            "@graph": [{"@context": url, **body}],
        },
        "nested-in-value": {
            "@context": url,
            **dict(body, genome={"@value": {"@context": {}}, "@type": "@json"}),
        },
        "top-level-array": [{"@context": swapped, **body}],
        "nest": {
            "@context": url,
            **{k: v for k, v in body.items() if k != "genome"},
            "@nest": {"genome": body["genome"]},
        },
        "nest-in-taxon": {
            "@context": url,
            **dict(body, taxon={"@nest": body["taxon"]}),
        },
        "remote": {"@context": "https://schema.org/", **body},
        "remote-in-array": {"@context": ["https://schema.org/"], **body},
    }


def test_writer_output_with_a_swapped_context_is_refused(metadata):
    metadata["documentation"] = "Documentation text"
    document = jsonld.to_jsonld(metadata)
    swapped = dict(
        document,
        **{"@context": remapped(document["@context"], ("genome", "documentation"))},
    )
    with pytest.raises(ValueError, match=r"J3\)"):
        jsonld.from_jsonld(swapped)


@pytest.mark.parametrize(
    "name",
    list(hostile_contexts(jsonld.to_jsonld(load("examples/example.fhr.json")))),
)
def test_only_the_fhr_context_is_read(metadata, name, monkeypatch):
    document = hostile_contexts(jsonld.to_jsonld(metadata))[name]
    assert not jsonld.is_canonical(document)
    # The refusal needs no JSON-LD processor: it comes before expansion.
    monkeypatch.setitem(sys.modules, "pyld", None)
    with pytest.raises(ValueError) as error:
        jsonld.from_jsonld(document)
    message = str(error.value)
    assert "docs/JSONLD.md J3" in message or message.startswith(
        "JSON-LD context is not available offline: "
    ), message


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d,
        lambda d: dict(d, **{"@context": [jsonld.RAW_MAIN_CONTEXT_URL]}),
        lambda d: dict(d, **{"@context": [d["@context"]]}),
        lambda d: dict(d, **{"@context": dict(reversed(list(d["@context"].items())))}),
        lambda d: {
            "@context": d["@context"],
            "@graph": [{k: v for k, v in d.items() if k != "@context"}],
        },
    ],
)
def test_the_fhr_context_alone_is_read(metadata, change):
    pytest.importorskip("pyld")
    document = change(jsonld.to_jsonld(metadata))
    jsonld.check_contexts(document)
    assert jsonld.from_jsonld(document) == metadata


def test_context_equality_keeps_json_types_apart(metadata):
    document = jsonld.to_jsonld(metadata)
    assert jsonld.is_canonical(document)
    for key, value in (("@protected", 1), ("@version", "1.1")):
        changed = dict(
            document, **{"@context": dict(document["@context"], **{key: value})}
        )
        assert not jsonld.is_canonical(changed)
        assert not jsonld.is_fhr_context(changed["@context"])


def test_fhp_reads_only_its_canonical_context():
    record = load("examples/fhp/rich-database.fhp.json")
    document = jsonld.fhp_to_jsonld(record)
    assert jsonld.fhp_canonical_record(document) == record
    context = document["@context"]
    for value in (
        remapped(context, ("proteome", "documentation")),
        [context],
        [jsonld.FHP_RAW_MAIN_CONTEXT_URL],
        dict(context, **{"@protected": 1}),
        {"@import": jsonld.FHP_RAW_MAIN_CONTEXT_URL},
    ):
        data = fhr()
        with pytest.raises(ValueError):
            data.input_jsonld(json.dumps(dict(document, **{"@context": value})))


# R14: link schemes.


@pytest.mark.parametrize("value", ACCEPTED)
def test_accepted_links_are_written(metadata, value):
    metadata["relatedLink"] = [value]
    assert jsonld.to_jsonld(metadata)["relatedLink"] == [value]
    assert jsonld.to_export(metadata)["@graph"][0]["fhr:relatedLink"] == [
        {"@id": value}
    ]
    assert link_scheme_warnings(metadata) == []


@pytest.mark.parametrize("value", OTHER_SCHEMES)
@pytest.mark.parametrize(
    "field",
    ["relatedLink", "assemblyProtocol", "accessionID.url", "assemblySoftware.uri"],
)
def test_other_schemes_are_refused_by_writers(metadata, field, value):
    if field == "relatedLink":
        metadata["relatedLink"] = ["https://example.org/ok", value]
    elif field == "assemblyProtocol":
        metadata["assemblyProtocol"] = value
    elif field == "accessionID.url":
        metadata["accessionID"] = dict(metadata["accessionID"], url=value)
    else:
        metadata["assemblySoftware"] = [{"name": "x", "uri": value}]
    for write in (jsonld.to_jsonld, jsonld.to_export):
        with pytest.raises(ValueError, match="R14"):
            write(metadata)
    messages = link_scheme_warnings(metadata)
    assert len(messages) == 1 and "R14" in messages[0], messages
    # The value itself is never echoed (it may hold control characters).
    assert value not in messages[0]


def test_fhp_writer_refuses_other_schemes_and_warns():
    record = load("examples/fhp/rich-database.fhp.json")
    record["source"][0]["url"] = "javascript:void(0)"
    with pytest.raises(
        ValueError, match=r"source\[0\]\.url uses the URI scheme 'javascript'"
    ):
        jsonld.fhp_to_jsonld(record)
    assert [m.split(" ")[0] for m in link_scheme_warnings(record)] == ["source[0].url"]


def test_fhgff3_validator_warns():
    record = load("examples/fhgff3/minimal-reference.fhgff3.json")
    record["annotationProtocol"] = "file:///protocol.txt"
    assert [m.split(" ")[0] for m in link_scheme_warnings(record)] == [
        "annotationProtocol"
    ]


@pytest.mark.parametrize(
    "value, promoted",
    [
        ("https://example.org/README", True),
        ("HTTPS://EXAMPLE.ORG/README", True),
        ("ftp://example.org/README", True),
        ("file:///data/README", False),
        ("javascript://example.org/%0A", False),
        ("data://text/plain,x", False),
        (" https://example.org/README", False),
        ("https:///README", False),
        ("urn:example:readme", False),
    ],
)
def test_only_urls_are_promoted_to_links(metadata, value, promoted):
    metadata["documentation"] = value
    metadata["reuseConditions"] = value
    document = jsonld.to_jsonld(metadata)
    assert ("subjectOf" in document) == promoted
    assert ("documentation" in document) != promoted
    assembly = jsonld.to_export(metadata)["@graph"][0]
    assert ({"@id": value} in assembly.get("subjectOf", [])) == promoted
    assert (assembly["license"] == {"@id": value}) == promoted
    assert (assembly.get("description") == value) != promoted
    back = jsonld.from_jsonld(json.loads(json.dumps(document)))
    assert back["documentation"] == value


@pytest.mark.parametrize("key", ["id", "url"])
def test_export_context_links_need_a_url_scheme(key):
    jsonld.check_export({key: "https://example.org/x"})
    for value in ("javascript://example.org/x", "file:///x", "urn:uuid:1"):
        with pytest.raises(ValueError, match="http, https or ftp"):
            jsonld.check_export({key: value})


def test_cli_warns_and_refuses_to_write_links(metadata, tmp_path):
    metadata["relatedLink"] = ["javascript:void(0)"]
    source = tmp_path / "in.json"
    source.write_text(json.dumps(metadata))
    result = bioheaders("validate", source)
    assert result.returncode == 0, result.stderr
    assert result.stderr == (
        "FHR: warning: relatedLink[0] uses the URI scheme 'javascript'; links should "
        "use http or https (accepted: http, https, ftp, urn, doi, info; "
        "docs/FORMAT.md R14)\n"
    )
    for args in ((), ("--jsonld-profile", "export")):
        result = bioheaders("convert", source, tmp_path / "out.jsonld", *args)
        assert result.returncode == 1
        assert "it is not written as a link" in result.stderr.splitlines()[-1]
        assert not (tmp_path / "out.jsonld").exists()
    # Other outputs keep the value, with the warning.
    for name in ("out.yaml", "out.html"):
        result = bioheaders("convert", source, tmp_path / name)
        assert result.returncode == 0, result.stderr
        assert "warning: relatedLink[0]" in result.stderr


def test_combine_and_verify_warn_for_a_fasta_header(tmp_path):
    data = fhr(**load("examples/example.fhr.json"))
    data.relatedLink = ["javascript:void(0)"]
    sequence = tmp_path / "plain.fasta"
    sequence.write_text(">c1\nACGT\n")
    metadata = tmp_path / "m.json"
    metadata.write_text(data.output_json())
    combined = tmp_path / "x.fhr.fasta"
    result = bioheaders("combine", metadata, sequence, "-o", combined)
    assert result.returncode == 0, result.stderr
    assert "warning: relatedLink[0]" in result.stderr
    result = bioheaders("verify", combined)
    assert result.returncode == 0, result.stderr
    assert "warning: relatedLink[0]" in result.stderr


# J8 and microdata: hostile values stay text.


class Page(HTMLParser):
    """Element and comment events, as an HTML tokenizer sees them."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.starts, self.ends, self.comments, self.text = [], [], [], []

    def handle_starttag(self, tag, attrs):
        self.starts.append(tag)

    def handle_endtag(self, tag):
        self.ends.append(tag)

    def handle_comment(self, data):
        self.comments.append(data)

    def handle_data(self, data):
        self.text.append(data)


def test_script_element_keeps_hostile_values_inside(metadata):
    metadata["genomeSynonym"] = HOSTILE
    element = jsonld.script_element(jsonld.to_jsonld(metadata))
    inner = element.split(">", 1)[1].rsplit("</script>", 1)[0]
    assert not set("<>&  ") & set(inner)
    page = Page()
    page.feed(element + "<p>after</p>")
    page.close()
    assert page.starts == ["script", "p"] and page.ends == ["script", "p"]
    assert json.loads(page.text[0])["genomeSynonym"] == HOSTILE
    assert jsonld.from_jsonld(json.loads(page.text[0])) == metadata


def test_script_text_is_the_same_json():
    text = json.dumps({"v": HOSTILE, "n": 1.5, "t": True}, ensure_ascii=False)
    assert json.loads(jsonld.script_text(text)) == json.loads(text)


@pytest.mark.parametrize(
    "path",
    ["examples/example.fhr.json", "examples/fhp/rich-database.fhp.json"],
)
def test_microdata_writers_escape_hostile_values(path, tmp_path):
    record = load(path)
    record["documentation"] = " ".join(HOSTILE)
    record["relatedLink"] = ["javascript:void(0)"]
    data = fhr(**record)
    html = data.output_microdata()
    assert "<script" not in html.lower() and "</script" not in html.lower()
    assert "<!--" not in html and "]]>" not in html
    assert 'href="javascript' not in html and "src=" not in html
    page = Page()
    page.feed(html)
    page.close()
    assert "script" not in page.starts and page.comments == []
    back = fhr()
    back.input_microdata(html)
    assert back.__dict__["documentation"] == record["documentation"]
    assert back.__dict__["relatedLink"] == ["javascript:void(0)"]
