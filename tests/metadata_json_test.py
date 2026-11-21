"""``bioheaders metadata --json``: the options as a JSON document (issue #197,
specs/005-metadata-json-options)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders.metadata import JSON_OPTIONS, MetadataError, options_from_json

BIN = Path(sys.executable).parent
ADAM = {"name": "Adam Wright", "orcid": "https://orcid.org/0000-0002-5719-4024"}
DAVID = {"name": "David Molik", "orcid": "https://orcid.org/0000-0003-3192-6538"}
REQUIRED = {
    "genome": "Taeniopygia guttata",
    "taxon-name": "Taeniopygia guttata",
    "taxon-id": "59729",
    "version": "1",
    "metadata-author": [ADAM],
    "assembly-author": [DAVID],
    "date-created": "2024-01-02",
    "masking": "not-masked",
}
FASTA = b">s1\nACGTNACGTT\nNNNNNGGCC\n>s2\nnnACGTnn\n"
HOSTILE = 'a\'b \\ "c" $(touch x) ${HOME} `id` > @ : # - {} yes 010 .nan é \t'


def bioheaders(*args, stdin=b""):
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)], input=stdin, capture_output=True
    )


def as_flags(document):
    """The command-line options equivalent to ``document``, written independently
    of the implementation from the documented mapping
    (contracts/metadata-options.md)."""
    argv = []
    for key, value in document.items():
        if value is None or value == []:
            continue
        flag = "--" + key
        if key in ("metadata-author", "assembly-author"):
            for item in value:
                orcid = item.get("orcid")
                argv.append(f"{flag}={item['name']}" + (f" <{orcid}>" if orcid else ""))
        elif key == "assembly-software":
            for item in value:
                text = item["name"]
                if item.get("version") is not None or item.get("uri") is not None:
                    text += "=" + (item.get("version") or "")
                if item.get("uri") is not None:
                    text += "=" + item["uri"]
                argv.append(f"{flag}={text}")
        elif key in ("stat", "extra"):
            for item in value:
                argv.append(f"{flag}={item['key']}={item['value']}")
        elif isinstance(value, list):
            for item in value:
                argv.append(f"{flag}={item}")
        else:
            argv.append(f"{flag}={value}")
    return argv


EVERY_OPTION = {
    **REQUIRED,
    "type": "fhr",
    "genome-synonym": ["zebra finch", "bTaeGut1"],
    "metadata-author": [ADAM, {"name": "Some Org", "orcid": None}],
    "assembly-author": [DAVID, {"name": "VGP"}],
    "voucher-specimen": "specimen 1",
    "accession": "GCA_000001405.29",
    "accession-url": "https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000001405.29",
    "instrument": ["PacBio Revio", "Illumina NovaSeq"],
    "scholarly-article": "10.5281/zenodo.6762550",
    "documentation": "docs",
    "identifier": ["insdc.gca:GCA_000001405.29"],
    "related-link": ["https://example.org/a", "https://example.org/b"],
    "funding": "grant 1",
    "reuse-conditions": "CC-BY-4.0",
    "assembly-software": [
        {"name": "hifiasm", "version": "0.19.8"},
        {"name": "yahs", "version": "1.2", "uri": "https://x.org/?a=b"},
        {"name": "purge_dups"},
        {"name": "bwa", "uri": "https://github.com/lh3/bwa"},
    ],
    "assembly-protocol": "https://example.org/protocol",
    "seqcol-id": "A" * 32,
    "stat": [
        {"key": "readTechnology", "value": "hifi"},
        {"key": "N50", "value": "5"},
        {"key": "gcContent", "value": "41.5"},
    ],
    "extra": [
        {"key": "x-vgp-label", "value": "bTaeGut1"},
        {"key": "x-b", "value": "2"},
    ],
}

CASES = {
    "required only": REQUIRED,
    "every option": EVERY_OPTION,
    "hostile text": {
        **REQUIRED,
        "genome": HOSTILE,
        "genome-synonym": [HOSTILE, "-starts-with-a-dash"],
        "metadata-author": [{"name": HOSTILE.replace(">", "")}],
        "documentation": HOSTILE,
        "funding": "yes",
        "extra": [{"key": "x-note", "value": HOSTILE}],
        "stat": [{"key": "readTechnology", "value": HOSTILE}],
    },
    "nulls and empty lists are absent": {
        **REQUIRED,
        "genome-synonym": [],
        "funding": None,
        "stat": None,
        "assembly-software": [{"name": "x", "version": None, "uri": None}],
    },
    "unicode and tabs": {**REQUIRED, "genome": "Ἀθηνᾶ\tو‍x", "version": "1.0 β"},
    "every masking": {**REQUIRED, "masking": "repeat-masked"},
    "a single optional value": {**REQUIRED, "accession": "GCA_1"},
}


def write(tmp_path, document, name="options.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize("output_format", ["yaml", "json"])
@pytest.mark.parametrize("case", CASES)
def test_output_is_identical_to_the_flags(tmp_path, case, output_format):
    document = CASES[case]
    path = write(tmp_path, document)
    from_json = bioheaders("metadata", "--json", path, "--format", output_format)
    from_flags = bioheaders("metadata", *as_flags(document), "--format", output_format)
    assert from_flags.returncode == 0, from_flags.stderr
    assert from_json.returncode == 0, from_json.stderr
    assert from_json.stdout == from_flags.stdout
    assert from_json.stderr == from_flags.stderr


def test_numbers_give_the_same_output_as_their_text(tmp_path):
    numbers = {
        **REQUIRED,
        "taxon-id": 59729,
        "stat": [{"key": "N50", "value": 5}, {"key": "gcContent", "value": 41.5}],
    }
    texts = {
        **REQUIRED,
        "stat": [{"key": "N50", "value": "5"}, {"key": "gcContent", "value": "41.5"}],
    }
    one = bioheaders("metadata", "--json", write(tmp_path, numbers, "a.json"))
    two = bioheaders("metadata", "--json", write(tmp_path, texts, "b.json"))
    assert one.returncode == 0, one.stderr
    assert one.stdout == two.stdout


def test_stats_from_and_file_output(tmp_path):
    fasta = tmp_path / "genome.fa"
    fasta.write_bytes(FASTA)
    document = {**REQUIRED, "stats-from": str(fasta)}
    out_json = tmp_path / "a.yaml"
    out_flags = tmp_path / "b.yaml"
    one = bioheaders("metadata", "--json", write(tmp_path, document), "-o", out_json)
    two = bioheaders("metadata", *as_flags(document), "-o", out_flags)
    assert one.returncode == two.returncode == 0, one.stderr
    assert out_json.read_bytes() == out_flags.read_bytes()
    assert b"totalBasePairs: 27" in out_json.read_bytes()


def test_stdin(tmp_path):
    content = json.dumps(EVERY_OPTION).encode()
    from_stdin = bioheaders("metadata", "--json", "-", stdin=content)
    from_file = bioheaders("metadata", "--json", write(tmp_path, EVERY_OPTION))
    assert from_stdin.returncode == 0, from_stdin.stderr
    assert from_stdin.stdout == from_file.stdout


def test_stdin_cannot_also_be_the_fasta():
    document = {**REQUIRED, "stats-from": "-"}
    result = bioheaders("metadata", "--json", "-", stdin=json.dumps(document).encode())
    assert result.returncode == 1
    assert b"stats-from cannot also read standard input" in result.stderr


def test_stats_from_stdin_with_a_json_file(tmp_path):
    document = {**REQUIRED, "stats-from": "-"}
    result = bioheaders("metadata", "--json", write(tmp_path, document), stdin=FASTA)
    assert result.returncode == 0, result.stderr
    assert b"totalBasePairs: 27" in result.stdout


@pytest.mark.parametrize(
    "flags",
    [
        ["--genome", "x"],
        ["--type", "fhr"],
        ["--stats-from", "g.fa"],
        ["--stat", "N50=1"],
        ["--extra", "x-a=b"],
        ["--assembly-author", "A", "--masking", "unknown"],
    ],
)
def test_metadata_flags_with_json_are_refused(tmp_path, flags):
    out = tmp_path / "out.yaml"
    result = bioheaders(
        "metadata", "--json", write(tmp_path, REQUIRED), *flags, "-o", out
    )
    assert result.returncode == 1
    assert b"cannot be given with --json" in result.stderr
    assert flags[0].encode() in result.stderr
    assert not out.exists()


def test_output_options_may_accompany_json(tmp_path):
    out = tmp_path / "m.json"
    result = bioheaders("metadata", "--json", write(tmp_path, REQUIRED), "-o", out)
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text())["genome"] == "Taeniopygia guttata"


def test_output_must_differ_from_the_document(tmp_path):
    path = write(tmp_path, REQUIRED, "options.json")
    result = bioheaders("metadata", "--json", path, "-o", path)
    assert result.returncode == 1
    assert b"must differ from the --json document" in result.stderr
    assert json.loads(path.read_text()) == REQUIRED


def test_missing_document(tmp_path):
    result = bioheaders("metadata", "--json", tmp_path / "nope.json")
    assert result.returncode == 1
    assert b"nope.json" in result.stderr


# ---------------------------------------------------------------- refusals


def refused(document, message, tmp_path):
    out = tmp_path / "out.yaml"
    result = bioheaders("metadata", "--json", write(tmp_path, document), "-o", out)
    assert result.returncode == 1, result.stdout
    assert message.encode() in result.stderr, result.stderr
    assert not out.exists()


@pytest.mark.parametrize(
    "change, message",
    [
        # Every check of the flags, in the same words.
        ({"version": None, "assembly-author": []}, "--version, --assembly-author"),
        ({"genome": "a\nb"}, "--genome: control or line-break character"),
        ({"genome": "a\rb"}, "--genome: control or line-break character"),
        ({"documentation": "a b"}, "--documentation: control or line-break"),
        ({"funding": "a\x00b"}, "--funding: control"),
        ({"genome": "a‮b"}, "invisible character U+202E"),
        ({"genome": "\ud800"}, "--genome: the value is not valid UTF-8"),
        ({"genome": "  "}, "--genome: the value is empty"),
        ({"genome": ""}, "missing required value: --genome"),
        ({"funding": ""}, "--funding: the value is empty"),
        (
            {"metadata-author": [{**ADAM, "orcid": ADAM["orcid"][:-1] + "5"}]},
            "fails the ORCID check digit",
        ),
        (
            {"assembly-author": [{"name": "A", "orcid": "0000-0002-5719-4024"}]},
            "is not an ORCID URI",
        ),
        ({"assembly-author": [{"name": "A <b>"}]}, "'<' and '>' are not allowed"),
        (
            {"assembly-author": [{"name": "A <" + ADAM["orcid"] + ">"}]},
            "assembly-author[0].name: '<' and '>' are not allowed",
        ),
        ({"date-created": "2026-02-30"}, "--date-created: '2026-02-30' is not a date"),
        ({"date-created": "2026-2-3"}, "is not an ISO date"),
        ({"taxon-id": "96O6"}, "--taxon-id: '96O6' is not an NCBI taxonomy id"),
        ({"taxon-id": 0}, "--taxon-id: '0' is not"),
        ({"taxon-id": -5}, "--taxon-id: '-5' is not"),
        ({"masking": "masked"}, "--masking: 'masked' is not one of"),
        ({"masking": ""}, "missing required value: --masking"),
        ({"extra": [{"key": "X-a", "value": "1"}]}, "is not an extension key"),
        ({"extra": [{"key": "x-a", "value": "1"}] * 2}, "x-a given more than once"),
        ({"stat": [{"key": "N50", "value": "big"}]}, "is not a non-negative integer"),
        ({"stat": [{"key": "N50", "value": 1.5}]}, "is not a non-negative integer"),
        ({"stat": [{"key": "N50", "value": -1}]}, "is not a non-negative integer"),
        ({"stat": [{"key": "N50", "value": 10**20}]}, "larger than 2^63 - 1"),
        ({"stat": [{"key": "gcContent", "value": 1e300}]}, "non-negative number"),
        ({"stat": [{"key": "n50", "value": "1"}]}, "is not KEY=VALUE with KEY one of"),
        (
            {"stat": [{"key": "N50", "value": "1"}], "stats-from": "g.fa"},
            "--stats-from computes this value",
        ),
        ({"accession-url": "https://x.org"}, "--accession-url needs --accession"),
        ({"related-link": ["javascript:alert(1)"]}, "javascript"),
        ({"type": "fhp"}, "only fhr metadata can be written yet"),
        ({"type": "fht"}, "--type: 'fht' is not one of"),
        # What the JSON format adds.
        ({"date_created": "2024-01-02"}, "unknown key 'date_created'"),
        ({"dateCreated": "2024-01-02"}, "did you mean 'date-created'?"),
        ({"output": "x.yaml"}, "unknown key 'output'"),
        ({"format": "json"}, "unknown key 'format'"),
        ({"json": "x.json"}, "unknown key 'json'"),
        ({"genome": 5}, "genome: expected text, found a number"),
        ({"genome": True}, "genome: expected text, found a boolean"),
        ({"genome": ["a"]}, "genome: expected text, found a list"),
        ({"taxon-id": True}, "taxon-id: expected text, found a boolean"),
        ({"taxon-id": 9606.0}, "taxon-id: expected text, found a number"),
        ({"genome-synonym": "a"}, "genome-synonym: expected a list, found text"),
        ({"genome-synonym": ["a", None]}, "genome-synonym[1]: expected text"),
        ({"metadata-author": ["Adam"]}, "metadata-author[0]: expected an object"),
        ({"metadata-author": [{"nam": "A"}]}, "metadata-author[0]: unknown key 'nam'"),
        ({"metadata-author": [{"orcid": ADAM["orcid"]}]}, "'name' is required"),
        ({"metadata-author": [{"name": None}]}, "'name' is required"),
        ({"assembly-software": [{"name": "a=b"}]}, "'=' is not allowed in the name"),
        (
            {"assembly-software": [{"name": "a", "version": "1=2"}]},
            "'=' is not allowed in the version",
        ),
        ({"assembly-software": [{"name": "a", "version": ""}]}, "the value is empty"),
        ({"assembly-software": [{"name": ""}]}, "is not NAME, NAME=VERSION"),
        ({"stat": [{"key": "N50"}]}, "stat[0]: 'value' is required"),
        ({"stat": [{"key": "N50", "value": True}]}, "expected text, found a boolean"),
        ({"stat": [{"key": "N50", "value": [1]}]}, "expected text, found a list"),
        ({"extra": [{"key": "x-a", "value": 1}]}, "extra[0].value: expected text"),
    ],
)
def test_refusals(tmp_path, change, message):
    refused({**REQUIRED, **change}, message, tmp_path)


def test_only_stat_values_and_the_taxon_id_may_be_numbers():
    options = options_from_json(
        json.dumps({"taxon-id": 9606, "stat": [{"key": "N50", "value": 5}]}).encode()
    )
    assert options == {"taxon_id": "9606", "stat": ["N50=5"]}
    with pytest.raises(MetadataError, match=r"extra\[0\]\.value: expected text"):
        options_from_json(b'{"extra": [{"key": "x-a", "value": 1}]}')


@pytest.mark.parametrize(
    "content, message",
    [
        (b"[]", "expected a JSON object of options, found a list"),
        (b'"genome"', "found text"),
        (b"null", "found null"),
        (b"", "not JSON"),
        (b'{"genome": "a"', "not JSON"),
        (b'{"genome": "a",}', "not JSON"),
        (b'{"genome": "a\nb"}', "not JSON: Invalid control character"),
        (b'{"genome": "a", "genome": "b"}', "key 'genome' appears twice"),
        (b'{"stat": [{"key": "N50", "key": "L50", "value": "1"}]}', "appears twice"),
        (b'{"genome": NaN}', "NaN is not a JSON number"),
        (b'{"genome": -Infinity}', "-Infinity is not a JSON number"),
        (b'\xef\xbb\xbf{"genome": "a"}', "byte order mark"),
        (b'{"genome": "caf\xe9"}', "the document is not UTF-8 (byte 15)"),
        (b"[" * 100000, "nested too deeply"),
        (b'{"genome": "' + b"a" * (1 << 20) + b'"}', "larger than 1 MiB"),
    ],
)
def test_malformed_documents(content, message):
    with pytest.raises(
        MetadataError, match=message.replace("(", r"\(").replace(")", r"\)")
    ):
        options_from_json(content)


def test_malformed_document_through_the_command():
    result = bioheaders("metadata", "--json", "-", stdin=b'{"genome": NaN}')
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"--json: NaN is not a JSON number" in result.stderr


def test_large_document_is_not_read_in_full():
    # More than 1 MiB on stdin: refused after reading 1 MiB + 1 byte.
    content = b'{"genome": "' + b"a" * (4 << 20) + b'"}'
    result = bioheaders("metadata", "--json", "-", stdin=content)
    assert result.returncode == 1
    assert b"larger than 1 MiB" in result.stderr


def test_document_is_checked_before_the_fasta_is_read(tmp_path):
    # The FASTA would be refused (not nucleotides); the document fails first.
    fasta = tmp_path / "g.fa"
    fasta.write_bytes(b">a\n!!!!\n")
    refused(
        {**REQUIRED, "stats-from": str(fasta), "date-created": "today"},
        "is not an ISO date",
        tmp_path,
    )


def test_every_option_has_a_key():
    # Every metadata option of the command line has a key, and every key an
    # option: the help lists the same names.
    result = bioheaders("metadata", "--help")
    help_text = result.stdout.decode()
    for key in JSON_OPTIONS:
        assert f"--{key}" in help_text
    for flag in ("--output", "--format", "--json"):
        assert flag.lstrip("-") not in JSON_OPTIONS


def test_documented_examples_are_valid(tmp_path):
    # The README's document parses; the help's example writes metadata.
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    section = readme.split("#### Options from a JSON document", 1)[1]
    example = section.split("```json\n", 1)[1].split("```", 1)[0]
    options = options_from_json(example.encode())
    assert options["stats_from"] == "genome.fa.gz"
    help_text = bioheaders("metadata", "--help").stdout.decode()
    block = help_text.split("without their dashes, for example\n\n", 1)[1]
    block = block.split("\n\n", 1)[0]
    result = bioheaders("metadata", "--json", "-", stdin=block.encode())
    assert result.returncode == 0, result.stderr
