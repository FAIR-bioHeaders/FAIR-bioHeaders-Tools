"""``bioheaders faidx``: samtools-compatible .fai and .gzi indexes (issue #108).

The samtools comparisons run when ``samtools`` and ``bgzip`` are on PATH and the
pysam ones when pysam is installed; CI installs both.
"""

import gzip
import io
import json
import os
import random
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from bioheaders import fhr
from bioheaders.cli import BgzfWriter, combine, strip_header
from bioheaders.faidx import GZIP_ERROR, MAX_FAI_LINE, build_fai, build_index

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
SAMTOOLS = shutil.which("samtools")
BGZIP = shutil.which("bgzip")
# CI sets FHR_REQUIRE_FAIDX_TOOLS so that the comparisons cannot be skipped there.
REQUIRED = bool(os.environ.get("FHR_REQUIRE_FAIDX_TOOLS"))
needs_samtools = pytest.mark.skipif(
    not (SAMTOOLS and BGZIP) and not REQUIRED,
    reason="samtools and bgzip are not installed",
)


def fai(data, size=None):
    chunks = [data] if size is None else chunked(data, size)
    return build_fai(chunks)[0]


def chunked(data, size):
    return [data[i : i + size] for i in range(0, len(data), size)]


def bgzf(data, block=None):
    output = io.BytesIO()
    writer = BgzfWriter(output)
    for piece in chunked(data, block) if block else [data]:
        writer.write(piece)
    writer.close()
    return output.getvalue()


def bioheaders_faidx(*args):
    return subprocess.run(
        [str(BIN / "bioheaders"), "faidx", *map(str, args)], capture_output=True
    )


def headed(body, metadata="examples/example.fhr.json"):
    data = json.loads((ROOT / metadata).read_text(encoding="utf-8"))
    return combine(fhr(**data), body, "fasta")


# Expected .fai lines worked out from htslib's fai_build_core rules.


def test_records_follow_samtools_rules():
    data = b">chr1 description\nACGTA\nCGTAC\nGT\n>chr2\tx\nAC\n"
    assert fai(data) == b"chr1\t12\t18\t5\t6\nchr2\t2\t41\t2\t3\n"


def test_crlf_counts_the_carriage_return_in_the_width():
    data = b">a\r\nACGT\r\nAC\r\n\r\n>b\r\nA\r\n"
    assert fai(data) == b"a\t6\t4\t4\t6\nb\t1\t20\t1\t3\n"


def test_last_line_without_terminator_and_unwrapped_record():
    assert fai(b">a\nACGT\nACGT") == b"a\t8\t3\t4\t5\n"
    assert fai(b">  a  b\n" + b"A" * 1000) == b"a\t1000\t8\t1000\t1001\n"


def test_offsets_include_the_header_and_leading_comments():
    body = b">ctg1 x\nACGTACGT\nACG\n>ctg2\nTTTT\n"
    data = headed(body)
    lead = len(data) - len(body)
    assert fai(data) == b"ctg1\t11\t%d\t8\t9\nctg2\t4\t%d\t4\t5\n" % (
        lead + 8,
        lead + 27,
    )
    commented = b"; an ordinary comment\n\n" + data
    assert fai(commented) == fai(data).replace(
        b"\t%d\t" % (lead + 8), b"\t%d\t" % (lead + 8 + 23)
    ).replace(b"\t%d\t" % (lead + 27), b"\t%d\t" % (lead + 27 + 23))


def test_header_lines_are_the_ones_strip_removes():
    body = b">ctg\nAC\n"
    data = headed(body)
    assert strip_header(data, "fasta") == body
    assert fai(data) == b"ctg\t2\t%d\t2\t3\n" % (len(data) - len(body) + 5)


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 64])
def test_chunk_boundaries_do_not_change_the_index(size):
    data = headed(
        b"> s1 d\r\nAC GT\r\nACGTA\r\nA\r\n\r\n>s2\nACGTACGT\nACGTACGT\nACG\n"
        b">s3\n" + b"ACGTA\n" * 40 + b"AC\n>s4\n>s5\nNNNN"
    )
    assert fai(data, size) == fai(data)


