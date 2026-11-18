"""The Galaxy "FAIR-bioHeaders metadata" wrapper keeps user text out of the shell.

Its text parameters are not sanitized (so quotes, backslashes and $ reach
bioheaders unchanged); that is safe only because the command holds nothing but
Galaxy-controlled paths and the values are read from the inputs configfile by
fair_bioheaders_metadata.py, which runs bioheaders without a shell.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parents[1] / "galaxy" / "tools" / "fair_bioheaders"
TOOL_XML = TOOL_DIR / "fair_bioheaders_metadata.xml"
HELPER = TOOL_DIR / "fair_bioheaders_metadata.py"

# The only Cheetah variables the command may use: all are Galaxy-controlled paths.
ALLOWED = {"__tool_directory__", "inputs", "output"}


def load_helper():
    spec = importlib.util.spec_from_file_location("fair_bioheaders_metadata", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_helper()


def test_command_uses_only_galaxy_paths():
    root = ET.parse(TOOL_XML).getroot()
    command = root.find("command").text
    assert "#" not in command, "no Cheetah directives in the command"
    names = set(re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", command))
    assert names == ALLOWED, f"the command may only use {sorted(ALLOWED)}"
    assert "@" not in command, "no macro tokens in the command"
    configfiles = root.find("configfiles")
    assert [child.tag for child in configfiles] == ["inputs"]
    assert configfiles.find("inputs").get("name") == "inputs"
    assert configfiles.find("inputs").get("data_style") == "paths"


def test_unsanitized_parameters_never_reach_the_command():
    # Any parameter (sanitized or not) would fail the test above; this one names
    # the unsanitized ones, so that a failure says what would leak.
    text = TOOL_XML.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    command = root.find("command").text
    names = {param.get("name") for param in root.iter("param")}
    names |= {
        param.get("name")
        for macro in root.iter("xml")
        for param in macro.iter("param")
        if param.get("name")
    }
    names |= {"value", "name", "orcid"}
    leaked = {
        name
        for name in names
        if name and name not in ALLOWED and re.search(rf"\${{?{name}\b", command)
    }
    assert not leaked


NASTY = "a\\'b \\\\ \"c\" $(touch injected) ${HOME} `id` $'\\x41' %s; | & \\"


def params(**overrides):
    record = {
        "genome": NASTY,
        "genome_synonyms": [{"value": "-x"}],
        "taxon_name": "Homo sapiens",
        "taxon_id": 9606,
        "assembly_version": "1",
        "metadata_authors": [
            {"name": "O'Neil", "orcid": "https://orcid.org/0000-0002-1825-0097"}
        ],
        "assembly_authors": [{"name": "$(id)", "orcid": None}],
        "date_created": "2026-01-02",
        "masking": "unknown",
        "statistics": {"compute": "no"},
        "optional_fields": {
            "instruments": [],
            "assembly_software": [
                {"name": "a\\b", "software_version": None, "uri": "https://x.org/?a=b"}
            ],
            "assembly_protocol": None,
            "documentation": "",
            "accession": None,
            "accession_url": None,
            "identifiers": [],
            "reuse_conditions": None,
            "related_links": [],
            "voucher_specimen": None,
            "scholarly_article": None,
            "funding": "`x`",
            "seqcol_id": None,
            "stats": [{"key": "readTechnology", "value": "hi\\fi"}],
            "extras": [{"key": "x-note", "value": "a: b # c"}],
        },
        "output_format": "json",
    }
    record.update(overrides)
    return record


def test_build_command_passes_values_unchanged():
    command = helper.build_command(params(), "/out/x.dat")
    assert command == [
        "bioheaders",
        "metadata",
        "--genome=" + NASTY,
        "--genome-synonym=-x",
        "--taxon-name=Homo sapiens",
        "--taxon-id=9606",
        "--version=1",
        "--metadata-author=O'Neil <https://orcid.org/0000-0002-1825-0097>",
        "--assembly-author=$(id)",
        "--date-created=2026-01-02",
        "--masking=unknown",
        "--assembly-software=a\\b==https://x.org/?a=b",
        "--funding=`x`",
        "--stat=readTechnology=hi\\fi",
        "--extra=x-note=a: b # c",
        "--format=json",
        "--output=/out/x.dat",
    ]


def test_stats_from_path():
    command = helper.build_command(
        params(statistics={"compute": "yes", "fasta": "/data/a.dat"}), "o"
    )
    assert "--stats-from=/data/a.dat" in command


@pytest.mark.parametrize(
    "bad", ["a\nb", "a\rb", "a\x00b", "a\x1bb", "a\x85b", "a\u2028b", "a\u2029b"]
)
def test_control_characters_are_refused(bad):
    with pytest.raises(helper.InputError, match="control characters"):
        helper.build_command(params(genome=bad), "o")
    extras = [{"key": "x-a", "value": bad}]
    optional = dict(params()["optional_fields"], extras=extras)
    with pytest.raises(helper.InputError):
        helper.build_command(params(optional_fields=optional), "o")


def test_tab_is_allowed():
    assert "--genome=a\tb" in helper.build_command(params(genome="a\tb"), "o")


@pytest.mark.parametrize(
    "software",
    [
        {"name": "a=b", "software_version": None, "uri": None},
        {"name": "a", "software_version": "1=2", "uri": None},
    ],
)
def test_equals_in_software_is_refused(software):
    optional = dict(params()["optional_fields"], assembly_software=[software])
    with pytest.raises(helper.InputError, match="cannot contain ="):
        helper.build_command(params(optional_fields=optional), "o")


@pytest.mark.skipif(shutil.which("bioheaders") is None, reason="bioheaders not on PATH")
def test_round_trip(tmp_path):
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps(params()), encoding="utf-8")
    output = tmp_path / "out.json"
    result = subprocess.run(
        [sys.executable, str(HELPER), str(inputs), str(output)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.startswith("bioheaders metadata ")
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["genome"] == NASTY
    assert record["funding"] == "`x`"
    assert not (tmp_path / "injected").exists()


def test_failure_exit_status(tmp_path):
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps(params(genome="a\nb")), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(HELPER), str(inputs), str(tmp_path / "o")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Genome name" in result.stderr
