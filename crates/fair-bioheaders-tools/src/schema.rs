// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! JSON Schema draft 2020-12 validation of metadata against the selected
//! bundled contract, plus the non-schema value checks the Python reference
//! applies after it (`check_checksums` R4 and FHT C1).
//!
//! Differences from the Python reference that decision 9 (specification#296)
//! makes deliberate: `pattern` is evaluated by an ECMA-262 engine (`regress`),
//! and `format: uri` is asserted on every install.

use crate::diagnostics::Code;
use crate::report::Diagnostic;
use crate::value::{Number, Value};
use jsonschema::{Keyword, ValidationError, Validator};
use num_bigint::BigInt;
use serde_json::{Map, Value as Json};
use std::collections::BTreeMap;
use std::sync::Arc;

/// Compiled validators for every bundled schema file.
pub struct Schemas {
    compiled: BTreeMap<String, (Arc<Validator>, Json)>,
}

impl std::fmt::Debug for Schemas {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Schemas")
            .field("files", &self.compiled.keys().collect::<Vec<_>>())
            .finish()
    }
}

struct EcmaPattern {
    regex: regress::Regex,
    source: String,
}

impl<'i> Keyword<'i> for EcmaPattern {
    fn validate(&self, instance: &'i Json) -> Result<(), ValidationError<'i>> {
        if self.is_valid(instance) {
            Ok(())
        } else {
            let text = instance.as_str().unwrap_or_default();
            Err(ValidationError::custom(format!(
                "{} does not match {}",
                crate::yaml::py_repr(text),
                crate::yaml::py_repr(&self.source)
            )))
        }
    }

    fn is_valid(&self, instance: &'i Json) -> bool {
        match instance.as_str() {
            Some(text) => self.regex.find(text).is_some(),
            None => true,
        }
    }
}

/// RFC 3339 `full-date` with years 0000–9999 (Python `is_full_date`).
pub fn is_full_date(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() != 10 || b[4] != b'-' || b[7] != b'-' {
        return false;
    }
    let digits = |r: std::ops::Range<usize>| -> Option<u32> {
        let s = &value[r];
        if s.bytes().all(|c| c.is_ascii_digit()) {
            s.parse().ok()
        } else {
            None
        }
    };
    let (Some(year), Some(month), Some(day)) = (digits(0..4), digits(5..7), digits(8..10)) else {
        return false;
    };
    if !(1..=12).contains(&month) {
        return false;
    }
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month as usize - 1]
        + u32::from(month == 2 && leap);
    (1..=days).contains(&day)
}

/// The validator configuration: draft 2020-12, asserted formats, the
/// RFC 3339 `full-date` rule with years 0000-9999, and ECMA-262 `pattern`.
pub fn validator_options() -> jsonschema::ValidationOptions<'static> {
    jsonschema::options()
        .with_draft(jsonschema::Draft::Draft202012)
        .should_validate_formats(true)
        .with_format("date", is_full_date)
        .with_keyword(
            "pattern",
            |_parent: &Map<String, Json>, value: &Json, _location| {
                let source = value.as_str().unwrap_or_default().to_owned();
                let regex = regress::Regex::with_flags(&source, "u")
                    .or_else(|_| regress::Regex::new(&source))
                    .map_err(|e| {
                        ValidationError::custom(format!("invalid ECMA-262 pattern {source:?}: {e}"))
                    })?;
                Ok(Box::new(EcmaPattern { regex, source }))
            },
        )
}

impl Schemas {
    /// Compile every bundled schema.
    pub fn compile() -> Result<Schemas, String> {
        let mut compiled = BTreeMap::new();
        for (name, bytes) in fair_bioheaders_tools_bundles::SCHEMAS {
            let json: Json = serde_json::from_slice(bytes).map_err(|e| format!("{name}: {e}"))?;
            let validator = validator_options()
                .build(&json)
                .map_err(|e| format!("{name}: {e}"))?;
            compiled.insert((*name).to_owned(), (Arc::new(validator), json));
        }
        Ok(Schemas { compiled })
    }

