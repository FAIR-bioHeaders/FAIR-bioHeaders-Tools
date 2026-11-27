// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! The exact metadata value tree (Tools#207 section 4).
//!
//! Every number keeps the text it was written as (its *lexeme*) and an exact
//! value: integers are arbitrary precision, decimals keep the exact decimal the
//! source wrote, never a binary64 approximation. Conversions to host types are
//! explicit and report whether they were exact.

use num_bigint::{BigInt, Sign};
use num_traits::{ToPrimitive, Zero};
use std::fmt;

/// Whether a number was written as an integer or as a decimal.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum NumberKind {
    /// An integer literal (decimal or `0x` hexadecimal).
    Int,
    /// A decimal or exponent literal.
    Decimal,
}

/// An exact number: `mantissa * 10^exponent`, plus the source text.
#[derive(Clone, Debug)]
pub struct Number {
    kind: NumberKind,
    lexeme: String,
    mantissa: BigInt,
    exponent: i64,
}

impl PartialEq for Number {
    /// Numbers are equal when they have the same kind and the same exact value
    /// (the lexeme is provenance, not value).
    fn eq(&self, other: &Self) -> bool {
        self.kind == other.kind && self.canonical() == other.canonical()
    }
}

/// A number literal that could not be read.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NumberError;

impl Number {
    /// An integer from decimal digits with an optional sign, or `0x` hex digits
    /// (no sign), as YAML 1.2 core and JSON write them.
    pub fn parse_int(lexeme: &str) -> Result<Number, NumberError> {
        let (negative, body) = split_sign(lexeme);
        let mantissa =
            if let Some(hex) = body.strip_prefix("0x").or_else(|| body.strip_prefix("0X")) {
                if hex.is_empty() || !hex.bytes().all(|b| b.is_ascii_hexdigit()) {
                    return Err(NumberError);
                }
                BigInt::parse_bytes(hex.as_bytes(), 16).ok_or(NumberError)?
            } else if let Some(oct) = body.strip_prefix("0o") {
                if oct.is_empty() || !oct.bytes().all(|b| (b'0'..=b'7').contains(&b)) {
                    return Err(NumberError);
                }
                BigInt::parse_bytes(oct.as_bytes(), 8).ok_or(NumberError)?
            } else {
                if body.is_empty() || !body.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(NumberError);
                }
                BigInt::parse_bytes(body.as_bytes(), 10).ok_or(NumberError)?
            };
        Ok(Number {
            kind: NumberKind::Int,
            lexeme: lexeme.to_owned(),
            mantissa: if negative { -mantissa } else { mantissa },
            exponent: 0,
        })
    }

    /// A decimal: `[-+]?(digits[.digits*] | .digits)([eE][-+]?digits)?`.
    pub fn parse_decimal(lexeme: &str) -> Result<Number, NumberError> {
        let (negative, body) = split_sign(lexeme);
        let (significand, exp_text) = match body.find(['e', 'E']) {
            Some(index) => (&body[..index], Some(&body[index + 1..])),
            None => (body, None),
        };
        let (whole, fraction) = match significand.find('.') {
            Some(index) => (&significand[..index], &significand[index + 1..]),
            None => (significand, ""),
        };
        if whole.is_empty() && fraction.is_empty() {
            return Err(NumberError);
        }
        if !whole.bytes().all(|b| b.is_ascii_digit())
            || !fraction.bytes().all(|b| b.is_ascii_digit())
        {
            return Err(NumberError);
        }
        let mut exponent: i64 = 0;
        if let Some(text) = exp_text {
            let (exp_negative, digits) = split_sign(text);
            if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
                return Err(NumberError);
            }
            // Exponents beyond i64 are absurd; refuse rather than wrap.
            let value: i64 = digits.parse().map_err(|_| NumberError)?;
            exponent = if exp_negative { -value } else { value };
        }
        let digits = format!("{whole}{fraction}");
        let digits = if digits.is_empty() {
            "0".to_owned()
        } else {
            digits
        };
        let mut mantissa = BigInt::parse_bytes(digits.as_bytes(), 10).ok_or(NumberError)?;
        if negative {
            mantissa = -mantissa;
        }
        exponent = exponent
            .checked_sub(fraction.len() as i64)
            .ok_or(NumberError)?;
        let mut number = Number {
            kind: NumberKind::Decimal,
            lexeme: lexeme.to_owned(),
            mantissa,
            exponent,
        };
        number.normalize();
        Ok(number)
    }

    /// A JSON number lexeme (RFC 8259 grammar; kind from the presence of `.`/`e`).
    pub fn parse_json(lexeme: &str) -> Result<Number, NumberError> {
        if lexeme.contains(['.', 'e', 'E']) {
            Number::parse_decimal(lexeme)
        } else {
            Number::parse_int(lexeme)
        }
    }

    /// An exact integer value with the given lexeme.
    pub fn from_bigint(value: BigInt, lexeme: String) -> Number {
        Number {
            kind: NumberKind::Int,
            lexeme,
            mantissa: value,
            exponent: 0,
        }
    }

    fn normalize(&mut self) {
        if self.mantissa.is_zero() {
            self.exponent = 0;
            return;
        }
        let ten = BigInt::from(10);
        while (&self.mantissa % &ten).is_zero() {
            self.mantissa /= &ten;
            self.exponent += 1;
        }
    }

    /// The number's kind.
    pub fn kind(&self) -> NumberKind {
        self.kind
    }

    /// The source text, for example `0x1F` or `1.10`.
    pub fn lexeme(&self) -> &str {
        &self.lexeme
    }

    /// Whether the exact value is a mathematical integer (`1.0` is).
    pub fn is_integral(&self) -> bool {
        self.exponent >= 0
    }

    /// The exact value as an integer, when it is integral and the exponent is
    /// small enough to expand (|exponent| up to 4096 digits).
    pub fn to_bigint(&self) -> Option<BigInt> {
        if self.exponent < 0 || self.exponent > 4096 {
            return if self.mantissa.is_zero() {
                Some(BigInt::zero())
            } else {
                None
            };
        }
        Some(&self.mantissa * BigInt::from(10).pow(self.exponent as u32))
    }

    /// The value as `i64`, or `None` when it is not an integer in range.
    pub fn as_i64(&self) -> Option<i64> {
        self.to_bigint().and_then(|v| v.to_i64())
    }

    /// The nearest binary64 and whether it is exactly the value.
    pub fn as_f64(&self) -> (f64, bool) {
        let text = self.scientific();
        let value: f64 = text.parse().unwrap_or(f64::NAN);
        if !value.is_finite() {
            return (value, false);
        }
        let exact = Number::from_f64_exact(value).is_some_and(|back| back.same_value(self));
        (value, exact)
    }

    /// Whether binary64 rounding of the value overflows to infinity (R13).
    pub fn overflows_binary64(&self) -> bool {
        let text = self.scientific();
        text.parse::<f64>().map(|v| v.is_infinite()).unwrap_or(true)
    }

    fn same_value(&self, other: &Number) -> bool {
        self.mantissa == other.mantissa && self.exponent == other.exponent
    }

    fn from_f64_exact(value: f64) -> Option<Number> {
        // Rust's `{}` prints the shortest text that round-trips, which is not the
        // exact binary value; exactness is decided by printing with enough digits.
        let text = format!("{value:.1100e}");
        let mut number = Number::parse_decimal(&text).ok()?;
        number.normalize();
        Some(number)
    }

    /// `mantissa e exponent`, parseable by `str::parse::<f64>`.
    fn scientific(&self) -> String {
        format!("{}e{}", self.mantissa, self.exponent)
    }

    /// The canonical exact text (Tools#207 section 4): integers as
    /// `-?[0-9]+` with no leading zeros; decimals as the exact value in plain
    /// positional notation with trailing fractional zeros removed (an integral
    /// decimal has no fractional part). Values whose positional form would
    /// exceed 1,000 digits use `<digits>e<exponent>`.
    pub fn canonical(&self) -> String {
        if self.mantissa.is_zero() {
            return "0".to_owned();
        }
        let negative = self.mantissa.sign() == Sign::Minus;
        let digits = self.mantissa.magnitude().to_string();
        let sign = if negative { "-" } else { "" };
        let length = digits.len() as i64;
        if self.exponent >= 0 {
            if length + self.exponent > 1000 {
                return format!("{sign}{digits}e{}", self.exponent);
            }
            return format!("{sign}{digits}{}", "0".repeat(self.exponent as usize));
        }
        let fraction = -self.exponent;
        if fraction > 1000 {
            return format!("{sign}{digits}e{}", self.exponent);
        }
        if fraction >= length {
            format!(
                "{sign}0.{}{digits}",
                "0".repeat((fraction - length) as usize)
            )
        } else {
            let split = (length - fraction) as usize;
            format!("{sign}{}.{}", &digits[..split], &digits[split..])
        }
    }

    /// JSON text of the exact value, valid for `serde_json` with
    /// `arbitrary_precision`: integers as digits, decimals as the canonical
    /// text, keeping a `.0` on integral decimals so JSON Schema sees the
    /// same number (it treats `1.0` as an integer either way).
    pub fn json_text(&self) -> String {
        let canonical = self.canonical();
        match self.kind {
            NumberKind::Int => canonical,
            NumberKind::Decimal if canonical.contains(['.', 'e']) => canonical,
            NumberKind::Decimal => format!("{canonical}.0"),
        }
    }
}

