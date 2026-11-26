// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Rust harness over the exported C symbols (Tools#207 section 3,
//! Tools#208 section 5): arguments, ownership, values, streams, errors, and
//! field-for-field projection equality with the safe API over the corpus.

use fair_bioheaders_tools::{Container, Engine, Layer, Operation, Report, Value};
use fhcore::*;
use std::ptr;

fn bytes_of(p: *const u8, n: usize) -> Vec<u8> {
    if n == 0 {
        Vec::new()
    } else {
        unsafe { std::slice::from_raw_parts(p, n) }.to_vec()
    }
}

fn engine() -> *mut fh_engine {
    let mut e = ptr::null_mut();
    let mut err = ptr::null_mut();
    assert_eq!(
        unsafe { fh_engine_new(ptr::null(), &mut e, &mut err) },
        FH_OK
    );
    assert!(err.is_null());
    e
}

fn verify(e: *const fh_engine, op: i32, c: i32, data: &[u8]) -> *mut fh_result {
    let mut r = ptr::null_mut();
    let mut err = ptr::null_mut();
    let rc = unsafe { fh_verify_bytes(e, op, c, data.as_ptr(), data.len(), &mut r, &mut err) };
    assert_eq!(rc, FH_OK, "{}", error_text(err));
    r
}

fn error_text(err: *mut fh_error) -> String {
    if err.is_null() {
        return String::new();
    }
    let (mut p, mut n) = (ptr::null(), 0);
    unsafe { fh_error_message(err, &mut p, &mut n) };
    let text = String::from_utf8_lossy(&bytes_of(p, n)).into_owned();
    unsafe { fh_error_free(err) };
    text
}

const FHR: &[u8] = b"schema: https://w3id.org/fair-bioheaders/fhr/v0.6.0\nschemaVersion: '2.1'\ngenome: \"G\\0x\"\ntaxon:\n  name: H\n  uri: https://identifiers.org/taxonomy:9606\nversion: '1'\nmetadataAuthor:\n- name: A\nassemblyAuthor:\n- name: B\ndateCreated: '2022-03-21'\nmasking: soft-masked\nchecksum: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='\nx-big: 18446744073709551617\nx-dec: 1.10\nx-list: [1, true, null]\n";

#[test]
fn versions_and_capabilities() {
    assert_eq!((fh_abi_major(), fh_abi_minor()), (0, 1));
    let (mut p, mut n) = (ptr::null(), 0);
    assert_eq!(unsafe { fh_engine_version(&mut p, &mut n) }, FH_OK);
    assert_eq!(bytes_of(p, n), Engine::version().as_bytes());
    assert_eq!(
        unsafe { *p.add(n) },
        0,
        "trailing NUL after the counted bytes"
    );
    let e = engine();
    let mut count = 0;
    assert_eq!(
        unsafe { fh_engine_capability_count(e, FH_CAP_PROFILES, &mut count) },
        FH_OK
    );
    assert!(count >= 1);
    assert_eq!(
        unsafe { fh_engine_capability_at(e, FH_CAP_PROFILES, count, &mut p, &mut n) },
        FH_E_RANGE
    );
    unsafe { fh_engine_free(e) };
}

#[test]
fn null_and_wrong_handles_are_refused() {
    let mut r = ptr::null_mut();
    let mut err = ptr::null_mut();
    assert_eq!(
        unsafe { fh_verify_bytes(ptr::null(), 0, 0, ptr::null(), 0, &mut r, &mut err) },
        FH_E_NULL_ARG
    );
    assert!(!err.is_null());
    assert_eq!(unsafe { fh_error_code(err) }, FH_E_NULL_ARG);
    unsafe { fh_error_free(err) };
    let mut o = ptr::null_mut();
    assert_eq!(unsafe { fh_options_new(&mut o) }, FH_OK);
    // An options handle passed as an engine handle: refused, not misread.
    let rc = unsafe {
        fh_verify_bytes(
            o as *const fh_engine,
            0,
            0,
            ptr::null(),
            0,
            &mut r,
            ptr::null_mut(),
        )
    };
    assert_eq!(rc, FH_E_INVALID_HANDLE);
    unsafe { fh_options_free(o) };
    let e = engine();
    assert_eq!(
        unsafe { fh_verify_bytes(e, 9, 0, ptr::null(), 0, &mut r, ptr::null_mut()) },
        FH_E_INVALID_ARGUMENT
    );
    assert_eq!(
        unsafe { fh_verify_bytes(e, 0, 0, ptr::null(), 5, &mut r, ptr::null_mut()) },
        FH_E_NULL_ARG
    );
    // Release functions accept NULL.
    unsafe {
        fh_options_free(ptr::null_mut());
        fh_engine_free(ptr::null_mut());
        fh_stream_free(ptr::null_mut());
        fh_result_free(ptr::null_mut());
        fh_error_free(ptr::null_mut());
        fh_engine_free(e);
    }
}

