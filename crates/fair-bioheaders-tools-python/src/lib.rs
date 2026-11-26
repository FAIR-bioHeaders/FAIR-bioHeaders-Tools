// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! `fair_bioheaders_tools._native`: the PyO3 binding of the engine over the
//! safe Rust API (Tools#207 sections 4-6). Results are converted eagerly into
//! Python objects; no engine handle other than the engine and stream objects
//! reaches Python. Engine work runs with the interpreter detached.

use fair_bioheaders_tools::{
    Container, Engine, EngineBuilder, EngineError, Layer, LimitKind, NumberKind, Operation, Report,
    Value, Verifier,
};
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyOSError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use std::sync::Mutex;

create_exception!(
    _native,
    EngineErrorBase,
    PyException,
    "A call failure of the engine (never a verdict)."
);
create_exception!(
    _native,
    InternalError,
    EngineErrorBase,
    "A contained internal failure (panic) of the engine."
);
create_exception!(
    _native,
    CancelledError,
    EngineErrorBase,
    "The stream was cancelled."
);
create_exception!(
    _native,
    StateError,
    EngineErrorBase,
    "The stream is finished, in use or poisoned."
);
create_exception!(
    _native,
    ProfileError,
    EngineErrorBase,
    "The requested profile or draft lane is not available."
);

fn to_py_err(e: EngineError) -> PyErr {
    match e {
        EngineError::Io { message } => PyOSError::new_err(message),
        EngineError::Cancelled => CancelledError::new_err("cancelled"),
        EngineError::InvalidArgument { message } => PyValueError::new_err(message),
        EngineError::IncompatibleProfile { message } => ProfileError::new_err(message),
        EngineError::State { message } => StateError::new_err(message),
        EngineError::Internal { message } => InternalError::new_err(message),
    }
}

fn operation(name: &str) -> PyResult<Operation> {
    match name {
        "validate" => Ok(Operation::Validate),
        "verify" => Ok(Operation::Verify),
        other => Err(PyValueError::new_err(format!(
            "unknown operation {other:?}; use 'validate' or 'verify'"
        ))),
    }
}

fn container(name: &str) -> PyResult<Container> {
    Ok(match name {
        "auto" => Container::Auto,
        "fasta" => Container::Fasta,
        "fhp-fasta" => Container::FhpFasta,
        "gfa" => Container::Gfa,
        "gff3" => Container::Gff3,
        "metadata-yaml" => Container::MetadataYaml,
        "metadata-json" => Container::MetadataJson,
        other => {
            return Err(PyValueError::new_err(format!(
                "unknown container {other:?}"
            )));
        }
    })
}

fn limit_kind(name: &str) -> PyResult<LimitKind> {
    LimitKind::ALL
        .iter()
        .copied()
        .find(|k| k.as_str() == name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown limit {name:?}")))
}

/// Convert the exact value tree into Python objects.
fn value_to_py<'py>(
    py: Python<'py>,
    value: &Value,
    exact_decimals: bool,
) -> PyResult<Bound<'py, PyAny>> {
    Ok(match value {
        Value::Null => py.None().into_bound(py),
        Value::Bool(b) => b.into_pyobject(py)?.to_owned().into_any(),
        Value::Number(n) => match n.kind() {
            NumberKind::Int => match n.as_i64() {
                Some(i) => i.into_pyobject(py)?.into_any(),
                None => py
                    .import("builtins")?
                    .getattr("int")?
                    .call1((n.canonical(),))?,
            },
            NumberKind::Decimal if exact_decimals => py
                .import("decimal")?
                .getattr("Decimal")?
                .call1((n.canonical(),))?,
            NumberKind::Decimal => {
                // The correctly rounded nearest double of the exact value,
                // which is what PyYAML and json produce from the same text.
                let (f, _) = n.as_f64();
                f.into_pyobject(py)?.into_any()
            }
        },
        Value::String(s) => s.into_pyobject(py)?.into_any(),
        Value::Array(items) => {
            let list = PyList::empty(py);
            for item in items {
                list.append(value_to_py(py, item, exact_decimals)?)?;
            }
            list.into_any()
        }
        Value::Object(items) => {
            let dict = PyDict::new(py);
            for (key, item) in items {
                dict.set_item(key, value_to_py(py, item, exact_decimals)?)?;
            }
            dict.into_any()
        }
    })
}

