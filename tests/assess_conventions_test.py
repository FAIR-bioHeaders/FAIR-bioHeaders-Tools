# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Header-region readers, one test per parsing rule of research R-02/R-15 (T020)."""

import gzip

import pytest
from assess_helpers import (
    ALL_HEADER_FIXTURES,
    REFSEQ_GFF3,
    assess,
    evidence_by_id,
    finding_lines,
)

from bioheaders.assess import conventions


def _by_line(report):
    return {item["line"]: item for item in report["evidence"]}


def test_gff3_directives_and_pragmas_with_and_without_colon():
    report = assess(REFSEQ_GFF3)
    lines = _by_line(report)
    assert lines[1]["convention"] == "gff3-directive"
    assert lines[1]["key"] == "gff-version" and lines[1]["value"] == "3"
    assert lines[5]["convention"] == "gff3-pragma"
    assert lines[5]["key"] == "genome-build-accession"
    assert lines[5]["concepts"] == ["assembly-accession"]
    assert lines[5]["value_forms"] == ["insdc-assembly-accession"]


def test_pragma_key_with_trailing_colon(tmp_path):
    path = tmp_path / "h.gff3"
    path.write_bytes(
        b"##gff-version 3\n#!assembly: GRCh38\n#!annotationSource RefSeq\n"
    )
    lines = _by_line(assess(path))
    assert lines[2]["key"] == "assembly:"
    assert lines[2]["normalised_key"] == "assembly"
    assert lines[2]["value"] == "GRCh38"
    assert "assembly-name" in lines[2]["concepts"]
    assert lines[3]["normalised_key"] == "annotation-source"
    assert lines[3]["concepts"] == ["source-data"]


def test_comment_before_gff_version_is_kept_and_reported():
    report = assess("alliance_gff3_GFF_WB_4.gff")
    line = _by_line(report)[1]
    assert line["convention"] == "unrecognised"
    assert line["raw"] == "# WormBase release WS298"
    assert finding_lines(report, "format-irregularity") == [1]
    assert finding_lines(report, "unrecognised-comment") == [1]


def test_header_ends_at_first_feature_or_fasta_directive(tmp_path):
    path = tmp_path / "a.gff3"
    path.write_bytes(
        b"##gff-version 3\nctg\ts\tgene\t1\t2\t.\t+\t.\tID=g\n#!genome-build late\n"
    )
    report = assess(path)
    assert [item["line"] for item in report["evidence"]] == [1]
    path.write_bytes(b"##gff-version 3\n##FASTA\n>ctg\nACGT\n")
    report = assess(path)
    assert [item["line"] for item in report["evidence"]] == [1, 2]


def test_every_sequence_region_line_is_read(tmp_path):
    regions = b"".join(
        b"##sequence-region s%d 1 %d\n" % (i, 1000 + i) for i in range(1870)
    )
    path = tmp_path / "fly.gff.gz"
    path.write_bytes(gzip.compress(b"##gff-version 3\n" + regions, mtime=0))
    report = assess(path)
    regions_read = [i for i in report["evidence"] if "sequence-region" in i["concepts"]]
    assert len(regions_read) == 1870
    assert regions_read[-1]["value"] == {"seqid": "s1869", "start": 1, "end": 2869}


def test_gaf_first_block_is_file_scope_and_later_blocks_are_provenance():
    report = assess("go_gaf_wb.gaf")
    lines = _by_line(report)
    assert lines[1]["key"] == "gaf-version" and lines[1]["scope"] == "file"
    assert lines[5]["key"] == "date-generated" and lines[5]["scope"] == "file"
    later = [item for line, item in lines.items() if line > 7]
    assert later and all(item["scope"] == "upstream-provenance" for item in later)
    assert lines[23]["key"] == "Created on"


def test_vcf_contig_subfields_and_source_split():
    lines = _by_line(assess("alliance_vcf_VCF-GZ_WBcel235_38.vcf"))
    contig = [item for item in lines.values() if item["key"] == "contig"][0]
    assert contig["value"] == {
        "ID": "IV",
        "assembly": "WBcel235",
        "species": "Caenorhabditis elegans",
    }
    assert "assembly-name" in contig["concepts"] and "taxon" in contig["concepts"]
    source = _by_line(assess("ensembl_vcf_homo_sapiens-chrMT.vcf"))[3]
    assert source["value"] == {
        "source": "ensembl",
        "version": "116",
        "url": "https://e116.ensembl.org/homo_sapiens",
    }
    assert set(source["concepts"]) == {"creator", "version", "access-url"}


