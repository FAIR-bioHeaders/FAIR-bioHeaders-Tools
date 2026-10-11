# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The ``bioheaders assess`` command (T025)."""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys

import pytest
from assess_helpers import FIXTURES, REFSEQ_GFF3

from bioheaders.cli import SUBCOMMANDS


def bioheaders(*args, stdin=b""):
    return subprocess.run(
        [sys.executable, "-m", "bioheaders", *map(str, args)],
        input=stdin,
        capture_output=True,
    )


@pytest.mark.parametrize("output_format", ["text", "markdown", "json"])
def test_formats(output_format):
    result = bioheaders("assess", "--format", output_format, FIXTURES / REFSEQ_GFF3)
    assert result.returncode == 0, result.stderr
    out = result.stdout.decode()
    if output_format == "json":
        assert json.loads(out)["input"]["format"] == "gff3"
    else:
        assert "RDA-I3-04M" in out


def test_text_is_the_default():
    result = bioheaders("assess", FIXTURES / REFSEQ_GFF3)
    assert result.stdout.decode().startswith("FAIR header assessment: ")


def test_output_directory(tmp_path):
    out = tmp_path / "reports"
    result = bioheaders("assess", "--output", out, FIXTURES / REFSEQ_GFF3)
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in out.iterdir()) == [
        REFSEQ_GFF3 + ".assessment.json",
        REFSEQ_GFF3 + ".assessment.md",
    ]
    assert REFSEQ_GFF3 in result.stdout.decode()
    first = (out / (REFSEQ_GFF3 + ".assessment.json")).read_bytes()
    bioheaders("assess", "--output", out, FIXTURES / REFSEQ_GFF3)
    assert (out / (REFSEQ_GFF3 + ".assessment.json")).read_bytes() == first
    assert not [p for p in out.iterdir() if p.name.endswith(".tmp")]


def test_stdin_with_and_without_type():
    content = (FIXTURES / "ncbi-clinvar_vcf_clinvar.vcf").read_bytes()
    result = bioheaders(
        "assess", "--type", "vcf", "--format", "json", "-", stdin=content
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["input"]["path"] == "-" and report["input"]["size"] is None
    assert report["input"]["format_source"] == "option"
    assert bioheaders("assess", "-", stdin=content).returncode == 2


def test_missing_path_exits_1():
    result = bioheaders("assess", FIXTURES / "does-not-exist.gff3")
    assert result.returncode == 1
    assert result.stderr.decode().startswith("FHR: ")


def test_corrupt_gzip_exits_1(tmp_path):
    path = tmp_path / "bad.gff3.gz"
    path.write_bytes(gzip.compress(b"##gff-version 3\n" * 1000, mtime=0)[:40])
    result = bioheaders("assess", "--format", "json", path)
    assert result.returncode == 1
    assert result.stderr.decode().startswith("FHR: ")
    assert json.loads(result.stdout)["input"]["scope"] == "error"


@pytest.mark.parametrize("name", ["stub.bam", "gff3-in-tar.gff.gz"])
def test_out_of_scope_exits_0(name):
    result = bioheaders("assess", "--format", "json", FIXTURES / name)
    assert result.returncode == 0
    assert json.loads(result.stdout)["input"]["scope"] == "out_of_scope"


def test_record_limit_zero_reads_header_only():
    path = FIXTURES / "gzip-refseq.gff.gz"
    report = json.loads(
        bioheaders("assess", "--format", "json", "--record-limit", "0", path).stdout
    )
    assert report["input"]["records_sampled"] == 0
    report = json.loads(bioheaders("assess", "--format", "json", path).stdout)
    assert report["input"]["records_sampled"] == 1


def test_hash_inputs():
    path = FIXTURES / "gzip-refseq.gff.gz"
    report = json.loads(
        bioheaders("assess", "--format", "json", "--hash-inputs", path).stdout
    )
    assert (
        report["input"]["file_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    report = json.loads(bioheaders("assess", "--format", "json", path).stdout)
    assert "file_sha256" not in report["input"]


def test_help_shows_the_rda_attribution():
    result = bioheaders("assess", "--help")
    assert result.returncode == 0
    text = result.stdout.decode()
    assert "10.15497/rda00050" in text and "CC BY 4.0" in text


def _subcommand_help(subcommands, name):
    args_parser = argparse.ArgumentParser(prog="bioheaders")
    subparsers = args_parser.add_subparsers(dest="command")
    for subcommand in subcommands:
        subcommand.add_to(subparsers)
    return subparsers.choices[name].format_help()


def test_existing_subcommand_help_is_unchanged():
    names = [s.name for s in SUBCOMMANDS]
    assert names == [
        "convert",
        "validate",
        "combine",
        "strip",
        "verify",
        "verify-links",
        "assess",
    ]
    added = {"verify-links", "assess"}
    without = [s for s in SUBCOMMANDS if s.name not in added]
    for name in names:
        if name not in added:
            assert _subcommand_help(SUBCOMMANDS, name) == _subcommand_help(
                without, name
            )


PAIRS = FIXTURES / "pairs"


def test_related_file_report_sections():
    result = bioheaders(
        "assess",
        "--related",
        PAIRS / "genome-plain.fa",
        PAIRS / "annotation-no-link.gff3",
    )
    assert result.returncode == 0, result.stderr
    text = result.stdout.decode()
    assert "Circumstantial evidence (not a recorded link)" in text
    assert "verdict: consistent" in text
    assert "Pair: consistent-unverified" in text


@pytest.mark.parametrize(
    "derived, genome, flag, code",
    [
        ("annotation-version-mismatch.gff3", "genome-fhr-v2.fa", True, 3),
        ("annotation-version-mismatch.gff3", "genome-fhr-v2.fa", False, 0),
        ("annotation-correct.gff3", "genome-fhr.fa", True, 0),
        ("variants-contig-md5.vcf", "genome-plain.fa", True, 3),
        ("annotation-accession-only.gff3", "genome-plain.fa", True, 0),
    ],
)
def test_fail_on_mismatch(derived, genome, flag, code):
    options = ["--fail-on-mismatch"] if flag else []
    result = bioheaders(
        "assess", *options, "--related", PAIRS / genome, PAIRS / derived
    )
    assert result.returncode == code, result.stderr


def test_unreadable_related_file_exits_1_before_3(tmp_path):
    result = bioheaders(
        "assess",
        "--fail-on-mismatch",
        "--format",
        "json",
        "--related",
        tmp_path / "missing.fa",
        PAIRS / "annotation-correct.gff3",
    )
    assert result.returncode == 1
    assert result.stderr.decode().startswith("FHR: ")
    report = json.loads(result.stdout)
    assert report["links"][0]["verification"]["reason"] == "related-file-unreadable"
