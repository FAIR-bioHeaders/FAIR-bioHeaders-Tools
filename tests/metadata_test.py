"""``bioheaders metadata``: typed FHR metadata and vitalStats (issue #171)."""

import gzip
import io
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from bioheaders import fhr, load_yaml
from bioheaders.cli import BgzfWriter
from bioheaders.metadata import (
    MASKING,
    FastaStats,
    build_record,
    current_fhr,
    fasta_stats,
    nx_lx,
    orcid_check_digit,
)

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent

# Hand-computed (see the comments): four records, one all-N.
SMALL = (
    b">s1 first record\n"
    b"ACGTNACGTT\n"  # contigs ACGT (4), ACGTT (5) - the N run spans the line end
    b"NNNNNGGCC\n"  # GGCC (4); s1 is 19 bp
    b">s2\n"
    b"nnACGTnn\n"  # leading/trailing n runs: one contig ACGT (4); 8 bp
    b">s3\n"
    b"NNNN\n"  # no contig; 4 bp
    b">s4\n"
    b"AAAAAAAAAAAAAAAAAAAACCCC\n"  # one contig of 24
)
# Contigs 24, 5, 4, 4, 4 (sum 41): 50% = 20.5 -> 24 (L1); 90% = 36.9 ->
# 24+5+4+4 = 37 (L4, N 4). Scaffolds 24, 19, 8, 4 (sum 55): 50% = 27.5 -> 24+19
# (L2, N 19); 90% = 49.5 -> 24+19+8 = 51 (L3, N 8). G+C = 4+2+4 = 14 over
# A+C+G+T = 13+4+24 = 41 -> 34.146...% -> 34.15.
SMALL_STATS = {
    "totalBasePairs": 55,
    "numberContigs": 5,
    "numberScaffolds": 4,
    "N50": 24,
    "L50": 1,
    "N90": 4,
    "L90": 4,
    "scaffoldN50": 19,
    "scaffoldL50": 2,
    "scaffoldN90": 8,
    "scaffoldL90": 3,
    "gcContent": 34.15,
}

ADAM = "Adam Wright <https://orcid.org/0000-0002-5719-4024>"
DAVID = "David Molik <https://orcid.org/0000-0003-3192-6538>"
REQUIRED_ARGS = [
    "--genome",
    "Taeniopygia guttata",
    "--taxon-name",
    "Taeniopygia guttata",
    "--taxon-id",
    "59729",
    "--version",
    "1",
    "--metadata-author",
    ADAM,
    "--assembly-author",
    DAVID,
    "--date-created",
    "2024-01-02",
    "--masking",
    "not-masked",
]


def bioheaders(*args, stdin=b""):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], input=stdin, capture_output=True
    )


def stats_of(data, size=None):
    if size is None:
        return fasta_stats([data])
    return fasta_stats(data[i : i + size] for i in range(0, len(data), size))


def bgzf(data):
    out = io.BytesIO()
    writer = BgzfWriter(out)
    writer.write(data)
    writer.close()
    return out.getvalue()


# ---------------------------------------------------------------- statistics


def test_hand_computed_statistics():
    assert stats_of(SMALL) == (SMALL_STATS, [])


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 11, 64])
def test_chunk_boundaries_do_not_change_statistics(size):
    assert stats_of(SMALL, size) == (SMALL_STATS, [])


@pytest.mark.parametrize("size", [None, 1, 3])
def test_crlf_lone_cr_and_comments(size):
    crlf = SMALL.replace(b"\n", b"\r\n")
    assert stats_of(crlf, size)[0] == SMALL_STATS
    assert stats_of(SMALL.replace(b"\n", b"\r"), size)[0] == SMALL_STATS
    commented = b"; ordinary comment\n\n" + SMALL.replace(
        b">s2\n", b">s2\n; old-style comment > with marker\n"
    )
    assert stats_of(commented, size)[0] == SMALL_STATS


