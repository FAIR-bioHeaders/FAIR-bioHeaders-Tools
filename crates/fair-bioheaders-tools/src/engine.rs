// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The engine: builder, one-shot reads and the push stream (Tools#207 §2).

use crate::checksum::{self, Scan};
use crate::diagnostics::Code;
use crate::family;
use crate::framing::{Framer, FramingError, Kind, Part};
use crate::gzip::{self, PushError};
use crate::report::{
    ChecksumResult, Diagnostic, Layer, LayerResult, LayerStatus, NotRunReason, Outcome, Provenance,
    Report, Selection, Severity,
};
use crate::schema::{self, Schemas};
use crate::selection::{Bundle, Choice, Profile, Selector};
use crate::value::Value;
use crate::yaml::{self, YamlLimits};
use std::io::Read;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

/// The C ABI version this engine implements.
pub const ABI_VERSION: (u32, u32) = (0, 1);

/// Which checks to run.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Operation {
    /// Everything except the checksum layer (the Python `validate` command).
    Validate,
    /// Every layer including the covered-bytes checksum.
    Verify,
}

/// The input container.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Container {
    /// Sniff from content (never from a file name).
    Auto,
    /// FASTA (FHR, FHP and, where available, FHT headers).
    Fasta,
    /// FASTA expected to carry an FHP header (R17 still decides).
    FhpFasta,
    /// GFA.
    Gfa,
    /// GFF3 with an FHGFF3 header.
    Gff3,
    /// A YAML metadata file.
    MetadataYaml,
    /// A JSON metadata file.
    MetadataJson,
}

impl Container {
    fn kind(self) -> Option<Kind> {
        match self {
            Container::Fasta | Container::FhpFasta => Some(Kind::Fasta),
            Container::Gfa => Some(Kind::Gfa),
            Container::Gff3 => Some(Kind::Gff3),
            _ => None,
        }
    }

    /// The lower-case name.
    pub fn as_str(self) -> &'static str {
        match self {
            Container::Auto => "auto",
            Container::Fasta => "fasta",
            Container::FhpFasta => "fhp-fasta",
            Container::Gfa => "gfa",
            Container::Gff3 => "gff3",
            Container::MetadataYaml => "metadata-yaml",
            Container::MetadataJson => "metadata-json",
        }
    }
}

/// A resource bound.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LimitKind {
    /// Bytes of header lines.
    HeaderBytes,
    /// Number of header lines.
    HeaderLines,
    /// YAML/JSON nodes.
    YamlNodes,
    /// YAML/JSON nesting depth.
    YamlDepth,
    /// Metadata file bytes after decompression.
    MetadataBytes,
    /// Decompressed bytes an operation may buffer.
    InMemoryDecompressedBytes,
    /// Bytes of one scalar.
    ScalarBytes,
    /// Consumer exact-integer bits (unset = exact).
    ConsumerExactIntegerBits,
}

impl LimitKind {
    /// All kinds.
    pub const ALL: [LimitKind; 8] = [
        LimitKind::HeaderBytes,
        LimitKind::HeaderLines,
        LimitKind::YamlNodes,
        LimitKind::YamlDepth,
        LimitKind::MetadataBytes,
        LimitKind::InMemoryDecompressedBytes,
        LimitKind::ScalarBytes,
        LimitKind::ConsumerExactIntegerBits,
    ];

    /// The snake-case name.
    pub fn as_str(self) -> &'static str {
        match self {
            LimitKind::HeaderBytes => "header_bytes",
            LimitKind::HeaderLines => "header_lines",
            LimitKind::YamlNodes => "yaml_nodes",
            LimitKind::YamlDepth => "yaml_depth",
            LimitKind::MetadataBytes => "metadata_bytes",
            LimitKind::InMemoryDecompressedBytes => "in_memory_decompressed_bytes",
            LimitKind::ScalarBytes => "scalar_bytes",
            LimitKind::ConsumerExactIntegerBits => "consumer_exact_integer_bits",
        }
    }

    fn default_value(self) -> Option<u64> {
        Some(match self {
            LimitKind::HeaderBytes => 1 << 20,
            LimitKind::HeaderLines => 10_000,
            LimitKind::YamlNodes => 20_000,
            LimitKind::YamlDepth => 64,
            LimitKind::MetadataBytes => 64 << 20,
            LimitKind::InMemoryDecompressedBytes => 1 << 30,
            LimitKind::ScalarBytes => 1 << 20,
            LimitKind::ConsumerExactIntegerBits => return None,
        })
    }
}

/// A call failure (never a verdict).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EngineError {
    /// Reading the input failed.
    Io {
        /// Description.
        message: String,
    },
    /// The stream was cancelled.
    Cancelled,
    /// An argument was invalid.
    InvalidArgument {
        /// Description.
        message: String,
    },
    /// The requested profile or lane is not available.
    IncompatibleProfile {
        /// Description.
        message: String,
    },
    /// The stream is finished, cancelled or poisoned.
    State {
        /// Description.
        message: String,
    },
    /// A contained internal failure (panic).
    Internal {
        /// Description.
        message: String,
    },
}

impl std::fmt::Display for EngineError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EngineError::Io { message } => write!(f, "I/O error: {message}"),
            EngineError::Cancelled => f.write_str("cancelled"),
            EngineError::InvalidArgument { message } => write!(f, "invalid argument: {message}"),
            EngineError::IncompatibleProfile { message } => {
                write!(f, "incompatible profile: {message}")
            }
            EngineError::State { message } => write!(f, "invalid state: {message}"),
            EngineError::Internal { message } => write!(f, "internal error: {message}"),
        }
    }
}

