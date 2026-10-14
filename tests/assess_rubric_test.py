# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Status derivation of data-model §5 (T021)."""

import pytest
from assess_helpers import (
    ALL_HEADER_FIXTURES,
    FIXTURES,
    REFSEQ_GFF3,
    assess,
    cited_lines,
    finding_lines,
    result,
    status,
)

from bioheaders.assess import data

INDICATORS = data.load().indicators
OFFLINE = [i["id"] for i in INDICATORS if i["assessability"] == "offline"]
NOT_APPLICABLE = {
    i["id"]: i["reason"] for i in INDICATORS if i["assessability"] == "not_applicable"
}


@pytest.mark.parametrize("name", ALL_HEADER_FIXTURES)
def test_each_indicator_once_in_rubric_order_with_allowed_reasons(name):
    report = assess(name)
    assert [r["indicator"] for r in report["results"]] == [i["id"] for i in INDICATORS]
    for item in report["results"]:
        if item["status"] == "not_applicable":
            assert item["reason"] in {
                "embedded-metadata",
                "repository-level",
                "object-in-hand",
            }
            assert item["reason"] == NOT_APPLICABLE[item["indicator"]]
            assert item["method"] == "none"


def test_step_1_not_applicable_comes_before_out_of_scope():
    report = assess("stub.bam")
    for indicator, reason in NOT_APPLICABLE.items():
        assert (status(report, indicator), result(report, indicator)["reason"]) == (
            "not_applicable",
            reason,
        )


@pytest.mark.parametrize(
    "name, reason",
    [
        ("stub.bam", "binary-format-out-of-scope"),
        ("gff3-in-tar.gff.gz", "archive-not-supported"),
        ("flybase_gff3_dmel-all-r6.69.gff.gz", "archive-not-supported"),
    ],
)
def test_step_2_out_of_scope_inputs(name, reason):
    report = assess(name)
    assert report["input"]["scope"] == "out_of_scope"
    for item in report["results"]:
        if item["indicator"] not in NOT_APPLICABLE:
            assert (item["status"], item["reason"]) == ("not_assessed", reason)


def test_steps_3_and_4_deferred_and_online_not_requested():
    report = assess(REFSEQ_GFF3)
    for indicator in ("RDA-I3-01D", "RDA-I3-02D"):
        assert result(report, indicator)["reason"] == "deferred-data-body"
    for indicator in ("RDA-A1-03D", "RDA-A1-04D", "RDA-A1-05D", "RDA-A1.1-01D"):
        item = result(report, indicator)
        assert (item["status"], item["reason"]) == (
            "not_assessed",
            "online-check-not-requested",
        )


def test_step_6_unsupported_header_type_only_for_conformance_checks():
    report = assess("fht-stub.fa")
    for indicator in ("RDA-R1.3-01M", "RDA-R1.3-02M"):
        assert result(report, indicator)["reason"] == "unsupported-header-type"
    assert status(report, "RDA-R1.1-01M") == "evidenced"  # core fields still read


def test_step_6_unsupported_schema_version(tmp_path):
    path = tmp_path / "v2.fa"
    source = FIXTURES / "fhr-valid.fhr.fasta"
    path.write_bytes(source.read_bytes().replace(b"/fhr/v0.4.0", b"/fhr/v0.0.0"))
    report = assess(path)
    assert report["conformance"]["result"] == "not_assessed"
    assert report["conformance"]["reason"] == "unsupported-schema-version"
    assert result(report, "RDA-R1.3-01M")["reason"] == "unsupported-schema-version"


def test_step_7_ncbi_refseq_accession_is_evidenced_on_line_5():
    report = assess(REFSEQ_GFF3)
    assert status(report, "RDA-I3-04M") == "evidenced"
    assert 5 in cited_lines(report, "RDA-I3-04M")
    item = result(report, "RDA-I3-04M")
    assert (item["conditions_met"], item["conditions_total"]) == (2, 2)
    assert item["suggestion"] is None


def test_fasta_without_header_is_not_evidenced_everywhere_with_suggestions():
    report = assess("no-header.fa")
    for indicator in OFFLINE:
        item = result(report, indicator)
        assert item["status"] == "not_evidenced", indicator
        assert item["suggestion"]["line"].startswith(";~"), indicator
        assert item["suggestion"]["convention"] == "fair-bioheaders"


def test_step_8_first_record_cap():
    report = assess("flybase_fasta-transcript_dmel-all-transcript-r6.69.fasta")
    assert status(report, "RDA-F1-02D") == "partially_evidenced"
    assert status(report, "RDA-F2-01M") == "not_evidenced"  # taxon only first-record


def test_step_8_conflicting_values_cap():
    report = assess("conflicting-accessions.gff3")
    assert status(report, "RDA-I3-04M") == "partially_evidenced"
    assert finding_lines(report, "conflicting-values") == [2, 3]


def test_malformed_value_satisfies_nothing():
    report = assess("malformed-checksum.gff3")
    assert report["links"][0]["well_formed"] is False
    item = result(report, "RDA-I3-04M")
    assert item["status"] == "partially_evidenced"
    assert [f["kind"] for f in item["findings"]] == ["malformed"]


def test_upstream_provenance_is_never_used_for_file_level_indicators():
    report = assess("go_gaf_wb.gaf")
    assert status(report, "RDA-I3-02M") == "not_evidenced"  # go-version is upstream
    assert status(report, "RDA-R1.2-01M") == "partially_evidenced"
    assert all(line <= 5 for line in cited_lines(report, "RDA-R1.2-01M"))


def test_identifier_in_free_text_gets_no_credit():
    report = assess("accession-in-comment.gff3")
    assert status(report, "RDA-I3-04M") == "not_evidenced"
    assert report["links"] == []
    assert finding_lines(report, "identifier-in-free-text") == [2]


def test_header_truncated_keeps_status_and_attaches_finding(tmp_path):
    from bioheaders.assess import conventions

    path = tmp_path / "huge.gff3"
    row = b"##sequence-region s 1 100" + b" " * 1000 + b"\n"
    with path.open("wb") as output:
        output.write(b"##gff-version 3\n")
        for _ in range(conventions.MAX_HEADER_BYTES // len(row) + 2):
            output.write(row)
    report = assess(path)
    item = result(report, "RDA-R1.1-01M")
    assert item["status"] == "not_evidenced"
    assert "header-truncated" in [f["kind"] for f in item["findings"]]
    assert status(report, "RDA-I1-01D") == "evidenced"