@pytest.mark.parametrize(
    "name, expected",
    [
        (
            "ensembl_fasta-protein_Homo_sapiens.GRCh38.pep.all.fa",
            {"ensembl-coord-assembly": "GRCh38"},
        ),
        (
            "flybase_fasta-transcript_dmel-all-transcript-r6.69.fasta",
            {"MD5": "6c3abf7c6ba8b1392a073c85365b2e75", "release": "r6.69"},
        ),
        (
            "wormbase_fasta-protein_c_elegans.PRJNA13758.WS298.protein.fa",
            {
                "gene": "WBGene00007063",
                "product": "C2H2-type domain-containing protein",
            },
        ),
    ],
)
def test_first_fasta_defline_is_record_level(name, expected):
    report = assess(name)
    (defline,) = report["evidence"]
    assert defline["convention"] == "fasta-defline"
    assert defline["scope"] == "first-record"
    assert expected.items() <= defline["value"].items()


@pytest.mark.parametrize("name", ALL_HEADER_FIXTURES)
def test_every_header_line_yields_exactly_one_evidence_item(name):
    report = assess(name)
    if report["input"]["scope"] != "assessed":
        assert report["evidence"] == []
        return
    lines = [item["line"] for item in report["evidence"]]
    assert lines == sorted(set(lines))
    assert [item["id"] for item in report["evidence"]] == [
        f"e{n}" for n in range(1, len(lines) + 1)
    ]
    assert report["input"]["header_lines_read"] >= len(lines)


def test_line_too_long(tmp_path):
    path = tmp_path / "long.gff3"
    path.write_bytes(
        b"##gff-version 3\n#!tool " + b"x" * (conventions.MAX_LINE_BYTES + 10) + b"\n"
    )
    report = assess(path)
    line = _by_line(report)[2]
    assert len(line["raw"].encode()) <= conventions.MAX_LINE_BYTES
    assert finding_lines(report, "line-too-long") == [2]


def test_header_truncated_at_16_mib(tmp_path):
    path = tmp_path / "huge.gff3"
    row = b"##sequence-region s 1 100" + b" " * 1000 + b"\n"
    count = conventions.MAX_HEADER_BYTES // len(row) + 2
    with path.open("wb") as output:
        output.write(b"##gff-version 3\n")
        for _ in range(count):
            output.write(row)
    report = assess(path)
    assert any(f["kind"] == "header-truncated" for f in report["findings"])
    assert report["input"]["header_lines_read"] < count


def test_undecodable_line_is_not_interpreted():
    report = assess("non-utf8.gff3")
    line = _by_line(report)[2]
    assert line["convention"] == "unrecognised"
    assert line["concepts"] == [] and line["key"] is None
    assert finding_lines(report, "undecodable-line") == [2]


def test_unknown_text_lines_are_unrecognised_comments():
    report = assess("unknown-convention.txt")
    assert report["input"]["format"] == "unknown-text"
    assert [i["convention"] for i in report["evidence"]] == ["unrecognised"] * 2
    assert finding_lines(report, "unrecognised-comment") == [1, 2]


def test_fhr_lines_and_gff3_directives_combine():
    report = assess("fhr-and-directives.gff3")
    conventions_used = {item["convention"] for item in report["evidence"]}
    assert conventions_used == {"gff3-directive", "fair-bioheaders"}
    taxon = [i for i in report["evidence"] if i["key"] == "taxon"][0]
    assert taxon["value"] == {
        "name": "Homo sapiens",
        "uri": "https://identifiers.org/taxonomy:9606",
    }
    assert "taxonomy-iri" in taxon["value_forms"]


def test_evidence_values_have_no_floats():
    report = assess("fhr-valid.fhr.fasta")
    version = [i for i in report["evidence"] if i["key"] == "schemaVersion"][0]
    assert version["value"] == "2.0"
    assert evidence_by_id(report)