def test_single_contig():
    stats, _ = stats_of(b">only\nGGGGAAAATT\n")
    assert stats == {
        "totalBasePairs": 10,
        "numberContigs": 1,
        "numberScaffolds": 1,
        "N50": 10,
        "L50": 1,
        "N90": 10,
        "L90": 1,
        "scaffoldN50": 10,
        "scaffoldL50": 1,
        "scaffoldN90": 10,
        "scaffoldL90": 1,
        "gcContent": 40.0,
    }


def test_all_n_has_no_contig_statistics_or_gc():
    stats, _ = stats_of(b">a\nNNNN\nnnnn\n>b\nNN\n")
    assert stats == {
        "totalBasePairs": 10,
        "numberContigs": 0,
        "numberScaffolds": 2,
        "scaffoldN50": 8,
        "scaffoldL50": 1,
        "scaffoldN90": 2,
        "scaffoldL90": 2,
    }


def test_other_ambiguity_codes_are_bases_but_not_gc():
    stats, _ = stats_of(b">a\nSSWWACGTRY\n")
    assert stats["numberContigs"] == 1 and stats["N50"] == 10
    assert stats["gcContent"] == 50.0  # S and W left out: 2 of A, C, G, T


def test_u_counts_like_t():
    assert stats_of(b">r\nGCUU\n")[0]["gcContent"] == 50.0


def test_records_without_bases_are_not_scaffolds():
    stats, warnings = stats_of(b">empty1\n>a\nACGT\n>empty2 desc\n\n")
    assert stats["numberScaffolds"] == 1
    assert warnings == [
        "--stats-from: 2 record(s) without bases are not counted as scaffolds: "
        "'empty1', 'empty2'"
    ]


@pytest.mark.parametrize(
    "data, message",
    [
        (b"", "holds no '>' records"),
        (b"; just a comment\n", "holds no '>' records"),
        (b">a\n>b\n", "hold no bases"),
        (b"ACGT\n>a\nACGT\n", "before the first '>'"),
        (b">p\nMKVLAAGIVG\n", "'L', which is not an IUPAC nucleotide code"),
        (b">a\nAC-GT\n", "'-'"),
        (b">a\nACGT>b\n", "'>'"),
    ],
)
def test_stat_errors(data, message):
    with pytest.raises(ValueError, match=message):
        stats_of(data)


def test_nx_lx_exact_thresholds():
    assert nx_lx([10, 10]) == (10, 1, 10, 2)  # 50% reached exactly by the first
    assert nx_lx([1]) == (1, 1, 1, 1)
    assert nx_lx([5, 3, 2]) == (5, 1, 2, 3)


def test_memory_holds_lengths_not_sequence():
    stats = FastaStats()
    line = b"ACGT" * 1024 + b"\n"
    stats.feed(b">big\n")
    for _ in range(256):
        stats.feed(line * 16)
    assert stats.length == 4096 * 256 * 16
    assert len(stats.contigs) == 0 and stats.contig == stats.length


# ---------------------------------------------------------------- the record


def namespace(**values):
    defaults = dict(
        header_type="fhr",
        genome="g",
        genome_synonym=None,
        taxon_name="Homo sapiens",
        taxon_id="9606",
        assembly_version="1",
        metadata_author=[ADAM],
        assembly_author=[DAVID],
        date_created="2024-01-02",
        masking="soft-masked",
        voucher_specimen=None,
        accession=None,
        accession_url=None,
        instrument=None,
        scholarly_article=None,
        documentation=None,
        identifier=None,
        related_link=None,
        funding=None,
        reuse_conditions=None,
        assembly_software=None,
        assembly_protocol=None,
        seqcol_id=None,
        stat=None,
        extra=None,
    )
    defaults.update(values)
    return Namespace(**defaults)


def test_current_contract_is_fhr_2_1_v0_6_0():
    assert current_fhr() == ("https://w3id.org/fair-bioheaders/fhr/v0.6.0", "2.1")
    assert MASKING == (
        "not-masked",
        "hard-masked",
        "soft-masked",
        "repeat-masked",
        "unknown",
    )


