// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Tools-owned targeted vectors (Tools#208 sections 2 and 4). Each case cites
//! the specification text its expectation comes from.

use fair_bioheaders_tools::{
    Container, Engine, EngineBuilder, EngineError, Layer, LayerStatus, LimitKind, NotRunReason,
    Operation, Outcome, Value, ops,
};

const FHR21: &str = "schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0
schemaVersion: '2.1'
genome: Synthetic genome
taxon:
  name: Homo sapiens
  uri: https://identifiers.org/taxonomy:9606
version: '0.0.1'
metadataAuthor:
- name: A
assemblyAuthor:
- name: B
dateCreated: '2022-03-21'
masking: soft-masked
";

const FHT10: &str = "schema: https://w3id.org/fair-bioheaders/fht/v0.7.0
schemaVersion: '1.0'
transcriptome: Synthetic transcript set
assemblyType: de novo
taxon:
  name: Homo sapiens
  uri: https://identifiers.org/taxonomy:9606
version: '1.0.0'
metadataAuthor:
- name: A
dateCreated: '2026-11-10'
";

fn engine() -> Engine {
    Engine::new().unwrap()
}

/// A FASTA file with `metadata` as its header and a correct checksum.
fn fasta(metadata: &str, body: &str) -> Vec<u8> {
    let header: String = metadata.lines().map(|l| format!(";~{l}\n")).collect();
    let covered = format!("{header}{body}");
    let digest = ops::sha512_256_base64(covered.as_bytes());
    format!("{header};~checksum: {digest}\n{body}").into_bytes()
}

/// Validate a metadata file: `text` plus a canonical placeholder checksum.
fn validate_yaml(text: &str) -> fair_bioheaders_tools::Report {
    let text = format!("{text}checksum: '{}='\n", "A".repeat(43));
    engine()
        .verify_bytes(
            Operation::Validate,
            Container::MetadataYaml,
            text.as_bytes(),
        )
        .unwrap()
}

fn number(report: &fair_bioheaders_tools::Report, key: &str) -> (String, String) {
    match report.metadata.as_ref().and_then(|m| m.get(key)) {
        Some(Value::Number(n)) => (n.canonical(), n.lexeme().to_owned()),
        other => panic!("{key}: {other:?}"),
    }
}

/// Tools#208 section 4 rows 1-3 (FORMAT.md R13 text: integers are exact; R15
/// extension values may be any JSON value).
#[test]
fn integers_are_exact() {
    let cases = [
        ("2147483647", "2147483647"),
        ("2147483648", "2147483648"),
        ("3100000000", "3100000000"),
        ("9007199254740991", "9007199254740991"),
        ("9007199254740992", "9007199254740992"),
        ("9007199254740993", "9007199254740993"),
        ("-9007199254740993", "-9007199254740993"),
        ("9223372036854775807", "9223372036854775807"),
        ("9223372036854775808", "9223372036854775808"),
        ("18446744073709551616", "18446744073709551616"),
        ("-9223372036854775809", "-9223372036854775809"),
        (
            "1000000000000000000000000000000",
            "1000000000000000000000000000000",
        ),
        ("0x1F", "31"),
        ("0xFFFFFFFFFFFFFFFFFFFF", "1208925819614629174706175"),
    ];
    for (lexeme, canonical) in cases {
        let report = validate_yaml(&format!("{FHR21}x-n: {lexeme}\n"));
        assert_eq!(
            report.outcome,
            Outcome::Valid,
            "{lexeme}: {:?}",
            report.first_error()
        );
        assert_eq!(
            number(&report, "x-n"),
            (canonical.to_owned(), lexeme.to_owned())
        );
    }
}

/// Tools#208 section 4 rows 4-6.
#[test]
fn decimals_are_exact_and_r13_applies_to_the_float_path() {
    let report = validate_yaml(&format!(
        "{FHR21}x-a: 1.10\nx-b: 0.1\nx-c: 1.7976931348623157e+308\n"
    ));
    assert_eq!(report.outcome, Outcome::Valid);
    assert_eq!(number(&report, "x-a"), ("1.1".into(), "1.10".into()));
    assert_eq!(number(&report, "x-b"), ("0.1".into(), "0.1".into()));
    for bad in ["1.8e+308", ".inf", "-.inf", ".nan"] {
        let report = validate_yaml(&format!("{FHR21}x-a: {bad}\n"));
        assert_eq!(report.outcome, Outcome::Invalid, "{bad}");
        assert_eq!(report.first_error().unwrap().rule, Some("R13"), "{bad}");
    }
}

