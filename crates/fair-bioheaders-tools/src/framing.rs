// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Header-block framing of FASTA, GFA and GFF3 bytes (FORMAT.md R1, R7, R10;
//! FHGFF3.md G1), as an incremental push parser.
//!
//! This is a port of `sequence_parts` in the Python reference
//! (`bioheaders/__init__.py`, toolkit 0.13.1): lines are split exactly as
//! `bytes.splitlines(keepends=True)` would split the whole input (a line ends at
//! LF, CRLF or a CR not followed by LF), each FHR line of the leading header
//! block is one header part, every other byte is data, and an end marker is
//! emitted at the first record. Later FHR lines are rejected.

use crate::diagnostics::Code;

const BOM: &[u8] = b"\xef\xbb\xbf";
const GFF3_FASTA: &[u8] = b"##FASTA";
const VERSION_PREFIX: &[u8] = b"##gff-version";

/// The sequence container family being framed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    /// FASTA (FHR, FHP and FHT headers), prefix `;~`.
    Fasta,
    /// GFA, prefix `#~`.
    Gfa,
    /// GFF3 (FHGFF3 headers), prefix `#~` after a `##gff-version 3` line.
    Gff3,
}

impl Kind {
    /// The header line prefix.
    pub fn prefix(self) -> &'static [u8] {
        match self {
            Kind::Fasta => b";~",
            Kind::Gfa | Kind::Gff3 => b"#~",
        }
    }
}

/// A framed part of the input.
#[derive(Debug, PartialEq, Eq)]
pub enum Part<'a> {
    /// One complete header line (prefix and terminator included), with its
    /// 1-based line number.
    Header(&'a [u8], u64),
    /// Other bytes, in order; pieces may split lines.
    Data(&'a [u8]),
    /// The header block ended (first record); emitted once.
    End,
}

/// A framing failure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FramingError {
    /// Registry code.
    pub code: Code,
    /// Python-compatible message.
    pub message: String,
    /// 1-based line, when known.
    pub line: Option<u64>,
}

impl FramingError {
    fn new(code: Code, message: impl Into<String>, line: Option<u64>) -> FramingError {
        FramingError {
            code,
            message: message.into(),
            line,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum LineKind {
    Header,
    Data,
    MaybeBlank,
}

/// Whether `line` (terminator ignored) is a G1 `##gff-version` line.
pub fn is_gff3_version_line(line: &[u8]) -> bool {
    let text = rstrip(line, b"\r\n");
    let Some(rest) = text.strip_prefix(b"##gff-version 3") else {
        return false;
    };
    let mut rest = rest;
    if rest.first() == Some(&b'.') {
        // .x.y with ASCII digits.
        let mut parts = 0;
        while rest.first() == Some(&b'.') && parts < 2 {
            let digits = rest[1..].iter().take_while(|b| b.is_ascii_digit()).count();
            if digits == 0 {
                return false;
            }
            rest = &rest[1 + digits..];
            parts += 1;
        }
        if parts != 2 {
            return false;
        }
    }
    rest.iter().all(|b| *b == b' ' || *b == b'\t')
}

fn rstrip<'a>(data: &'a [u8], chars: &[u8]) -> &'a [u8] {
    let mut end = data.len();
    while end > 0 && chars.contains(&data[end - 1]) {
        end -= 1;
    }
    &data[..end]
}

fn lstrip<'a>(data: &'a [u8], chars: &[u8]) -> &'a [u8] {
    let mut start = 0;
    while start < data.len() && chars.contains(&data[start]) {
        start += 1;
    }
    &data[start..]
}

/// Python `bytes.strip()` whitespace: space, \t, \n, \r, \x0b, \x0c.
fn is_py_space(b: u8) -> bool {
    matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c)
}

/// Count line terminators in `data`, given whether the previous byte was CR
/// (LF, CRLF and a CR not followed by LF each end one line).
pub fn count_lines(data: &[u8], after_cr: bool) -> u64 {
    let mut count = bytecount::count(data, b'\n') as u64;
    if after_cr && data.first() == Some(&b'\n') {
        count -= 1; // the second byte of a CRLF split between chunks
    }
    if memchr::memchr(b'\r', data).is_some() {
        let cr = bytecount::count(data, b'\r') as u64;
        let crlf = memchr::memmem::find_iter(data, b"\r\n").count() as u64;
        count += cr - crlf;
    }
    count
}

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    memchr::memmem::find(haystack, needle)
}