def test_orcid_check_digit():
    assert orcid_check_digit("000000021825009") == "7"  # ORCID's documented example
    assert orcid_check_digit("000000025719402") == "4"


def test_every_option_maps_to_its_schema_field():
    record = build_record(
        namespace(
            genome_synonym=["zebra finch", "bTaeGut1"],
            metadata_author=[ADAM, "Some Org"],
            voucher_specimen="specimen 1",
            accession="GCA_000001405.29",
            accession_url="https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000001405.29",
            instrument=["PacBio Revio", "Illumina NovaSeq"],
            scholarly_article="10.5281/zenodo.6762550",
            documentation="docs",
            identifier=["insdc.gca:GCA_000001405.29"],
            related_link=["https://example.org/a"],
            funding="grant 1",
            reuse_conditions="CC-BY-4.0",
            assembly_software=["hifiasm=0.19.8", "yahs=1.2=https://x.org/?a=b"],
            assembly_protocol="https://example.org/protocol",
            seqcol_id="A" * 32,
            stat=["readTechnology=hifi", "N50=5"],
            extra=["x-vgp-label=bTaeGut1.hap1.cur"],
        )
    )
    assert record == {
        "schema": "https://w3id.org/fair-bioheaders/fhr/v0.6.0",
        "schemaVersion": "2.1",
        "genome": "g",
        "genomeSynonym": ["zebra finch", "bTaeGut1"],
        "taxon": {
            "name": "Homo sapiens",
            "uri": "https://identifiers.org/taxonomy:9606",
        },
        "version": "1",
        "metadataAuthor": [
            {"name": "Adam Wright", "uri": "https://orcid.org/0000-0002-5719-4024"},
            {"name": "Some Org"},
        ],
        "assemblyAuthor": [
            {"name": "David Molik", "uri": "https://orcid.org/0000-0003-3192-6538"}
        ],
        "dateCreated": "2024-01-02",
        "voucherSpecimen": "specimen 1",
        "accessionID": {
            "name": "GCA_000001405.29",
            "url": "https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000001405.29",
        },
        "instrument": ["PacBio Revio", "Illumina NovaSeq"],
        "scholarlyArticle": "10.5281/zenodo.6762550",
        "documentation": "docs",
        "identifier": ["insdc.gca:GCA_000001405.29"],
        "relatedLink": ["https://example.org/a"],
        "funding": "grant 1",
        "reuseConditions": "CC-BY-4.0",
        "masking": "soft-masked",
        "vitalStats": {"N50": 5, "readTechnology": "hifi"},
        "assemblySoftware": [
            {"name": "hifiasm", "version": "0.19.8"},
            {"name": "yahs", "version": "1.2", "uri": "https://x.org/?a=b"},
        ],
        "assemblyProtocol": "https://example.org/protocol",
        "seqcol_id": "A" * 32,
        "x-vgp-label": "bTaeGut1.hap1.cur",
    }
    assert "checksum" not in record


