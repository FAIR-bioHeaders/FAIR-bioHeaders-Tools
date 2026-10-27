"""The bioheaders package and command, and the deprecated fhr names."""

import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import bioheaders
import bioheaders.cli
from bioheaders import SCHEMA, fhr
from bioheaders.cli import checksum, combine, strip_header

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
BODIES = {"fasta": b">ctg\r\nACGT\r\n; comment\n", "gfa": b"S\tctg\tACGT\r\n"}
# The fhr-* command that matches each bioheaders subcommand of a sequence kind.
SEQUENCE_COMMANDS = {"combine": "combine", "strip": "strip", "verify": "validate"}


@pytest.fixture(scope="module")
def metadata():
    return json.loads((ROOT / "examples/example.fhr.json").read_text())


def run(*args, stdin=b"", cwd=None, env=None):
    return subprocess.run(
        [str(arg) for arg in args],
        input=stdin,
        capture_output=True,
        cwd=cwd,
        env=env,
    )


def bioheaders_command(*args, **options):
    return run(BIN / "bioheaders", *args, **options)


def python(code):
    return run(sys.executable, "-c", code, cwd=ROOT / "tests")


def test_library_round_trip_through_bioheaders(metadata):
    for kind, body in BODIES.items():
        combined = combine(fhr(**metadata), body, kind)
        assert strip_header(combined, kind) == body
        data = fhr()
        getattr(data, "input_" + kind)(combined)
        data.fhr_validate()
        assert data.checksum == checksum(combined, kind)
    assert SCHEMA["$id"] == bioheaders.ITEM_TYPE


def test_schema_copies_are_identical():
    packaged = (ROOT / "bioheaders/fhr_schema.json").read_bytes()
    assert (ROOT / "fhr_schema.json").read_bytes() == packaged
    assert (ROOT / "fhr/fhr_schema.json").read_bytes() == packaged


def test_fhr_is_bioheaders_and_warns_once():
    result = python(
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import fhr\n"
        "    import fhr.cli\n"
        "    from fhr import fhr as metadata_class, SCHEMA\n"
        "    from fhr.cli import checksum, combine, strip_header, BgzfWriter\n"
        "    import fhr as again\n"
        "import bioheaders, bioheaders.cli\n"
        "assert fhr is again is bioheaders and fhr.cli is bioheaders.cli\n"
        "assert metadata_class is bioheaders.fhr and checksum is bioheaders.cli.checksum\n"
        "print(len(caught), caught[0].category.__name__, caught[0].filename)\n"
        "print(caught[0].message)\n"
    )
    assert result.returncode == 0, result.stderr
    count, category, filename = result.stdout.decode().splitlines()[0].split()
    assert (count, category, filename) == ("1", "DeprecationWarning", "<string>")
    assert "bioheaders" in result.stdout.decode().splitlines()[1]


def test_fhr_from_import_alone_and_monkeypatching_reach_bioheaders():
    result = python(
        "import warnings\n"
        "warnings.simplefilter('ignore')\n"
        "from fhr.cli import read_metadata\n"
        "import fhr, bioheaders\n"
        "fhr.MAX_HEADER_BYTES = 7\n"
        "assert bioheaders.MAX_HEADER_BYTES == 7\n"
        "assert read_metadata.__module__ == 'bioheaders.cli'\n"
    )
    assert result.returncode == 0, result.stderr


