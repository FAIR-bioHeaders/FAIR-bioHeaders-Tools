# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The draft GFF3 annotation header FHGFF3 (FHR-Specification spec 007, contracts/cli.md)."""

import copy
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bioheaders import (
    FHGFF3_SCHEMA,
    cross_check,
    fhr,
    header_type,
    is_fhgff3_schema,
    read_chunks,
    schema_for,
)
from bioheaders.cli import (
    MAX_DIRECTIVE_BYTES,
    SequenceScan,
    checksum,
    combine,
    strip_header,
)
from bioheaders.gff3 import _genome_match, header_report

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
FIXTURES = ROOT / "tests" / "fixtures" / "fhgff3"
EXAMPLES = ROOT / "examples" / "fhgff3"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
# The repository was renamed FAIR-bioHeaders-Specification (#108); an old-named
# checkout still works.
SPEC = Path(
    os.environ.get("FHR_SPECIFICATION")
    or next(
        (
            path
            for path in (
                ROOT.parent / "FAIR-bioHeaders-Specification",
                ROOT.parent / "FHR-Specification",
            )
            if path.exists()
        ),
        ROOT.parent / "FAIR-bioHeaders-Specification",
    )
)
FHGFF3_URL = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhgff3.json"
FHP_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhp.json"
)
NOTICE = (
    "A match confirms file identity only, not that the annotation or translations "
    "are correct."
)
BODY = (
    b"##gff-version 3\n"
    b"##sequence-region ctg1 1 20\n"
    b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
)


def run(*args, cwd=None):
    return subprocess.run(
        [str(arg) for arg in args], capture_output=True, cwd=cwd, text=True
    )


def bioheaders_command(*args, **options):
    return run(BIN / "bioheaders", *args, **options)


def vector_bytes(vector):
    data = (FIXTURES / vector["file"]).read_bytes()
    return gzip.decompress(data) if vector["compressed"] else data


@pytest.fixture()
def record():
    return yaml.safe_load(
        (EXAMPLES / "annotation.fhgff3.yaml").read_text(encoding="utf-8")
    )


def write_metadata(path, metadata):
    path.write_text(json.dumps(metadata), encoding="utf-8")
    return path


# Header type and schema.


def test_header_type_from_the_schema_url(record):
    assert is_fhgff3_schema(FHGFF3_URL)
    assert header_type(record) == "FHGFF3"
    assert schema_for(record) == FHGFF3_SCHEMA
    assert header_type(dict(record, schema=FHP_URL)) == "FHP"
    other = dict(record, schema="https://example.org/fhgff3.json")
    assert header_type(other) == "FHR"


def test_bundled_schema_and_examples_match_the_specification():
    if not (SPEC / "fhgff3.json").is_file():
        pytest.skip("no FHR-Specification checkout with FHGFF3")
    assert (SPEC / "fhgff3.json").read_bytes() == (
        ROOT / "bioheaders" / "fhgff3_schema.json"
    ).read_bytes()
    for example in (SPEC / "examples" / "fhgff3").iterdir():
        assert (
            example.read_bytes() == (EXAMPLES / example.name).read_bytes()
        ), example.name


def test_messages(record, tmp_path):
    result = bioheaders_command("validate", EXAMPLES / "minimal-reference.fhgff3.json")
    assert (result.returncode, result.stdout) == (0, "FHGFF3 metadata is valid.\n")
    result = bioheaders_command("validate", ROOT / "examples/example.fhr.json")
    assert result.stdout == "FHR metadata is valid.\n"
    path = write_metadata(
        tmp_path / "x.json", {k: v for k, v in record.items() if k != "derivedFrom"}
    )
    result = bioheaders_command("validate", path)
    assert result.returncode == 1
    assert "no genome link: give a derivedFrom item" in result.stderr
    assert "{'schema'" not in result.stderr


# Conformance vectors (copies of FHR-Specification conformance/, format fhgff3).


