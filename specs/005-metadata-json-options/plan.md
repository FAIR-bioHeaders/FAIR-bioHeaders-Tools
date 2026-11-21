# Implementation Plan: `bioheaders metadata --json`

**Branch**: `005-metadata-json-options` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-metadata-json-options/spec.md`; issue #197 (Refs; #197 remains open until the PR merges).

## Summary

`bioheaders metadata` gains `--json FILE` (`-` for stdin). A new function,
`options_from_json` in `bioheaders/metadata.py`, reads a bounded, strict JSON
document and turns each key into the **text its command-line option would
receive** (an author object becomes `Name <orcid>`, a software object
`NAME=VERSION=URI`, a `stat`/`extra` entry `KEY=VALUE`). Those values fill the
same argparse namespace the flags fill, so `build_record`, the schema check,
the statistics and the writers run unchanged, and the output is identical to
the flags' by construction. Metadata flags given with `--json` are refused.
Research (planemo against Galaxy 26.1) shows the Galaxy wrapper can build the
document in a Cheetah `<configfile>` with `json.dumps` from raw parameter
values, with only paths on the command line and no sanitizer override.

## Technical Context

**Language/Version**: Python 3.9+ (CI: 3.9 and 3.13)

**Primary Dependencies**: standard library `json` and `difflib`; nothing new

**Storage**: N/A (reads one JSON document, writes the existing outputs)

**Testing**: pytest (`tests/metadata_json_test.py`, installed command through
`subprocess`); planemo for the Galaxy research probe (not in CI)

**Target Platform**: Linux/macOS command line, Galaxy, Nextflow

**Project Type**: CLI and library

**Performance Goals**: reading the document is negligible next to
`--stats-from`; bounded at 1 MiB

**Constraints**: output byte-identical to the equivalent flags; fail closed
on anything the format does not define (constitution III)

**Scale/Scope**: one new option, one loader, docs, tests; no schema change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
| --- | --- | --- |
| I. The specification is the contract | No FHR field, schema or version change; the options format describes command input only | Pass |
| II. Exact bytes and one reading | Output bytes are produced by the existing writers from the same namespace | Pass |
| III. Fail closed on untrusted input | Unknown and duplicate keys, wrong types, NaN/Infinity, BOM, invalid UTF-8, >1 MiB and deep nesting are refused; flags with `--json` refused | Pass |
| IV. Preserve metadata and typed values | Values reach the record unchanged; tests compare bytes with the flags | Pass |
| V. Compatible, small, tested | No new dependency; the flags are unchanged; the format is public API from its release; regression tests added | Pass |
| Verification gates | pytest, ruff, isort, black, mypy; `poetry build` and `python -m build compat/fhr` in CI | Planned |

Post-design re-check: unchanged (Pass). The one design choice that touches the
parser — `--type` now defaults to `None` and is resolved to `fhr` in the command
— keeps the documented default and lets `--json` tell an explicit `--type`
apart.

## Project Structure

### Documentation (this feature)

```text
specs/005-metadata-json-options/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0, including the Galaxy probe
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── metadata-options.md   # the JSON options format
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
bioheaders/
├── metadata.py      # JSON_OPTIONS table and options_from_json()
└── cli.py           # --json option, _read_json_options(), help epilog
tests/
└── metadata_json_test.py
README.md            # "Options from a JSON document (--json)"
CHANGELOG.md         # Unreleased entry
plugins/fair-bioheaders/skills/fair-bioheaders/SKILL.md   # one sentence
```

**Structure Decision**: the loader lives beside `build_record` in
`bioheaders/metadata.py` (it depends only on that module's error type and
limits); the command wiring stays in `cli.py` with the other `metadata` code.
The Galaxy wrapper (`galaxy/tools/fair_bioheaders/`) is **not** changed in this
PR: the wrapper pins a released toolkit, so it moves to `--json` after the
release and the Bioconda update (design in research.md R6).

## Complexity Tracking

No violations.
