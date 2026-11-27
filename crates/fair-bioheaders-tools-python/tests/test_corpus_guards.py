# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The missing-corpus guard of conftest.py (review 6091339996 finding 3): the
local opt-out reports the corpus tests NOT_RUN and passes; in CI, or without
the opt-out, a missing corpus fails the session."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SUITE = Path(__file__).with_name("test_conformance.py")
CORPUS_VARIABLES = ("FH_SPEC_V060", "FH_SPEC_34BBE21A", "CI", "FH_ALLOW_MISSING_CORPUS")


def run_suite(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if k not in CORPUS_VARIABLES}
    env.update(extra, FH_RECEIPT_DIR=str(tmp_path / "receipts"))
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(SUITE)],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=300,
    )


def test_local_opt_out_reports_not_run_and_passes(tmp_path):
    result = run_suite(tmp_path, FH_ALLOW_MISSING_CORPUS="1")
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "3 skipped" in output and "NOT_RUN: 3 test(s)" in output, output
    assert "Error" not in output, output
    assert not (tmp_path / "receipts").exists()  # no receipt without a corpus


@pytest.mark.parametrize(
    "extra",
    [{"FH_ALLOW_MISSING_CORPUS": "1", "CI": "true"}, {}],
    ids=["ci", "no-opt-out"],
)
def test_missing_corpus_fails_in_ci_and_without_the_opt_out(tmp_path, extra):
    result = run_suite(tmp_path, **extra)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "3 failed" in output and "a missing corpus is a failure" in output, output
