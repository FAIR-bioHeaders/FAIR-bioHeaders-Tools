# Tasks: `bioheaders metadata`

- [x] T001 Check every option against `bioheaders/schemas/fhr-2.1.json`; record shapes and the checksum behaviour of `combine`/`validate` in plan.md (Research).
- [x] T002 `bioheaders/metadata.py`: `FastaStats` streaming statistics (contig/scaffold N/L 50/90, totals, GC) per plan.md definitions.
- [x] T003 `bioheaders/metadata.py`: `build_record` with typed parsers (taxon id, ORCID with check digit, date, software, extras, stats, URIs, control characters) and the missing-required list.
- [x] T004 `bioheaders/metadata.py`: schema validation with the checksum set aside, header-size limits, YAML (R11/R12/R13) and JSON rendering.
- [x] T005 `bioheaders/cli.py`: `metadata` subcommand, `--type` (fhr; fhp/fhgff3 refused), `--format`, `-o`.
- [x] T006 Tests: hand-computed statistics (plain, gzip, BGZF, headed, CRLF, chunk sizes 1-64), all-N, single contig, empty/header-only/non-nucleotide input, every option, missing required list, hostile values round trip, metadata → combine → verify → strip end to end, installed command.
- [x] T007 Docs: README section, plugin skill, AGENTS.md map, CHANGELOG Unreleased, regenerated capability matrix.
- [x] T008 Code review and adversarial review; fix findings with regression tests.
- [x] T009 Review fixes: header limit counts the checksum line; every value checked before the FASTA is read; output extension must be .yaml/.yml/.json without --format; --stat strict decimal digits and refused for every computable key with --stats-from; tab allowed; unparsable `<...>` author refused; NAME-only software; gcContent fraction warning; "assembly length" reading recorded.
- [x] T010 Adversarial-review fixes: non-UTF-8 arguments refused; taxon ids positive without leading zeros (at most 18 digits) and long values shortened in messages; `--stat` integers at most 2^63 - 1; `--format` may not contradict the extension; bzip2/xz/zstd named; future creation date warns; author names kept as written; gap search with `bytes.find` (about 10 s per GB); README states memory per contig and the protein-letter limit.
