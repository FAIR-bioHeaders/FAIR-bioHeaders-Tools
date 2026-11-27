// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The C ABI of the FAIR-bioHeaders engine (`libfhcore`, header `fhcore.h`;
//! Tools#207 section 3). Consumers: the Julia (`@ccall`) and Perl
//! (FFI::Platypus) wrappers.
//!
//! Rules: opaque handles, fixed-width integers, `double` and pointers only;
//! every byte string has an explicit length (outputs also carry a trailing NUL
//! that is not counted); outputs are borrowed from the handle that produced
//! them until its release function runs; every release function accepts NULL;
//! a verdict is `FH_OK` with a result; no thread-local error state; every
//! entry point contains panics and returns `FH_E_INTERNAL`.
//!
//! Not contained (documented for every wrapper): `panic = "abort"` builds, a
//! panic while panicking, a panic in `Drop` during unwinding, allocation
//! failure, stack overflow, `abort` inside a dependency, and memory
//! corruption by a host that violates the pointer, length or ownership rules.

#![allow(non_camel_case_types)]
#![allow(clippy::missing_safety_doc)]

use fair_bioheaders_tools::{
    Container, Engine, EngineBuilder, EngineError, Layer, LayerStatus, LimitKind, Number,
    NumberKind, Operation, Outcome, Report, Severity, Value, Verifier,
};
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, OnceLock};

/// Return codes.
pub type fh_rc = i32;
pub const FH_OK: fh_rc = 0;
pub const FH_E_NULL_ARG: fh_rc = 1;
pub const FH_E_INVALID_HANDLE: fh_rc = 2;
pub const FH_E_INVALID_ARGUMENT: fh_rc = 3;
pub const FH_E_RANGE: fh_rc = 4;
pub const FH_E_STATE: fh_rc = 5;
pub const FH_E_IO: fh_rc = 6;
pub const FH_E_CANCELLED: fh_rc = 7;
pub const FH_E_INCOMPATIBLE: fh_rc = 8;
pub const FH_E_INTERNAL: fh_rc = 9;

/// Operations.
pub const FH_OP_VALIDATE: i32 = 0;
pub const FH_OP_VERIFY: i32 = 1;
/// Containers.
pub const FH_C_AUTO: i32 = 0;
pub const FH_C_FASTA: i32 = 1;
pub const FH_C_FHP_FASTA: i32 = 2;
pub const FH_C_GFA: i32 = 3;
pub const FH_C_GFF3: i32 = 4;
pub const FH_C_METADATA_YAML: i32 = 5;
pub const FH_C_METADATA_JSON: i32 = 6;
/// Outcomes.
pub const FH_OUTCOME_VALID: i32 = 0;
pub const FH_OUTCOME_INVALID: i32 = 1;
pub const FH_OUTCOME_UNSUPPORTED: i32 = 2;
pub const FH_OUTCOME_LIMIT: i32 = 3;
/// Layers.
pub const FH_LAYER_FRAMING: i32 = 0;
pub const FH_LAYER_YAML: i32 = 1;
pub const FH_LAYER_SELECTION: i32 = 2;
pub const FH_LAYER_SCHEMA: i32 = 3;
pub const FH_LAYER_FAMILY: i32 = 4;
pub const FH_LAYER_CHECKSUM: i32 = 5;
pub const FH_LAYER_MODEL: i32 = 6;
/// Layer status.
pub const FH_STATUS_PASS: i32 = 0;
pub const FH_STATUS_FAIL: i32 = 1;
pub const FH_STATUS_NOT_RUN: i32 = 2;
pub const FH_STATUS_UNSUPPORTED: i32 = 3;
pub const FH_STATUS_LIMIT: i32 = 4;
/// Limit kinds.
pub const FH_LIMIT_HEADER_BYTES: i32 = 0;
pub const FH_LIMIT_HEADER_LINES: i32 = 1;
pub const FH_LIMIT_YAML_NODES: i32 = 2;
pub const FH_LIMIT_YAML_DEPTH: i32 = 3;
pub const FH_LIMIT_METADATA_BYTES: i32 = 4;
pub const FH_LIMIT_IN_MEMORY_DECOMPRESSED_BYTES: i32 = 5;
pub const FH_LIMIT_SCALAR_BYTES: i32 = 6;
pub const FH_LIMIT_CONSUMER_EXACT_INTEGER_BITS: i32 = 7;
/// Selection fields.
pub const FH_SEL_HEADER_TYPE: i32 = 0;
pub const FH_SEL_RELEASE: i32 = 1;
pub const FH_SEL_SCHEMA_FILE: i32 = 2;
pub const FH_SEL_SCHEMA_SHA256: i32 = 3;
pub const FH_SEL_RULE: i32 = 4;
/// Checksum fields.
pub const FH_CK_STATED: i32 = 0;
pub const FH_CK_COMPUTED: i32 = 1;
/// Provenance fields.
pub const FH_PROV_ENGINE_VERSION: i32 = 0;
pub const FH_PROV_ABI_VERSION: i32 = 1;
pub const FH_PROV_BUNDLE_ID: i32 = 2;
pub const FH_PROV_BUNDLE_MANIFEST_SHA256: i32 = 3;
pub const FH_PROV_SPEC_COMMIT: i32 = 4;
pub const FH_PROV_PROFILE_ID: i32 = 5;
pub const FH_PROV_PROFILE_SHA256: i32 = 6;
pub const FH_PROV_LIMITS_APPLIED: i32 = 7;
/// Diagnostic text fields.
pub const FH_DIAG_CODE: i32 = 0;
pub const FH_DIAG_RULE: i32 = 1;
pub const FH_DIAG_MESSAGE: i32 = 2;
pub const FH_DIAG_JSON_POINTER: i32 = 3;
/// Diagnostic integer fields (-1 = absent).
pub const FH_DIAG_SEVERITY: i32 = 0;
pub const FH_DIAG_LAYER: i32 = 1;
pub const FH_DIAG_LINE: i32 = 2;
pub const FH_DIAG_BYTE_OFFSET: i32 = 3;
pub const FH_DIAG_BYTE_LEN: i32 = 4;
/// Value kinds.
pub const FH_VALUE_NULL: i32 = 0;
pub const FH_VALUE_BOOL: i32 = 1;
pub const FH_VALUE_INT: i32 = 2;
pub const FH_VALUE_DECIMAL: i32 = 3;
pub const FH_VALUE_STRING: i32 = 4;
pub const FH_VALUE_ARRAY: i32 = 5;
pub const FH_VALUE_OBJECT: i32 = 6;
/// Capability kinds.
pub const FH_CAP_PROFILES: i32 = 0;
pub const FH_CAP_CONTAINERS: i32 = 1;
pub const FH_CAP_DRAFT_LANES: i32 = 2;
pub const FH_CAP_RULES: i32 = 3;