#[test]
fn options_profiles_and_limits() {
    let mut o = ptr::null_mut();
    unsafe { fh_options_new(&mut o) };
    let id = b"no-such-profile";
    assert_eq!(
        unsafe { fh_options_set_profile(o, id.as_ptr(), id.len()) },
        FH_OK
    );
    let mut e = ptr::null_mut();
    let mut err = ptr::null_mut();
    assert_eq!(
        unsafe { fh_engine_new(o, &mut e, &mut err) },
        FH_E_INCOMPATIBLE
    );
    assert!(e.is_null());
    assert!(error_text(err).contains("no-such-profile"));
    let id = b"python";
    unsafe { fh_options_set_profile(o, id.as_ptr(), id.len()) };
    assert_eq!(
        unsafe { fh_options_set_limit(o, FH_LIMIT_YAML_NODES, 5) },
        FH_OK
    );
    assert_eq!(
        unsafe { fh_options_set_limit(o, 99, 5) },
        FH_E_INVALID_ARGUMENT
    );
    assert_eq!(unsafe { fh_engine_new(o, &mut e, ptr::null_mut()) }, FH_OK);
    let r = verify(e, FH_OP_VALIDATE, FH_C_METADATA_YAML, FHR);
    assert_eq!(unsafe { fh_result_outcome(r) }, FH_OUTCOME_LIMIT);
    unsafe {
        fh_result_free(r);
        fh_engine_free(e);
        fh_options_free(o);
    }
}

#[test]
fn values_are_exact_and_strings_keep_nul() {
    let e = engine();
    let r = verify(e, FH_OP_VALIDATE, FH_C_METADATA_YAML, FHR);
    assert_eq!(unsafe { fh_result_outcome(r) }, FH_OUTCOME_VALID);
    let mut root = ptr::null();
    unsafe { fh_result_metadata(r, &mut root) };
    assert_eq!(unsafe { fh_value_kind(root) }, FH_VALUE_OBJECT);
    let find = |key: &str| -> *const fh_value {
        let mut len = 0;
        unsafe { fh_value_len(root, &mut len) };
        for i in 0..len {
            let (mut p, mut n) = (ptr::null(), 0);
            unsafe { fh_value_key_at(root, i, &mut p, &mut n) };
            if bytes_of(p, n) == key.as_bytes() {
                let mut child = ptr::null();
                unsafe { fh_value_at(root, i, &mut child) };
                return child;
            }
        }
        panic!("{key} missing")
    };
    let big = find("x-big");
    assert_eq!(unsafe { fh_value_kind(big) }, FH_VALUE_INT);
    let mut i = 0i64;
    assert_eq!(unsafe { fh_value_i64(big, &mut i) }, FH_E_RANGE);
    let (mut p, mut n) = (ptr::null(), 0);
    unsafe { fh_value_number_text(big, &mut p, &mut n) };
    assert_eq!(bytes_of(p, n), b"18446744073709551617");
    let (mut f, mut exact) = (0f64, 1);
    unsafe { fh_value_f64(big, &mut f, &mut exact) };
    assert_eq!(exact, 0);
    let dec = find("x-dec");
    assert_eq!(unsafe { fh_value_kind(dec) }, FH_VALUE_DECIMAL);
    unsafe { fh_value_number_lexeme(dec, &mut p, &mut n) };
    assert_eq!(bytes_of(p, n), b"1.10");
    unsafe { fh_value_number_text(dec, &mut p, &mut n) };
    assert_eq!(bytes_of(p, n), b"1.1");
    let genome = find("genome");
    unsafe { fh_value_string(genome, &mut p, &mut n) };
    assert_eq!(
        bytes_of(p, n),
        b"G\0x",
        "U+0000 round-trips with its length"
    );
    let list = find("x-list");
    let mut child = ptr::null();
    assert_eq!(unsafe { fh_value_at(list, 3, &mut child) }, FH_E_RANGE);
    unsafe { fh_value_at(list, 2, &mut child) };
    assert_eq!(unsafe { fh_value_kind(child) }, FH_VALUE_NULL);
    unsafe {
        fh_result_free(r);
        fh_engine_free(e);
    }
}

