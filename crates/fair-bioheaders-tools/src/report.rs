// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The one result model every surface projects (Tools#207 section 2).

use crate::diagnostics::{self, Code};
use crate::value::Value;
use std::fmt;

/// The verdict of a read.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Outcome {
    /// Every required layer passed.
    Valid,
    /// A layer failed.
    Invalid,
    /// Rule V4: the cited schema version is not available (no fallback).
    Unsupported,
    /// A configured resource bound stopped evaluation.
    Limit,
}

impl Outcome {
    /// The lower-case name used in receipts and bindings.
    pub fn as_str(self) -> &'static str {
        match self {
            Outcome::Valid => "valid",
            Outcome::Invalid => "invalid",
            Outcome::Unsupported => "unsupported",
            Outcome::Limit => "limit",
        }
    }
}

/// A pipeline layer, in pipeline order.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Layer {
    /// Header-block framing, compression and line rules.
    Framing,
    /// YAML/JSON metadata syntax and portability.
    Yaml,
    /// Schema selection (V1–V7).
    Selection,
    /// JSON Schema validation.
    Schema,
    /// Non-schema family predicates (R17, G, P, R4 values, C1).
    Family,
    /// The covered-bytes checksum.
    Checksum,
    /// Model-layer checks (FHGM, parent links); never run in Phase 1.
    Model,
}

impl Layer {
    /// All layers in pipeline order.
    pub const ALL: [Layer; 7] =
        [Layer::Framing, Layer::Yaml, Layer::Selection, Layer::Schema, Layer::Family, Layer::Checksum, Layer::Model];

    /// The lower-case name.
    pub fn as_str(self) -> &'static str {
        match self {
            Layer::Framing => "framing",
            Layer::Yaml => "yaml",
            Layer::Selection => "selection",
            Layer::Schema => "schema",
            Layer::Family => "family",
            Layer::Checksum => "checksum",
            Layer::Model => "model",
        }
    }

    /// Position in [`Layer::ALL`].
    pub fn index(self) -> usize {
        self as usize
    }
}

/// The status of one layer.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LayerStatus {
    /// The layer ran and passed.
    Pass,
    /// The layer ran and found an error.
    Fail,
    /// The layer did not run; see the reason.
    NotRun,
    /// Selection only: the cited version is unsupported.
    Unsupported,
    /// A limit stopped the layer.
    Limit,
}

impl LayerStatus {
    /// The lower-case name.
    pub fn as_str(self) -> &'static str {
        match self {
            LayerStatus::Pass => "pass",
            LayerStatus::Fail => "fail",
            LayerStatus::NotRun => "not-run",
            LayerStatus::Unsupported => "unsupported",
            LayerStatus::Limit => "limit",
        }
    }
}

/// Why a layer did not run (Tools#208 section 6).
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum NotRunReason {
    /// Validate does not run the checksum layer.
    NotRequested,
    /// An earlier layer's failure left this layer without input.
    BlockedBy(Layer),
    /// Outside the Phase 1 engine (JSON-LD, microdata, model).
    OutsideEngineScope(String),
    /// Outside the engine's consumer support profile.
    OutsideProfile(String),
    /// The specification has not decided the expected outcome.
    SpecUndecided(String),
}

impl fmt::Display for NotRunReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NotRunReason::NotRequested => f.write_str("not-requested"),
            NotRunReason::BlockedBy(layer) => write!(f, "blocked-by:{}", layer.as_str()),
            NotRunReason::OutsideEngineScope(what) => write!(f, "outside-engine-scope:{what}"),
            NotRunReason::OutsideProfile(what) => write!(f, "outside-profile:{what}"),
            NotRunReason::SpecUndecided(what) => write!(f, "spec-undecided:{what}"),
        }
    }
}

/// One layer's result.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LayerResult {
    /// Which layer.
    pub layer: Layer,
    /// Its status.
    pub status: LayerStatus,
    /// The reason when `status` is `NotRun`.
    pub not_run_reason: Option<NotRunReason>,
}

/// Error or warning.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Severity {
    /// Makes the layer fail.
    Error,
    /// Informational; never changes validity.
    Warning,
}

impl Severity {
    /// The lower-case name.
    pub fn as_str(self) -> &'static str {
        match self {
            Severity::Error => "error",
            Severity::Warning => "warning",
        }
    }
}

/// Where a diagnostic points.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Location {
    /// 1-based line in the decompressed stream.
    pub header_line: Option<u64>,
    /// Byte offset in the decompressed stream.
    pub byte_offset: Option<u64>,
    /// Length in bytes.
    pub byte_len: Option<u64>,
    /// RFC 6901 pointer into the metadata.
    pub json_pointer: Option<String>,
}

/// A structured diagnostic. `code` and `rule` are the contract; `message` is
/// informative English and may change.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Diagnostic {
    /// Error or warning.
    pub severity: Severity,
    /// Stable registry code.
    pub code: &'static str,
    /// The specification rule, if the code maps to one.
    pub rule: Option<&'static str>,
    /// The layer that produced it.
    pub layer: Layer,
    /// Informative message.
    pub message: String,
    /// Location.
    pub location: Location,
}

impl Diagnostic {
    /// A diagnostic for a registered code.
    pub fn new(code: Code, message: impl Into<String>) -> Diagnostic {
        let entry = diagnostics::entry(code);
        Diagnostic {
            severity: entry.severity,
            code: entry.code,
            rule: entry.rule,
            layer: entry.layer,
            message: message.into(),
            location: Location::default(),
        }
    }