@pytest.mark.parametrize(
    "values, message",
    [
        ({"taxon_id": "96O6"}, "--taxon-id: '96O6' is not an NCBI taxonomy id"),
        ({"taxon_id": "-1"}, "--taxon-id"),
        ({"taxon_id": "0"}, "--taxon-id: '0' is not"),
        ({"taxon_id": "00012"}, "no leading zero"),
        ({"taxon_id": " 12"}, "--taxon-id"),
        ({"taxon_id": "1" * 5000}, r"--taxon-id: '1{40}\.\.\.' is not"),
        ({"genome": "caf\udce9"}, "--genome: the value is not valid UTF-8"),
        ({"stat": ["totalBasePairs=" + "9" * 23]}, "larger than 2\\^63 - 1"),
        ({"date_created": "2026-02-30"}, "--date-created: '2026-02-30' is not a date"),
        ({"date_created": "2026-2-3"}, "is not an ISO date"),
        ({"date_created": "today"}, "is not an ISO date"),
        (
            {"metadata_author": ["A <https://orcid.org/0000-0002-5719-4025>"]},
            "fails the ORCID check digit",
        ),
        (
            {"assembly_author": ["A <http://orcid.org/0000-0002-5719-4024>"]},
            "--assembly-author: 'http://orcid.org/0000-0002-5719-4024' is not an "
            "ORCID URI",
        ),
        ({"assembly_author": ["<https://orcid.org/0000-0002-5719-4024>"]}, "no name"),
        ({"assembly_author": ["  "]}, "--assembly-author: the value is empty"),
        ({"masking": "masked"}, "--masking: 'masked' is not one of"),
        ({"genome": "a\nb"}, r"--genome: control or line-break character '\\n'"),
        ({"genome": "a b"}, "--genome: control or line-break"),
        ({"genome": "a\x00b"}, "--genome: control"),
        ({"extra": ["x-a=1", "x-a=2"]}, "--extra: x-a given more than once"),
        ({"extra": ["X-a=1"]}, "is not an extension key"),
        ({"extra": ["x-=1"]}, "is not an extension key"),
        ({"extra": ["x-a"]}, "is not x-KEY=VALUE"),
        ({"stat": ["N50=big"]}, "--stat N50: 'big' is not a non-negative integer"),
        ({"stat": ["N50=1_000"]}, "is not a non-negative integer"),
        ({"stat": ["N50=1.0"]}, "is not a non-negative integer"),
        ({"stat": ["N50=-1"]}, "is not a non-negative integer"),
        ({"stat": ["N50=\u0661"]}, "is not a non-negative integer"),
        ({"stat": ["gcContent=nan"]}, "is not a non-negative number"),
        ({"stat": ["gcContent=1e400"]}, "is not a non-negative number"),
        ({"stat": ["gcContent=" + "9" * 400]}, "at most 30 characters"),
        ({"assembly_author": ["X <y> z"]}, "is neither 'Name' nor"),
        ({"stat": ["n50=1"]}, "is not KEY=VALUE with KEY one of"),
        ({"stat": ["N50=1", "N50=2"]}, "given more than once"),
        ({"assembly_software": ["hifiasm="]}, "is not NAME, NAME=VERSION"),
        ({"assembly_software": ["=1"]}, "is not NAME, NAME=VERSION"),
        ({"accession_url": "https://x.org"}, "--accession-url needs --accession"),
        (
            {"genome": None, "assembly_version": "", "metadata_author": []},
            "missing required values: --genome, --version, --metadata-author",
        ),
    ],
)
def test_bad_values_name_their_option(values, message):
    with pytest.raises(ValueError, match=message):
        build_record(namespace(**values))


def test_stat_that_stats_from_computes_is_refused():
    # Refused even when this FASTA left the value out (all-N: no N50).
    for given in ({"N50": 4}, {"totalBasePairs": 4}, None):
        with pytest.raises(ValueError, match="--stats-from computes this value"):
            build_record(namespace(stat=["N50=3"], stats_from="g.fa"), given)
    record = build_record(
        namespace(stat=["readTechnology=hifi"], stats_from="g.fa"), {"N50": 4}
    )
    assert record["vitalStats"] == {"N50": 4, "readTechnology": "hifi"}


def test_tab_is_allowed_and_software_forms():
    record = build_record(
        namespace(
            documentation="a\tb",
            assembly_software=["hifiasm", "yahs==https://x.org/yahs", "a=1"],
        )
    )
    assert record["documentation"] == "a\tb"
    spaced = build_record(namespace(assembly_author=[" Lead and trail "]))
    assert spaced["assemblyAuthor"] == [{"name": " Lead and trail "}]
    assert record["assemblySoftware"] == [
        {"name": "hifiasm"},
        {"name": "yahs", "uri": "https://x.org/yahs"},
        {"name": "a", "version": "1"},
    ]


# ---------------------------------------------------------------- the command


def test_command_writes_yaml_to_stdout_and_it_round_trips():
    result = bioheaders("metadata", *REQUIRED_ARGS)
    assert result.returncode == 0, result.stderr
    record = load_yaml(result.stdout.decode())
    assert record["schema"] == "https://w3id.org/fair-bioheaders/fhr/v0.6.0"
    assert record["schemaVersion"] == "2.1"
    assert record["version"] == "1" and "checksum" not in record
    assert result.stderr == b""


