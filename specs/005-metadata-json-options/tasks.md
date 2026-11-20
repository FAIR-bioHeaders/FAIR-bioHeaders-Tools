# Tasks: `bioheaders metadata --json`

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/metadata-options.md

**Tests**: required (spec SC-001, SC-002, SC-005).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Research: Galaxy configfile probes (planemo, Galaxy 26.1) and the planned wrapper command; record in specs/005-metadata-json-options/research.md and research/*.xml.

## Phase 2: Foundational

- [x] T002 `bioheaders/metadata.py`: `JSON_OPTIONS` key table (key → argparse attribute, kind) covering every metadata option of `_metadata_arguments`.
- [x] T003 `bioheaders/metadata.py`: `options_from_json()` — 1 MiB bound, BOM and UTF-8 checks, duplicate keys, NaN/Infinity, nesting, top-level object, unknown keys with suggestion, JSON types, list objects, `null`/`[]` as absent, joins to the flags' text (R1, R2).

## Phase 3: User Story 1 — write metadata from a JSON document (P1)

- [x] T004 [US1] `bioheaders/cli.py`: `--json FILE|-` option; `_read_json_options()` reads the bounded document from a file or stdin and fills the namespace; `--type` default resolved in the command.
- [x] T005 [P] [US1] `tests/metadata_json_test.py`: byte-identical output and stderr vs the flags (YAML and JSON) for required-only, every option, hostile text, nulls/empty lists, Unicode/tab, masking, single optional; numbers vs text; `stats-from` file and `-o`; stdin; `stats-from -` with a file document.

## Phase 4: User Story 2 — same validation as the flags (P1)

- [x] T006 [US2] `bioheaders/cli.py`: refuse metadata flags with `--json` (each named); refuse `stats-from -` with `--json -`; `-o` may not be the document.
- [x] T007 [P] [US2] `tests/metadata_json_test.py`: every refusal of the flags through JSON (required list, control and line-break characters, invisible characters, invalid UTF-8, ORCID form and check digit, dates, taxon ids, masking, x- keys, duplicate stat/extra, stat typing and range, stat with stats-from, accession-url, R14 schemes, type); flags with `--json`; document checked before the FASTA.

## Phase 5: User Story 3 — reject what the format does not define (P1)

- [x] T008 [P] [US3] `tests/metadata_json_test.py`: unknown keys (top level and in objects, with suggestion), output keys in the document, wrong JSON types, booleans, list members, `<`/`>` in names, `=` in software, malformed documents (syntax, duplicates, NaN, BOM, UTF-8, nesting, size), more than 1 MiB on stdin.

## Phase 6: User Story 4 — Galaxy can call the installed command (P2)

- [x] T009 [US4] Planned wrapper verified with planemo against this branch (13/13); design in research.md R6. The wrapper itself changes after the release and Bioconda (follow-up; not in this PR).

## Phase 7: Polish

- [x] T010 [P] README "Options from a JSON document (`--json`)", help epilog example, plugin skill sentence, CHANGELOG Unreleased.
- [x] T011 [P] `tests/metadata_json_test.py`: README and help examples are valid; every key is a documented option.
- [x] T012 Full suite, ruff, isort, black, mypy.
- [ ] T013 Code review by an independent different model (Copilot or David's Codex) or Adam; fix findings in new commits.
- [ ] T014 Follow-up after release and Bioconda: switch `galaxy/tools/fair_bioheaders/fair_bioheaders_metadata.xml` and tools-iuc to `--json`, delete `fair_bioheaders_metadata.py`.

## Dependencies

T002–T003 before T004; T004 before T005–T008; T001 informs T009; T013 before merge; T014 after release.