fn report_to_py<'py>(
    py: Python<'py>,
    report: &Report,
    exact_decimals: bool,
) -> PyResult<Bound<'py, PyDict>> {
    let out = PyDict::new(py);
    out.set_item("outcome", report.outcome.as_str())?;
    out.set_item("container", report.container.as_str())?;
    let layers = PyList::empty(py);
    for layer in Layer::ALL {
        let r = report.layer(layer);
        layers.append((
            layer.as_str(),
            r.status.as_str(),
            r.not_run_reason.as_ref().map(|x| x.to_string()),
        ))?;
    }
    out.set_item("layers", layers)?;
    let diagnostics = PyList::empty(py);
    for d in &report.diagnostics {
        let item = PyDict::new(py);
        item.set_item("severity", d.severity.as_str())?;
        item.set_item("code", d.code)?;
        item.set_item("rule", d.rule)?;
        item.set_item("layer", d.layer.as_str())?;
        item.set_item("message", &d.message)?;
        item.set_item("header_line", d.location.header_line)?;
        item.set_item("byte_offset", d.location.byte_offset)?;
        item.set_item("byte_len", d.location.byte_len)?;
        item.set_item("json_pointer", d.location.json_pointer.as_deref())?;
        diagnostics.append(item)?;
    }
    out.set_item("diagnostics", diagnostics)?;
    match &report.selection {
        Some(s) => {
            let item = PyDict::new(py);
            item.set_item("header_type", &s.header_type)?;
            item.set_item("release", &s.release)?;
            item.set_item("schema_file", &s.schema_file)?;
            item.set_item("schema_sha256", &s.schema_sha256)?;
            item.set_item("rule", s.rule)?;
            item.set_item("draft", s.draft)?;
            out.set_item("selection", item)?;
        }
        None => out.set_item("selection", py.None())?,
    }
    match &report.checksum {
        Some(c) => {
            let item = PyDict::new(py);
            item.set_item("stated", c.stated.as_deref())?;
            item.set_item("computed", c.computed.as_deref())?;
            item.set_item("matches", c.matches)?;
            item.set_item("covered_bytes", c.covered_bytes)?;
            out.set_item("checksum", item)?;
        }
        None => out.set_item("checksum", py.None())?,
    }
    match &report.metadata {
        Some(m) => out.set_item("metadata", value_to_py(py, m, exact_decimals)?)?,
        None => out.set_item("metadata", py.None())?,
    }
    out.set_item("provenance", provenance_to_py(py, &report.provenance)?)?;
    Ok(out)
}

fn provenance_to_py<'py>(
    py: Python<'py>,
    p: &fair_bioheaders_tools::Provenance,
) -> PyResult<Bound<'py, PyDict>> {
    let item = PyDict::new(py);
    item.set_item("engine_version", &p.engine_version)?;
    item.set_item("abi_version", &p.abi_version)?;
    item.set_item("bundle_id", &p.bundle_id)?;
    item.set_item("bundle_manifest_sha256", &p.bundle_manifest_sha256)?;
    item.set_item("spec_commit", &p.spec_commit)?;
    item.set_item("profile_id", &p.profile_id)?;
    item.set_item("profile_sha256", &p.profile_sha256)?;
    let limits = PyDict::new(py);
    for (kind, value, raised) in &p.limits_applied {
        limits.set_item(kind, (value, raised))?;
    }
    item.set_item("limits_applied", limits)?;
    Ok(item)
}

/// An immutable engine; safe to share between threads.
#[pyclass(
    frozen,
    module = "fair_bioheaders_tools._native",
    name = "NativeEngine"
)]
struct NativeEngine {
    engine: Engine,
    exact_decimals: bool,
}

#[pymethods]
impl NativeEngine {
    #[new]
    #[pyo3(signature = (profile = "python", limits = None, raise_limits = None, draft_lanes = Vec::new(), exact_decimals = false))]
    fn new(
        py: Python<'_>,
        profile: &str,
        limits: Option<Vec<(String, u64)>>,
        raise_limits: Option<Vec<(String, u64)>>,
        draft_lanes: Vec<String>,
        exact_decimals: bool,
    ) -> PyResult<Self> {
        let mut builder = EngineBuilder::new().profile(profile);
        for (name, value) in limits.unwrap_or_default() {
            builder = builder.limit(limit_kind(&name)?, value);
        }
        for (name, value) in raise_limits.unwrap_or_default() {
            builder = builder.raise_limit(limit_kind(&name)?, value);
        }
        for lane in &draft_lanes {
            builder = builder.draft_lane(lane);
        }
        let engine = py.detach(|| builder.build()).map_err(to_py_err)?;
        Ok(NativeEngine {
            engine,
            exact_decimals,
        })
    }