@pytest.mark.parametrize("vector", MANIFEST["vectors"], ids=lambda v: v["id"])
def test_conformance_vector(vector):
    result = run(BIN / "fhr-gff3-validate", FIXTURES / vector["file"])
    assert (result.returncode == 0) == (vector["expected"] == "valid"), result.stderr
    if vector["expected"] == "valid":
        assert checksum(vector_bytes(vector), "gff3") == vector["checksum"]


def test_fixtures_match_the_specification():
    published = SPEC / "conformance"
    if not (published / "manifest.json").is_file():
        pytest.skip("no FHR-Specification checkout")
    manifest = json.loads((published / "manifest.json").read_text(encoding="utf-8"))
    vectors = [v for v in manifest["vectors"] if v["format"] == "fhgff3"]
    if not vectors:
        pytest.skip("the FHR-Specification checkout predates FHGFF3")
    assert vectors == MANIFEST["vectors"]
    for vector in vectors:
        assert (published / vector["file"]).read_bytes() == (
            FIXTURES / vector["file"]
        ).read_bytes()


# Placement (G1) and byte preservation.


def test_combine_puts_the_header_after_the_version_line(record):
    combined = combine(fhr(**record), BODY, "gff3")
    lines = combined.split(b"\n")
    assert lines[0] == b"##gff-version 3"
    assert lines[1].startswith(b"#~schema: ")
    assert combined.endswith(
        b"##sequence-region ctg1 1 20\nctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
    )
    assert strip_header(combined, "gff3") == BODY
    assert yaml.safe_load(
        b"\n".join(line[2:] for line in lines if line.startswith(b"#~"))
    )["checksum"] == checksum(combined, "gff3")


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_combine_and_strip_preserve_every_byte(record, ending):
    body = (BODY + b"##FASTA\n>ctg1\nACGTacgtNN\n").replace(b"\n", ending)
    combined = combine(fhr(**record), body, "gff3")
    assert combined.startswith(b"##gff-version 3" + ending + b"#~")
    assert strip_header(combined, "gff3") == body
    tampered = combined.replace(b"ACGTacgtNN", b"ACGTACGTNN")
    assert checksum(tampered, "gff3") != checksum(combined, "gff3")


def test_strip_removes_exactly_the_header_lines_of_every_valid_vector():
    for vector in MANIFEST["vectors"]:
        if vector["expected"] != "valid":
            continue
        data = vector_bytes(vector)
        stripped = strip_header(data, "gff3")
        kept = b"".join(
            line
            for line in data.splitlines(keepends=True)
            if not line.startswith(b"#~")
        )
        assert stripped == kept, vector["id"]


def test_combine_requires_the_version_line(record, tmp_path):
    with pytest.raises(ValueError, match="GFF3 must begin with ##gff-version 3"):
        combine(fhr(**record), b"ctg1\tx\tgene\t1\t2\t.\t+\t.\tID=g\n", "gff3")
    metadata = write_metadata(tmp_path / "m.json", record)
    (tmp_path / "bad.gff3").write_bytes(b"# not a version line\n" + BODY[16:])
    result = run(BIN / "fhr-gff3-combine", metadata, tmp_path / "bad.gff3")
    assert result.returncode == 1
    assert "GFF3 must begin with ##gff-version 3" in result.stderr


@pytest.mark.parametrize(
    "data, message",
    [
        (b"#~schema: x\n##gff-version 3\n", "must follow ##gff-version 3"),
        (BODY + b"#~funding: late\n", "after sequence data"),
        (b"##gff-version 3\n##FASTA\n#~funding: late\n>c\nA\n", "after sequence data"),
    ],
)
def test_misplaced_header_lines(data, message):
    with pytest.raises(ValueError, match=message):
        strip_header(data, "gff3")


def test_plain_gff3_without_a_version_line_strips_unchanged():
    data = b"# a comment\nctg1\tx\tgene\t1\t2\t.\t+\t.\tID=g\n"
    assert strip_header(data, "gff3") == data


