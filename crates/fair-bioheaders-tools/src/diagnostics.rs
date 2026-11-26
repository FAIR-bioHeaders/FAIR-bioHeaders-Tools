// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The diagnostic code registry (Tools#207 section 2).
//!
//! Codes are append-only: a code is never renamed or removed without a
//! reviewed deprecation, and its rule, layer and severity never change. The
//! committed snapshot `diagnostics.snapshot.json` is checked by a test so that
//! an accidental rename fails CI. Messages are not part of the contract.

use crate::report::{Layer, Severity};

/// A registry entry.
#[derive(Clone, Copy, Debug)]
pub struct Entry {
    /// The stable code.
    pub code: &'static str,
    /// The specification rule, or `None` for engine-local codes.
    pub rule: Option<&'static str>,
    /// The layer that emits it.
    pub layer: Layer,
    /// Error or warning.
    pub severity: Severity,
}

macro_rules! registry {
    ($( $variant:ident => ($code:literal, $rule:expr, $layer:ident, $severity:ident) ),* $(,)?) => {
        /// Every diagnostic code the engine can emit.
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
        #[allow(missing_docs)]
        pub enum Code { $( $variant ),* }

        /// The registry, in declaration order.
        pub static REGISTRY: &[Entry] = &[
            $( Entry { code: $code, rule: $rule, layer: Layer::$layer, severity: Severity::$severity } ),*
        ];

        /// The entry of `code`.
        pub fn entry(code: Code) -> &'static Entry {
            &REGISTRY[code as usize]
        }
    };
}