def test_records_without_sequence_are_omitted_with_a_warning():
    index, warnings = build_fai([b">a\n>b\nAC\n>c\n\n>d\nA\n"])
    assert index == b"b\t2\t6\t2\t3\nd\t1\t16\t1\t2\n"
    assert len(warnings) == 2 and "'a'" in warnings[0] and "'c'" in warnings[1]
    # A lone ">" at the very end is ignored, as htslib does.
    assert fai(b">a\nAC\n>") == b"a\t2\t3\t2\t3\n"


@pytest.mark.parametrize(
    "data, message",
    [
        (b"", "No FASTA records to index"),
        (b"\n\n; only a comment\n", "No FASTA records to index"),
        (b">a\nACGT\nACGTA\n", "Different line length in sequence 'a' at line 3"),
        (b">a\nACGT\nAC\nACGT\n", 'unexpected "A" at line 4'),
        (b">a\nAC\n>a\nGT\n", "Duplicate sequence name 'a' at line 3"),
        (b">a\nAC\n>b\n", "File truncated at line 4"),
        (b">a\nAC\n>b x", "File truncated"),
        (b">a\nAC\n>b", "The last entry 'b' has no sequence"),
        (b"\r>a\nAC\n", "carriage return not followed by new line at line 1"),
        (b"ACGT\n>a\nAC\n", 'unexpected "A" at line 1'),
        (b"@r\nACGT\n+\nIIII\n", "FASTQ is not supported"),
        (b">a\nAC\n;~late: header\n", "FHR header line after sequence data"),
    ],
)
def test_errors(data, message):
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        build_fai([data])


def test_header_only_file_has_no_records():
    data = headed(b"")
    with pytest.raises(ValueError, match="No FASTA records"):
        build_fai([data])


def test_header_limits_apply():
    data = b";~x: " + b"a" * (2**20) + b"\n>a\nAC\n"
    with pytest.raises(ValueError, match="size limit"):
        build_fai(chunked(data, 2**16))


def test_name_too_long_for_htslib_to_read_back():
    with pytest.raises(ValueError, match="too long for a .fai index"):
        build_fai([b">" + b"n" * (MAX_FAI_LINE + 1) + b"\nAC\n"])
    with pytest.raises(ValueError, match="too long for a .fai index"):
        build_fai([b">" + b"n" * (MAX_FAI_LINE - 5) + b"\nAC\n"])


def test_bgzf_index_lists_every_block_after_the_first():
    body = headed(b">a\n" + b"ACGTACGTAC\n" * 30000)
    compressed = bgzf(body)
    index, gzi, _ = build_index(io.BytesIO(compressed))
    assert index == fai(body)
    count = struct.unpack("<Q", gzi[:8])[0]
    pairs = [struct.unpack("<QQ", gzi[8 + 16 * i : 24 + 16 * i]) for i in range(count)]
    assert len(gzi) == 8 + 16 * count and count == len(body) // 0xFF00
    assert [u for _, u in pairs] == [0xFF00 * (i + 1) for i in range(count)]
    for address, offset in pairs:  # Each pair starts a block of those bytes.
        member = gzip.decompress(compressed[address:])
        assert member == body[offset:]


def test_plain_gzip_and_corrupt_bgzf_are_errors():
    data = b">a\nACGT\n"
    with pytest.raises(ValueError, match=GZIP_ERROR):
        build_index(io.BytesIO(gzip.compress(data)))
    with pytest.raises(ValueError, match=GZIP_ERROR):
        build_index(io.BytesIO(bgzf(data)[:-28] + gzip.compress(data)))
    broken = bytearray(bgzf(data))
    broken[20] ^= 0xFF
    with pytest.raises(ValueError, match="Invalid BGZF block"):
        build_index(io.BytesIO(bytes(broken)))
    with pytest.raises(ValueError, match="Truncated BGZF block"):
        build_index(io.BytesIO(bgzf(data)[:30]))


