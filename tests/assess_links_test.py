# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Recorded links, verification against a related file, circumstantial checks (T037)."""

import hashlib

import pytest
from assess_helpers import FIXTURES, assess

from bioheaders.assess import circumstantial, related

PAIRS = FIXTURES / "pairs"


def pair(derived, genome, **options):
    return assess(PAIRS / derived, related=PAIRS / genome, **options)


def verification(report, index=0):
    return report["links"][index]["verification"]


def test_computed_fhr_checksum_match():
    report = pair("annotation-correct.gff3", "genome-fhr.fa")
    check = verification(report)
    assert (check["verdict"], check["method"], check["reason"]) == (
        "match",
        "computed-fhr-checksum",
        None,
    )
    assert check["expected"] == check["actual"]
    assert report["pair_classification"] == "recorded-match"


def test_version_mismatch():
    report = pair("annotation-version-mismatch.gff3", "genome-fhr-v2.fa")
    check = verification(report)
    assert check["verdict"] == "mismatch"
    assert check["expected"] != check["actual"]
    assert report["pair_classification"] == "recorded-mismatch"


def test_stated_fhr_checksum_is_used_when_the_file_cannot_be_hashed(monkeypatch):
    monkeypatch.setattr(related, "_computed_checksum", lambda scan: None)
    related.clear_cache()
    check = verification(pair("annotation-correct.gff3", "genome-fhr.fa"))
    related.clear_cache()
    assert (check["verdict"], check["method"]) == ("match", "stated-fhr-checksum")


def test_checksum_against_a_genome_without_identity_is_unverifiable():
    check = verification(pair("annotation-correct.gff3", "genome-plain.fa"))
    assert (check["verdict"], check["reason"]) == (
        "unverifiable",
        "related-file-states-no-identity",
    )


def test_stated_seqcol(tmp_path):
    digest = "3aH2VIDvPa1rVLSwmJp4pE6lF2Hkt2Az"
    genome = tmp_path / "genome.fa"
    genome.write_bytes(f";~seqcol_id: {digest}\n>I\nACGT\n".encode())
    annotation = tmp_path / "a.gff3"
    annotation.write_bytes(
        b"##gff-version 3\n#~derivedFrom: [{headerType: FHR, relationship: annotates, "
        + f"seqcol_id: {digest}}}]\n".encode()
    )
    check = assess(annotation, related=genome)["links"][0]["verification"]
    assert (check["verdict"], check["method"]) == ("match", "stated-seqcol")
    genome.write_bytes(b">I\nACGT\n")
    related.clear_cache()
    check = assess(annotation, related=genome)["links"][0]["verification"]
    assert (check["verdict"], check["reason"]) == (
        "unverifiable",
        "related-file-states-no-seqcol",
    )


def test_computed_md5_per_sequence_set():
    report = pair("variants-contig-md5.vcf", "genome-plain.fa")
    link = report["links"][0]
    check = link["verification"]
    assert (link["kind"], check["verdict"], check["method"]) == (
        "sequence-digests",
        "mismatch",
        "computed-md5",
    )
    assert set(check["actual"]) == {"III"}  # only the differing names are listed
    assert report["pair_classification"] == "recorded-mismatch"


def test_md5_is_upper_cased_without_whitespace(tmp_path):
    genome = tmp_path / "g.fa"
    genome.write_bytes(b">s1\nacgt\nAC GT\n")
    digest = hashlib.md5(b"ACGTACGT").hexdigest()
    vcf = tmp_path / "v.vcf"
    vcf.write_bytes(
        f"##fileformat=VCFv4.3\n##contig=<ID=s1,md5={digest}>\n#CHROM\tPOS\n".encode()
    )
    assert assess(vcf, related=genome)["links"][0]["verification"]["verdict"] == "match"


def test_accession_is_unverifiable_and_a_file_name_is_only_a_hint(tmp_path):
    genome = tmp_path / "GCF_000002985.6_WBcel235_genomic.fna"
    genome.write_bytes((PAIRS / "genome-plain.fa").read_bytes())
    report = assess(PAIRS / "annotation-accession-only.gff3", related=genome)
    check = report["links"][0]["verification"]
    assert (check["verdict"], check["method"], check["reason"]) == (
        "unverifiable",
        "stated-identity",
        "related-file-states-no-identity",
    )
    assert any("GCF_000002985.6" in hint for hint in check["hints"])
    assert report["pair_classification"] == "consistent-unverified"


def test_accession_stated_by_the_related_file(tmp_path):
    genome = tmp_path / "g.fa"
    genome.write_bytes(b";~accessionID:\n;~  name: GCF_000002985.6\n>I\nACGT\n")
    annotation = PAIRS / "annotation-accession-only.gff3"
    assert assess(annotation, related=genome)["links"][0]["verification"][
        "verdict"
    ] == ("match")
    genome.write_bytes(b";~accessionID:\n;~  name: GCF_000001405.40\n>I\nACGT\n")
    related.clear_cache()
    assert (
        assess(annotation, related=genome)["links"][0]["verification"]["verdict"]
        == "mismatch"
    )