registry! {
    // Framing (bytes, compression, header block).
    R7ByteOrderMark => ("R7.byte-order-mark", Some("R7"), Framing, Error),
    R10LateHeader => ("R10.late-header", Some("R10"), Framing, Error),
    G1HeaderBeforeVersion => ("G1.header-before-version-line", Some("G1"), Framing, Error),
    G1BadVersionLine => ("G1.bad-version-line", Some("G1"), Framing, Error),
    R1GzipHeader => ("R1.gzip-bad-header", Some("R1"), Framing, Error),
    R1GzipHeaderCrc => ("R1.gzip-header-crc", Some("R1"), Framing, Error),
    R1GzipData => ("R1.gzip-bad-data", Some("R1"), Framing, Error),
    R1GzipCrc => ("R1.gzip-crc-mismatch", Some("R1"), Framing, Error),
    R1GzipLength => ("R1.gzip-length-mismatch", Some("R1"), Framing, Error),
    R1GzipTruncated => ("R1.gzip-truncated", Some("R1"), Framing, Error),
    R1GzipTrailing => ("R1.gzip-trailing-data", Some("R1"), Framing, Error),
    InputNoHeader => ("INPUT.no-header", None, Framing, Error),
    InputEmpty => ("INPUT.empty", None, Framing, Error),
    // Metadata syntax and portability.
    R6InvalidUtf8 => ("R6.invalid-utf8", Some("R6"), Yaml, Error),
    R6YamlLineBreak => ("R6.yaml-only-line-break", Some("R6"), Yaml, Error),
    R8DuplicateKey => ("R8.duplicate-key", Some("R8"), Yaml, Error),
    R8AnchorAlias => ("R8.anchor-or-alias", Some("R8"), Yaml, Error),
    R8MergeKey => ("R8.merge-key", Some("R8"), Yaml, Error),
    R12Tag => ("R12.explicit-tag", Some("R12"), Yaml, Error),
    R12NonPortable => ("R12.non-portable-scalar", Some("R12"), Yaml, Error),
    R12Directive => ("R12.directive-or-document-marker", Some("R12"), Yaml, Error),
    R13NonFinite => ("R13.non-finite-number", Some("R13"), Yaml, Error),
    YamlSyntax => ("YAML.syntax", None, Yaml, Error),
    JsonSyntax => ("JSON.syntax", None, Yaml, Error),
    InputNotObject => ("INPUT.not-an-object", None, Yaml, Error),
    // Selection.
    V4Unsupported => ("V4.unsupported-version", Some("V4"), Selection, Error),
    V5NearMiss => ("V5.near-miss", Some("V5"), Selection, Warning),
    V6Fhr1Citation => ("V6.fhr1-citation", Some("V6"), Selection, Warning),
    V7DraftContract => ("V7.draft-contract", Some("V7"), Selection, Warning),
    NotRunOutsideProfile => ("NOTRUN.outside-profile", None, Selection, Error),
    // Schema.
    SchemaFhr => ("SCHEMA.fhr", None, Schema, Error),
    SchemaFht => ("SCHEMA.fht", None, Schema, Error),
    P1Schema => ("P1.schema", Some("P1"), Schema, Error),
    G2Schema => ("G2.schema", Some("G2"), Schema, Error),
    R15UnknownField => ("R15.unknown-field", Some("R15"), Schema, Error),
    R15NotAllowed => ("R15.extension-not-in-version", Some("R15"), Schema, Error),
    R4NonCanonical => ("R4.non-canonical-checksum", Some("R4"), Schema, Error),
    C1CompletenessSum => ("C1.completeness-sum", Some("C1"), Schema, Error),
    SchemaEvaluation => ("SCHEMA.evaluation-error", None, Schema, Error),
    // Family predicates and advisory warnings.
    R17ContainerMismatch => ("R17.container-mismatch", Some("R17"), Family, Error),
    R14LinkScheme => ("R14.link-scheme", Some("R14"), Family, Warning),
    R11RecordMarker => ("R11.record-marker", Some("R11"), Family, Warning),
    G2DirectiveMismatch => ("FHGFF3.directive-mismatch", None, Family, Warning),
    // Checksum.
    R2ChecksumLines => ("R2.checksum-line-count", Some("R2"), Checksum, Error),
    R5ChecksumIncomplete => ("R5.checksum-line-incomplete", Some("R5"), Checksum, Error),
    R5ChecksumContent => ("R5.checksum-line-content", Some("R5"), Checksum, Error),
    R3ChecksumMismatch => ("R3.checksum-mismatch", Some("R3"), Checksum, Error),
    // Engine-local.
    LimitHeaderBytes => ("LIMIT.header-bytes", None, Framing, Error),
    LimitHeaderLines => ("LIMIT.header-lines", None, Framing, Error),
    LimitYamlNodes => ("LIMIT.yaml-nodes", None, Yaml, Error),
    LimitYamlDepth => ("LIMIT.yaml-depth", None, Yaml, Error),
    LimitMetadataBytes => ("LIMIT.metadata-bytes", None, Framing, Error),
    LimitDecompressed => ("LIMIT.in-memory-decompressed-bytes", None, Framing, Error),
    LimitScalarBytes => ("LIMIT.scalar-bytes", None, Yaml, Error),
    LimitConsumerInteger => ("LIMIT.consumer-integer", None, Schema, Error),
    NotRunRequiredLayer => ("NOTRUN.required-layer", None, Model, Error),
    SpecUndecided => ("NOTRUN.spec-undecided", None, Yaml, Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn codes_are_unique_and_well_formed() {
        let mut seen = HashSet::new();
        for entry in REGISTRY {
            assert!(seen.insert(entry.code), "duplicate code {}", entry.code);
            let prefix = entry.code.split('.').next().unwrap();
            match entry.rule {
                Some(rule) => assert_eq!(prefix, rule, "{} must start with its rule", entry.code),
                None => assert!(
                    [
                        "INPUT", "LIMIT", "NOTRUN", "YAML", "JSON", "SCHEMA", "FHGFF3", "IO"
                    ]
                    .contains(&prefix),
                    "{} has no rule and no engine-local prefix",
                    entry.code
                ),
            }
        }
    }
}
