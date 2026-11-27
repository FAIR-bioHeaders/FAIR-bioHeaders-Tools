# Agent instructions

## Current repository context

This is the active family toolkit, including installed commands and the Claude
Code plugin. The former FHR-File-Converter repository name redirects here (verified 2026-11-20); it is not a deleted repository.
Redirects are not a guarantee against future reuse of the old name. The shared specification publishes
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

## Rust core (Project 14 Phase 1, development branch `p14-rust-core`)

`Cargo.toml` is a workspace of four crates under `crates/` (specs/006): `fair-bioheaders-tools` (the
read/validate/verify engine: framing, SHA-512/256 coverage, portable YAML/JSON with exact numbers,
gzip/BGZF, V1–V7 selection, JSON Schema 2020-12 with ECMA-262 `pattern`, family predicates),
`fair-bioheaders-tools-bundles` (byte copies of the selected schemas with `data/bundle.json` digests and
the consumer profiles; regenerate with `tools/refresh_bundle.py`, never edit schema bytes),
`fair-bioheaders-tools-capi` (`libfhcore`, `include/fhcore.h` generated by cbindgen) and
`fair-bioheaders-tools-python` (the PyO3 `fair-bioheaders-tools` wheel, built with maturin). MSRV is 1.85;
`rust-toolchain.toml` pins the release toolchain; `cargo deny check` must pass. The engine reads no
environment variables and does no network access.

```bash
export FH_SPEC_V060=<Specification checkout at 0ae18b00> FH_SPEC_34BBE21A=<checkout at 34bbe21a>
cargo test --workspace --exclude fair-bioheaders-tools-python --locked   # receipts in target/receipts/
maturin build --release -m crates/fair-bioheaders-tools-python/Cargo.toml -o dist
pip install dist/*.whl && (cd /tmp && pytest <repo>/crates/fair-bioheaders-tools-python/tests)
BIOHEADERS_ENGINE=rust poetry run pytest   # the toolkit suite with the opt-in engine backend
```

A missing corpus is a failure, never a skip (`FH_ALLOW_MISSING_CORPUS=1` exists for local work outside
CI only). Expectations come only from the specification manifests; never regenerate them from engine or
toolkit output. Diagnostic codes in `crates/fair-bioheaders-tools/src/diagnostics.rs` are append-only
(`diagnostics.snapshot.json`). The toolkit's default backend stays the pure-Python reader;
`bioheaders/_engine.py` is the opt-in adapter and moves to Tools-Python with the toolkit.

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

When a PR receives code review (human or model):

1. Read the overall review and every inline comment before changing anything.
2. Make each fix in a **new commit**. Do not amend or force-push over reviewed
   commits; if a rebase is required, cite the new head in the replies.
3. Reply to each inline finding with the fix and the relevant commit hash.
4. Resolve that inline comment/thread.
5. After all findings are handled, post an overall reply to the review
   summarizing each finding's disposition and the commits.
6. Treat optional suggestions as required unless they are genuinely out of
   scope; state why and link a follow-up issue.

### Project 14 PR receipt (maintainer decision, 2026-11-25)