    /// The parsed schema document `file`.
    pub fn document(&self, file: &str) -> Option<&Json> {
        self.compiled.get(file).map(|(_, json)| json)
    }

    /// Validate `record` against `file`; diagnostics in the order the
    /// validator reports them, the Python `best_match` choice first.
    pub fn validate(&self, file: &str, header_type: &str, record: &Value) -> Vec<Diagnostic> {
        let Some((validator, schema)) = self.compiled.get(file) else {
            return vec![Diagnostic::new(
                Code::SchemaEvaluation,
                format!("no bundled schema {file}"),
            )];
        };
        let instance = record.to_json();
        let mut errors: Vec<(usize, Diagnostic)> = Vec::new();
        for error in validator.iter_errors(&instance) {
            let depth = error.instance_path().iter().count();
            let weak = matches!(
                error.kind(),
                jsonschema::error::ValidationErrorKind::AnyOf { .. }
                    | jsonschema::error::ValidationErrorKind::OneOfNotValid { .. }
                    | jsonschema::error::ValidationErrorKind::OneOfMultipleValid { .. }
            );
            let diagnostic = describe(&error, header_type, schema, &instance);
            errors.push((depth * 2 + usize::from(weak), diagnostic));
        }
        // best_match: the shallowest error, preferring non-anyOf/oneOf; stable.
        if let Some(best) = errors
            .iter()
            .enumerate()
            .min_by_key(|(i, (rank, _))| (*rank, *i))
            .map(|(i, _)| i)
        {
            let first = errors.remove(best);
            errors.insert(0, first);
        }
        errors.into_iter().map(|(_, d)| d).collect()
    }
}

fn default_code(header_type: &str) -> Code {
    match header_type {
        "FHP" => Code::P1Schema,
        "FHGFF3" => Code::G2Schema,
        "FHT" => Code::SchemaFht,
        _ => Code::SchemaFhr,
    }
}