def test_bioheaders_import_does_not_warn():
    result = run(
        sys.executable,
        "-W",
        "error",
        "-c",
        "import bioheaders, bioheaders.cli",
        cwd=ROOT / "tests",
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""


def test_commands_never_print_the_deprecation(tmp_path):
    env = dict(os.environ, PYTHONWARNINGS="error")
    sequence = tmp_path / "sequence.fasta"
    sequence.write_bytes(BODIES["fasta"])
    metadata = ROOT / "examples/example.fhr.yaml"
    combined = tmp_path / "combined.fasta"
    commands = [
        [BIN / "fhr-fasta-combine", metadata, sequence, "-o", combined],
        [BIN / "fhr-fasta-validate", combined],
        [BIN / "fhr-validate", combined],
        [BIN / "bioheaders", "verify", combined],
        [sys.executable, ROOT / "fasta/fhr_fasta_validate.py", combined],
        [sys.executable, ROOT / "fhr_validate.py", combined],
    ]
    for args in commands:
        result = run(*args, cwd=tmp_path, env=env)
        assert result.returncode == 0, (args, result.stderr)
        assert result.stderr == b"", args


def test_installed_bioheaders_command(tmp_path):
    result = bioheaders_command("--version", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode().strip() == bioheaders.__version__ == "0.8.3"
    result = run(sys.executable, "-m", "bioheaders", "--version", cwd=tmp_path)
    assert result.stdout.decode().strip() == "0.8.3"
    result = bioheaders_command("--help", cwd=tmp_path)
    for name in ("convert", "validate", "combine", "strip", "verify", "checksum"):
        assert name in result.stdout.decode()
    result = bioheaders_command(cwd=tmp_path)
    assert result.returncode == 2
    assert b"required" in result.stderr


def test_convert_and_validate_match_fhr_commands(tmp_path):
    source = ROOT / "examples/example.fhr.yaml"
    for extension in ("json", "fasta", "gfa", "html", "jsonld"):
        new, old = tmp_path / f"new.{extension}", tmp_path / f"old.{extension}"
        assert bioheaders_command("convert", source, new).returncode == 0
        assert run(BIN / "fhr-convert", source, old).returncode == 0
        assert new.read_bytes() == old.read_bytes()
        validated = bioheaders_command("validate", new)
        assert validated.returncode == 0, validated.stderr
        assert validated.stdout == run(BIN / "fhr-validate", old).stdout
    piped = bioheaders_command(
        "convert", "-", "-", "--from", "yaml", "--to", "json", stdin=source.read_bytes()
    )
    assert piped.stdout == (tmp_path / "new.json").read_bytes()
    assert bioheaders_command("validate", "-", stdin=b"{}").returncode == 1
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"genome": "missing everything"}')
    new, old = bioheaders_command("validate", invalid), run(
        BIN / "fhr-validate", invalid
    )
    assert new.returncode == old.returncode == 1
    assert new.stderr == old.stderr


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
@pytest.mark.parametrize("suffix", ["", ".gz", ".bgz"])
def test_sequence_subcommands_match_fhr_commands(tmp_path, kind, suffix):
    metadata = ROOT / "examples/example.fhr.yaml"
    sequence = tmp_path / f"sequence.{kind}{suffix}"
    body = BODIES[kind]
    sequence.write_bytes(gzip.compress(body) if suffix else body)
    for tool in ("new", "old"):
        (tmp_path / tool).mkdir()
        shutil.copy(sequence, tmp_path / tool)
    local = sequence.name

    def both(command, *args):
        new = bioheaders_command(command, *args, cwd=tmp_path / "new")
        old = run(
            BIN / f"fhr-{kind}-{SEQUENCE_COMMANDS[command]}",
            *args,
            cwd=tmp_path / "old",
        )
        assert new.returncode == old.returncode
        assert (new.stdout, new.stderr) == (old.stdout, old.stderr)
        return new

    # Default output name, compression, and checksum all match fhr-* output.
    assert both("combine", metadata, local).returncode == 0
    combined = f"sequence.fhr.{kind}{suffix}"
    new, old = tmp_path / "new" / combined, tmp_path / "old" / combined
    plain = gzip.decompress(new.read_bytes()) if suffix else new.read_bytes()
    assert plain == (gzip.decompress(old.read_bytes()) if suffix else old.read_bytes())
    assert both("verify", combined).stdout == b"Checksum verified.\n"
    assert both("strip", combined).stdout == body
    assert both("strip", combined, f"stripped.{kind}").returncode == 0
    assert (tmp_path / "new" / f"stripped.{kind}").read_bytes() == body
    alias = bioheaders_command("checksum", new)
    assert alias.returncode == 0, alias.stderr
    new.write_bytes(plain.replace(b"ACGT", b"ACGA"))
    old.write_bytes(plain.replace(b"ACGT", b"ACGA"))
    failed = both("verify", combined)
    assert failed.returncode == 1
    assert failed.stderr == b"FHR: Checksum verification failed\n"


@pytest.mark.parametrize("kind", ["fasta", "gfa"])
def test_sequence_type_option(tmp_path, metadata, kind):
    body = BODIES[kind]
    combined = combine(fhr(**metadata), body, kind)
    # Standard streams need --type.
    result = bioheaders_command("verify", "-", stdin=combined)
    assert result.returncode == 1
    assert b"--type" in result.stderr
    result = bioheaders_command("verify", "-", "--type", kind, stdin=combined)
    assert result.returncode == 0, result.stderr
    result = bioheaders_command("strip", "-", "--type", kind, stdin=combined)
    assert result.stdout == body
    metadata_path = ROOT / "examples/example.fhr.json"
    result = bioheaders_command(
        "combine", metadata_path, "-", "--type", kind, stdin=body
    )
    assert result.stdout == combined
    # --type also overrides or replaces a file extension.
    other = tmp_path / "sequence.txt"
    other.write_bytes(combined)
    assert bioheaders_command("verify", other).returncode == 1
    result = bioheaders_command("verify", other, "--type", kind)
    assert result.returncode == 0, result.stderr
    # Metadata files are not sequence files.
    result = bioheaders_command("strip", metadata_path)
    assert result.returncode == 1
    assert b"Expected a FASTA, GFA or GFF3 file" in result.stderr
    result = bioheaders_command("strip", other, "--type", "json")
    assert result.returncode == 2


def _toml_section(text, name):
    section = text.split(f"\n[{name}]\n", 1)[1].split("\n[", 1)[0]
    return [line for line in section.splitlines() if line and line[0] != "#"]


def test_compat_distribution_matches():
    main = (ROOT / "pyproject.toml").read_text()
    compat = (ROOT / "compat/fhr/pyproject.toml").read_text()
    version = bioheaders.__version__
    assert f'\nversion = "{version}"\n' in main
    assert f'\nversion = "{version}"\n' in compat
    assert f'\ndependencies = ["fair-bioheaders=={version}"]\n' in compat
    commands = [
        line for line in _toml_section(main, "tool.poetry.scripts") if "fhr-" in line
    ]
    assert len(commands) == 11
    assert _toml_section(compat, "project.scripts") == commands
