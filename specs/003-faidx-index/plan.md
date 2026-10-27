# Implementation Plan: `bioheaders faidx`

**Branch**: `bioheaders-faidx` | **Spec**: [spec.md](spec.md) | **Issue**: #108

## Summary

A new module `bioheaders/faidx.py` streams the (decompressed) file through
`sequence_parts`, skips the FHR header lines it reports, and feeds every other
byte to a state machine that mirrors htslib's `fai_build_core`, counting
absolute offsets. A small BGZF block reader decompresses BGZF input and records
the `.gzi` entries. `bioheaders faidx` in `cli.py` writes both files with
`write_output`.

## Technical context

Python 3.9+, standard library only (`zlib`, `struct`, `re`). Reads in 1 MiB
chunks (`read_chunks`) or 64 KiB BGZF blocks. Reference: htslib 1.24 `faidx.c`
(`fai_build_core`, `fai_insert_index`, `fai_save`, `fai_read`, `fai_build3_core`)
and `bgzf.c` (`check_header`, `bgzf_read_block`, `bgzf_index_add_block`,
`bgzf_index_dump_hfile`).

## Research

- **Record rules** (`fai_build_core`): bytes are read one at a time through a
  state machine (out of record, name, sequence). The name is the first run of
  non-`isspace` bytes after `>` (leading spaces and tabs skipped; an empty name
  is possible). OFFSET is `bgzf_utell` after the `>` line's `\n`. Each sequence
  line's width counts every byte up to and including `\n` (so `\r` counts) and
  its bases count `isgraph` bytes. The first line sets LINEBASES/LINEWIDTH; a
  wider line is "Different line length"; a narrower line ends the record, after
  which only `>`, `\n` or `\r\n` may follow ("Format error, unexpected X"). A
  blank line also ends the record. A last line without `\n` counts as if it had
  one. Only `\n` ends lines; `\r` is special only between records, where it must
  be followed by `\n`.
- **Records without sequence**: a record is inserted when the next `>` is
  followed by a byte, or at EOF, only if it had a sequence line; otherwise it is
  silently dropped. At EOF it is "File truncated" instead; a name cut by EOF is
  "The last entry ... has no sequence"; a lone final `>` is ignored.
- **Duplicates**: `fai_insert_index` warns and keeps the first.
- **Index lines**: `fai_save` writes `%s\t%llu\t%llu\t%llu\t%llu\n`; `fai_read`
  reads lines into a 64 KiB buffer, which bounds usable names.
- **FASTQ**: a first `@` switches to FASTQ (five columns); not supported here.
- **BGZF**: `check_header` requires `1f 8b 08`, FEXTRA, XLEN 6 and the `BC`
  subfield of length 2; other gzip members set `is_gzip`, and with index building
  enabled reading fails and `fai_build3_core` reports "Cannot index files
  compressed with gzip, please use bgzip". Empty blocks (the EOF marker) are
  skipped. The `.gzi` has one entry per non-empty block read,
  (compressed address, uncompressed address), and the dump writes the count
  minus one and skips the first entry. samtools faidx reads single-threaded.
- **Toolkit reuse**: `sequence_parts` (header block, late-header check, size
  and line limits), `read_chunks`, `write_output`, `_output_is_input`,
  `_stream_path`, `run`. The toolkit has a BGZF writer but no block-level
  reader (`open_input` uses `gzip.GzipFile`, which hides block offsets), so a
  reader is added.
- **Measured** on a 718 MB headed FASTA (5 wrapped chromosomes, one 200 Mb
  unwrapped line): 2.5 s and 35 MB peak RSS plain, 2.7 s and 35 MB as BGZF.

## Design

- `FaiBuilder.feed(data, offset, leading)`: per-state handling with `find` for
  line ends and `bytes.translate` to count `isgraph` bytes. In a record with a
  known width, the lines up to the next `\n>` or `\n\n` are checked at once
  (newline count and positions, no `>` at a line start) and summed in one
  step; irregular lines fall back to line-by-line processing up to that point,
  so work stays linear.
- Leading block: FHR lines are skipped (lines counted for messages); other
  lines go through the state machine with `;` comment lines allowed.
- `build_index(stream)` checks the gzip magic and either reads plain chunks or
  BGZF blocks, returning `.fai` bytes, `.gzi` bytes or None, and warnings.
- CLI: `bioheaders faidx IN [-o FAI] [--gzi GZI]`; regular files only; checks
  outputs differ from the input and each other; warnings as `FHR: warning:`;
  writes `.gzi` then `.fai` atomically only after the whole input is indexed.
  Subcommand appended after `assess` so existing help output is unchanged.

## Constitution check

I: no format or schema change; the spec's "Recommended workarounds" are updated
upstream separately. II: the header block is identified by the same reader as
strip/verify; no bytes are rewritten. III: malformed input fails closed
(including duplicate names); memory is bounded. V: new subcommand only; the
`fhr-*` commands and existing help are unchanged; regression tests added.

## Verification

pytest on Python 3.9 and 3.13 with samtools/bgzip/pysam installed (CI installs
them and sets `FHR_REQUIRE_FAIDX_TOOLS=1` so the comparisons cannot be skipped),
ruff, isort, black, mypy.
