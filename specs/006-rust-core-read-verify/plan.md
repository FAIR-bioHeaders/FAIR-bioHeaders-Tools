# Implementation Plan: Phase 1 Rust core, read/validate/verify engine with Python and C bindings

**Branch**: `p14-rust-core` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-rust-core-read-verify/spec.md`

## Summary

Port the toolkit's read/validate/verify pipeline (header framing and
SHA-512/256 coverage, portable YAML/JSON loading with exact numbers, strict
gzip/BGZF, record-aware V1–V7 selection over digest-pinned bundles, draft
2020-12 validation with asserted formats and ECMA-262 patterns, family
predicates and FHT C1) into one Rust engine in a new Cargo workspace in Tools.
Expose it as a safe Rust API, a C ABI (`libfhcore`, `fhcore.h`) and a PyO3
abi3 extension (`fair-bioheaders-tools`), add an opt-in engine backend to the
`fair-bioheaders` toolkit with the default unchanged, and prove G1 with
Rust-native L1 receipts (frozen 198 passed + 30 superseded-by-crosswalk / 63
NOT_RUN per G1-D1, 254/65 current, 64 reader-policy) and
Python-native installed acceptance in both toolkit modes. Technical choices
are in [research.md](research.md).

## Technical Context

**Language/Version**: Rust, edition 2024, MSRV 1.85 (`rust-version`), release
toolchain pinned in `rust-toolchain.toml`; Python ≥ 3.9 for the binding and
toolkit.

**Primary Dependencies**: `saphyr-parser` 0.4 (YAML events), `serde_json` 1
(`arbitrary_precision`), `num-bigint` 0.4, `jsonschema` 0.63
(`default-features = false`, `arbitrary-precision`), `regress` 0.12,
`flate2` 1.1 (`zlib-rs`), `sha2` 0.10, `data-encoding` 2; `pyo3` 0.30
(`abi3-py39`) with `maturin`; dev/CI: `cbindgen`, `cargo-deny`, `cargo-fuzz`,
`cc` (header smoke test).

**Storage**: N/A (bundled read-only data compiled into the binary).

**Testing**: `cargo test` (unit, L1 conformance with receipts, C-ABI harness,
projection equality, fault injection behind a `fault-injection` feature);
`pytest` against the installed wheel and the toolkit suite in both modes.

**Target Platform**: Tier 1 linux x86_64/aarch64 glibc and macOS arm64;
Alpine musl and the glibc 2.28 floor for the wheel; Tier 2 Windows x86_64 and
macOS x86_64 for Python only (#210 §2, decisions 17, 20).

**Project Type**: library (Rust crate + C library + Python extension).

**Performance Goals**: verify time through Python within 20% of the
pure-Python reader on x86_64 for ≥2 GiB inputs, memory bounded per SC-007
(SC-006 as amended by G1-D3, [specification#296 comment 7206358624](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7206358624); the original goal was ≥ the
Python reader's throughput).

**Constraints**: retained memory independent of file size (<256 MiB, SC-007);
offline, no environment reads in the engine; no panics across FFI; exact
numbers; frozen fixtures and expectations untouched.

**Scale/Scope**: 4 sequence containers × 3 transports + 2 metadata formats;
15 bundled schema files; ~350 corpus vectors plus targeted vectors.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status |
| --- | --- |
| I. Specification is the contract | Pass: expectations come only from pinned specification manifests; bundled schemas are byte copies with recorded commit and SHA-256; no schema/field change. |
| II. Exact bytes and one reading | Pass: framing ported from `sequence_parts`; metadata read from the hashed lines; checksum over exact bytes, SHA-512/256 only. |
| III. Fail closed on untrusted input | Pass: anchors/aliases/tags/merge keys/duplicates rejected before construction; limits enforced before allocation; limit is its own outcome. |
| IV. Preserve metadata and typed values | Pass: exact numeric tree with lexemes; Python default types unchanged. |
| V. Compatible, small, tested | Pass with note: the toolkit gets an opt-in backend only; default unchanged; public names untouched. New dependencies are in the Rust engine and the separate `fair-bioheaders-tools` distribution, not in `fair-bioheaders`' required dependencies. |
| Verification gates | The existing Python gates (pytest, ruff, isort, black, build on 3.9 and 3.13) still apply to the toolkit adapter; Rust gates (`cargo fmt --check`, `clippy -D warnings`, `cargo test`, `cargo deny`, MSRV build) are added for the workspace. |
| Decision boundaries | No publication, tag, release or deployment; agents never merge. |

Post-design re-check: unchanged (pass).

## Project Structure

### Documentation (this feature)

```text
specs/006-rust-core-read-verify/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── rust-api.md
│   ├── fhcore.h
│   └── python-api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
Cargo.toml                      # workspace: members crates/*, resolver 3
Cargo.lock
rust-toolchain.toml
deny.toml
crates/
├── fair-bioheaders-tools/      # core safe API (lib fair_bioheaders_tools)
│   ├── diagnostics.toml        # code registry
│   ├── build.rs                # generates code constants from the registry
│   ├── src/
│   │   ├── lib.rs  engine.rs  report.rs  limits.rs  error.rs
│   │   ├── framing.rs          # sequence_parts port, header lines, late headers
│   │   ├── checksum.rs         # R1–R4 coverage, SHA-512/256, canonical base64
│   │   ├── gzip.rs             # member framing over raw inflate
│   │   ├── yaml.rs             # events → exact tree; R8/R12/R13; limits
│   │   ├── json.rs             # JSON metadata → exact tree
│   │   ├── value.rs            # Value, Number (exact)
│   │   ├── selection.rs        # V1–V7, profiles, near-miss
│   │   ├── schema.rs           # jsonschema + regress pattern keywords + formats
│   │   ├── family.rs           # P/G/R17 container predicates, FHT C1, GFF3 checks
│   │   └── ops.rs              # named shared operations
│   └── tests/
│       ├── corpus/mod.rs       # pinned-corpus loader, digest/count guards, receipts
│       ├── conformance_frozen.rs  conformance_source.rs  reader_policy.rs
│       ├── precision.rs  limits.rs  diagnostics_registry.rs  gzip_controls.rs
│       └── vectors/            # Tools-owned targeted vectors (each cites a spec line)
├── fair-bioheaders-tools-bundles/   # data/ schema copies, bundle.json, profiles/
├── fair-bioheaders-tools-capi/      # cdylib+staticlib "fhcore", include/fhcore.h, cbindgen.toml
│   └── tests/abi_harness.rs  header_smoke.rs  projection.rs  fault_injection.rs
└── fair-bioheaders-tools-python/    # PyO3 extension, pyproject.toml (maturin)
    ├── python/fair_bioheaders_tools/__init__.py
    ├── src/lib.rs
    ├── tests/                  # pytest, installed-wheel acceptance + frozen suite + receipts
    └── bench/verify_bench.py
