# Agent instructions

## Current repository context

This is the active family toolkit, including installed commands and the Claude
Code plugin. FHT-File-Converter is retired. The shared specification publishes
contracts; type repositories develop them. Bundle reviewed, versioned schemas
with provenance and explicit supported-version behavior. A new parser/form/export
need does not authorize new metadata fields. Synchronize all packaged and
compatibility schema/context copies using the current build/test tooling.
Merged is not released: main can run ahead of the latest PyPI/container
release, so check the newest tag (`git tag --contains <commit>`) before
describing a fix as shipped; shared conformance and CI pin released toolkit
bytes, never main.

## Schema additions and their own development cycle

A new optional field, structured alternative, enum value, constraint, required
field or changed meaning is a schema-contract change, even when motivated by a
UI, exporter, parser fix or documentation task. Identify it explicitly as a
**schema addition** or other contract change in its issue and PR. Supporting an
already adopted field in a consumer is implementation work, not a new field.

Schema additions have their own proposal, review, compatibility, versioning and
release cycle. Keep them separately reviewable from routine fixes, website work,
packaging and dependency updates; link dependent implementation PRs rather than
silently adopting a field downstream. Shared fields/objects and cross-type rules
belong in FAIR-bioHeaders-Specification; type-specific design starts in the owning
development repository and is coordinated into shared publication. Name affected
types, requiredness, semantics, mappings, serializers and conformance fixtures.

During active construction of FHP, FHT and FHGFF3, maintainers may iterate on draft
fields with lighter process and include coordinated schema/implementation work in
one clearly scoped PR. Record the proposal and compatibility impact in that PR;
this flexibility does not make every field adopted or supported. Preserve already
published contracts and cited versions, label draft behavior, and obtain joint
maintainer review before publication. FHR additions retain the separate cycle.
Do not apply draft flexibility to released FHP/FHGFF3 schemas retroactively.

Use the shared specification's `docs/SCHEMA-VERSIONS.md` and
`schemas/versions.json`: contract versions are per type, distinct from repository
release tags and biological resource versions. Additive changes that preserve all
valid values and meanings qualify for a minor increment; invalidating records or
changing meanings requires a major increment. Do not assign a new version merely
for implementing an existing contract. Never rewrite immutable releases, fixed
schema aliases or existing file-bound headers as incidental cleanup. Header edits
require checksum recomputation and may affect downstream parent links.

Check the adoption decision and released support before implementing a proposal;
an issue or PR's existence does not establish adoption. Structured vouchers
(FAIR-bioHeaders-Specification#139/#140) and mapping profiles (#56 in that same
repository) have their own review history. Implemented subsets do not establish
full profile or header-family support. The mapping page tracked in
fair-bioheaders.github.io#29 depends on approved profiles. Recheck these records
rather than relying on a copied description of their temporary status.

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

`bioheaders/__init__.py` holds the mapping, input/output methods, and packaged schema loading. `bioheaders/cli.py` implements all installed commands: the `bioheaders` subcommands and the eight `fhr-*` entry points share one implementation per command. `fhr.py` is the deprecated `fhr` import name (an alias of `bioheaders`, warning once); the `fhr/` directory is not a package and only keeps `cli.py` and `fhr_schema.json` for FAIR-bioHeaders-Specification's checkout checks. Old top-level and FASTA/GFA scripts are compatibility wrappers. `bioheaders/faidx.py` implements `bioheaders faidx` (issue #108): samtools-compatible `.fai`/`.gzi` indexes for FASTA with a header, following htslib's `fai_build_core`; `tests/faidx_test.py` compares it with samtools and pysam when they are installed. `bioheaders/jsonld.py` writes and reads canonical JSON-LD (FAIR-bioHeaders-Specification docs/JSONLD.md); `bioheaders/fhr.context.jsonld` is a byte-identical copy of FAIR-bioHeaders-Specification `jsonld/fhr.context.jsonld`, included in distributions, and `examples/*.fhr.jsonld` match the specification's examples. `bioheaders/fhp.context.jsonld` is the reviewed FHP-Specification context, and `bioheaders/fhp_microdata.py` implements the FHP microdata binding. `bioheaders/fhr_schema.json` is included in distributions; root and `fhr/` `fhr_schema.json` are compatibility copies. `compat/fhr` builds the code-free `fhr` distribution that requires the same `fair-bioheaders` version. `tests/fhr_test.py` covers semantic round trips, validation, and exact-byte sequence helpers; `tests/bioheaders_test.py` covers the `bioheaders` command and the `fhr` compatibility names. Poetry config defines nine entry points; the `fhr-*` commands are public API and must not print deprecation notices. `bioheaders/assess/` implements `bioheaders assess` (FAIR-bioHeaders-Specification feature 010): `sniff`, `conventions` and `synonyms` read the header, `rubric` derives the 41 indicator statuses, `suggestions`, `links`, `related` and `circumstantial` handle suggestions and related-file checks, `conformance` validates FHR headers, `render` writes the reports, `batch` runs batch mode and `online` (imported only with `--online`) does the opt-in resolution. Its versioned data files (`rubric.json`, `synonyms.json`, `reference/*.json` and their schemas, and `assessment-report.schema.json`, byte-identical to the specification's contract) live in `bioheaders/assess/data/` and are included in distributions. `tests/assess_*_test.py` run with sockets disabled (`tests/conftest.py`), except tests marked `online_local`, which use a server on 127.0.0.1. `scripts/bench_assess.py` is the SC-004 benchmark (not packaged).