impl std::error::Error for EngineError {}

/// Builds an [`Engine`].
#[derive(Clone, Debug)]
pub struct EngineBuilder {
    profile: String,
    limits: Vec<(LimitKind, u64, bool)>,
    lanes: Vec<String>,
}

impl Default for EngineBuilder {
    fn default() -> Self {
        Self::new()
    }
}

impl EngineBuilder {
    /// The `python` profile with specification limits.
    pub fn new() -> EngineBuilder {
        EngineBuilder {
            profile: "python".into(),
            limits: Vec::new(),
            lanes: Vec::new(),
        }
    }

    /// Select a consumer support profile.
    pub fn profile(mut self, id: &str) -> Self {
        self.profile = id.to_owned();
        self
    }

    /// Lower (or keep) a limit.
    pub fn limit(mut self, kind: LimitKind, value: u64) -> Self {
        self.limits.push((kind, value, false));
        self
    }

    /// Raise a limit above the specification value (recorded in provenance).
    pub fn raise_limit(mut self, kind: LimitKind, value: u64) -> Self {
        self.limits.push((kind, value, true));
        self
    }

    /// Open an opt-in draft lane (`fht`).
    pub fn draft_lane(mut self, lane: &str) -> Self {
        self.lanes.push(lane.to_owned());
        self
    }

    /// Build the engine.
    pub fn build(self) -> Result<Engine, EngineError> {
        guard(|| self.build_inner())
    }

    fn build_inner(self) -> Result<Engine, EngineError> {
        let profile =
            Profile::load(&self.profile).ok_or_else(|| EngineError::IncompatibleProfile {
                message: format!("unknown profile {:?}", self.profile),
            })?;
        for lane in &self.lanes {
            if !profile.draft_lanes.contains(lane) {
                return Err(EngineError::IncompatibleProfile {
                    message: format!(
                        "draft lane {lane:?} is not available in profile {:?}",
                        profile.id
                    ),
                });
            }
        }
        let mut limits = Limits::defaults(profile.consumer_exact_integer_bits.map(u64::from));
        for (kind, value, raise) in self.limits {
            if value == 0 {
                return Err(EngineError::InvalidArgument {
                    message: format!("limit {} must be positive", kind.as_str()),
                });
            }
            let current = limits.get(kind);
            let spec = kind.default_value().or(current);
            match spec {
                Some(spec) if value > spec && !raise => {
                    return Err(EngineError::InvalidArgument {
                        message: format!(
                            "limit {} = {value} is above the specification value {spec}; use raise_limit",
                            kind.as_str()
                        ),
                    });
                }
                _ => {}
            }
            limits.set(kind, value, raise && spec.is_some_and(|s| value > s));
        }
        let fht_lane = self.lanes.iter().any(|l| l == "fht");
        let bundle = Bundle::load();
        let schemas = Schemas::compile().map_err(|message| EngineError::Internal { message })?;
        let provenance = Provenance {
            engine_version: env!("CARGO_PKG_VERSION").to_owned(),
            abi_version: format!("{}.{}", ABI_VERSION.0, ABI_VERSION.1),
            bundle_id: bundle.bundle_id.clone(),
            bundle_manifest_sha256: bundle.manifest_sha256.clone(),
            spec_commit: bundle.spec_commit.clone(),
            profile_id: profile.id.clone(),
            profile_sha256: profile.sha256.clone(),
            limits_applied: limits.applied(),
        };
        let selector = Selector::new(bundle, profile, fht_lane);
        Ok(Engine {
            inner: Arc::new(Inner {
                selector,
                schemas,
                limits,
                provenance,
            }),
        })
    }
}

#[derive(Clone, Debug)]
struct Limits {
    values: Vec<(LimitKind, Option<u64>, bool)>,
}

impl Limits {
    fn defaults(consumer_bits: Option<u64>) -> Limits {
        Limits {
            values: LimitKind::ALL
                .iter()
                .map(|k| {
                    let value = if *k == LimitKind::ConsumerExactIntegerBits {
                        consumer_bits
                    } else {
                        k.default_value()
                    };
                    (*k, value, false)
                })
                .collect(),
        }
    }

    fn get(&self, kind: LimitKind) -> Option<u64> {
        self.values
            .iter()
            .find(|(k, _, _)| *k == kind)
            .and_then(|(_, v, _)| *v)
    }

    fn set(&mut self, kind: LimitKind, value: u64, raised: bool) {
        for entry in &mut self.values {
            if entry.0 == kind {
                entry.1 = Some(value);
                entry.2 = raised;
            }
        }
    }

    fn applied(&self) -> Vec<(String, u64, bool)> {
        self.values
            .iter()
            .filter_map(|(k, v, r)| v.map(|v| (k.as_str().to_owned(), v, *r)))
            .collect()
    }

    fn yaml(&self) -> YamlLimits {
        let header = self.get(LimitKind::HeaderBytes).unwrap_or(u64::MAX);
        YamlLimits {
            nodes: self.get(LimitKind::YamlNodes).unwrap_or(u64::MAX),
            depth: self.get(LimitKind::YamlDepth).unwrap_or(u64::MAX),
            scalar_bytes: self.get(LimitKind::ScalarBytes).unwrap_or(header),
        }
    }
}

#[derive(Debug)]
struct Inner {
    selector: Selector,
    schemas: Schemas,
    limits: Limits,
    provenance: Provenance,
}