fuzz/                           # cargo-fuzz targets (not a default member)
bioheaders/_engine.py           # toolkit opt-in backend adapter (ported to Tools-Python later)
tests/engine_backend_test.py    # toolkit-side adapter tests
.github/workflows/rust.yml      # fmt, clippy, test (Tier-1 + Alpine), MSRV, deny, header drift
.github/workflows/engine-python.yml   # wheel build + installed acceptance (+ glibc 2.28, Alpine)
```

**Structure Decision**: #206 D5 layout with the Clarification Q2 names. The
toolkit adapter lives beside the toolkit until the relocation (research R7).
No existing Python file outside `bioheaders/__init__.py` (one `set_engine`
hook), `bioheaders/cli.py` (dispatch through the hook) and the new adapter is
modified. No release or publish workflow is added.

## Phased delivery (milestones and pushes)

1. **M0 plan/tasks** pushed; draft PR to `main` opened with the receipt block.
2. **M1 bytes**: workspace, framing, checksum, gzip/BGZF; Rust tests for
   R1–R4 and gzip controls; checksum layer passes all valid vectors.
3. **M2 YAML/values**: exact tree, R8/R12/R13, limits; precision vectors.
4. **M3 selection/validation**: bundles, V1–V7, schema with ECMA patterns and
   formats, family predicates, C1; full L1 receipts (frozen 198 + 30
   superseded / 63 per G1-D1, 254/65, 64).
5. **M4 C ABI**: header, harness, projection equality, fault injection.
6. **M5 Python**: PyO3 wheel, installed pytest acceptance with frozen suite.
7. **M6 toolkit opt-in**: adapter; toolkit suite in both modes; supplemental
   differential; benchmark.
8. **M7 G1 evidence**: CI on Tier-1/Alpine/glibc 2.28, cargo-deny, fuzz hours,
   cost entry; independent review; PR marked ready only when the G1 list holds.

Each milestone ends with a push to `p14-rust-core` and a handoff comment on
#212/#213.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Four crates instead of one | Clarification Q2; bundles versioned as data; cdylib/staticlib and Python extension need their own crate types | One crate with features would mix crate types and make the C ABI and Python build each other's dependencies |
| Own gzip member framing | Spec-visible member/trailer outcomes (R1) | `MultiGzDecoder` hides trailing-garbage and padding decisions |
