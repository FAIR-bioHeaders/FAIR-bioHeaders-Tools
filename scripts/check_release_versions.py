#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Check release metadata before tagging (Python 3.11 or newer)."""

import argparse
import ast
import datetime
import json
import re
import sys
import tomllib
from pathlib import Path
from xml.etree import ElementTree


def check(root: Path, tag: str | None = None) -> list[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["poetry"]
    version = project["version"]
    problems = []
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        problems.append("package version must be a stable X.Y.Z release")
    if tag is not None and tag != "v" + version:
        problems.append(f"tag {tag!r} does not match package {version!r}")
    compat = tomllib.loads((root / "compat/fhr/pyproject.toml").read_text())["project"]
    if (compat["version"], compat["dependencies"]) != (
        version,
        [f"fair-bioheaders=={version}"],
    ):
        problems.append("compat/fhr version and sole exact dependency must match")
    tree = ast.parse((root / "bioheaders/__init__.py").read_text())
    code_versions = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
    ]
    if code_versions != [version]:
        problems.append("bioheaders.__version__ must match package")
    macros = ElementTree.parse(root / "galaxy/tools/fair_bioheaders/macros.xml")
    values = [node.text for node in macros.findall("./token[@name='@TOOL_VERSION@']")]
    if values != [version]:
        problems.append("Galaxy @TOOL_VERSION@ must match package")
    suffixes = [
        node.text for node in macros.findall("./token[@name='@VERSION_SUFFIX@']")
    ]
    if len(suffixes) != 1 or not re.fullmatch(r"[0-9]+", suffixes[0] or ""):
        problems.append("Galaxy @VERSION_SUFFIX@ must be one nonnegative integer")
    plugin = json.loads(
        (root / "plugins/fair-bioheaders/.claude-plugin/plugin.json").read_text()
    )
    if plugin["version"] != version:
        problems.append("plugin version must match package")
    citation = (root / "CITATION.cff").read_text()
    versions = re.findall(r"^version: *['\"]?([^'\"\s]+)", citation, re.M)
    if versions != [version]:
        problems.append("CITATION.cff version must match package")
    dates = re.findall(
        r"^date-released: *(['\"]?)(\d{4}-\d{2}-\d{2})\1 *$", citation, re.M
    )
    if len(dates) != 1:
        problems.append("CITATION.cff requires one explicit release date")
    else:
        try:
            datetime.date.fromisoformat(dates[0][1])
        except ValueError:
            problems.append("CITATION.cff release date is not a calendar date")
    readme = re.search(
        r"^\*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", (root / "README.md").read_text(), re.M
    )
    if not readme or readme.group(1) != version:
        problems.append("README current version must match package")
    if not re.search(
        r"^## " + re.escape(version) + r" \(", (root / "CHANGELOG.md").read_text(), re.M
    ):
        problems.append("CHANGELOG requires the release version heading")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--tag", help="also require this exact vX.Y.Z tag")
    args = parser.parse_args()
    try:
        problems = check(args.root, args.tag)
    except (
        OSError,
        ValueError,
        KeyError,
        SyntaxError,
        ElementTree.ParseError,
    ) as error:
        problems = [str(error)]
    if problems:
        print("release versions: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(
        "release versions: package, code, compatibility, Galaxy, plugin, citation and changelog agree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
