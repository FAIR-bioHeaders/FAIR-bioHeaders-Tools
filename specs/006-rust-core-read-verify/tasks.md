# Tasks: Phase 1 Rust core, read/validate/verify engine with Python and C bindings

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: required (spec G1 acceptance, SC-001 to SC-010; native-language CI rule).

**Paths**: `core/` = `crates/fair-bioheaders-tools/`, `bundles/` =
`crates/fair-bioheaders-tools-bundles/`, `capi/` =
`crates/fair-bioheaders-tools-capi/`, `py/` = `crates/fair-bioheaders-tools-python/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (M0/M1)

- [x] T001 Workspace: root `Cargo.toml` (members `crates/*`, resolver 3, `rust-version = "1.85"`, edition 2024, shared `[workspace.dependencies]`, release profile `panic = "unwind"`), `rust-toolchain.toml`, `.gitignore` additions (`/target`, `fuzz/target`), crate skeletons for core, bundles, capi, py.
- [x] T002 [P] `deny.toml` per research R9; `cargo deny check` passes on the skeleton.
- [x] T003 [P] `.github/workflows/rust.yml`: fmt, clippy `-D warnings`, test on ubuntu-24.04, ubuntu-24.04-arm, macos-15 and Alpine container, MSRV 1.85 build, cargo-deny, header drift; checks out the specification at `0ae18b00` and `34bbe21a`, sets `FH_REQUIRE_CORPUS=1`; uploads receipts.
- [x] T004 Corpus harness `core/tests/corpus/mod.rs`: locate checkouts from `FH_SPEC_V060`/`FH_SPEC_34BBE21A`, verify manifest SHA-256 and count before running, fail (never skip) when required and missing, per-format accounting, two-way NOT_RUN check, receipt writer to `target/receipts/<label>.json` (data-model Receipt).

## Phase 2: Foundational (blocking)

- [x] T005 `core/src/value.rs`: `Value`, exact `Number` (kind, lexeme, canonical text; hex/octal; `as_i64`, `as_f64` with exactness, `as_bigint`), unit tests for #208 §4 canonical texts.
- [x] T006 `core/diagnostics.toml` + `core/build.rs`: code registry and generated constants; `core/src/report.rs` (Report, LayerResult, NotRunReason, Diagnostic, RuleId, outcome derivation per data-model), `core/src/error.rs`, `core/src/limits.rs`.
- [x] T007 `core/src/framing.rs`: port of `sequence_parts`/`header_text`/`record_marker_warnings` as an incremental push parser (FASTA `;~`, GFA `#~`, GFF3 G1 line 1 and `##FASTA`), BOM refusal, late-header detection with line numbers, header byte/line limits; unit tests for chunk boundaries (CR/LF split across chunks).
- [x] T008 `core/src/checksum.rs`: root checksum-line identification (R2/R3), coverage excluding exactly that line, streaming SHA-512/256 (`sha2` 0.10), canonical padded base64 and R4 canonical check (`ops.rs`).
- [x] T009 `core/src/gzip.rs`: RFC 1952 member reader over `flate2::Decompress` (zlib-rs): FHCRC, FEXTRA/BGZF, multi-member, EOF block, CRC32/ISIZE, trailing garbage and NUL padding policy matching the Python reference; decompressed-byte budget; cancellation check every 1 MiB.
- [x] T010 `core/src/engine.rs`: EngineBuilder/Engine/Verifier/CancelHandle per contracts/rust-api.md; container sniffing; pipeline orchestration and continue-after-failure rules; `verify_bytes/reader/path`; validate early completion.

## Phase 3: User Story 2 — frozen-suite receipt (P1) 🎯 G1 core

- [x] T011 [US2] `core/src/yaml.rs`: saphyr-parser events → exact tree; reject anchors/aliases/tags/merge keys, duplicate keys; R12 `portable_plain_tag` port (YAML 1.2 core vs PyYAML 1.1 resolver incl. y/n, timestamps as strings, leading-zero ints); `%YAML` directive handling as `_Loader.process_directives`; node/depth/scalar limits; locations.
- [x] T012 [P] [US2] `core/src/json.rs`: JSON metadata (serde_json arbitrary_precision) → exact tree, duplicate keys, BOM handling as `_text`, non-finite refusal, limits.
- [x] T013 [US2] `bundles/`: copy the 15 schema files byte-for-byte, `data/bundle.json` (sources, commits, SHA-256, selection table from `bioheaders/schemas/bundled.json`), profiles `python.json` and `test-narrow.json`; test that hashes match and equal the toolkit's copies.
- [x] T014 [US2] `core/src/selection.rs`: port `selection.py` (V1–V7, raw/w3id parsing, unsupported V4 with no fallback, V6 FHR1 numeric `schemaVersion` incl. `true` excluded, near-miss and FHR1 warnings, draft lanes via builder only), profile filtering (`outside-profile`).
- [x] T015 [US2] `core/src/schema.rs`: `jsonschema` 0.63 draft 2020-12, formats asserted, offline registry of bundled resources, `regress` ECMA `pattern`/`patternProperties` keywords, exact-number instance conversion, error → diagnostic with JSON Pointer and rule mapping (R5/R15/P1/G2/…, per Python `validation_message`).
- [x] T016 [US2] `core/src/family.rs`: R17 container/header-type pairing, FHGFF3 G1–G3 (`cross_check` directives), FHP P1–P2, checksum value checks (`check_checksums` R4/C1 placement), FHT C1 exact completeness (`check_fht_completeness`), R14 link-scheme warnings, R11 record-marker warnings.
- [x] T017 [US2] `core/tests/conformance_frozen.rs` and `conformance_source.rs`: run every non-JSON-LD/microdata vector in both operations as the manifest requires (valid: accepted, checksum equal, listed metadata equal; invalid: rejected; `unsupported-version`: outcome unsupported; `warnings`: diagnostic with that rule); receipts. Target: 228/63 and 254/65, 0 failed.
- [x] T018 [P] [US2] `core/tests/reader_policy.rs`: the 64 C-POLICY cases at `34bbe21a` (cases.json digest check, payload digest check per case), receipt.
- [x] T019 [US2] Guard tests: tampered manifest digest, wrong count, zero vectors, undeclared skip and NOT_RUN two-way mismatch each make the harness fail (run against temporary modified copies).

## Phase 4: User Story 3 — exact numbers (P2)

- [x] T020 [P] [US3] `core/tests/precision.rs`: every #208 §4 row through `verify_bytes` (value text, lexeme, `1.0` integer, `1.10`, R13 cases, `schemaVersion: true`, C1 above 2^53−1 in python profile exact and in a 53-bit test profile `LIMIT.consumer-integer`), the >309-digit vector recorded as `NOT_RUN(spec-undecided)` in the receipt.

## Phase 5: User Story 4 — structured results (P2)

- [x] T021 [P] [US4] `core/tests/diagnostics_registry.rs`: registry rules ⊆ pinned manifest `rules` (+C1), every emitted code across all corpora is registered, codes append-only check against a committed snapshot.
- [x] T022 [P] [US4] `core/tests/outcomes.rs`: R2 double checksum location, V4 unsupported with schema blocked, limit vs invalid, pipeline order with schema + checksum errors, Validate checksum `NotRun(not-requested)`.

## Phase 6: User Story 5 — bounded resources (P2)

- [x] T023 [P] [US5] `core/tests/limits.rs`: each limit at boundary and boundary+1, lowering and explicit raising recorded in provenance, decompression bomb under the 1 GiB buffer limit, >4 GiB synthetic streamed input (ignored-by-default heavy test run in CI nightly), cancellation from another thread.
- [x] T024 [P] [US5] `core/tests/gzip_controls.rs`: CRC, truncation, trailing garbage, NUL padding, FHCRC, multi-member, BGZF EOF, each with its expected outcome citing R1.

## Phase 7: User Story 7 — C ABI and standalone use (P3)

- [x] T025 [US7] `capi/src/lib.rs`: every function of contracts/fhcore.h with `catch_unwind`, handle type tags (debug), owned error objects, borrowed outputs with trailing NUL, stream poisoning; `cbindgen.toml` and committed `include/fhcore.h`; SONAME `libfhcore.so.0`.
- [x] T026 [P] [US7] `capi/tests/header_smoke.rs` (compile the header with `cc` and link a C caller), `abi_harness.rs` (NULL args, zero-length/NUL/non-UTF-8 input, value tree, release-NULL no-ops, 10^4-iteration leak loop), `projection.rs` (C-ABI projection == safe-API Report for every corpus vector).

## Phase 8: User Story 6 — containment (P3)

- [x] T027 [US6] `fault-injection` feature: `fh_test_panic`, a core test-only panic trigger, Python `_native._test_panic`; tests that the C ABI returns `FH_E_INTERNAL`, a panicked stream then returns `FH_E_STATE`, Python raises `InternalError` and continues; a test asserting release builds lack the symbol. Containment limits documented in `capi/README.md`.

## Phase 9: User Story 1 — Python users unchanged (P1)

- [x] T028 [US1] `py/`: PyO3 0.30 abi3-py39 extension and `python/fair_bioheaders_tools/__init__.py` per contracts/python-api.md (GIL released, eager conversion, exact ints, float or Decimal, exception classes).
- [x] T029 [US1] `py/tests/`: pytest installed-wheel acceptance — import from outside the checkout guard, frozen suite through the binding with Python-native digest/count/receipt/two-way NOT_RUN guards and skip-as-failure, precision rows, exceptions, threads, stream cancel, bytes/NUL/len-0 inputs.
- [x] T030 [US1] `bioheaders/_engine.py` + hooks in `bioheaders/__init__.py` and `bioheaders/cli.py`: `set_engine`/`engine()`/`BIOHEADERS_ENGINE`, mapping Report → today's values, exceptions (`jsonschema.ValidationError` with `json_path`), warnings and exit codes; `ImportError` when the engine is missing or mismatched.
- [x] T031 [US1] `tests/engine_backend_test.py` and a CI job running the whole toolkit suite with `BIOHEADERS_ENGINE=rust`; document every test whose expectation differs only by the decision-9 dispositions (uri, pattern) — no other expectation edited.
- [x] T032 [P] [US1] `.github/workflows/engine-python.yml`: maturin wheels (manylinux_2_28 x86_64/aarch64, musllinux_1_2, macOS arm64), install in clean venvs outside the checkout on Tier-1 runners, glibc-2.28 container and Alpine; run `py/tests` and the toolkit suite in both modes; supplemental differential job vs the pure-Python reader (non-required).

## Phase 10: Polish and G1 evidence (M7)

- [ ] T033 [P] Decision-9 regression vectors (uri with/without `rfc3987`, ECMA `pattern` cases incl. non-ASCII `\d` and `$` before final LF) in `core/tests/vectors/` and the toolkit tests.
- [x] T034 [P] `fuzz/`: targets framing, yaml, gzip, verify; run ≥1 CPU-hour each; record results on #212.
- [ ] T035 [P] `py/bench/verify_bench.py`; run SC-006/SC-007 measurements; record on #212.
- [ ] T036 [P] `crates/*/README.md`, CHANGELOG Unreleased entry, AGENTS.md Rust section (build, test, corpus variables).
- [ ] T037 G1 checklist evidence comment on #212/#213/#205 (receipts, CI run ids, platforms, deny, vet report, fuzz, bench, cost entry for #209); request independent review by another model; disposition findings; mark the PR ready only when every G1 item holds.

## Dependencies

T001 → T004–T010 → T011–T016 → T017–T019 (G1 corpus) → T020–T024;
T010 → T025–T027; T010 → T028 → T029 → T030 → T031 → T032; T033–T037 last.

## Implementation notes (2026-11-26)

- T006: the registry is the `registry!` table in `core/src/diagnostics.rs`
  (57 codes); `core/diagnostics.snapshot.json` is the committed append-only
  snapshot (`FH_UPDATE_SNAPSHOT=1` adds new codes), not a TOML file plus build
  script.
- T017: the frozen v0.6.0 suite gives 198 passed plus 30 valid vectors
  superseded by the specification's R4 retirement crosswalk (each verified),
  pending the maintainer decision reported on #212; the current suite gives
  254/254.
- T018: the reader-policy tree is byte-identical at all three pins (research R10).
- T030: in engine mode a failure replays the Python reader for byte-identical
  exceptions; `BIOHEADERS_ENGINE_TRACE` records any engine-only rejection.
- T034: `fuzz/` (cargo-fuzz, scheduled CI) plus `core/tests/robustness.rs`, a
  deterministic mutation test (3,000,000 rounds locally: no panic; chunked and
  one-shot reads agree).
- Extra: `core/tests/fht_lane.rs` runs the published FHT v0.7.0 lane (89 run
  and passed; 4 C3 parent-link vectors declared NOT_RUN).
