# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""SC-002 proxy: applying a suggestion never lowers, and usually raises, a status (T024)."""

import gzip
import re

import pytest
from assess_helpers import ALL_HEADER_FIXTURES, FIXTURES, assess, result

RANK = {"not_evidenced": 0, "partially_evidenced": 1, "evidenced": 2}
PLACEHOLDER = re.compile(r"<[^<>\s]*\s[^<>]*>")
DECLARATIONS = (b"##gff-version", b"##fileformat", b"!gaf-version")


def fill(line):
    """Fill each <label, e.g. example> placeholder with its example."""

    def example(match):
        text = match.group(0)[1:-1]
        assert "e.g. " in text, text
        return text.split("e.g. ", 1)[1]

    return PLACEHOLDER.sub(example, line)


def insert(content, line):
    """Insert a header line after the format declaration, or at the top."""
    lines = content.splitlines(keepends=True)
    position = 0
    for index, existing in enumerate(lines[:5]):
        if existing.startswith(DECLARATIONS):
            position = index + 1
            break
    return b"".join(
        lines[:position] + [line.encode("utf-8") + b"\n"] + lines[position:]
    )


def _read(path):
    content = path.read_bytes()
    return gzip.decompress(content) if content[:2] == b"\x1f\x8b" else content


CASES = [
    (name, item["indicator"])
    for name in ALL_HEADER_FIXTURES
    for item in assess(name)["results"]
    if item["suggestion"]
]


@pytest.mark.parametrize("name, indicator", CASES)
def test_applying_a_suggestion_never_lowers_the_status(tmp_path, name, indicator):
    report = assess(name)
    before = result(report, indicator)
    suggestion = before["suggestion"]
    assert suggestion["value_source"] in {
        "file",
        "related-file",
        "placeholder",
        "file-name",
    }
    if suggestion["value_source"] == "file-name":
        assert "confirm before use" in suggestion["text"]
    assert suggestion["guideline_item"].startswith("G")
    if "until the schema supports it" in suggestion["text"]:
        pytest.skip("the suggestion needs a field that FHR schemaVersion 1 lacks")
    content = _read(FIXTURES / name)
    replaced = re.match(r"Replace the existing (\S+) entry", suggestion["text"])
    if replaced:  # Remove the existing top-level entry (one line in the fixtures).
        prefix = suggestion["line"][:2].encode()
        content = b"".join(
            line
            for line in content.splitlines(keepends=True)
            if not line.startswith(prefix + replaced.group(1).encode() + b":")
        )
    path = tmp_path / name.replace(".gz", "")
    path.write_bytes(insert(content, fill(suggestion["line"])))
    after = result(assess(path), indicator)
    assert RANK[after["status"]] >= RANK[before["status"]], (before, after)
    if before["conditions_total"] == 1:
        assert RANK[after["status"]] > RANK[before["status"]], suggestion["line"]


def test_suggestions_use_the_file_convention():
    report = assess("ncbi-refseq_gff3_GCF_000002985.6_WBcel235_genomic.gff")
    licence = result(report, "RDA-R1.1-01M")["suggestion"]
    assert licence["line"] == "#!reuseConditions <SPDX licence id, e.g. CC-BY-4.0>"
    assert licence["convention"] == "gff3-pragma"
    assert licence["value_source"] == "placeholder"
    vcf = result(assess("ncbi-clinvar_vcf_clinvar.vcf"), "RDA-R1.1-01M")["suggestion"]
    assert vcf["line"].startswith("##reuseConditions=")
    gaf = result(assess("go_gaf_wb.gaf"), "RDA-R1.1-01M")["suggestion"]
    assert gaf["line"].startswith("!reuseConditions: ")
    fasta = result(assess("no-header.fa"), "RDA-R1.1-01M")["suggestion"]
    assert fasta["line"].startswith(";~reuseConditions: ")
    assert "draft specifications" in fasta["text"]


def test_value_from_the_file_is_used_and_labelled():
    report = assess("ncbi-refseq_gff3_GCF_000002985.6_WBcel235_genomic.gff")
    taxon = result(report, "RDA-I2-01M")["suggestion"]
    assert taxon["line"] == "##species https://identifiers.org/taxonomy:6239"
    assert taxon["value_source"] == "file"


def test_value_from_the_file_name_says_confirm_before_use(tmp_path):
    path = tmp_path / "GCF_000002985.6_WBcel235_genomic.gff"
    path.write_bytes(b"##gff-version 3\n##sequence-region I 1 100\n")
    suggestion = result(assess(path), "RDA-I3-04M")["suggestion"]
    assert suggestion["value_source"] == "file-name"
    assert (
        suggestion["line"] == "#!genome-build-accession NCBI_Assembly:GCF_000002985.6"
    )
    assert "from the file name; confirm before use" in suggestion["text"]
