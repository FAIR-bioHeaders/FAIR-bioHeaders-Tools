// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Record-aware schema selection (SCHEMA-VERSIONS.md V1–V7) over the bundled
//! contracts, filtered by the engine's consumer support profile.
//!
//! Port of `bioheaders/selection.py` (toolkit 0.13.1). Schemas are never
//! fetched; an unknown release is unsupported (V4) with no fallback. The FHT
//! draft lane is opened only by an explicit builder option, never by the
//! environment.

use crate::value::Value;
use crate::yaml::py_repr;
use serde_json::Value as Json;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

const RAW_PREFIX: &str = "https://raw.githubusercontent.com/FAIR-bioHeaders/";
const W3ID_PREFIX: &str = "https://w3id.org/fair-bioheaders/";
const FHT_DRAFT_RAW: &str = "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json";
const FHR1_RELEASE: &str = "v0.3.1";
const DRAFT_ENV: &str = "BIOHEADERS_EXPERIMENTAL_FHT";

/// The parsed contract bundle.
#[derive(Debug, Clone)]
pub struct Bundle {
    /// Release tag → header type → file name.
    pub releases: BTreeMap<String, BTreeMap<String, String>>,
    /// The FHT draft file, citation, revision and digest.
    pub fht_draft: Option<(String, String, String)>,
    /// File name → SHA-256.
    pub digests: BTreeMap<String, String>,
    /// SHA-256 of `bundle.json`.
    pub manifest_sha256: String,
    /// `fhb-` + 16 hex digits of the manifest digest.
    pub bundle_id: String,
    /// The specification commit of the current release.
    pub spec_commit: String,
}

impl Bundle {
    /// Parse the compiled-in bundle.
    pub fn load() -> Bundle {
        let text = fair_bioheaders_tools_bundles::BUNDLE_JSON;
        let json: Json = serde_json::from_str(text).expect("bundle.json is valid JSON");
        let mut releases = BTreeMap::new();
        for (tag, row) in json["releases"].as_object().expect("releases") {
            let mut types = BTreeMap::new();
            for (kind, file) in row.as_object().expect("release row") {
                types.insert(kind.clone(), file.as_str().expect("file").to_owned());
            }
            releases.insert(tag.clone(), types);
        }
        let fht_draft = json["drafts"].get("FHT").map(|d| {
            (
                d["file"].as_str().unwrap_or_default().to_owned(),
                d["revision"].as_str().unwrap_or_default().to_owned(),
                d["sha256"].as_str().unwrap_or_default().to_owned(),
            )
        });
        let mut digests = BTreeMap::new();
        for (name, entry) in json["files"].as_object().expect("files") {
            digests.insert(name.clone(), entry["sha256"].as_str().unwrap_or_default().to_owned());
        }
        let manifest_sha256 = hex(&Sha256::digest(text.as_bytes()));
        Bundle {
            releases,
            fht_draft,
            digests,
            bundle_id: format!("fhb-{}", &manifest_sha256[..16]),
            manifest_sha256,
            spec_commit: json["specCommit"].as_str().unwrap_or_default().to_owned(),
        }
    }
}

/// A consumer support profile.
#[derive(Debug, Clone)]
pub struct Profile {
    /// Profile id.
    pub id: String,
    /// The release that raw-main citations select for this consumer.
    pub current_release: String,
    /// Releases this consumer supports.
    pub releases: Vec<String>,
    /// Draft lanes this consumer may enable.
    pub draft_lanes: Vec<String>,
    /// Consumer exact-integer bound for FHT C1, if any.
    pub consumer_exact_integer_bits: Option<u32>,
    /// SHA-256 of the definition.
    pub sha256: String,
}

