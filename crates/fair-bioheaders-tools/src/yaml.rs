// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Portable YAML metadata (FORMAT.md R8, R12, R13) read from parser events
//! into the exact value tree.
//!
//! The rules follow `_Loader` in the Python reference
//! (`bioheaders/__init__.py`): no directives or explicit document start, no
//! anchors, aliases, tags or merge keys, no duplicate keys, node and depth
//! limits checked before a node is built, and plain scalars typed by the YAML
//! 1.2 core schema only where YAML 1.1 (PyYAML's resolver plus `y`/`n`) reads
//! the same type. Numbers keep their source text.

use crate::diagnostics::Code;
use crate::value::{Number, Value};
use saphyr_parser::{Event, Parser, ScalarStyle};
use std::sync::OnceLock;

/// Limits that apply while loading.
#[derive(Clone, Copy, Debug)]
pub struct YamlLimits {
    /// Maximum nodes (scalars and collections).
    pub nodes: u64,
    /// Maximum depth (the root is depth 0; a node at this depth is refused).
    pub depth: u64,
    /// Maximum bytes of one scalar.
    pub scalar_bytes: u64,
}

/// A load failure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoadError {
    /// Registry code.
    pub code: Code,
    /// Message (Python wording where practical).
    pub message: String,
    /// 1-based line in the YAML text, when known.
    pub line: Option<u64>,
}

fn fail(code: Code, message: impl Into<String>, line: Option<u64>) -> LoadError {
    LoadError {
        code,
        message: message.into(),
        line,
    }
}

/// A successfully loaded document.
#[derive(Debug, Clone)]
pub struct Loaded {
    /// The value; `None` for an empty stream (PyYAML returns `None`).
    pub value: Option<Value>,
    /// Python-style dotted path of the first NaN or infinity, if any (R13 is
    /// decided by the caller, which knows the header type for its message).
    pub non_finite: Option<(String, String)>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Tag {
    Null,
    Bool,
    Int,
    Float,
    Str,
    Merge,
    Value,
}

struct Patterns {
    bool11: regress::Regex,
    float11: regress::Regex,
    int11: regress::Regex,
    null11: regress::Regex,
    timestamp11: regress::Regex,
    null12: regress::Regex,
    bool12: regress::Regex,
    int12: regress::Regex,
    float12: regress::Regex,
}

fn patterns() -> &'static Patterns {
    static PATTERNS: OnceLock<Patterns> = OnceLock::new();
    PATTERNS.get_or_init(|| {
        let r = |p: &str| regress::Regex::new(&format!("^(?:{p})$")).expect("static YAML pattern");
        Patterns {
            bool11: r("yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF"),
            float11: r(concat!(
                "[-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+][0-9]+)?",
                "|\\.[0-9_]+(?:[eE][-+][0-9]+)?",
                "|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*",
                "|[-+]?\\.(?:inf|Inf|INF)",
                "|\\.(?:nan|NaN|NAN)"
            )),
            int11: r(concat!(
                "[-+]?0b[0-1_]+",
                "|[-+]?0[0-7_]+",
                "|[-+]?(?:0|[1-9][0-9_]*)",
                "|[-+]?0x[0-9a-fA-F_]+",
                "|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+"
            )),
            null11: r("~|null|Null|NULL|"),
            timestamp11: r(concat!(
                "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]",
                "|[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?",
                "(?:[Tt]|[ \\t]+)[0-9][0-9]?:[0-9][0-9]:[0-9][0-9]",
                "(?:\\.[0-9]*)?(?:[ \\t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?"
            )),
            null12: r("~|null|Null|NULL|"),
            bool12: r("true|True|TRUE|false|False|FALSE"),
            int12: r("[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+"),
            float12: r(concat!(
                "[-+]?(?:\\.[0-9]+|[0-9]+(?:\\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?",
                "|[-+]?\\.(?:inf|Inf|INF)|\\.(?:nan|NaN|NAN)"
            )),
        }
    })
}

fn matches(re: &regress::Regex, value: &str) -> bool {
    re.find(value).is_some()
}