# The installed command.


def test_command_writes_fai_and_gzi_next_to_the_input(tmp_path):
    body = b">a\nACGT\n"
    data = headed(body)
    plain = tmp_path / "x.fhr.fa"
    plain.write_bytes(data)
    result = bioheaders_faidx(plain)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"" and result.stderr == b""
    assert (tmp_path / "x.fhr.fa.fai").read_bytes() == fai(data)
    assert not (tmp_path / "x.fhr.fa.gzi").exists()
    compressed = tmp_path / "x.fhr.fa.gz"
    compressed.write_bytes(bgzf(data))
    assert bioheaders_faidx(compressed).returncode == 0
    assert (tmp_path / "x.fhr.fa.gz.fai").read_bytes() == fai(data)
    assert (tmp_path / "x.fhr.fa.gz.gzi").read_bytes() == struct.pack("<Q", 0)
    result = bioheaders_faidx(
        compressed, "-o", tmp_path / "o.fai", "--gzi", tmp_path / "o.gzi"
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "o.fai").read_bytes() == fai(data)
    assert (tmp_path / "o.gzi").read_bytes() == struct.pack("<Q", 0)
    result = bioheaders_faidx(plain, "-o", "-")
    assert result.stdout == fai(data)


@pytest.mark.parametrize(
    "data, options, message",
    [
        (gzip.compress(b">a\nAC\n"), [], GZIP_ERROR),
        (b">a\nAC\nACG\n", [], "Different line length"),
        (b">a\nAC\n>a\nAC\n", [], "Duplicate sequence name"),
        (b"", [], "No FASTA records"),
        (b">a\nAC\n", ["--gzi", "x.gzi"], "--gzi applies only to BGZF input"),
    ],
)
def test_command_errors_write_nothing(tmp_path, data, options, message):
    path = tmp_path / "in.fa"
    path.write_bytes(data)
    result = bioheaders_faidx(path, *options)
    assert result.returncode == 1
    assert result.stderr.decode().startswith("FHR: ")
    assert message in result.stderr.decode()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.fa"]


def test_command_refuses_to_overwrite_the_input_or_read_stdin(tmp_path):
    path = tmp_path / "in.fa.gz"
    data = bgzf(b">a\nAC\n")
    path.write_bytes(data)
    for options in (["-o", path], ["--gzi", path], ["-o", "same", "--gzi", "same"]):
        result = bioheaders_faidx(path, *options)
        assert result.returncode == 1 and b"must differ" in result.stderr, options
    assert path.read_bytes() == data
    result = bioheaders_faidx("-")
    assert result.returncode == 1 and b"regular file" in result.stderr
    result = bioheaders_faidx(tmp_path / "missing.fa")
    assert result.returncode == 1 and result.stderr.startswith(b"FHR: ")


def test_command_header_only_file_is_an_error(tmp_path):
    path = tmp_path / "h.fa"
    path.write_bytes(headed(b""))
    result = bioheaders_faidx(path)
    assert result.returncode == 1 and b"No FASTA records" in result.stderr


# Comparison with samtools faidx.