`plugins/fair-bioheaders` is the Claude Code plugin (one skill) and `.claude-plugin/marketplace.json` its marketplace; neither is packaged. The plugin's `plugin.json` `version` follows the package version, so bump it in every release (`tests/claude_plugin_test.py` checks this), and keep the skill's commands and schema table in step with the CLI and bundled schemas.

`galaxy/tools/fair_bioheaders` holds the Galaxy wrappers (not packaged), laid out for galaxyproject/tools-iuc. Their `@TOOL_VERSION@` in `macros.xml` also follows the package version (`galaxy-tools.yml` checks this), so bump it, and reset `@VERSION_SUFFIX@` to 0, in every release; keep the wrappers' options in step with the CLI.

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
  block: run `bioheaders strip genome.fhr.fa genome.fa` first. htslib-based tools
  (samtools faidx with a region, bcftools, pysam, JBrowse, VEP) can instead use an
  index from `bioheaders faidx genome.fhr.fa` (0.8.3 and later), written
  before they run. In Biopython use `SeqIO.parse(path, "fasta-pearson")`.
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
poetry run mypy -p bioheaders
```

For schema changes, inspect compatibility of valid existing instances, required
fields, types, unknown-property policy, patterns, URI/date formats, and optional
values. Coordinate published-schema changes upstream and synchronize every affected
packaged schema, released snapshot and compatibility copy in this checkout. Review the
schema diff before intentionally updating upstream schema drift baselines; never
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

## Issue, project and code-review behavior

### Issues and the connected project

- Add every issue you work on to the connected project (project #9, "FAIR
  BioHeaders — 2026 refresh") and set `Status` to `In Progress` when work starts.
- Keep `Status` current as the work moves (`Todo`, `In Progress`, `Blocked`,
  `Blocked - In Progress`, `Done`), and set `Outcome` when it closes.
- Link every PR to its issue (`Closes #N` or `Refs #N`). Do not do unreported work.
- After each work run (implementation, tests, review pass), post a status comment
  on the issue or PR: what changed, checks run and results, commit/PR links,
  blockers, and the next action. Do not rely on chat history.

### Code review on a PR

When a PR receives code review (human or Copilot):

1. Read the overall review and every inline comment before changing anything.
2. Make each fix in a **new commit**. Do not amend or force-push over reviewed
   commits; if a rebase is required, cite the new head in the replies.
3. Reply to each inline finding with the fix and the relevant commit hash.
4. Resolve that inline comment/thread.
5. After all findings are handled, post an overall reply to the review
   summarizing each finding's disposition and the commits.
6. Treat optional suggestions as required unless they are genuinely out of
   scope; state why and link a follow-up issue.

Do not push to a repository's main branch or merge a PR without maintainer
approval.

## Licensing policy (2026-10-09)

New FAIR BioHeaders project contributions from March 2025 onward use MPL-2.0.
David Molik left USDA in February 2025. Preserve historical USDA public-domain
material, previously granted permissions, and third-party licenses/notices;
do not label all current contributors as government employees. See LICENSE
for scope. Do not rewrite historical releases or silently relicense upstream
material. Keep README badges, package metadata and citation metadata consistent.
Keep `compat/fhr/LICENSE` identical to the root LICENSE so the compatibility
distribution ships the complete MPL and historical USDA notice.

## Bundled schemas, streaming and workflow integrations

`bioheaders/schemas/bundled.json` selects current schemas and fixed released
snapshots under `bioheaders/schemas/`; `bioheaders/selection.py` implements the
shared rules V1-V6 of `docs/SCHEMA-VERSIONS.md`. V6 needs the record, not just its
`schema` value (an FHR 1 record citing raw-main with `schemaVersion` the number 1
is read as v0.3.1, with a warning), so code that validates a record selects its
schema with `select_record()`/`schema_for()`, never `select(record["schema"])`.
Check this registry and every affected
packaged/compatibility copy when adopting schema support. A current-schema refresh
must not overwrite frozen release snapshots. Keep type/serialization/version
support explicit; success for FHR JSON-LD does not establish FHP/FHGFF3 parity.
Preserve stdin/pipes and gzip/BGZF handling, bounded processing, exact byte coverage
and ordinary comments when changing sequence readers/writers. Test the changed
input paths, not just a small uncompressed metadata round trip.

The nf-core-style modules and the Dockstore workflow moved to FAIR-bioHeaders/FHR-Nextflow
(FHR-Nextflow#21); make Nextflow changes there. The copies in `nextflow/` and
`.dockstore.yml` are frozen at fair-bioheaders 0.8.2 and stay only until the
FHR-Nextflow workflow is registered on Dockstore, then they are removed and the
Dockstore entry here is marked deprecated (its versions stay as history). Until then,
if CI needs a fix, run `nf-test test --profile
docker --ci --verbose` from `nextflow/` (one command), following
`.github/workflows/nextflow-modules.yml` and its pinned tool versions. Keep module
container tags and `environment.yml` Conda pins coordinated across modules.

The Dockerfile builds from a specified released wheel. The module CI builds the
pinned release image, so a successful module test does not automatically test
unreleased Python changes. Coordinate source tests and explicit candidate-image
checks when both change. `.github/workflows/container.yml` smoke-tests amd64 and
arm64, then publishes released images; follow its tag/latest rules. Runtime,
container, plugin and module pin changes must state their scope, not silently
upgrade one another. Do not publish an image merely to validate a documentation
change. Keep Python 3.9 CI on a runner with available builds (currently 24.04);
review runtime availability before replacing pinned runner images.