fn yaml12_tag(value: &str) -> Tag {
    let p = patterns();
    if matches(&p.null12, value) {
        Tag::Null
    } else if matches(&p.bool12, value) {
        Tag::Bool
    } else if matches(&p.int12, value) {
        Tag::Int
    } else if matches(&p.float12, value) {
        Tag::Float
    } else {
        Tag::Str
    }
}

/// PyYAML's implicit resolver (YAML 1.1), first-character dispatch and
/// registration order, plus `y`/`n` booleans; timestamps read as strings.
fn yaml11_tag(value: &str) -> Tag {
    if matches!(value, "y" | "Y" | "n" | "N") {
        return Tag::Bool;
    }
    let p = patterns();
    let first = value.chars().next();
    let in_set = |set: &str| first.is_some_and(|c| set.contains(c));
    if in_set("yYnNtTfFoO") && matches(&p.bool11, value) {
        return Tag::Bool;
    }
    if in_set("-+0123456789.") && matches(&p.float11, value) {
        return Tag::Float;
    }
    if in_set("-+0123456789") && matches(&p.int11, value) {
        return Tag::Int;
    }
    if first == Some('<') && value == "<<" {
        return Tag::Merge;
    }
    if (first.is_none() || in_set("~nN")) && matches(&p.null11, value) {
        return Tag::Null;
    }
    if in_set("0123456789") && matches(&p.timestamp11, value) {
        return Tag::Str; // Dates and times stay strings, as written (R12).
    }
    if first == Some('=') && value == "=" {
        return Tag::Value;
    }
    Tag::Str
}

/// The tag of a plain scalar, or `None` if YAML 1.1 and 1.2 disagree (R12).
fn portable_plain_tag(value: &str) -> Option<Tag> {
    let tag = yaml12_tag(value);
    if tag != yaml11_tag(value) {
        return None;
    }
    if tag == Tag::Int {
        let digits = value.trim_start_matches(['+', '-']);
        let bytes = digits.as_bytes();
        if bytes.len() > 1 && bytes[0] == b'0' && !matches!(bytes[1], b'x' | b'X') {
            return None; // YAML 1.1 reads a leading zero as octal.
        }
    }
    Some(tag)
}