def varied_fastas(seed, count):
    """Header-less FASTA files: fixed cases, then generated ones."""
    yield from [
        b">chr1\nACGT\nACGT\nAC\n>chr2\nGGGG\n",
        b">a\r\nACGT\r\nACGT\r\nA\r\n>b desc\r\nNN\r\n",
        b">unwrapped some description\n" + b"ACGT" * 5000 + b"\n",
        b">n" + b"x" * 500 + b" a long description " * 20 + b"\nACGTN\nAC",
        b"\n\n>blank_lines_before\nAC\n\n\n>after_blank\nGT\n",
        b"\r\n>crlf_blank_first\r\nAC\r\n\r\n>z\r\nA",
        b">  leading_space\tx\nacgtNNNNRYKM\nacg\n",
        b">empty_middle\n>b\nAC\n",
        b">a\nAC GT\nA-C*\n",
        b">a\nACGT\nACG\nACGT\n",
        b">a\nACGT\nACGTA\n",
        b"\r>a\nAC\n",
        b">a\nAC\n>b\n",
        b">a\nAC\n>",
        b"",
        b"x\n>a\nAC\n",
    ]
    rng = random.Random(seed)
    for _ in range(count):
        newline = rng.choice([b"\n", b"\n", b"\r\n"])
        parts = [newline * rng.randint(0, 2) if rng.random() < 0.2 else b""]
        for record in range(rng.randint(1, 6)):
            name = rng.choice([b"chr", b"scaffold_", b"n" * rng.randint(1, 200)])
            description = rng.choice([b"", b" desc", b"\tA=1 B=2", b" "])
            gap = b" " if rng.random() < 0.1 else b""
            parts.append(b">" + gap + name + b"%d" % record + description + newline)
            length = rng.choice([0, 1, rng.randint(2, 60), rng.randint(61, 3000)])
            width = rng.choice([60, 61, 70, 80, 1, 7, max(length, 1)])
            sequence = bytes(rng.choice(b"ACGTNacgtn") for _ in range(length))
            lines = [sequence[i : i + width] for i in range(0, length, width)]
            if lines and rng.random() < 0.05:  # An inconsistent line.
                lines[rng.randrange(len(lines))] += b"A"
            parts.append(newline.join(lines))
            if lines and rng.random() < 0.85:
                parts.append(newline)
            if rng.random() < 0.15:
                parts.append(newline)
        yield b"".join(parts)