def test_missing_values_are_listed_and_nothing_is_written(tmp_path):
    out = tmp_path / "m.yaml"
    result = bioheaders("metadata", "--genome", "g", "-o", out)
    assert result.returncode == 1
    assert result.stderr.decode() == (
        "FHR: missing required values: --taxon-name, --taxon-id, --version, "
        "--metadata-author, --assembly-author, --date-created, --masking "
        "(FHR metadata never invents them)\n"
    )
    assert not out.exists()


def test_date_created_has_no_default():
    args = [a for a in REQUIRED_ARGS if a not in ("--date-created", "2024-01-02")]
    result = bioheaders("metadata", *args)
    assert result.returncode == 1
    assert b"missing required value: --date-created" in result.stderr


def test_invalid_value_leaves_no_output(tmp_path):
    out = tmp_path / "m.yaml"
    out.write_text("old\n")
    result = bioheaders(
        "metadata", *REQUIRED_ARGS, "--related-link", "javascript:alert(1)", "-o", out
    )
    assert result.returncode == 1
    assert b"relatedLink[0]" in result.stderr and b"R14" in result.stderr
    assert out.read_text() == "old\n"


@pytest.mark.parametrize(
    "extra, message",
    [
        (["--identifier", "no-colon"], b"schema validation failed at $.identifier[0]"),
        (["--scholarly-article", "https://doi.org/10.1/x"], b"scholarlyArticle"),
        (["--seqcol-id", "short"], b"seqcol_id"),
    ],
)
def test_schema_validation_failures(extra, message):
    result = bioheaders("metadata", *REQUIRED_ARGS, *extra)
    assert result.returncode == 1 and message in result.stderr
    assert result.stdout == b""


@pytest.mark.parametrize("kind", ["fhp", "fhgff3"])
def test_other_types_are_refused_for_now(kind):
    result = bioheaders("metadata", "--type", kind, *REQUIRED_ARGS)
    assert result.returncode == 1
    assert b"--type " + kind.encode() + b": only fhr metadata" in result.stderr


def test_masking_choices_come_from_the_schema():
    result = bioheaders("metadata", *REQUIRED_ARGS[:-1], "masked")
    assert result.returncode == 2 and b"invalid choice: 'masked'" in result.stderr


def test_json_output_from_extension_and_flag(tmp_path):
    out = tmp_path / "m.json"
    assert bioheaders("metadata", *REQUIRED_ARGS, "-o", out).returncode == 0
    from_extension = json.loads(out.read_text())
    flagged = bioheaders("metadata", *REQUIRED_ARGS, "--format", "json")
    assert json.loads(flagged.stdout) == from_extension
    assert from_extension["taxon"]["uri"] == "https://identifiers.org/taxonomy:59729"


HOSTILE = [
    "quote \" and ' and \\ backslash",
    "> starts a record",
    "@ starts fastq",
    "key: value # not a comment",
    "- not a list",
    "{not: a mapping}",
    "[not, a, list]",
    "yes",
    "010",
    ".nan",
    "null",
    "2024-01-02",
    "&anchor *alias !tag",
    "|",
    "%YAML 1.2",
    "---",
    " leading space",
    "émoji ✓ 🧬",
]


