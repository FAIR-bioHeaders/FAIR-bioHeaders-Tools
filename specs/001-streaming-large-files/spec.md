# Feature Specification: Stream FASTA/GFA sequence commands with bounded memory

**Feature Branch**: `001-streaming-large-files`

**Created**: 2026-10-08

**Status**: Draft

**Input**: Review finding for FAIR-bioHeaders-Specification#29 (decision 5): "Sequence helpers
currently read entire files into memory; consider large-assembly suitability
separately."

## Background

At converter 0.3.0, the sequence commands read the whole file into memory, and
validation reads it twice (text and bytes). Measured with `/usr/bin/time -f %M`
on a 305 MB FASTA: combine and strip peak at about 1.5 GB, validate and convert at
about 0.9 GB, roughly 5x the input. A 3 GB human assembly would need about 15 GB.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate a large assembly (Priority: P1)

A curator runs `fhr-fasta-validate` or `fhr-gfa-validate` on a chromosome-scale
assembly on an ordinary workstation or a small cluster node.

**Why this priority**: Validation is the most frequent operation, and it runs on
downloaded files that may be any size.

**Independent Test**: Validate a generated 2 GB FASTA and assert the result and
checksum match the 0.3.0 implementation while peak RSS stays below the limit in
SC-001.

**Acceptance Scenarios**:

1. **Given** a valid 2 GB FHR FASTA, **When** it is validated, **Then** it passes
   with the same checksum as 0.3.0 and peak memory stays bounded.
2. **Given** the same file with one sequence byte changed, **When** it is
   validated, **Then** it fails with a nonzero exit.

---

### User Story 2 - Combine and strip large assemblies (Priority: P2)

A pipeline attaches metadata to, or removes it from, a large FASTA/GFA.

**Why this priority**: Combine and strip have the highest peak today (about 5x).

**Independent Test**: `strip(combine(x)) == x` byte for byte on a 2 GB input,
under the memory limit.

**Acceptance Scenarios**:

1. **Given** metadata and a 2 GB payload, **When** combined, **Then** the output
   is byte-identical to 0.3.0 output and validates.
2. **Given** the combined file, **When** stripped, **Then** the payload is
   byte-identical to the original.

---

### User Story 3 - Convert header metadata from a large file (Priority: P3)

`fhr-convert` extracts metadata from a large FASTA/GFA to JSON, YAML, or HTML.

**Independent Test**: Convert a 2 GB FHR FASTA to JSON under the memory limit.

**Acceptance Scenarios**:

1. **Given** a 2 GB FHR FASTA, **When** converted to JSON, **Then** the JSON
   matches 0.3.0 output.

### Edge Cases

- `\r\n` split across a read-chunk boundary must count as one line terminator.
- Lone `\r`, mixed endings, and no final newline hash exactly as in 0.3.0.
- A very long single sequence line (unwrapped chromosome) must not be held whole.
- A header far larger than normal must hit a size cap with a clear error rather
  than exhausting memory.
- FHR lines after sequence data are invalid, because FHR lines must form the
  leading header block. Header parsing can finish at the first record line, but
  the remaining stream must still be checked for late `;~`/`#~` lines.
- Input from a pipe or stdin, where a second pass is impossible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Checksums MUST be byte-identical to 0.3.0 for every input that 0.3.0
  accepts, including every regression test fixture.
- **FR-002**: Validate MUST read the input once, feeding every non-checksum line
  to SHA-512/256 as it streams.
- **FR-003**: Only `;~`/`#~` header lines MAY be collected for YAML parsing, subject
  to a documented size cap.
- **FR-004**: Line splitting MUST match `bytes.splitlines` semantics used by 0.3.0
  for the terminators the specification recognizes, across chunk boundaries.
- **FR-005**: Strip MUST stream payload lines to output without buffering them.
- **FR-006**: Combine MUST produce output identical to 0.3.0. It MAY use two passes
  over a seekable input (hash then write) [NEEDS CLARIFICATION: is a temporary
  file acceptable for non-seekable input, or should combine require a path?].
- **FR-007**: Outputs MUST be written atomically (temporary file then rename) so a
  failure never leaves a partial file at the destination.
- **FR-008**: The public Python API (`fhr` methods and `fhr.cli.checksum`) MUST
  keep working for in-memory bytes; streaming entry points are additive.
- **FR-009**: Error messages and exit codes MUST be unchanged except where a size
  cap is newly enforced.

### Key Entities

- **Line stream**: exact byte lines with their terminators, as hashed.
- **Header block**: the collected `;~`/`#~` lines that are parsed as YAML.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Peak RSS for validate, strip, combine, and convert stays under
  256 MB regardless of input size (header size excluded).
- **SC-002**: Throughput on a 2 GB file is no worse than 0.3.0.
- **SC-003**: All existing tests plus new chunk-boundary tests pass on Python 3.9
  and 3.13.

## Assumptions

- Inputs are files on local or network storage; compressed (`.gz`) input is out
  of scope for this feature.
- The header is small relative to the sequence; a cap in the low megabytes is
  acceptable.
- Builds on header parsing that identifies header lines from the same byte lines
  that are hashed, as docs/FORMAT.md requires.