Every Project 14 PR (the Rust core and wrapper migration, including the
development-branch PR to `main`) fills in the `p14-receipt v1` block from
`.github/pull_request_template.md`: work package, class, author model/agent,
independent reviewer model(s), review and fix rounds, model usage, human time
bucket and current-head CI evidence. Usage and time may be given as an
`estimate` or as `unavailable`; label estimates and never write a missing value
as 0. Update the block when review or fix rounds change. Other PRs omit it.
A missing block counts against receipt coverage in the Tools#209 ledger rather
than failing CI. Design and field definitions:
[FAIR-bioHeaders-Tools#209](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/209).

## Agent review and human-only PR merges (maintainer direction, 2026-11-20)

[Authoritative Round 16 policy and plan](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/211#issuecomment-7042896529) supersedes the former conditional agent-merge authorization.
This rule applies to all repositories and operators, including FAIR-bioHeaders,
external upstream repositories and personal forks. This is a rule for agent
behavior, not a claim of ownership of upstream projects or permission to edit
their policy. Respect upstream contribution rules and write permissions too.

Agents must never merge pull requests. A human performs the merge. Agents must
not enable auto-merge, enter a merge queue, use another agent/service as a merge
proxy, or push directly to a default branch instead of merging a PR. Model
review never grants an agent merge authority. Preserve platform protections;
do not forge approval or work around repository permissions.

Every PR receives independent review from another actual model. Prefer another
model family, for example Qwen or Gemma reviewing Codex work, but a different
family is a preference rather than a hard requirement. A second session of the
same model is not another model. Record actual author/reviewer model identities
and never invent review provenance.

Agents continue monitoring CI and fixing failures and actionable review
findings. Read overall and inline reviews, fix in new commits, reply with
disposition/evidence, resolve handled findings and acknowledge clean reviews with a comment and validation summary.
Validate the current head after changes; hand the human exact head/base,
review, CI, dependency and remaining-risk information. Missing, failed and
NOT_RUN checks are not passes. Contract adoption, curator acceptance and
publication keep their separate authority and gates.

Port the current policy through live AGENTS and applicable existing LLM/llms,
plugin/skill, contribution and workplan guidance. The six specification holders
remain semantically in step, not byte-identical; preserve local sections.
Immutable published/vendored historical instruction copies keep their bytes
and provenance and are explicitly non-operative from current parent guidance.
Their older text never authorizes an agent merge. Earlier rounds' authorized
merges and dated receipts remain historical facts, not future permission.


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

Current release preparation deliberately bundles actual specification v0.6.1,
v0.7.0 and v0.8.0 tag artifacts, with FHT 1.0 available by default through shared
publication citations. Owning FHT raw-main remains a distinct historical V7 lane;
its switch does not gate published FHT. Fixed FHT HTML itemtype is the schema
`$id` at v0.7.0, including when later family releases repeat that same contract.
No FHT JSON-LD/context/DCMI adoption follows. External w3id redirect deployment
is independent and remains unverified here. Native FHGM0.1 is separately bundled from actual v0.8.0; toolkit 0.13.1 is published; future publication
remains separate. Do not add an FHGM header registry row.

`bioheaders/schemas/bundled.json` selects immutable released schemas and
historical snapshots. Current family release v0.8.0 repeats the four header
contracts from v0.7.0; normal FHT 1.0 support ships in toolkit 0.13.1.
`bioheaders/selection.py` implements record-aware selection: use
`select_record()`/`schema_for()`, never just `select(record["schema"])` when
validating a record. Shared selection rules V1–V6 are defined in the publication authority
`docs/SCHEMA-VERSIONS.md`. V6 needs the entire record: an FHR 1 record citing
raw-main with numeric `schemaVersion: 1` selects v0.3.1 with a warning. The
historical V7-style owning FHT replay uses `BIOHEADERS_EXPERIMENTAL_FHT=1`
and `bundled.json`'s `drafts.FHT` immutable commit/SHA-256 pins; warnings name
both (Tools #162). Nothing in this packet removes that lane.
Historical owning FHT replay remains explicitly opt-in;
native FHGM 0.1 is a separate model contract, behind its independent gate, not a
fifth header schema. See docs/FHT-PUBLICATION-CANDIDATE.md and docs/FHGM-MODEL.md.
Preserve frozen snapshots, exact-byte fixtures, pins and provenance. Keep
serialization and layer support explicit; a base-header/checksum pass does not
establish model or biological validation. Preserve stdin/pipes and gzip/BGZF,
bounded processing, exact byte coverage and ordinary comments. Test changed
input paths rather than only small metadata round trips.

Type/transport/version support is enforced by `docs/CAPABILITY-MATRIX.md`, generated by
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

- **FHGM model checks (opt-in, `bioheaders/fhgm.py`):**
  `BIOHEADERS_EXPERIMENTAL_FHGM=1` enables model checks; published native 0.1
  from shared v0.8.0 is selected through `modelContracts.FHGM`, outside the
  four-header registry. `BIOHEADERS_FHGM_CONTRACT=draft` explicitly replays
  unchanged historical owning V7 bytes and warnings; unknown selections fail.
  No FHGM header schemaVersion or in-record schema field is added. Model,
  released FHGFF3 base, checksum and feature/biology results stay separate;
  feature/biology is always not-run here. A closed implementation gate does not
  evaluate model rules. Preserve the accepted v0.5.0/v0.6.0 carrier allowlist,
  historical92-suite and original291 payloads. Native92×2-base tests reuse the
  digest-pinned owning twin derivation, not a second model validator. See
  `docs/FHGM-MODEL.md`; publication, installed package and downstream promotion
  remain separately measured steps.

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
  `bioheaders-pin-audit`, the thirteenth console script (`bioheaders` plus twelve
  `fhr-*` names, which stay frozen and mirrored in `compat/fhr`, plus this one), and
  resolves each row against the authoritative bytes **at that revision**: tags for
  released material, never `main`, because a self-consistency gate cannot detect
  drift both sides share. It reports `FRESH`/`DRIFT`/`ABSENT`, runs a 404 control
  probe on every backend and downgrades a backend that answers the nonsense path,
  probes tracked files for unresolved merge-conflict markers (`git grep -I`),
  labels draft rows `draft, not acceptance`, and writes nothing: exit status is 0
  whatever it finds unless `--exit-on-drift` is passed. Refreshing a pin stays a
  deliberate, dated commit. `.github/workflows/pin-audit.yml` runs it on a schedule;
  findings never fail the job, but a crash of the audit (exit 2) does. See
  docs/PIN-AUDIT.md for the measured table and the red/green proof.

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