const TAG_OPTIONS: u64 = 0x6668_6f70_7469_6f6e;
const TAG_ENGINE: u64 = 0x6668_656e_6769_6e65;
const TAG_STREAM: u64 = 0x6668_7374_7265_616d;
const TAG_RESULT: u64 = 0x6668_7265_7375_6c74;
const TAG_ERROR: u64 = 0x6668_6572_726f_7221;
const TAG_DEAD: u64 = 0xdead_dead_dead_dead;

/// Owned bytes with a trailing NUL that is not part of the length.
#[derive(Clone, Debug, Default)]
struct Bytes(Vec<u8>);

impl Bytes {
    fn new(data: &[u8]) -> Bytes {
        let mut v = Vec::with_capacity(data.len() + 1);
        v.extend_from_slice(data);
        v.push(0);
        Bytes(v)
    }
    fn of(text: &str) -> Bytes {
        Bytes::new(text.as_bytes())
    }
    fn len(&self) -> usize {
        self.0.len() - 1
    }
    unsafe fn out(&self, p: *mut *const u8, n: *mut usize) {
        unsafe {
            *p = self.0.as_ptr();
            *n = self.len();
        }
    }
}

/// Engine options under construction.
pub struct fh_options {
    tag: u64,
    profile: String,
    limits: Vec<(LimitKind, u64, bool)>,
    lanes: Vec<String>,
}

/// A built engine.
pub struct fh_engine {
    tag: u64,
    engine: Engine,
    capabilities: Vec<Vec<Bytes>>,
}

/// A push stream. Only shared references are ever formed, so
/// `fh_stream_cancel` may run on another thread while a feed is in progress.
pub struct fh_stream {
    tag: u64,
    verifier: Mutex<Option<Verifier>>,
    cancel: fair_bioheaders_tools::CancelHandle,
    poisoned: AtomicBool,
}

/// A metadata value node, borrowed from its result.
pub struct fh_value {
    kind: i32,
    boolean: bool,
    text: Bytes,
    lexeme: Bytes,
    number: Option<Number>,
    children: Vec<fh_value>,
    keys: Vec<Bytes>,
}

/// One diagnostic, projected.
struct Diag {
    code: Bytes,
    rule: Option<Bytes>,
    message: Bytes,
    pointer: Option<Bytes>,
    severity: i64,
    layer: i64,
    line: i64,
    offset: i64,
    len: i64,
}

/// A result.
pub struct fh_result {
    tag: u64,
    report: Report,
    layers: Vec<(i32, Option<Bytes>)>,
    selection: Option<[Bytes; 5]>,
    checksum: [Option<Bytes>; 2],
    provenance: [Bytes; 8],
    diagnostics: Vec<Diag>,
    metadata: Option<Box<fh_value>>,
    json: OnceLock<Bytes>,
}

/// An owned error.
pub struct fh_error {
    tag: u64,
    code: i32,
    message: Bytes,
}

fn engine_error_code(e: &EngineError) -> fh_rc {
    match e {
        EngineError::Io { .. } => FH_E_IO,
        EngineError::Cancelled => FH_E_CANCELLED,
        EngineError::InvalidArgument { .. } => FH_E_INVALID_ARGUMENT,
        EngineError::IncompatibleProfile { .. } => FH_E_INCOMPATIBLE,
        EngineError::State { .. } => FH_E_STATE,
        EngineError::Internal { .. } => FH_E_INTERNAL,
    }
}

unsafe fn set_error(err: *mut *mut fh_error, code: fh_rc, message: &str) -> fh_rc {
    if !err.is_null() {
        let boxed = Box::new(fh_error {
            tag: TAG_ERROR,
            code,
            message: Bytes::of(message),
        });
        unsafe { *err = Box::into_raw(boxed) };
    }
    code
}