    /// Read an in-memory input (bytes are not copied for `bytes` objects).
    fn verify_bytes<'py>(
        &self,
        py: Python<'py>,
        operation_name: &str,
        container_name: &str,
        data: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let op = operation(operation_name)?;
        let c = container(container_name)?;
        let report = if let Ok(bytes) = data.cast::<PyBytes>() {
            let slice: &[u8] = bytes.as_bytes();
            py.detach(|| self.engine.verify_bytes(op, c, slice))
        } else {
            let owned: Vec<u8> = data.extract()?;
            py.detach(|| self.engine.verify_bytes(op, c, &owned))
        }
        .map_err(to_py_err)?;
        report_to_py(py, &report, self.exact_decimals)
    }

    /// Read a file by path.
    fn verify_path<'py>(
        &self,
        py: Python<'py>,
        operation_name: &str,
        container_name: &str,
        path: std::path::PathBuf,
    ) -> PyResult<Bound<'py, PyDict>> {
        let op = operation(operation_name)?;
        let c = container(container_name)?;
        let report = py
            .detach(|| self.engine.verify_path(op, c, &path))
            .map_err(to_py_err)?;
        report_to_py(py, &report, self.exact_decimals)
    }

    /// A push stream.
    fn stream(&self, operation_name: &str, container_name: &str) -> PyResult<NativeStream> {
        let verifier = self
            .engine
            .stream(operation(operation_name)?, container(container_name)?);
        let cancel = verifier.cancel_handle();
        Ok(NativeStream {
            verifier: Mutex::new(Some(verifier)),
            cancel,
            exact_decimals: self.exact_decimals,
        })
    }

    /// Engine identity and configuration.
    #[getter]
    fn provenance<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        provenance_to_py(py, self.engine.provenance())
    }

    /// Test-only panic inside the engine (fault-injection builds only).
    #[cfg(feature = "fault-injection")]
    fn _test_panic(&self, py: Python<'_>) -> PyResult<()> {
        py.detach(|| self.engine.test_panic()).map_err(to_py_err)
    }
}

/// A push stream; feed from one thread at a time, cancel from any thread.
#[pyclass(
    frozen,
    module = "fair_bioheaders_tools._native",
    name = "NativeStream"
)]
struct NativeStream {
    verifier: Mutex<Option<Verifier>>,
    cancel: fair_bioheaders_tools::CancelHandle,
    exact_decimals: bool,
}

#[pymethods]
impl NativeStream {
    /// Feed bytes; returns True once a validate-only read may stop.
    fn feed(&self, py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<bool> {
        let owned: Vec<u8> = if let Ok(bytes) = data.cast::<PyBytes>() {
            bytes.as_bytes().to_vec()
        } else {
            data.extract()?
        };
        py.detach(|| {
            let mut guard = self.verifier.try_lock().map_err(|_| EngineError::State {
                message: "the stream is in use by another thread".into(),
            })?;
            let verifier = guard.as_mut().ok_or_else(|| EngineError::State {
                message: "the stream is finished".into(),
            })?;
            verifier.feed(&owned)
        })
        .map(|p| p == fair_bioheaders_tools::Progress::Complete)
        .map_err(to_py_err)
    }

    /// Finish and return the report.
    fn finish<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let verifier = self
            .verifier
            .try_lock()
            .map_err(|_| StateError::new_err("the stream is in use by another thread"))?
            .take()
            .ok_or_else(|| StateError::new_err("the stream is finished"))?;
        let report = py.detach(|| verifier.finish()).map_err(to_py_err)?;
        report_to_py(py, &report, self.exact_decimals)
    }

    /// Cancel (thread-safe).
    fn cancel(&self) {
        self.cancel.cancel();
    }

    /// Release the stream's engine state now (idempotent).
    fn close(&self) {
        if let Ok(mut guard) = self.verifier.try_lock() {
            guard.take();
        }
    }
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("ENGINE_VERSION", Engine::version())?;
    let (major, minor) = fair_bioheaders_tools::ABI_VERSION;
    m.add("ABI_VERSION", format!("{major}.{minor}"))?;
    m.add("FAULT_INJECTION", cfg!(feature = "fault-injection"))?;
    m.add_class::<NativeEngine>()?;
    m.add_class::<NativeStream>()?;
    let py = m.py();
    m.add("EngineError", py.get_type::<EngineErrorBase>())?;
    m.add("InternalError", py.get_type::<InternalError>())?;
    m.add("CancelledError", py.get_type::<CancelledError>())?;
    m.add("StateError", py.get_type::<StateError>())?;
    m.add("ProfileError", py.get_type::<ProfileError>())?;
    Ok(())
}
