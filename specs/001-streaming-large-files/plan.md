# Implementation Plan: Stream FASTA/GFA sequence commands with bounded memory

**Branch**: `001-streaming-large-files` | **Spec**: [spec.md](spec.md) | **Issue**: #24

## Summary

Replace whole-file reads in the sequence commands with one chunked line scanner
that reproduces `bytes.splitlines(keepends=True)` (terminators `\n`, `\r`,
`\r\n`) across chunk boundaries. The existing bytes API feeds the same scanner,
so there is one implementation of header detection, checksum-line selection,
and hashing.

## Technical context

Python 3.9+, standard library plus PyYAML and jsonschema (unchanged). Chunks of
1 MiB; FHR header lines capped at 16 MiB in total.

## Design

- `fhr.sequence_parts(chunks, prefix)` yields header lines and other bytes in
  order. Inside the leading header block it works line by line; non-FHR lines
  are passed through in pieces, so long comment lines are never assembled.
  After the first record it stops splitting lines: each chunk is searched for
  `\n` or `\r` followed by the prefix (late header lines), terminators are
  counted for the error's line number, and the chunk is passed through whole.
- Checksum: hash every part as it streams. The root indentation can only
  decrease as header lines arrive, so at most one candidate checksum line can
  stay valid; a digest copy taken before that line excludes it. At the end of
  the header block only the needed digest is kept.
- Validate: one pass collects header lines and the digest, then runs the
  current checks in the current order.
- Strip: stream parts except header lines. Stdout output is pre-scanned so that
  errors still produce no output.
- Combine: pass 1 hashes the generated header plus the stripped input stream;
  pass 2 writes the final header and the stripped input stream.
- Convert/validate metadata from FASTA/GFA: scan without hashing.
- Outputs: temporary file in the destination directory, then `os.replace`,
  keeping the existing mode. Non-regular targets such as `/dev/null` are
  written directly.

## Constitution check

I (spec is contract): no format change; the header cap is an implementation
resource limit. II (exact bytes, one reading): same lines identify and hash
metadata. III (bounded resources): this feature. V: API is additive and every
behaviour change is tested.

## Verification

pytest (including chunk sizes 1-7 against `bytes.splitlines` oracles), ruff,
isort, black, `poetry build` on 3.9 and 3.13; opt-in memory test
(`FHR_MEMORY_TEST=1`) on a 300 MB FASTA; FAIR-bioHeaders-Specification `check_release.py`.
