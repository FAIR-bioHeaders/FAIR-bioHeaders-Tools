// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Checksum coverage (FORMAT.md R1–R5): SHA-512/256 over every byte except the
//! single root-level checksum line, computed in one streaming pass.
//!
//! Port of `SequenceScan` in the Python reference (`bioheaders/cli.py`): every
//! byte is hashed as it streams except the candidate checksum line; the root
//! indentation of header lines can only decrease, so at most one candidate
//! stays valid, and a digest copied before it excludes it.

use crate::framing::{Kind, Part};
use sha2::{Digest, Sha512_256};

/// Bytes of one compared GFF3 directive kept at most (`MAX_DIRECTIVE_BYTES`).
const MAX_DIRECTIVE_BYTES: usize = 64 * 1024;

/// The streaming checksum scan.
#[derive(Clone)]
pub struct Scan {
    prefix: &'static [u8],
    gff3: bool,
    /// Header lines in order, with their line numbers.
    pub header: Vec<(Vec<u8>, u64)>,
    root_indent: Option<usize>,
    matches: u32,
    checksum_line: Option<(Vec<u8>, u64)>,
    digest: Option<Sha512_256>,
    digest_len: u64,
    excluded: Option<(Sha512_256, u64)>,
    in_block: bool,
    /// GFF3: first value of each compared native directive in the leading block.
    pub directives: Vec<(String, String)>,
    directive_line: Option<Vec<u8>>,
    continued_line: bool,
}

/// Directive names compared with an FHGFF3 header.
const GFF3_DIRECTIVES: [&[u8]; 4] = [
    b"##species",
    b"##genome-build",
    b"#!genome-build-accession",
    b"#!genome-build",
];

impl Scan {
    /// A scan for `kind`.
    pub fn new(kind: Kind) -> Scan {
        Scan {
            prefix: kind.prefix(),
            gff3: kind == Kind::Gff3,
            header: Vec::new(),
            root_indent: None,
            matches: 0,
            checksum_line: None,
            digest: Some(Sha512_256::new()),
            digest_len: 0,
            excluded: None,
            in_block: true,
            directives: Vec::new(),
            directive_line: None,
            continued_line: false,
        }
    }

    /// Feed one framed part.
    pub fn part(&mut self, part: &Part<'_>) {
        match part {
            Part::Header(line, number) => self.header_line(line, *number),
            Part::End => {
                self.in_block = false;
                self.digest = None;
                if self.matches != 1 {
                    self.excluded = None;
                }
                if self.gff3 {
                    self.finish_directive();
                }
            }
            Part::Data(data) => {
                if self.in_block && self.gff3 {
                    self.directive_part(data);
                }
                self.update(data);
            }
        }
    }

    /// Call after the last part.
    pub fn finish(&mut self) {
        if self.in_block && self.gff3 {
            self.finish_directive();
        }
    }

    fn update(&mut self, data: &[u8]) {
        if let Some(digest) = self.digest.as_mut() {
            digest.update(data);
            self.digest_len += data.len() as u64;
        }
        if let Some((excluded, len)) = self.excluded.as_mut() {
            excluded.update(data);
            *len += data.len() as u64;
        }
    }

    fn header_line(&mut self, line: &[u8], number: u64) {
        self.header.push((line.to_vec(), number));
        let metadata = &line[self.prefix.len()..];
        let stripped_all = trim_start(metadata, is_py_space);
        let has_text = metadata.iter().any(|b| !is_py_space(*b));
        let directive_like = is_directive_like(trim_start(metadata, |b| b == b' ' || b == b'\t'));
        if has_text && !stripped_all.starts_with(b"#") && !directive_like {
            let indent = metadata.len() - trim_start(metadata, |b| b == b' ' || b == b'\t').len();
            if self.root_indent.is_none_or(|root| indent < root) {
                self.root_indent = Some(indent);
                self.matches = 0;
                self.excluded = None;
            }
            if Some(indent) == self.root_indent && is_checksum_candidate(line, self.prefix) {
                self.matches += 1;
                self.checksum_line = Some((line.to_vec(), number));
                self.excluded = None;
                if self.matches == 1 {
                    if let Some(digest) = self.digest.as_ref() {
                        self.excluded = Some((digest.clone(), self.digest_len));
                    }
                }
                if let Some(digest) = self.digest.as_mut() {
                    digest.update(line);
                    self.digest_len += line.len() as u64;
                }
                return;
            }
        }
        self.update(line);
    }

