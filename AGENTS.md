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

`bioheaders/__init__.py` holds the mapping, input/output methods, and packaged schema loading. `bioheaders/cli.py` implements all installed commands: the `bioheaders` subcommands and the eleven `fhr-*` entry points share one implementation per command. `fhr.py` is the deprecated `fhr` import name (an alias of `bioheaders`, warning once); the `fhr/` directory is not a package and only keeps `cli.py` and `fhr_schema.json` for FAIR-bioHeaders-Specification's checkout checks. Old top-level and FASTA/GFA scripts are compatibility wrappers. `bioheaders/faidx.py` implements `bioheaders faidx` (issue #108): samtools-compatible `.fai`/`.gzi` indexes for FASTA with a header, following htslib's `fai_build_core`; `tests/faidx_test.py` compares it with samtools and pysam when they are installed. `bioheaders/metadata.py` implements `bioheaders metadata` (issue #171, specs/004-bioheaders-metadata): FHR metadata from typed options, validated with the checksum requirement set aside (the output has no checksum; `combine` writes it), and streaming `vitalStats` from FASTA under the contig/scaffold definitions in the README; `tests/metadata_test.py` covers it, including metadata → combine → verify. `bioheaders/jsonld.py` writes and reads canonical JSON-LD (FAIR-bioHeaders-Specification docs/JSONLD.md); `bioheaders/fhr.context.jsonld` is a byte-identical copy of FAIR-bioHeaders-Specification `jsonld/fhr.context.jsonld`, included in distributions, and `examples/*.fhr.jsonld` match the specification's examples. `bioheaders/fhp.context.jsonld` is the reviewed FHP-Specification context, and `bioheaders/fhp_microdata.py` implements the FHP microdata binding. `bioheaders/fhr_schema.json` is included in distributions; root and `fhr/` `fhr_schema.json` are compatibility copies. `compat/fhr` builds the code-free `fhr` distribution that requires the same `fair-bioheaders` version. `tests/fhr_test.py` covers semantic round trips, validation, and exact-byte sequence helpers; `tests/bioheaders_test.py` covers the `bioheaders` command and the `fhr` compatibility names. Poetry config defines twelve installed console commands today — `bioheaders` plus eleven `fhr-*` names (`tests/bioheaders_test.py::test_compat_distribution_matches` pins that count and mirrors them in `compat/fhr`); a thirteenth, `bioheaders-pin-audit`, is described under "Bundled schemas" below and is not an `fhr-*` name. The `fhr-*` commands are public API and must not print deprecation notices. `bioheaders/assess/` implements `bioheaders assess` (FAIR-bioHeaders-Specification feature 010): `sniff`, `conventions` and `synonyms` read the header, `rubric` derives the 41 indicator statuses, `suggestions`, `links`, `related` and `circumstantial` handle suggestions and related-file checks, `conformance` validates FHR headers, `render` writes the reports, `batch` runs batch mode and `online` (imported only with `--online`) does the opt-in resolution. Its versioned data files (`rubric.json`, `synonyms.json`, `reference/*.json` and their schemas, and `assessment-report.schema.json`, byte-identical to the specification's contract) live in `bioheaders/assess/data/` and are included in distributions. `tests/assess_*_test.py` run with sockets disabled (`tests/conftest.py`), except tests marked `online_local`, which use a server on 127.0.0.1. `scripts/bench_assess.py` is the SC-004 benchmark (not packaged).

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
- Link every PR to its issue. Use `Closes #N` only when merging the PR completes
  the issue's entire acceptance scope. For partial work and umbrella trackers,
  use `Refs #N` and state `#N remains open`.
- Avoid negated closing keywords immediately before issue references in PR
  descriptions, comments and commit messages: GitHub can still recognize the
  closing keyword and reference. Express continued scope with `#N remains open`.
  Do not do unreported work.
- After each work run (implementation, tests, review pass), post a status comment
  on the issue or PR: what changed, checks run and results, commit/PR links,
  blockers, and the next action. Do not rely on chat history.

Explicit maintainer project boundaries override the generic routing rule above.
Project 12 alone owns specification #206/#228 and Tools #150. Project 13 alone
owns specification #248/#249, Tools #169/#170 and Janeway plugin #1–#5.
Adam's Galaxy/VGP/GTN work, Tools #171 and its GTN planning child #176, is outside
Project 9. Do not add these through automatic or generic routing. Shared
foundations remain in Project 9 even when those projects consume them; for
example, specification #251 defines shared assembly statistics, not GTN content.

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

Do not push directly to a repository's main branch.

The maintainer's independent-review rule (2026-11-18) applies only to
FAIR-bioHeaders repositories and agents operated by David Molik (`molikd`) or
Adam Wright (`adamjohnwright`). A PR submitted by either maintainer or their
agents may satisfy the approval gate through an independent **different model**:
Copilot, or a model operated by David or Adam. The approving model/agent must be
other than the submitter; an agent must not self-approve its PR, and another
instance of the same model does not satisfy the different-model requirement.
Record author/reviewer model provenance when needed to establish independence.
David and Adam themselves may self-approve their PRs; this exception does not
apply to their agents.

An eligible agent may merge only after that approval requirement is met, all
applicable CI checks are green, and its own validation of the current changes
passes, including changes after review. Recheck the exact head, base branch,
findings and dependencies immediately before merging. Missing checks are not
passing checks, and branch protection must not be bypassed. Read every overall
review and inline finding, reply with its disposition and fix/evidence, resolve
handled threads, and post an overall response. Merge authorization does not grant
contract adoption, curator acceptance, release, publication or deployment
authority; those retain their separate maintainer gates.

Authority: [approval by another, different model](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/268#issuecomment-6984337685)
and [human self-approval exception](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/268#issuecomment-6984418624).

Port source: FAIR-bioHeaders-Specification commit
`0d0d6b43efdee96bc7548f1f7c65fdafb2a31f32` (2026-11-18).

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
shared rules V1-V6 of `docs/SCHEMA-VERSIONS.md`, plus a V7-style opt-in draft
lane (warnings name V7's required pinned commit and SHA-256 digest of the draft
bytes, FAIR-bioHeaders-Tools#162):
with `BIOHEADERS_EXPERIMENTAL_FHT=1` it also reads the recognised draft
contract (FHT-Specification's raw-main `fht.json`, pinned by commit and SHA-256
under `drafts` in `bioheaders/schemas/bundled.json`) and warns on every record so
read; the default is unchanged. V6 needs the record, not just its
`schema` value (an FHR 1 record citing raw-main with `schemaVersion` the number 1
is read as v0.3.1, with a warning), so code that validates a record selects its
schema with `select_record()`/`schema_for()`, never `select(record["schema"])`.
Check this registry and every affected
packaged/compatibility copy when adopting schema support. A current-schema refresh
must not overwrite frozen release snapshots. Keep type/serialization/version
support explicit; success for FHR JSON-LD does not establish FHP/FHGFF3 parity.
That sentence is enforced by `docs/CAPABILITY-MATRIX.md`, generated by
`scripts/render_capability_matrix.py` from the entry points, the CLI's own
subcommand and format tables, `schemas/bundled.json`, `pins.json`, the vendored
per-format manifests and the specification at the tag that registry names, with
each mark cited to a probe that ran during the render or to a test found in the
tree. Change the generator or the registries, never the document by hand:
`--check` fails on drift, `--self-test` fails unless the deliberate defects are
rejected, `tests/capability_matrix_test.py` recomputes the published grid digest
from the published tables and requires every citation that can skip to say when,
and `.github/workflows/capability-matrix.yml` runs all of it against a tag
checkout and the installed commands.
Preserve stdin/pipes and gzip/BGZF handling, bounded processing, exact byte coverage
and ordinary comments when changing sequence readers/writers. Test the changed
input paths, not just a small uncompressed metadata round trip.

- **Cross-repo pin audit (new command, advisory only):** `bioheaders/pins.json`
  enumerates every cross-repo contract reference this repository holds in the five
  classes — the four of FAIR-bioHeaders-Specification#241 (`released-contract`
  (a specification **tag**), `draft-contract` (a commit), `conformance-suite` (the
  suite's own commit) and `base-carrier` (the released schema a draft embeds, at the
  tag it pins)) plus the byte-copied-tree class `copied-tree`
  (FAIR-bioHeaders-Tools#163): a whole vendored directory under one consumer
  provenance record, scored per path by SHA-256 of the authority bytes at the
  named revision — never by size, because same-size/different-digest files are
  the ordinary drift shape — with present-on-one-side counts for
  recorded-but-missing, in-tree-unrecorded, authority-only (`prefixes`
  enumeration) and sibling-record (`against_provenance`) path sets. A copied
  tree of released material pinned at a branch is unusable under rule 1, exactly
  like a released file row; a consumer with **no** provenance record reports
  `ABSENT`, this repository's unrecorded `examples/` tree included. `bioheaders/pin_audit.py` implements
  `bioheaders-pin-audit`, the thirteenth console script (`bioheaders` plus eleven
  `fhr-*` names, which stay frozen and mirrored in `compat/fhr`, plus this one), and
  resolves each row against the authoritative bytes **at that revision**: tags for
  released material, never `main`, because a self-consistency gate cannot detect
  drift both sides share. It reports `FRESH`/`DRIFT`/`ABSENT`, runs a 404 control
  probe on every backend and downgrades a backend that answers the nonsense path,
  probes tracked files for unresolved merge-conflict markers (`git grep -I`),
  labels draft rows `draft, not acceptance`, and writes nothing: exit status is 0
  whatever it finds unless `--exit-on-drift` is passed. Refreshing a pin stays a
  deliberate, dated commit. `.github/workflows/pin-audit.yml` runs it on a schedule
  with every step `continue-on-error`. See docs/PIN-AUDIT.md for the measured table
  and the red/green proof.

`bioheaders-pin-audit --against-default --consumers` adds read-only advisory
content/consumer evidence (Tools#167). A currency verdict requires verified pin
integrity; default-content differences invalidate no historical release pin.
Preserve recorded commit meanings, compare digests rather than ancestry/counts,
and never auto-repin. The known-consumer table is not native acceptance or the
whole-federation inventory. Derived subsets remain conformance-suite
relationships, with declared filters and explicit limits on what was checked.
See `docs/PIN-AUDIT.md`; pin-reconciliation proposals require separate approval.

The `fairbioheaders/{combine,validate,convert,verify}` modules are merged into
`nf-core/modules`; use `nf-core modules install fairbioheaders/<module>` in consuming
pipelines and contribute upstream module changes there. The local modules and the
Dockstore workflow live in
FAIR-bioHeaders/FAIR-bioHeaders-Nextflow (Dockstore entry
`github.com/FAIR-bioHeaders/FAIR-bioHeaders-Nextflow/fair-bioheaders`); make workflow
changes there. The old Dockstore entry for this repository is archived.

The Dockerfile builds from a specified released wheel. `.github/workflows/dockerfile.yml`
builds the newest release's image, so a successful Dockerfile check does not test
unreleased Python changes. Coordinate source tests and explicit candidate-image
checks when both change. `.github/workflows/container.yml` smoke-tests amd64 and
arm64, then publishes released images; follow its tag/latest rules. Runtime,
container and plugin pin changes must state their scope, not silently
upgrade one another. Do not publish an image merely to validate a documentation
change. Keep Python 3.9 CI on a runner with available builds (currently 24.04);
review runtime availability before replacing pinned runner images.
