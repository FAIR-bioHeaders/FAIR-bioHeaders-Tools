// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Pinned-corpus harness (Tools#208 sections 1 and 6): locate a
//! specification checkout, verify the manifest digest and count before
//! running anything, account for every vector, and write a receipt.
//!
//! A missing corpus is a failure, never a skip. Only an explicit
//! `FH_ALLOW_MISSING_CORPUS=1` (local development, never CI) turns it into a
//! recorded NOT_RUN of the whole suite.

#![allow(dead_code)]

use fair_bioheaders_tools::{Container, Engine, Operation, Outcome, Report, Severity};
use serde_json::{Value as Json, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// A pinned corpus identity.
pub struct Pin {
    pub label: &'static str,
    pub env: &'static str,
    pub commit: &'static str,
    pub manifest: &'static str,
    pub sha256: &'static str,
    pub count: usize,
}

pub const C_FROZEN: Pin = Pin {
    label: "C-FROZEN",
    env: "FH_SPEC_V060",
    commit: "0ae18b00ee4bd71ab2dc28bae706b0f9d195076b",
    manifest: "conformance/manifest.json",
    sha256: "cdbb79b1fbfda52b27a9f54b73d3bae1efb662efcbb4c41ba02b9e3be40a51e1",
    count: 291,
};

pub const C_SOURCE: Pin = Pin {
    label: "C-SOURCE",
    env: "FH_SPEC_34BBE21A",
    commit: "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b",
    manifest: "conformance/manifest.json",
    sha256: "7c10fb83bbac5c5739240bff695e5469730ac26a066a51a44d5275598b2df3f6",
    count: 319,
};

/// The specification's R4 retirement crosswalk (Tools#208 C-HIST).
pub const C_HIST: Pin = Pin {
    label: "C-HIST",
    env: "FH_SPEC_34BBE21A",
    commit: "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b",
    manifest: "conformance/reader-policy/retirement-crosswalk.json",
    sha256: "c648601b6dc7589fa3efd40e870cc053385636e0f58ac6a73f429ff6abaabc4b",
    count: 78,
};

pub const C_POLICY: Pin = Pin {
    label: "C-POLICY",
    env: "FH_SPEC_34BBE21A",
    commit: "34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b",
    manifest: "conformance/reader-policy/cases.json",
    sha256: "b42d9c545d47ff9654f72b38a294f08640ed0e42aa4ff7fc756b0c33217db7c7",
    count: 64,
};

/// Formats outside the Phase 1 engine (#207 section 1).
pub const OUTSIDE_ENGINE: [&str; 2] = ["jsonld", "microdata"];

pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

/// The corpus root, or `None` when missing and explicitly allowed.
pub fn locate(pin: &Pin) -> Option<PathBuf> {
    match std::env::var_os(pin.env) {
        Some(path) => Some(PathBuf::from(path)),
        None => {
            if std::env::var("FH_ALLOW_MISSING_CORPUS").as_deref() == Ok("1")
                && std::env::var("CI").is_err()
            {
                eprintln!(
                    "{}: NOT_RUN (corpus missing; FH_ALLOW_MISSING_CORPUS=1)",
                    pin.label
                );
                None
            } else {
                panic!(
                    "{}: set {} to a FAIR-bioHeaders-Specification checkout at {} (a missing corpus is a failure)",
                    pin.label, pin.env, pin.commit
                )
            }
        }
    }
}

/// Load and verify the manifest; panics on any identity mismatch.
pub fn manifest(root: &Path, pin: &Pin) -> Json {
    let path = root.join(pin.manifest);
    let bytes = std::fs::read(&path)
        .unwrap_or_else(|e| panic!("{}: cannot read {}: {e}", pin.label, path.display()));
    let digest = sha256_hex(&bytes);
    assert_eq!(
        digest, pin.sha256,
        "{}: manifest digest is not the pinned one",
        pin.label
    );
    let json: Json = serde_json::from_slice(&bytes).expect("manifest JSON");
    let entries = json
        .get("vectors")
        .or_else(|| json.get("cases"))
        .and_then(Json::as_array)
        .expect("vector list");
    assert_eq!(
        entries.len(),
        pin.count,
        "{}: manifest count differs from the pin",
        pin.label
    );
    json
}

/// Per-format accounting.
#[derive(Default, Debug)]
pub struct Tally {
    pub total: usize,
    pub run: usize,
    pub passed: usize,
    pub failed: usize,
    pub not_run: BTreeMap<String, usize>,
}

/// A completed run.
#[derive(Default, Debug)]
pub struct Run {
    pub per_format: BTreeMap<String, Tally>,
    pub failures: Vec<String>,
    pub executed: Vec<String>,
    pub declared_not_run: Vec<String>,
    /// Vectors whose historical expectation the specification retired
    /// (crosswalk), each verified to be rejected for the retirement reason.
    pub superseded: Vec<String>,
}

impl Run {
    pub fn record(&mut self, format: &str, id: &str, result: Result<(), String>) {
        let tally = self.per_format.entry(format.to_owned()).or_default();
        tally.total += 1;
        tally.run += 1;
        self.executed.push(id.to_owned());
        match result {
            Ok(()) => tally.passed += 1,
            Err(message) => {
                tally.failed += 1;
                self.failures.push(format!("{id}: {message}"));
            }
        }
    }

    pub fn superseded(&mut self, format: &str, id: &str) {
        let tally = self.per_format.entry(format.to_owned()).or_default();
        tally.total += 1;
        tally.run += 1;
        self.executed.push(id.to_owned());
        self.superseded.push(id.to_owned());
    }

    pub fn not_run(&mut self, format: &str, id: &str, reason: &str) {
        let tally = self.per_format.entry(format.to_owned()).or_default();
        tally.total += 1;
        *tally.not_run.entry(reason.to_owned()).or_default() += 1;
        self.declared_not_run.push(id.to_owned());
    }

    pub fn totals(&self) -> (usize, usize, usize, usize) {
        let mut out = (0, 0, 0, 0);
        for t in self.per_format.values() {
            out.0 += t.total;
            out.1 += t.run;
            out.2 += t.passed;
            out.3 += t.failed;
        }
        out
    }

    /// Write the receipt and return its path.
    pub fn write_receipt(&self, pin: &Pin, engine: &Engine) -> PathBuf {
        let provenance = engine.provenance();
        let mut per_format = serde_json::Map::new();
        let mut not_run = BTreeMap::<String, usize>::new();
        for (format, t) in &self.per_format {
            per_format.insert(
                format.clone(),
                json!({"total": t.total, "run": t.run, "passed": t.passed, "failed": t.failed, "notRun": t.not_run}),
            );
            for (reason, n) in &t.not_run {
                *not_run.entry(reason.clone()).or_default() += n;
            }
        }
        let (total, run, passed, failed) = self.totals();
        let receipt = json!({
            "corpus": pin.label,
            "manifest": pin.manifest,
            "manifestSha256": pin.sha256,
            "specCommit": pin.commit,
            "engineVersion": provenance.engine_version,
            "abiVersion": provenance.abi_version,
            "bundleId": provenance.bundle_id,
            "profileId": provenance.profile_id,
            "platform": format!("{}-{}", std::env::consts::ARCH, std::env::consts::OS),
            "packageVersion": Json::Null,
            "totals": {"total": total, "run": run, "passed": passed, "failed": failed},
            "perFormat": per_format,
            "notRun": not_run,
            "supersededByCrosswalk": {"count": self.superseded.len(), "ids": self.superseded,
                "crosswalk": C_HIST.manifest, "crosswalkSha256": C_HIST.sha256},
            "failures": self.failures,
            "runner": {"harness": "cargo test", "skipped": 0},
            "ciRunId": std::env::var("GITHUB_RUN_ID").ok(),
        });
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../target/receipts");
        std::fs::create_dir_all(&dir).expect("receipt directory");
        let path = dir.join(format!("{}.json", pin.label));
        std::fs::write(
            &path,
            serde_json::to_string_pretty(&receipt).unwrap() + "\n",
        )
        .expect("write receipt");
        path
    }
}

/// Values compare as the specification README says: numbers by value,
/// strings, numbers and booleans never equal to each other.
pub fn same_json(left: &Json, right: &Json) -> bool {
    match (left, right) {
        (Json::Number(a), Json::Number(b)) => {
            let a = fair_bioheaders_tools::Number::parse_json(&a.to_string());
            let b = fair_bioheaders_tools::Number::parse_json(&b.to_string());
            match (a, b) {
                (Ok(a), Ok(b)) => a.canonical() == b.canonical(),
                _ => false,
            }
        }
        (Json::Array(a), Json::Array(b)) => {
            a.len() == b.len() && a.iter().zip(b).all(|(x, y)| same_json(x, y))
        }
        (Json::Object(a), Json::Object(b)) => {
            a.len() == b.len()
                && a.iter()
                    .all(|(k, v)| b.get(k).is_some_and(|w| same_json(v, w)))
        }
        _ => left == right,
    }
}

pub fn container_for(format: &str) -> Option<Container> {
    match format {
        "fasta" => Some(Container::Fasta),
        "fhp-fasta" => Some(Container::FhpFasta),
        "gfa" => Some(Container::Gfa),
        "fhgff3" => Some(Container::Gff3),
        _ => None,
    }
}

/// Check one main-suite vector against its manifest expectation.
pub fn check_vector(engine: &Engine, root: &Path, vector: &Json) -> Result<Report, String> {
    let file = root
        .join("conformance")
        .join(vector["file"].as_str().expect("file"));
    let bytes = std::fs::read(&file).map_err(|e| format!("cannot read {}: {e}", file.display()))?;
    let container = container_for(vector["format"].as_str().unwrap()).expect("engine format");
    let report = engine
        .verify_bytes(Operation::Verify, container, &bytes)
        .map_err(|e| format!("engine error: {e}"))?;
    let expected = vector["expected"].as_str().unwrap();
    let first = report
        .first_error()
        .map(|d| format!("{} ({}): {}", d.code, d.rule.unwrap_or("-"), d.message));
    match expected {
        "valid" => {
            if report.outcome != Outcome::Valid {
                return Err(format!(
                    "expected valid, got {} [{}]",
                    report.outcome.as_str(),
                    first.unwrap_or_default()
                ));
            }
            if let Some(stated) = vector.get("checksum").and_then(Json::as_str) {
                let computed = report.checksum.as_ref().and_then(|c| c.computed.clone());
                if computed.as_deref() != Some(stated) {
                    return Err(format!("checksum {computed:?}, expected {stated}"));
                }
            }
            if let Some(Json::Object(expected)) = vector.get("metadata") {
                let actual = report
                    .metadata
                    .as_ref()
                    .map(|m| m.to_json())
                    .unwrap_or(Json::Null);
                for (key, value) in expected {
                    let got = actual.get(key).cloned().unwrap_or(Json::Null);
                    if !same_json(&got, value) {
                        return Err(format!("metadata {key}: got {got}, expected {value}"));
                    }
                }
            }
            if let Some(Json::Array(rules)) = vector.get("warnings") {
                for rule in rules {
                    let rule = rule.as_str().unwrap();
                    if !report
                        .diagnostics
                        .iter()
                        .any(|d| d.severity == Severity::Warning && d.rule == Some(rule))
                    {
                        return Err(format!("no warning under {rule}"));
                    }
                }
            }
        }
        "invalid" => {
            let unsupported =
                vector.get("result").and_then(Json::as_str) == Some("unsupported-version");
            let want = if unsupported {
                Outcome::Unsupported
            } else {
                Outcome::Invalid
            };
            if report.outcome != want {
                return Err(format!(
                    "expected {} ({}), got {} [{}]",
                    want.as_str(),
                    vector.get("rule").and_then(Json::as_str).unwrap_or("-"),
                    report.outcome.as_str(),
                    first.unwrap_or_default()
                ));
            }
        }
        other => return Err(format!("unknown expectation {other}")),
    }
    Ok(report)
}