fn panic_text(payload: &Box<dyn std::any::Any + Send>) -> String {
    payload
        .downcast_ref::<&str>()
        .map(|s| (*s).to_owned())
        .or_else(|| payload.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "panic".to_owned())
}

/// Run `f`, containing panics; `err` receives an internal error.
unsafe fn guarded(
    err: *mut *mut fh_error,
    f: impl FnOnce() -> Result<(), (fh_rc, String)>,
) -> fh_rc {
    if !err.is_null() {
        unsafe { *err = ptr::null_mut() };
    }
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => FH_OK,
        Ok(Err((code, message))) => unsafe { set_error(err, code, &message) },
        Err(payload) => unsafe { set_error(err, FH_E_INTERNAL, &panic_text(&payload)) },
    }
}

/// Run `f` for functions without an error out-parameter.
fn plain(f: impl FnOnce() -> fh_rc) -> fh_rc {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(FH_E_INTERNAL)
}

unsafe fn bytes_in<'a>(p: *const u8, n: usize) -> Option<&'a [u8]> {
    if n == 0 {
        Some(&[])
    } else if p.is_null() {
        None
    } else {
        Some(unsafe { std::slice::from_raw_parts(p, n) })
    }
}

unsafe fn handle<'a, T>(p: *const T, tag: u64, get: impl Fn(&T) -> u64) -> Result<&'a T, fh_rc> {
    if p.is_null() {
        return Err(FH_E_NULL_ARG);
    }
    let r = unsafe { &*p };
    if get(r) != tag {
        return Err(FH_E_INVALID_HANDLE);
    }
    Ok(r)
}

unsafe fn handle_mut<'a, T>(
    p: *mut T,
    tag: u64,
    get: impl Fn(&T) -> u64,
) -> Result<&'a mut T, fh_rc> {
    if p.is_null() {
        return Err(FH_E_NULL_ARG);
    }
    let r = unsafe { &mut *p };
    if get(r) != tag {
        return Err(FH_E_INVALID_HANDLE);
    }
    Ok(r)
}

fn limit_kind(k: i32) -> Option<LimitKind> {
    LimitKind::ALL.get(usize::try_from(k).ok()?).copied()
}

fn operation(op: i32) -> Option<Operation> {
    match op {
        0 => Some(Operation::Validate),
        1 => Some(Operation::Verify),
        _ => None,
    }
}

fn container(c: i32) -> Option<Container> {
    Some(match c {
        0 => Container::Auto,
        1 => Container::Fasta,
        2 => Container::FhpFasta,
        3 => Container::Gfa,
        4 => Container::Gff3,
        5 => Container::MetadataYaml,
        6 => Container::MetadataJson,
        _ => return None,
    })
}

// ---------------------------------------------------------------- versions

/// The ABI major version.
#[unsafe(no_mangle)]
pub extern "C" fn fh_abi_major() -> u32 {
    fair_bioheaders_tools::ABI_VERSION.0
}

/// The ABI minor version.
#[unsafe(no_mangle)]
pub extern "C" fn fh_abi_minor() -> u32 {
    fair_bioheaders_tools::ABI_VERSION.1
}

static VERSION: OnceLock<Bytes> = OnceLock::new();

/// The engine version (a static string).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_engine_version(p: *mut *const u8, n: *mut usize) -> fh_rc {
    plain(|| {
        if p.is_null() || n.is_null() {
            return FH_E_NULL_ARG;
        }
        unsafe {
            VERSION
                .get_or_init(|| Bytes::of(Engine::version()))
                .out(p, n)
        };
        FH_OK
    })
}

// ---------------------------------------------------------------- options

/// New options (python profile, specification limits).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_new(out: *mut *mut fh_options) -> fh_rc {
    plain(|| {
        if out.is_null() {
            return FH_E_NULL_ARG;
        }
        let boxed = Box::new(fh_options {
            tag: TAG_OPTIONS,
            profile: "python".into(),
            limits: Vec::new(),
            lanes: Vec::new(),
        });
        unsafe { *out = Box::into_raw(boxed) };
        FH_OK
    })
}

/// Release options (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_free(o: *mut fh_options) {
    let _ = plain(|| {
        if !o.is_null() && unsafe { (*o).tag } == TAG_OPTIONS {
            unsafe { (*o).tag = TAG_DEAD };
            drop(unsafe { Box::from_raw(o) });
        }
        FH_OK
    });
}