/// What the engine can do.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Capabilities {
    /// Profiles compiled in.
    pub profiles: Vec<String>,
    /// Containers.
    pub containers: Vec<String>,
    /// Draft lanes of this engine's profile.
    pub draft_lanes: Vec<String>,
    /// Rule ids the diagnostics registry maps to.
    pub rules: Vec<String>,
}

/// An immutable, thread-shareable engine.
#[derive(Clone, Debug)]
pub struct Engine {
    inner: Arc<Inner>,
}

fn guard<T>(f: impl FnOnce() -> Result<T, EngineError>) -> Result<T, EngineError> {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(result) => result,
        Err(payload) => Err(EngineError::Internal {
            message: panic_message(&payload),
        }),
    }
}

fn panic_message(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        (*s).to_owned()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "panic".to_owned()
    }
}

impl Engine {
    /// A default engine (`python` profile).
    pub fn new() -> Result<Engine, EngineError> {
        EngineBuilder::new().build()
    }

    /// The engine (crate) version.
    pub fn version() -> &'static str {
        env!("CARGO_PKG_VERSION")
    }

    /// Engine identity and configuration.
    pub fn provenance(&self) -> &Provenance {
        &self.inner.provenance
    }

    /// Capabilities.
    pub fn capabilities(&self) -> Capabilities {
        let mut rules: Vec<String> = crate::diagnostics::REGISTRY
            .iter()
            .filter_map(|e| e.rule.map(str::to_owned))
            .collect();
        rules.sort();
        rules.dedup();
        Capabilities {
            profiles: fair_bioheaders_tools_bundles::PROFILES
                .iter()
                .map(|(id, _)| (*id).to_owned())
                .collect(),
            containers: [
                "fasta",
                "fhp-fasta",
                "gfa",
                "gff3",
                "metadata-yaml",
                "metadata-json",
            ]
            .map(str::to_owned)
            .to_vec(),
            draft_lanes: self.inner.selector.profile().draft_lanes.clone(),
            rules,
        }
    }

    /// Read an in-memory input.
    pub fn verify_bytes(
        &self,
        op: Operation,
        container: Container,
        input: &[u8],
    ) -> Result<Report, EngineError> {
        let mut stream = self.stream(op, container);
        stream.feed_all(input)?;
        stream.finish()
    }

    /// Read from a reader to its end.
    pub fn verify_reader<R: Read>(
        &self,
        op: Operation,
        container: Container,
        mut reader: R,
    ) -> Result<Report, EngineError> {
        let mut stream = self.stream(op, container);
        let mut buffer = vec![0u8; 1 << 20];
        loop {
            let n = match reader.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => n,
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(e) => {
                    return Err(EngineError::Io {
                        message: e.to_string(),
                    });
                }
            };
            stream.feed_all(&buffer[..n])?;
        }
        stream.finish()
    }

    /// Read a file.
    pub fn verify_path(
        &self,
        op: Operation,
        container: Container,
        path: &Path,
    ) -> Result<Report, EngineError> {
        let file = std::fs::File::open(path).map_err(|e| EngineError::Io {
            message: format!("{}: {e}", path.display()),
        })?;
        self.verify_reader(op, container, file)
    }

    /// A push stream.
    pub fn stream(&self, op: Operation, container: Container) -> Verifier {
        Verifier::new(self.clone(), op, container)
    }

    #[cfg(feature = "fault-injection")]
    /// Test-only: panic inside a guarded engine call.
    pub fn test_panic(&self) -> Result<(), EngineError> {
        guard(|| panic!("fault-injection: deliberate engine panic"))
    }
}

/// Whether a stream needs more input.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Progress {
    /// Feed more.
    NeedMore,
    /// For Validate: the header block has ended; the host may stop reading
    /// (later bytes are then not checked for late header lines).
    Complete,
}

/// A cancellation handle usable from any thread.
#[derive(Clone, Debug)]
pub struct CancelHandle(Arc<AtomicBool>);

impl CancelHandle {
    /// Request cancellation.
    pub fn cancel(&self) {
        self.0.store(true, Ordering::SeqCst);
    }
}

enum Transport {
    Sniff(Vec<u8>),
    Plain,
    Gzip(Box<gzip::Decoder>),
}

enum Body {
    Undecided(Vec<u8>),
    Sequence {
        kind: Kind,
        framer: Box<Framer>,
        scan: Box<Scan>,
    },
    Metadata {
        json: bool,
        buffer: Vec<u8>,
    },
}

enum StreamState {
    Open,
    Poisoned,
}

/// A push-mode reader.
pub struct Verifier {
    engine: Engine,
    op: Operation,
    container: Container,
    transport: Transport,
    body: Body,
    failure: Option<Diagnostic>,
    cancelled: Arc<AtomicBool>,
    state: StreamState,
    since_check: u64,
}

impl Verifier {
    fn new(engine: Engine, op: Operation, container: Container) -> Verifier {
        Verifier {
            engine,
            op,
            container,
            transport: Transport::Sniff(Vec::new()),
            body: Body::Undecided(Vec::new()),
            failure: None,
            cancelled: Arc::new(AtomicBool::new(false)),
            state: StreamState::Open,
            since_check: 0,
        }
    }

    /// A handle that cancels this stream.
    pub fn cancel_handle(&self) -> CancelHandle {
        CancelHandle(self.cancelled.clone())
    }

