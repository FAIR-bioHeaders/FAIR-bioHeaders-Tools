# Feature Specification: `bioheaders faidx`, a samtools-compatible index for FASTA files with a header

**Feature Branch**: `bioheaders-faidx`

**Created**: 2026-10-26

**Status**: Draft

**Input**: Issue #108. htslib's `fai_build_core` rejects a FASTA file whose
first line starts with `;` (`[E::fai_build_core] Format error, unexpected ";" at
line 1`), and the htslib maintainers declined to change that
(samtools/htslib#2103, #2106). htslib does use an existing `.fai` (and `.gzi`)
instead of rebuilding it, and the specification's tool survey
(FAIR-bioHeaders-Specification `docs/TOOL_COMPATIBILITY.md`, "Recommended
workarounds") found that region lookups, VEP and JBrowse give the plain-file
results with a header-aware `.fai`. The toolkit should write that index.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Region lookups on an FHR FASTA (Priority: P1)

A user keeps `genome.fhr.fa` (or `genome.fhr.fa.gz`, BGZF) as the single file of
record and wants `samtools faidx genome.fhr.fa chr1:100-200`, pysam
`FastaFile`, bcftools, bedtools, JBrowse or VEP to read it without a stripped
copy.

**Independent Test**: Run `bioheaders faidx` on a headed file, then fetch many
random regions per record with `samtools faidx` and pysam; the sequences equal
those from the stripped file indexed by samtools.

**Acceptance Scenarios**:

1. **Given** an FHR or FHP FASTA, plain or BGZF, **When** `bioheaders faidx` is
   run, **Then** `in.fa.fai` (and `in.fa.gz.gzi`) are written and region
   lookups return the stripped file's sequences.
2. **Given** the same file, **When** `samtools faidx file.fa` is run with no
   region, **Then** it still fails, because samtools rebuilds the index; this is
   documented.

### User Story 2 - Same index as samtools for header-less files (Priority: P1)

**Independent Test**: For a varied set of header-less files (multi-record,
wrapped and unwrapped, CRLF, BGZF, long names with descriptions, a shorter or
unterminated last line, blank lines), `bioheaders faidx` output is
byte-identical to `samtools faidx` output, and both fail on the same malformed
inputs.

### User Story 3 - Clear errors (Priority: P2)

Plain gzip, inconsistent line lengths, duplicate names, empty input, a
header-only file and FASTQ give a one-line `FHR: ...` error, exit 1, and no
output files.

### Edge Cases

- Ordinary `;` comment lines and blank lines in the leading header block; a
  comment line ends at `\r`, `\r\n` or `\n`, as `sequence_parts` splits lines.
- Millions of blank lines or records without sequence.
- A NUL byte in a sequence name.
- CRLF: `\r` is part of the line width, as in samtools; a lone `\r` between
  records is an error, as in samtools.
- `>` at the very end of the file; a record whose `>` line has no terminator.
- Records without sequence (samtools omits them from its index silently).
- Sequence lines longer than the read chunk (unwrapped chromosomes).
- A BGZF file with empty blocks, or plain gzip members after BGZF blocks.
- A sequence name longer than htslib can read back from a `.fai` line.
- Late FHR lines after the first record (already an error in every command).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `bioheaders faidx IN` MUST write `IN.fai`; for BGZF input also
  `IN.gzi`. `-o/--output` sets the `.fai` path and `--gzi` the `.gzi` path
  (BGZF only).
- **FR-002**: The leading header block MUST be identified by `sequence_parts`,
  the reader `strip` and `verify` use, so the skipped FHR lines are exactly the
  ones `strip` removes; its size and line limits apply.
- **FR-003**: All later bytes MUST be indexed with the rules of htslib 1.24
  `fai_build_core`: NAME is the first whitespace-delimited word after `>`;
  LENGTH counts `isgraph` bytes; OFFSET is the byte offset of the first base
  in the decompressed original file, header included; LINEBASES and LINEWIDTH
  come from the first sequence line; a longer line is an error, a shorter line
  ends the record; a blank line ends the record; a last line without a
  terminator counts as terminated.
- **FR-004**: For input without a header, the `.fai` and `.gzi` MUST be
  byte-identical to `samtools faidx` output, and every input samtools rejects
  MUST be rejected, except that `;` comment and blank lines before the first
  record are allowed (see FR-002). A name ends at its first NUL byte, as in
  htslib. The deliberate differences on input samtools accepts: duplicate names
  and names over 64 KiB are errors, a BGZF block with a wrong ISIZE is an error
  (htslib ignores the field), and plain gzip data after BGZF blocks is an error
  (htslib silently drops the records in it).
- **FR-005**: The `.gzi` MUST use htslib's format: a little-endian uint64 count,
  then (compressed offset, uncompressed offset) uint64 pairs for every
  non-empty BGZF block after the first, as `bgzf_index_dump` writes.
- **FR-006**: Gzip input that is not BGZF MUST fail with "Cannot index files
  compressed with gzip, please use bgzip". Corrupt BGZF blocks (header, size,
  CRC-32, length) MUST fail.
- **FR-007**: Memory MUST stay bounded independent of sequence length (1 MiB
  reads, 64 KiB BGZF blocks, no whole lines held); only the index itself (the
  `.fai` bytes in one buffer, 16 bytes of `.gzi` per BGZF block) and the set of
  names for the duplicate check grow, with the number of records and blocks,
  comparable to samtools. Warnings about records without sequence are capped
  (the first 10, then one line with the remaining count), and runs of blank
  lines are skipped in bulk.
- **FR-008**: Outputs MUST be written atomically (`write_output`); an output
  path equal to the input, or `.fai` equal to `.gzi`, MUST be refused, and so
  MUST `--gzi -` (the `.gzi` is binary and is read from a file). On error no
  output is written: both temporary files are written before either replaces
  its destination, so a failure to write the `.fai` leaves no new `.gzi`.
- **FR-009**: Input MUST be a regular file (an index of stdin or a pipe cannot
  be used); FASTQ MUST give a clear error.
- **FR-010**: The header is not parsed or validated; `bioheaders verify` does
  that. Files without a header are indexed too.

## Clarifications

### Session 2026-10-26

Resolved from the issue's acceptance list and htslib's behaviour:

- Q: Duplicate sequence names? → A: An error. htslib warns, keeps the first and
  makes the later records unreachable; the constitution (III) asks for fail
  closed on ambiguous input. The other differences in exit status from samtools
  on input samtools accepts are listed in FR-004.
- Q: Records with no sequence? → A: Omitted, as htslib does (otherwise the index
  differs from samtools'), with a warning on stderr.
- Q: FASTQ? → A: Not supported: FAIR-bioHeaders defines no FASTQ header. A clear
  error at the first `@` record.
- Q: Ordinary `;` comments in the leading block? → A: Skipped with the header,
  as they belong to the block `strip` and `verify` treat as the header; samtools
  would reject them, so this is a superset of samtools' input.
- Q: Names too long for a `.fai` line (htslib reads 64 KiB lines)? → A: An
  error, since htslib could not read the index back.
- Q: stdin? → A: Not supported (FR-009).
- Q: `--verify` (optional in the issue)? → A: Not in this feature; run
  `bioheaders verify` before indexing. Can be added later.

## Key Entities

- **`.fai` record**: `NAME\tLENGTH\tOFFSET\tLINEBASES\tLINEWIDTH\n`.
- **`.gzi`**: uint64 count, then uint64 (compressed, uncompressed) offset pairs.

## Success Criteria *(mandatory)*

- **SC-001**: Byte-identical `.fai`/`.gzi` to samtools 1.24 over a generated set
  of at least 200 header-less files, and the same accept/reject decision.
- **SC-002**: Region lookups through samtools and pysam on headed files (FHR
  and FHP, plain and BGZF) equal the stripped file's for 50+ random regions per
  record.
- **SC-003**: Peak memory independent of sequence length; existing tests, ruff,
  isort, black and mypy pass on Python 3.9 and 3.13.

## Assumptions

- samtools/htslib 1.24 is the reference; the `.fai` format has been stable since
  htslib 1.0. Tests that need samtools or pysam are skipped when they are not
  installed; CI installs them. CI tests against Ubuntu's packaged samtools
  (1.19 on the current runners) and the comparisons were also run locally
  against samtools 1.24.
- The specification's "Recommended workarounds" section is updated in a separate
  FAIR-bioHeaders-Specification PR.
