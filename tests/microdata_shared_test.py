# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Cross-family regressions from the post-merge review of #139 (#140)."""

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
BIN = Path(sys.executable).parent
CASES = [
    (fhp_microdata, FHP_SCHEMA, "fhp/minimal-predicted.fhp.json"),
    (fhgff3_microdata, FHGFF3_SCHEMA, "fhgff3/minimal-reference.microdata.fhgff3.json"),
]
pytestmark = pytest.mark.filterwarnings("ignore:FHGFF3 HTML microdata is experimental")


def record(path):
    return json.loads((ROOT / "examples" / path).read_text())


@pytest.mark.parametrize("module,schema,path", CASES)
@pytest.mark.parametrize("suffix", ["\n", "\r", "\r\n", " ", "?extra=1"])
@pytest.mark.parametrize("raw", [False, True])
def test_schema_urls_match_the_entire_value(module, schema, path, suffix, raw):
    data = record(path)
    family = "fhp" if module is fhp_microdata else "fhgff3"
    url = (
        f"https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/v0.4.0/{family}.json"
        if raw
        else f"https://w3id.org/fair-bioheaders/{family}/v0.4.0"
    )
    data["schema"] = url + suffix
    with pytest.raises(module.MicrodataError, match="unsupported .* schema selection"):
        module.extract(module.write_page(data), schema)


@pytest.mark.parametrize("module,schema,path", CASES)
@pytest.mark.parametrize("kind", ["array", "object"])
def test_unowned_typed_containers_cannot_hide_properties(module, schema, path, kind):
    page = module.write_page(record(path))
    hidden = (
        f'<span data-fhr-type="{kind}"><span itemprop="funding">hidden</span></span>'
    )
    with pytest.raises(module.MicrodataError, match="without itemprop"):
        module.extract(page.replace("</div>", hidden + "</div>", 1), schema)


@pytest.mark.parametrize("module,schema,path", CASES)
def test_object_container_requires_itemscope(module, schema, path):
    page = module.write_page(record(path))
    hidden = '<span itemprop="source" data-fhr-type="object"><span itemprop="name">X</span></span>'
    with pytest.raises(module.MicrodataError, match="without itemscope"):
        module.extract(page.replace("</div>", hidden + "</div>", 1), schema)


@pytest.mark.parametrize(
    "first,second", [("FHR", "FHP"), ("FHR", "FHGFF3"), ("FHP", "FHGFF3")]
)
@pytest.mark.parametrize("same_element", [False, True])
def test_dispatch_rejects_mixed_families(first, second, same_element):
    left, right = [
        sorted(_microdata.FAMILY_ITEMTYPES[name])[0] for name in (first, second)
    ]
    if same_element:
        page = f'<div itemscope itemtype="{left} {right}"></div>'
    else:
        page = f'<div itemscope itemtype="{left}"></div><div itemscope itemtype="{right}"></div>'
    with pytest.raises(ValueError, match="mixed-family"):
        fhr().input_microdata(page)
    # Public family APIs must enforce the same decision as the dispatcher.
    for module, schema, _ in CASES:
        with pytest.raises(module.MicrodataError, match="mixed-family"):
            module.extract(page, schema)


@pytest.mark.parametrize("module,schema,path", CASES)
def test_carriage_returns_survive_browser_preprocessing(module, schema, path):
    data = record(path)
    data["metadataAuthor"][0]["name"] = "before\r\nafter\rfinal & <text>"
    page = module.write_page(data)
    assert "\r" not in page
    assert "&#13;" in page
    browser_text = page.replace("\r\n", "\n").replace("\r", "\n")
    assert module.extract(browser_text, schema) == data


def test_fhr_writer_also_preserves_carriage_returns():
    data = fhr()
    data.input_json(json.dumps({"metadataAuthor": [{"name": "A\r\nB\rC"}]}))
    page = data.output_microdata()
    assert "\r" not in page
    assert "A&#13;\nB&#13;C" in page


@pytest.mark.parametrize("module,schema,path", CASES)
def test_template_end_tags_cannot_expose_inert_scopes(module, schema, path):
    page = "<section><template></section>" + module.write_page(record(path))
    with pytest.raises(module.MicrodataError, match="found 0"):
        module.extract(page, schema)


def test_depth_is_capped_before_unbounded_ancestor_scans(monkeypatch):
    calls = []
    original = _microdata._TreeBuilder._close_implied

    def counted(self, tag):
        calls.append(tag)
        return original(self, tag)

    monkeypatch.setattr(_microdata._TreeBuilder, "_close_implied", counted)
    with pytest.raises(RecursionError, match="nested too deeply"):
        _microdata.document_families("<div>" * 16_000)
    assert len(calls) <= _microdata.MAX_DOCUMENT_DEPTH + 1


# 0.10.0 applied MAX_DEPTH to the whole document, so page layout around an item
# scope counted against it and every HTML input with deep wrappers failed.


