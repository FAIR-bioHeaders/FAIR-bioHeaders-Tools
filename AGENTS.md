# Agent instructions

## Strategy and boundaries

Read README, relevant issue requirements, and current code before editing. The
[2024 FHR paper](https://doi.org/10.1093/bib/bbae122) motivates minimal metadata,
multiple serializations, provenance tied closely to data, compatibility, FAIR,
and TRUST. Practical interpretation: preserve user metadata and sequence bytes,
keep required fields/dependencies small, and prefer interoperable incremental
changes over speculative frameworks. These are implementation guidelines inferred
from the paper, not quotations or governance rules.

David and Adam are the maintainers and jointly hold schema and release authority
(GOVERNANCE.md). The documented steering-group option is not active; do not treat
it as current authority.

## Repository map

`bioheaders/__init__.py` holds the mapping, input/output methods, and packaged schema loading. `bioheaders/cli.py` implements all installed commands: the `bioheaders` subcommands and the eight `fhr-*` entry points share one implementation per command. `fhr.py` is the deprecated `fhr` import name (an alias of `bioheaders`, warning once); the `fhr/` directory is not a package and only keeps `cli.py` and `fhr_schema.json` for FAIR-bioHeaders-Specification's checkout checks. Old top-level and FASTA/GFA scripts are compatibility wrappers. `bioheaders/jsonld.py` writes and reads canonical JSON-LD (FAIR-bioHeaders-Specification docs/JSONLD.md); `bioheaders/fhr.context.jsonld` is a byte-identical copy of FAIR-bioHeaders-Specification `jsonld/fhr.context.jsonld`, included in distributions, and `examples/*.fhr.jsonld` match the specification's examples. `bioheaders/fhr_schema.json` is included in distributions; root and `fhr/` `fhr_schema.json` are compatibility copies. `compat/fhr` builds the code-free `fhr` distribution that requires the same `fair-bioheaders` version. `tests/fhr_test.py` covers semantic round trips, validation, and exact-byte sequence helpers; `tests/bioheaders_test.py` covers the `bioheaders` command and the `fhr` compatibility names. Poetry config defines nine entry points; the `fhr-*` commands are public API and must not print deprecation notices. `bioheaders/assess/` implements `bioheaders assess` (FAIR-bioHeaders-Specification feature 010): `sniff`, `conventions` and `synonyms` read the header, `rubric` derives the 41 indicator statuses, `suggestions`, `links`, `related` and `circumstantial` handle suggestions and related-file checks, `conformance` validates FHR headers, `render` writes the reports, `batch` runs batch mode and `online` (imported only with `--online`) does the opt-in resolution. Its versioned data files (`rubric.json`, `synonyms.json`, `reference/*.json` and their schemas, and `assessment-report.schema.json`, byte-identical to the specification's contract) live in `bioheaders/assess/data/` and are included in distributions. `tests/assess_*_test.py` run with sockets disabled (`tests/conftest.py`), except tests marked `online_local`, which use a server on 127.0.0.1. `scripts/bench_assess.py` is the SC-004 benchmark (not packaged).

`plugins/fair-bioheaders` is the Claude Code plugin (one skill) and `.claude-plugin/marketplace.json` its marketplace; neither is packaged. The plugin's `plugin.json` `version` follows the package version, so bump it in every release (`tests/claude_plugin_test.py` checks this), and keep the skill's commands and schema table in step with the CLI and bundled schemas.

## Using FAIR-bioHeaders in another project

For assistants and people adding FAIR-bioHeaders headers to data in another project:

- Install `pip install fair-bioheaders` (command `bioheaders`). Add a header with
  `bioheaders combine metadata.yaml genome.fa -o genome.fhr.fa` (FASTA, `.gfa`,
  `.gff3`; FHP for protein FASTA) and check it with `bioheaders verify genome.fhr.fa`.
  `combine` computes the checksum; never write or edit it by hand, and recombine
  after any change.
- Cite a versioned schema in `schema`: `https://w3id.org/fair-bioheaders/fhr/v0.4.0`
  (`schemaVersion: '2.0'`), `.../fhp/v0.4.0` or `.../fhgff3/v0.4.0` (`'1.0'`). The
  required fields are in those schemas; never invent values for them.
- samtools faidx (htslib), pysam `FastaFile`, bedtools, Picard, the Bowtie2, HISAT2
  and STAR index builders and other strict FASTA readers reject a leading `;~`
  block: run `bioheaders strip genome.fhr.fa genome.fa` first. In Biopython use
  `SeqIO.parse(path, "fasta-pearson")`.
- FASTA header values with `>` or `@` are written as `\x3E` and `\x40` (rule R11);
  `combine` does this, and every YAML reader returns the characters.
- The rules are in FAIR-bioHeaders-Specification (`docs/FORMAT.md`,
  `docs/TOOL_COMPATIBILITY.md`); the Claude Code plugin in `plugins/fair-bioheaders`
  packages these steps as a skill.

## Verification

Run relevant checks from the repository root:

```bash
poetry install
poetry run pytest
poetry run ruff check .
poetry run isort . --check-only
poetry run black . --check
```

For schema changes, inspect compatibility of valid existing instances, required
fields, types, unknown-property policy, patterns, URI/date formats, and optional
values. Synchronize the published schema and all three converter copies. Review the
schema diff before intentionally updating `.github/schema-baseline.json`; never
refresh it simply to hide a failed check. For serialization changes, test all
formats and HTML escaping/typed values. For sequence tools, test metadata and
sequence tampering, CRLF, ordinary comments, combine/strip, and installed commands
from outside the checkout. Record environment limitations and failed checks.

Use exact file bytes for SHA-512/256 coverage except the scalar checksum line;
read the format policy before editing checksum behavior. SeqCol is a supplied
collection identifier, not an FHR checksum. Use authoritative pinned MIxS terms
and report partial/lossy mappings explicitly; do not invent accessions or metadata.

Update examples, README, citations, and release notes alongside behavior changes.
Keep cross-repo PR links current. Publishing, adoption of governance, and reporting
contact confirmation are separate maintainer actions. Do not fabricate contacts
or claim a policy has been adopted.

## Licensing policy (2026-10-09)

New FAIR BioHeaders project contributions from March 2025 onward use MPL-2.0.
David Molik left USDA in February 2025. Preserve historical USDA public-domain
material, previously granted permissions, and third-party licenses/notices;
do not label all current contributors as government employees. See LICENSE
for scope. Do not rewrite historical releases or silently relicense upstream
material. Keep README badges, package metadata and citation metadata consistent.
Keep `compat/fhr/LICENSE` identical to the root LICENSE so the compatibility
distribution ships the complete MPL and historical USDA notice.