impl Profile {
    /// The compiled-in profile `id`.
    pub fn load(id: &str) -> Option<Profile> {
        let text = fair_bioheaders_tools_bundles::profile(id)?;
        let json: Json = serde_json::from_str(text).ok()?;
        let list = |key: &str| -> Vec<String> {
            json[key].as_array().map(|a| a.iter().filter_map(|v| v.as_str().map(str::to_owned)).collect()).unwrap_or_default()
        };
        Some(Profile {
            id: json["id"].as_str()?.to_owned(),
            current_release: json["currentRelease"].as_str()?.to_owned(),
            releases: list("releases"),
            draft_lanes: list("draftLanes"),
            consumer_exact_integer_bits: json["consumerExactIntegerBits"].as_u64().map(|v| v as u32),
            sha256: hex(&Sha256::digest(text.as_bytes())),
        })
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// What a `schema` value selects.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Choice {
    /// A bundled file.
    Selected { header_type: String, release: String, file: String, rule: &'static str, draft: bool },
    /// V4: not available.
    Unsupported { header_type: String, message: String },
    /// Bundled, but outside this consumer's profile.
    OutsideProfile { header_type: String, release: String, message: String },
}

/// The selection context: bundle, profile and enabled lanes.
#[derive(Debug, Clone)]
pub struct Selector {
    bundle: Bundle,
    profile: Profile,
    fht_draft_lane: bool,
}

impl Selector {
    /// A selector; `fht_draft_lane` opens the historical FHT draft (V7).
    pub fn new(bundle: Bundle, profile: Profile, fht_draft_lane: bool) -> Selector {
        Selector { bundle, profile, fht_draft_lane }
    }

    /// The bundle.
    pub fn bundle(&self) -> &Bundle {
        &self.bundle
    }

    /// The profile.
    pub fn profile(&self) -> &Profile {
        &self.profile
    }

    fn current_files(&self) -> &BTreeMap<String, String> {
        self.bundle.releases.get(&self.profile.current_release).expect("profile current release is bundled")
    }

    fn profile_has(&self, release: &str, kind: &str) -> bool {
        self.profile.releases.iter().any(|r| r == release)
            && self.bundle.releases.get(release).is_some_and(|row| row.contains_key(kind))
    }

    /// Whether FHT is selectable at all (a released FHT within the profile).
    pub fn shared_fht_available(&self) -> bool {
        self.profile.releases.iter().any(|r| self.bundle.releases.get(r).is_some_and(|row| row.contains_key("FHT")))
    }

    /// `(header type, ref)` for a FAIR-bioHeaders schema URL, else `None`.
    pub fn parse(&self, value: &str) -> Option<(String, String, bool)> {
        if let Some((kind, reference)) = parse_raw(value, &["FHR-Specification", "FAIR-bioHeaders-Specification"], &["fhr", "fhp", "fhgff3"]) {
            return Some((type_name(&kind), reference, false));
        }
        if let Some((kind, release)) = parse_w3id(value, &["fhr", "fhp", "fhgff3"]) {
            return Some((type_name(&kind), release, true));
        }
        if self.shared_fht_available() {
            if let Some((_, reference)) = parse_raw(value, &["FAIR-bioHeaders-Specification"], &["fht"]) {
                return Some(("FHT".into(), reference, false));
            }
            if let Some((_, release)) = parse_w3id(value, &["fht"]) {
                return Some(("FHT".into(), release, true));
            }
        }
        if self.fht_draft_lane && value == FHT_DRAFT_RAW {
            return Some(("FHT".into(), "main".into(), false));
        }
        None
    }

    /// The header type a `schema` value names (V5: FHR otherwise).
    pub fn header_type(&self, schema: Option<&Value>) -> String {
        schema.and_then(Value::as_str).and_then(|s| self.parse(s)).map_or_else(|| "FHR".to_owned(), |p| p.0)
    }

    /// The header type of a record.
    pub fn record_header_type(&self, record: &Value) -> String {
        self.header_type(record.get("schema"))
    }

    fn supported(&self, kind: &str) -> Vec<String> {
        let mut names = Vec::new();
        if self.current_files().contains_key(kind) {
            names.push(format!("main ({})", self.profile.current_release));
        }
        for release in &self.profile.releases {
            if self.bundle.releases.get(release).is_some_and(|row| row.contains_key(kind)) {
                names.push(release.clone());
            }
        }
        names
    }

    fn unsupported(&self, value: &str, kind: &str) -> Choice {
        Choice::Unsupported {
            header_type: kind.to_owned(),
            message: format!(
                "unsupported schema version: {} (this tool has {kind} schemas for {})",
                py_repr(value),
                self.supported(kind).join(", ")
            ),
        }
    }

    /// Select for a `schema` value (V1–V5, V7).
    pub fn select(&self, schema: Option<&str>) -> Choice {
        let Some(value) = schema else {
            return self.current("FHR", "V5");
        };
        let Some((kind, reference, w3id)) = self.parse(value) else {
            return self.current("FHR", "V5");
        };
        if kind == "FHT" && value == FHT_DRAFT_RAW {
            let (file, _, _) = self.bundle.fht_draft.clone().unwrap_or_default();
            return Choice::Selected { header_type: kind, release: "main".into(), file, rule: "V7", draft: true };
        }
        if reference == "main" && self.current_files().contains_key(&kind) {
            return self.current(&kind, "V1");
        }
        if is_release(&reference) {
            if self.profile_has(&reference, &kind) {
                let file = self.bundle.releases[&reference][&kind].clone();
                return Choice::Selected {
                    header_type: kind,
                    release: reference,
                    file,
                    rule: if w3id { "V3" } else { "V2" },
                    draft: false,
                };
            }
            if self.bundle.releases.get(&reference).is_some_and(|row| row.contains_key(&kind)) {
                return Choice::OutsideProfile {
                    header_type: kind.clone(),
                    release: reference.clone(),
                    message: format!(
                        "unsupported schema version: {} is outside the {} support profile (this tool has {kind} schemas for {})",
                        py_repr(value),
                        self.profile.id,
                        self.supported(&kind).join(", ")
                    ),
                };
            }
        }
        self.unsupported(value, &kind)
    }

    fn current(&self, kind: &str, rule: &'static str) -> Choice {
        match self.current_files().get(kind) {
            Some(file) => Choice::Selected {
                header_type: kind.to_owned(),
                release: self.profile.current_release.clone(),
                file: file.clone(),
                rule,
                draft: false,
            },
            None => self.unsupported(kind, kind),
        }
    }

    /// Select for a record (V1–V7, with V6).
    pub fn select_record(&self, record: &Value) -> Choice {
        if self.reads_as_fhr1(record) {
            if self.profile_has(FHR1_RELEASE, "FHR") {
                return Choice::Selected {
                    header_type: "FHR".into(),
                    release: FHR1_RELEASE.into(),
                    file: self.bundle.releases[FHR1_RELEASE]["FHR"].clone(),
                    rule: "V6",
                    draft: false,
                };
            }
            return Choice::OutsideProfile {
                header_type: "FHR".into(),
                release: FHR1_RELEASE.into(),
                message: format!("unsupported schema version: FHR 1 ({FHR1_RELEASE}) is outside the {} support profile", self.profile.id),
            };
        }
        let schema = record.get("schema");
        match schema {
            Some(Value::String(s)) => self.select(Some(s)),
            _ => self.select(None),
        }
    }

    /// V6: raw-main `fhr.json` with `schemaVersion` the number 1.
    pub fn reads_as_fhr1(&self, record: &Value) -> bool {
        let Some(Value::String(schema)) = record.get("schema") else {
            return false;
        };
        let parsed = self.parse(schema);
        if parsed.as_ref().map(|(k, r, _)| (k.as_str(), r.as_str())) != Some(("FHR", "main")) {
            return false;
        }
        matches!(record.get("schemaVersion"), Some(Value::Number(n)) if n.is_integral() && n.canonical() == "1")
    }

    /// Selection warnings (V6, V7, V5 near-miss), in the Python order.
    pub fn warnings(&self, record: &Value) -> Vec<(&'static str, String)> {
        let mut out = Vec::new();
        if self.reads_as_fhr1(record) {
            out.push(("V6", self.fhr1_warning()));
        }
        let schema = record.get("schema").and_then(Value::as_str);
        if let Some(value) = schema {
            if self.fht_draft_lane && value == FHT_DRAFT_RAW {
                let (_, revision, digest) = self.bundle.fht_draft.clone().unwrap_or_default();
                out.push((
                    "V7",
                    format!(
                        "schema {value} selects the bundled FHT draft contract (commit {revision}, sha256 {digest} of those bytes) \
                         (development only, not a released schema; experimental opt-in via {DRAFT_ENV}, see docs/FHT-SELECTION-DESIGN.md)"
                    ),
                ));
            }
            if let Some(message) = self.near_miss_warning(value) {
                out.push(("V5", message));
            }
        }
        out
    }

    fn fhr1_warning(&self) -> String {
        let current = self.current_fhr_version();
        format!(
            "schemaVersion 1 via the raw-main schema URL is read as FHR 1 ({FHR1_RELEASE}); \
             cite {W3ID_PREFIX}fhr/{FHR1_RELEASE} or move to schemaVersion \"{current}\""
        )
    }

    fn current_fhr_version(&self) -> String {
        let Some(file) = self.current_files().get("FHR") else {
            return String::new();
        };
        let bytes = fair_bioheaders_tools_bundles::schema(file).unwrap_or_default();
        let json: Json = serde_json::from_slice(bytes).unwrap_or(Json::Null);
        let versions = json["properties"]["schemaVersion"]["enum"].as_array().cloned().unwrap_or_default();
        versions
            .iter()
            .filter_map(|v| v.as_str())
            .max_by_key(|v| v.split('.').map(|p| p.parse::<u64>().unwrap_or(0)).collect::<Vec<_>>())
            .unwrap_or_default()
            .to_owned()
    }

    fn near_miss_warning(&self, value: &str) -> Option<String> {
        if self.parse(value).is_some() {
            return None;
        }
        let lowered = value.to_lowercase();
        if !(lowered.starts_with(&W3ID_PREFIX.to_lowercase()) || lowered.starts_with(&RAW_PREFIX.to_lowercase())) {
            return None;
        }
        if let Some(kind) = near_miss_type(&lowered) {
            return Some(format!(
                "schema {} is not a FAIR-bioHeaders schema URL; read as FHR, not {kind}, against the current schema (rule V5)",
                py_repr(value)
            ));
        }
        let message = format!(
            "schema {} is not a FAIR-bioHeaders schema URL; read as FHR against the current schema (rule V5)",
            py_repr(value)
        );
        let suggestion = format!("{W3ID_PREFIX}fhr/{}", self.profile.current_release);
        Some(format!("{message}; did you mean {}?", py_repr(&suggestion)))
    }
}

/// `(?:^|[/._-])(fhp|fhgff3|fht)(?:[/._-]|$)` on the lower-cased value.
fn near_miss_type(lowered: &str) -> Option<&'static str> {
    let bytes = lowered.as_bytes();
    let sep = |b: u8| matches!(b, b'/' | b'.' | b'_' | b'-');
    let mut best: Option<(usize, &'static str)> = None;
    for (word, kind) in [("fhp", "FHP"), ("fhgff3", "FHGFF3"), ("fht", "FHT")] {
        let mut start = 0;
        while let Some(found) = lowered[start..].find(word) {
            let index = start + found;
            let before_ok = index == 0 || sep(bytes[index - 1]);
            let end = index + word.len();
            let after_ok = end == bytes.len() || sep(bytes[end]);
            if before_ok && after_ok {
                if best.is_none_or(|(i, _)| index < i) {
                    best = Some((index, kind));
                }
                break;
            }
            start = index + 1;
        }
    }
    best.map(|(_, k)| k)
}

fn type_name(kind: &str) -> String {
    match kind {
        "fhr" => "FHR",
        "fhp" => "FHP",
        "fhgff3" => "FHGFF3",
        _ => "FHT",
    }
    .to_owned()
}

/// `v[0-9]+\.[0-9]+\.[0-9]+`
pub fn is_release(text: &str) -> bool {
    let Some(rest) = text.strip_prefix('v') else {
        return false;
    };
    let parts: Vec<&str> = rest.split('.').collect();
    parts.len() == 3 && parts.iter().all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()))
}

