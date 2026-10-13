"""The container image inputs and the Nextflow modules stay in step with the package."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "nextflow" / "modules" / "nf-core" / "fairbioheaders"


def caret_range(spec):
    """Poetry's ^X.Y[.Z] as the equivalent >=X.Y[.Z],<X+1 (for X >= 1)."""
    version = spec.lstrip("^")
    major = int(version.split(".")[0])
    assert major >= 1, spec
    return f">={version},<{major + 1}"


def test_docker_requirements_match_pyproject():
    tomllib = pytest.importorskip("tomllib")
    with open(ROOT / "pyproject.toml", "rb") as stream:
        dependencies = tomllib.load(stream)["tool"]["poetry"]["dependencies"]
    expected = {}
    for name, spec in dependencies.items():
        if name == "python":
            continue
        if isinstance(spec, str):
            spec = {"version": spec}
        extras = f"[{','.join(spec['extras'])}]" if spec.get("extras") else ""
        expected[name.lower()] = f"{name.lower()}{extras}{caret_range(spec['version'])}"
    lines = (
        (ROOT / "docker" / "requirements.in").read_text(encoding="utf-8").splitlines()
    )
    found = {}
    for line in lines:
        if line.strip() and not line.startswith("#"):
            found[re.split(r"[\[<>=]", line, maxsplit=1)[0].lower()] = line.strip()
    assert found == expected


def test_docker_requirements_are_locked():
    locked = (ROOT / "docker" / "requirements.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([A-Za-z0-9._-]+)==\S+ \\$", locked, flags=re.M)
    assert {"jsonschema", "pyyaml", "pyld"} <= {pin.lower() for pin in pins}
    blocks = re.split(r"^(?=[A-Za-z0-9._-]+==)", locked, flags=re.M)[1:]
    assert len(blocks) == len(pins)
    for block in blocks:
        assert "--hash=sha256:" in block, block.splitlines()[0]


def test_modules_pin_one_released_version():
    versions = set()
    for module in ("combine", "verify"):
        main = (MODULES / module / "main.nf").read_text(encoding="utf-8")
        environment = (MODULES / module / "environment.yml").read_text(encoding="utf-8")
        versions |= set(
            re.findall(r"ghcr\.io/fair-bioheaders/fair-bioheaders:([0-9.]+)'", main)
        )
        versions |= set(
            re.findall(r"bioconda::fair-bioheaders=([0-9.]+)$", environment, re.M)
        )
        assert f"FAIRBIOHEADERS_{module.upper()}" in main
        assert "topic: versions" in main
    assert len(versions) == 1
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", versions.pop())
