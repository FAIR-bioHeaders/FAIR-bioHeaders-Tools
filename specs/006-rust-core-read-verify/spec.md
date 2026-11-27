# Feature Specification: Phase 1 Rust core, read/validate/verify engine with Python and C bindings

**Feature Branch**: `p14-rust-core` (development branch per decision 21; spec directory `006-rust-core-read-verify`)

**Created**: 2026-11-26

**Status**: Clarified

**Input**: Project 14 implementation instruction item 3
([specification#296 comment](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7200839678),
Adam Wright, 2026-11-26): build the Phase 1 Rust core for
[Tools#212](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/212)
(byte/YAML/checksum/compressed-input engine) and
[Tools#213](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/213)
(offline selection, pinned schemas and semantic validation), on a development
branch in Tools, through Spec Kit, following the accepted designs and
maintainer decisions on
[#207](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/207#issuecomment-7172953692)
(API, C ABI, diagnostics, numbers, resources),
[#208](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/208#issuecomment-7172955174)
(conformance, precision, per-consumer gates),
[#210](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/210#issuecomment-7172852786)
(dependencies, platforms, artifacts) and
[#206](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/206#issuecomment-7172928109)
(workspace layout, D7 Phase 1 scope), and David's
[consolidated decisions](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7173402271)
(numbered "decision N" below).

This is **not a schema addition**: no FHR field, contract version, schema byte,
fixture byte or conformance expectation changes. The engine implements the
specification as published; the specification remains the authority
(constitution I).

References of the form "#207 §4" point to section numbers in that issue's
design record; "D7" points to the #206 record.

## Scope

**In Phase 1** (decision 13, #207 §1, #206 D7): read, validate and verify of

- the four sequence containers **FASTA, GFA, FHP-FASTA and FHGFF3**, each plain,
  gzip or BGZF, from a file, a byte buffer or a stream, under R1–R17, P1–P2,
  G1–G3, V1–V7 and FHT C1;
- standalone **YAML and JSON metadata files**;

delivered as three surfaces over one implementation:

1. a **Rust library** (the safe API of #207 §2), usable on its own from a
   pinned `core-v*` source tag (decision 19);
2. a **C-ABI library** with a generated C header (#207 §3), for the later Julia
   and Perl wrappers (decisions 7, 8);
3. **Python bindings** built as the separate engine distribution
   **`fair-bioheaders-tools`** (decision 3; PyPI pending publisher on Tools'
   `release.yml`, #210 comment of 2026-11-25).

**Reported as NOT_RUN by the engine** (never as pass): JSON-LD (J1–J9) and HTML
microdata (M1–M5, R9), with reason `outside-engine-scope`. The Python toolkit
keeps its own readers for these.

**Out of scope** (later issues): strip/combine/convert writers and serializers,
FHGM model checks (K1–K6, B1) and parent links (all #214, reported as `not_run`
model-layer results where relevant); assessment, exports, `metadata`/vitalStats
builders, faidx and CLI orchestration (stay in Python, D7); R, Julia and Perl
wrappers (only after G1); any tag, release, registry upload or publication; a
default switch of the Python toolkit to the engine (#215 and Python#1).

## Clarifications

### Session 2026-11-26

Answers from Adam Wright (the recommended option in each case), relayed by the
Project 14 coordinator on 2026-11-26.

- Q1: How does the Phase 1 binding reach `fair-bioheaders`, and what does
  G1's "installed Python acceptance" cover? → A: **an opt-in backend in
  `fair-bioheaders`, default unchanged.** The toolkit gains an explicit opt-in
  that routes its Phase 1 reads (read, validate, verify) through
  `fair-bioheaders-tools`; without it the pure-Python reader is used exactly as
  today. At G1 the toolkit's existing installed test suite runs in **both
  modes** and passes in both.
- Q2: Crate, library, header and import names and workspace layout? → A:
  **`crates/fair-bioheaders-tools`** (core safe API),
  **`crates/fair-bioheaders-tools-bundles`** (pinned contract bundles and
  provenance), **`crates/fair-bioheaders-tools-capi`** (C library
  **`libfhcore`**, header **`fhcore.h`**, symbol prefix **`fh_`**) and
  **`crates/fair-bioheaders-tools-python`** (PyO3 extension; Python import
  **`fair_bioheaders_tools`**; distribution `fair-bioheaders-tools`).
- Q3: G1 pass bar on the current suite? → A: **all 254 run vectors pass**, with
  65 declared NOT_RUN, the same bar as the frozen suite.

### Session 2026-11-27 (G1 decisions)

David Molik confirmed the four recommended G1 options ("Your recommendations
are good, go with those", [specification#296 comment 7206358624](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7206358624),
2026-11-27T00:19Z) on the questions Adam Wright raised in
[comment 7204432917](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7204432917)
(1-2) and
[comment 7206321764](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/296#issuecomment-7206321764)
(3-4). These amend SC-001, SC-006, FR-062 and G1 item 1 below.

- G1-D1: Frozen-suite accounting? → A: **198 passed + 30
  superseded-by-crosswalk + 63 NOT_RUN** (option A). The 30 are the valid
  FHP/FHGFF3 vectors whose synthetic parent checksum is not canonical base64,
  which the specification retires in
  `conformance/reader-policy/retirement-crosswalk.json` at `34bbe21a` ("R4
  applies to nested checksums too"). The harness counts a non-pass as
  superseded only if the pinned crosswalk (digest-verified) retires that id,
  expectation and byte digest for R4 and the engine rejects it with
  `R4.non-canonical-checksum`; the superseded set must equal the crosswalk's
  valid retirements in the frozen manifest; anything else fails. No
  expectation is regenerated and no non-spec lane is added.
- G1-D2: YAML node and depth limits on JSON metadata? → A: **kept.** JSON
  metadata is held to the FR-064 node (20,000) and depth (64) limits like YAML.
  Python's `json` has no depth bound, so this is a dispositioned behaviour
  change (FR-062) with its own regression vector
  (`targeted::json_metadata_obeys_yaml_node_and_depth_limits`).
- G1-D3: SC-006 speed parity? → A: **amended** to "within 20% of the Python
  reader on x86_64; memory bounded per SC-007", with the measurement recorded
  (research R6, R12). Hashing may be revisited later.
- G1-D4: MIT-0 for `borrow-or-share`? → A: **accepted** as a scoped licence
  exception (`deny.toml`, research R9).

### Session 2026-11-28 (validate scope)

Adam Wright chose option A (relayed 2026-11-28) on the question raised in
[Tools#217 comment 7227914387](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/pull/217#issuecomment-7227914387).
Since the early stop of review 6088963147 finding 4, a Validate verdict on a
late FHR line (R10) in the body depended on how much of the body a host had
read: `validate(bytes)` was invalid, `validate(path)` valid. This amends FR-002
and User Story 5 scenario 4.

- Validate scope? → A: **Validate is header-only.** It frames the input up to
  the end of the header block and never inspects body bytes after it, on every
  entry point (bytes, path, pull reader, push stream, C ABI), however much of
  the body is supplied. Body findings (a late FHR line, R10; gzip damage after
  the header block, R1) are verify-time findings: Verify frames and decodes the
  whole input and reports them. The toolkit's opt-in engine backend keeps the
  Python reader's behaviour (its read paths frame the whole input and reject a
  late FHR line), so toolkit users see no change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Python user's results are unchanged (Priority: P1)

A researcher or pipeline that validates or verifies FASTA, GFA, FHP-FASTA,
FHGFF3 and metadata files with the Python toolkit gets the same verdicts, the
same checksums, the same metadata values and types, the same exceptions
(`jsonschema.ValidationError` with `json_path`, decision 11), the same CLI exit
statuses and the same warnings when those reads are served by the Rust engine,
apart from the two dispositioned changes listed in FR-062.

**Why this priority**: the Python toolkit is the only published consumer.
Without unchanged Python behaviour, nothing else in Project 14 can ship
(constitution V; #296 "preserve fair-bioheaders/bioheaders and fhr public
distribution/import/command compatibility").

**Independent Test**: install the built `fair-bioheaders-tools` wheel into a
clean environment outside the checkout and run Python-native acceptance
through it, then run the toolkit's existing installed test suite with the
opt-in engine backend (FR-052a) and without it; compare every verdict, checksum and metadata
value with the pure-Python reader on the same inputs.

**Acceptance Scenarios**:

1. **Given** each valid and invalid vector of the four sequence formats (plain,
   gzip, BGZF), **When** a Python user validates or verifies it through the
   engine, **Then** the verdict, stated/computed checksum and first error rule
   equal the pure-Python reader's result.
2. **Given** a metadata header with integers above 2^63 and decimals such as
   `1.10`, **When** read through the engine from Python, **Then** integers are
   exact Python `int` values and decimals are `float` by default, exactly as
   today, and `exact_decimals=True` yields `decimal.Decimal("1.10")`-equal values.
3. **Given** a schema-invalid header, **When** the existing validation API is
   called, **Then** it raises `jsonschema.ValidationError` with the same
   `json_path` it raises today.
4. **Given** the toolkit's existing public test suite, **When** it runs against
   the installed packages with the engine serving Phase 1 reads, **Then** it
   passes unchanged (no test edited to accommodate the engine, other than the
   FR-062 dispositions).

---

### User Story 2 - Frozen-suite receipt: 228 pass plus 63 NOT_RUN (Priority: P1)

A maintainer deciding G1 runs the engine's conformance suite and gets a
machine-readable receipt showing that, on the frozen v0.6.0 suite, every one of
the 228 FASTA/GFA/FHP-FASTA/FHGFF3 vectors ran and matched the specification's
expectation, and that the 63 JSON-LD and microdata vectors are declared
`NOT_RUN(outside-engine-scope)`, with the corpus identity checked first. The
same run produces the pinned current-suite (C-SOURCE) receipt.

**Why this priority**: it is the G1 corpus gate (decision 21) and the only
independent evidence that the engine implements the specification rather than
agreeing with another implementation (#208 §2 L1).

**Independent Test**: run the Rust conformance suite on a clean checkout;
inspect the receipt; then tamper with one manifest byte, delete one vector,
and mark one vector skipped, and confirm each run fails.

**Acceptance Scenarios**:

1. **Given** the frozen suite at tag `v0.6.0` (manifest sha256
   `cdbb79b1…a51e1`, 291 vectors), **When** the suite runs, **Then** the
   receipt reports 228 run, 228 passed, 0 failed and 63 NOT_RUN (37 jsonld, 26
   microdata), per format: fasta 98, gfa 56, fhgff3 38, fhp-fasta 36.
2. **Given** the current suite at specification commit `34bbe21a` (manifest
   sha256 `7c10fb83…2df3f6`, 319 vectors), **When** the suite runs, **Then**
   the receipt reports 254 run, 254 passed, 0 failed and 65 NOT_RUN (38
   jsonld, 27 microdata).
3. **Given** a manifest whose digest or count differs from the pin, a run that
   executes zero vectors, an undeclared skip, a vector declared NOT_RUN that
   ran, or a vector that ran but was not declared, **When** the suite runs,
   **Then** it fails (#208 §6).
4. **Given** any NOT_RUN vector, **Then** it is never counted as a pass in any
   total.

---

### User Story 3 - Exact numbers, never silently rounded (Priority: P2)

A metadata author whose header holds large counts (for example `vitalStats`
above 2^53, or an integer above 2^64) or precise decimals gets those values back
exactly, sees validation and FHT C1 completeness decided on the exact values,
and is told explicitly whenever a host representation cannot hold a value.

**Why this priority**: silent rounding has already produced divergent verdicts
across implementations (#207 §0); exactness is a non-negotiable #296 boundary.

**Independent Test**: run the #208 §4 precision vectors through the Rust API,
the C ABI and the Python binding and compare against the expected exact text.

**Acceptance Scenarios**:

1. **Given** integers 2^31−1, 2^31, 3100000000, 2^53±1, 2^63−1, 2^63, 2^64,
   −2^63−1, 10^30 and a large hexadecimal literal, **When** read, **Then** each
   is valid and its exact value and original source text are both available.
2. **Given** `1.0` in an integer-typed field, **Then** it validates as an
   integer; **given** `1.10` and `0.1`, **Then** the source text `1.10` and the
   canonical exact text `1.1` are both available.
3. **Given** `1.7976931348623157e308`, **Then** it is valid; **given** `1.8e308`,
   `.inf` or `.nan`, **Then** the result is invalid under R13.
4. **Given** a plain integer literal over 309 digits, **Then** the vector is
   `NOT_RUN(spec-undecided)` until the specification records the R13 decision
   (decision 10), and is never counted as a pass.
5. **Given** an FHT C1 count above 2^53−1, **Then** the Python profile computes
   an exact pass or fail, and a profile that sets a 53-bit consumer integer
   bound returns `Limit` / `LIMIT.consumer-integer` (decision 12).

---

### User Story 4 - Structured results with rule IDs (Priority: P2)

A tool author (Python today, Julia/Perl/R later) receives one structured result
for every read: an outcome of valid, invalid, unsupported or limit; per-layer
status with named NOT_RUN reasons; and diagnostics carrying a stable code, the
specification rule ID, the layer and a location; and a call failure (I/O,
cancelled, bad argument, incompatible profile, internal) that is never confused
with a verdict.

**Why this priority**: today rule IDs live inside message text and Julia
reports limits and internal errors as invalid (#207 §0, #208 §4 item 2); every
wrapper needs one result model to project.

**Independent Test**: for each rule exercised by the corpus and the targeted
vectors, check that the result's codes belong to the diagnostic registry and
map to the expected rule; check the outcome classes for an invalid, an
unsupported-version, a limit and an injected internal failure.

**Acceptance Scenarios**:

1. **Given** a FASTA with two checksum lines, **Then** the outcome is invalid
   with a diagnostic whose rule is R2, whose code is in the registry, and whose
   location gives the 1-based header line.
2. **Given** a header declaring an unknown release, **Then** the outcome is
   unsupported (V4), the schema layer is `NotRun(blocked-by selection)`, and no
   fallback schema is used.
3. **Given** a header above the 1 MiB header-bytes limit, **Then** the outcome
   is limit with code `LIMIT.header-bytes`, naming the configured value and
   the observed lower bound, and is never invalid.
4. **Given** a schema error and a checksum mismatch in the same file, **Then**
   both are reported in pipeline order (framing, yaml, selection, schema,
   family, checksum), so a single-exception host raises the first.
5. **Given** a `Validate` request, **Then** the checksum layer is
   `NotRun(not-requested)` and does not make the result valid by itself.

---

### User Story 5 - Bounded resources on large and hostile input (Priority: P2)

An operator verifying whole genomes, or a service reading files downloaded from
anywhere, can verify arbitrarily large plain, gzip and BGZF inputs (including
from a pipe) with memory bounded independently of file size, can lower any
limit, and gets an explicit limit outcome, not a crash or an unbounded
allocation, on decompression bombs, deep or huge YAML, or oversized headers.

**Why this priority**: constitution III (fail closed, bounded resources);
no current consumer caps decompression while streaming a checksum (#207 §0).

**Independent Test**: verify a multi-GiB synthetic file and its compressed
forms while measuring peak memory; feed each limit's boundary and
boundary-plus-one inputs; feed gzip negative controls.

**Acceptance Scenarios**:

1. **Given** each default limit (header bytes 1 MiB, header lines 10,000, YAML
   nodes 20,000, YAML depth 64, metadata file 64 MiB after decompression,
   in-memory decompressed bytes 1 GiB), **When** an input sits exactly at the
   limit, **Then** it is read; **When** it exceeds it by one unit, **Then** the
   outcome is limit for that kind.
2. **Given** a host that lowers a limit, **Then** the lower value applies and
   is reported in the result's applied limits; **given** a host that raises one
   above the specification value, **Then** this needs an explicit call and is
   reported.
3. **Given** the existing gzip/BGZF negative controls (bad CRC, truncation,
   trailing garbage, NUL padding, FHCRC, multi-member), **Then** each produces
   its documented outcome.
4. **Given** a validate-only request on a large file, **Then** reading stops
   once the header block has ended, and the verdict is the same on every entry
   point whatever was read after it: bytes after the header block (a late FHR
   line, gzip body damage) are not inspected by Validate and are reported by
   Verify (Clarifications 2026-11-28).
5. **Given** a long stream, **When** another thread cancels it, **Then** the
   call ends as cancelled, not as a verdict.

---

### User Story 6 - Internal failures are contained (Priority: P3)

A host process embedding the engine (a Python interpreter today; Julia and Perl
later) survives an internal engine fault: it receives a structured internal
error, the faulting stream refuses further use, and the process continues.

**Why this priority**: #296 requires that no panic escapes the interface; the
host must be able to tell an engine bug from an invalid file.

**Independent Test**: a test-only fault-injection build triggers a panic inside
the engine through each surface (Rust API boundary, C ABI, Python binding).

**Acceptance Scenarios**:

1. **Given** the fault-injection build, **When** a panic is triggered through
   the C ABI, **Then** the call returns the internal return code with the
   message in an owned error, and the process continues.
2. **Given** the same through Python, **Then** a distinct internal exception
   class is raised (never a validation failure) and the interpreter continues.
3. **Given** a stream that panicked, **When** it is fed again, **Then** it
   returns a state error.
4. **Given** a release build, **Then** the fault-injection entry point is absent.

---

### User Story 7 - Standalone use and later wrappers (Priority: P3)

A Rust developer depends on the engine from a pinned `core-v*` tag, and the
future Julia and Perl wrapper authors bind the C ABI, without needing the
Python toolkit, any network access or any environment variable.

**Why this priority**: decision 3 and 19 (the core stays usable on its own);
the C ABI must be stable enough that wrappers after G1 do not reopen it.

**Independent Test**: a Rust integration test and a Rust-driven C-ABI harness
(plus a C header compile smoke test) exercise the same corpus; the C-ABI
projection of every corpus result equals the Rust API result field for field.

**Acceptance Scenarios**:

1. **Given** the C header, **When** compiled by a C compiler, **Then** it
   compiles cleanly and every exported symbol is declared.
2. **Given** every corpus vector, **Then** the C-ABI projection equals the safe
   API result field for field.
3. **Given** inputs with embedded NUL bytes, zero length or non-UTF-8 body
   bytes, **Then** lengths are honoured exactly and nothing relies on NUL
   termination.
4. **Given** the engine running with networking disabled and no environment
   variables set, **Then** results are identical to a normal run.

---

### Edge Cases

- CRLF, CR-only and mixed line endings; no final newline; ordinary comment
  lines; header-only and body-only files; the checksum line not first or
  appearing twice (R2); record markers in odd places.
- Non-UTF-8 bytes in the sequence body (hashed, never decoded) versus inside a
  header line (R6 invalid); embedded NUL in input; YAML `"\0"` escapes in
  metadata (output strings may contain U+0000).
- YAML duplicate keys, anchors/aliases, tags, merge keys, folded and escaped
  scalars, R12 scalar agreement, `.inf`/`.nan`, `schemaVersion: true` (booleans
  are never numbers; V6 does not apply).
- gzip with FHCRC, multi-member gzip, BGZF EOF block, NUL padding, trailing
  garbage, truncated member, a compressed input that expands past 1 GiB where
  buffering is needed, stdin and pipes with no length.
- Inputs larger than 4 GiB (size range checks on 64-bit hosts; synthetic,
  streamed, never stored).
- Unknown, legacy and near-miss release identifiers; draft lanes (FHT/FHGM) not
  enabled; a release outside the selected consumer profile
  (`NotRun(outside-profile)` or unsupported, never a silent widening).
- `format: uri` and ECMA-262 `pattern` cases where ECMA and Python `re` differ
  (non-ASCII digits for `\d`, `$` before a final newline).
- An unknown enum value received by a wrapper from a newer engine.

## Requirements *(mandatory)*

Each requirement names its source. "Python reference" means the pure-Python
reader of toolkit 0.13.1 (Tools `1f3cf7c2`), or of the 0.14.0 relocation
release once published, which is byte-for-byte the same code.

### Functional Requirements

**Scope and surfaces** (#207 §1–§3, #206 D5/D7, decisions 3, 13, 19)

- **FR-001**: The engine MUST provide read, validate and verify for FASTA, GFA,
  FHP-FASTA and FHGFF3 (plain, gzip, BGZF) and for YAML and JSON metadata
  files, from a path, an in-memory buffer, a pull reader and a push stream.
- **FR-002** (amended 2026-11-28): Validate MUST run every layer except the
  checksum over the input up to the end of the header block, and MUST NOT
  inspect bytes after it on any entry point, so its verdict never depends on
  how much of the body was read; verify MUST frame and decode the whole input
  (including the R10 late-header check and gzip body integrity) and also run
  the checksum layer (#207 §2 `Operation`; Clarifications 2026-11-28).
- **FR-003**: Container detection in automatic mode MUST use content only,
  never the file name; callers MUST be able to state the container explicitly
  (#207 §2; #208 §4 item 5).
- **FR-004**: The engine MUST report JSON-LD and microdata inputs and checks as
  `NOT_RUN(outside-engine-scope)`, and FHGM model and parent-link checks as
  `not_run` model-layer results; it MUST NOT report them as passes.
- **FR-005**: The same engine MUST be exposed as a Rust library, a C-ABI library
  with a generated header, and a Python extension in the `fair-bioheaders-tools`
  distribution, in one Cargo workspace in Tools with the crates
  `fair-bioheaders-tools` (core), `fair-bioheaders-tools-bundles`,
  `fair-bioheaders-tools-capi` (library `libfhcore`, header `fhcore.h`, prefix
  `fh_`) and `fair-bioheaders-tools-python` (import `fair_bioheaders_tools`)
  under `crates/` (Clarification Q2).
- **FR-006**: No FH semantics (rule logic, selection tables, digests) may live
  in a binding layer; bindings only convert arguments, results and errors
  (#207 §6).
- **FR-007**: The engine MUST perform no network access, read no environment
  variables, start no threads and do no I/O beyond reading the path it is
  given; draft lanes are enabled only by an explicit builder option (#207 §2).

**Bytes, framing and checksum** (#212 criterion 1; Spec FORMAT.md R1–R17)

- **FR-010**: The engine MUST compute SHA-512/256 over exactly the bytes the
  specification covers, excluding only the single root-level checksum line,
  preserving line terminators, ordinary comments and body bytes, and compare it
  with the stated value in canonical padded base64. Truncated SHA-512 MUST NOT
  be substituted.
- **FR-011**: Header-block splitting MUST identify metadata from the same byte
  lines that are hashed (constitution II).
- **FR-012**: Body bytes MUST be hashed without decoding; header lines MUST be
  decoded as UTF-8 and rejected under R6 when invalid.

**YAML and JSON metadata** (#212 criterion 2)

- **FR-020**: The YAML reader MUST reject duplicate keys, aliases/anchors,
  forbidden tags and merge keys, apply the specification's escape and folding
  behaviour and R12 scalar agreement, and reject non-finite numbers under R13,
  each before any expansion or loss of information.
- **FR-021**: The YAML reader MUST enforce node-count and depth limits before
  recursion or allocation, and keep each number's source text (#207 §4; #212
  owns parser selection, which must expose event-level lexemes and styles).
- **FR-022**: JSON metadata files MUST be read under the same numeric and limit
  rules.

**Compressed input** (#212 criterion 3)

- **FR-030**: The engine MUST read multi-member gzip and BGZF strictly, by magic
  bytes, and produce the documented outcome for each existing negative control
  (CRC mismatch, truncation, trailing garbage, NUL padding, FHCRC).
- **FR-031**: Streaming verify MUST retain no decompressed body beyond the
  header block and decoder window; any path that must buffer decompressed data
  MUST be bounded by `in_memory_decompressed_bytes` (default 1 GiB,
  configurable, decision 14).

**Selection and validation** (#213 criteria 1–4)

- **FR-040**: Selection MUST be record-aware V1–V7, offline, using digest-pinned
  schema bundles with recorded provenance; unknown releases MUST be
  unsupported (V4) with no fallback and never resolved against a floating
  branch; legacy and near-miss identifiers MUST produce warnings.
- **FR-041**: Validation MUST implement JSON Schema draft 2020-12 with asserted
  formats, including `if`/`then`, `contains`/`minContains`, references,
  date/URI formats and ECMA-262 `pattern`, evaluated on exact numeric values;
  `format: uri` MUST be enforced deterministically (decision 9).
- **FR-042**: Canonical-base64 checksum form, FHT C1 and the agreed non-schema
  family predicates (P1–P2, G1–G3 and others the Python reference applies)
  MUST be named shared operations with positive and negative vectors.
- **FR-043**: Each engine MUST be built for one consumer support profile, read
  from a Tools data file, listing allowed releases per header type, draft
  lanes, serializations and numeric policy; anything outside it MUST be
  unsupported or `NotRun(outside-profile)`. Phase 1 MUST ship the Python
  profile (v0.3.0–v0.8.0 including FHT 1.0; FHT/FHGM draft lanes opt-in, #208
  §4) and MUST demonstrate that a narrower profile is not widened.
- **FR-044**: Native FHGM model data and historical extension transport MUST stay
  distinct from header-type selection (#213 criterion 5).

**Result model and diagnostics** (#207 §2)

- **FR-045**: Every read MUST return one result with: outcome (valid, invalid,
  unsupported, limit); per-layer status (pass, fail, not-run, unsupported,
  limit) with named NOT_RUN reasons (`outside-engine-scope:<format>`,
  `outside-profile:<release|lane>`, `spec-undecided:<topic>`,
  `not-requested`, `blocked-by:<layer>`); diagnostics in pipeline order;
  selection; checksum (stated, computed, match, covered bytes); typed exact
  metadata; and provenance (engine version, ABI version, bundle id and
  manifest digest, specification commit, profile id and digest, limits
  applied).
- **FR-046**: A result is valid only if every layer the operation requires
  passed; a required layer that did not run MUST make the result invalid with a
  visible `NOTRUN.required-layer` error.
- **FR-047**: Call failures (I/O, cancelled, invalid argument, incompatible
  profile, internal) MUST be distinct from verdicts and MUST NOT be reported
  as invalid.
- **FR-048**: Each diagnostic MUST carry severity, a stable code, at most one
  rule ID from the closed set (R1–R17, V1–V7, J1–J9, M1–M5, P1–P2, G1–G3, C1,
  K1–K6, B1), its layer, an informative message and a location (1-based header
  line in the decompressed stream, byte offset and length, JSON Pointer).
- **FR-049**: Codes MUST come from an append-only Tools-owned registry; a test
  MUST assert that every rule in it appears in the pinned specification
  manifest `rules` table (or the pinned FHT source for C1). Messages are not a
  contract.

**Exact numbers** (#207 §4, #208 §4, decisions 10, 12)

- **FR-050**: Every YAML/JSON number MUST keep its source text and an exact
  value (arbitrary-precision integers; exact decimals); schema evaluation and
  C1 arithmetic MUST use the exact values; R13 overflow MUST apply on the
  floating-point path; booleans MUST never be numbers.
- **FR-051**: Every surface MUST make the exact value available without loss
  (kind plus canonical exact text and source text); any lossy host conversion
  MUST be either impossible or announced; no engine output is pre-rounded.

**Python binding** (#207 §4–§6, decisions 3, 9, 11; #210 §2–§3)

- **FR-052**: The Python binding MUST return exact `int` for integers, `float`
  for decimals by default (today's behaviour), and `decimal.Decimal` from the
  exact text when exact decimals are requested; `None`/`bool` for null and
  booleans.
- **FR-052a**: `fair-bioheaders` MUST gain an explicit opt-in backend that
  routes its Phase 1 reads (read, validate, verify of the four sequence
  formats and metadata files) through `fair-bioheaders-tools`; the default MUST
  remain the pure-Python reader, unchanged. Selecting the backend when the
  engine is not installed, or is an incompatible version, MUST fail with an
  actionable error and never fall back silently (Clarification Q1).
- **FR-053**: Where the toolkit's existing validation API is served by the
  engine, it MUST keep raising `jsonschema.ValidationError` with the same
  `json_path` (decision 11), and engine internal failures MUST map to a
  distinct exception class.
- **FR-054**: The wheel MUST be a stable-ABI (abi3) build loadable on every
  CPython the toolkit supports (currently 3.9 and later), with the engine
  compiled in statically and no system library lookup.
- **FR-055**: The binding MUST release the interpreter lock during engine work
  and support use of one engine from several Python threads.

**C ABI** (#207 §3, decision 14; #210 addendum 2)

- **FR-056**: The C ABI MUST use only opaque handles, fixed-width integers,
  `double` and pointers; every byte string MUST carry an explicit length; each
  handle type MUST have exactly one NULL-tolerant release function; every
  fallible call MUST return a status code with an optional owned error and no
  thread-local last error; verdicts MUST be returned as success with a result.
- **FR-057**: The ABI version MUST be `0.x` with exact major.minor matching and
  be reported by a version call; engine, ABI, bundle and package versions are
  four separate values.
- **FR-058**: The C ABI MUST expose the typed metadata value tree (kinds, exact
  number text, source text, 64-bit fast path with range error, nearest double
  with an exactness flag, strings, arrays, keys in source order) and MAY expose
  a derived JSON view that wrappers must not use for metadata or verdicts.
- **FR-059**: Streams MUST support coarse-chunk feeding, finishing, and
  thread-safe cancellation checked at least every 1 MiB of decompressed data;
  engines and results MUST be immutable and shareable across threads.

**Containment and robustness** (#207 §3 "Panic containment", #212 fuzzing)

- **FR-060**: Every C-ABI and Python entry point MUST contain panics and return
  an internal error; a panicked stream MUST be poisoned. The release profile
  MUST unwind. The documented non-contained cases (abort builds, double panic,
  panic in `Drop` during unwinding, allocation failure, stack overflow, abort in
  a dependency, host violation of pointer/length/ownership rules) MUST be
  listed in the delivered documentation.
- **FR-061**: Every input-sized allocation MUST be bounded by a limit before it
  is made; YAML and validation MUST be iterative or depth-checked before
  recursion; framing, YAML and decompression MUST have fuzz targets.

**No regressions to public Python behaviour** (constitution V, #296, decision 9)

- **FR-062**: For every input in the corpora, the toolkit's tests and the
  targeted vectors, the engine's verdict, first error rule, checksum, metadata
  values and types, exception class and `json_path`, CLI exit status and
  warnings MUST equal the Python reference's, except for the two dispositioned
  changes of decision 9 that touch Python: deterministic `format: uri`
  enforcement regardless of `rfc3987`, and ECMA-compatible `pattern`; and the
  G1-D2 change: JSON metadata obeys the YAML node and depth limits (a `limit`
  outcome where Python's `json` accepts the input). Each of
  those MUST have its own regression vector and independent review. Any other
  difference found is a defect or needs a new reviewed disposition; it is never
  absorbed by editing an expectation.
- **FR-063**: No public Python import, distribution name, command or entry point
  (`fair-bioheaders`, `bioheaders`, `fhr` and its `fhr-*` scripts) may change
  or disappear in Phase 1, and no fixture, golden or frozen schema byte may be
  rewritten.

**Limits** (#207 §7, decision 14)

- **FR-064**: Limits MUST default to header bytes 1 MiB, header lines 10,000,
  YAML nodes 20,000, YAML depth 64, metadata file 64 MiB after decompression,
  in-memory decompressed bytes 1 GiB, scalar bytes at most header bytes, and
  consumer exact-integer bits unset; hosts MAY lower any limit and MUST make an
  explicit call to raise one, which the result reports. A breach MUST produce
  outcome limit with code `LIMIT.<kind>`, never invalid.

**Conformance and acceptance in Rust** (#208 §1, §2 L1, §6; #212 criterion 5;
#213 criterion 6; native-language CI rule)

- **FR-070**: Primary core acceptance MUST be Rust tests run by Cargo, reading
  the specification-pinned corpora by verified digest (not copies in Tools
  `tests/fixtures`), with expectations taken only from the specification
  manifests and never regenerated from any implementation's output.
- **FR-071**: Each run MUST verify the manifest digest and count before running,
  and MUST fail on: wrong digest, wrong count, zero vectors or tests, any
  undeclared skip, a two-way mismatch between declared NOT_RUN and executed
  vectors, accounted vectors differing from the manifest, a test count below
  the floor, a missing or unparsable receipt, or any failure.
- **FR-072**: Each run MUST write a receipt with corpus label, manifest sha256,
  specification commit, engine/ABI/bundle/profile identities, platform triple,
  per-format totals (total, run, passed, failed, NOT_RUN by reason), the test
  runner's totals and the CI run id. Expected counts come from the pinned
  manifest and profile data.
- **FR-073**: The current suite (C-SOURCE, `34bbe21a`, 319 vectors) MUST run
  254 vectors, all of which MUST pass, and declare 65 NOT_RUN
  (Clarification Q3).
- **FR-074**: Reader-policy L1 tests MUST use `34bbe21a`
  (`cases.json` sha256 `b42d9c54…`) only after a written diff of
  `conformance/reader-policy/` between `9b5269de`, `6dee4c8b` and `34bbe21a`
  accounts for every changed case (decision 15).
- **FR-075**: Targeted Tools-owned regression vectors (YAML R8/R11/R12/R13,
  gzip/BGZF R1 negatives, V1–V7, formats and regex, family predicates,
  precision, limits) MUST each cite the specification line their expectation
  comes from.
- **FR-076**: Comparisons with the Python reference and the independent
  JavaScript implementation MUST run only in jobs named `supplemental-*` that
  are never required and never a prerequisite of a primary job; divergences
  MUST be documented (#212 criterion 6).
- **FR-077**: The Python binding's primary acceptance MUST be Python-native
  (pytest) against the installed wheel outside the checkout, with Python-native
  digest, count, receipt and missing/zero/skipped guards, and MUST include a
  Python-native run of the frozen suite through the binding.

**Dependencies, builds and platforms** (#210 §1–§2, decisions 17, 18)

- **FR-080**: The workspace MUST declare MSRV 1.85, pin a release toolchain,
  commit `Cargo.lock`, build releases with `--locked`, use crates.io sources only
  with minimal features and no network features, and record a justification
  for each direct dependency (obligation, maintenance, MSRV, licence, parity
  evidence).
- **FR-081**: `cargo-deny` (advisories, licences against the #210 allowlist,
  bans, sources) MUST be a required check; `cargo-vet` runs report-only.
- **FR-082**: Rust tests MUST run on Tier-1 platforms (linux x86_64 and aarch64
  glibc, macOS arm64) and in Alpine (musl) containers; the Python wheel's
  installed suite MUST run on Tier-1 runners, in a glibc 2.28 container
  (`manylinux_2_28` floor) and on Alpine (`musllinux_1_2`); Windows x86_64 and
  macOS x86_64 are Tier 2 for Python only.

**Process** (#296 rules, decision 21)

- **FR-090**: All work MUST stay on the `p14-rust-core` development branch until
  the G1 checklist below is complete; only then is a PR to `main` opened.
  Every PR needs independent review by a different actual model with findings
  dispositioned; agents never merge; missing, failed or NOT_RUN checks are not
  passes. No tag, GitHub Release, wheel upload or registry action occurs in
  this feature.
- **FR-091**: No new workflow may publish anything; core tags use the
  `core-v*` namespace only when a human later creates them.

### G1 acceptance (decision 21; #209 addendum item 2; #208 decision record)

G1 must hold, with evidence linked on Tools#212/#213 and #205, before the PR
to `main` and before any R, Julia or Perl implementation:

1. **Frozen-suite receipt** (G1-D1): v0.6.0 manifest sha256
   `cdbb79b1fbfda52b27a9f54b73d3bae1efb662efcbb4c41ba02b9e3be40a51e1`, 291
   vectors; 228 run: 198 passed and 30 superseded by the pinned R4 retirement
   crosswalk, 0 failed, 63 declared `NOT_RUN(outside-engine-scope)`; all FR-071
   guards active; from Rust (FR-070) and from the installed Python binding
   (FR-077).
2. **Pinned current-suite evidence**: C-SOURCE manifest sha256
   `7c10fb83bbac5c5739240bff695e5469730ac26a066a51a44d5275598b2df3f6`
   (`34bbe21a`), 254 run and passed, 0 failed, 65 declared NOT_RUN; reader-policy
   receipt per FR-074.
3. **Installed Python acceptance**: the FR-077 suite and the FR-062
   non-regression checks pass from the installed wheel on every Tier-1
   platform, the glibc 2.28 floor and Alpine; the toolkit's existing installed
   test suite passes both with the default pure-Python reader and with the
   opt-in engine backend (FR-052a).
4. **Precision, diagnostics, limits and containment**: every #208 §4 vector
   (with the over-309-digit case `NOT_RUN(spec-undecided)`), the FR-049
   registry test, every FR-064 limit boundary, the FR-030 negative controls and
   the FR-060 fault-injection tests pass.
5. **Decision-9 dispositions touching the core** (uri, pattern): each has a
   regression vector and an independent review recorded.
6. **Supply chain**: `cargo-deny` clean; dependency justifications recorded;
   `cargo-vet` report attached (report-only).
7. **Cost checkpoint**: the #209 G1 cost entry is recorded with observed work
   and labelled estimates (decision 21, 23).
8. **Review**: current-head CI green; independent review by another model with
   all findings dispositioned; a human merges.

A NOT_RUN never counts as a pass in any item above.

### Key Entities

- **Engine**: an immutable, thread-shareable reader configured once with a
  consumer profile, limits and opt-in draft lanes.
- **Consumer support profile**: Tools data naming allowed releases per header
  type, draft lanes, serializations and numeric policy; identified by id and
  digest.
- **Contract bundle**: the digest-pinned schemas and selection data taken from
  the specification, with a provenance manifest (specification commit, file
  digests).
- **Result (Report)**: outcome, layer statuses, diagnostics, selection,
  checksum, typed metadata and provenance; projected identically by every
  surface.
- **Diagnostic** and **diagnostic registry**: a stable code mapped to at most
  one rule ID, a layer and a severity; append-only.
- **Exact value**: a metadata value tree whose numbers carry kind, exact
  canonical text and source text.
- **Receipt**: the machine-readable record of one conformance run, with corpus
  and engine identities and per-format accounting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (amended by G1-D1): The frozen-suite receipt shows exactly 198
  passed, 30 superseded-by-crosswalk (each retired by the pinned R4 crosswalk
  and rejected under R4), 0 failed and 63 declared NOT_RUN at the pinned
  digest, from both the Rust suite and the installed Python binding, on every
  Tier-1 platform.
- **SC-002**: The current-suite receipt shows 254 run and 65 NOT_RUN at the
  pinned digest, with all 254 passed and 0 failed.
- **SC-003**: 100% of inputs in the corpora, targeted vectors and the toolkit's
  existing tests give Python users the same verdict, first error rule,
  checksum, metadata values and types and exception as the Python reference,
  except the two dispositioned decision-9 changes and the G1-D2 JSON-limit
  change; the toolkit's existing test
  suite passes with zero edited expectations.
- **SC-004**: 0 numbers are rounded without announcement: every #208 §4
  precision vector returns its exact expected text through all three surfaces.
- **SC-005**: Every diagnostic emitted across all runs has a registered code,
  and every rule ID in the registry exists in the pinned specification
  sources.
- **SC-006** (amended by G1-D3): Verifying a file of at least 2 GiB (FASTA
  plain, gzip and BGZF, and a GFA of at least 1 GiB) through the Python binding
  is within 20% of the Python reader on x86_64 on the same machine (median of
  5 runs, ratio ≤ 1.20), and validate-only on the same files is within 20% too;
  memory is bounded per SC-007. Measured before the amendment (one x86_64
  laptop, about ±15% run-to-run noise): plain FASTA 1.08, gzip 0.88, BGZF
  1.17, GFA 1.05 (research R6). The original bar was ratio ≤ 1.00.
- **SC-007**: Peak resident memory while verifying any of the SC-006 inputs
  stays below 256 MiB and does not grow with file size between a 2 GiB and an
  8 GiB input; a decompression bomb ends in a limit outcome without exceeding
  the configured buffer limit.
- **SC-008**: 100% of fault-injection panics through the C ABI and the Python
  binding end in an internal error with the host process still running; fuzz
  targets for framing, YAML and decompression run for at least one CPU-hour
  each with no crash, hang or escaped panic.
- **SC-009**: Every limit kind returns a limit outcome, never invalid, at
  boundary plus one, and reads successfully at the boundary.
- **SC-010**: `cargo-deny` reports no advisory, licence, ban or source finding
  at the G1 head, and the engine runs to identical results with networking
  disabled.

## Assumptions

- **Corpus identities rechecked 2026-11-26.** Specification `main` was
  `62c63e8f`, six commits after `34bbe21a`, with no change under
  `conformance/`; the `v0.6.0` tag object is still `ab7e3ddd…`, and both
  manifest digests and per-format counts match #208 §1. They are rechecked
  again when implementation starts.
- **Python floor**: the abi3 wheel targets CPython 3.9+, matching the toolkit's
  `python = "^3.9"`, as #210 §2 records (PyO3 0.30.1 offers `abi3-py39`).
  Raising it is a separate reviewed decision in Python#2/#4. Free-threaded
  CPython is not promised.
- **Where the engine wheel is built**: in Tools, published later from Tools'
  `release.yml` under the `pypi` environment (Adam's pending publisher,
  2026-11-25). Phase 1 only builds and tests it; nothing is uploaded.
- **Warnings**: R14 and other specification-rule warnings, and legacy/near-miss
  selection warnings, are engine diagnostics. The toolkit's own advisory
  warnings (`required_value_warnings`, `link_scheme_warnings`,
  `schema_warnings`, `gff3.header_report`) stay in Python per D7, so the
  user-visible warning set is unchanged.
- **Python reference**: toolkit 0.13.1 (Tools `1f3cf7c2`) is the comparison
  baseline; the 0.14.0 relocation release is the same code.
- **Profiles**: Phase 1 ships the Python profile and a test-only narrower
  profile to prove non-widening; R, Julia and Perl profiles are defined as data
  when their wrappers start after G1 (the Perl and R rows of #208 §4 are
  recorded, decisions 12 and 13).
- **Windows paths** stay out of the C ABI until a C-ABI consumer is promoted on
  Windows (#207 §8.8); Python on Windows uses the safe API.
- **No Rust command-line tool** is part of Phase 1; the CLI stays the Python
  toolkit's.
- **Relocation ordering**: Rust code may land on the development branch before
  the 0.14.0 relocation and Tools cleanup, provided it adds no tag and no
  release workflow (#206 D6 step 6).
- **Dependencies**: YAML parser, JSON Schema validator, gzip/BGZF and SHA-2
  crates are chosen in the plan's research with the #210 §1 justification;
  `serde_yaml` is excluded and the SHA-2 line must meet MSRV 1.85.
- **R13 huge integers** stay `NOT_RUN(spec-undecided)` until the specification
  records decision 10 with a vector.

## Dependencies

- Specification: pinned manifests (v0.6.0 and `34bbe21a`), reader-policy cases,
  FHT lane, rule tables; the R13 decision (decision 10) for one vector.
- Tools#206 relocation (parallel, item 2 of the instruction): only affects
  where the Python reference and toolkit tests live.
- The opt-in backend lands in the toolkit's home at the time (Tools before the
  relocation cut, Tools-Python after it), coordinated with Python#1.
- #209 for the G1 cost entry.
