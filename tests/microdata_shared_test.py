# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Cross-family regressions from the post-merge review of #139 (#140)."""

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
    assert len(calls) <= _microdata.MAX_DEPTH


def test_released_self_closing_policy_is_explicit():
    # Preserve FHP's released leaf policy; only FHGFF3 adopts HTML M2 here.
    legacy = fhp_microdata._tree("<span/>text</span>")
    html = fhgff3_microdata._tree("<span/>text</span>")
    assert legacy.children[0].children == []
    assert html.children[0].children == ["text"]


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