    /// The number of root-level checksum candidate lines (R2).
    pub fn candidate_count(&self) -> u32 {
        self.matches
    }

    /// The single candidate checksum line and its line number.
    pub fn checksum_line(&self) -> Option<(&[u8], u64)> {
        self.checksum_line.as_ref().map(|(l, n)| (l.as_slice(), *n))
    }

    /// The base64 digest of the covered bytes and their count, when exactly
    /// one candidate line exists.
    pub fn computed(&self) -> Option<(String, u64)> {
        if self.matches != 1 {
            return None;
        }
        let (digest, len) = self.excluded.as_ref()?;
        let bytes = digest.clone().finalize();
        Some((data_encoding::BASE64.encode(&bytes), *len))
    }

    fn directive_part(&mut self, data: &[u8]) {
        if self.continued_line {
            if let Some(line) = self.directive_line.as_mut() {
                if line.len() + data.len() > MAX_DIRECTIVE_BYTES {
                    self.directive_line = None;
                } else {
                    line.extend_from_slice(data);
                }
            }
        } else if data.starts_with(b"#") && !self.recorded_directive_prefix(data) {
            self.directive_line = if data.len() <= MAX_DIRECTIVE_BYTES {
                Some(data.to_vec())
            } else {
                None
            };
        } else {
            self.directive_line = None;
        }
        self.continued_line = !(data.ends_with(b"\n") || data.ends_with(b"\r"));
        if !self.continued_line {
            self.finish_directive();
        }
    }

    fn recorded_directive_prefix(&self, data: &[u8]) -> bool {
        let text = trim_end(data, |b| b == b'\r' || b == b'\n');
        self.directives.iter().any(|(name, _)| {
            let encoded = name.as_bytes();
            text.starts_with(encoded)
                && ((text.len() == encoded.len() && text.len() < data.len())
                    || matches!(text.get(encoded.len()), Some(b' ') | Some(b'\t')))
        })
    }

    fn finish_directive(&mut self) {
        let Some(line) = self.directive_line.take() else {
            return;
        };
        if let Some((name, value)) = gff3_directive(&line) {
            if !self.directives.iter().any(|(n, _)| *n == name) {
                self.directives.push((name, value));
            }
        }
    }
}

/// `(name, value)` for a compared native directive line.
pub fn gff3_directive(line: &[u8]) -> Option<(String, String)> {
    let text = trim_end(line, |b| b == b'\r' || b == b'\n');
    for name in GFF3_DIRECTIVES {
        if text.starts_with(name)
            && (text.len() == name.len() || matches!(text[name.len()], b' ' | b'\t'))
        {
            let value = trim(&text[name.len()..], is_py_space);
            return Some((
                String::from_utf8_lossy(name).into_owned(),
                String::from_utf8_lossy(value).into_owned(),
            ));
        }
    }
    None
}

/// `^<prefix>[ \t]*checksum[ \t]*:` on the full line.
fn is_checksum_candidate(line: &[u8], prefix: &[u8]) -> bool {
    let Some(rest) = line.strip_prefix(prefix) else {
        return false;
    };
    let rest = trim_start(rest, |b| b == b' ' || b == b'\t');
    let Some(rest) = rest.strip_prefix(b"checksum") else {
        return false;
    };
    trim_start(rest, |b| b == b' ' || b == b'\t').starts_with(b":")
}

/// `^(?:%|---(?:[ \t]|$)|\.\.\.(?:[ \t]|$))` with Python `$` semantics.
fn is_directive_like(text: &[u8]) -> bool {
    if text.starts_with(b"%") {
        return true;
    }
    for marker in [&b"---"[..], &b"..."[..]] {
        if let Some(rest) = text.strip_prefix(marker) {
            if rest.is_empty() || rest == b"\n" || rest[0] == b' ' || rest[0] == b'\t' {
                return true;
            }
        }
    }
    false
}

