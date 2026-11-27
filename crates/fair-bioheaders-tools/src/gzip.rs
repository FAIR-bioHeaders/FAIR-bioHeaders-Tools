// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

//! Strict gzip and BGZF input (FORMAT.md R1): RFC 1952 members decoded one by
//! one over raw DEFLATE, with header CRC (FHCRC), CRC-32 and ISIZE checks.
//! After the final member only NUL padding may follow; any other byte must
//! start a valid member, otherwise the input is invalid. This keeps the
//! outcomes of the Python reference (`_GzipStream`, `bioheaders/cli.py`).

use crate::diagnostics::Code;
use flate2::{Decompress, FlushDecompress, Status};

/// The gzip magic bytes.
pub const MAGIC: [u8; 2] = [0x1f, 0x8b];

const FTEXT: u8 = 1;
const FHCRC: u8 = 2;
const FEXTRA: u8 = 4;
const FNAME: u8 = 8;
const FCOMMENT: u8 = 16;
/// Header fields longer than this are refused (names, comments, extra data).
const MAX_HEADER_FIELD: usize = 1 << 20;

/// A gzip failure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GzipError {
    /// Registry code.
    pub code: Code,
    /// Message.
    pub message: String,
}

fn error(code: Code, message: &str) -> GzipError {
    GzipError {
        code,
        message: format!("Invalid gzip input: {message}"),
    }
}

enum State {
    /// Collecting a member header.
    Header(Vec<u8>),
    /// Inflating member data.
    Data,
    /// Collecting the 8-byte trailer.
    Trailer(Vec<u8>),
    /// A member ended; the next byte decides member or padding.
    Between,
    /// Only NUL bytes may follow.
    Padding,
}

/// The push decoder.
pub struct Decoder {
    state: State,
    inflate: Decompress,
    crc: crc32fast::Hasher,
    size: u32,
    members: u64,
    output: Vec<u8>,
    decompressed: u64,
}

impl Default for Decoder {
    fn default() -> Self {
        Self::new()
    }
}

impl Decoder {
    /// A decoder positioned at the first member header.
    pub fn new() -> Decoder {
        Decoder {
            state: State::Header(Vec::new()),
            inflate: Decompress::new(false),
            crc: crc32fast::Hasher::new(),
            size: 0,
            members: 0,
            output: vec![0; 64 * 1024],
            decompressed: 0,
        }
    }

    /// Decompressed bytes produced so far.
    pub fn decompressed(&self) -> u64 {
        self.decompressed
    }

    /// Feed compressed bytes; decompressed bytes go to `out` in bounded pieces.
    /// `out` may stop the decoder by returning an error value of its own.
    pub fn push<E>(
        &mut self,
        mut input: &[u8],
        out: &mut dyn FnMut(&[u8]) -> Result<(), E>,
    ) -> Result<(), PushError<E>> {
        while !input.is_empty() {
            match &mut self.state {
                State::Header(buffer) => {
                    // Take bytes until the header parses or is known incomplete.
                    let take = input.len();
                    let before = buffer.len();
                    buffer.extend_from_slice(&input[..take]);
                    match parse_header(buffer).map_err(PushError::Gzip)? {
                        Some(length) => {
                            let used = length - before;
                            input = &input[used..];
                            self.inflate.reset(false);
                            self.crc = crc32fast::Hasher::new();
                            self.size = 0;
                            self.state = State::Data;
                        }
                        None => {
                            input = &input[take..];
                        }
                    }
                }
                State::Data => {
                    let before_in = self.inflate.total_in();
                    let before_out = self.inflate.total_out();
                    let status = self
                        .inflate
                        .decompress(input, &mut self.output, FlushDecompress::None)
                        .map_err(|e| {
                            PushError::Gzip(error(
                                Code::R1GzipData,
                                &format!("invalid deflate data ({e})"),
                            ))
                        })?;
                    let consumed = (self.inflate.total_in() - before_in) as usize;
                    let produced = (self.inflate.total_out() - before_out) as usize;
                    input = &input[consumed..];
                    if produced > 0 {
                        let piece = &self.output[..produced];
                        self.crc.update(piece);
                        self.size = self.size.wrapping_add(produced as u32);
                        self.decompressed += produced as u64;
                        out(piece).map_err(PushError::Sink)?;
                    }
                    if status == Status::StreamEnd {
                        self.state = State::Trailer(Vec::with_capacity(8));
                    } else if consumed == 0 && produced == 0 {
                        // Needs more input than this call holds.
                        if input.is_empty() {
                            break;
                        }
                        return Err(PushError::Gzip(error(
                            Code::R1GzipData,
                            "invalid deflate data (no progress)",
                        )));
                    }
                }
                State::Trailer(buffer) => {
                    let take = (8 - buffer.len()).min(input.len());
                    buffer.extend_from_slice(&input[..take]);
                    input = &input[take..];
                    if buffer.len() == 8 {
                        let crc = u32::from_le_bytes(buffer[0..4].try_into().unwrap());
                        let size = u32::from_le_bytes(buffer[4..8].try_into().unwrap());
                        let computed =
                            std::mem::replace(&mut self.crc, crc32fast::Hasher::new()).finalize();
                        if crc != computed {
                            return Err(PushError::Gzip(error(Code::R1GzipCrc, "CRC-32 mismatch")));
                        }
                        if size != self.size {
                            return Err(PushError::Gzip(error(
                                Code::R1GzipLength,
                                "length (ISIZE) mismatch",
                            )));
                        }
                        self.members += 1;
                        self.state = State::Between;
                    }
                }
                State::Between => {
                    if input[0] == 0 {
                        self.state = State::Padding;
                    } else {
                        if input[0] != MAGIC[0] {
                            return Err(PushError::Gzip(error(
                                Code::R1GzipTrailing,
                                "non-gzip data after final member",
                            )));
                        }
                        self.state = State::Header(Vec::new());
                    }
                }
                State::Padding => {
                    if input.iter().any(|b| *b != 0) {
                        return Err(PushError::Gzip(error(
                            Code::R1GzipTrailing,
                            "non-gzip data after final member",
                        )));
                    }
                    input = &[];
                }
            }
        }
        Ok(())
    }