    /// Feed one chunk.
    pub fn feed(&mut self, chunk: &[u8]) -> Result<Progress, EngineError> {
        if matches!(self.state, StreamState::Poisoned) {
            return Err(EngineError::State {
                message: "the stream failed internally and cannot be used".into(),
            });
        }
        let result = catch_unwind(AssertUnwindSafe(|| self.feed_inner(chunk)));
        match result {
            Ok(r) => r,
            Err(payload) => {
                self.state = StreamState::Poisoned;
                Err(EngineError::Internal {
                    message: panic_message(&payload),
                })
            }
        }
    }

    fn feed_all(&mut self, chunk: &[u8]) -> Result<(), EngineError> {
        self.feed(chunk).map(|_| ())
    }

    fn check_cancel(&self) -> Result<(), EngineError> {
        if self.cancelled.load(Ordering::SeqCst) {
            Err(EngineError::Cancelled)
        } else {
            Ok(())
        }
    }

    fn feed_inner(&mut self, chunk: &[u8]) -> Result<Progress, EngineError> {
        self.check_cancel()?;
        if self.failure.is_none() && !chunk.is_empty() {
            self.transport_push(Some(chunk))?;
        }
        Ok(self.progress())
    }

    fn progress(&self) -> Progress {
        match &self.body {
            Body::Sequence { framer, .. }
                if self.op == Operation::Validate && framer.header_done() =>
            {
                Progress::Complete
            }
            _ if self.failure.is_some() => Progress::Complete,
            _ => Progress::NeedMore,
        }
    }

    /// Route bytes through the transport (`None` = end of input).
    fn transport_push(&mut self, chunk: Option<&[u8]>) -> Result<(), EngineError> {
        if let Transport::Sniff(buffer) = &mut self.transport {
            if let Some(c) = chunk {
                buffer.extend_from_slice(c);
                if buffer.len() < 2 {
                    return Ok(());
                }
            }
            let buffer = std::mem::take(buffer);
            self.transport = if buffer.starts_with(&gzip::MAGIC) {
                Transport::Gzip(Box::default())
            } else {
                Transport::Plain
            };
            if !buffer.is_empty() {
                self.transport_push(Some(&buffer))?;
            }
            if chunk.is_none() {
                return self.transport_push(None);
            }
            return Ok(());
        }
        let mut transport = std::mem::replace(&mut self.transport, Transport::Plain);
        let result = match &mut transport {
            Transport::Plain => match chunk {
                Some(c) => self.body_push(Some(c)),
                None => self.body_push(None),
            },
            Transport::Gzip(decoder) => match chunk {
                Some(c) => {
                    let mut sink =
                        |piece: &[u8]| -> Result<(), EngineError> { self.body_push(Some(piece)) };
                    match decoder.push(c, &mut sink) {
                        Ok(()) => Ok(()),
                        Err(PushError::Sink(e)) => Err(e),
                        Err(PushError::Gzip(g)) => {
                            self.fail(Diagnostic::new(g.code, g.message));
                            Ok(())
                        }
                    }
                }
                None => match decoder.finish() {
                    Ok(()) => self.body_push(None),
                    Err(g) => {
                        self.fail(Diagnostic::new(g.code, g.message));
                        Ok(())
                    }
                },
            },
            Transport::Sniff(_) => unreachable!(),
        };
        self.transport = transport;
        result
    }

    fn fail(&mut self, diagnostic: Diagnostic) {
        if self.failure.is_none() {
            self.failure = Some(diagnostic);
        }
    }

    fn body_push(&mut self, chunk: Option<&[u8]>) -> Result<(), EngineError> {
        if self.failure.is_some() {
            return Ok(());
        }
        if let Some(c) = chunk {
            self.since_check += c.len() as u64;
            if self.since_check >= 1 << 20 {
                self.since_check = 0;
                self.check_cancel()?;
            }
        }
        if let Body::Undecided(buffer) = &mut self.body {
            if let Some(c) = chunk {
                buffer.extend_from_slice(c);
                if buffer.len() < 16 {
                    return Ok(());
                }
            }
            let buffer = std::mem::take(buffer);
            let container = match self.container {
                Container::Auto => sniff(&buffer),
                other => other,
            };
            self.container = container;
            let limits = &self.engine.inner.limits;
            self.body = match container.kind() {
                Some(kind) => Body::Sequence {
                    kind,
                    framer: Box::new(Framer::new(
                        kind,
                        limits.get(LimitKind::HeaderBytes).unwrap_or(u64::MAX),
                        limits.get(LimitKind::HeaderLines).unwrap_or(u64::MAX),
                    )),
                    scan: Box::new(Scan::new(kind)),
                },
                None => Body::Metadata {
                    json: container == Container::MetadataJson,
                    buffer: Vec::new(),
                },
            };
            if !buffer.is_empty() {
                self.body_push(Some(&buffer))?;
            }
            if chunk.is_none() {
                return self.body_push(None);
            }
            return Ok(());
        }
        let metadata_limit = self
            .engine
            .inner
            .limits
            .get(LimitKind::MetadataBytes)
            .unwrap_or(u64::MAX);
        let memory_limit = self
            .engine
            .inner
            .limits
            .get(LimitKind::InMemoryDecompressedBytes)
            .unwrap_or(u64::MAX);
        let mut failure = None;
        match &mut self.body {
            Body::Sequence { framer, scan, .. } => {
                let mut sink = |part: Part<'_>| scan.part(&part);
                if let Err(FramingError {
                    code,
                    message,
                    line,
                }) = framer.push(chunk, &mut sink)
                {
                    let mut d = Diagnostic::new(code, message);
                    if let Some(line) = line {
                        d = d.at_line(line);
                    }
                    failure = Some(d);
                }
            }
            Body::Metadata { buffer, .. } => {
                if let Some(c) = chunk {
                    buffer.extend_from_slice(c);
                    if buffer.len() as u64 > metadata_limit {
                        failure = Some(Diagnostic::new(
                            Code::LimitMetadataBytes,
                            format!(
                                "Metadata input exceeds the {} MiB size limit",
                                metadata_limit >> 20
                            ),
                        ));
                    } else if buffer.len() as u64 > memory_limit {
                        failure = Some(Diagnostic::new(
                            Code::LimitDecompressed,
                            format!(
                                "Buffered input exceeds the in-memory limit of {memory_limit} bytes"
                            ),
                        ));
                    }
                }
            }
            Body::Undecided(_) => unreachable!(),
        }
        if let Some(d) = failure {
            self.fail(d);
        }
        Ok(())
    }