fn is_extension_key(key: &str) -> bool {
    let mut chars = key.strip_prefix("x-").map(str::chars);
    let Some(chars) = chars.as_mut() else {
        return false;
    };
    match chars.next() {
        Some(c) if c.is_ascii_alphanumeric() => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-'))
}

fn quoted(keys: &[String]) -> String {
    keys.iter()
        .map(|k| crate::yaml::py_repr(k))
        .collect::<Vec<_>>()
        .join(", ")
}

const EXTENSION_RULE: &str = "FAIR-bioHeaders-Specification docs/FORMAT.md R15";

fn unknown_field_message(keys: &[String]) -> String {
    format!(
        "unknown field {}: not a field of this schema, and not an extension field (x- followed by a letter or digit, \
         then letters, digits, _, . or -) ({EXTENSION_RULE})",
        quoted(keys)
    )
}

fn describe(
    error: &ValidationError<'_>,
    header_type: &str,
    root: &Json,
    instance: &Json,
) -> Diagnostic {
    use jsonschema::error::ValidationErrorKind as K;
    let pointer = error.instance_path().as_str().to_owned();
    let at_root = pointer.is_empty();
    let schema_at = resolve_pointer(root, error.schema_path().as_str());
    let (code, message) = match error.kind() {
        K::Not { schema } if schema == &serde_json::json!({"pattern": "^x-"}) => {
            let key = error.instance().as_str().unwrap_or_default().to_owned();
            if !is_extension_key(&key) {
                (Code::R15UnknownField, unknown_field_message(&[key]))
            } else {
                (
                    Code::R15NotAllowed,
                    format!(
                        "{}: extension fields (x- keys) are not allowed in a record that states the older schemaVersion; \
                         state the version that adds them (FHR '2.1', FHP and FHGFF3 '1.1') ({EXTENSION_RULE})",
                        crate::yaml::py_repr(&key)
                    ),
                )
            }
        }
        K::Not { schema } if schema == &serde_json::json!({"pattern": "\n"}) => {
            let key = error.instance().as_str().unwrap_or_default();
            (Code::R15UnknownField, format!("the key {} contains a line feed ({EXTENSION_RULE})", crate::yaml::py_repr(key)))
        }
        K::AdditionalProperties { unexpected } => {
            let parent = schema_at.and_then(|_| parent_schema(root, error.schema_path().as_str()));
            let has_patterns = parent.is_some_and(|p| p.get("patternProperties").is_some());
            let has_schema_version = parent.is_some_and(|p| p.get("properties").and_then(|v| v.get("schemaVersion")).is_some());
            if has_patterns {
                (Code::R15UnknownField, unknown_field_message(unexpected))
            } else if at_root && has_schema_version && !unexpected.is_empty() && unexpected.iter().all(|k| is_extension_key(k)) {
                (
                    Code::R15NotAllowed,
                    format!(
                        "{}: this schema has no extension fields (x- keys); cite a v0.5.0 or later schema and state its \
                         schemaVersion (FHR '2.1', FHP and FHGFF3 '1.1') ({EXTENSION_RULE})",
                        quoted(unexpected)
                    ),
                )
            } else {
                (default_code(header_type), python_message(error, instance))
            }
        }
        K::AnyOf { .. } if error.schema_path().as_str().contains("anyOf") && mentions(root, error.schema_path().as_str(), "genomeReference") => (
            default_code(header_type),
            "no genome link: give a derivedFrom item with headerType FHR and relationship annotates, or a genomeReference \
             with accession and seqcol_id (FAIR-bioHeaders-Specification docs/FHGFF3.md G2)"
                .to_owned(),
        ),
        K::Not { schema } if schema.to_string().contains("Annotates") || mentions(root, error.schema_path().as_str(), "Annotates") => {
            (default_code(header_type), "more than one derivedFrom item has the relationship annotates".to_owned())
        }
        _ => (default_code(header_type), python_message(error, instance)),
    };
    Diagnostic::new(code, message).at_pointer(pointer)
}

/// A message in the shape of Python `jsonschema` (informative only).
fn python_message(error: &ValidationError<'_>, _instance: &Json) -> String {
    use jsonschema::error::ValidationErrorKind as K;
    let shown = |v: &Json| python_literal(v);
    match error.kind() {
        K::Required { property } => format!("{} is a required property", shown(property)),
        K::Type { kind } => format!(
            "{} is not of type {}",
            shown(error.instance()),
            type_names(kind)
        ),
        K::Enum { options } => format!(
            "{} is not one of {}",
            shown(error.instance()),
            shown(options)
        ),
        K::Constant { expected_value } => format!("{} was expected", shown(expected_value)),
        K::Format { format } => format!(
            "{} is not a {}",
            shown(error.instance()),
            crate::yaml::py_repr(format)
        ),
        K::Pattern { pattern } => format!(
            "{} does not match {}",
            shown(error.instance()),
            crate::yaml::py_repr(pattern)
        ),
        K::Custom { message, .. } => message.clone(),
        K::AdditionalProperties { unexpected } => {
            let verb = if unexpected.len() == 1 { "was" } else { "were" };
            format!(
                "Additional properties are not allowed ({} {verb} unexpected)",
                quoted(unexpected)
            )
        }
        K::MinLength { .. } => format!("{} should be non-empty", shown(error.instance())),
        K::MinItems { .. } => format!("{} should be non-empty", shown(error.instance())),
        K::Minimum { limit } => format!(
            "{} is less than the minimum of {}",
            shown(error.instance()),
            limit
        ),
        K::Maximum { limit } => format!(
            "{} is greater than the maximum of {}",
            shown(error.instance()),
            limit
        ),
        _ => error.to_string(),
    }
}

fn type_names(kind: &jsonschema::error::TypeKind) -> String {
    use jsonschema::error::TypeKind;
    match kind {
        TypeKind::Single(t) => crate::yaml::py_repr(&t.to_string()),
        TypeKind::Multiple(ts) => {
            let names: Vec<String> = ts
                .iter()
                .map(|t| crate::yaml::py_repr(&t.to_string()))
                .collect();
            format!("[{}]", names.join(", "))
        }
    }
}

/// Python `repr` of a JSON value as `jsonschema` shows instances.
pub fn python_literal(value: &Json) -> String {
    match value {
        Json::Null => "None".into(),
        Json::Bool(true) => "True".into(),
        Json::Bool(false) => "False".into(),
        Json::Number(n) => n.to_string(),
        Json::String(s) => crate::yaml::py_repr(s),
        Json::Array(items) => format!(
            "[{}]",
            items
                .iter()
                .map(python_literal)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Json::Object(map) => format!(
            "{{{}}}",
            map.iter()
                .map(|(k, v)| format!("{}: {}", crate::yaml::py_repr(k), python_literal(v)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn resolve_pointer<'a>(root: &'a Json, pointer: &str) -> Option<&'a Json> {
    root.pointer(pointer)
}

/// The schema object that holds the failing keyword (`.../additionalProperties` → `...`).
fn parent_schema<'a>(root: &'a Json, schema_path: &str) -> Option<&'a Json> {
    let cut = schema_path.rfind('/')?;
    let parent = &schema_path[..cut];
    let found = root.pointer(parent);
    if found.is_some() {
        return found;
    }
    // Paths through $ref name the keyword, not the resolved location; fall back
    // to the root when the keyword is reached through a reference.
    Some(root)
}

fn mentions(root: &Json, schema_path: &str, word: &str) -> bool {
    root.pointer(schema_path)
        .is_some_and(|v| v.to_string().contains(word))
}

/// R4 over checksum properties declared by the selected contract
/// (`check_checksums`): unknown and extension fields stay opaque.
pub fn check_checksums(record: &Value, schema: &Json) -> Option<Diagnostic> {
    fn visit(
        value: &Value,
        part: &Json,
        root: &Json,
        path: &mut Vec<String>,
        out: &mut Option<Diagnostic>,
    ) {
        if out.is_some() {
            return;
        }
        let Some(part_map) = part.as_object() else {
            return;
        };
        if let Some(Json::String(reference)) = part_map.get("$ref") {
            if let Some(rest) = reference.strip_prefix("#/") {
                let pointer = format!("/{rest}");
                if let Some(resolved) = root.pointer(&pointer) {
                    visit(value, resolved, root, path, out);
                }
            }
        }
        match value {
            Value::Object(items) => {
                if let Some(Json::Object(properties)) = part_map.get("properties") {
                    for (key, definition) in properties {
                        if key.starts_with("x-") {
                            continue;
                        }
                        let Some((_, child)) = items.iter().find(|(k, _)| k == key) else {
                            continue;
                        };
                        if key == "checksum" {
                            if let Value::String(text) = child {
                                if !crate::checksum::is_canonical_base64_digest(text.as_bytes()) {
                                    let mut pointer = path.clone();
                                    pointer.push(key.clone());
                                    *out = Some(
                                        Diagnostic::new(
                                            Code::R4NonCanonical,
                                            "R4: checksum must be canonical base64 SHA-512/256",
                                        )
                                        .at_pointer(to_pointer(&pointer)),
                                    );
                                    return;
                                }
                                continue;
                            }
                        }
                        path.push(key.clone());
                        visit(child, definition, root, path, out);
                        path.pop();
                    }
                }
            }
            Value::Array(items) => {
                if let Some(item_schema @ Json::Object(_)) = part_map.get("items") {
                    for (index, child) in items.iter().enumerate() {
                        path.push(index.to_string());
                        visit(child, item_schema, root, path, out);
                        path.pop();
                    }
                }
            }
            _ => {}
        }
        for keyword in ["allOf", "anyOf", "oneOf"] {
            if let Some(Json::Array(branches)) = part_map.get(keyword) {
                for branch in branches {
                    visit(value, branch, root, path, out);
                }
            }
        }
        for keyword in ["if", "then", "else"] {
            if let Some(branch) = part_map.get(keyword) {
                visit(value, branch, root, path, out);
            }
        }
    }
    let mut out = None;
    visit(record, schema, schema, &mut Vec::new(), &mut out);
    out
}

fn to_pointer(path: &[String]) -> String {
    path.iter()
        .map(|p| format!("/{}", p.replace('~', "~0").replace('/', "~1")))
        .collect()
}

/// The outcome of FHT C1.
pub enum C1 {
    /// Satisfied, or not applicable (schema errors stay with the schema).
    Ok,
    /// Component counts do not sum to the total.
    Fail(Diagnostic),
    /// A count exceeds the profile's consumer exact-integer bound.
    Limit(Diagnostic),
}

/// FHT C1: complete supplied integer counts must sum to `total`, computed
/// exactly; a profile with a consumer integer bound returns a limit instead
/// of deciding outside it (decision 12).
pub fn check_fht_completeness(record: &Value, consumer_bits: Option<u32>) -> C1 {
    let Some(Value::Object(_)) = record.get("completeness") else {
        return C1::Ok;
    };
    let completeness = record.get("completeness").expect("checked");
    let names = [
        "completeSingle",
        "completeDuplicated",
        "fragmented",
        "missing",
        "total",
    ];
    let mut values: Vec<BigInt> = Vec::new();
    for name in names {
        match completeness.get(name) {
            Some(Value::Number(n)) if n.is_integral() => match n.to_bigint() {
                Some(v) => values.push(v),
                None => return C1::Ok,
            },
            _ => return C1::Ok,
        }
    }
    if let Some(bits) = consumer_bits {
        let bound = (BigInt::from(1) << bits) - 1;
        let sum: BigInt = values[..4].iter().sum();
        if values
            .iter()
            .chain(std::iter::once(&sum))
            .any(|v| v > &bound || v < &(-bound.clone()))
        {
            return C1::Limit(
                Diagnostic::new(
                    Code::LimitConsumerInteger,
                    format!("C1: completeness counts exceed this consumer's exact integer range (2^{bits}-1)"),
                )
                .at_pointer("/completeness"),
            );
        }
    }
    let sum: BigInt = values[..4].iter().sum();
    if sum != values[4] {
        return C1::Fail(
            Diagnostic::new(
                Code::C1CompletenessSum,
                "C1: completeness component counts must sum to total",
            )
            .at_pointer("/completeness"),
        );
    }
    let _ = Number::parse_int;
    C1::Ok
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Decision 9: `pattern` is ECMA-262 (regress), not a translation: `\d`
    /// is ASCII and `$` matches only at the very end.
    #[test]
    fn pattern_is_evaluated_by_ecma_engine() {
        let schema = serde_json::json!({"type": "string", "pattern": "^\\d+$"});
        let validator = validator_options().build(&schema).unwrap();
        assert!(validator.is_valid(&serde_json::json!("123")));
        assert!(!validator.is_valid(&serde_json::json!("\u{663}")));
        assert!(!validator.is_valid(&serde_json::json!("123\n")));
        let instance = serde_json::json!("x");
        let err = validator.iter_errors(&instance).next().unwrap();
        assert!(
            matches!(
                err.kind(),
                jsonschema::error::ValidationErrorKind::Custom { .. }
            ),
            "{:?}",
            err.kind()
        );
    }

    #[test]
    fn full_dates() {
        assert!(is_full_date("0000-02-29"));
        assert!(is_full_date("2024-02-29"));
        assert!(!is_full_date("2023-02-29"));
        assert!(!is_full_date("2023-13-01"));
        assert!(!is_full_date("2023-1-01"));
    }

    #[test]
    fn schemas_compile_and_pattern_is_ecma() {
        let schemas = Schemas::compile().unwrap();
        let record = crate::json::load(
            r#"{"schema":"https://w3id.org/fair-bioheaders/fhr/v0.8.0","schemaVersion":"2.1","genome":"g","version":"1",
               "masking":"not-masked\n"}"#,
            crate::yaml::YamlLimits { nodes: 100, depth: 64, scalar_bytes: 1000 },
        )
        .unwrap()
        .value
        .unwrap();
        let diagnostics = schemas.validate("fhr-2.1.json", "FHR", &record);
        assert!(
            diagnostics
                .iter()
                .any(|d| d.location.json_pointer.as_deref() == Some("/masking")),
            "{diagnostics:#?}"
        );
    }
}
