// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Family predicates outside JSON Schema: container pairing (R17), link
//! schemes (R14 warnings), FASTA record markers (R11 warnings) and FHGFF3
//! native-directive cross-checks (warnings). Ports of
//! `validate_header_family`, `link_scheme_warnings`, `record_marker_warnings`
//! and `cross_check` in the Python reference.

use crate::diagnostics::Code;
use crate::framing::Kind;
use crate::report::Diagnostic;
use crate::value::Value;
use serde_json::Value as Json;

/// R17: whether the header type may ride in this container.
pub fn check_container(kind: Kind, header_type: &str, fht_available: bool) -> Option<Diagnostic> {
    let (name, allowed): (&str, Vec<&str>) = match kind {
        Kind::Fasta if fht_available => ("FASTA", vec!["FHR", "FHP", "FHT"]),
        Kind::Fasta => ("FASTA", vec!["FHR", "FHP"]),
        Kind::Gfa => ("GFA", vec!["FHR"]),
        Kind::Gff3 => ("GFF3", vec!["FHGFF3"]),
    };
    if allowed.contains(&header_type) {
        return None;
    }
    Some(Diagnostic::new(
        Code::R17ContainerMismatch,
        format!("{header_type} metadata is incompatible with {name}; expected {} metadata", allowed.join(" or ")),
    ))
}

const LINK_SCHEMES: [&str; 6] = ["http", "https", "ftp", "urn", "doi", "info"];
const URL_SCHEMES: [&str; 3] = ["http", "https", "ftp"];

/// Python `URI_FORM`: a scheme, a colon, then one or more characters that are not whitespace, C0/C1 controls or bidirectional marks and overrides (U+200E, U+200F, U+202A to U+202E, U+2066 to U+2069); full match.
fn uri_scheme(value: &str) -> Option<String> {
    let colon = value.find(':')?;
    let scheme = &value[..colon];
    let mut chars = scheme.chars();
    if !chars.next().is_some_and(|c| c.is_ascii_alphabetic()) {
        return None;
    }
    if !chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '.' | '-')) {
        return None;
    }
    let rest = &value[colon + 1..];
    if rest.is_empty() {
        return None;
    }
    let bad = |c: char| {
        c.is_whitespace()
            || (c as u32) <= 0x1f
            || (0x7f..=0x9f).contains(&(c as u32))
            || matches!(c as u32, 0x200e | 0x200f | 0x202a..=0x202e | 0x2066..=0x2069)
            || is_py_whitespace(c)
    };
    if rest.chars().any(bad) {
        return None;
    }
    Some(scheme.to_ascii_lowercase())
}

/// Python `\s` for `str` patterns: Unicode whitespace plus \x1c-\x1f.
fn is_py_whitespace(c: char) -> bool {
    c.is_whitespace() || matches!(c as u32, 0x1c..=0x1f | 0x85)
}

fn link_problem(value: &str) -> Option<String> {
    let scheme = uri_scheme(value);
    if let Some(s) = &scheme {
        if LINK_SCHEMES.contains(&s.as_str()) {
            let rest = &value[s.len() + 1..];
            if !URL_SCHEMES.contains(&s.as_str()) {
                return None;
            }
            if rest.starts_with("//") && rest.len() > 2 && rest.as_bytes()[2] != b'/' {
                return None;
            }
        }
    }
    Some(match scheme {
        None => "is not an absolute URI".to_owned(),
        Some(s) if URL_SCHEMES.contains(&s.as_str()) => format!("is not an absolute {s} URL"),
        Some(s) => format!("uses the URI scheme {}", crate::yaml::py_repr(&s)),
    })
}

fn resolve<'a>(mut schema: &'a Json, root: &'a Json) -> &'a Json {
    let mut seen: Vec<String> = Vec::new();
    while let Some(Json::String(reference)) = schema.get("$ref") {
        if !reference.starts_with("#/") || seen.contains(reference) {
            break;
        }
        seen.push(reference.clone());
        match root.pointer(&reference[1..]) {
            Some(target) => schema = target,
            None => break,
        }
    }
    schema
}