    /// End of input: evaluate and return the report.
    pub fn finish(mut self) -> Result<Report, EngineError> {
        if matches!(self.state, StreamState::Poisoned) {
            return Err(EngineError::State {
                message: "the stream failed internally and cannot be used".into(),
            });
        }
        let result = catch_unwind(AssertUnwindSafe(|| {
            self.check_cancel()?;
            if self.failure.is_none() {
                self.transport_push(None)?;
            }
            Ok(self.evaluate())
        }));
        match result {
            Ok(r) => r,
            Err(payload) => Err(EngineError::Internal {
                message: panic_message(&payload),
            }),
        }
    }

    fn evaluate(&mut self) -> Report {
        let inner = self.engine.inner.clone();
        let mut ev = Evaluation::new(self.op, inner.provenance.clone());
        let container = if self.container == Container::Auto {
            Container::MetadataYaml
        } else {
            self.container
        };
        ev.container = container;
        if let Some(failure) = self.failure.take() {
            ev.add(failure);
            ev.block_after(Layer::Framing);
            return ev.finish();
        }
        match std::mem::replace(&mut self.body, Body::Undecided(Vec::new())) {
            Body::Sequence { kind, mut scan, .. } => {
                scan.finish();
                evaluate_sequence(&inner, &mut ev, kind, &scan);
            }
            Body::Metadata { json, buffer } => evaluate_metadata(&inner, &mut ev, json, &buffer),
            Body::Undecided(buffer) => {
                // Fewer than 16 bytes in total: decide now.
                let container = if self.container == Container::Auto {
                    sniff(&buffer)
                } else {
                    self.container
                };
                ev.container = container;
                match container.kind() {
                    Some(kind) => {
                        let limits = &inner.limits;
                        let mut framer = Framer::new(
                            kind,
                            limits.get(LimitKind::HeaderBytes).unwrap_or(u64::MAX),
                            limits.get(LimitKind::HeaderLines).unwrap_or(u64::MAX),
                        );
                        let mut scan = Scan::new(kind);
                        let mut sink = |part: Part<'_>| scan.part(&part);
                        let result = framer
                            .push(Some(&buffer), &mut sink)
                            .and_then(|()| framer.push(None, &mut sink));
                        if let Err(FramingError {
                            code,
                            message,
                            line,
                        }) = result
                        {
                            let mut d = Diagnostic::new(code, message);
                            if let Some(line) = line {
                                d = d.at_line(line);
                            }
                            ev.add(d);
                            ev.block_after(Layer::Framing);
                            return ev.finish();
                        }
                        scan.finish();
                        evaluate_sequence(&inner, &mut ev, kind, &scan);
                    }
                    None => evaluate_metadata(
                        &inner,
                        &mut ev,
                        container == Container::MetadataJson,
                        &buffer,
                    ),
                }
            }
        }
        ev.finish()
    }
}

/// Sniff a container from the first decompressed bytes (never the name).
fn sniff(start: &[u8]) -> Container {
    let body = start.strip_prefix(b"\xef\xbb\xbf").unwrap_or(start);
    if body.starts_with(b";~") || body.starts_with(b">") || body.starts_with(b";") {
        return Container::Fasta;
    }
    if body.starts_with(b"##gff-version") {
        return Container::Gff3;
    }
    if body.starts_with(b"#~") || body.starts_with(b"H\t") || body.starts_with(b"S\t") {
        return Container::Gfa;
    }
    let trimmed: &[u8] = {
        let skip = body
            .iter()
            .take_while(|b| matches!(b, b' ' | b'\t' | b'\r' | b'\n'))
            .count();
        &body[skip..]
    };
    if trimmed.starts_with(b"{") || trimmed.starts_with(b"[") {
        return Container::MetadataJson;
    }
    Container::MetadataYaml
}

struct Evaluation {
    op: Operation,
    layers: Vec<LayerResult>,
    diagnostics: Vec<Diagnostic>,
    selection: Option<Selection>,
    checksum: Option<ChecksumResult>,
    metadata: Option<Value>,
    provenance: Provenance,
    container: Container,
    run: [bool; 7],
}

impl Evaluation {
    fn new(op: Operation, provenance: Provenance) -> Evaluation {
        let layers = Layer::ALL
            .iter()
            .map(|l| LayerResult {
                layer: *l,
                status: LayerStatus::Pass,
                not_run_reason: None,
            })
            .collect();
        let mut ev = Evaluation {
            op,
            layers,
            diagnostics: Vec::new(),
            selection: None,
            checksum: None,
            metadata: None,
            provenance,
            container: Container::Auto,
            run: [false; 7],
        };
        ev.not_run(
            Layer::Model,
            NotRunReason::OutsideEngineScope("model".into()),
        );
        if op == Operation::Validate {
            ev.not_run(Layer::Checksum, NotRunReason::NotRequested);
        }
        ev
    }