/// Select a profile by id (UTF-8 bytes).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_set_profile(
    o: *mut fh_options,
    id: *const u8,
    n: usize,
) -> fh_rc {
    plain(|| {
        let options = match unsafe { handle_mut(o, TAG_OPTIONS, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(bytes) = (unsafe { bytes_in(id, n) }) else {
            return FH_E_NULL_ARG;
        };
        match std::str::from_utf8(bytes) {
            Ok(text) => {
                options.profile = text.to_owned();
                FH_OK
            }
            Err(_) => FH_E_INVALID_ARGUMENT,
        }
    })
}

unsafe fn set_limit(o: *mut fh_options, kind: i32, value: u64, raise: bool) -> fh_rc {
    plain(|| {
        let options = match unsafe { handle_mut(o, TAG_OPTIONS, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(kind) = limit_kind(kind) else {
            return FH_E_INVALID_ARGUMENT;
        };
        options.limits.push((kind, value, raise));
        FH_OK
    })
}

/// Lower (or keep) a limit.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_set_limit(
    o: *mut fh_options,
    limit_kind: i32,
    value: u64,
) -> fh_rc {
    unsafe { set_limit(o, limit_kind, value, false) }
}

/// Raise a limit above the specification value (recorded in provenance).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_raise_limit(
    o: *mut fh_options,
    limit_kind: i32,
    value: u64,
) -> fh_rc {
    unsafe { set_limit(o, limit_kind, value, true) }
}

/// Open a draft lane by name.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_options_enable_draft_lane(
    o: *mut fh_options,
    lane: *const u8,
    n: usize,
) -> fh_rc {
    plain(|| {
        let options = match unsafe { handle_mut(o, TAG_OPTIONS, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(bytes) = (unsafe { bytes_in(lane, n) }) else {
            return FH_E_NULL_ARG;
        };
        match std::str::from_utf8(bytes) {
            Ok(text) => {
                options.lanes.push(text.to_owned());
                FH_OK
            }
            Err(_) => FH_E_INVALID_ARGUMENT,
        }
    })
}

// ---------------------------------------------------------------- engine

/// Build an engine from options (NULL options = defaults).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_engine_new(
    o: *const fh_options,
    out: *mut *mut fh_engine,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            if out.is_null() {
                return Err((FH_E_NULL_ARG, "out is NULL".into()));
            }
            *out = ptr::null_mut();
            let mut builder = EngineBuilder::new();
            if !o.is_null() {
                let options = handle(o, TAG_OPTIONS, |x| x.tag)
                    .map_err(|rc| (rc, "invalid options handle".to_owned()))?;
                builder = builder.profile(&options.profile);
                for (kind, value, raise) in &options.limits {
                    builder = if *raise {
                        builder.raise_limit(*kind, *value)
                    } else {
                        builder.limit(*kind, *value)
                    };
                }
                for lane in &options.lanes {
                    builder = builder.draft_lane(lane);
                }
            }
            let engine = builder
                .build()
                .map_err(|e| (engine_error_code(&e), e.to_string()))?;
            let caps = engine.capabilities();
            let capabilities = [caps.profiles, caps.containers, caps.draft_lanes, caps.rules]
                .into_iter()
                .map(|list| list.iter().map(|s| Bytes::of(s)).collect())
                .collect();
            *out = Box::into_raw(Box::new(fh_engine {
                tag: TAG_ENGINE,
                engine,
                capabilities,
            }));
            Ok(())
        })
    }
}

/// Release an engine (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_engine_free(e: *mut fh_engine) {
    let _ = plain(|| {
        if !e.is_null() && unsafe { (*e).tag } == TAG_ENGINE {
            unsafe { (*e).tag = TAG_DEAD };
            drop(unsafe { Box::from_raw(e) });
        }
        FH_OK
    });
}

/// Number of capability strings of a kind (0 profiles, 1 containers, 2 draft lanes, 3 rules).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_engine_capability_count(
    e: *const fh_engine,
    cap_kind: i32,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let engine = match unsafe { handle(e, TAG_ENGINE, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if n.is_null() {
            return FH_E_NULL_ARG;
        }
        match usize::try_from(cap_kind)
            .ok()
            .and_then(|k| engine.capabilities.get(k))
        {
            Some(list) => {
                unsafe { *n = list.len() };
                FH_OK
            }
            None => FH_E_INVALID_ARGUMENT,
        }
    })
}

/// One capability string (borrowed from the engine).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_engine_capability_at(
    e: *const fh_engine,
    cap_kind: i32,
    i: usize,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let engine = match unsafe { handle(e, TAG_ENGINE, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if p.is_null() || n.is_null() {
            return FH_E_NULL_ARG;
        }
        let Some(list) = usize::try_from(cap_kind)
            .ok()
            .and_then(|k| engine.capabilities.get(k))
        else {
            return FH_E_INVALID_ARGUMENT;
        };
        match list.get(i) {
            Some(b) => {
                unsafe { b.out(p, n) };
                FH_OK
            }
            None => FH_E_RANGE,
        }
    })
}

// ---------------------------------------------------------------- results

fn status_code(s: LayerStatus) -> i32 {
    match s {
        LayerStatus::Pass => 0,
        LayerStatus::Fail => 1,
        LayerStatus::NotRun => 2,
        LayerStatus::Unsupported => 3,
        LayerStatus::Limit => 4,
    }
}

fn outcome_code(o: Outcome) -> i32 {
    match o {
        Outcome::Valid => 0,
        Outcome::Invalid => 1,
        Outcome::Unsupported => 2,
        Outcome::Limit => 3,
    }
}