/// JSON Schema: a number with zero fractional part is an integer (`1.0`).
#[test]
fn integral_decimal_is_a_schema_integer() {
    let text = format!(
        "{FHT10}completeness:\n  completeSingle: 1.0\n  completeDuplicated: 0\n  fragmented: 0\n  missing: 0\n  total: 1\n  lineageDataset: primates_odb10\n"
    );
    let report = validate_yaml(&text);
    assert_eq!(report.outcome, Outcome::Valid, "{:?}", report.first_error());
}

/// SCHEMA-VERSIONS.md V6: a boolean is not the number 1.
#[test]
fn boolean_schema_version_is_not_fhr1() {
    let text = "schema: https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/fhr.json\nschemaVersion: true\n";
    let report = validate_yaml(text);
    assert_ne!(report.selection.as_ref().map(|s| s.rule), Some("V6"));
}

/// TERMS.md FHT C1 exact arithmetic; decision 12 consumer bound.
#[test]
fn fht_c1_exact_and_consumer_bound() {
    let big = "9007199254740993";
    let record = |total: &str| {
        format!(
            "{FHT10}completeness:\n  completeSingle: {big}\n  completeDuplicated: 0\n  fragmented: 0\n  missing: 0\n  total: {total}\n  lineageDataset: primates_odb10\n"
        )
    };
    assert_eq!(validate_yaml(&record(big)).outcome, Outcome::Valid);
    let wrong = validate_yaml(&record("9007199254740992"));
    assert_eq!(wrong.outcome, Outcome::Invalid);
    assert_eq!(wrong.first_error().unwrap().rule, Some("C1"));
    // The test-narrow profile has no FHT release, so its engine reads FHT URLs
    // as FHR (V5); the consumer bound is exercised through the shared operation.
    let parsed = fair_bioheaders_tools::json::load(
        &format!(
            r#"{{"completeness":{{"completeSingle":{big},"completeDuplicated":0,"fragmented":0,"missing":0,"total":{big}}}}}"#
        ),
        fair_bioheaders_tools::yaml::YamlLimits { nodes: 100, depth: 64, scalar_bytes: 1000 },
    )
    .unwrap()
    .value
    .unwrap();
    assert!(matches!(
        ops::check_fht_completeness(&parsed, Some(53)),
        ops::C1::Limit(_)
    ));
    assert!(matches!(
        ops::check_fht_completeness(&parsed, None),
        ops::C1::Ok
    ));
}

/// FORMAT.md R2 with a location; diagnostics carry the rule id.
#[test]
fn two_checksum_lines_are_r2_with_line() {
    let mut bytes = fasta(FHR21, ">s\nACGT\n");
    let extra = b";~checksum: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n";
    bytes.splice(0..0, extra.iter().copied());
    let report = engine()
        .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
        .unwrap();
    assert_eq!(report.outcome, Outcome::Invalid);
    assert!(
        report
            .diagnostics
            .iter()
            .any(|d| d.rule == Some("R8") || d.rule == Some("R2"))
    );
}

/// SCHEMA-VERSIONS.md V4: unsupported, schema blocked, no fallback.
#[test]
fn unsupported_version_blocks_schema() {
    let text = FHR21.replace("fhr/v0.6.0", "fhr/v9.9.9");
    let report = validate_yaml(&text);
    assert_eq!(report.outcome, Outcome::Unsupported);
    let schema = report.layer(Layer::Schema);
    assert_eq!(schema.status, LayerStatus::NotRun);
    assert_eq!(
        schema.not_run_reason,
        Some(NotRunReason::BlockedBy(Layer::Selection))
    );
    assert!(report.selection.is_none());
}