/// `https://raw.githubusercontent.com/FAIR-bioHeaders/<repo>/(.+?)/(<file>)\.json`
fn parse_raw(value: &str, repositories: &[&str], files: &[&str]) -> Option<(String, String)> {
    let rest = value.strip_prefix(RAW_PREFIX)?;
    for repository in repositories {
        let Some(rest) = rest.strip_prefix(repository).and_then(|r| r.strip_prefix('/')) else {
            continue;
        };
        for file in files {
            let suffix = format!("/{file}.json");
            if let Some(reference) = rest.strip_suffix(&suffix) {
                if !reference.is_empty() && !reference.contains('\n') {
                    return Some(((*file).to_owned(), reference.to_owned()));
                }
            }
        }
    }
    None
}

/// `https://w3id.org/fair-bioheaders/(<type>)/(vX.Y.Z)/?`
fn parse_w3id(value: &str, types: &[&str]) -> Option<(String, String)> {
    let rest = value.strip_prefix(W3ID_PREFIX)?;
    for kind in types {
        if let Some(release) = rest.strip_prefix(kind).and_then(|r| r.strip_prefix('/')) {
            let release = release.strip_suffix('/').unwrap_or(release);
            if is_release(release) {
                return Some(((*kind).to_owned(), release.to_owned()));
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn selector(profile: &str, draft: bool) -> Selector {
        Selector::new(Bundle::load(), Profile::load(profile).unwrap(), draft)
    }

    fn file(choice: Choice) -> String {
        match choice {
            Choice::Selected { file, .. } => file,
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn v1_to_v5() {
        let s = selector("python", false);
        let raw = |r: &str, f: &str| format!("https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/{r}/{f}.json");
        assert_eq!(file(s.select(Some(&raw("main", "fhr")))), "fhr-2.1.json");
        assert_eq!(file(s.select(Some(&raw("v0.4.0", "fhp")))), "fhp-1.0.json");
        assert_eq!(file(s.select(Some("https://w3id.org/fair-bioheaders/fhr/v0.3.1/"))), "fhr-1.json");
        assert_eq!(file(s.select(Some("https://example.org/x"))), "fhr-2.1.json");
        assert!(matches!(s.select(Some(&raw("v9.9.9", "fhr"))), Choice::Unsupported { .. }));
        assert!(matches!(s.select(Some(&raw("refs/heads/main", "fhr"))), Choice::Unsupported { .. }));
        assert!(matches!(s.select(Some(&raw("v0.3.0", "fhp"))), Choice::Unsupported { .. }));
    }

    #[test]
    fn profile_does_not_widen() {
        let narrow = selector("test-narrow", false);
        let url = "https://w3id.org/fair-bioheaders/fhr/v0.8.0";
        assert!(matches!(narrow.select(Some(url)), Choice::OutsideProfile { .. }));
        assert!(!narrow.shared_fht_available());
        assert_eq!(file(narrow.select(Some("https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/fhp.json"))), "fhp-1.2.json");
    }

    #[test]
    fn draft_lane_only_when_enabled() {
        assert_eq!(selector("python", false).header_type(Some(&Value::String(FHT_DRAFT_RAW.into()))), "FHR");
        let s = selector("python", true);
        assert_eq!(file(s.select(Some(FHT_DRAFT_RAW))), "fht-draft.json");
    }

    #[test]
    fn unsupported_message_matches_python() {
        let s = selector("python", false);
        let Choice::Unsupported { message, .. } = s.select(Some("https://w3id.org/fair-bioheaders/fhp/v0.3.0")) else {
            panic!()
        };
        assert_eq!(
            message,
            "unsupported schema version: 'https://w3id.org/fair-bioheaders/fhp/v0.3.0' (this tool has FHP schemas for main (v0.8.0), v0.4.0, v0.4.1, v0.4.2, v0.5.0, v0.6.0, v0.6.1, v0.7.0, v0.8.0)"
        );
    }
}