/// The incremental framer.
pub struct Framer {
    kind: Kind,
    prefix: &'static [u8],
    versioned: Option<bool>,
    pending: Vec<u8>,
    started: bool,
    in_header: bool,
    line: Option<LineKind>,
    first_line: Vec<u8>,
    parts: Vec<u8>,
    header_line_number: u64,
    header_size: u64,
    header_count: u64,
    lines: u64,
    tail: Vec<u8>,
    after_cr: bool,
    max_header_bytes: u64,
    max_header_lines: u64,
    total: u64,
    ended: bool,
}

impl Framer {
    /// A framer for `kind` with the header byte and line limits.
    pub fn new(kind: Kind, max_header_bytes: u64, max_header_lines: u64) -> Framer {
        Framer {
            kind,
            prefix: kind.prefix(),
            versioned: None,
            pending: Vec::new(),
            started: false,
            in_header: true,
            line: None,
            first_line: Vec::new(),
            parts: Vec::new(),
            header_line_number: 0,
            header_size: 0,
            header_count: 0,
            lines: 0,
            tail: Vec::new(),
            after_cr: false,
            max_header_bytes,
            max_header_lines,
            total: 0,
            ended: false,
        }
    }

    /// Whether the header block has ended.
    pub fn header_done(&self) -> bool {
        !self.in_header
    }

    /// Total bytes pushed so far.
    pub fn total_bytes(&self) -> u64 {
        self.total
    }