/// The checksum line's value, as R5 requires: optional spaces, `checksum`,
/// spaces, `:`, at least one space, the canonical 44-character value plain or
/// quoted, then spaces only.
pub fn checksum_line_is_strict(line_without_prefix: &[u8]) -> bool {
    let text = trim_end(line_without_prefix, |b| b == b'\r' || b == b'\n');
    let rest = trim_start(text, |b| b == b' ');
    let Some(rest) = rest.strip_prefix(b"checksum") else {
        return false;
    };
    let rest = trim_start(rest, |b| b == b' ');
    let Some(rest) = rest.strip_prefix(b":") else {
        return false;
    };
    let after = trim_start(rest, |b| b == b' ');
    if after.len() == rest.len() {
        return false; // at least one space
    }
    let rest = after;
    let (value, rest) = match rest.first() {
        Some(q @ (b'\'' | b'"')) => {
            let Some(inner) = rest.get(1..45) else {
                return false;
            };
            if rest.get(45) != Some(q) {
                return false;
            }
            (inner, &rest[46..])
        }
        _ => match rest.get(..44) {
            Some(v) => (v, &rest[44..]),
            None => return false,
        },
    };
    is_canonical_base64_digest(value) && rest.iter().all(|b| *b == b' ')
}

/// R4: 44 characters of canonical padded base64 of a 32-byte digest.
pub fn is_canonical_base64_digest(value: &[u8]) -> bool {
    value.len() == 44
        && value[..42]
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || *b == b'+' || *b == b'/')
        && b"AEIMQUYcgkosw048".contains(&value[42])
        && value[43] == b'='
}

/// Base64 of SHA-512/256 of `covered`.
pub fn sha512_256_base64(covered: &[u8]) -> String {
    data_encoding::BASE64.encode(&Sha512_256::digest(covered))
}

fn is_py_space(b: u8) -> bool {
    matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c)
}

fn trim_start(data: &[u8], f: impl Fn(u8) -> bool) -> &[u8] {
    let start = data.iter().position(|b| !f(*b)).unwrap_or(data.len());
    &data[start..]
}

fn trim_end(data: &[u8], f: impl Fn(u8) -> bool) -> &[u8] {
    let end = data.iter().rposition(|b| !f(*b)).map_or(0, |i| i + 1);
    &data[..end]
}

fn trim(data: &[u8], f: impl Fn(u8) -> bool + Copy) -> &[u8] {
    trim_end(trim_start(data, f), f)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::framing::Framer;

    fn scan(kind: Kind, input: &[u8]) -> Scan {
        let mut framer = Framer::new(kind, 1 << 20, 10_000);
        let mut scan = Scan::new(kind);
        for chunk in input.chunks(3) {
            framer.push(Some(chunk), &mut |p| scan.part(&p)).unwrap();
        }
        framer.push(None, &mut |p| scan.part(&p)).unwrap();
        scan.finish();
        scan
    }

    #[test]
    fn excludes_exactly_the_checksum_line() {
        let body = b";~genome: g\n>s\nACGT\n";
        let line = b";~checksum: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n";
        let mut input = line.to_vec();
        input.extend_from_slice(body);
        let s = scan(Kind::Fasta, &input);
        assert_eq!(s.candidate_count(), 1);
        let (computed, len) = s.computed().unwrap();
        assert_eq!(computed, sha512_256_base64(body));
        assert_eq!(len, body.len() as u64);
    }

    #[test]
    fn nested_checksum_is_not_a_candidate() {
        let s = scan(Kind::Fasta, b";~a:\n;~  checksum: x\n;~checksum: y\n>s\n");
        assert_eq!(s.candidate_count(), 1);
        assert_eq!(s.checksum_line().unwrap().1, 3);
    }

    #[test]
    fn strict_line() {
        assert!(checksum_line_is_strict(
            b"checksum: Z1p/siczUlN/N+lDB5Kg6vFRrztGErgLw9H4MfVfZeU=\n"
        ));
        assert!(checksum_line_is_strict(
            b"checksum : 'Z1p/siczUlN/N+lDB5Kg6vFRrztGErgLw9H4MfVfZeU='  \r\n"
        ));
        assert!(!checksum_line_is_strict(
            b"checksum:Z1p/siczUlN/N+lDB5Kg6vFRrztGErgLw9H4MfVfZeU=\n"
        ));
        assert!(!checksum_line_is_strict(
            b"checksum: Z1p/siczUlN/N+lDB5Kg6vFRrztGErgLw9H4MfVfZeU= # c\n"
        ));
        assert!(!checksum_line_is_strict(
            b"checksum: Z1p/siczUlN/N+lDB5Kg6vFRrztGErgLw9H4MfVfZeV=\n"
        ));
    }
}
