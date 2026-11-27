// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! FAIR-bioHeaders read/validate/verify engine (Project 14, Phase 1).
//!
//! One implementation of header framing, exact SHA-512/256 coverage, portable
//! YAML/JSON metadata with exact numbers, strict gzip/BGZF, record-aware
//! schema selection (V1–V7) over digest-pinned bundles, draft 2020-12
//! validation and family predicates, for FASTA, GFA, FHP-FASTA and FHGFF3
//! files and YAML/JSON metadata files. JSON-LD, microdata and model checks are
//! outside this engine and reported as not run.
//!
//! The engine does no network access, reads no environment variables and
//! starts no threads.
#![forbid(unsafe_code)]

pub mod checksum;
pub mod diagnostics;
mod engine;
pub mod family;
pub mod framing;
pub mod gzip;
pub mod json;
pub mod report;
pub mod schema;
pub mod selection;
pub mod value;
pub mod yaml;

pub use engine::{
    ABI_VERSION, CancelHandle, Capabilities, Container, Engine, EngineBuilder, EngineError,
    LimitKind, Operation, Progress, Verifier,
};
pub use report::{
    ChecksumResult, Diagnostic, Layer, LayerResult, LayerStatus, Location, NotRunReason, Outcome,
    Provenance, Report, Selection, Severity,
};
pub use value::{Number, NumberKind, Value};

/// Named shared operations (Tools#213).
pub mod ops {
    pub use crate::checksum::{is_canonical_base64_digest, sha512_256_base64};
    pub use crate::schema::{C1, check_fht_completeness};
}
