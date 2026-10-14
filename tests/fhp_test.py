# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The draft protein header FHP (FHR-Specification spec 006, contracts/cli.md)."""

import copy
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

import bioheaders
from bioheaders import fhr, header_type, is_fhp_schema, schema_for
from bioheaders.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
FIXTURES = ROOT / "tests" / "fixtures" / "fhp"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
SPEC = Path(os.environ.get("FHR_SPECIFICATION", ROOT.parent / "FHR-Specification"))
FHP_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhp.json"
)
FHR_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/fhr.json"
)
# Amino-acid bytes with every residue class FHP must preserve (spec 006 FR-017).
PROTEINS = b">p1 stop\nMKTAYIAKQR*\n>p2 rare\r\nMUOBZJXmkta-yi*AKQR\n"
IDENTITY_NOTICE = (
    "A match confirms file identity only, not that the translations are correct."
)


def run(*args, cwd=None):
    return subprocess.run(
        [str(arg) for arg in args], capture_output=True, cwd=cwd, text=True
    )


def bioheaders_command(*args, **options):
    return run(BIN / "bioheaders", *args, **options)


@pytest.fixture()
def minimal():
    return json.loads(
        (ROOT / "examples/fhp/minimal-predicted.fhp.json").read_text(encoding="utf-8")
    )


def vector_bytes(vector):
    data = (FIXTURES / vector["file"]).read_bytes()
    return gzip.decompress(data) if vector["compressed"] else data


def combined(metadata, body=PROTEINS):
    return combine(fhr(**copy.deepcopy(metadata)), body, "fasta")


# Schema selection.


def test_header_type_from_the_schema_url(minimal):
    assert is_fhp_schema(FHP_URL)
    assert is_fhp_schema(FHP_URL.replace("/main/", "/0123abc/"))
    for value in (
        FHR_URL,
        FHP_URL + "\n",
        FHP_URL.replace("FHR-Specification", "FHT-Specification"),
        "fhp.json",
        None,
        1,
    ):
        assert not is_fhp_schema(value), value
    assert header_type(minimal) == "FHP"
    # The examples cite the v0.4.0 release, so its frozen copy is used; it equals
    # the current copy while v0.4.0 is the current release.
    assert schema_for(minimal) == bioheaders.FHP_SCHEMA
    assert schema_for(dict(minimal, schema=FHP_URL)) is bioheaders.FHP_SCHEMA
    fhr_record = json.loads((ROOT / "examples/example.fhr.json").read_text())
    assert header_type(fhr_record) == "FHR"
    assert schema_for(fhr_record) == bioheaders.SCHEMA
    assert header_type({}) == "FHR"


def test_fhp_records_validate_against_the_fhp_schema(minimal):
    fhr(**minimal).fhr_validate()
    with pytest.raises(ValidationError, match="genome"):
        fhr(**dict(minimal, schema=FHR_URL, schemaVersion="2.0")).fhr_validate()
    with pytest.raises(ValidationError):
        fhr(**dict(minimal, sourceType="curated")).fhr_validate()
    with pytest.raises(ValidationError):
        fhr(**dict(minimal, genome="An FHR-only key")).fhr_validate()


def test_every_fhp_example_is_valid():
    names = sorted((ROOT / "examples" / "fhp").glob("*.fhp.*"))
    assert len(names) == 7
    for path in names:
        if path.suffix == ".fasta":
            result = bioheaders_command("verify", path)
            assert (result.returncode, result.stdout) == (0, "Checksum verified.\n")
        else:
            result = bioheaders_command("validate", path)
            assert (result.returncode, result.stdout) == (0, "FHP metadata is valid.\n")


def test_fhr_messages_are_unchanged(tmp_path):
    result = bioheaders_command("validate", ROOT / "examples/example.fhr.json")
    assert (result.returncode, result.stdout) == (0, "FHR metadata is valid.\n")
    result = run(BIN / "fhr-validate", ROOT / "examples/example.fhr.json")
    assert (result.returncode, result.stdout) == (0, "FHR metadata is valid.\n")
    result = bioheaders_command(
        "validate", ROOT / "examples/fhp/minimal-predicted.fhp.json"
    )
    assert result.stdout == "FHP metadata is valid.\n"


# Conformance vectors (copies of FHR-Specification conformance/, format fhp-fasta).


@pytest.mark.parametrize("vector", MANIFEST["vectors"], ids=lambda v: v["id"])
def test_conformance_vector(vector):
    result = run(BIN / "fhr-fasta-validate", FIXTURES / vector["file"])
    assert (result.returncode == 0) == (vector["expected"] == "valid"), result.stderr
    if vector["expected"] == "valid":
        assert checksum(vector_bytes(vector), "fasta") == vector["checksum"]