#[test]
fn streams_feed_finish_cancel() {
    let e = engine();
    let mut s = ptr::null_mut();
    assert_eq!(
        unsafe {
            fh_stream_new(
                e,
                FH_OP_VALIDATE,
                FH_C_METADATA_YAML,
                &mut s,
                ptr::null_mut(),
            )
        },
        FH_OK
    );
    for chunk in FHR.chunks(7) {
        let mut complete = 0;
        assert_eq!(
            unsafe {
                fh_stream_feed(
                    s,
                    chunk.as_ptr(),
                    chunk.len(),
                    &mut complete,
                    ptr::null_mut(),
                )
            },
            FH_OK
        );
    }
    let mut r = ptr::null_mut();
    assert_eq!(
        unsafe { fh_stream_finish(s, &mut r, ptr::null_mut()) },
        FH_OK
    );
    assert_eq!(unsafe { fh_result_outcome(r) }, FH_OUTCOME_VALID);
    let mut again = ptr::null_mut();
    assert_eq!(
        unsafe { fh_stream_finish(s, &mut again, ptr::null_mut()) },
        FH_E_STATE
    );
    unsafe {
        fh_result_free(r);
        fh_stream_free(s);
    }
    let mut s = ptr::null_mut();
    unsafe { fh_stream_new(e, FH_OP_VERIFY, FH_C_FASTA, &mut s, ptr::null_mut()) };
    let addr = s as usize;
    std::thread::spawn(move || unsafe { fh_stream_cancel(addr as *mut fh_stream) })
        .join()
        .unwrap();
    let mut err = ptr::null_mut();
    assert_eq!(
        unsafe { fh_stream_feed(s, b";~a: 1\n".as_ptr(), 7, ptr::null_mut(), &mut err) },
        FH_E_CANCELLED
    );
    error_text(err);
    unsafe {
        fh_stream_free(s);
        fh_engine_free(e);
    }
}

#[test]
fn ten_thousand_cycles_release_cleanly() {
    let e = engine();
    for _ in 0..10_000 {
        let r = verify(e, FH_OP_VALIDATE, FH_C_METADATA_YAML, b"a: [");
        let (mut p, mut n) = (ptr::null(), 0);
        unsafe { fh_result_json(r, &mut p, &mut n) };
        unsafe { fh_result_free(r) };
    }
    unsafe { fh_engine_free(e) };
}

/// Rebuild a `Value` from the C value tree.
fn read_value(v: *const fh_value) -> Value {
    let text = |f: unsafe extern "C" fn(*const fh_value, *mut *const u8, *mut usize) -> fh_rc| {
        let (mut p, mut n) = (ptr::null(), 0);
        assert_eq!(unsafe { f(v, &mut p, &mut n) }, FH_OK);
        String::from_utf8(bytes_of(p, n)).unwrap()
    };
    match unsafe { fh_value_kind(v) } {
        FH_VALUE_NULL => Value::Null,
        FH_VALUE_BOOL => {
            let mut b = 0;
            unsafe { fh_value_bool(v, &mut b) };
            Value::Bool(b == 1)
        }
        FH_VALUE_INT | FH_VALUE_DECIMAL => {
            let lexeme = text(fh_value_number_lexeme);
            let canonical = text(fh_value_number_text);
            let number = if unsafe { fh_value_kind(v) } == FH_VALUE_INT {
                fair_bioheaders_tools::Number::from_bigint(canonical.parse().unwrap(), lexeme)
            } else {
                fair_bioheaders_tools::Number::parse_decimal(&canonical).unwrap()
            };
            Value::Number(number)
        }
        FH_VALUE_STRING => Value::String(text(fh_value_string)),
        kind => {
            let mut len = 0;
            unsafe { fh_value_len(v, &mut len) };
            let children: Vec<Value> = (0..len)
                .map(|i| {
                    let mut c = ptr::null();
                    unsafe { fh_value_at(v, i, &mut c) };
                    read_value(c)
                })
                .collect();
            if kind == FH_VALUE_ARRAY {
                Value::Array(children)
            } else {
                let keys = (0..len).map(|i| {
                    let (mut p, mut n) = (ptr::null(), 0);
                    unsafe { fh_value_key_at(v, i, &mut p, &mut n) };
                    String::from_utf8(bytes_of(p, n)).unwrap()
                });
                Value::Object(keys.zip(children).collect())
            }
        }
    }
}