    /// With a header line.
    pub fn at_line(mut self, line: u64) -> Diagnostic {
        self.location.header_line = Some(line);
        self
    }

    /// With a JSON Pointer.
    pub fn at_pointer(mut self, pointer: impl Into<String>) -> Diagnostic {
        self.location.json_pointer = Some(pointer.into());
        self
    }

    /// With a byte range.
    pub fn at_bytes(mut self, offset: u64, len: u64) -> Diagnostic {
        self.location.byte_offset = Some(offset);
        self.location.byte_len = Some(len);
        self
    }
}

/// The schema a record selected.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Selection {
    /// FHR, FHP, FHGFF3 or FHT.
    pub header_type: String,
    /// The release tag, or `main`.
    pub release: String,
    /// The bundled schema file.
    pub schema_file: String,
    /// SHA-256 of the bundled schema bytes.
    pub schema_sha256: String,
    /// The selection rule that applied.
    pub rule: &'static str,
    /// Whether a draft lane selected it.
    pub draft: bool,
}

/// The checksum layer's result.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct ChecksumResult {
    /// The checksum the header states.
    pub stated: Option<String>,
    /// The computed checksum.
    pub computed: Option<String>,
    /// Whether they match; `None` when either is missing.
    pub matches: Option<bool>,
    /// Bytes covered by the digest.
    pub covered_bytes: u64,
}

/// Engine identity and configuration a result was produced under.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Provenance {
    /// Engine (crate) version.
    pub engine_version: String,
    /// C ABI version `major.minor`.
    pub abi_version: String,
    /// Contract bundle id.
    pub bundle_id: String,
    /// SHA-256 of the bundle manifest.
    pub bundle_manifest_sha256: String,
    /// Specification commit the bundle was taken from.
    pub spec_commit: String,
    /// Consumer support profile id.
    pub profile_id: String,
    /// SHA-256 of the profile definition.
    pub profile_sha256: String,
    /// Every limit with its value; raised ones are marked.
    pub limits_applied: Vec<(String, u64, bool)>,
}

/// The result of one read.
#[derive(Clone, Debug, PartialEq)]
pub struct Report {
    /// The verdict.
    pub outcome: Outcome,
    /// One entry per layer, in [`Layer::ALL`] order.
    pub layers: Vec<LayerResult>,
    /// Diagnostics in pipeline order.
    pub diagnostics: Vec<Diagnostic>,
    /// The selected schema.
    pub selection: Option<Selection>,
    /// The checksum result.
    pub checksum: Option<ChecksumResult>,
    /// The metadata, exactly.
    pub metadata: Option<Value>,
    /// Engine identity.
    pub provenance: Provenance,
    /// The container that was read.
    pub container: crate::Container,
}

impl Report {
    /// Whether the outcome is valid.
    pub fn is_valid(&self) -> bool {
        self.outcome == Outcome::Valid
    }

    /// The status of `layer`.
    pub fn layer(&self, layer: Layer) -> &LayerResult {
        &self.layers[layer.index()]
    }

    /// The first error diagnostic in pipeline order.
    pub fn first_error(&self) -> Option<&Diagnostic> {
        self.diagnostics.iter().find(|d| d.severity == Severity::Error)
    }

    /// Warnings in order.
    pub fn warnings(&self) -> impl Iterator<Item = &Diagnostic> {
        self.diagnostics.iter().filter(|d| d.severity == Severity::Warning)
    }

    /// A derived JSON view with exact numbers (logging and differentials
    /// only; wrappers must not use it for verdicts or metadata).
    pub fn to_json(&self) -> String {
        let layers: Vec<serde_json::Value> = self
            .layers
            .iter()
            .map(|l| {
                serde_json::json!({
                    "layer": l.layer.as_str(),
                    "status": l.status.as_str(),
                    "notRunReason": l.not_run_reason.as_ref().map(|r| r.to_string()),
                })
            })
            .collect();
        let diagnostics: Vec<serde_json::Value> = self
            .diagnostics
            .iter()
            .map(|d| {
                serde_json::json!({
                    "severity": d.severity.as_str(),
                    "code": d.code,
                    "rule": d.rule,
                    "layer": d.layer.as_str(),
                    "message": d.message,
                    "headerLine": d.location.header_line,
                    "byteOffset": d.location.byte_offset,
                    "byteLen": d.location.byte_len,
                    "jsonPointer": d.location.json_pointer,
                })
            })
            .collect();
        let value = serde_json::json!({
            "outcome": self.outcome.as_str(),
            "layers": layers,
            "diagnostics": diagnostics,
            "selection": self.selection.as_ref().map(|s| serde_json::json!({
                "headerType": s.header_type, "release": s.release, "schemaFile": s.schema_file,
                "schemaSha256": s.schema_sha256, "rule": s.rule, "draft": s.draft,
            })),
            "checksum": self.checksum.as_ref().map(|c| serde_json::json!({
                "stated": c.stated, "computed": c.computed, "matches": c.matches,
                "coveredBytes": c.covered_bytes,
            })),
            "metadata": self.metadata.as_ref().map(Value::to_json),
            "provenance": {
                "engineVersion": self.provenance.engine_version,
                "abiVersion": self.provenance.abi_version,
                "bundleId": self.provenance.bundle_id,
                "bundleManifestSha256": self.provenance.bundle_manifest_sha256,
                "specCommit": self.provenance.spec_commit,
                "profileId": self.provenance.profile_id,
                "profileSha256": self.provenance.profile_sha256,
            },
        });
        value.to_string()
    }
}