    /// End of compressed input.
    pub fn finish(&mut self) -> Result<(), GzipError> {
        match &self.state {
            State::Between | State::Padding => Ok(()),
            State::Header(buffer) if buffer.is_empty() && self.members == 0 => {
                Err(error(Code::R1GzipTruncated, "truncated gzip member"))
            }
            State::Header(buffer) if buffer.len() >= 2 && buffer[..2] != MAGIC => Err(error(
                Code::R1GzipTrailing,
                "non-gzip data after final member",
            )),
            _ => Err(error(Code::R1GzipTruncated, "truncated gzip member")),
        }
    }
}

/// An error from the decoder or from the sink it feeds.
#[derive(Debug)]
pub enum PushError<E> {
    /// The compressed input is invalid.
    Gzip(GzipError),
    /// The sink stopped decoding.
    Sink(E),
}

/// The header length when `buffer` holds a complete valid header, `None` if
/// more bytes are needed.
fn parse_header(buffer: &[u8]) -> Result<Option<usize>, GzipError> {
    if !buffer.is_empty() && buffer[0] != MAGIC[0] || buffer.len() >= 2 && buffer[1] != MAGIC[1] {
        return Err(error(
            Code::R1GzipTrailing,
            "incorrect header check (not a gzip member)",
        ));
    }
    if buffer.len() >= 3 && buffer[2] != 8 {
        return Err(error(Code::R1GzipHeader, "unknown compression method"));
    }
    if buffer.len() < 10 {
        return Ok(None);
    }
    let flags = buffer[3];
    if flags & 0xe0 != 0 {
        return Err(error(Code::R1GzipHeader, "unknown header flags set"));
    }
    let _ = FTEXT;
    let mut position = 10;
    if flags & FEXTRA != 0 {
        if buffer.len() < position + 2 {
            return Ok(None);
        }
        let length = u16::from_le_bytes([buffer[position], buffer[position + 1]]) as usize;
        position += 2;
        if buffer.len() < position + length {
            return Ok(None);
        }
        position += length;
    }
    for flag in [FNAME, FCOMMENT] {
        if flags & flag != 0 {
            match buffer[position..].iter().position(|b| *b == 0) {
                Some(end) => position += end + 1,
                None => {
                    if buffer.len() - position > MAX_HEADER_FIELD {
                        return Err(error(Code::R1GzipHeader, "header field too long"));
                    }
                    return Ok(None);
                }
            }
        }
    }
    if flags & FHCRC != 0 {
        if buffer.len() < position + 2 {
            return Ok(None);
        }
        let stated = u16::from_le_bytes([buffer[position], buffer[position + 1]]);
        let computed = (crc32fast::hash(&buffer[..position]) & 0xffff) as u16;
        if stated != computed {
            return Err(error(Code::R1GzipHeaderCrc, "header crc mismatch"));
        }
        position += 2;
    }
    Ok(Some(position))
}

#[cfg(test)]
mod tests {
    use super::*;
    use flate2::{Compression, write::GzEncoder};
    use std::io::Write;

    fn gzip(data: &[u8]) -> Vec<u8> {
        let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
        encoder.write_all(data).unwrap();
        encoder.finish().unwrap()
    }

    fn decode(input: &[u8], chunk: usize) -> Result<Vec<u8>, GzipError> {
        let mut decoder = Decoder::new();
        let mut output = Vec::new();
        for piece in input.chunks(chunk) {
            decoder
                .push::<()>(piece, &mut |d| {
                    output.extend_from_slice(d);
                    Ok(())
                })
                .map_err(|e| match e {
                    PushError::Gzip(g) => g,
                    PushError::Sink(()) => unreachable!(),
                })?;
        }
        decoder.finish()?;
        Ok(output)
    }

    #[test]
    fn members_padding_and_trailing_data() {
        let mut two = gzip(b"hello ");
        two.extend(gzip(b"world"));
        for size in [1, 3, 7, 1000] {
            assert_eq!(decode(&two, size).unwrap(), b"hello world");
            let mut padded = two.clone();
            padded.extend([0u8; 9]);
            assert_eq!(decode(&padded, size).unwrap(), b"hello world");
            let mut trailing = two.clone();
            trailing.extend(b"junk");
            assert_eq!(
                decode(&trailing, size).unwrap_err().code,
                Code::R1GzipTrailing
            );
            let truncated = &two[..two.len() - 3];
            assert_eq!(
                decode(truncated, size).unwrap_err().code,
                Code::R1GzipTruncated
            );
        }
    }

    #[test]
    fn crc_mismatch() {
        let mut data = gzip(b"hello");
        let n = data.len();
        data[n - 8] ^= 1;
        assert_eq!(decode(&data, 4).unwrap_err().code, Code::R1GzipCrc);
    }
}
