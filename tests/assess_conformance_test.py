# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FAIR-bioHeaders schema conformance, reported apart from the checklist (T022)."""

import hashlib
from importlib.resources import files

from assess_helpers import FIXTURES, assess, result

CANONICAL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhr.json"
)


def test_valid_fhr_fasta_records_the_schema_used():
    report = assess("fhr-valid.fhr.fasta")
    conformance = report["conformance"]
    assert conformance["result"] == "valid" and conformance["reason"] is None
    assert conformance["header_type"] == "FHR"
    # The fixture cites the v0.4.0 release (FHR-Specification docs/SCHEMA-VERSIONS.md
    # V3), so the bundled copy of that release is used.
    assert conformance["cited_schema"] == "https://w3id.org/fair-bioheaders/fhr/v0.4.0"
    assert conformance["cited_schema_version"] == "2.0"
    bundled = files("bioheaders").joinpath("schemas/fhr-2.0.json").read_bytes()
    assert conformance["schema_used"] == {
        "canonical_url": CANONICAL.replace("/main/", "/v0.4.0/"),
        "bundled_sha256": hashlib.sha256(bundled).hexdigest(),
        "version": "2.0",
    }
    # Separate from the results: no result carries the conformance object.
    assert all("conformance" not in item for item in report["results"])
    assert result(report, "RDA-R1.3-02M")["status"] == "evidenced"


def test_duplicate_key_header_is_invalid_and_not_used_as_evidence(tmp_path):
    source = (FIXTURES / "fhr-valid.fhr.fasta").read_bytes()
    path = tmp_path / "dup.fhr.fasta"
    path.write_bytes(
        source.replace(
            b";~version: 1.0.0\n",
            b";~version: 1.0.0\n;~reuseConditions: CC0-1.0\n;~version: 2\n",
        )
    )
    report = assess(path)
    assert report["conformance"]["result"] == "invalid"
    assert "duplicate" in report["conformance"]["reason"]
    fhr = [i for i in report["evidence"] if i["convention"] == "fair-bioheaders"]
    assert fhr and all(i["concepts"] == ["fair-bioheaders-invalid"] for i in fhr)
    assert result(report, "RDA-R1.1-01M")["status"] == "not_evidenced"
    assert result(report, "RDA-R1.3-01M")["status"] == "not_evidenced"


def test_schema_invalid_header_is_invalid_with_a_json_path(tmp_path):
    source = (FIXTURES / "fhr-valid.fhr.fasta").read_bytes()
    path = tmp_path / "bad.fhr.fasta"
    path.write_bytes(source.replace(b";~masking: not-masked\n", b""))
    report = assess(path)
    assert report["conformance"]["result"] == "invalid"
    assert "masking" in report["conformance"]["reason"]


def test_fht_stub_is_not_assessed_unsupported_header_type():
    conformance = assess("fht-stub.fa")["conformance"]
    assert conformance["header_type"] == "FHT"
    assert (conformance["result"], conformance["reason"]) == (
        "not_assessed",
        "unsupported-header-type",
    )
    assert conformance["schema_used"] is None


def test_unknown_schema_value_has_no_header_type():
    conformance = assess("malformed-checksum.gff3")["conformance"]
    assert conformance["header_type"] is None
    assert conformance["reason"] == "unsupported-header-type"


def test_unbundled_schema_version_is_not_fetched(tmp_path):
    # FHR-Specification rule V4: a release this package does not bundle.
    source = (FIXTURES / "fhr-valid.fhr.fasta").read_bytes()
    path = tmp_path / "v9.fhr.fasta"
    path.write_bytes(source.replace(b"/fhr/v0.4.0", b"/fhr/v9.9.9"))
    conformance = assess(path)["conformance"]  # sockets are disabled here
    assert (conformance["result"], conformance["reason"]) == (
        "not_assessed",
        "unsupported-schema-version",
    )
    assert conformance["cited_schema"] == "https://w3id.org/fair-bioheaders/fhr/v9.9.9"
    assert conformance["schema_used"] is None


def test_unknown_schema_version_under_a_bundled_url_is_invalid(tmp_path):
    # The URL selects the schema (V1-V3); the selected schema rejects the version.
    source = (FIXTURES / "fhr-valid.fhr.fasta").read_bytes()
    path = tmp_path / "v9.fhr.fasta"
    path.write_bytes(source.replace(b"schemaVersion: '2.0'", b"schemaVersion: '9.0'"))
    conformance = assess(path)["conformance"]
    assert conformance["result"] == "invalid"
    assert "schemaVersion" in conformance["reason"]


def test_no_fair_bioheaders_lines_means_no_conformance_section():
    assert (
        assess("ncbi-refseq_gff3_GCF_000002985.6_WBcel235_genomic.gff")["conformance"]
        is None
    )