fn project_value(v: &Value) -> fh_value {
    let mut node = fh_value {
        kind: 0,
        boolean: false,
        text: Bytes::default(),
        lexeme: Bytes::default(),
        number: None,
        children: Vec::new(),
        keys: Vec::new(),
    };
    match v {
        Value::Null => node.kind = 0,
        Value::Bool(b) => {
            node.kind = 1;
            node.boolean = *b;
        }
        Value::Number(n) => {
            node.kind = if n.kind() == NumberKind::Int { 2 } else { 3 };
            node.text = Bytes::of(&n.canonical());
            node.lexeme = Bytes::of(n.lexeme());
            node.number = Some(n.clone());
        }
        Value::String(s) => {
            node.kind = 4;
            node.text = Bytes::of(s);
        }
        Value::Array(items) => {
            node.kind = 5;
            node.children = items.iter().map(project_value).collect();
        }
        Value::Object(items) => {
            node.kind = 6;
            node.keys = items.iter().map(|(k, _)| Bytes::of(k)).collect();
            node.children = items.iter().map(|(_, v)| project_value(v)).collect();
        }
    }
    node
}

fn project(report: Report) -> fh_result {
    let layers = Layer::ALL
        .iter()
        .map(|l| {
            let r = report.layer(*l);
            (
                status_code(r.status),
                r.not_run_reason.as_ref().map(|x| Bytes::of(&x.to_string())),
            )
        })
        .collect();
    let selection = report.selection.as_ref().map(|s| {
        [
            Bytes::of(&s.header_type),
            Bytes::of(&s.release),
            Bytes::of(&s.schema_file),
            Bytes::of(&s.schema_sha256),
            Bytes::of(s.rule),
        ]
    });
    let checksum = match &report.checksum {
        Some(c) => [
            c.stated.as_deref().map(Bytes::of),
            c.computed.as_deref().map(Bytes::of),
        ],
        None => [None, None],
    };
    let p = &report.provenance;
    let limits = serde_json::Value::Array(
        p.limits_applied
            .iter()
            .map(|(k, v, r)| serde_json::json!({"kind": k, "value": v, "raised": r}))
            .collect(),
    )
    .to_string();
    let provenance = [
        Bytes::of(&p.engine_version),
        Bytes::of(&p.abi_version),
        Bytes::of(&p.bundle_id),
        Bytes::of(&p.bundle_manifest_sha256),
        Bytes::of(&p.spec_commit),
        Bytes::of(&p.profile_id),
        Bytes::of(&p.profile_sha256),
        Bytes::of(&limits),
    ];
    let opt = |v: Option<u64>| v.map_or(-1, |x| x as i64);
    let diagnostics = report
        .diagnostics
        .iter()
        .map(|d| Diag {
            code: Bytes::of(d.code),
            rule: d.rule.map(Bytes::of),
            message: Bytes::of(&d.message),
            pointer: d.location.json_pointer.as_deref().map(Bytes::of),
            severity: if d.severity == Severity::Error { 0 } else { 1 },
            layer: d.layer.index() as i64,
            line: opt(d.location.header_line),
            offset: opt(d.location.byte_offset),
            len: opt(d.location.byte_len),
        })
        .collect();
    let metadata = report.metadata.as_ref().map(|m| Box::new(project_value(m)));
    fh_result {
        tag: TAG_RESULT,
        report,
        layers,
        selection,
        checksum,
        provenance,
        diagnostics,
        metadata,
        json: OnceLock::new(),
    }
}

unsafe fn emit(
    out: *mut *mut fh_result,
    result: Result<Report, EngineError>,
) -> Result<(), (fh_rc, String)> {
    match result {
        Ok(report) => {
            unsafe { *out = Box::into_raw(Box::new(project(report))) };
            Ok(())
        }
        Err(e) => Err((engine_error_code(&e), e.to_string())),
    }
}

/// One-shot read of a buffer.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_verify_bytes(
    e: *const fh_engine,
    op: i32,
    c: i32,
    data: *const u8,
    n: usize,
    out: *mut *mut fh_result,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            if out.is_null() {
                return Err((FH_E_NULL_ARG, "out is NULL".into()));
            }
            *out = ptr::null_mut();
            let engine = handle(e, TAG_ENGINE, |x| x.tag)
                .map_err(|rc| (rc, "invalid engine handle".to_owned()))?;
            let op =
                operation(op).ok_or((FH_E_INVALID_ARGUMENT, "unknown operation".to_owned()))?;
            let c = container(c).ok_or((FH_E_INVALID_ARGUMENT, "unknown container".to_owned()))?;
            let input = bytes_in(data, n)
                .ok_or((FH_E_NULL_ARG, "data is NULL with nonzero length".to_owned()))?;
            emit(out, engine.engine.verify_bytes(op, c, input))
        })
    }
}

/// One-shot read of a file (path as OS bytes).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_verify_file(
    e: *const fh_engine,
    op: i32,
    c: i32,
    path: *const u8,
    n: usize,
    out: *mut *mut fh_result,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            if out.is_null() {
                return Err((FH_E_NULL_ARG, "out is NULL".into()));
            }
            *out = ptr::null_mut();
            let engine = handle(e, TAG_ENGINE, |x| x.tag)
                .map_err(|rc| (rc, "invalid engine handle".to_owned()))?;
            let op =
                operation(op).ok_or((FH_E_INVALID_ARGUMENT, "unknown operation".to_owned()))?;
            let c = container(c).ok_or((FH_E_INVALID_ARGUMENT, "unknown container".to_owned()))?;
            let bytes = bytes_in(path, n).ok_or((FH_E_NULL_ARG, "path is NULL".to_owned()))?;
            if bytes.is_empty() || bytes.contains(&0) {
                return Err((
                    FH_E_INVALID_ARGUMENT,
                    "path is empty or contains NUL".into(),
                ));
            }
            #[cfg(unix)]
            let path = {
                use std::os::unix::ffi::OsStrExt;
                std::path::PathBuf::from(std::ffi::OsStr::from_bytes(bytes))
            };
            #[cfg(not(unix))]
            let path = std::path::PathBuf::from(
                std::str::from_utf8(bytes)
                    .map_err(|_| (FH_E_INVALID_ARGUMENT, "path is not UTF-8".to_owned()))?,
            );
            emit(out, engine.engine.verify_path(op, c, &path))
        })
    }
}