/// Validate does not run the checksum layer and is still valid.
#[test]
fn validate_does_not_require_checksum() {
    let bytes = fasta(FHR21, ">s\nACGT\n");
    let report = engine()
        .verify_bytes(Operation::Validate, Container::Fasta, &bytes)
        .unwrap();
    assert_eq!(report.outcome, Outcome::Valid, "{:?}", report.first_error());
    assert_eq!(
        report.layer(Layer::Checksum).not_run_reason,
        Some(NotRunReason::NotRequested)
    );
    let verified = engine()
        .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
        .unwrap();
    assert_eq!(verified.outcome, Outcome::Valid);
    assert_eq!(verified.checksum.unwrap().matches, Some(true));
}

/// Schema and checksum errors are both reported, in pipeline order.
#[test]
fn pipeline_order() {
    let mut bytes = fasta(&FHR21.replace("soft-masked", "maybe"), ">s\nACGT\n");
    let n = bytes.len();
    bytes[n - 2] = b'A'; // body tamper
    let report = engine()
        .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
        .unwrap();
    let errors: Vec<&str> = report
        .diagnostics
        .iter()
        .filter(|d| d.severity == fair_bioheaders_tools::Severity::Error)
        .map(|d| d.code)
        .collect();
    assert_eq!(errors.first(), Some(&"SCHEMA.fhr"), "{errors:?}");
    assert!(errors.contains(&"R3.checksum-mismatch"), "{errors:?}");
}

/// FORMAT.md limits: at the bound reads, bound + 1 is a limit (never invalid).
#[test]
fn limits_at_and_over_the_bound() {
    let small = EngineBuilder::new()
        .limit(LimitKind::HeaderLines, 15)
        .build()
        .unwrap();
    let bytes = fasta(FHR21, ">s\nA\n"); // 13 metadata lines + checksum = 14 header lines
    assert_eq!(
        small
            .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
            .unwrap()
            .outcome,
        Outcome::Valid
    );
    let tight = EngineBuilder::new()
        .limit(LimitKind::HeaderLines, 13)
        .build()
        .unwrap();
    let report = tight
        .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
        .unwrap();
    assert_eq!(report.outcome, Outcome::Limit);
    assert_eq!(report.first_error().unwrap().code, "LIMIT.header-lines");
    let nodes = EngineBuilder::new()
        .limit(LimitKind::YamlNodes, 5)
        .build()
        .unwrap();
    let report = nodes
        .verify_bytes(
            Operation::Validate,
            Container::MetadataYaml,
            FHR21.as_bytes(),
        )
        .unwrap();
    assert_eq!(report.outcome, Outcome::Limit);
    assert_eq!(report.first_error().unwrap().code, "LIMIT.yaml-nodes");
    let meta = EngineBuilder::new()
        .limit(LimitKind::MetadataBytes, 64)
        .build()
        .unwrap();
    let report = meta
        .verify_bytes(
            Operation::Validate,
            Container::MetadataYaml,
            FHR21.as_bytes(),
        )
        .unwrap();
    assert_eq!(report.outcome, Outcome::Limit);
    assert_eq!(report.first_error().unwrap().code, "LIMIT.metadata-bytes");
}