def test_hostile_values_round_trip_through_yaml_json_and_fasta(tmp_path):
    args = list(REQUIRED_ARGS)
    args[1] = HOSTILE[0]
    for value in HOSTILE:
        # VALUE joined with "=": argparse reads a separate "-..." as an option.
        args += [f"--genome-synonym={value}", f"--instrument={value}"]
    args += ["--metadata-author", "O'Brien > <https://orcid.org/0000-0002-1825-0097>"]
    args += ["--extra", "x-a.b_c-d=@>:" + HOSTILE[3]]
    yaml_out = tmp_path / "m.yaml"
    result = bioheaders("metadata", *args, "-o", yaml_out)
    assert result.returncode == 0, result.stderr
    text = yaml_out.read_text(encoding="utf-8")
    assert ">" not in text and "@" not in text  # R11: escaped in double quotes
    record = load_yaml(text)
    assert record["genome"] == HOSTILE[0]
    assert record["genomeSynonym"] == HOSTILE
    assert record["instrument"] == HOSTILE
    assert record["metadataAuthor"][1] == {
        "name": "O'Brien >",
        "uri": "https://orcid.org/0000-0002-1825-0097",
    }
    assert record["x-a.b_c-d"] == "@>:" + HOSTILE[3]
    # The YAML embeds unchanged as header lines (R11, R12).
    embedded = fhr()
    embedded.input_fasta(
        "".join(";~" + line + "\n" for line in text.splitlines()) + ">a\nACGT\n"
    )
    assert embedded.__dict__ == record
    as_json = bioheaders("metadata", *args, "--format", "json")
    assert json.loads(as_json.stdout) == record
    fasta = tmp_path / "g.fa"
    fasta.write_bytes(SMALL)
    combined = tmp_path / "g.fhr.fa"
    assert bioheaders("combine", yaml_out, fasta, "-o", combined).returncode == 0
    verified = bioheaders("verify", combined)
    assert verified.returncode == 0 and verified.stderr == b"", verified.stderr
    assert b"\n>" not in combined.read_bytes().split(b"\n>s1")[0]


@pytest.mark.parametrize("compression", ["plain", "gzip", "bgzf"])
def test_metadata_combine_verify_strip_end_to_end(tmp_path, compression):
    data = {"plain": SMALL, "gzip": gzip.compress(SMALL), "bgzf": bgzf(SMALL)}
    suffix = "" if compression == "plain" else ".gz"
    fasta = tmp_path / f"genome.fa{suffix}"
    fasta.write_bytes(data[compression])
    meta = tmp_path / "metadata.yaml"
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", fasta, "-o", meta)
    assert result.returncode == 0, result.stderr
    assert load_yaml(meta.read_text())["vitalStats"] == SMALL_STATS
    combined = tmp_path / f"genome.fhr.fa{suffix}"
    assert bioheaders("combine", meta, fasta, "-o", combined).returncode == 0
    verified = bioheaders("verify", combined)
    assert verified.returncode == 0, verified.stderr
    assert verified.stdout == b"Checksum verified.\n"
    stripped = tmp_path / "stripped.fa"
    assert bioheaders("strip", combined, stripped).returncode == 0
    assert stripped.read_bytes() == SMALL
    # Statistics from the headed file ignore its header.
    again = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", combined)
    assert load_yaml(again.stdout.decode())["vitalStats"] == SMALL_STATS
    # A standalone document is pre-combine metadata: validate wants a checksum.
    checked = bioheaders("validate", meta)
    assert checked.returncode == 1 and b"'checksum' is a required" in checked.stderr


def test_stats_from_stdin_and_any_file_name(tmp_path):
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", "-", stdin=SMALL)
    assert load_yaml(result.stdout.decode())["vitalStats"] == SMALL_STATS
    galaxy = tmp_path / "dataset_42.dat"  # Galaxy names datasets like this
    galaxy.write_bytes(gzip.compress(SMALL))
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", galaxy)
    assert result.returncode == 0, result.stderr
    assert load_yaml(result.stdout.decode())["vitalStats"] == SMALL_STATS


def test_stats_from_errors_exit_non_zero(tmp_path):
    empty = tmp_path / "empty.fa"
    empty.write_bytes(b"")
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", empty)
    assert result.returncode == 1 and b"holds no '>' records" in result.stderr
    truncated = tmp_path / "t.fa.gz"
    truncated.write_bytes(gzip.compress(SMALL)[:-12])
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", truncated)
    assert result.returncode == 1 and result.stdout == b""
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", tmp_path / "no")
    assert result.returncode == 1 and b"No such file" in result.stderr


