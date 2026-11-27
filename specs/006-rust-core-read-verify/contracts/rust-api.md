# Contract: Rust safe API (crate `fair-bioheaders-tools`, lib name `fair_bioheaders_tools`)

Source of truth for the shape: Tools#207 §2. Semver 0.x: minor bumps may break
until 1.0. Everything below is `pub`; anything not listed is private.

```rust
pub struct EngineBuilder { /* private */ }
pub struct Engine { /* private; Send + Sync */ }
pub struct Verifier { /* private; Send, !Sync */ }
pub struct CancelHandle { /* private; Send + Sync, Clone */ }

#[non_exhaustive] pub enum Operation { Validate, Verify }
#[non_exhaustive] pub enum Container { Auto, Fasta, FhpFasta, Gfa, Gff3, MetadataYaml, MetadataJson }
#[non_exhaustive] pub enum LimitKind { HeaderBytes, HeaderLines, YamlNodes, YamlDepth,
    MetadataBytes, InMemoryDecompressedBytes, ScalarBytes, ConsumerExactIntegerBits }
pub enum Progress { NeedMore, Complete }

impl EngineBuilder {
    pub fn new() -> Self;                                   // profile "python", spec limits
    pub fn profile(self, id: &str) -> Self;
    pub fn limit(self, kind: LimitKind, value: u64) -> Self;        // lower or equal only
    pub fn raise_limit(self, kind: LimitKind, value: u64) -> Self;  // explicit raise
    pub fn draft_lane(self, lane: &str) -> Self;                    // "fht" | "fhgm"
    pub fn build(self) -> Result<Engine, EngineError>;
}

impl Engine {
    pub fn verify_bytes(&self, op: Operation, c: Container, input: &[u8]) -> Result<Report, EngineError>;
    pub fn verify_reader<R: std::io::Read>(&self, op: Operation, c: Container, r: R) -> Result<Report, EngineError>;
    pub fn verify_path(&self, op: Operation, c: Container, p: &std::path::Path) -> Result<Report, EngineError>;
    pub fn stream(&self, op: Operation, c: Container) -> Verifier;
    pub fn capabilities(&self) -> &Capabilities;
    pub fn provenance(&self) -> &Provenance;
    pub fn version() -> &'static str;
}

impl Verifier {
    pub fn feed(&mut self, chunk: &[u8]) -> Result<Progress, EngineError>;
    pub fn finish(self) -> Result<Report, EngineError>;
    pub fn cancel_handle(&self) -> CancelHandle;
}
impl CancelHandle { pub fn cancel(&self); }

#[non_exhaustive]
pub enum EngineError {
    Io { message: String },           // also carries std::io::ErrorKind
    Cancelled,
    InvalidArgument { message: String },
    IncompatibleProfile { message: String },
    State { message: String },
    Internal { message: String },     // contained panic
}
```

`Report`, `LayerResult`, `Diagnostic`, `Selection`, `ChecksumResult`, `Value`,
`Number`, `Provenance`, `Capabilities` are plain data with public read
accessors, as in [data-model.md](../data-model.md). `Report` implements
`PartialEq` (projection tests) and a `to_json()` derived view (exact number
text; never used for decisions).

Named shared operations (#213 criterion 3), exposed in `fair_bioheaders_tools::ops`:

```rust
pub fn sha512_256_base64(covered: &[u8]) -> String;
pub fn is_canonical_base64_digest(s: &str) -> bool;     // R4 form
pub fn fht_c1(record: &Value) -> Result<(), Vec<Diagnostic>>;  // exact arithmetic
```

Guarantees: no network, no environment variables, no threads, no I/O except
`verify_path`'s file read; deterministic output for identical input, profile
and limits.