/// FR-031 / review 6088963147 finding 3: `in_memory_decompressed_bytes`
/// bounds the header lines a sequence read retains, counted with their
/// copies (`HEADER_COPIES`), while body bytes still stream with no total cap.
#[test]
fn memory_limit_bounds_retained_sequence_headers() {
    use fair_bioheaders_tools::framing::HEADER_COPIES;
    use std::io::Write;
    // A 4 MiB body: far over every memory bound used below.
    let body = format!(">s\n{}\n", "ACGT".repeat(1 << 20));
    let bytes = fasta(FHR21, &body);
    let header_bytes = bytes
        .split_inclusive(|b| *b == b'\n')
        .take_while(|l| l.starts_with(b";~"))
        .map(<[u8]>::len)
        .sum::<usize>() as u64;
    let needed = header_bytes * HEADER_COPIES;
    let mut gz = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    gz.write_all(&bytes).unwrap();
    let gz = gz.finish().unwrap();
    for (limit, expected) in [(needed, Outcome::Valid), (needed - 1, Outcome::Limit)] {
        let e = EngineBuilder::new()
            .limit(LimitKind::InMemoryDecompressedBytes, limit)
            .build()
            .unwrap();
        for op in [Operation::Validate, Operation::Verify] {
            for input in [&bytes, &gz] {
                let report = e.verify_bytes(op, Container::Fasta, input).unwrap();
                assert_eq!(report.outcome, expected, "{op:?} limit {limit}");
                if expected == Outcome::Limit {
                    let first = report.first_error().unwrap();
                    assert_eq!(first.code, "LIMIT.in-memory-decompressed-bytes");
                    assert_eq!(report.layer(Layer::Framing).status, LayerStatus::Limit);
                }
            }
        }
    }
    // The 100-byte case from the review: the equivalent metadata input and the
    // FASTA both report the in-memory limit.
    let e = EngineBuilder::new()
        .limit(LimitKind::InMemoryDecompressedBytes, 100)
        .build()
        .unwrap();
    let small = fasta(FHR21, ">s\nACGT\n");
    for (container, input) in [
        (Container::Fasta, small.as_slice()),
        (Container::MetadataYaml, FHR21.as_bytes()),
    ] {
        let report = e.verify_bytes(Operation::Verify, container, input).unwrap();
        assert_eq!(
            report.first_error().unwrap().code,
            "LIMIT.in-memory-decompressed-bytes",
            "{container:?}"
        );
    }
}

/// Raising a limit needs the explicit call and is recorded.
#[test]
fn raising_limits_is_explicit() {
    let err = EngineBuilder::new()
        .limit(LimitKind::HeaderBytes, 2 << 20)
        .build()
        .unwrap_err();
    assert!(matches!(err, EngineError::InvalidArgument { .. }));
    let raised = EngineBuilder::new()
        .raise_limit(LimitKind::HeaderBytes, 2 << 20)
        .build()
        .unwrap();
    assert!(
        raised
            .provenance()
            .limits_applied
            .iter()
            .any(|(k, v, r)| k == "header_bytes" && *v == 2 << 20 && *r)
    );
}

/// FORMAT.md R1: gzip and BGZF controls (decompressed bytes are what is hashed).
#[test]
fn gzip_members_padding_and_trailing_data() {
    use std::io::Write;
    let plain = fasta(FHR21, ">s\nACGT\n");
    let gz = |data: &[u8]| {
        let mut e = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
        e.write_all(data).unwrap();
        e.finish().unwrap()
    };
    let (a, b) = plain.split_at(40);
    let mut members = gz(a);
    members.extend(gz(b));
    let check = |bytes: &[u8]| {
        engine()
            .verify_bytes(Operation::Verify, Container::Fasta, bytes)
            .unwrap()
    };
    assert_eq!(check(&members).outcome, Outcome::Valid);
    let mut padded = members.clone();
    padded.extend([0u8; 7]);
    assert_eq!(check(&padded).outcome, Outcome::Valid);
    let mut trailing = members.clone();
    trailing.extend(b"x");
    let report = check(&trailing);
    assert_eq!(report.outcome, Outcome::Invalid);
    assert_eq!(report.first_error().unwrap().rule, Some("R1"));
    let truncated = &members[..members.len() - 4];
    assert_eq!(
        check(truncated).first_error().unwrap().code,
        "R1.gzip-truncated"
    );
}

/// Cancellation from another handle ends the stream as cancelled.
#[test]
fn cancellation_is_not_a_verdict() {
    let e = engine();
    let mut stream = e.stream(Operation::Verify, Container::Fasta);
    let handle = stream.cancel_handle();
    stream.feed(b";~a: 1\n").unwrap();
    std::thread::spawn(move || handle.cancel()).join().unwrap();
    assert_eq!(stream.feed(b">s\n").unwrap_err(), EngineError::Cancelled);
}

