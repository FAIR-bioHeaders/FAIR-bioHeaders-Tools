# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The opt-in Rust engine backend (Project 14, specs/006 FR-052a)."""

import base64
import hashlib
import subprocess
import sys

import pytest

import bioheaders
from bioheaders import _engine

FHR = (
    ";~schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0\n"
    ";~schemaVersion: '2.1'\n"
    ";~genome: Synthetic genome\n"
    ";~taxon:\n;~  name: Homo sapiens\n;~  uri: https://identifiers.org/taxonomy:9606\n"
    ";~version: '0.0.1'\n;~metadataAuthor:\n;~- name: A\n;~assemblyAuthor:\n;~- name: B\n"
    ";~dateCreated: '2022-03-21'\n;~masking: soft-masked\n"
)


def fasta(header=FHR, body=">s\nACGT\n"):
    data = (header + body).encode()
    digest = base64.b64encode(hashlib.new("sha512_256", data).digest()).decode()
    return (header + f";~checksum: {digest}\n" + body).encode()


@pytest.fixture
def rust():
    pytest.importorskip("fair_bioheaders_tools")
    previous = bioheaders.engine()
    bioheaders.set_engine("rust")
    yield
    bioheaders.set_engine(previous)


def test_default_backend_is_python(monkeypatch):
    assert _engine.BACKENDS == ("python", "rust")
    with pytest.raises(ValueError, match="unknown engine"):
        bioheaders.set_engine("java")


def test_rust_without_engine_is_an_import_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "fair_bioheaders_tools":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    previous = bioheaders.engine()
    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(ImportError, match="fair-bioheaders-tools"):
        bioheaders.set_engine("rust")
    assert bioheaders.engine() == previous  # unchanged: no silent switch


def test_incompatible_engine_is_refused(monkeypatch):
    engine = pytest.importorskip("fair_bioheaders_tools")
    monkeypatch.setattr(engine, "ABI_VERSION", "9.9")
    with pytest.raises(ImportError, match="ABI"):
        bioheaders.set_engine("rust")


def test_rust_reads_and_validates(rust):
    record = bioheaders.fhr()
    record.input_fasta(fasta())
    assert record.genome == "Synthetic genome"
    record.fhr_validate()


def test_rust_errors_keep_python_classes_and_messages(rust):
    from jsonschema.exceptions import ValidationError

    record = bioheaders.fhr()
    record.input_fasta(fasta(FHR.replace("soft-masked", "maybe")))
    with pytest.raises(ValidationError) as error:
        record.fhr_validate()
    assert error.value.json_path == "$.masking"
    with pytest.raises(ValueError, match="FHR header line after sequence data at line"):
        bioheaders.fhr().input_fasta(fasta() + b";~late: 1\n")


def test_rust_applies_ecma_dollar_decision_9(rust):
    """Decision 9: ECMA-262 $ does not match before a final line feed (the
    toolkit's translation has done the same since 0.13.0; 0.12.0 did not)."""
    from jsonschema.exceptions import ValidationError

    record = bioheaders.fhr()
    record.input_fasta(
        fasta(FHR.replace("masking: soft-masked", 'masking: "soft-masked\\n"'))
    )
    with pytest.raises(ValidationError) as error:
        record.fhr_validate()
    assert error.value.json_path == "$.masking"


def test_rust_verify_command(rust, tmp_path):
    path = tmp_path / "x.fhr.fasta"
    path.write_bytes(fasta())
    env = {"BIOHEADERS_ENGINE": "rust", "PATH": ""}
    command = [
        sys.executable,
        "-c",
        "import sys; from bioheaders.cli import fasta_validate_main as m; sys.argv=['x', sys.argv[1]]; sys.exit(m())",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Checksum verified."
    tampered = fasta()[:-2] + b"A\n"
    path.write_bytes(tampered)
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 1
    assert result.stderr.strip() == "FHR: Checksum verification failed"