def test_malformed_link_is_unverifiable():
    report = pair("annotation-malformed-checksum.gff3", "genome-fhr.fa")
    check = verification(report)
    assert (check["verdict"], check["reason"]) == ("unverifiable", "malformed")


def test_circumstantial_names_and_lengths():
    report = pair("annotation-partial.gff3", "genome-plain.fa")
    check = report["circumstantial"]
    assert check["label"] == "circumstantial evidence, not a recorded link"
    assert (check["source"], check["verdict"]) == (
        "sequence-region",
        "partially_consistent",
    )
    assert check["missing_from_related"] == ["Y"]
    assert check["length_mismatches"] == [
        {"name": "II", "declared": 154, "actual": 153}
    ]
    assert (check["names_compared"], check["lengths_compared"]) == (7, 6)
    assert check["not_declared_count"] == 1  # MtDNA
    assert report["pair_classification"] == "partial"


def test_circumstantial_inconsistent_lists_every_missing_name():
    report = pair("annotation-genbank-names.gff3", "genome-refseq-names.fa")
    missing = report["circumstantial"]["missing_from_related"]
    assert missing == sorted(missing) and len(missing) == 7
    assert report["circumstantial"]["verdict"] == "inconsistent"
    assert report["pair_classification"] == "inconsistent"


def test_undeclared_lengths_never_lower_the_verdict(tmp_path):
    vcf = tmp_path / "v.vcf"
    vcf.write_bytes(
        b"##fileformat=VCFv4.3\n##contig=<ID=I>\n##contig=<ID=II>\n#CHROM\n"
    )
    check = assess(vcf, related=PAIRS / "genome-plain.fa")["circumstantial"]
    assert (check["source"], check["verdict"], check["lengths_compared"]) == (
        "vcf-contig",
        "consistent",
        0,
    )


def test_record_seqids_when_nothing_is_declared(tmp_path):
    gff = tmp_path / "a.gff3"
    gff.write_bytes(b"##gff-version 3\nI\ts\tgene\t1\t2\t.\t+\t.\tID=a\n")
    check = assess(gff, related=PAIRS / "genome-plain.fa")["circumstantial"]
    assert (check["source"], check["names_compared"], check["verdict"]) == (
        "record-seqids",
        1,
        "consistent",
    )


def test_circumstantial_is_never_cited_by_an_indicator():
    report = pair("annotation-no-link.gff3", "genome-plain.fa")
    regions = {
        e["id"] for e in report["evidence"] if "sequence-region" in e["concepts"]
    }
    for item in report["results"]:
        assert not set(item["evidence"]) & regions, item["indicator"]
        assert "circumstantial" not in item
    assert report["pair_classification"] == "consistent-unverified"


@pytest.mark.parametrize(
    "links, verdict, expected",
    [
        (["mismatch", "match"], "consistent", "recorded-mismatch"),
        (["match", "unverifiable"], "inconsistent", "recorded-match"),
        (["unverifiable"], "inconsistent", "inconsistent"),
        ([], "partially_consistent", "partial"),
        ([], "consistent", "consistent-unverified"),
        ([], "not_checked", "unknown"),
    ],
)
def test_pair_classification_precedence(links, verdict, expected):
    assert circumstantial.classify(links, verdict) == expected


def test_recorded_match_with_disagreeing_names_is_reported(tmp_path):
    annotation = tmp_path / "a.gff3"
    content = (PAIRS / "annotation-correct.gff3").read_bytes()
    annotation.write_bytes(
        content.replace(b"##sequence-region I 1", b"##sequence-region Z 1")
    )
    report = assess(annotation, related=PAIRS / "genome-fhr.fa")
    assert report["pair_classification"] == "recorded-match"
    assert any(f["kind"] == "format-irregularity" for f in report["findings"])


def test_a_related_file_is_scanned_once(monkeypatch):
    related.clear_cache()
    calls = []
    original = related._scan

    def counting(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(related, "_scan", counting)
    pair("annotation-no-link.gff3", "genome-plain.fa")
    pair("annotation-accession-only.gff3", "genome-plain.fa")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "kind, payload",
    [
        ("fasta", b">demo\nacgt\n>second\nACGT\n"),
        ("gfa", b"S\tdemo\tacgt\nS\tsecond\tACGT\n"),
    ],
)
def test_vcf_identifiers_work_when_security_md5_is_disabled(monkeypatch, kind, payload):
    """Simulate security-flag-restricted MD5 for VCF interoperability identifiers."""
    original = hashlib.md5
    calls = []

    def restricted_md5(*args, usedforsecurity=True, **kwargs):
        calls.append(usedforsecurity)
        if usedforsecurity:
            raise ValueError("MD5 disabled for security use")
        return original(*args, usedforsecurity=False, **kwargs)

    monkeypatch.setattr(related.hashlib, "md5", restricted_md5)
    names = {}
    parser = related._Sequences(kind, names)
    parser.feed(payload)
    parser.close()
    assert names == {
        "demo": [4, "f1f8f4bf413b16ad135722aa4591043e"],
        "second": [4, "f1f8f4bf413b16ad135722aa4591043e"],
    }
    assert calls == [False, False]