def samtools_index(path):
    assert SAMTOOLS and BGZIP, "samtools and bgzip are required"
    for suffix in (".fai", ".gzi"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    result = subprocess.run([SAMTOOLS, "faidx", str(path)], capture_output=True)
    if result.returncode:
        return None, None
    gzi = Path(f"{path}.gzi")
    return (
        Path(f"{path}.fai").read_bytes(),
        gzi.read_bytes() if gzi.exists() else None,
    )


def ours(path):
    try:
        with open(path, "rb") as stream:
            index, gzi, _ = build_index(stream, str(path))
    except ValueError:
        return None, None
    return index, gzi


@needs_samtools
def test_byte_identical_to_samtools_without_a_header(tmp_path):
    compared = indexed = 0
    rng = random.Random(108)
    for number, data in enumerate(varied_fastas(108, 200)):
        plain = tmp_path / f"t{number}.fa"
        plain.write_bytes(data)
        # Small chunks must not change the index.
        try:
            whole = fai(data)
        except ValueError:
            whole = None
        if whole is not None:
            assert fai(data, rng.randint(1, 50)) == whole
        variants = [plain]
        compressed = tmp_path / f"t{number}.fa.gz"
        subprocess.run([BGZIP, "-c", str(plain)], stdout=compressed.open("wb"))
        variants.append(compressed)
        if number % 4 == 0:  # The toolkit's own BGZF writer, in small blocks.
            small = tmp_path / f"t{number}.small.fa.gz"
            small.write_bytes(bgzf(data, block=rng.randint(100, 5000)))
            variants.append(small)
        for path in variants:
            expected = samtools_index(path)
            assert ours(path) == expected, (path, data[:200])
            compared += 1
            indexed += expected[0] is not None
    print(f"compared {compared} indexes with samtools, {indexed} accepted")
    assert compared >= 400 and indexed >= 300


@needs_samtools
def test_duplicate_names_differ_from_samtools_only_by_failing(tmp_path):
    path = tmp_path / "dup.fa"
    path.write_bytes(b">a\nAC\n>a\nGT\n")
    assert samtools_index(path)[0] == b"a\t2\t3\t2\t3\n"
    assert ours(path) == (None, None)


def record_bodies(rng, protein=False):
    alphabet = b"ACDEFGHIKLMNPQRSTVWY" if protein else b"ACGTNacgt"
    bodies = []
    for newline in (b"\n", b"\r\n"):
        parts = []
        for record in range(5):
            length = rng.choice([1, 37, 500, 4000, 70000])
            width = rng.choice([60, 61, 80, length])
            sequence = bytes(rng.choice(alphabet) for _ in range(length))
            lines = [sequence[i : i + width] for i in range(0, length, width)]
            parts.append(b">rec%d some description%s" % (record, newline))
            parts.append(newline.join(lines) + newline)
        bodies.append(b"".join(parts))
    return bodies


def regions_for(index, rng, per_record=50):
    regions = []
    for line in index.splitlines():
        name, length = line.split(b"\t")[:2]
        length = int(length)
        for _ in range(per_record):
            start = rng.randint(1, length)
            end = rng.randint(start, min(length, start + rng.choice([0, 10, 1000])))
            regions.append((name.decode(), start, end))
        regions.append((name.decode(), 1, length))
    return regions


def headed_cases(tmp_path, rng):
    """(headed path, stripped path) pairs: FHR and FHP, plain and BGZF."""
    cases = []
    for kind, metadata, protein in (
        ("fhr", "examples/example.fhr.json", False),
        ("fhp", "examples/fhp/minimal-predicted.fhp.json", True),
    ):
        for number, body in enumerate(record_bodies(rng, protein)):
            data = headed(body, metadata)
            for compressed in (False, True):
                suffix = ".fa.gz" if compressed else ".fa"
                path = tmp_path / f"{kind}{number}{suffix}"
                stripped = tmp_path / f"{kind}{number}.stripped{suffix}"
                path.write_bytes(bgzf(data) if compressed else data)
                stripped.write_bytes(bgzf(body) if compressed else body)
                result = bioheaders_faidx(path)
                assert result.returncode == 0, result.stderr
                cases.append((path, stripped))
    return cases


@needs_samtools
def test_samtools_regions_on_headed_files_match_the_stripped_file(tmp_path):
    rng = random.Random(1080)
    for path, stripped in headed_cases(tmp_path, rng):
        assert samtools_index(stripped)[0] is not None
        regions = regions_for(Path(f"{stripped}.fai").read_bytes(), rng)
        listing = tmp_path / "regions.txt"
        listing.write_text("".join(f"{n}:{s}-{e}\n" for n, s, e in regions))

        def fetch(target):
            result = subprocess.run(
                [SAMTOOLS, "faidx", str(target), "-r", str(listing)],
                capture_output=True,
            )
            assert result.returncode == 0, result.stderr
            return result.stdout

        assert fetch(path) == fetch(stripped)
        # Without a region samtools rebuilds the index and still rejects the
        # header; the pre-built index is left in place.
        index = Path(f"{path}.fai").read_bytes()
        result = subprocess.run([SAMTOOLS, "faidx", str(path)], capture_output=True)
        assert result.returncode != 0 and b"unexpected" in result.stderr
        assert Path(f"{path}.fai").read_bytes() == index


def test_pysam_fetch_on_headed_files_matches_the_stripped_file(tmp_path):
    if REQUIRED:
        import pysam
    else:
        pysam = pytest.importorskip("pysam")
    rng = random.Random(1081)
    for path, stripped in headed_cases(tmp_path, rng):
        # pysam builds the stripped file's index itself; ours is used for path.
        with (
            pysam.FastaFile(str(path)) as ours_file,
            pysam.FastaFile(str(stripped)) as plain_file,
        ):
            assert ours_file.references == plain_file.references
            assert ours_file.lengths == plain_file.lengths
            index = b"".join(
                b"%s\t%d\n" % (name.encode(), length)
                for name, length in zip(plain_file.references, plain_file.lengths)
            )
            for name, start, end in regions_for(index, rng):
                assert ours_file.fetch(name, start - 1, end) == plain_file.fetch(
                    name, start - 1, end
                )