fn uri_values(value: &Value, schema: &Json, path: &str, root: &Json, found: &mut Vec<(String, String)>) {
    let schema = resolve(schema, root);
    let Some(map) = schema.as_object() else {
        return;
    };
    if map.get("format").and_then(Json::as_str) == Some("uri") {
        if let Value::String(s) = value {
            found.push((path.to_owned(), s.clone()));
        }
    }
    for keyword in ["allOf", "anyOf", "oneOf"] {
        if let Some(Json::Array(branches)) = map.get(keyword) {
            for branch in branches {
                uri_values(value, branch, path, root, found);
            }
        }
    }
    match value {
        Value::Object(items) => {
            if let Some(Json::Object(properties)) = map.get("properties") {
                for (key, item) in items {
                    if let Some(definition) = properties.get(key) {
                        let child = if path.is_empty() { key.clone() } else { format!("{path}.{key}") };
                        uri_values(item, definition, &child, root, found);
                    }
                }
            }
        }
        Value::Array(items) => {
            if let Some(item_schema @ Json::Object(_)) = map.get("items") {
                for (index, item) in items.iter().enumerate() {
                    uri_values(item, item_schema, &format!("{path}[{index}]"), root, found);
                }
            }
        }
        _ => {}
    }
}

/// R14 warnings for `format: uri` values without an accepted link scheme.
pub fn link_scheme_warnings(record: &Value, schema: &Json) -> Vec<Diagnostic> {
    let mut found = Vec::new();
    uri_values(record, schema, "", schema, &mut found);
    let mut messages: Vec<String> = Vec::new();
    for (path, value) in found {
        if let Some(problem) = link_problem(&value) {
            let message = format!(
                "{path} {problem}; links should use http or https (accepted: {}; docs/FORMAT.md R14)",
                LINK_SCHEMES.join(", ")
            );
            if !messages.contains(&message) {
                messages.push(message);
            }
        }
    }
    messages.into_iter().map(|m| Diagnostic::new(Code::R14LinkScheme, m)).collect()
}

/// R11 warnings for FASTA header lines holding a raw `>` or `@`.
pub fn record_marker_warnings(lines: &[(Vec<u8>, u64)], prefix: &[u8]) -> Vec<Diagnostic> {
    let mut out = Vec::new();
    for (index, (line, number)) in lines.iter().enumerate() {
        let body = &line[prefix.len().min(line.len())..];
        let found: Vec<char> = ['>', '@'].into_iter().filter(|c| body.contains(&(*c as u8))).collect();
        if found.is_empty() {
            continue;
        }
        let raw = found.iter().map(|c| format!("'{c}'")).collect::<Vec<_>>().join(" and ");
        let escaped = found.iter().map(|c| if *c == '>' { "\\x3E" } else { "\\x40" }).collect::<Vec<_>>().join(" and ");
        out.push(
            Diagnostic::new(
                Code::R11RecordMarker,
                format!(
                    "FHR header line {} contains a raw {raw}: kseq-based FASTA readers start a record there; write {escaped} \
                     in a double-quoted value instead (FAIR-bioHeaders-Specification docs/FORMAT.md R11)",
                    index + 1
                ),
            )
            .at_line(*number),
        );
    }
    out
}

fn taxon_id(value: Option<&str>) -> Option<String> {
    let text = value?.trim();
    let text = text.strip_suffix('/').unwrap_or(text);
    let digits: String = text.chars().rev().take_while(|c| c.is_ascii_digit()).collect::<Vec<_>>().into_iter().rev().collect();
    if digits.is_empty() {
        return None;
    }
    let before = &text[..text.len() - digits.len()];
    if before.ends_with("taxonomy:") || before.ends_with('/') || before.ends_with("?id=") || before.ends_with("&id=") {
        Some(digits)
    } else {
        None
    }
}