    fn ran(&mut self, layer: Layer) {
        self.run[layer.index()] = true;
    }

    fn not_run(&mut self, layer: Layer, reason: NotRunReason) {
        let entry = &mut self.layers[layer.index()];
        if entry.status == LayerStatus::Pass && !self.run[layer.index()] {
            entry.status = LayerStatus::NotRun;
            entry.not_run_reason = Some(reason);
        }
    }

    fn block_after(&mut self, layer: Layer) {
        for later in Layer::ALL
            .iter()
            .filter(|l| **l > layer && **l != Layer::Model)
        {
            self.not_run(*later, NotRunReason::BlockedBy(layer));
        }
    }

    fn add(&mut self, d: Diagnostic) {
        let index = d.layer.index();
        self.run[index] = true;
        if d.severity == Severity::Error {
            let status = if d.code.starts_with("LIMIT.") {
                LayerStatus::Limit
            } else if d.code == "V4.unsupported-version" || d.code == "NOTRUN.outside-profile" {
                LayerStatus::Unsupported
            } else {
                LayerStatus::Fail
            };
            let entry = &mut self.layers[index];
            let rank = |s: LayerStatus| match s {
                LayerStatus::Limit => 4,
                LayerStatus::Unsupported => 3,
                LayerStatus::Fail => 2,
                LayerStatus::NotRun => 1,
                LayerStatus::Pass => 0,
            };
            if rank(status) > rank(entry.status) || entry.status == LayerStatus::NotRun {
                entry.status = status;
                entry.not_run_reason = None;
            }
        }
        self.diagnostics.push(d);
    }

    fn has_error(&self, layer: Layer) -> bool {
        matches!(
            self.layers[layer.index()].status,
            LayerStatus::Fail | LayerStatus::Limit | LayerStatus::Unsupported
        )
    }

    fn finish(mut self) -> Report {
        // Layers that never ran and were not given a reason.
        for layer in Layer::ALL {
            let i = layer.index();
            if !self.run[i] && self.layers[i].status == LayerStatus::Pass {
                // A layer with nothing to check for this container passes only
                // if it is not required; mark it not-run with a scope reason.
                if matches!(
                    self.container,
                    Container::MetadataYaml | Container::MetadataJson
                ) && matches!(layer, Layer::Framing | Layer::Checksum)
                {
                    self.layers[i].status = LayerStatus::NotRun;
                    self.layers[i].not_run_reason =
                        Some(NotRunReason::OutsideEngineScope("metadata-file".into()));
                }
            }
        }
        // Diagnostics are reported in pipeline order (stable within a layer).
        self.diagnostics.sort_by_key(|d| d.layer);
        let required: Vec<Layer> = match (self.op, self.container) {
            (_, Container::MetadataYaml | Container::MetadataJson) => {
                vec![Layer::Yaml, Layer::Selection, Layer::Schema]
            }
            (Operation::Validate, _) => vec![
                Layer::Framing,
                Layer::Yaml,
                Layer::Selection,
                Layer::Schema,
                Layer::Family,
            ],
            (Operation::Verify, _) => {
                vec![
                    Layer::Framing,
                    Layer::Yaml,
                    Layer::Selection,
                    Layer::Schema,
                    Layer::Family,
                    Layer::Checksum,
                ]
            }
        };
        let status = |l: Layer| self.layers[l.index()].status;
        let outcome = if self.layers.iter().any(|l| l.status == LayerStatus::Limit) {
            Outcome::Limit
        } else if status(Layer::Selection) == LayerStatus::Unsupported {
            Outcome::Unsupported
        } else if self.layers.iter().any(|l| l.status == LayerStatus::Fail) {
            Outcome::Invalid
        } else if required.iter().any(|l| status(*l) == LayerStatus::NotRun) {
            let missing: Vec<&str> = required
                .iter()
                .filter(|l| status(**l) == LayerStatus::NotRun)
                .map(|l| l.as_str())
                .collect();
            self.diagnostics.push(Diagnostic::new(
                Code::NotRunRequiredLayer,
                format!("required layer(s) did not run: {}", missing.join(", ")),
            ));
            Outcome::Invalid
        } else {
            Outcome::Valid
        };
        Report {
            outcome,
            layers: self.layers,
            diagnostics: self.diagnostics,
            selection: self.selection,
            checksum: self.checksum,
            metadata: self.metadata,
            provenance: self.provenance,
            container: self.container,
        }
    }
}

/// `header_text`: the YAML text of one header line, or an R6 failure.
#[allow(clippy::result_large_err)]
fn header_text(line: &[u8], prefix: &[u8]) -> Result<String, Diagnostic> {
    let mut body = &line[prefix.len()..];
    while let Some((last, rest)) = body.split_last() {
        if *last == b'\n' || *last == b'\r' {
            body = rest;
        } else {
            break;
        }
    }
    let text = std::str::from_utf8(body).map_err(|e| {
        let position = e.valid_up_to();
        Diagnostic::new(
            Code::R6InvalidUtf8,
            format!(
                "'utf-8' codec can't decode byte 0x{:02x} in position {position}: invalid start byte",
                body.get(position).copied().unwrap_or(0)
            ),
        )
    })?;
    if text.contains(['\u{85}', '\u{2028}', '\u{2029}']) {
        return Err(Diagnostic::new(
            Code::R6YamlLineBreak,
            "FHR header lines must not contain U+0085, U+2028, or U+2029",
        ));
    }
    Ok(text.to_owned())
}