def test_stats_from_and_output_must_differ(tmp_path):
    fasta = tmp_path / "g.fa"
    fasta.write_bytes(SMALL)
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", fasta, "-o", fasta)
    assert result.returncode == 1 and fasta.read_bytes() == SMALL


def test_help_lists_the_command():
    result = bioheaders("--help")
    assert b"metadata" in result.stdout
    result = bioheaders("metadata", "--help")
    assert result.returncode == 0 and b"--stats-from" in result.stdout


def test_values_are_checked_before_the_fasta_is_read(tmp_path):
    bad = [
        a if a != DAVID else "D <https://orcid.org/0000-0003-3192-6539>"
        for a in REQUIRED_ARGS
    ]
    result = bioheaders("metadata", *bad, "--stats-from", tmp_path / "missing.fa")
    assert result.returncode == 1 and b"ORCID check digit" in result.stderr
    result = bioheaders(
        "metadata", *REQUIRED_ARGS, "--stat", "N50=1", "--stats-from", tmp_path / "x"
    )
    assert b"--stats-from computes this value" in result.stderr


@pytest.mark.parametrize("name", ["m.txt", "genome.fa", "m"])
def test_output_needs_a_metadata_extension_or_format(tmp_path, name):
    result = bioheaders("metadata", *REQUIRED_ARGS, "-o", tmp_path / name)
    assert result.returncode == 1 and b"give a .yaml, .yml or .json" in result.stderr
    assert not (tmp_path / name).exists()
    result = bioheaders(
        "metadata", *REQUIRED_ARGS, "--format", "yaml", "-o", tmp_path / name
    )
    if name == "genome.fa":  # an extension that names another format
        assert result.returncode == 1 and b"contradicts the extension" in result.stderr
        assert not (tmp_path / name).exists()
    else:
        assert result.returncode == 0


@pytest.mark.parametrize(
    "name, form",
    [
        ("m.html", "yaml"),
        ("m.html", "json"),
        ("m.jsonld", "json"),
        ("m.yaml", "json"),
        ("m.gff3", "yaml"),
    ],
)
def test_format_must_not_contradict_any_known_extension(tmp_path, name, form):
    out = tmp_path / name
    result = bioheaders("metadata", *REQUIRED_ARGS, "--format", form, "-o", out)
    assert result.returncode == 1 and b"contradicts the extension" in result.stderr
    assert not out.exists()


@pytest.mark.parametrize(
    "char", ["\u202e", "\u202a", "\u2066", "\u2069", "\u200b", "\u200e", "\ufeff"]
)
def test_invisible_reordering_characters_are_refused(char):
    with pytest.raises(
        ValueError, match=f"--genome: invisible character U\\+{ord(char):04X}"
    ):
        build_record(namespace(genome=f"evil{char}gnp.exe"))
    with pytest.raises(ValueError, match="--metadata-author: invisible character"):
        build_record(namespace(metadata_author=[f"A{char}B"]))


def test_zero_width_joiners_stay_allowed():
    # ZWNJ and ZWJ are ordinary in Persian, Indic scripts and emoji sequences.
    record = build_record(
        namespace(genome="\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 a\u200db")
    )
    assert "\u200c" in record["genome"] and "\u200d" in record["genome"]


@pytest.mark.parametrize(
    "gc, acgt, percent",
    [(1, 32, 3.13), (3, 32, 9.38), (1, 3, 33.33), (2, 3, 66.67), (1, 8, 12.5)],
)
def test_gc_content_rounds_halves_up(gc, acgt, percent):
    from bioheaders.metadata import gc_percent

    assert gc_percent(gc, acgt) == percent
    assert round(100 * 1 / 32, 2) == 3.12  # what half-to-even round() gave


def test_gc_content_tie_from_a_fasta():
    # 1 G in 32 bases: 3.125 %, written 3.13.
    assert stats_of(b">c\nG" + b"A" * 31 + b"\n")[0]["gcContent"] == 3.13


@pytest.mark.parametrize("value", ["0000-01-01", "0000-02-29", "2000-02-29"])
def test_year_zero_and_leap_days_are_dates(value):
    # RFC 3339 full-date, the schema's format: date, allows year 0000; Python's
    # date type does not.
    assert build_record(namespace(date_created=value))["dateCreated"] == value


