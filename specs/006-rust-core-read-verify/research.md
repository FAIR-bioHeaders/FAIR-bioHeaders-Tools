# Phase 0 Research: Phase 1 Rust core

**Feature**: [spec.md](spec.md) | **Date**: 2026-11-26

Crate facts below were read from the crates.io API on 2026-11-26 (version,
declared `rust-version`, licence). Specification facts were read from shallow
checkouts of FAIR-bioHeaders-Specification at `34bbe21a` and `0ae18b00`
(tag `v0.6.0`). Python reference facts are from Tools `1f3cf7c2`
(toolkit 0.13.1). Every dependency choice still needs the corpus parity
evidence of #210 §1(f) before G1; a choice that fails it is replaced, never
patched over by editing an expectation.

## R1. YAML parser

**Decision**: `saphyr-parser` 0.4.1 (MIT OR Apache-2.0, MSRV 1.85), used only
at the **event level**. The engine builds its own value tree from events and
applies the toolkit's portability rules itself:

- any anchor, alias, explicit tag (`!`, `!!`) or merge key (`<<`) is an error
  (R8; constitution III), detected from the event's anchor id/tag before any
  node is built, so no alias is ever expanded;
- duplicate mapping keys are an error (R8), compared after scalar resolution as
  PyYAML's constructor does (`_Loader.construct_mapping`);
- plain scalars are typed with the R12 rule ported from
  `bioheaders/__init__.py:430-470` (`portable_plain_tag`): the YAML 1.2 core
  tag and the YAML 1.1 tag (PyYAML resolver plus `y/n`) must agree, timestamps
  stay strings, leading-zero integers are refused; disagreement is R12 invalid;
- the plain scalar's text is the number's **source lexeme**; quoted scalars are
  always strings;
- node count (20,000) and depth (64) are counted on events, before allocation;
- `%YAML` directives follow `_Loader.process_directives` (the reader-policy
  corpus has YAML-directive cases);
- U+0085/U+2028/U+2029 in a header line are rejected before parsing
  (`header_text`).

