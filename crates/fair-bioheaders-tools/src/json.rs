// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! JSON metadata files (RFC 8259) read into the exact value tree.
//!
//! Matches the Python reference (`json.loads` with `_unique_object`):
//! duplicate object keys are refused, numbers keep their text, and the
//! non-standard `NaN`/`Infinity` tokens Python accepts are read so that R13
//! (not a syntax error) rejects them. Node and depth limits apply as for YAML.

use crate::diagnostics::Code;
use crate::value::{Number, Value};
use crate::yaml::{LoadError, Loaded, YamlLimits, py_repr};

struct Reader<'a> {
    text: &'a [u8],
    position: usize,
    nodes: u64,
    limits: YamlLimits,
    non_finite: Option<(String, String)>,
}

/// Parse one JSON document.
pub fn load(text: &str, limits: YamlLimits) -> Result<Loaded, LoadError> {
    let mut reader = Reader { text: text.as_bytes(), position: 0, nodes: 0, limits, non_finite: None };
    reader.skip_space();
    let value = reader.value(0, String::new())?;
    reader.skip_space();
    if reader.position != reader.text.len() {
        return Err(reader.error("Extra data"));
    }
    Ok(Loaded { value: Some(value), non_finite: reader.non_finite })
}

impl Reader<'_> {
    fn line(&self) -> u64 {
        1 + self.text[..self.position.min(self.text.len())].iter().filter(|b| **b == b'\n').count() as u64
    }

    fn error(&self, message: &str) -> LoadError {
        LoadError {
            code: Code::JsonSyntax,
            message: format!("{message}: line {} (char {})", self.line(), self.position),
            line: Some(self.line()),
        }
    }

    fn skip_space(&mut self) {
        while self.position < self.text.len() && matches!(self.text[self.position], b' ' | b'\t' | b'\n' | b'\r') {
            self.position += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.text.get(self.position).copied()
    }

    fn value(&mut self, depth: u64, path: String) -> Result<Value, LoadError> {
        self.nodes += 1;
        if self.nodes > self.limits.nodes {
            return Err(LoadError {
                code: Code::LimitYamlNodes,
                message: format!("FHR metadata exceeds {} YAML nodes", self.limits.nodes),
                line: Some(self.line()),
            });
        }
        if depth >= self.limits.depth {
            return Err(LoadError {
                code: Code::LimitYamlDepth,
                message: "metadata is nested too deeply".into(),
                line: Some(self.line()),
            });
        }
        match self.peek() {
            Some(b'{') => self.object(depth, path),
            Some(b'[') => self.array(depth, path),
            Some(b'"') => Ok(Value::String(self.string()?)),
            Some(b't') => self.literal("true", Value::Bool(true)),
            Some(b'f') => self.literal("false", Value::Bool(false)),
            Some(b'n') => self.literal("null", Value::Null),
            Some(b'N') => self.non_finite_literal("NaN", path),
            Some(b'I') => self.non_finite_literal("Infinity", path),
            Some(b'-') if self.text[self.position..].starts_with(b"-Infinity") => {
                self.non_finite_literal("-Infinity", path)
            }
            Some(b'-' | b'0'..=b'9') => self.number(path),
            _ => Err(self.error("Expecting value")),
        }
    }

    fn literal(&mut self, word: &str, value: Value) -> Result<Value, LoadError> {
        if self.text[self.position..].starts_with(word.as_bytes()) {
            self.position += word.len();
            Ok(value)
        } else {
            Err(self.error("Expecting value"))
        }
    }

    fn non_finite_literal(&mut self, word: &str, path: String) -> Result<Value, LoadError> {
        let value = self.literal(word, Value::Null)?;
        if self.non_finite.is_none() {
            self.non_finite = Some((path, word.to_owned()));
        }
        Ok(value)
    }

    fn number(&mut self, path: String) -> Result<Value, LoadError> {
        let start = self.position;
        let t = self.text;
        let mut i = self.position;
        if t.get(i) == Some(&b'-') {
            i += 1;
        }
        match t.get(i) {
            Some(b'0') => i += 1,
            Some(b'1'..=b'9') => {
                while t.get(i).is_some_and(u8::is_ascii_digit) {
                    i += 1;
                }
            }
            _ => return Err(self.error("Expecting value")),
        }
        if t.get(i) == Some(&b'.') && t.get(i + 1).is_some_and(u8::is_ascii_digit) {
            i += 1;
            while t.get(i).is_some_and(u8::is_ascii_digit) {
                i += 1;
            }
        }
        if matches!(t.get(i), Some(b'e' | b'E')) {
            let mut j = i + 1;
            if matches!(t.get(j), Some(b'+' | b'-')) {
                j += 1;
            }
            if t.get(j).is_some_and(u8::is_ascii_digit) {
                while t.get(j).is_some_and(u8::is_ascii_digit) {
                    j += 1;
                }
                i = j;
            }
        }
        self.position = i;
        let lexeme = std::str::from_utf8(&t[start..i]).expect("ASCII");
        let number = Number::parse_json(lexeme).map_err(|_| self.error("Expecting value"))?;
        if number.kind() == crate::value::NumberKind::Decimal && number.overflows_binary64() && self.non_finite.is_none()
        {
            self.non_finite = Some((path, lexeme.to_owned()));
        }
        Ok(Value::Number(number))
    }

    fn string(&mut self) -> Result<String, LoadError> {
        let t = self.text;
        self.position += 1; // opening quote
        let mut out: Vec<u8> = Vec::new();
        loop {
            let Some(&b) = t.get(self.position) else {
                return Err(self.error("Unterminated string starting at"));
            };
            match b {
                b'"' => {
                    self.position += 1;
                    if out.len() as u64 > self.limits.scalar_bytes {
                        return Err(LoadError {
                            code: Code::LimitScalarBytes,
                            message: "a JSON string exceeds the scalar size limit".into(),
                            line: Some(self.line()),
                        });
                    }
                    return String::from_utf8(out).map_err(|_| self.error("Invalid UTF-8"));
                }
                b'\\' => {
                    let escape = t.get(self.position + 1).copied();
                    self.position += 2;
                    match escape {
                        Some(b'"') => out.push(b'"'),
                        Some(b'\\') => out.push(b'\\'),
                        Some(b'/') => out.push(b'/'),
                        Some(b'b') => out.push(8),
                        Some(b'f') => out.push(12),
                        Some(b'n') => out.push(b'\n'),
                        Some(b'r') => out.push(b'\r'),
                        Some(b't') => out.push(b'\t'),
                        Some(b'u') => {
                            let first = self.hex4()?;
                            let code = if (0xd800..0xdc00).contains(&first)
                                && t[self.position..].starts_with(b"\\u")
                            {
                                let save = self.position;
                                self.position += 2;
                                let second = self.hex4()?;
                                if (0xdc00..0xe000).contains(&second) {
                                    0x10000 + ((first - 0xd800) << 10) + (second - 0xdc00)
                                } else {
                                    self.position = save;
                                    first
                                }
                            } else {
                                first
                            };
                            // Python keeps lone surrogates; they cannot be valid
                            // UTF-8, so they are refused here (never valid metadata).
                            let c = char::from_u32(code).ok_or_else(|| self.error("Invalid \\uXXXX escape"))?;
                            let mut buffer = [0u8; 4];
                            out.extend_from_slice(c.encode_utf8(&mut buffer).as_bytes());
                        }
                        _ => return Err(self.error("Invalid \\escape")),
                    }
                }
                0..=0x1f => return Err(self.error("Invalid control character at")),
                _ => {
                    out.push(b);
                    self.position += 1;
                }
            }
        }
    }

    fn hex4(&mut self) -> Result<u32, LoadError> {
        let digits = self.text.get(self.position..self.position + 4).ok_or_else(|| self.error("Invalid \\uXXXX escape"))?;
        let text = std::str::from_utf8(digits).map_err(|_| self.error("Invalid \\uXXXX escape"))?;
        let value = u32::from_str_radix(text, 16).map_err(|_| self.error("Invalid \\uXXXX escape"))?;
        self.position += 4;
        Ok(value)
    }

    fn array(&mut self, depth: u64, path: String) -> Result<Value, LoadError> {
        self.position += 1;
        let mut items = Vec::new();
        self.skip_space();
        if self.peek() == Some(b']') {
            self.position += 1;
            return Ok(Value::Array(items));
        }
        loop {
            self.skip_space();
            let child = format!("{path}[{}]", items.len());
            items.push(self.value(depth + 1, child)?);
            self.skip_space();
            match self.peek() {
                Some(b',') => self.position += 1,
                Some(b']') => {
                    self.position += 1;
                    return Ok(Value::Array(items));
                }
                _ => return Err(self.error("Expecting ',' delimiter")),
            }
        }
    }

    fn object(&mut self, depth: u64, path: String) -> Result<Value, LoadError> {
        self.position += 1;
        let mut items: Vec<(String, Value)> = Vec::new();
        self.skip_space();
        if self.peek() == Some(b'}') {
            self.position += 1;
            return Ok(Value::Object(items));
        }
        loop {
            self.skip_space();
            if self.peek() != Some(b'"') {
                return Err(self.error("Expecting property name enclosed in double quotes"));
            }
            let key = self.string()?;
            self.skip_space();
            if self.peek() != Some(b':') {
                return Err(self.error("Expecting ':' delimiter"));
            }
            self.position += 1;
            self.skip_space();
            let child = if path.is_empty() { key.clone() } else { format!("{path}.{key}") };
            let value = self.value(depth + 1, child)?;
            if items.iter().any(|(k, _)| *k == key) {
                return Err(LoadError {
                    code: Code::R8DuplicateKey,
                    message: format!("Duplicate JSON object key: {}", py_repr(&key)),
                    line: Some(self.line()),
                });
            }
            items.push((key, value));
            self.skip_space();
            match self.peek() {
                Some(b',') => self.position += 1,
                Some(b'}') => {
                    self.position += 1;
                    return Ok(Value::Object(items));
                }
                _ => return Err(self.error("Expecting ',' delimiter")),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIMITS: YamlLimits = YamlLimits { nodes: 20_000, depth: 64, scalar_bytes: 1 << 20 };

    #[test]
    fn reads_exact_numbers_and_rejects_duplicates() {
        let loaded = load(r#"{"a": 18446744073709551617, "b": 1.10, "c": "é😀"}"#, LIMITS).unwrap();
        let v = loaded.value.unwrap();
        assert!(matches!(v.get("a"), Some(Value::Number(n)) if n.canonical() == "18446744073709551617"));
        assert!(matches!(v.get("b"), Some(Value::Number(n)) if n.lexeme() == "1.10"));
        assert_eq!(v.get("c").and_then(Value::as_str), Some("é😀"));
        assert_eq!(load(r#"{"a": 1, "a": 2}"#, LIMITS).unwrap_err().code, Code::R8DuplicateKey);
        assert_eq!(load(r#"{"a": 1} x"#, LIMITS).unwrap_err().code, Code::JsonSyntax);
        let nan = load(r#"{"a": [1, NaN]}"#, LIMITS).unwrap();
        assert_eq!(nan.non_finite.unwrap().0, "a[1]");
        assert_eq!(load(r#"{"a": 1e400}"#, LIMITS).unwrap().non_finite.unwrap().0, "a");
    }
}