fn split_sign(text: &str) -> (bool, &str) {
    if let Some(rest) = text.strip_prefix('-') {
        (true, rest)
    } else if let Some(rest) = text.strip_prefix('+') {
        (false, rest)
    } else {
        (false, text)
    }
}

impl fmt::Display for Number {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.canonical())
    }
}

/// A metadata value. Object keys keep their source order and are unique.
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    /// `null`, `~` or an empty plain scalar.
    Null,
    /// `true` or `false`.
    Bool(bool),
    /// An exact number.
    Number(Number),
    /// A string.
    String(String),
    /// A sequence.
    Array(Vec<Value>),
    /// A mapping with string keys in source order.
    Object(Vec<(String, Value)>),
}

impl Value {
    /// The value under `key` when this is an object.
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Object(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    /// The string, when this is a string.
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::String(s) => Some(s),
            _ => None,
        }
    }

    /// A `serde_json::Value` with exact number text (for schema evaluation and
    /// the derived JSON view only).
    pub fn to_json(&self) -> serde_json::Value {
        match self {
            Value::Null => serde_json::Value::Null,
            Value::Bool(b) => serde_json::Value::Bool(*b),
            Value::Number(n) => {
                let parsed: serde_json::Number = n
                    .json_text()
                    .parse()
                    .expect("canonical number text is valid JSON");
                serde_json::Value::Number(parsed)
            }
            Value::String(s) => serde_json::Value::String(s.clone()),
            Value::Array(items) => {
                serde_json::Value::Array(items.iter().map(Value::to_json).collect())
            }
            Value::Object(items) => {
                let mut map = serde_json::Map::new();
                for (key, value) in items {
                    map.insert(key.clone(), value.to_json());
                }
                serde_json::Value::Object(map)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn canon(text: &str) -> String {
        Number::parse_json(text).unwrap().canonical()
    }

    #[test]
    fn integers_are_exact() {
        assert_eq!(canon("3100000000"), "3100000000");
        assert_eq!(canon("9007199254740993"), "9007199254740993");
        assert_eq!(canon("-9223372036854775809"), "-9223372036854775809");
        assert_eq!(
            canon("1000000000000000000000000000000"),
            "1000000000000000000000000000000"
        );
        assert_eq!(Number::parse_int("0x1F").unwrap().canonical(), "31");
        assert_eq!(Number::parse_int("+5").unwrap().canonical(), "5");
        assert_eq!(Number::parse_int("0x1F").unwrap().lexeme(), "0x1F");
    }

    #[test]
    fn decimals_are_exact() {
        assert_eq!(canon("1.10"), "1.1");
        assert_eq!(canon("0.1"), "0.1");
        assert_eq!(canon("1.0"), "1");
        assert_eq!(canon("1.5e+3"), "1500");
        assert_eq!(canon("-0.00120"), "-0.0012");
        assert_eq!(Number::parse_decimal(".5").unwrap().canonical(), "0.5");
        assert_eq!(Number::parse_decimal("1.").unwrap().canonical(), "1");
        assert!(Number::parse_decimal("1.0").unwrap().is_integral());
        assert_eq!(Number::parse_decimal("1.0").unwrap().json_text(), "1.0");
    }

    #[test]
    fn binary64_overflow() {
        assert!(
            !Number::parse_decimal("1.7976931348623157e308")
                .unwrap()
                .overflows_binary64()
        );
        assert!(
            Number::parse_decimal("1.8e308")
                .unwrap()
                .overflows_binary64()
        );
        let (value, exact) = Number::parse_decimal("0.1").unwrap().as_f64();
        assert_eq!(value, 0.1);
        assert!(!exact);
        let (value, exact) = Number::parse_decimal("0.5").unwrap().as_f64();
        assert_eq!(value, 0.5);
        assert!(exact);
        assert!(!Number::parse_int("9007199254740993").unwrap().as_f64().1);
        assert!(Number::parse_int("9007199254740992").unwrap().as_f64().1);
    }

    #[test]
    fn i64_fast_path() {
        assert_eq!(
            Number::parse_int("9223372036854775807").unwrap().as_i64(),
            Some(i64::MAX)
        );
        assert_eq!(
            Number::parse_int("9223372036854775808").unwrap().as_i64(),
            None
        );
    }
}
