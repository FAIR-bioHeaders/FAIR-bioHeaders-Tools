# Quickstart: validating `bioheaders metadata --json`

Prerequisites: a checkout of this branch, `poetry install`.

## 1. Automated checks

```bash
poetry run pytest tests/metadata_json_test.py tests/metadata_test.py
poetry run ruff check . && poetry run isort . --check-only && poetry run black . --check
poetry run mypy -p bioheaders
```

Expected: all pass. `metadata_json_test.py` compares `--json` with the
equivalent flags byte for byte (YAML and JSON output), covers every refusal
in [contracts/metadata-options.md](contracts/metadata-options.md), stdin, the
1 MiB bound and the README and help examples.

## 2. By hand

Write the example from the contract to `options.json` (drop `stats-from`, or
point it at a FASTA), then:

```bash
poetry run bioheaders metadata --json options.json -o a.yaml
poetry run bioheaders metadata --json - -o b.yaml < options.json
cmp a.yaml b.yaml                                   # identical
poetry run bioheaders metadata --json options.json --genome x   # exit 1: refused
echo '{"date_created": "2024-01-02"}' | poetry run bioheaders metadata --json -
# FHR: --json: unknown key 'date_created' (did you mean 'date-created'?)
```

Then `bioheaders combine a.yaml genome.fa -o genome.fhr.fa` and
`bioheaders verify genome.fhr.fa` succeed, as for metadata written from flags.

## 3. Galaxy (research only; the wrapper changes after the release)

Apply [research/galaxy-wrapper-command.xml](research/galaxy-wrapper-command.xml)
to a copy of `galaxy/tools/fair_bioheaders/fair_bioheaders_metadata.xml`
(replace `<command>` and `<configfiles>`, delete the helper script and the
`<sanitizer sanitize="false"/>` line, and assert `--json` instead of the script
name in the hostile-text tests), put this branch's `bioheaders` first on
`PATH`, and run `planemo test --no_dependency_resolution` on the copy. Expected:
all 13 tests pass and every job command line holds only paths
(research.md R6).
