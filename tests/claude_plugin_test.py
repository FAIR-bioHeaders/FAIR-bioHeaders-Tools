"""The Claude Code plugin in plugins/fair-bioheaders and its marketplace manifest.

The skill's instructions must keep working with this package: its example metadata
must combine and verify with the bundled current schema, and its schema table must
name the bundled schemaVersions.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
PLUGIN = ROOT / "plugins" / "fair-bioheaders"
SKILL = PLUGIN / "skills" / "fair-bioheaders" / "SKILL.md"


def run(*args, cwd=None):
    return subprocess.run(
        [str(arg) for arg in args], capture_output=True, text=True, cwd=cwd
    )


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md has no frontmatter"
    return yaml.safe_load(match.group(1))


def test_manifests_agree():
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    (entry,) = marketplace["plugins"]
    assert entry["name"] == plugin["name"] == "fair-bioheaders"
    assert (ROOT / entry["source"]).resolve() == PLUGIN
    assert marketplace["owner"]["name"]


def test_plugin_version_follows_the_package():
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    with open(ROOT / "pyproject.toml", "rb") as stream:
        version = tomllib.load(stream)["tool"]["poetry"]["version"]
    assert plugin["version"] == version


def test_skill_frontmatter():
    meta = frontmatter(SKILL.read_text())
    assert meta["name"] == "fair-bioheaders"
    assert "FASTA" in meta["description"] and "GFF3" in meta["description"]


def test_skill_schema_table_matches_bundled_schemas():
    text = SKILL.read_text()
    for header, schema in (
        ("FHR", "fhr_schema.json"),
        ("FHP", "fhp_schema.json"),
        ("FHGFF3", "fhgff3_schema.json"),
    ):
        bundled = json.loads((ROOT / "bioheaders" / schema).read_text())
        (version,) = bundled["properties"]["schemaVersion"]["enum"]
        row = next(
            line for line in text.splitlines() if line.startswith(f"| {header} |")
        )
        assert f"`'{version}'`" in row, (header, row)


def example_metadata():
    text = SKILL.read_text()
    match = re.search(r"Example FHR metadata.*?```yaml\n(.*?)```", text, re.S)
    assert match, "SKILL.md has no example FHR metadata block"
    return match.group(1)


def test_skill_example_combines_and_verifies(tmp_path):
    (tmp_path / "metadata.yaml").write_text(example_metadata())
    (tmp_path / "genome.fa").write_bytes(b">chr1 test\nACGTACGTAC\n")
    combined = run(
        BIN / "bioheaders",
        "combine",
        "metadata.yaml",
        "genome.fa",
        "-o",
        "genome.fhr.fa",
        cwd=tmp_path,
    )
    assert combined.returncode == 0, combined.stderr
    verified = run(BIN / "bioheaders", "verify", "genome.fhr.fa", cwd=tmp_path)
    assert verified.returncode == 0, verified.stderr
    assert "Checksum verified." in verified.stdout
    stripped = run(
        BIN / "bioheaders", "strip", "genome.fhr.fa", "genome.plain.fa", cwd=tmp_path
    )
    assert stripped.returncode == 0, stripped.stderr
    assert (tmp_path / "genome.plain.fa").read_bytes() == b">chr1 test\nACGTACGTAC\n"
