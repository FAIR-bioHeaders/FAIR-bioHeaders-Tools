# Data Model: Phase 1 Rust core

**Feature**: [spec.md](spec.md) | **Date**: 2026-11-26

Names are the Rust names in crate `fair-bioheaders-tools`; the C ABI and the
Python binding project the same entities ([contracts/](contracts/)).

## EngineBuilder → Engine

| Field | Type | Rule |
| --- | --- | --- |
| `profile` | profile id (string) | default `python`; must exist in the bundle's profile table, else `EngineError::IncompatibleProfile` |
| `limits` | `Limits` | defaults below; lowering allowed; raising needs `raise_limit` and is recorded |
| `draft_lanes` | set of lane ids (`fht`, `fhgm`) | must be allowed by the profile, else `IncompatibleProfile` |

`Engine` is immutable, `Send + Sync`, holds the compiled schemas and patterns
for its profile, and is cheap to share.

## Limits (`LimitKind`)

| Kind | Default | Unit |
| --- | --- | --- |
| `HeaderBytes` | 1,048,576 | bytes of header lines incl. terminators |
| `HeaderLines` | 10,000 | lines |
| `YamlNodes` | 20,000 | nodes (scalars + collections) per document |
| `YamlDepth` | 64 | nesting levels |
| `MetadataBytes` | 67,108,864 | bytes after decompression |
| `InMemoryDecompressedBytes` | 1,073,741,824 | bytes buffered decompressed |
| `ScalarBytes` | = `HeaderBytes` | bytes of one scalar |
| `ConsumerExactIntegerBits` | unset | bits (53 for an R profile) |

Validation: a value of 0 is `InvalidArgument`. `limits_applied` in the
provenance lists every kind with its value and whether it was raised.

## Operation, Container

- `Operation`: `Validate` (no checksum layer) | `Verify`.
- `Container`: `Auto` | `Fasta` | `FhpFasta` | `Gfa` | `Gff3` | `MetadataYaml`
  | `MetadataJson`. `Auto` sniffs from content: gzip magic is unwrapped first;
  `;~` first-line prefix → FASTA family (FHR or FHP decided by selection),
  `#~` → GFA, `##gff-version` → GFF3, `{`/`[` → JSON metadata, otherwise YAML
  metadata. The FASTA family's FHR/FHP split is a selection result (R17), not
  a container choice; `FhpFasta` is accepted as an explicit hint and checked
  against R17.

## Report

| Field | Type | Notes |
| --- | --- | --- |
| `outcome` | `Outcome` = `Valid` \| `Invalid` \| `Unsupported` \| `Limit` | derived, rules below |
| `layers` | `[LayerResult]` in fixed order | Framing, Yaml, Selection, Schema, Family, Checksum, Model |
| `diagnostics` | `[Diagnostic]` | pipeline order |
| `selection` | `Option<Selection>` | |
| `checksum` | `Option<ChecksumResult>` | |
| `metadata` | `Option<Value>` | exact tree |
| `provenance` | `Provenance` | |

`LayerResult { layer, status: Pass|Fail|NotRun|Unsupported|Limit, not_run_reason: Option<NotRunReason> }`

`NotRunReason`: `NotRequested` | `BlockedBy(Layer)` | `OutsideEngineScope(format)` |
`OutsideProfile(release_or_lane)` | `SpecUndecided(topic)`.

**Outcome derivation** (FR-046):
1. any layer `Limit` → `Limit`;
2. else selection `Unsupported` → `Unsupported` (schema `NotRun(BlockedBy(Selection))`);
3. else any `Fail` → `Invalid`;
4. else any required layer `NotRun` → `Invalid` + `NOTRUN.required-layer`;
5. else `Valid`.

Required layers: Validate = Framing, Yaml, Selection, Schema, Family;
Verify adds Checksum. Model is never required in Phase 1 (`NotRun(OutsideEngineScope("model"))`).

**Continue-after-failure**: after a Framing failure that prevents locating the
header block, later layers are `NotRun(BlockedBy(Framing))`; a Yaml failure
blocks Selection, Schema and Family but **not** Checksum (the covered bytes are
still defined); Schema failures do not block Family or Checksum.