/// FHGFF3 header vs native directive warnings (never errors).
pub fn directive_warnings(record: &Value, directives: &[(String, String)]) -> Vec<Diagnostic> {
    let get = |name: &str| directives.iter().find(|(n, _)| n == name).map(|(_, v)| v.as_str());
    let mut messages = Vec::new();
    if let (Some(taxon @ Value::Object(_)), Some(species)) = (record.get("taxon"), get("##species")) {
        let uri = taxon.get("uri").and_then(Value::as_str);
        match (taxon_id(uri), taxon_id(Some(species))) {
            (Some(header), Some(native)) if header != native => messages.push(format!(
                "taxon {} (taxonomy ID {header}) differs from ##species {species} (taxonomy ID {native})",
                uri.unwrap_or("None")
            )),
            (Some(_), Some(_)) => {}
            _ => messages.push(format!(
                "taxon not compared with ##species {species} (no NCBI Taxonomy ID found in one of them)"
            )),
        }
    }
    let reference = record.get("genomeReference").filter(|v| matches!(v, Value::Object(_)));
    let mut accession = reference.and_then(|r| r.get("accession")).and_then(Value::as_str).map(str::to_owned);
    if accession.is_none() {
        if let Some(Value::Array(items)) = record.get("derivedFrom") {
            let annotates: Vec<&Value> = items
                .iter()
                .filter(|i| matches!(i, Value::Object(_)) && i.get("relationship").and_then(Value::as_str) == Some("annotates"))
                .collect();
            let with_checksum: Vec<&Value> =
                annotates.iter().copied().filter(|i| i.get("checksum").is_some_and(|c| *c != Value::Null)).collect();
            let candidates = if with_checksum.is_empty() { annotates } else { with_checksum };
            for item in candidates {
                if let Some(name) = item.get("accessionID").and_then(|a| a.get("name")).and_then(Value::as_str) {
                    accession = Some(name.to_owned());
                    break;
                }
            }
        }
    }
    if let (Some(accession), Some(native)) = (accession, get("#!genome-build-accession")) {
        let stripped = strip_accession_prefix(native);
        if stripped != accession {
            messages.push(format!("genome accession {accession} differs from #!genome-build-accession {native}"));
        }
    }
    if let Some(name) = reference.and_then(|r| r.get("assemblyName")).and_then(Value::as_str) {
        for directive in ["##genome-build", "#!genome-build"] {
            if let Some(value) = get(directive) {
                let build = value.split_whitespace().last().unwrap_or("");
                if build != name {
                    messages.push(format!("assemblyName {name} differs from {directive} {value}"));
                }
            }
        }
    }
    messages.into_iter().map(|m| Diagnostic::new(Code::G2DirectiveMismatch, m)).collect()
}

/// `^[A-Za-z][A-Za-z0-9_]*:(?=\S)` removed.
fn strip_accession_prefix(value: &str) -> &str {
    let bytes = value.as_bytes();
    if !bytes.first().is_some_and(u8::is_ascii_alphabetic) {
        return value;
    }
    let end = bytes.iter().position(|b| !(b.is_ascii_alphanumeric() || *b == b'_')).unwrap_or(bytes.len());
    if bytes.get(end) == Some(&b':') && value[end + 1..].chars().next().is_some_and(|c| !c.is_whitespace()) {
        &value[end + 1..]
    } else {
        value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn link_problems() {
        assert_eq!(link_problem("https://example.org/x"), None);
        assert_eq!(link_problem("doi:10.1/x"), None);
        assert_eq!(link_problem("javascript:alert(1)").unwrap(), "uses the URI scheme 'javascript'");
        assert_eq!(link_problem("https:/x").unwrap(), "is not an absolute https URL");
        assert_eq!(link_problem("no scheme").unwrap(), "is not an absolute URI");
    }

    #[test]
    fn taxon_ids() {
        assert_eq!(taxon_id(Some("https://identifiers.org/taxonomy:9606")).as_deref(), Some("9606"));
        assert_eq!(taxon_id(Some("https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606")).as_deref(), Some("9606"));
        assert_eq!(taxon_id(Some("Homo sapiens")), None);
    }
}