/// Bytes: embedded NUL and non-UTF-8 body bytes are hashed, never decoded;
/// non-UTF-8 in a header line is R6.
#[test]
fn bytes_and_encoding() {
    let mut bytes = fasta(FHR21, "");
    let raw_body: &[u8] = b">s\nAC\0\xffGT\n";
    // Recompute with the raw body.
    let header: String = FHR21.lines().map(|l| format!(";~{l}\n")).collect();
    let mut covered = header.clone().into_bytes();
    covered.extend_from_slice(raw_body);
    let digest = ops::sha512_256_base64(&covered);
    bytes.clear();
    bytes.extend_from_slice(header.as_bytes());
    bytes.extend_from_slice(format!(";~checksum: {digest}\n").as_bytes());
    bytes.extend_from_slice(raw_body);
    let report = engine()
        .verify_bytes(Operation::Verify, Container::Fasta, &bytes)
        .unwrap();
    assert_eq!(report.outcome, Outcome::Valid, "{:?}", report.first_error());
    let bad = b";~genome: \xff\n>s\n";
    let report = engine()
        .verify_bytes(Operation::Validate, Container::Fasta, bad)
        .unwrap();
    assert_eq!(report.first_error().unwrap().rule, Some("R6"));
    let empty = engine()
        .verify_bytes(Operation::Verify, Container::Fasta, b"")
        .unwrap();
    assert_eq!(empty.outcome, Outcome::Invalid);
}

/// The engine never widens a consumer profile.
#[test]
fn narrow_profile_refuses_newer_releases() {
    let narrow = EngineBuilder::new().profile("test-narrow").build().unwrap();
    let text = FHR21.replace("fhr/v0.6.0", "fhr/v0.8.0");
    let report = narrow
        .verify_bytes(
            Operation::Validate,
            Container::MetadataYaml,
            text.as_bytes(),
        )
        .unwrap();
    assert_eq!(report.outcome, Outcome::Unsupported);
    assert_eq!(report.first_error().unwrap().code, "NOTRUN.outside-profile");
    assert!(matches!(
        EngineBuilder::new()
            .profile("test-narrow")
            .draft_lane("fht")
            .build(),
        Err(EngineError::IncompatibleProfile { .. })
    ));
}

/// Decision 9: ECMA-262 `$` matches only at the end (FHP P1 vector family).
#[test]
fn ecma_dollar_does_not_match_before_final_newline() {
    let text = FHR21.replace("masking: soft-masked", "masking: \"soft-masked\\n\"");
    let report = validate_yaml(&text);
    assert_eq!(
        report.outcome,
        Outcome::Invalid,
        "{:?}",
        report.first_error()
    );
    assert_eq!(
        report
            .first_error()
            .unwrap()
            .location
            .json_pointer
            .as_deref(),
        Some("/masking")
    );
}

/// Decision 9 (disposition 3): `format: uri` is asserted on every install.
/// Expectations follow RFC 3986 (FHR 2.1 `relatedLink` items are
/// `format: uri`); R14 makes a non-link scheme a warning, not an error.
#[test]
fn uri_format_is_asserted_deterministically() {
    for (value, valid) in [
        ("https://example.org/a", true),
        ("urn:x", true),
        ("javascript:alert(1)", true),
        ("not a uri", false),
        ("https://x/a b", false),
        ("https://ex.org/%zz", false),
    ] {
        let text = format!("{FHR21}relatedLink:\n- '{value}'\n");
        let report = validate_yaml(&text);
        assert_eq!(
            report.outcome == Outcome::Valid,
            valid,
            "{value}: {:?}",
            report.first_error()
        );
        if !valid {
            assert_eq!(
                report
                    .first_error()
                    .unwrap()
                    .location
                    .json_pointer
                    .as_deref(),
                Some("/relatedLink/0")
            );
        }
    }
    let report = validate_yaml(&format!("{FHR21}relatedLink:\n- 'javascript:alert(1)'\n"));
    assert!(report.warnings().any(|d| d.rule == Some("R14")));
}

/// Decision 9 (disposition 4): ECMA-262 `\d` is ASCII-only. No bundled contract
/// uses `\d` today, so this is pinned at the validator (schema::tests) and here
/// through the FHR 2.1 ORCID pattern's `[0-9]` with a non-ASCII digit.
#[test]
fn ecma_digits_are_ascii() {
    let text = FHR21.replace(
        "- name: A",
        "- name: A\n  uri: https://orcid.org/0000-0002-5719-402\u{0664}",
    );
    let report = validate_yaml(&text);
    assert_eq!(report.outcome, Outcome::Invalid);
}