**Rationale**: the engine needs syntax-level control (#212 criterion 2):
events expose scalar style, anchor and tag, and the marker positions give line
and byte locations for diagnostics. Building our own tree means no
alias/merge expansion can happen before the checks. `saphyr-parser` is the
maintained successor of `yaml-rust`, matches MSRV 1.85 and the licence
allowlist, and has no unsafe-expansion API to misuse.

**Alternatives considered**:
- `yaml-rust2` 0.13.2: same lineage and MSRV; its loader builds whole
  documents (expanding aliases) and its event API is the older one. Kept as the
  fallback if `saphyr-parser` fails parity.
- `serde_yaml`: deprecated (`0.9.34+deprecated`), excluded by #210.
- `yaml_serde` / `serde_yml`: serde-level only; no access to styles, anchors or
  lexemes, so R8/R12 and exact numbers cannot be enforced before conversion.
- `libyaml-safer`: non-standard licence on crates.io; needs a reviewed
  exception (#210 §1).

**Parity risk**: the Python reference parses with PyYAML (a YAML 1.1 parser),
while `saphyr-parser` is YAML 1.2. Inside the R12-portable subset they agree by
construction of the rule, but syntax-level edge cases (indentation of
continuation lines, tabs, flow-collection details, wrapped quoted scalars) may
differ. Mitigation: the corpora (frozen, current, reader-policy) plus a
supplemental differential job (`supplemental-yaml-pyyaml`) that feeds the
Julia/Tools YAML differential cases (#208 §7) through both and reports
divergences. Any divergence becomes a vector cited to the specification, or a
spec question; it is never resolved by silently copying PyYAML.

## R2. Exact numbers

**Decision**: the engine's value tree stores each number as
`Number { kind: Int | Decimal, lexeme: String, canonical: String }` with
integers parsed into `num-bigint` 0.4 (`BigInt`) and decimals kept as an exact
decimal (`BigInt` mantissa plus base-10 exponent), canonical text per #207 §4.
JSON metadata is parsed by `serde_json` with `arbitrary_precision` (numbers
keep their source text), then converted into the same tree; JSON duplicate keys
are rejected as in `_unique_object`.

R13: a decimal whose binary64 rounding overflows to infinity is invalid
(R13), `.inf`/`.nan` are invalid; integer literals are exact and never
overflow, but the over-309-digit vector is `NOT_RUN(spec-undecided)` (decision
10).

**Rationale**: exact values are needed for schema evaluation and FHT C1; the
lexeme is required by the C ABI and by `exact_decimals`. `num-bigint` 0.4 is
already in the JSON Schema validator's dependency tree.

**Alternatives**: `bigdecimal` (licence field `MIT/Apache-2.0`, no declared
MSRV) adds a second decimal type for no gain; `rust_decimal` caps at 28
digits, which is silent loss.

## R3. JSON Schema draft 2020-12 validator

**Decision**: `jsonschema` 0.63.2 (MIT, MSRV 1.85) with
`default-features = false` and features `["arbitrary-precision"]`. No
`resolve-http`, `resolve-file`, `resolve-async` or TLS features: every
`$ref` resolves only inside the bundled schemas (FR-007). Configuration:

- draft 2020-12, `should_validate_formats(true)` (asserted formats);
- the engine converts its exact tree to a `serde_json::Value` whose numbers are
  the canonical exact text, so `multipleOf`, `minimum`, `maximum` and
  integer-ness (`1.0` is an integer) are evaluated on exact values;
- **`pattern` and `patternProperties`** are evaluated with ECMA-262 semantics
  using `regress` (R4 below), installed as custom keyword overrides, so `$`
  matches only at the end (`fhp-fasta-pattern-trailing-newline-canonical-parent`
  must be invalid);
- `format: uri`, `date`, `date-time`, `email` asserted deterministically by the
  validator's own implementations (decision 9; no optional dependency changes
  the verdict). Each format the bundled schemas use gets L1 vectors citing the
  specification; differences from the Python reference with and without
  `rfc3987` are listed in the regression vectors for disposition 3.
- Error location: the instance path becomes the diagnostic's JSON Pointer and
  is projected to the Python `json_path` the toolkit raises today.

**Rationale**: the most used and actively released Rust 2020-12 validator; it
supports arbitrary precision and custom keywords/formats; MSRV and licence fit.

**Alternatives**: `boon` 0.6.1 (last release 2025-01, no declared MSRV) has
good 2020-12 coverage but fails the 12-month maintenance criterion; a
hand-written validator would duplicate the hardest semantics.

**Parity evidence needed**: `if/then`, `contains/minContains`, `$ref` within
and across bundled files, `unevaluatedProperties` if used, `1.0` as integer,
and huge-integer comparisons, each as an L1 vector (#213 criterion 2).

## R4. ECMA-262 regular expressions

**Decision**: `regress` 0.12.0 (MIT OR Apache-2.0) for schema `pattern`s,
with the `pattern` evaluated unanchored (JSON Schema semantics) and Unicode
mode as JSON Schema specifies; compiled once per bundle and cached in the
engine.

**Rationale**: `regress` is an ECMAScript regex engine (used by Boa), so `$`,
`\d` (ASCII only), `\w` and Unicode handling follow ECMA-262 by construction,
which decision 9 requires to be "demonstrated with vectors".

**Alternatives**: `fancy-regex` plus a translation layer (what `jsonschema`
does by default, and what Python does approximately): translation is exactly
the approximation decision 9 replaces. `regress` declares no MSRV; the MSRV CI
job is the check.

## R5. gzip and BGZF

**Decision**: the engine parses gzip member headers and trailers itself
(RFC 1952: magic, CM=8, FLG bits incl. FHCRC/FEXTRA/FNAME/FCOMMENT, CRC32 and
ISIZE trailer) and inflates each member with `flate2` 1.1 raw `Decompress`
using the `zlib-rs` backend (pure Rust, Zlib licence, MSRV 1.75). BGZF is gzip
with a `BC` extra field; the reader treats it as multi-member gzip and accepts
the empty EOF block. Policies (trailing garbage, NUL padding, truncation, CRC
mismatch, FHCRC mismatch) follow the R1 text and the Python reference's
outcomes (`bioheaders/cli.py:139-194`), proved by the existing negative
controls in the corpora and the reader-policy gzip cases.

**Rationale**: `MultiGzDecoder` hides exactly the member-boundary decisions
that the specification makes observable (trailing garbage versus a new member,
NUL padding). Owning the framing (about 200 lines) keeps those outcomes
explicit and testable; raw inflate stays in a proven library.

**Alternatives**: `MultiGzDecoder` (insufficient control); `noodles-bgzf`
0.53 (MSRV 1.91 > 1.85, and BGZF-only); `miniz_oxide` backend (slower; kept as
a feature fallback).

## R6. SHA-512/256 and base64

**Decision**: `sha2` **0.10.x** (`Sha512_256`; MSRV 1.72), as #210 §1
requires: 0.11.1+ declares MSRV 1.88. Canonical padded base64 via
`data-encoding` 2.x (already in the validator's tree), with the R4
canonical-base64 check (unused bits zero, padding present) as a named
operation.

**Rationale**: SHA-512/256 is FIPS 180-4's truncated-IV variant, not a
truncation of SHA-512; `sha2` implements it directly with SIMD backends.

**Alternatives**: `sha2 =0.11.0` (MSRV 1.85 but pinning an old patch of a new
line); `ring`/`aws-lc-rs` (C/asm builds, licence review, no SHA-512/256 API in
`ring`).

## R7. Python binding: PyO3 and maturin

**Decision**: `pyo3` 0.30.1 (MSRV 1.85) with features
`["extension-module", "abi3-py39"]`, built by `maturin` (>=1.9) from
`crates/fair-bioheaders-tools-python/pyproject.toml`, distribution
`fair-bioheaders-tools`, import package `fair_bioheaders_tools` with a native
submodule `fair_bioheaders_tools._native`. Engine work runs with the GIL
released (`Python::allow_threads`). Exceptions: `InternalError` (engine
internal failure), `IncompatibleEngineError`, `CancelledError`, all
subclasses of `fair_bioheaders_tools.EngineError`; verdicts are returned, not
raised.

**Toolkit opt-in backend (Clarification Q1)**: `fair-bioheaders` gains
`bioheaders/_engine.py`, an adapter selected by
`BIOHEADERS_ENGINE=rust` (environment, read by the toolkit, not by the
engine) or `bioheaders.set_engine("rust")`. The adapter maps the engine result
onto today's exceptions (`ValueError` texts, `UnsupportedSchemaVersion`,
`jsonschema.ValidationError` with `json_path`, `NonFiniteValueError`) and
values. Default remains `"python"`. Selecting `rust` without a compatible
engine raises an actionable `ImportError`; there is no silent fallback.
Because the toolkit relocates to Tools-Python (0.14.0), the adapter is written
on this branch against the toolkit as it is in Tools, kept in its own files
(`bioheaders/_engine.py` plus tests), and ported by a separate PR to
Tools-Python once the relocation cut has happened (Python#1). The G1 run uses
whichever home holds the toolkit at that time.

**Rationale**: abi3-py39 matches `python = "^3.9"` (#210 §2) and PyO3 0.30.1
offers it; one wheel per platform covers all CPython versions.

**Alternatives**: ctypes/cffi over the C ABI (hand-written conversion, rejected
in #207 §6); a non-abi3 wheel per Python version (larger matrix).

## R8. C ABI tooling

**Decision**: crate `fair-bioheaders-tools-capi` builds `cdylib` and
`staticlib` named `fhcore`; `fhcore.h` is generated with `cbindgen` (a
developer/CI tool, not a dependency) and committed; CI regenerates and fails on
drift; a Cargo-driven smoke test compiles the header with the system C
compiler (`cc` crate as a dev-dependency) and calls the exported symbols.
`SONAME` `libfhcore.so.0` (ABI major 0) on Linux. Every `extern "C"` body is
wrapped in `catch_unwind`.

**Rationale**: #207 §3, #210 addendum 2.

## R9. Supply-chain gates

**Decision**: `cargo-deny` with `deny.toml` (advisories, licences allowlist
MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Zlib, Unicode-3.0, MPL-2.0,
plus `CDLA-Permissive-2.0` only if `webpki-roots`-style data appears, which it
should not without TLS; bans for duplicates warn, yanked deny; sources
crates.io only) as a required job; `cargo vet` report-only (decision 18);
`rust-toolchain.toml` pins the release toolchain; an MSRV job builds with
1.85. Third-party notices from `cargo-bundle-licenses` are deferred to the
release workflow (not in Phase 1).

## R10. Decision-15 reader-policy diff (prerequisite for FR-074)

**Method**: the GitHub contents API listing of
`conformance/reader-policy/` at the three commits, comparing git object ids,
plus SHA-256 of `cases.json`, on 2026-11-26.

| Entry | `9b5269de` | `6dee4c8b` | `34bbe21a` |
| --- | --- | --- | --- |
| `README.md` blob | `f8065d0a…` | `f8065d0a…` | `f8065d0a…` |
| `cases.json` blob | `b3185747…` | `b3185747…` | `b3185747…` |
| `retirement-crosswalk.json` blob | `b8f2be18…` | `b8f2be18…` | `b8f2be18…` |
| `observations/` tree | `7a8fb37d…` | `7a8fb37d…` | `7a8fb37d…` |
| `payloads/` tree | `d3830550…` | `d3830550…` | `d3830550…` |

`cases.json` SHA-256 at `34bbe21a`:
`b42d9c545d47ff9654f72b38a294f08640ed0e42aa4ff7fc756b0c33217db7c7`
(64 cases: 34 invalid, 22 valid, 8 unsupported-version).

**Finding**: the reader-policy directory is **byte-identical** at all three
commits (equal git tree and blob ids, which are content hashes over every
file). No case or expectation changed between the consumer pins and
`34bbe21a`, so there is nothing further to account for, and core L1 can adopt
`34bbe21a` (decision 15). The commits differ elsewhere (`9b5269de` is 52
commits and `6dee4c8b` 54 commits behind `34bbe21a`), notably in the main
`conformance/manifest.json`, which is pinned separately (C-SOURCE). Each
consumer keeps its own pin until its own repin. The same result is to be
posted on #212/#213.

## R11. Corpus identities (recheck 2026-11-26)

| Corpus | Identity | Counts |
| --- | --- | --- |
| C-FROZEN | tag `v0.6.0` → commit `0ae18b00ee4bd71ab2dc28bae706b0f9d195076b`, `manifest.json` sha256 `cdbb79b1fbfda52b27a9f54b73d3bae1efb662efcbb4c41ba02b9e3be40a51e1` | 291: run 228 (fasta 98, gfa 56, fhgff3 38, fhp-fasta 36), NOT_RUN 63 (jsonld 37, microdata 26); 4 `unsupported-version` |
| C-SOURCE | commit `34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b`, sha256 `7c10fb83bbac5c5739240bff695e5469730ac26a066a51a44d5275598b2df3f6` | 319: run 254 (fasta 107, gfa 58, fhgff3 46, fhp-fasta 43), NOT_RUN 65 (jsonld 38, microdata 27); 5 `unsupported-version` |
| C-POLICY | `34bbe21a`, `cases.json` sha256 `b42d9c54…` | 64 |

Specification `main` (`62c63e8f`) has no change under `conformance/` since
`34bbe21a`.

**How the Rust tests obtain the corpora**: a `xtask`-free approach. A test
helper reads `FH_SPEC_V060` and `FH_SPEC_34BBE21A` (paths to checkouts) when
set; CI checks out the specification at the two exact commits with
`actions/checkout` (`fetch-depth: 1`, `ref: <sha>`). The tests verify the
manifest SHA-256 and vector count before running and **fail** (never skip) if
a path is unset in CI (`FH_REQUIRE_CORPUS=1`). Locally the helper accepts the
same variables. The engine itself never reads these variables (FR-007); only
the test harness does. Copies in Tools `tests/fixtures` are not used (#206
cross-link in #208).

**Known toolkit gap relevant to FR-062**: the specification's
`toolkit-pin.json` lists `fhp-fasta-pattern-trailing-newline-canonical-parent`
as a known gap of the Python toolkit (Python `re` `$`). The engine must get it
right (ECMA `$`); the toolkit's opt-in backend therefore changes this one
verdict, which is disposition 4 of decision 9.

## R12. Performance measurement (SC-006, SC-007)

**Decision**: a Python benchmark script in the binding's test tree
(`bench/verify_bench.py`, not part of acceptance counts) generates synthetic
FHR FASTA (2 GiB and 8 GiB, plain/gzip/BGZF) and GFA (1 GiB) into a temporary
directory on demand, runs the pure-Python reader (`bioheaders` `verify`) and
the engine via the opt-in backend five times each, and reports medians and
peak RSS (`resource.getrusage`, children). Results are recorded on #212 with
the machine description. Generation is streamed; files are deleted after the
run (disk budget).

**Rationale**: the success criterion compares against the Python reader on the
same machine; synthetic inputs avoid shipping large fixtures.

## R13. Fuzzing

**Decision**: `cargo-fuzz` targets (framing, YAML events → tree, gzip member
reader, full verify) in `fuzz/` (excluded from the workspace default
members), run locally and in a scheduled non-required job; SC-008's one
CPU-hour per target is recorded on #212. Requires a nightly toolchain only for
the fuzz job.
