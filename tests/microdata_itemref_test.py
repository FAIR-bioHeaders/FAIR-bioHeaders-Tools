# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""MICRODATA.md M1: ``itemref`` is refused, not ignored, in every reader.

A reader that followed ``itemref`` and one that ignored it would read different
metadata from the same page (FAIR-bioHeaders-Specification vector
``microdata-itemref``), so an ``itemref`` on the item or any element inside it
makes the document invalid. Outside the item it is not ours to judge.
"""

import json
from pathlib import Path

import pytest

from bioheaders import FHGFF3_SCHEMA, FHP_SCHEMA, fhgff3_microdata, fhp_microdata, fhr

ROOT = Path(__file__).resolve().parents[1]
FHR_PAGE = (ROOT / "examples/example.microdata.fhr.html").read_text()
OUTSIDE = '<p id="extra"><span itemprop="reuseConditions">CC0-1.0</span></p>'
pytestmark = pytest.mark.filterwarnings("ignore:FHGFF3 HTML microdata is experimental")


def read_fhr(page):
    data = fhr()
    data.input_microdata(page)
    return data


@pytest.mark.parametrize(
    "outside", ['<div itemref="outside"></div>', '<div itemref="outside"/>']
)
def test_itemref_after_an_implicitly_closed_item_is_outside(outside):
    # All example properties use inline spans, so a paragraph can carry the
    # complete item. The following div closes it before that div's attributes
    # are interpreted, just as an explicit paragraph end would.
    paragraph = FHR_PAGE.replace("<div itemscope", "<p itemscope", 1)
    explicit = paragraph.replace("</div>", "</p>" + outside, 1)
    implicit = paragraph.replace("</div>", outside, 1)
    expected = read_fhr(explicit)
    actual = read_fhr(implicit)
    actual.fhr_validate()
    assert actual.__dict__ == expected.__dict__


def test_itemref_before_the_paragraph_item_ends_is_still_refused():
    page = FHR_PAGE.replace("<div itemscope", "<p itemscope", 1).replace(
        '<span itemprop="funding"',
        '<span itemref="extra"></span><span itemprop="funding"',
        1,
    )
    with pytest.raises(ValueError, match="itemref is not supported"):
        read_fhr(page)


@pytest.mark.parametrize(
    "page",
    [
        FHR_PAGE.replace("<div itemscope", '<div itemref="extra" itemscope', 1)
        + OUTSIDE,
        FHR_PAGE.replace(
            '<span itemprop="funding"', '<span itemref="extra" itemprop="funding"', 1
        ),
        FHR_PAGE.replace(
            '<span itemprop="funding"',
            '<meta itemref="extra"><span itemprop="funding"',
            1,
        ),
        # The FHR reader checks itemref before it skips script/template
        # content, so inert elements inside the item are refused too.
        FHR_PAGE.replace(
            '<span itemprop="funding"',
            '<template itemref="extra"></template><span itemprop="funding"',
            1,
        ),
        FHR_PAGE.replace(
            '<span itemprop="funding"',
            '<script itemref="extra"></script><span itemprop="funding"',
            1,
        ),
        FHR_PAGE.replace(
            '<span itemprop="funding"',
            '<template><p><b itemref="extra"></b></p></template>'
            '<span itemprop="funding"',
            1,
        ),
        FHR_PAGE.replace(
            '<span itemprop="funding"',
            '<template itemref="extra"/><span itemprop="funding"',
            1,
        ),
    ],
    ids=[
        "on-the-item",
        "inside-the-item",
        "void-element-inside",
        "template-inside",
        "script-inside",
        "inside-template-content",
        "self-closing-template",
    ],
)
def test_fhr_reader_refuses_itemref(page):
    with pytest.raises(ValueError, match="itemref is not supported"):
        read_fhr(page)


def test_itemref_outside_the_item_is_not_ours():
    page = FHR_PAGE.replace("<body>", '<body><p itemref="x">x</p>', 1)
    assert read_fhr(page).genome == read_fhr(FHR_PAGE).genome


@pytest.mark.parametrize(
    "module,schema,path",
    [
        (fhp_microdata, FHP_SCHEMA, "fhp/minimal-predicted.fhp.json"),
        (
            fhgff3_microdata,
            FHGFF3_SCHEMA,
            "fhgff3/minimal-reference.microdata.fhgff3.json",
        ),
    ],
)
@pytest.mark.parametrize("where", ["item", "inside"])
def test_fhp_and_fhgff3_readers_refuse_itemref(module, schema, path, where):
    record = json.loads((ROOT / "examples" / path).read_text())
    page = module.write_page(record)
    if where == "item":
        page = page.replace(
            " itemscope itemtype=", ' itemref="extra" itemscope itemtype=', 1
        )
    else:
        page = page.replace(
            '<span itemprop="schema"', '<span itemref="extra" itemprop="schema"', 1
        )
    assert "itemref" in page
    with pytest.raises(module.MicrodataError, match="itemref is not supported"):
        module.extract(page + OUTSIDE, schema)


@pytest.mark.parametrize(
    "module,schema,path",
    [
        (fhp_microdata, FHP_SCHEMA, "fhp/minimal-predicted.fhp.json"),
        (
            fhgff3_microdata,
            FHGFF3_SCHEMA,
            "fhgff3/minimal-reference.microdata.fhgff3.json",
        ),
    ],
)
@pytest.mark.parametrize(
    "tag,nested", [("script", False), ("template", False), ("template", True)]
)
def test_itemref_guard_includes_inert_elements_and_their_descendants(
    module, schema, path, tag, nested
):
    record = json.loads((ROOT / "examples" / path).read_text())
    page = module.write_page(record)
    inert = (
        f'<{tag}><span itemref="extra">hidden</span></{tag}>'
        if nested
        else f'<{tag} itemref="extra"></{tag}>'
    )
    page = page.replace('<span itemprop="schema"', inert + '<span itemprop="schema"', 1)
    assert inert in page
    with pytest.raises(module.MicrodataError, match="itemref is not supported"):
        module.extract(page, schema)


@pytest.mark.parametrize(
    "module,schema,path",
    [
        (fhp_microdata, FHP_SCHEMA, "fhp/minimal-predicted.fhp.json"),
        (
            fhgff3_microdata,
            FHGFF3_SCHEMA,
            "fhgff3/minimal-reference.microdata.fhgff3.json",
        ),
    ],
)
def test_inert_elements_without_itemref_are_still_accepted(module, schema, path):
    # Control: the refusals above come from itemref, not from the inert element.
    record = json.loads((ROOT / "examples" / path).read_text())
    page = module.write_page(record).replace(
        '<span itemprop="schema"',
        '<template id="t"></template><script></script><span itemprop="schema"',
        1,
    )
    assert module.extract(page, schema) == record


def test_fhr_reader_accepts_inert_elements_without_itemref():
    page = FHR_PAGE.replace(
        '<span itemprop="funding"',
        '<template id="t"></template><script></script><span itemprop="funding"',
        1,
    )
    assert read_fhr(page).funding == read_fhr(FHR_PAGE).funding
