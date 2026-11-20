# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Experimental-draft warnings in the CLI, and the draft digest check (rule V7).

The library raises ``ExperimentalMicrodataWarning`` (FHGFF3 HTML) and
``ExperimentalDraftWarning`` (the FHT draft lane) through :mod:`warnings`, for API
users. The CLI prints them as ``TYPE: warning: message`` lines, once per run,
instead of Python's ``path:line: Category: message`` form with a source line.
"""

import copy
import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
import yaml

from bioheaders import fhgff3_microdata, selection

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
FHGFF3_HTML = ROOT / "examples/r4-current/fhgff3/minimal-reference.microdata.fhgff3.html"
FHT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/"
    "FHT-Specification/main/fht.json"
)


def run(*args, draft=False):
    env = {k: v for k, v in os.environ.items() if k != selection.DRAFT_ENV}
    if draft:
        env[selection.DRAFT_ENV] = "1"
    return subprocess.run(
        [str(BIN / "bioheaders"), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
    )


def assert_clean(stderr):
    assert "Warning:" not in stderr, stderr  # no "ExperimentalXWarning:" form
    assert ".py:" not in stderr, stderr  # no source path and line number


@pytest.mark.parametrize("target", ["out.html", "out.json"])
def test_fhgff3_html_warning_is_one_clean_line(tmp_path, target):
    """HTML to HTML warned twice (read and write); every convert warns once."""
    result = run("convert", FHGFF3_HTML, tmp_path / target)
    assert result.returncode == 0, result.stderr
    assert_clean(result.stderr)
    lines = [line for line in result.stderr.splitlines() if "experimental" in line]
    assert len(lines) == 1, result.stderr
    assert lines[0].startswith("FHGFF3: warning: FHGFF3 HTML microdata is experimental")


def test_fhgff3_validate_warning_is_clean():
    result = run("validate", FHGFF3_HTML)
    assert result.returncode == 0, result.stderr
    assert_clean(result.stderr)
    assert result.stderr.count("FHGFF3: warning:") == 1


@pytest.fixture
def fht_file(tmp_path):
    metadata = tmp_path / "fht.yaml"
    metadata.write_text(
        yaml.safe_dump(
            {
                "schema": FHT_URL,
                "schemaVersion": "1.0",
                "transcriptome": "Synthetic transcript set",
                "assemblyType": "de novo",
                "taxon": {
                    "name": "Tribolium castaneum",
                    "uri": "https://identifiers.org/taxonomy:7070",
                },
                "version": "1.0.0",
                "metadataAuthor": [{"name": "Test Author"}],
                "dateCreated": "2026-11-12",
            }
        )
    )
    fasta = tmp_path / "t.fa"
    fasta.write_text(">t\nAUGC\n")
    out = tmp_path / "t.fht.fa"
    result = run("combine", metadata, fasta, "-o", out, draft=True)
    assert result.returncode == 0, result.stderr
    return out


def test_fht_draft_warning_is_one_clean_line(fht_file):
    result = run("verify", fht_file, draft=True)
    assert result.returncode == 0, result.stderr
    assert_clean(result.stderr)
    assert result.stderr.count("FHT: warning: FHT support is experimental") == 1


def test_the_library_still_warns_through_the_warnings_module():
    with pytest.warns(fhgff3_microdata.ExperimentalMicrodataWarning):
        fhgff3_microdata.extract(
            FHGFF3_HTML.read_text(),
            selection.select(fhgff3_microdata.FHGFF3_ITEMTYPE)[2],
        )


# The draft digest (rule V7) -----------------------------------------------------


@pytest.fixture
def fresh_cache(monkeypatch):
    monkeypatch.setattr(selection, "_CACHE", {})
    monkeypatch.setenv(selection.DRAFT_ENV, "1")


def test_matching_draft_bytes_load_without_a_digest_warning(fresh_cache):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selection.select(FHT_URL)
    assert not [w for w in caught if w.category is selection.DraftDigestWarning]


def test_draft_bytes_that_differ_from_the_recorded_digest_warn(
    fresh_cache, monkeypatch
):
    bundled = copy.deepcopy(selection.BUNDLED)
    bundled["drafts"]["FHT"]["sha256"] = "0" * 64
    monkeypatch.setattr(selection, "BUNDLED", bundled)
    with pytest.warns(selection.DraftDigestWarning, match="not the recorded 0{64}"):
        kind, _, schema = selection.select(FHT_URL)
    assert kind == "FHT" and schema["title"] == "FHT"
    # Hashed once, on load: the cached copy does not warn again.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selection.select(FHT_URL)
    assert not [w for w in caught if w.category is selection.DraftDigestWarning]