def wrapped(page, depth):
    return "<span>" * depth + page


@pytest.mark.parametrize("depth", [130, _microdata.MAX_DOCUMENT_DEPTH - 10])
def test_wrapper_depth_outside_item_scopes_is_not_capped_at_max_depth(depth):
    page = (ROOT / "examples/example.microdata.fhr.html").read_text()
    assert _microdata.document_families(wrapped(page, depth)) == {"FHR"}
    data = fhr()
    data.input_microdata(wrapped(page, depth))
    expected = fhr()
    expected.input_microdata(page)
    assert data.output_json() == expected.output_json()


@pytest.mark.parametrize("module,schema,path", CASES)
def test_wrapped_fhp_and_fhgff3_pages_still_read(module, schema, path):
    page = wrapped(module.write_page(record(path)), _microdata.MAX_DEPTH + 10)
    assert module.extract(page, schema) == record(path)


def test_depth_inside_an_item_scope_is_still_capped():
    inside = (
        '<div itemscope itemtype="'
        + next(iter(_microdata.FAMILY_ITEMTYPES["FHP"]))
        + '">'
        + "<span>" * (_microdata.MAX_DEPTH + 1)
    )
    with pytest.raises(RecursionError, match="nested too deeply"):
        _microdata.document_families(wrapped(inside, 200))
    # A closed scope frees its budget: a later scope is measured afresh.
    closed = inside.replace("<span>" * (_microdata.MAX_DEPTH + 1), "") + "</div>"
    deep_again = "<div itemscope>" + "<span>" * (_microdata.MAX_DEPTH - 2)
    assert _microdata.document_families(closed + deep_again) == {"FHP"}


def test_document_depth_is_still_capped():
    with pytest.raises(RecursionError, match="nested too deeply"):
        _microdata.document_families("<span>" * (_microdata.MAX_DOCUMENT_DEPTH + 1))


def test_cli_accepts_the_wrapped_fhr_example(tmp_path):
    page = (ROOT / "examples/example.microdata.fhr.html").read_text()
    path = tmp_path / "wrapped.microdata.fhr.html"
    path.write_text(wrapped(page, 130))
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", path], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "examples/fhgff3").glob("invalid-*.html")),
    ids=lambda p: p.name,
)
def test_fhgff3_html_errors_are_labelled_fhgff3(path):
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", path], capture_output=True, text=True
    )
    assert result.returncode == 1
    errors = [
        line
        for line in result.stderr.splitlines()
        if line and "Warning" not in line and not line.startswith("  ")
    ]
    assert errors and all(line.startswith("FHGFF3: ") for line in errors), errors


def test_fhp_html_errors_are_labelled_fhp(tmp_path):
    data = record("fhp/minimal-predicted.fhp.json")
    del data["checksum"]
    path = tmp_path / "invalid.microdata.fhp.html"
    path.write_text(fhp_microdata.write_page(data))
    result = subprocess.run(
        [str(BIN / "bioheaders"), "validate", path], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert result.stderr.startswith("FHP: "), result.stderr


def test_itemprop_splits_on_ascii_whitespace_only():
    node = _microdata._Node(
        "span", {"itemprop": "a\u00a0b\tc\x0bd", "itemtype": "x\u2003y z"}
    )
    assert node.itemprop == ["a\u00a0b", "c\x0bd"]
    assert node.itemtype == ["x\u2003y", "z"]


def test_released_self_closing_policy_is_explicit():
    # Preserve FHP's released leaf policy; only FHGFF3 adopts HTML M2 here.
    legacy = fhp_microdata._tree("<span/>text</span>")
    html = fhgff3_microdata._tree("<span/>text</span>")
    assert legacy.children[0].children == []
    assert html.children[0].children == ["text"]


def test_dispatch_preserves_fhp_leaf_policy_after_template_startend_tag():
    data = record("fhp/minimal-predicted.fhp.json")
    page = "<template/>" + fhp_microdata.write_page(data)

    loaded = fhr()
    loaded.input_microdata(page)
    assert loaded.__dict__ == data


def test_dispatch_does_not_count_fhp_leaf_tags_as_nesting():
    data = record("fhp/minimal-predicted.fhp.json")
    page = "<span/>" * 129 + fhp_microdata.write_page(data)

    loaded = fhr()
    loaded.input_microdata(page)
    assert loaded.__dict__ == data


def test_fhgff3_runtime_is_marked_experimental():
    data = record(CASES[1][2])
    with pytest.warns(
        fhgff3_microdata.ExperimentalMicrodataWarning, match="experimental"
    ):
        page = fhgff3_microdata.write_page(data)
    with pytest.warns(
        fhgff3_microdata.ExperimentalMicrodataWarning, match="experimental"
    ):
        fhgff3_microdata.extract(page, FHGFF3_SCHEMA)