/// The outcome (0 valid, 1 invalid, 2 unsupported, 3 limit; -1 bad handle).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_outcome(r: *const fh_result) -> i32 {
    plain(|| match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
        Ok(result) => outcome_code(result.report.outcome),
        Err(_) => -1,
    })
}

/// A layer's status and not-run reason (reason empty when absent).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_layer_status(
    r: *const fh_result,
    layer: i32,
    status: *mut i32,
    reason: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if status.is_null() {
            return FH_E_NULL_ARG;
        }
        let Some((s, why)) = usize::try_from(layer)
            .ok()
            .and_then(|l| result.layers.get(l))
        else {
            return FH_E_INVALID_ARGUMENT;
        };
        unsafe { *status = *s };
        if !reason.is_null() && !n.is_null() {
            static EMPTY: OnceLock<Bytes> = OnceLock::new();
            let empty = EMPTY.get_or_init(|| Bytes::of(""));
            unsafe { why.as_ref().unwrap_or(empty).out(reason, n) };
        }
        FH_OK
    })
}

unsafe fn out_opt(b: Option<&Bytes>, p: *mut *const u8, n: *mut usize) -> fh_rc {
    if p.is_null() || n.is_null() {
        return FH_E_NULL_ARG;
    }
    match b {
        Some(b) => {
            unsafe { b.out(p, n) };
            FH_OK
        }
        None => FH_E_RANGE,
    }
}

/// Selection fields (0 type, 1 release, 2 file, 3 sha256, 4 rule); FH_E_RANGE if none.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_selection(
    r: *const fh_result,
    field: i32,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Ok(field) = usize::try_from(field) else {
            return FH_E_INVALID_ARGUMENT;
        };
        if field > 4 {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { out_opt(result.selection.as_ref().map(|s| &s[field]), p, n) }
    })
}

/// Checksum fields (0 stated, 1 computed); FH_E_RANGE if absent.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_checksum(
    r: *const fh_result,
    field: i32,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(slot) = usize::try_from(field)
            .ok()
            .and_then(|f| result.checksum.get(f))
        else {
            return FH_E_INVALID_ARGUMENT;
        };
        unsafe { out_opt(slot.as_ref(), p, n) }
    })
}

/// Whether the checksum matched (-1 not run, 0 no, 1 yes).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_checksum_matches(r: *const fh_result, tri: *mut i32) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if tri.is_null() {
            return FH_E_NULL_ARG;
        }
        let value = match result.report.checksum.as_ref().and_then(|c| c.matches) {
            None => -1,
            Some(false) => 0,
            Some(true) => 1,
        };
        unsafe { *tri = value };
        FH_OK
    })
}

/// Provenance fields (0..7; 7 is the applied limits as JSON).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_provenance(
    r: *const fh_result,
    field: i32,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(b) = usize::try_from(field)
            .ok()
            .and_then(|f| result.provenance.get(f))
        else {
            return FH_E_INVALID_ARGUMENT;
        };
        unsafe { out_opt(Some(b), p, n) }
    })
}

/// Number of diagnostics (0 for an invalid handle).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_diagnostic_count(r: *const fh_result) -> usize {
    catch_unwind(AssertUnwindSafe(|| {
        match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(result) => result.diagnostics.len(),
            Err(_) => 0,
        }
    }))
    .unwrap_or(0)
}

/// Diagnostic text fields (0 code, 1 rule, 2 message, 3 JSON pointer); FH_E_RANGE if absent.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_diag_text(
    r: *const fh_result,
    i: usize,
    field: i32,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        let Some(d) = result.diagnostics.get(i) else {
            return FH_E_RANGE;
        };
        let b = match field {
            0 => Some(&d.code),
            1 => d.rule.as_ref(),
            2 => Some(&d.message),
            3 => d.pointer.as_ref(),
            _ => return FH_E_INVALID_ARGUMENT,
        };
        unsafe { out_opt(b, p, n) }
    })
}

/// Diagnostic integer fields (0 severity, 1 layer, 2 line, 3 byte offset, 4 byte length; -1 absent).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_diag_int(
    r: *const fh_result,
    i: usize,
    field: i32,
    v: *mut i64,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if v.is_null() {
            return FH_E_NULL_ARG;
        }
        let Some(d) = result.diagnostics.get(i) else {
            return FH_E_RANGE;
        };
        let value = match field {
            0 => d.severity,
            1 => d.layer,
            2 => d.line,
            3 => d.offset,
            4 => d.len,
            _ => return FH_E_INVALID_ARGUMENT,
        };
        unsafe { *v = value };
        FH_OK
    })
}