/// The C projection of a report equals the safe-API report, field for field.
fn assert_projection(r: *const fh_result, report: &Report) {
    let outcome = match report.outcome {
        fair_bioheaders_tools::Outcome::Valid => FH_OUTCOME_VALID,
        fair_bioheaders_tools::Outcome::Invalid => FH_OUTCOME_INVALID,
        fair_bioheaders_tools::Outcome::Unsupported => FH_OUTCOME_UNSUPPORTED,
        fair_bioheaders_tools::Outcome::Limit => FH_OUTCOME_LIMIT,
    };
    assert_eq!(unsafe { fh_result_outcome(r) }, outcome);
    for layer in Layer::ALL {
        let (mut status, mut p, mut n) = (0, ptr::null(), 0);
        unsafe { fh_result_layer_status(r, layer.index() as i32, &mut status, &mut p, &mut n) };
        let expected = report.layer(layer);
        assert_eq!(status, expected.status as i32);
        let reason = expected
            .not_run_reason
            .as_ref()
            .map(|x| x.to_string())
            .unwrap_or_default();
        assert_eq!(bytes_of(p, n), reason.as_bytes());
    }
    assert_eq!(
        unsafe { fh_result_diagnostic_count(r) },
        report.diagnostics.len()
    );
    for (i, d) in report.diagnostics.iter().enumerate() {
        let field = |f| {
            let (mut p, mut n) = (ptr::null(), 0);
            match unsafe { fh_diag_text(r, i, f, &mut p, &mut n) } {
                FH_OK => Some(String::from_utf8(bytes_of(p, n)).unwrap()),
                _ => None,
            }
        };
        assert_eq!(field(FH_DIAG_CODE).as_deref(), Some(d.code));
        assert_eq!(field(FH_DIAG_RULE).as_deref(), d.rule);
        assert_eq!(field(FH_DIAG_MESSAGE).as_deref(), Some(d.message.as_str()));
        assert_eq!(field(FH_DIAG_JSON_POINTER), d.location.json_pointer);
        let mut line = 0;
        unsafe { fh_diag_int(r, i, FH_DIAG_LINE, &mut line) };
        assert_eq!(line, d.location.header_line.map_or(-1, |l| l as i64));
    }
    let (mut p, mut n) = (ptr::null(), 0);
    match &report.selection {
        Some(s) => {
            unsafe { fh_result_selection(r, FH_SEL_SCHEMA_FILE, &mut p, &mut n) };
            assert_eq!(bytes_of(p, n), s.schema_file.as_bytes());
        }
        None => assert_eq!(
            unsafe { fh_result_selection(r, FH_SEL_SCHEMA_FILE, &mut p, &mut n) },
            FH_E_RANGE
        ),
    }
    let computed = report.checksum.as_ref().and_then(|c| c.computed.clone());
    let rc = unsafe { fh_result_checksum(r, FH_CK_COMPUTED, &mut p, &mut n) };
    assert_eq!(
        if rc == FH_OK {
            Some(String::from_utf8(bytes_of(p, n)).unwrap())
        } else {
            None
        },
        computed
    );
    let mut root = ptr::null();
    unsafe { fh_result_metadata(r, &mut root) };
    match &report.metadata {
        Some(m) => assert_eq!(&read_value(root), m),
        None => assert!(root.is_null()),
    }
}

#[test]
fn projection_equals_safe_api_over_the_corpus() {
    let Some(root) = std::env::var_os("FH_SPEC_34BBE21A") else {
        if std::env::var("FH_ALLOW_MISSING_CORPUS").as_deref() == Ok("1")
            && std::env::var("CI").is_err()
        {
            return;
        }
        panic!("set FH_SPEC_34BBE21A (a missing corpus is a failure)");
    };
    let root = std::path::PathBuf::from(root);
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(root.join("conformance/manifest.json")).unwrap())
            .unwrap();
    let safe = Engine::new().unwrap();
    let e = engine();
    let mut checked = 0;
    for vector in manifest["vectors"].as_array().unwrap() {
        let (c, container) = match vector["format"].as_str().unwrap() {
            "fasta" => (FH_C_FASTA, Container::Fasta),
            "fhp-fasta" => (FH_C_FHP_FASTA, Container::FhpFasta),
            "gfa" => (FH_C_GFA, Container::Gfa),
            "fhgff3" => (FH_C_GFF3, Container::Gff3),
            _ => continue,
        };
        let bytes = std::fs::read(
            root.join("conformance")
                .join(vector["file"].as_str().unwrap()),
        )
        .unwrap();
        let report = safe
            .verify_bytes(Operation::Verify, container, &bytes)
            .unwrap();
        let r = verify(e, FH_OP_VERIFY, c, &bytes);
        assert_projection(r, &report);
        unsafe { fh_result_free(r) };
        checked += 1;
    }
    assert_eq!(checked, 254);
    unsafe { fh_engine_free(e) };
}