def test_fixtures_match_the_specification():
    published = SPEC / "conformance"
    if not (published / "manifest.json").is_file():
        pytest.skip("no FHR-Specification checkout")
    manifest = json.loads((published / "manifest.json").read_text(encoding="utf-8"))
    vectors = [v for v in manifest["vectors"] if v["format"] == "fhp-fasta"]
    assert vectors == MANIFEST["vectors"]
    for vector in vectors:
        assert (published / vector["file"]).read_bytes() == (
            FIXTURES / vector["file"]
        ).read_bytes()
    assert (SPEC / "fhp.json").read_bytes() == (
        ROOT / "bioheaders" / "fhp_schema.json"
    ).read_bytes()


# Byte preservation, whatever the alphabet.


def test_combine_and_strip_preserve_every_protein_byte(minimal):
    data = combined(minimal)
    assert data.endswith(PROTEINS)
    assert strip_header(data, "fasta") == PROTEINS
    reader = fhr()
    reader.input_fasta(data)
    assert reader.checksum == checksum(data, "fasta")
    reader.fhr_validate()


def test_strip_removes_exactly_the_fhp_lines_of_every_valid_vector():
    for vector in MANIFEST["vectors"]:
        if vector["expected"] != "valid":
            continue
        data = vector_bytes(vector)
        metadata = fhr()
        metadata.input_fasta(data)
        body = strip_header(data, "fasta")
        assert body == b"".join(
            line
            for line in data.splitlines(keepends=True)
            if not line.startswith(b";~")
        ), vector["id"]
        # Combining the stripped body again gives a valid file with that body,
        # and stripping it gives the body back byte for byte.
        again = combine(metadata, body, "fasta")
        assert again.endswith(body)
        assert checksum(again, "fasta") == fhr_checksum_of(again)
        assert strip_header(again, "fasta") == body


def fhr_checksum_of(data):
    reader = fhr()
    reader.input_fasta(data)
    return reader.checksum


def test_normalising_residues_breaks_the_checksum(minimal):
    data = combined(minimal)
    for old, new in ((b"*\n", b"\n"), (b"mkta", b"MKTA"), (b"\r\n", b"\n")):
        changed = data.replace(old, new)
        assert changed != data
        assert checksum(changed, "fasta") != fhr_checksum_of(changed), old


# Command behaviour.