/// Derived JSON view (logging and differentials only).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_json(
    r: *const fh_result,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if p.is_null() || n.is_null() {
            return FH_E_NULL_ARG;
        }
        unsafe {
            result
                .json
                .get_or_init(|| Bytes::of(&result.report.to_json()))
                .out(p, n)
        };
        FH_OK
    })
}

/// Release a result (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_free(r: *mut fh_result) {
    let _ = plain(|| {
        if !r.is_null() && unsafe { (*r).tag } == TAG_RESULT {
            unsafe { (*r).tag = TAG_DEAD };
            drop(unsafe { Box::from_raw(r) });
        }
        FH_OK
    });
}

// ---------------------------------------------------------------- values

/// The metadata root (NULL when there is none).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_result_metadata(
    r: *const fh_result,
    root: *mut *const fh_value,
) -> fh_rc {
    plain(|| {
        let result = match unsafe { handle(r, TAG_RESULT, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        if root.is_null() {
            return FH_E_NULL_ARG;
        }
        unsafe {
            *root = result
                .metadata
                .as_deref()
                .map_or(ptr::null(), |v| v as *const fh_value)
        };
        FH_OK
    })
}

unsafe fn node<'a>(v: *const fh_value) -> Option<&'a fh_value> {
    if v.is_null() {
        None
    } else {
        Some(unsafe { &*v })
    }
}

/// Value kind (0 null, 1 bool, 2 int, 3 decimal, 4 string, 5 array, 6 object; -1 NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_kind(v: *const fh_value) -> i32 {
    plain(|| unsafe { node(v) }.map_or(-1, |n| n.kind))
}

/// A boolean.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_bool(v: *const fh_value, b: *mut i32) -> fh_rc {
    plain(|| {
        let Some(n) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if b.is_null() {
            return FH_E_NULL_ARG;
        }
        if n.kind != 1 {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { *b = i32::from(n.boolean) };
        FH_OK
    })
}

/// An integer as `int64_t`; FH_E_RANGE when it does not fit.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_i64(v: *const fh_value, out: *mut i64) -> fh_rc {
    plain(|| {
        let Some(n) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if out.is_null() {
            return FH_E_NULL_ARG;
        }
        let Some(number) = &n.number else {
            return FH_E_INVALID_ARGUMENT;
        };
        match number.as_i64() {
            Some(x) => {
                unsafe { *out = x };
                FH_OK
            }
            None => FH_E_RANGE,
        }
    })
}

/// The canonical exact decimal text of a number.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_number_text(
    v: *const fh_value,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if node.number.is_none() {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { out_opt(Some(&node.text), p, n) }
    })
}

/// The source text of a number (e.g. `0x1F`, `1.10`).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_number_lexeme(
    v: *const fh_value,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if node.number.is_none() {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { out_opt(Some(&node.lexeme), p, n) }
    })
}

/// The nearest double and whether it is exact.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_f64(v: *const fh_value, out: *mut f64, exact: *mut i32) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if out.is_null() {
            return FH_E_NULL_ARG;
        }
        let Some(number) = &node.number else {
            return FH_E_INVALID_ARGUMENT;
        };
        let (value, is_exact) = number.as_f64();
        unsafe { *out = value };
        if !exact.is_null() {
            unsafe { *exact = i32::from(is_exact) };
        }
        FH_OK
    })
}

/// A string's UTF-8 bytes (may contain U+0000).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_string(
    v: *const fh_value,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if node.kind != 4 {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { out_opt(Some(&node.text), p, n) }
    })
}

/// Number of items (array) or members (object).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_len(v: *const fh_value, n: *mut usize) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if n.is_null() {
            return FH_E_NULL_ARG;
        }
        if node.kind != 5 && node.kind != 6 {
            return FH_E_INVALID_ARGUMENT;
        }
        unsafe { *n = node.children.len() };
        FH_OK
    })
}

/// The i-th item or member value.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_at(
    v: *const fh_value,
    i: usize,
    child: *mut *const fh_value,
) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if child.is_null() {
            return FH_E_NULL_ARG;
        }
        match node.children.get(i) {
            Some(c) => {
                unsafe { *child = c as *const fh_value };
                FH_OK
            }
            None => FH_E_RANGE,
        }
    })
}

/// The i-th member key of an object (source order).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_value_key_at(
    v: *const fh_value,
    i: usize,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let Some(node) = (unsafe { node(v) }) else {
            return FH_E_NULL_ARG;
        };
        if node.kind != 6 {
            return FH_E_INVALID_ARGUMENT;
        }
        match node.keys.get(i) {
            Some(k) => unsafe { out_opt(Some(k), p, n) },
            None => FH_E_RANGE,
        }
    })
}

// ---------------------------------------------------------------- streams