def test_default_combine_name_and_compression(record, tmp_path):
    metadata = write_metadata(tmp_path / "m.json", record)
    (tmp_path / "genes.gff").write_bytes(BODY)
    result = bioheaders_command("combine", metadata, tmp_path / "genes.gff")
    assert result.returncode == 0, result.stderr
    combined = (tmp_path / "genes.fhgff3.gff3").read_bytes()
    result = bioheaders_command(
        "combine",
        metadata,
        tmp_path / "genes.gff",
        "-o",
        tmp_path / "genes.fhgff3.gff3.gz",
    )
    assert result.returncode == 0, result.stderr
    assert gzip.decompress((tmp_path / "genes.fhgff3.gff3.gz").read_bytes()) == combined
    result = bioheaders_command("verify", tmp_path / "genes.fhgff3.gff3.gz")
    assert (result.returncode, result.stdout) == (0, "Checksum verified.\n")


def test_stdin_combine_and_strip(record, tmp_path):
    metadata = write_metadata(tmp_path / "m.json", record)
    result = subprocess.run(
        [
            str(BIN / "bioheaders"),
            "combine",
            str(metadata),
            "-",
            "--type",
            "gff3",
            "-o",
            "-",
        ],
        input=BODY,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == combine(fhr(**record), BODY, "gff3")
    stripped = subprocess.run(
        [str(BIN / "fhr-gff3-strip"), "-"], input=result.stdout, capture_output=True
    )
    assert stripped.stdout == BODY


def test_examples_round_trip(tmp_path):
    result = bioheaders_command(
        "strip", EXAMPLES / "annotation.fhgff3.gff3", tmp_path / "plain.gff3"
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "plain.gff3").read_bytes() == (
        EXAMPLES / "no-header.gff3"
    ).read_bytes()
    result = bioheaders_command(
        "combine",
        EXAMPLES / "annotation.fhgff3.yaml",
        tmp_path / "plain.gff3",
        "-o",
        tmp_path / "again.gff3",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "again.gff3").read_bytes() == (
        EXAMPLES / "annotation.fhgff3.gff3"
    ).read_bytes()


def test_converts_between_json_yaml_and_gff3(tmp_path):
    source = EXAMPLES / "annotation.fhgff3.gff3"
    for target in ("x.json", "x.yaml"):
        result = bioheaders_command("convert", source, tmp_path / target)
        assert result.returncode == 0, result.stderr
    data = fhr()
    with open(tmp_path / "x.yaml", "rb") as stream:
        data.input_yaml(stream)
    with open(source, "rb") as stream:
        original = fhr()
        original.input_gff3(stream)
    assert data.__dict__ == original.__dict__


def test_convert_to_gff3_writes_the_version_line(record, tmp_path):
    output = tmp_path / "x.gff3"
    result = bioheaders_command("convert", EXAMPLES / "annotation.fhgff3.yaml", output)
    assert result.returncode == 0, result.stderr
    content = output.read_bytes()
    assert content.startswith(b"##gff-version 3\n#~schema: ")
    result = bioheaders_command("validate", output)
    assert (result.returncode, result.stdout) == (0, "FHGFF3 metadata is valid.\n")
    data = fhr()
    data.input_gff3(content)
    assert data.__dict__ == record
    compressed = tmp_path / "x.gff3.gz"
    result = bioheaders_command(
        "convert", EXAMPLES / "annotation.fhgff3.yaml", compressed
    )
    assert result.returncode == 0, result.stderr
    assert gzip.decompress(compressed.read_bytes()) == content


def test_convert_to_gff3_stdout(record):
    result = bioheaders_command(
        "convert", EXAMPLES / "annotation.fhgff3.yaml", "-", "--to", "gff3"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("##gff-version 3\n#~schema: ")
    data = fhr()
    data.input_gff3(result.stdout.encode("utf-8"))
    assert data.__dict__ == record


@pytest.mark.parametrize(
    "metadata, target, kind",
    [
        (ROOT / "examples/example.fhr.json", "gff3", "GFF3"),
        (ROOT / "examples/fhp/minimal-predicted.fhp.json", "gff3", "GFF3"),
        (ROOT / "examples/fhp/minimal-predicted.fhp.json", "gfa", "GFA"),
        (EXAMPLES / "annotation.fhgff3.yaml", "fasta", "FASTA"),
        (EXAMPLES / "annotation.fhgff3.yaml", "gfa", "GFA"),
    ],
    ids=["FHR-gff3", "FHP-gff3", "FHP-gfa", "FHGFF3-fasta", "FHGFF3-gfa"],
)
def test_convert_rejects_incompatible_sequence_output(metadata, target, kind, tmp_path):
    """Every sequence output checks the header family in both directions (#75 review)."""
    output = tmp_path / f"x.{target}"
    result = bioheaders_command("convert", metadata, output)
    assert result.returncode == 1
    assert f"metadata is incompatible with {kind}" in result.stderr
    assert not output.exists()


def test_convert_writes_supported_sequence_outputs(tmp_path):
    """The formats a family supports keep working after the generic check."""
    for target in ("fasta", "gfa"):
        output = tmp_path / f"fhr.{target}"
        result = bioheaders_command(
            "convert", ROOT / "examples/example.fhr.json", output
        )
        assert result.returncode == 0, result.stderr
        assert output.exists()
    fhp = tmp_path / "fhp.fasta"
    result = bioheaders_command(
        "convert", ROOT / "examples/fhp/minimal-predicted.fhp.json", fhp
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("target", ["x.jsonld", "x.html"])
def test_jsonld_and_microdata_output_are_refused(target, tmp_path):
    result = bioheaders_command(
        "convert", EXAMPLES / "rich.fhgff3.yaml", tmp_path / target
    )
    assert result.returncode == 1
    assert "not available for FHGFF3 metadata yet" in result.stderr


# Native-directive cross-check (warnings only).


def test_cross_check_pairs(record):
    reference = {
        "accession": "GCF_000001405.40",
        "seqcol_id": "S" * 32,
        "assemblyName": "GRCh38.p14",
    }
    metadata = dict(record, genomeReference=reference)
    agreeing = {
        "##species": "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
        "#!genome-build-accession": "NCBI_Assembly:GCF_000001405.40",
        "#!genome-build": "GRCh38.p14",
        "##genome-build": "NCBI GRCh38.p14",
    }
    assert cross_check(metadata, agreeing) == []
    disagreeing = {
        "##species": "https://identifiers.org/taxonomy:10090",
        "#!genome-build-accession": "NCBI_Assembly:GCF_000001405.39",
        "##genome-build": "NCBI GRCh37",
    }
    warnings = cross_check(metadata, disagreeing)
    assert len(warnings) == 3
    assert "taxonomy ID 9606" in warnings[0] and "taxonomy ID 10090" in warnings[0]
    assert "GCF_000001405.39" in warnings[1]
    assert "GRCh37" in warnings[2]
    assert cross_check(metadata, {}) == []
    unparsed = cross_check(metadata, {"##species": "Homo sapiens"})
    assert unparsed == [
        "taxon not compared with ##species Homo sapiens "
        "(no NCBI Taxonomy ID found in one of them)"
    ]


def test_cross_check_uses_the_annotates_accession(record):
    item = dict(record["derivedFrom"][0], accessionID={"name": "GCA_000146045.2"})
    metadata = dict(record, derivedFrom=[item])
    assert cross_check(metadata, {"#!genome-build-accession": "GCA_000146045.2"}) == []
    assert cross_check(metadata, {"#!genome-build-accession": "GCA_000146045.1"})


def test_cross_check_prefers_the_first_annotates_item_with_a_checksum(record):
    first = dict(record["derivedFrom"][0], accessionID={"name": "GCA_000146045.1"})
    second = dict(record["derivedFrom"][0], accessionID={"name": "GCA_000146045.2"})
    metadata = dict(record, derivedFrom=[first, second])
    assert cross_check(metadata, {"#!genome-build-accession": "GCA_000146045.1"}) == []
    warnings = cross_check(metadata, {"#!genome-build-accession": "GCA_000146045.2"})
    assert warnings and "GCA_000146045.1" in warnings[0]


def test_genome_match_uses_the_first_annotates_item_with_a_checksum(record):
    without_checksum = {"headerType": "FHR", "relationship": "annotates"}
    metadata = dict(record, derivedFrom=[without_checksum, record["derivedFrom"][0]])
    status, _ = _genome_match(metadata, EXAMPLES / "genome.fhr.fasta")
    assert status == "matched"


DIRECTIVES = (
    b"##gff-version 3\n"
    b"##species https://identifiers.org/taxonomy:9606\n"
    b"##genome-build NCBI GRCh38.p14\n"
    b"#!genome-build-accession NCBI_Assembly:GCF_000001405.40\n"
    b"#!genome-build GRCh38.p14\n"
    b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
)
EXPECTED_DIRECTIVES = {
    "##species": "https://identifiers.org/taxonomy:9606",
    "##genome-build": "NCBI GRCh38.p14",
    "#!genome-build-accession": "NCBI_Assembly:GCF_000001405.40",
    "#!genome-build": "GRCh38.p14",
}


@pytest.mark.parametrize("size", [1, 2, 3, 4, 7, 13, 24, 25, 1000])
def test_directives_survive_chunk_boundaries(size):
    for content in (
        DIRECTIVES,
        DIRECTIVES.replace(b"\n", b"\r\n"),
        DIRECTIVES.rstrip(b"\n"),
    ):
        assert (
            SequenceScan(read_chunks(content, size), "gff3").directives
            == EXPECTED_DIRECTIVES
        )


GENOME_DIRECTIVES = (
    b"##gff-version 3\n"
    b"#!genome-build GRCh38.p14\n"
    b"#!genome-build-accession NCBI_Assembly:GCF_000001405.40\n"
    b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
)
EXPECTED_GENOME_DIRECTIVES = {
    "#!genome-build": "GRCh38.p14",
    "#!genome-build-accession": "NCBI_Assembly:GCF_000001405.40",
}


@pytest.mark.parametrize("size", list(range(1, 401)) + [1000, 4096, 65536])
def test_genome_build_name_at_a_chunk_boundary_keeps_the_next_directive(size):
    """An exact-name piece is a repeat only when it ends its line (Tools#75)."""
    for content in (
        GENOME_DIRECTIVES,
        GENOME_DIRECTIVES.replace(b"\n", b"\r\n"),
        GENOME_DIRECTIVES.replace(b"\n", b"\r"),
        GENOME_DIRECTIVES.rstrip(b"\n"),
        GENOME_DIRECTIVES.replace(b"\n", b"\r\n").rstrip(b"\r\n"),
        GENOME_DIRECTIVES.replace(b"\n", b"\r").rstrip(b"\r"),
    ):
        assert (
            SequenceScan(read_chunks(content, size), "gff3").directives
            == EXPECTED_GENOME_DIRECTIVES
        )


@pytest.mark.parametrize("size", list(range(1, 40)) + [60, 1000])
def test_directive_like_comment_text_is_not_a_directive(size):
    """A split ordinary comment cannot become a directive (Tools#75 review)."""
    content = (
        b"##gff-version 3\n"
        b"# note: ##species https://identifiers.org/taxonomy:10090\n"
        b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
    )
    assert SequenceScan(read_chunks(content, size), "gff3").directives == {}


def test_over_long_directive_is_dropped_and_does_not_block_later_ones():
    """The buffer is bounded; a dropped line does not hide the next directive."""
    content = (
        b"##gff-version 3\n"
        b"##species " + b"x" * (MAX_DIRECTIVE_BYTES + 10) + b"\n"
        b"##genome-build NCBI GRCh38.p14\n"
        b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
    )
    directives = SequenceScan(read_chunks(content, 7), "gff3").directives
    assert directives == {"##genome-build": "NCBI GRCh38.p14"}


def test_one_byte_chunks_buffer_a_long_directive_within_the_cap():
    """A long directive is reassembled from 1-byte chunks without exceeding the cap."""
    value = "x" * (MAX_DIRECTIVE_BYTES // 2)
    content = (
        b"##gff-version 3\n"
        b"##species " + value.encode("ascii") + b"\n"
        b"##genome-build NCBI GRCh38.p14\n"
        b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
    )
    assert SequenceScan(read_chunks(content, 1), "gff3").directives == {
        "##species": value,
        "##genome-build": "NCBI GRCh38.p14",
    }
    # Feed one line a byte at a time and check the buffer never exceeds the cap.
    scan = SequenceScan([], "gff3")
    line = b"##species " + b"y" * (MAX_DIRECTIVE_BYTES - 30)
    for index in range(len(line)):
        scan._directive_part(line[index : index + 1])
        assert (
            scan._directive_line is None
            or len(scan._directive_line) <= MAX_DIRECTIVE_BYTES
        )
    scan._directive_part(b"\n")
    assert scan.directives == {"##species": "y" * (MAX_DIRECTIVE_BYTES - 30)}


def test_first_directive_value_wins_without_buffering_repeats():
    content = (
        b"##gff-version 3\n"
        b"##species https://identifiers.org/taxonomy:9606\n"
        b"##species https://identifiers.org/taxonomy:10090\n"
        b"ctg1\tsynthetic\tgene\t1\t20\t.\t+\t.\tID=gene1\n"
    )
    for size in (1, 3, 7, 1000):
        assert SequenceScan(read_chunks(content, size), "gff3").directives == {
            "##species": "https://identifiers.org/taxonomy:9606"
        }


def test_verify_warns_and_keeps_its_exit_status(record, tmp_path):
    body = BODY.replace(
        b"##sequence-region",
        b"##species https://identifiers.org/taxonomy:10090\n" b"##sequence-region",
    )
    path = tmp_path / "x.gff3"
    path.write_bytes(combine(fhr(**record), body, "gff3"))
    result = run(BIN / "fhr-gff3-validate", path)
    assert result.returncode == 0
    assert result.stdout == "Checksum verified.\n"
    assert (
        "FHR: warning: taxon https://identifiers.org/taxonomy:9606 (taxonomy ID 9606) "
        "differs from ##species" in result.stderr
    )
    assert path.read_bytes() == combine(fhr(**record), body, "gff3")


def test_directives_after_the_header_block_are_not_compared(record, tmp_path):
    body = BODY + b"##species https://identifiers.org/taxonomy:10090\n"
    path = tmp_path / "x.gff3"
    path.write_bytes(combine(fhr(**record), body, "gff3"))
    result = run(BIN / "fhr-gff3-validate", path)
    assert (result.returncode, result.stderr) == (0, "")


# verify-links.


def links(*args, cwd=None):
    return bioheaders_command("verify-links", *args, cwd=cwd)


def test_links_matched_and_stale():
    result = links(EXAMPLES / "annotation.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith(
        "derivedFrom[0] FHR annotates: matched"
    )
    assert result.stdout.splitlines()[-1] == NOTICE
    result = links(EXAMPLES / "stale-parent.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta")
    assert result.returncode == 3
    assert "derivedFrom[0] FHR annotates: not matched" in result.stdout


def test_links_genome_reference(tmp_path):
    reference = json.loads((EXAMPLES / "minimal-reference.fhgff3.json").read_text())
    annotation = tmp_path / "ref.gff3"
    annotation.write_bytes(combine(fhr(**reference), BODY, "gff3"))
    genome = yaml.safe_load(
        b"\n".join(
            line[2:]
            for line in (EXAMPLES / "genome.fhr.fasta").read_bytes().splitlines()
            if line.startswith(b";~")
        )
    )

    def genome_file(name, **changes):
        path = tmp_path / name
        path.write_bytes(
            combine(fhr(**dict(genome, **changes)), b">ctg1\nACGT\n", "fasta")
        )
        return path

    result = links(annotation)
    assert result.returncode == 0
    assert (
        "genomeReference SYNTHETIC_ASSEMBLY.1: not checked (no FHR genome supplied)"
        in result.stdout
    )
    result = links(annotation, genome_file("no-seqcol.fa"))
    assert "not checked (" in result.stdout and "no seqcol_id recorded" in result.stdout
    result = links(annotation, genome_file("same.fa", seqcol_id="S" * 32))
    assert result.returncode == 0
    assert "genomeReference SYNTHETIC_ASSEMBLY.1: matched (" in result.stdout
    assert "not a recorded parent" not in result.stdout
    result = links(annotation, genome_file("other.fa", seqcol_id="T" * 32))
    assert result.returncode == 3
    assert "genomeReference SYNTHETIC_ASSEMBLY.1: not matched (" in result.stdout
    result = bioheaders_command("verify-links", "--require-all", annotation)
    assert result.returncode == 3


def test_links_gff3_parent_and_full_chain(tmp_path):
    """FHR genome -> FHGFF3 annotation -> FHP proteins (spec 007 SC-006)."""
    annotation_checksum = checksum(
        (EXAMPLES / "annotation.fhgff3.gff3").read_bytes(), "gff3"
    )
    genome_checksum = checksum((EXAMPLES / "genome.fhr.fasta").read_bytes(), "fasta")
    proteins = json.loads(
        (ROOT / "examples/fhp/minimal-predicted.fhp.json").read_text()
    )
    proteins["derivedFrom"] = [
        {
            "headerType": "FHR",
            "checksum": genome_checksum,
            "relationship": "translatedFrom",
        },
        {
            "headerType": "FHGFF3",
            "checksum": annotation_checksum,
            "relationship": "translatedFrom",
        },
    ]
    path = tmp_path / "proteins.fhp.fasta"
    path.write_bytes(combine(fhr(**proteins), b">p1\nMKT*\n", "fasta"))
    result = links(
        path, EXAMPLES / "genome.fhr.fasta", EXAMPLES / "annotation.fhgff3.gff3"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "derivedFrom[0] FHR translatedFrom: matched" in result.stdout
    assert "derivedFrom[1] FHGFF3 translatedFrom: matched" in result.stdout
    result = links(EXAMPLES / "annotation.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta")
    assert result.returncode == 0
    result = links(
        path, EXAMPLES / "genome.fhr.fasta", EXAMPLES / "stale-parent.fhgff3.gff3"
    )
    assert result.returncode == 3
    assert "derivedFrom[1] FHGFF3 translatedFrom: not matched" in result.stdout
    assert "derivedFrom[0] FHR translatedFrom: matched" in result.stdout


def test_links_never_write(tmp_path):
    before = {p.name: p.read_bytes() for p in EXAMPLES.iterdir()}
    links(EXAMPLES / "annotation.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta")
    assert before == {p.name: p.read_bytes() for p in EXAMPLES.iterdir()}


# The report the gff3-validator uses.


def test_header_report():
    good = header_report(
        EXAMPLES / "annotation.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta"
    )
    assert good["present"] and good["header_type"] == "FHGFF3"
    for key in ("placement", "yaml", "checksum", "schema", "genome_link"):
        assert good[key]["ok"] is True, key
    assert good["genome_match"] == "matched"
    assert header_report(EXAMPLES / "annotation.fhgff3.gff3")["genome_match"] is None
    stale = header_report(
        EXAMPLES / "stale-parent.fhgff3.gff3", EXAMPLES / "genome.fhr.fasta"
    )
    assert stale["checksum"]["ok"] is True and stale["genome_match"] == "not matched"
    invalid = header_report(EXAMPLES / "header-invalid.fhgff3.gff3")
    assert invalid["schema"]["ok"] is True
    assert invalid["genome_link"]["ok"] is False
    assert "no genome link" in invalid["genome_link"]["message"]
    plain = header_report(EXAMPLES / "no-header.gff3")
    assert plain["present"] is False and plain["placement"]["ok"] is None


def test_header_report_failures(record, tmp_path):
    late = tmp_path / "late.gff3"
    late.write_bytes(combine(fhr(**record), BODY, "gff3") + b"#~funding: late\n")
    assert header_report(late)["placement"]["ok"] is False
    tampered = tmp_path / "tampered.gff3"
    tampered.write_bytes(
        combine(fhr(**record), BODY, "gff3").replace(b"gene1", b"gene2")
    )
    assert header_report(tampered)["checksum"]["ok"] is False
    bad_yaml = tmp_path / "yaml.gff3"
    bad_yaml.write_bytes(b"##gff-version 3\n#~a: 1\n#~a: 2\n" + BODY[16:])
    assert header_report(bad_yaml)["yaml"]["ok"] is False
    schema = tmp_path / "schema.gff3"
    schema.write_bytes(
        combine(fhr(**record), BODY, "gff3").replace(
            b"#~version: 1.0.0\n", b"#~version: 1.0.0\n#~genome: extra\n"
        )
    )
    report = header_report(schema)
    assert report["schema"]["ok"] is False and "genome" in report["schema"]["message"]
    warned = tmp_path / "warned.gff3"
    warned.write_bytes(
        combine(
            fhr(**record),
            BODY.replace(
                b"##sequence-region",
                b"##species https://identifiers.org/taxonomy:10090\n"
                b"##sequence-region",
            ),
            "gff3",
        )
    )
    assert len(header_report(warned)["warnings"]) == 1


@pytest.mark.parametrize(
    "mutate, match",
    [
        pytest.param(
            lambda metadata: metadata["derivedFrom"][0].pop("checksum"),
            "not checked",
            id="missing-checksum",
        ),
        pytest.param(
            lambda metadata: metadata["derivedFrom"].insert(0, "not an object"),
            "matched",
            id="non-object-item",
        ),
        pytest.param(
            lambda metadata: metadata["derivedFrom"][0].update(accessionID="GCF_1"),
            "matched",
            id="accession-id-string",
        ),
    ],
)
def test_header_report_returns_a_schema_failure_for_malformed_derived_from(
    record, tmp_path, mutate, match
):
    metadata = copy.deepcopy(record)
    mutate(metadata)
    version = b"##gff-version 3\n"
    path = tmp_path / "malformed.gff3"
    path.write_bytes(
        version + fhr(**metadata).output_gff3().encode("utf-8") + BODY[len(version) :]
    )
    report = header_report(path, EXAMPLES / "genome.fhr.fasta")
    assert report["present"] and report["yaml"]["ok"] is True
    assert report["schema"]["ok"] is False
    assert report["genome_link"]["ok"] is True
    assert report["genome_match"] == match


# FHR and FHP are unchanged.


def test_fhr_and_fhp_combine_unchanged():
    fhr_example = (ROOT / "examples/example.fhr.fasta").read_bytes()
    metadata = fhr()
    with open(ROOT / "examples/example.fhr.fasta", "rb") as stream:
        metadata.input_fasta(stream)
    assert combine(metadata, strip_header(fhr_example, "fasta"), "fasta") == fhr_example
    fhp_example = (ROOT / "examples/fhp/example.fhp.fasta").read_bytes()
    with open(ROOT / "examples/fhp/example.fhp.fasta", "rb") as stream:
        metadata = fhr()
        metadata.input_fasta(stream)
    assert combine(metadata, strip_header(fhp_example, "fasta"), "fasta") == fhp_example


def test_assessment_reports_fhgff3_conformance():
    result = bioheaders_command(
        "assess", "--format", "json", EXAMPLES / "annotation.fhgff3.gff3"
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["conformance"]["header_type"] == "FHGFF3"
    assert report["conformance"]["result"] == "valid"


def test_record_copies_are_independent(record):
    data = fhr(**record)
    copy.deepcopy(data.__dict__)["derivedFrom"].clear()
    assert data.__dict__["derivedFrom"]


def test_both_repository_names_select_fhgff3():
    # FAIR-bioHeaders-Specification#108: the old name stays a supported alias.
    for repository in ("FHR-Specification", "FAIR-bioHeaders-Specification"):
        url = f"https://raw.githubusercontent.com/FAIR-bioHeaders/{repository}/main/fhgff3.json"
        assert is_fhgff3_schema(url)