/// Python `repr` of a string, for messages.
pub fn py_repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::new();
    out.push(quote);
    for c in text.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => {
                out.push_str(&format!("\\x{:02x}", c as u32))
            }
            c if (0x80..0xa0).contains(&(c as u32)) => {
                out.push_str(&format!("\\x{:02x}", c as u32))
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// A scalar after resolution, used for keys and values.
#[derive(Clone, Debug)]
enum Scalar {
    Null,
    Bool(bool),
    Number(Number),
    NonFinite,
    Str(String),
}

impl Scalar {
    /// Python equality between constructed keys (1 == 1.0 == True).
    fn py_eq(&self, other: &Scalar) -> bool {
        match (self.numeric(), other.numeric()) {
            (Some(a), Some(b)) => return a == b,
            (Some(_), None) | (None, Some(_)) => return false,
            _ => {}
        }
        match (self, other) {
            (Scalar::Null, Scalar::Null) => true,
            (Scalar::Str(a), Scalar::Str(b)) => a == b,
            _ => false,
        }
    }

    fn numeric(&self) -> Option<String> {
        match self {
            Scalar::Bool(b) => Some(if *b { "1".into() } else { "0".into() }),
            Scalar::Number(n) => Some(n.canonical()),
            _ => None,
        }
    }

    fn py_repr(&self) -> String {
        match self {
            Scalar::Null => "None".into(),
            Scalar::Bool(true) => "True".into(),
            Scalar::Bool(false) => "False".into(),
            Scalar::Number(n) => n.canonical(),
            Scalar::NonFinite => "nan".into(),
            Scalar::Str(s) => py_repr(s),
        }
    }
}

enum Frame {
    Seq {
        items: Vec<Value>,
        path: String,
    },
    Map {
        items: Vec<(String, Value)>,
        keys: Vec<Scalar>,
        pending: Option<Key>,
        path: String,
    },
}

enum Key {
    Str(String),
    Other,
}

struct Builder {
    stack: Vec<Frame>,
    root: Option<Value>,
    non_finite: Option<(String, String)>,
    non_string_key: Option<(bool, u64)>,
}

impl Builder {
    fn child_path(&self) -> String {
        match self.stack.last() {
            None => String::new(),
            Some(Frame::Seq { items, path }) => format!("{path}[{}]", items.len()),
            Some(Frame::Map {
                pending: Some(Key::Str(key)),
                path,
                ..
            }) => {
                if path.is_empty() {
                    key.clone()
                } else {
                    format!("{path}.{key}")
                }
            }
            Some(Frame::Map { path, .. }) => path.clone(),
        }
    }

    fn json_pointer_child(&self) -> String {
        String::new()
    }

    /// Whether the next node is a mapping key.
    fn expecting_key(&self) -> bool {
        matches!(self.stack.last(), Some(Frame::Map { pending: None, .. }))
    }

    fn push_value(&mut self, value: Value) {
        match self.stack.last_mut() {
            None => self.root = Some(value),
            Some(Frame::Seq { items, .. }) => items.push(value),
            Some(Frame::Map { items, pending, .. }) => match pending.take() {
                Some(Key::Str(key)) => items.push((key, value)),
                Some(Key::Other) | None => {}
            },
        }
    }
}

/// Load one YAML document under the portability rules.
pub fn load(text: &str, limits: YamlLimits) -> Result<Loaded, LoadError> {
    let _ = Builder::json_pointer_child;
    let mut builder = Builder {
        stack: Vec::new(),
        root: None,
        non_finite: None,
        non_string_key: None,
    };
    let mut nodes: u64 = 0;
    let mut documents = 0u32;
    let parser = Parser::new_from_str(text);
    for item in parser {
        let (event, span) = item.map_err(|e| {
            fail(
                Code::YamlSyntax,
                e.info().to_owned(),
                Some(e.marker().line() as u64),
            )
        })?;
        let line = Some(span.start.line() as u64);
        let is_node = matches!(
            event,
            Event::Scalar(..)
                | Event::SequenceStart(..)
                | Event::MappingStart(..)
                | Event::Alias(..)
        );
        if is_node {
            nodes += 1;
            if nodes > limits.nodes {
                return Err(fail(
                    Code::LimitYamlNodes,
                    format!("FHR metadata exceeds {} YAML nodes", limits.nodes),
                    line,
                ));
            }
            if builder.stack.len() as u64 >= limits.depth {
                return Err(fail(
                    Code::LimitYamlDepth,
                    "metadata is nested too deeply",
                    line,
                ));
            }
        }
        let is_map = matches!(event, Event::MappingStart(..));
        match event {
            Event::StreamStart | Event::StreamEnd | Event::Nothing | Event::DocumentEnd => {}
            Event::DocumentStart(explicit) => {
                documents += 1;
                if explicit {
                    return Err(fail(
                        Code::R12Directive,
                        "YAML directives and document-start markers are not allowed (R12)",
                        line,
                    ));
                }
                if documents > 1 {
                    return Err(fail(
                        Code::YamlSyntax,
                        "expected a single document in the stream",
                        line,
                    ));
                }
            }
            Event::Alias(_) => {
                return Err(fail(
                    Code::R8AnchorAlias,
                    "YAML anchors and aliases are not allowed in FHR metadata",
                    line,
                ));
            }
            Event::Scalar(value, style, anchor, tag) => {
                if anchor != 0 {
                    return Err(fail(
                        Code::R8AnchorAlias,
                        "YAML anchors and aliases are not allowed in FHR metadata",
                        line,
                    ));
                }
                if let Some(tag) = tag {
                    return Err(fail(
                        Code::R12Tag,
                        format!(
                            "YAML tags such as {}{} are not allowed in FHR metadata",
                            tag.handle, tag.suffix
                        ),
                        line,
                    ));
                }
                if value.len() as u64 > limits.scalar_bytes {
                    return Err(fail(
                        Code::LimitScalarBytes,
                        "a YAML scalar exceeds the scalar size limit",
                        line,
                    ));
                }
                let scalar = resolve(&value, style, line)?;
                if builder.expecting_key() {
                    if let Some(Frame::Map {
                        keys,
                        pending,
                        path,
                        ..
                    }) = builder.stack.last_mut()
                    {
                        if keys.iter().any(|k| k.py_eq(&scalar)) {
                            return Err(fail(
                                Code::R8DuplicateKey,
                                format!("found duplicate key {}", scalar.py_repr()),
                                line,
                            ));
                        }
                        keys.push(scalar.clone());
                        *pending = Some(match scalar {
                            Scalar::Str(s) => Key::Str(s),
                            _ => {
                                if builder.non_string_key.is_none() {
                                    builder.non_string_key =
                                        Some((path.is_empty(), span.start.line() as u64));
                                }
                                Key::Other
                            }
                        });
                    }
                } else {
                    let path = builder.child_path();
                    let value = match scalar {
                        Scalar::Null => Value::Null,
                        Scalar::Bool(b) => Value::Bool(b),
                        Scalar::Number(n) => {
                            if n.kind() == crate::value::NumberKind::Decimal
                                && n.overflows_binary64()
                                && builder.non_finite.is_none()
                            {
                                builder.non_finite = Some((path.clone(), n.lexeme().to_owned()));
                            }
                            Value::Number(n)
                        }
                        Scalar::NonFinite => {
                            if builder.non_finite.is_none() {
                                builder.non_finite = Some((path.clone(), value.to_string()));
                            }
                            Value::Null
                        }
                        Scalar::Str(s) => Value::String(s),
                    };
                    builder.push_value(value);
                }
            }
            Event::SequenceStart(anchor, tag) | Event::MappingStart(anchor, tag) => {
                if anchor != 0 {
                    return Err(fail(
                        Code::R8AnchorAlias,
                        "YAML anchors and aliases are not allowed in FHR metadata",
                        line,
                    ));
                }
                if let Some(tag) = tag {
                    return Err(fail(
                        Code::R12Tag,
                        format!(
                            "YAML tags such as {}{} are not allowed in FHR metadata",
                            tag.handle, tag.suffix
                        ),
                        line,
                    ));
                }
                if builder.expecting_key() {
                    // A collection used as a key: PyYAML refuses unhashable keys.
                    return Err(fail(Code::YamlSyntax, "found unhashable key", line));
                }
                let path = builder.child_path();
                builder.stack.push(if is_map {
                    Frame::Map {
                        items: Vec::new(),
                        keys: Vec::new(),
                        pending: None,
                        path,
                    }
                } else {
                    Frame::Seq {
                        items: Vec::new(),
                        path,
                    }
                });
            }
            Event::SequenceEnd | Event::MappingEnd => {
                let frame = builder.stack.pop().expect("balanced events");
                let value = match frame {
                    Frame::Seq { items, .. } => Value::Array(items),
                    Frame::Map { items, .. } => Value::Object(items),
                };
                builder.push_value(value);
            }
        }
    }
    if let Some((top, line)) = builder.non_string_key {
        let message = if top {
            "FHR metadata must be an object with string keys"
        } else {
            "Metadata object keys must be strings"
        };
        return Err(fail(Code::InputNotObject, message, Some(line)));
    }
    Ok(Loaded {
        value: builder.root,
        non_finite: builder.non_finite,
    })
}

fn resolve(value: &str, style: ScalarStyle, line: Option<u64>) -> Result<Scalar, LoadError> {
    if style != ScalarStyle::Plain {
        return Ok(Scalar::Str(value.to_owned()));
    }
    if value == "<<" {
        return Err(fail(
            Code::R8MergeKey,
            "YAML merge keys are not allowed in FHR metadata",
            line,
        ));
    }
    let Some(tag) = portable_plain_tag(value) else {
        return Err(fail(
            Code::R12NonPortable,
            format!(
                "the plain YAML value {} is read differently by YAML 1.1 and YAML 1.2 readers; quote it",
                py_repr(value)
            ),
            line,
        ));
    };
    Ok(match tag {
        Tag::Null => Scalar::Null,
        Tag::Bool => Scalar::Bool(value.starts_with(['t', 'T'])),
        Tag::Int => Scalar::Number(Number::parse_int(value).map_err(|_| {
            fail(
                Code::YamlSyntax,
                format!("cannot read the integer {}", py_repr(value)),
                line,
            )
        })?),
        Tag::Float => {
            let lower = value.to_ascii_lowercase();
            if lower.ends_with("inf") || lower.ends_with("nan") {
                Scalar::NonFinite
            } else {
                Scalar::Number(Number::parse_decimal(value).map_err(|_| {
                    fail(
                        Code::YamlSyntax,
                        format!("cannot read the number {}", py_repr(value)),
                        line,
                    )
                })?)
            }
        }
        Tag::Str => Scalar::Str(value.to_owned()),
        Tag::Merge | Tag::Value => {
            return Err(fail(
                Code::R12NonPortable,
                format!(
                    "the plain YAML value {} is read differently by YAML 1.1 and YAML 1.2 readers; quote it",
                    py_repr(value)
                ),
                line,
            ));
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIMITS: YamlLimits = YamlLimits {
        nodes: 20_000,
        depth: 64,
        scalar_bytes: 1 << 20,
    };

    fn ok(text: &str) -> Value {
        load(text, LIMITS).unwrap().value.unwrap()
    }

    fn err(text: &str) -> Code {
        load(text, LIMITS).unwrap_err().code
    }

    #[test]
    fn portable_types() {
        let v = ok("a: 1\nb: 1.10\nc: true\nd: ~\ne: 2024-01-01\nf: 0x1F\ng: hello\nh:\n");
        assert_eq!(
            v.get("a"),
            Some(&Value::Number(Number::parse_int("1").unwrap()))
        );
        match v.get("b") {
            Some(Value::Number(n)) => {
                assert_eq!((n.lexeme(), n.canonical().as_str()), ("1.10", "1.1"))
            }
            other => panic!("{other:?}"),
        }
        assert_eq!(v.get("c"), Some(&Value::Bool(true)));
        assert_eq!(v.get("d"), Some(&Value::Null));
        assert_eq!(v.get("e"), Some(&Value::String("2024-01-01".into())));
        assert!(matches!(v.get("f"), Some(Value::Number(n)) if n.canonical() == "31"));
        assert_eq!(v.get("h"), Some(&Value::Null));
    }

    #[test]
    fn non_portable_scalars() {
        for text in [
            "a: yes", "a: on", "a: 012", "a: 1e5", "a: 1_000", "a: 0o17", "a: y", "a: =",
        ] {
            assert_eq!(err(text), Code::R12NonPortable, "{text}");
        }
    }

    #[test]
    fn r8_and_tags() {
        assert_eq!(err("a: 1\na: 2"), Code::R8DuplicateKey);
        assert_eq!(err("a: &x 1\nb: *x"), Code::R8AnchorAlias);
        assert_eq!(err("a: !!str 1"), Code::R12Tag);
        assert_eq!(err("<<: {a: 1}"), Code::R8MergeKey);
        assert_eq!(err("--- \na: 1"), Code::R12Directive);
        assert_eq!(err("%YAML 1.2\n---\na: 1"), Code::R12Directive);
        assert_eq!(err("1: a"), Code::InputNotObject);
    }

    #[test]
    fn non_finite_is_reported_with_path() {
        let loaded = load("a:\n  b: [1, .inf]\n", LIMITS).unwrap();
        assert_eq!(loaded.non_finite.unwrap().0, "a.b[1]");
        let loaded = load("x: 1.8e+308\n", LIMITS).unwrap();
        assert_eq!(loaded.non_finite.unwrap().0, "x");
    }

    #[test]
    fn limits() {
        let deep = format!("{}1{}", "[".repeat(64), "]".repeat(64));
        assert_eq!(err(&deep), Code::LimitYamlDepth);
        let ok_depth = format!("{}1{}", "[".repeat(63), "]".repeat(63));
        assert!(load(&ok_depth, LIMITS).is_ok());
        let small = YamlLimits { nodes: 3, ..LIMITS };
        assert_eq!(
            load("a: 1\nb: 2", small).unwrap_err().code,
            Code::LimitYamlNodes
        );
    }
}