    /// Feed one chunk (`None` marks the end of input).
    pub fn push(
        &mut self,
        chunk: Option<&[u8]>,
        out: &mut dyn FnMut(Part<'_>),
    ) -> Result<(), FramingError> {
        if let Some(c) = chunk {
            self.total += c.len() as u64;
        }
        let is_final = chunk.is_none();
        if self.in_header {
            let data: Vec<u8> = match chunk {
                None => std::mem::take(&mut self.pending),
                Some(c) if !self.pending.is_empty() => {
                    let mut d = std::mem::take(&mut self.pending);
                    d.extend_from_slice(c);
                    d
                }
                Some(c) => c.to_vec(),
            };
            let position = self.header_phase(&data, is_final, out)?;
            if self.in_header {
                self.pending = data[position..].to_vec();
                if is_final && self.line == Some(LineKind::Header) {
                    let line = self.header_line_number;
                    out(Part::Header(&self.parts, line));
                    self.parts.clear();
                }
                return Ok(());
            }
            self.ended = true;
            out(Part::End);
            let rest = &data[position..];
            if !rest.is_empty() {
                self.data_phase(rest, out)?;
            }
            return Ok(());
        }
        match chunk {
            None => Ok(()),
            Some([]) => Ok(()),
            Some(c) => self.data_phase(c, out),
        }
    }

    /// Process header-block bytes; returns the position of unprocessed bytes.
    fn header_phase(
        &mut self,
        data: &[u8],
        is_final: bool,
        out: &mut dyn FnMut(Part<'_>),
    ) -> Result<usize, FramingError> {
        let prefix = self.prefix;
        let fasta = self.kind == Kind::Fasta;
        let gff3 = self.kind == Kind::Gff3;
        if !self.started {
            if data.len() < BOM.len() && !is_final {
                return Ok(0);
            }
            if data.starts_with(BOM) {
                return Err(FramingError::new(
                    Code::R7ByteOrderMark,
                    "FASTA/GFA files must not begin with a UTF-8 byte order mark",
                    Some(1),
                ));
            }
            self.started = true;
        }
        let size = data.len();
        let mut position = 0usize;
        while position < size {
            if self.line.is_none() {
                let rest = &data[position..];
                if rest.len() < prefix.len() && !is_final {
                    break;
                }
                if gff3 && self.lines > 0 {
                    if rest.len() < GFF3_FASTA.len() && !is_final {
                        break;
                    }
                    if rest.starts_with(GFF3_FASTA) {
                        self.in_header = false;
                        break;
                    }
                }
                if rest.starts_with(prefix) {
                    if gff3 && self.versioned != Some(true) {
                        return Err(FramingError::new(
                            Code::G1HeaderBeforeVersion,
                            "FHGFF3 header lines must follow ##gff-version 3 on line 1",
                            Some(self.lines + 1),
                        ));
                    }
                    self.line = Some(LineKind::Header);
                    self.header_line_number = self.lines + 1;
                } else if fasta && rest.starts_with(b">") {
                    self.in_header = false;
                    break;
                } else if fasta || rest.starts_with(b"#") {
                    self.line = Some(LineKind::Data);
                } else {
                    self.line = Some(LineKind::MaybeBlank);
                }
            }
            let next = memchr::memchr2(b'\n', b'\r', &data[position..]).map(|i| i + position);
            let (mut end, mut complete) = match next {
                Some(index) => (index + 1, true),
                None => (size, false),
            };
            if complete && data[end - 1] == b'\r' {
                if end < size {
                    if data[end] == b'\n' {
                        end += 1;
                    }
                } else if !is_final {
                    end -= 1;
                    complete = false;
                }
            }
            let piece = &data[position..end];
            let held_cr = !complete && !is_final && data.get(end) == Some(&b'\r');
            if gff3 && self.lines == 0 && self.versioned.is_none() {
                if self.line == Some(LineKind::Header) {
                    return Err(FramingError::new(
                        Code::G1HeaderBeforeVersion,
                        "FHGFF3 header lines must follow ##gff-version 3 on line 1",
                        Some(1),
                    ));
                }
                self.first_line.extend_from_slice(piece);
                let text = rstrip(&self.first_line, b"\r\n");
                let stripped = lstrip(text, b" \t");
                let looks_version = stripped.starts_with(VERSION_PREFIX);
                let line_done = complete || is_final || held_cr;
                if looks_version && line_done {
                    if !is_gff3_version_line(text) {
                        return Err(FramingError::new(
                            Code::G1BadVersionLine,
                            "GFF3 line 1 must be '##gff-version 3' with an optional .x.y version \
                             (FAIR-bioHeaders-Specification docs/FHGFF3.md G1)",
                            Some(1),
                        ));
                    }
                    self.versioned = Some(true);
                } else if looks_version || (!line_done && VERSION_PREFIX.starts_with(stripped)) {
                    // An unfinished first line may still become a version line.
                } else {
                    self.versioned = Some(false);
                }
                if self.first_line.len() as u64 > self.max_header_bytes {
                    return Err(FramingError::new(
                        Code::G1BadVersionLine,
                        "GFF3 line 1 is too long to be a ##gff-version line",
                        Some(1),
                    ));
                }
            }
            if self.line == Some(LineKind::MaybeBlank) && piece.iter().any(|b| !is_py_space(*b)) {
                self.in_header = false;
                break;
            }
            if self.line == Some(LineKind::Header) {
                self.header_size += piece.len() as u64;
                if self.header_size > self.max_header_bytes {
                    return Err(FramingError::new(
                        Code::LimitHeaderBytes,
                        format!(
                            "FHR header lines exceed the {} MiB size limit",
                            mib(self.max_header_bytes)
                        ),
                        Some(self.header_line_number),
                    ));
                }
                self.parts.extend_from_slice(piece);
            } else if !piece.is_empty() {
                out(Part::Data(piece));
            }
            position = end;
            if !complete {
                break;
            }
            self.lines += 1;
            if self.line == Some(LineKind::Header) {
                self.header_count += 1;
                if self.header_count > self.max_header_lines {
                    return Err(FramingError::new(
                        Code::LimitHeaderLines,
                        format!(
                            "FHR header lines exceed the {} line limit",
                            self.max_header_lines
                        ),
                        Some(self.header_line_number),
                    ));
                }
                out(Part::Header(&self.parts, self.header_line_number));
                self.parts.clear();
            }
            self.line = None;
        }
        Ok(position)
    }

    fn data_phase(
        &mut self,
        chunk: &[u8],
        out: &mut dyn FnMut(Part<'_>),
    ) -> Result<(), FramingError> {
        let prefix = self.prefix;
        let mut late: Option<i64> = None;
        let mut consider = |start: i64| {
            late = Some(match late {
                Some(current) => current.min(start),
                None => start,
            });
        };
        if !self.tail.is_empty() {
            let mut joined = self.tail.clone();
            joined.extend_from_slice(&chunk[..chunk.len().min(prefix.len())]);
            for terminator in *b"\n\r" {
                let mut needle = vec![terminator];
                needle.extend_from_slice(prefix);
                if let Some(found) = find(&joined, &needle) {
                    if found < self.tail.len() {
                        consider(found as i64 - self.tail.len() as i64 + 1);
                    }
                }
            }
        }
        let last = prefix[prefix.len() - 1];
        if chunk.contains(&last) {
            for terminator in *b"\n\r" {
                let mut needle = vec![terminator];
                needle.extend_from_slice(prefix);
                if let Some(found) = find(chunk, &needle) {
                    consider(found as i64 + 1);
                }
            }
        }
        if let Some(start) = late {
            if start > 0 {
                self.lines += count_lines(&chunk[..start as usize], self.after_cr);
            }
            return Err(FramingError::new(
                Code::R10LateHeader,
                format!(
                    "FHR header line after sequence data at line {}",
                    self.lines + 1
                ),
                Some(self.lines + 1),
            ));
        }
        self.lines += count_lines(chunk, self.after_cr);
        self.after_cr = chunk.last() == Some(&b'\r');
        let keep = prefix.len();
        let mut tail = std::mem::take(&mut self.tail);
        tail.extend_from_slice(&chunk[chunk.len().saturating_sub(keep)..]);
        let cut = tail.len().saturating_sub(keep);
        self.tail = tail[cut..].to_vec();
        out(Part::Data(chunk));
        Ok(())
    }
}

fn mib(bytes: u64) -> u64 {
    bytes / (1 << 20)
}

#[cfg(test)]
mod tests {
    use super::*;

    type Framed = (Vec<(Vec<u8>, u64)>, Vec<u8>, bool);

    fn frame(kind: Kind, input: &[u8], chunk: usize) -> Result<Framed, FramingError> {
        let mut framer = Framer::new(kind, 1 << 20, 10_000);
        let mut headers = Vec::new();
        let mut data = Vec::new();
        let mut ended = false;
        let mut sink = |part: Part<'_>| match part {
            Part::Header(line, number) => headers.push((line.to_vec(), number)),
            Part::Data(bytes) => data.extend_from_slice(bytes),
            Part::End => ended = true,
        };
        for piece in input.chunks(chunk.max(1)) {
            framer.push(Some(piece), &mut sink)?;
        }
        framer.push(None, &mut sink)?;
        Ok((headers, data, ended))
    }

    #[test]
    fn fasta_header_block_any_chunking() {
        let input = b";~schema: x\r\n; comment\n;~genome: g\r>seq\nACGT\n";
        for size in 1..input.len() + 1 {
            let (headers, data, ended) = frame(Kind::Fasta, input, size).unwrap();
            assert_eq!(headers.len(), 2, "chunk {size}");
            assert_eq!(headers[0].0, b";~schema: x\r\n");
            assert_eq!(headers[1], (b";~genome: g\r".to_vec(), 3));
            assert_eq!(data, b"; comment\n>seq\nACGT\n");
            assert!(ended);
        }
    }

    #[test]
    fn late_header_is_rejected_with_line() {
        let input = b";~a: 1\n>s\nAC\n;~b: 2\n";
        for size in 1..input.len() + 1 {
            let error = frame(Kind::Fasta, input, size).unwrap_err();
            assert_eq!(error.code, Code::R10LateHeader, "chunk {size}");
            assert_eq!(error.line, Some(4), "chunk {size}");
        }
    }

    #[test]
    fn bom_is_rejected() {
        let error = frame(Kind::Fasta, b"\xef\xbb\xbf;~a: 1\n", 1).unwrap_err();
        assert_eq!(error.code, Code::R7ByteOrderMark);
    }

    #[test]
    fn gfa_blank_lines_and_comments() {
        let (headers, data, _) =
            frame(Kind::Gfa, b"#~a: 1\n\n# c\n#~b: 2\nH\tVN:Z:1.0\n", 4).unwrap();
        assert_eq!(headers.len(), 2);
        assert_eq!(data, b"\n# c\nH\tVN:Z:1.0\n");
    }

    #[test]
    fn gff3_version_line_rules() {
        assert!(is_gff3_version_line(b"##gff-version 3\n"));
        assert!(is_gff3_version_line(b"##gff-version 3.1.26 \t\r\n"));
        assert!(!is_gff3_version_line(b"##gff-version 3.1\n"));
        assert!(!is_gff3_version_line(b"##gff-version 2\n"));
        for size in 1..10 {
            let (headers, _, ended) =
                frame(Kind::Gff3, b"##gff-version 3\n#~a: 1\nchr1\t.\n", size).unwrap();
            assert_eq!(headers.len(), 1);
            assert!(ended);
            assert_eq!(
                frame(Kind::Gff3, b"#~a: 1\n", size).unwrap_err().code,
                Code::G1HeaderBeforeVersion
            );
            assert_eq!(
                frame(Kind::Gff3, b"##gff-version 2\n#~a: 1\n", size)
                    .unwrap_err()
                    .code,
                Code::G1BadVersionLine
            );
        }
    }

    #[test]
    fn count_lines_handles_split_crlf() {
        assert_eq!(count_lines(b"a\r\nb\rc\n", false), 3);
        assert_eq!(count_lines(b"\nx", true), 0);
    }
}