## Diagnostic

| Field | Type |
| --- | --- |
| `severity` | `Error` \| `Warning` |
| `code` | `&'static str` from the registry, e.g. `R2.multiple-checksum-lines` |
| `rule` | `Option<RuleId>` |
| `layer` | `Layer` |
| `message` | `String` (informative only) |
| `location` | `{ header_line: Option<u64>, byte_offset: Option<u64>, byte_len: Option<u64>, json_pointer: Option<String> }` |

`RuleId`: closed enum R1–R17, V1–V7, J1–J9, M1–M5, P1–P2, G1–G3, C1, K1–K6, B1.

**Registry** `crates/fair-bioheaders-tools/diagnostics.toml`: one table per
code with `rule` (or `"none"` for `LIMIT.*`, `IO.*`, `INPUT.*`, `NOTRUN.*`),
`layer`, `severity`. Append-only; a test checks rules against the pinned
manifest `rules` table (plus C1 from the FHT source) and that every code the
engine can emit is registered (codes are `const`s generated from the file by a
build script).

## Selection

`{ header_type: FHR|FHP|FHGFF3|FHT, release: Option<String>, schema_file: String,
schema_sha256: String, rule: V1..V7, draft: bool }`.

## ChecksumResult

`{ stated: Option<String>, computed: Option<String>, matches: Option<bool>, covered_bytes: u64 }`.
`computed` is present whenever the checksum layer ran; `matches` is `None` when
no checksum is stated.

## Value (exact metadata tree)

`Null | Bool(bool) | Number(Number) | String(String) | Array(Vec<Value>) | Object(Vec<(String, Value)>)`
(object keys in source order; duplicates impossible by construction).

`Number { kind: Int | Decimal, lexeme: String, canonical: String }` with
accessors `as_i64() -> Option<i64>`, `as_f64() -> (f64, exact: bool)`,
`as_bigint()` (Int only). Canonical text: integers `-?[0-9]+` without leading
zeros (hex/octal lexemes converted); decimals the exact value with trailing
zeros removed and no exponent unless the exponent form is shorter by the
#207 §4 rule (decided in the contract test vectors).

## Provenance

`{ engine_version, abi_version, bundle_id, bundle_manifest_sha256, spec_commit,
profile_id, profile_sha256, limits_applied }`.

## Contract bundle (crate `fair-bioheaders-tools-bundles`)

- `data/` holds byte copies of each bundled schema (15 files today, the same
  bytes as `bioheaders/schemas/` and the root copies) and
  `data/bundle.json`: for each file its specification source (repository,
  commit, path), SHA-256, header type, release and status
  (`released`/`draft`/`model`), plus the selection table (releases → files)
  ported from `bioheaders/schemas/bundled.json`.
- `data/profiles/python.json`, `data/profiles/test-narrow.json`: profile
  definitions; their SHA-256 is the profile digest.
- `bundle_id` = `"fhb-" + first 16 hex of SHA-256(bundle.json)`.
- A build-time test verifies every file's SHA-256 against `bundle.json` and
  that the bundled copies equal the toolkit's copies (while both live in Tools).

## Stream state machine (`Verifier`)

`Open → (feed)* → Finished | Cancelled | Poisoned`. `feed` returns
`NeedMore` or `Complete` (Validate after the header block). After `finish`,
`Cancelled` or a contained panic (`Poisoned`), any further `feed` is
`EngineError::State`.

## Receipt (test harness, not engine)

```json
{ "corpus": "C-FROZEN", "manifestSha256": "...", "specCommit": "...",
  "engineVersion": "...", "abiVersion": "0.1", "bundleId": "...", "profileId": "python",
  "platform": "x86_64-unknown-linux-gnu", "packageVersion": null,
  "perFormat": { "fasta": {"total": 98, "run": 98, "passed": 98, "failed": 0, "notRun": {}} },
  "notRun": { "outside-engine-scope:jsonld": 37, "outside-engine-scope:microdata": 26 },
  "runner": { "tests": 0, "failed": 0, "errored": 0, "skipped": 0 }, "ciRunId": null }
```