def test_faa_extension_and_default_combine_name(minimal, tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps(minimal), encoding="utf-8")
    (tmp_path / "proteins.faa").write_bytes(PROTEINS)
    result = bioheaders_command("combine", "meta.json", "proteins.faa", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    output = tmp_path / "proteins.fhp.fasta"
    assert output.read_bytes().endswith(PROTEINS)
    assert bioheaders_command("verify", output).stdout == "Checksum verified.\n"
    result = bioheaders_command("strip", output, "back.faa", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "back.faa").read_bytes() == PROTEINS
    # FHR metadata keeps the .fhr.fasta default name.
    (tmp_path / "genome.fa").write_bytes(b">c\nACGT\n")
    fhr_meta = ROOT / "examples/minimal.fhr.json"
    result = bioheaders_command("combine", fhr_meta, "genome.fa", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "genome.fhr.fasta").is_file()


@pytest.mark.parametrize("target", ["out.jsonld", "out.html"])
def test_fhp_jsonld_and_microdata_output_are_refused(target, tmp_path):
    result = bioheaders_command(
        "convert", ROOT / "examples/fhp/minimal-predicted.fhp.json", tmp_path / target
    )
    assert result.returncode == 1
    assert "not available for FHP metadata yet" in result.stderr
    assert not (tmp_path / target).exists()


def test_fhp_converts_between_json_yaml_and_fasta(tmp_path):
    source = ROOT / "examples/fhp/rich-predicted.fhp.yaml"
    record = fhr()
    record.input_yaml(source.read_text(encoding="utf-8"))
    for name in ("x.json", "x.yaml"):
        result = bioheaders_command("convert", source, tmp_path / name)
        assert result.returncode == 0, result.stderr
        back = fhr()
        getattr(back, "input_" + ("json" if name.endswith("json") else "yaml"))(
            (tmp_path / name).read_text(encoding="utf-8")
        )
        assert back.__dict__ == record.__dict__


# verify-links.


@pytest.fixture()
def linked(minimal, tmp_path):
    """An FHP file with an FHR genome parent and an FHGFF3 annotation parent."""
    genome = ROOT / "examples/example.fhr.fasta"
    parent = fhr()
    parent.input_fasta(genome.read_bytes())
    record = dict(
        minimal,
        derivedFrom=[
            {
                "headerType": "FHR",
                "checksum": parent.checksum,
                "relationship": "translatedFrom",
            },
            {
                "headerType": "FHGFF3",
                "checksum": "C" * 43 + "=",
                "relationship": "translatedFrom",
            },
        ],
    )
    path = tmp_path / "linked.fhp.fasta"
    path.write_bytes(combined(record))
    (tmp_path / "ann.gff3").write_bytes(b"##gff-version 3\n")
    data = bytearray(genome.read_bytes())
    data[data.index(b"\n>") + 12] ^= 0x01  # Change one sequence byte.
    (tmp_path / "other.fhr.fasta").write_bytes(bytes(data))
    return path, genome


def links(*args, cwd):
    return bioheaders_command("verify-links", *args, cwd=cwd)


def test_links_matched_and_not_checked(linked, tmp_path):
    path, genome = linked
    result = links(path, genome, "ann.gff3", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"derivedFrom[0] FHR translatedFrom: matched ({genome})",
        # A GFF3 parent without an FHGFF3 header has no checksum to compare
        # (FHR-Specification spec 007 added GFF3 parents).
        "derivedFrom[1] FHGFF3 translatedFrom: not checked (no supplied file of that "
        "header type)",
        "ann.gff3: not checked (No #~ FHR metadata header found)",
        IDENTITY_NOTICE,
    ]


def test_links_not_matched(linked, tmp_path):
    path, _ = linked
    result = links(path, "other.fhr.fasta", cwd=tmp_path)
    assert result.returncode == 3
    lines = result.stdout.splitlines()
    assert lines[0].startswith(
        "derivedFrom[0] FHR translatedFrom: not matched (other.fhr.fasta has checksum "
    )
    assert lines[1] == (
        "derivedFrom[1] FHGFF3 translatedFrom: not checked "
        "(no supplied file of that header type)"
    )
    assert lines[2] == "other.fhr.fasta: not a recorded parent"
    assert lines[-1] == IDENTITY_NOTICE


def test_links_require_all(linked, tmp_path):
    path, genome = linked
    assert links(path, genome, cwd=tmp_path).returncode == 0
    assert links("--require-all", path, genome, cwd=tmp_path).returncode == 3


def test_links_without_derived_from(tmp_path):
    genome = ROOT / "examples/example.fhr.fasta"
    other = ROOT / "examples/fhp/example.fhp.fasta"
    result = links(genome, other, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "no parent files recorded",
        f"{other}: not a recorded parent",
        IDENTITY_NOTICE,
    ]


def test_links_unsupported_and_headerless_parents(linked, tmp_path):
    path, _ = linked
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "plain.fa").write_bytes(b">c\nACGT\n")
    result = links(path, "notes.txt", "plain.fa", cwd=tmp_path)
    assert result.returncode == 0
    assert "notes.txt: not checked (unsupported file type)" in result.stdout
    assert "plain.fa: not checked (" in result.stdout


def test_links_never_write(linked, tmp_path):
    path, genome = linked
    files = [path, genome, tmp_path / "ann.gff3", tmp_path / "other.fhr.fasta"]
    before = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files}
    links(path, genome, "ann.gff3", "other.fhr.fasta", cwd=tmp_path)
    assert {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in files} == before
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["ann.gff3", "linked.fhp.fasta", "other.fhr.fasta"]
    )


def test_links_check_the_file_itself(linked, tmp_path):
    path, genome = linked
    tampered = tmp_path / "tampered.fhp.fasta"
    tampered.write_bytes(path.read_bytes().replace(b"MKTAYIAKQR", b"MKTAYIAKQE"))
    result = links(tampered, genome, cwd=tmp_path)
    assert result.returncode == 1
    assert "Checksum verification failed" in result.stderr


# Assessment.


def test_assessment_reports_fhp_conformance():
    from bioheaders.assess import assess_file

    report = assess_file(ROOT / "examples/fhp/example.fhp.fasta")
    conformance = report["conformance"]
    assert conformance["header_type"] == "FHP"
    assert conformance["result"] == "valid"
    # The example cites the v0.4.0 w3id URL; the schema used is that release's copy.
    assert conformance["schema_used"]["canonical_url"] == FHP_URL.replace(
        "/main/", "/v0.4.0/"
    )
    assert conformance["schema_used"]["version"] == "1.0"


def test_both_repository_names_select_fhp():
    # FAIR-bioHeaders-Specification#108: the old name stays a supported alias.
    for repository in ("FHR-Specification", "FAIR-bioHeaders-Specification"):
        url = f"https://raw.githubusercontent.com/FAIR-bioHeaders/{repository}/main/fhp.json"
        assert bioheaders.is_fhp_schema(url)
    assert not bioheaders.is_fhp_schema(
        "https://raw.githubusercontent.com/FAIR-bioHeaders/Other-Specification/main/fhp.json"
    )