/// A push stream.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_stream_new(
    e: *const fh_engine,
    op: i32,
    c: i32,
    out: *mut *mut fh_stream,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            if out.is_null() {
                return Err((FH_E_NULL_ARG, "out is NULL".into()));
            }
            *out = ptr::null_mut();
            let engine = handle(e, TAG_ENGINE, |x| x.tag)
                .map_err(|rc| (rc, "invalid engine handle".to_owned()))?;
            let op =
                operation(op).ok_or((FH_E_INVALID_ARGUMENT, "unknown operation".to_owned()))?;
            let c = container(c).ok_or((FH_E_INVALID_ARGUMENT, "unknown container".to_owned()))?;
            let verifier = engine.engine.stream(op, c);
            let cancel = verifier.cancel_handle();
            *out = Box::into_raw(Box::new(fh_stream {
                tag: TAG_STREAM,
                verifier: Mutex::new(Some(verifier)),
                cancel,
                poisoned: AtomicBool::new(false),
            }));
            Ok(())
        })
    }
}

/// Feed a chunk; `complete` (optional) is set to 1 once Validate may stop.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_stream_feed(
    s: *mut fh_stream,
    chunk: *const u8,
    n: usize,
    complete: *mut i32,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            let stream = handle(s, TAG_STREAM, |x| x.tag)
                .map_err(|rc| (rc, "invalid stream handle".to_owned()))?;
            if stream.poisoned.load(Ordering::SeqCst) {
                return Err((
                    FH_E_STATE,
                    "the stream failed internally and cannot be used".into(),
                ));
            }
            let mut guard = stream.verifier.try_lock().map_err(|_| {
                (
                    FH_E_STATE,
                    "the stream is in use by another thread".to_owned(),
                )
            })?;
            let verifier = guard
                .as_mut()
                .ok_or((FH_E_STATE, "the stream is finished".to_owned()))?;
            let data = bytes_in(chunk, n).ok_or((
                FH_E_NULL_ARG,
                "chunk is NULL with nonzero length".to_owned(),
            ))?;
            match verifier.feed(data) {
                Ok(progress) => {
                    if !complete.is_null() {
                        *complete =
                            i32::from(progress == fair_bioheaders_tools::Progress::Complete);
                    }
                    Ok(())
                }
                Err(e) => {
                    if matches!(e, EngineError::Internal { .. }) {
                        stream.poisoned.store(true, Ordering::SeqCst);
                    }
                    Err((engine_error_code(&e), e.to_string()))
                }
            }
        })
    }
}

/// Finish the stream and produce the result (the stream must still be freed).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_stream_finish(
    s: *mut fh_stream,
    out: *mut *mut fh_result,
    err: *mut *mut fh_error,
) -> fh_rc {
    unsafe {
        guarded(err, || {
            if out.is_null() {
                return Err((FH_E_NULL_ARG, "out is NULL".into()));
            }
            *out = ptr::null_mut();
            let stream = handle(s, TAG_STREAM, |x| x.tag)
                .map_err(|rc| (rc, "invalid stream handle".to_owned()))?;
            if stream.poisoned.load(Ordering::SeqCst) {
                return Err((
                    FH_E_STATE,
                    "the stream failed internally and cannot be used".into(),
                ));
            }
            let taken = stream
                .verifier
                .try_lock()
                .map_err(|_| {
                    (
                        FH_E_STATE,
                        "the stream is in use by another thread".to_owned(),
                    )
                })?
                .take();
            let verifier = taken.ok_or((FH_E_STATE, "the stream is finished".to_owned()))?;
            emit(out, verifier.finish())
        })
    }
}

/// Cancel a stream; safe from any thread while another thread feeds it.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_stream_cancel(s: *mut fh_stream) {
    let _ = plain(|| {
        if !s.is_null() && unsafe { (*s).tag } == TAG_STREAM {
            // Only the shared atomic flag is touched.
            unsafe { (*s).cancel.cancel() };
        }
        FH_OK
    });
}

/// Release a stream (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_stream_free(s: *mut fh_stream) {
    let _ = plain(|| {
        if !s.is_null() && unsafe { (*s).tag } == TAG_STREAM {
            let mut owned = unsafe { Box::from_raw(s) };
            owned.tag = TAG_DEAD;
            drop(owned);
        }
        FH_OK
    });
}

// ---------------------------------------------------------------- errors

/// An error's return code (-1 for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_error_code(e: *const fh_error) -> i32 {
    plain(|| match unsafe { handle(e, TAG_ERROR, |x| x.tag) } {
        Ok(error) => error.code,
        Err(_) => -1,
    })
}

/// An error's message (UTF-8).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_error_message(
    e: *const fh_error,
    p: *mut *const u8,
    n: *mut usize,
) -> fh_rc {
    plain(|| {
        let error = match unsafe { handle(e, TAG_ERROR, |x| x.tag) } {
            Ok(x) => x,
            Err(rc) => return rc,
        };
        unsafe { out_opt(Some(&error.message), p, n) }
    })
}

/// Release an error (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_error_free(e: *mut fh_error) {
    let _ = plain(|| {
        if !e.is_null() && unsafe { (*e).tag } == TAG_ERROR {
            unsafe { (*e).tag = TAG_DEAD };
            drop(unsafe { Box::from_raw(e) });
        }
        FH_OK
    });
}

/// Test-only: panic inside the boundary (never in release artifacts).
#[cfg(feature = "fault-injection")]
#[unsafe(no_mangle)]
pub unsafe extern "C" fn fh_test_panic(err: *mut *mut fh_error) -> fh_rc {
    unsafe {
        guarded(err, || {
            panic!("fault-injection: deliberate panic inside the C ABI")
        })
    }
}