@pytest.mark.parametrize(
    "value", ["1900-02-29", "0001-02-29", "2026-13-01", "2026-00-10"]
)
def test_impossible_dates_are_refused(value):
    with pytest.raises(ValueError, match="is not a date"):
        build_record(namespace(date_created=value))


def test_compressed_yaml_output_combines(tmp_path):
    meta = tmp_path / "m.yaml.gz"
    assert bioheaders("metadata", *REQUIRED_ARGS, "-o", meta).returncode == 0
    fasta = tmp_path / "g.fa"
    fasta.write_bytes(SMALL)
    out = tmp_path / "g.fhr.fa"
    assert bioheaders("combine", meta, fasta, "-o", out).returncode == 0
    assert bioheaders("verify", out).returncode == 0


def test_gc_fraction_warning():
    result = bioheaders("metadata", *REQUIRED_ARGS, "--stat", "gcContent=0.42")
    assert result.returncode == 0
    assert b"gcContent 0.42 means 0.42 percent, not a fraction" in result.stderr


def test_header_limit_counts_the_checksum_line(tmp_path):
    # 14 lines of required fields + synonyms: exactly 10,000 lines without the
    # checksum line combine adds, so the record must be refused here.
    base = bioheaders("metadata", *REQUIRED_ARGS, "--genome-synonym", "s")
    lines = base.stdout.count(b"\n")
    synonyms = 10_000 - lines + 1
    args = [f"--genome-synonym=s{i}" for i in range(synonyms)]
    result = bioheaders("metadata", *REQUIRED_ARGS, *args)
    assert result.stdout.count(b"\n") == 0
    assert result.returncode == 1 and b"exceeds the header limits" in result.stderr
    result = bioheaders(
        "metadata", *REQUIRED_ARGS, *args[:-1], "-o", tmp_path / "m.yaml"
    )
    assert result.returncode == 0
    fasta = tmp_path / "g.fa"
    fasta.write_bytes(SMALL)
    combined = bioheaders(
        "combine", tmp_path / "m.yaml", fasta, "-o", tmp_path / "o.fa"
    )
    assert combined.returncode == 0, combined.stderr


def test_non_utf8_argument_is_refused():
    result = subprocess.run(
        [BIN / "bioheaders", "metadata", *REQUIRED_ARGS[2:], "--genome", b"caf\xe9"],
        capture_output=True,
    )
    assert result.returncode == 1 and b"not valid UTF-8" in result.stderr


def test_format_must_match_a_metadata_extension(tmp_path):
    out = tmp_path / "y.json"
    result = bioheaders("metadata", *REQUIRED_ARGS, "--format", "yaml", "-o", out)
    assert result.returncode == 1 and b"contradicts the extension" in result.stderr
    assert not out.exists()


def test_other_compressions_are_named(tmp_path):
    import bz2
    import lzma

    for name, data in (("bzip2", bz2.compress(SMALL)), ("xz", lzma.compress(SMALL))):
        path = tmp_path / "g.fa"
        path.write_bytes(data)
        result = bioheaders("metadata", *REQUIRED_ARGS, "--stats-from", path)
        assert result.returncode == 1
        assert f"looks {name}-compressed".encode() in result.stderr


def test_future_creation_date_warns():
    args = [a if a != "2024-01-02" else "2999-01-01" for a in REQUIRED_ARGS]
    result = bioheaders("metadata", *args)
    assert result.returncode == 0
    assert b"--date-created 2999-01-01 is in the future" in result.stderr


def test_long_n_runs_across_chunks():
    data = b">a\n" + b"AC" * 10 + b"N" * 3_000_000 + b"\n" + b"G" * 7 + b"N\n"
    for size in (None, 2**20, 4099):
        stats, _ = stats_of(data, size)
        assert stats["numberContigs"] == 2 and stats["N50"] == 20
        assert stats["totalBasePairs"] == 3_000_028