fn evaluate_sequence(inner: &Inner, ev: &mut Evaluation, kind: Kind, scan: &Scan) {
    ev.ran(Layer::Framing);
    let prefix = kind.prefix();
    if scan.header.is_empty() {
        ev.add(Diagnostic::new(
            Code::InputNoHeader,
            format!(
                "No {} FHR metadata header found",
                String::from_utf8_lossy(prefix)
            ),
        ));
        ev.block_after(Layer::Framing);
        return;
    }
    // Metadata from the same byte lines that are hashed.
    let mut texts = Vec::with_capacity(scan.header.len());
    let mut header_failure = None;
    for (line, number) in &scan.header {
        match header_text(line, prefix) {
            Ok(text) => texts.push(text),
            Err(d) => {
                header_failure = Some(d.at_line(*number));
                break;
            }
        }
    }
    let record = match header_failure {
        Some(d) => {
            ev.add(d);
            None
        }
        None => load_record(inner, ev, &texts.join("\n"), false, Some(&scan.header)),
    };
    match &record {
        Some(record) => evaluate_record(inner, ev, record, Some(kind)),
        None => {
            for layer in [Layer::Selection, Layer::Schema, Layer::Family] {
                ev.not_run(layer, NotRunReason::BlockedBy(Layer::Yaml));
            }
        }
    }
    if kind == Kind::Gff3 {
        if let Some(record) = &record {
            if inner.selector.record_header_type(record) == "FHGFF3" {
                for d in family::directive_warnings(record, &scan.directives) {
                    ev.add(d);
                }
            }
        }
    }
    if kind == Kind::Fasta {
        for d in family::record_marker_warnings(&scan.header, prefix) {
            ev.add(d);
        }
    }
    if ev.op == Operation::Verify {
        evaluate_checksum(inner, ev, scan, prefix, record.as_ref());
    }
}

fn load_record(
    inner: &Inner,
    ev: &mut Evaluation,
    text: &str,
    json: bool,
    header: Option<&Vec<(Vec<u8>, u64)>>,
) -> Option<Value> {
    ev.ran(Layer::Yaml);
    let limits = inner.limits.yaml();
    let loaded = if json {
        crate::json::load(text, limits)
    } else {
        yaml::load(text, limits)
    };
    let loaded = match loaded {
        Ok(loaded) => loaded,
        Err(e) => {
            let mut d = Diagnostic::new(e.code, e.message);
            if let Some(line) = e.line {
                // YAML line k is header line k of the block.
                let file_line = header
                    .and_then(|h| h.get(line.saturating_sub(1) as usize))
                    .map(|(_, n)| *n)
                    .unwrap_or(line);
                d = d.at_line(file_line);
            }
            ev.add(d);
            return None;
        }
    };
    let Some(record @ Value::Object(_)) = loaded.value else {
        ev.add(Diagnostic::new(
            Code::InputNotObject,
            "FHR metadata must be an object with string keys",
        ));
        return None;
    };
    if let Some((path, _)) = loaded.non_finite {
        let kind = inner.selector.record_header_type(&record);
        ev.add(
            Diagnostic::new(
                Code::R13NonFinite,
                format!("{kind}: {path} is not a finite number (FORMAT.md R13)"),
            )
            .at_pointer(dotted_to_pointer(&path)),
        );
        ev.metadata = Some(record);
        return None;
    }
    ev.metadata = Some(record.clone());
    Some(record)
}

fn dotted_to_pointer(path: &str) -> String {
    let mut out = String::new();
    let mut current = String::new();
    let mut chars = path.chars().peekable();
    let flush = |out: &mut String, current: &mut String| {
        if !current.is_empty() {
            out.push('/');
            out.push_str(&current.replace('~', "~0").replace('/', "~1"));
            current.clear();
        }
    };
    while let Some(c) = chars.next() {
        match c {
            '.' => flush(&mut out, &mut current),
            '[' => {
                flush(&mut out, &mut current);
                let index: String = chars.by_ref().take_while(|c| *c != ']').collect();
                out.push('/');
                out.push_str(&index);
            }
            c => current.push(c),
        }
    }
    flush(&mut out, &mut current);
    out
}

fn evaluate_record(inner: &Inner, ev: &mut Evaluation, record: &Value, kind: Option<Kind>) {
    let selector = &inner.selector;
    ev.ran(Layer::Selection);
    for (rule, message) in selector.warnings(record) {
        let code = match rule {
            "V6" => Code::V6Fhr1Citation,
            "V7" => Code::V7DraftContract,
            _ => Code::V5NearMiss,
        };
        ev.add(Diagnostic::new(code, message).at_pointer("/schema"));
    }
    let choice = selector.select_record(record);
    let (header_type, file) = match choice {
        Choice::Selected {
            header_type,
            release,
            file,
            rule,
            draft,
        } => {
            let digest = selector
                .bundle()
                .digests
                .get(&file)
                .cloned()
                .unwrap_or_default();
            ev.selection = Some(Selection {
                header_type: header_type.clone(),
                release,
                schema_file: file.clone(),
                schema_sha256: digest,
                rule,
                draft,
            });
            (header_type, file)
        }
        Choice::Unsupported { message, .. } => {
            ev.add(Diagnostic::new(Code::V4Unsupported, message).at_pointer("/schema"));
            ev.not_run(Layer::Schema, NotRunReason::BlockedBy(Layer::Selection));
            if let Some(kind) = kind {
                family_checks(inner, ev, record, kind, None);
            }
            return;
        }
        Choice::OutsideProfile {
            release, message, ..
        } => {
            ev.add(Diagnostic::new(Code::NotRunOutsideProfile, message).at_pointer("/schema"));
            ev.not_run(Layer::Schema, NotRunReason::OutsideProfile(release));
            return;
        }
    };
    ev.ran(Layer::Schema);
    for d in inner.schemas.validate(&file, &header_type, record) {
        ev.add(d);
    }
    let document = inner
        .schemas
        .document(&file)
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    if let Some(d) = schema::check_checksums(record, &document) {
        ev.add(d);
    }
    if header_type == "FHT" {
        match schema::check_fht_completeness(record, selector.profile().consumer_exact_integer_bits)
        {
            schema::C1::Ok => {}
            schema::C1::Fail(d) | schema::C1::Limit(d) => ev.add(d),
        }
    }
    if let Some(kind) = kind {
        family_checks(inner, ev, record, kind, Some(&document));
    } else {
        ev.ran(Layer::Family);
        for d in family::link_scheme_warnings(record, &document) {
            ev.add(d);
        }
    }
}

fn family_checks(
    inner: &Inner,
    ev: &mut Evaluation,
    record: &Value,
    kind: Kind,
    schema: Option<&serde_json::Value>,
) {
    ev.ran(Layer::Family);
    let header_type = inner.selector.record_header_type(record);
    let fht = inner.selector.shared_fht_available();
    if let Some(d) = family::check_container(kind, &header_type, fht) {
        ev.add(d);
    }
    if let Some(schema) = schema {
        for d in family::link_scheme_warnings(record, schema) {
            ev.add(d);
        }
    }
    let _ = ev.has_error(Layer::Family);
}

fn evaluate_checksum(
    inner: &Inner,
    ev: &mut Evaluation,
    scan: &Scan,
    prefix: &[u8],
    record: Option<&Value>,
) {
    ev.ran(Layer::Checksum);
    let mut result = ChecksumResult::default();
    if scan.candidate_count() != 1 {
        ev.add(Diagnostic::new(
            Code::R2ChecksumLines,
            "Expected exactly one scalar checksum header line",
        ));
        ev.checksum = Some(result);
        return;
    }
    let (line, number) = scan.checksum_line().expect("one candidate");
    let stated = header_text(line, prefix)
        .ok()
        .and_then(|text| yaml::load(&text, inner.limits.yaml()).ok())
        .and_then(|loaded| loaded.value)
        .and_then(|value| match value {
            Value::Object(items) if items.len() == 1 && items[0].0 == "checksum" => {
                match &items[0].1 {
                    Value::String(s) if !s.is_empty() => Some(s.clone()),
                    _ => None,
                }
            }
            _ => None,
        });
    let header_value = record
        .and_then(|r| r.get("checksum"))
        .and_then(Value::as_str);
    let consistent = match (&stated, record) {
        (Some(s), Some(_)) => header_value == Some(s.as_str()),
        (Some(_), None) => true, // the full header did not load; its own layer reports that
        (None, _) => false,
    };
    if let Some((computed, covered)) = scan.computed() {
        result.computed = Some(computed);
        result.covered_bytes = covered;
    }
    result.stated = stated.clone();
    if !consistent {
        ev.add(
            Diagnostic::new(
                Code::R5ChecksumIncomplete,
                "The checksum header line must contain the complete checksum value as a single-line scalar",
            )
            .at_line(number),
        );
        ev.checksum = Some(result);
        return;
    }
    if !checksum::checksum_line_is_strict(&line[prefix.len()..]) {
        ev.add(
            Diagnostic::new(
                Code::R5ChecksumContent,
                "The checksum header line must hold only the checksum value: 44 canonical base64 characters, optionally \
                 quoted, with no comment, tag, tab or other text (FAIR-bioHeaders-Specification docs/FORMAT.md R4 and R5)",
            )
            .at_line(number),
        );
        ev.checksum = Some(result);
        return;
    }
    let matches = result.computed.is_some() && result.computed == stated;
    result.matches = Some(matches);
    if !matches {
        ev.add(Diagnostic::new(
            Code::R3ChecksumMismatch,
            "Checksum verification failed",
        ));
    }
    ev.checksum = Some(result);
}

fn evaluate_metadata(inner: &Inner, ev: &mut Evaluation, json: bool, buffer: &[u8]) {
    ev.container = if json {
        Container::MetadataJson
    } else {
        Container::MetadataYaml
    };
    let text = match std::str::from_utf8(buffer) {
        Ok(text) => text,
        Err(e) => {
            ev.ran(Layer::Yaml);
            ev.add(Diagnostic::new(
                Code::R6InvalidUtf8,
                format!(
                    "'utf-8' codec can't decode byte 0x{:02x} in position {}: invalid start byte",
                    buffer.get(e.valid_up_to()).copied().unwrap_or(0),
                    e.valid_up_to()
                ),
            ));
            ev.block_after(Layer::Yaml);
            return;
        }
    };
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    match load_record(inner, ev, text, json, None) {
        Some(record) => evaluate_record(inner, ev, &record, None),
        None => ev.block_after(Layer::Yaml),
    }
}
