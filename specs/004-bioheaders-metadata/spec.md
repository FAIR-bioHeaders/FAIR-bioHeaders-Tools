# Feature Specification: `bioheaders metadata`, schema-validated FHR metadata from typed fields

**Feature Branch**: `004-bioheaders-metadata`

**Created**: 2026-11-16

**Status**: Draft

**Input**: Issue #171 (Adam Wright owns it; David's recommendations on the same
issue). Galaxy and Nextflow can't build FHR metadata cleanly from workflow
parameters with existing tools: there is no escaping, no validation before
`combine`, and no assembly statistics. The toolkit needs a command that
writes **schema-validated** FAIR-bioHeaders metadata from typed command-line
fields and can compute `vitalStats` from the FASTA. It must be useful on its
own (standalone use, then `bioheaders combine`), and later back a fifth Galaxy
tool and replace the pipeline-local helper in nf-core/genomeassembler#250.

## Clarifications

### Session 2026-11-16

Decisions recorded from the #171 brief (Adam) and David's recommendations on
#171. The command implements an existing contract; it adds no schema field.

- Q: Name? → A: `bioheaders metadata` (David, #171 Q2: it names the output
  more clearly than `new`).
- Q: Which header types? → A: FHR only for now. `--type` takes `fhr`
  (default); `fhp` and `fhgff3` are recognized and refused with a clear
  error, so they can be added later without breaking the command line.
- Q: Which contract? → A: the toolkit's current released FHR contract: FHR
  `schemaVersion` `"2.1"` of specification v0.6.0, cited as
  `https://w3id.org/fair-bioheaders/fhr/v0.6.0`. Both are derived from the
  bundled registry (`bioheaders/schemas/bundled.json`) and pinned by a test.
- Q: `dateCreated` default? → A: **none; `--date-created` is required.**
  David's "Additional correction: creation date" on #171: the contract defines
  `dateCreated` as the date the assembly was created, so defaulting to the
  export date would invent a required value. The value must be a real ISO
  date (`YYYY-MM-DD`).
- Q: Required values? → A: never invented. Every field the schema requires that
  the user supplies (`genome`, `taxon` name and id, `version`,
  `metadataAuthor`, `assemblyAuthor`, `dateCreated`, `masking`) must be given;
  if any is missing, the command lists all of them and exits non-zero.
  `masking` has no default either (David, #171 Q3).
- Q: Checksum? → A: the standalone output has **no `checksum`**. A checksum
  covers file bytes, and a metadata document has none; writing a placeholder
  would manufacture a value that looks like a checksum (David, #171 Q2: "Never
  manufacture a placeholder checksum"). `combine` already computes and inserts
  the checksum of metadata without one. The command validates the record
  against the full schema with only the `checksum` requirement set aside (it
  substitutes a syntactic stand-in in memory, as `combine` does, and never
  writes it). `bioheaders validate metadata.yaml` therefore reports the missing
  checksum; this is documented as pre-combine metadata.
- Q: Contig versus scaffold? → A: the schema and FAIR-bioHeaders-Specification
  `docs/TERMS.md`/`docs/FORMAT.md` say `N50`, `L50`, `N90`, `L90` and
  `numberContigs` are contig statistics and the `scaffold*` fields and
  `numberScaffolds` scaffold statistics, but define no gap rule. The command
  states its rule explicitly: every FASTA record with at least one base is one
  scaffold (records without bases are skipped with a warning); contigs are
  the maximal runs of non-`N` bases inside a scaffold, split at every run of one
  or more `N`/`n`; leading and trailing `N` runs belong to no contig. Record
  counts are never reported as contig counts (David, #171 Q2).
- Q: Which "assembly length" do the contig N/L statistics use? → A: the
  schema says N50/L50/N90/L90 are contig statistics "at 50 (90) percent of the
  assembly length" without saying whether gaps count. For contig statistics the
  command reads it as the ungapped assembly length, the sum of contig lengths
  (the usual convention of assembly-statistics tools, and the only reading
  under which contig N90 always exists); scaffold statistics use
  `totalBasePairs`. This is stated in the README and should be clarified in the
  specification's term definitions (follow-up).
- Q: Reusing existing statistics (gfastats)? → A: `--stat KEY=VALUE` sets a
  `vitalStats` field directly (for example from gfastats output that describes
  the exact assembly), and is the only way to give `readTechnology`. A key the
  command also computes with `--stats-from` is refused rather than overriding.
- Q: Assembly software? → A: only what the user passes (`--assembly-software
  NAME=VERSION[=URI]`); no prefilled tool list (David, #171 Q5).
- Q: YAML safety? → A: YAML output applies R11 (`>` and `@` in double-quoted
  scalars as `\x3E`/`\x40`), R12 (strings either YAML version would read as
  another type are quoted) and R13 (finite numbers only), so it can be embedded
  as header lines unchanged. JSON output holds the real characters.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Write valid metadata from typed fields (Priority: P1)

A person or a workflow step passes the genome name, taxon, version, authors,
creation date and masking state as options and gets a YAML (or JSON) metadata
file that the bundled FHR schema accepts.

**Independent Test**: run the command with every required option; the output
reads back as the same values, validates (with the checksum set aside), and
`combine` + `verify` succeed on it.

**Acceptance Scenarios**:

1. **Given** all required options, **When** `bioheaders metadata ... -o m.yaml`
   runs, **Then** `m.yaml` holds the record with the w3id `schema` URL and
   `schemaVersion: '2.1'`, no `checksum`, and exit status 0.
2. **Given** a missing `--version` and `--assembly-author`, **When** the command
   runs, **Then** it writes nothing, names both options, and exits non-zero.
3. **Given** `--taxon-id 96O6`, an author with a malformed ORCID, an unknown
   masking value or a date `2026-02-30`, **Then** each is refused with a message
   naming the option.

### User Story 2 - Compute vitalStats from the FASTA (Priority: P1)

**Independent Test**: on a small hand-computed FASTA (plain, gzip and BGZF, with
and without an FHR header) the statistics equal the hand-computed values.

**Acceptance Scenarios**:

1. **Given** `--stats-from genome.fa.gz`, **Then** `vitalStats` holds
   `totalBasePairs`, `numberScaffolds`, `numberContigs`, contig `N50`/`L50`/
   `N90`/`L90`, `scaffoldN50`/`scaffoldL50`/`scaffoldN90`/`scaffoldL90` and
   `gcContent`.
2. **Given** an all-`N` FASTA, **Then** `numberContigs` is 0, the contig N/L
   statistics and `gcContent` are omitted, and the scaffold statistics are
   written.
3. **Given** an empty or header-only FASTA, or bytes that are not nucleotide
   letters, **Then** the command fails with a clear error.

### User Story 3 - Metadata, combine, verify (Priority: P1)

**Independent Test**: `metadata -o m.yaml`, then `combine m.yaml genome.fa`,
then `verify` succeeds, and `strip` returns the original FASTA bytes.

### Edge Cases

- Hostile values: quotes, newlines, `>`, `@`, `: `, `#`, `- `, `{}`, `yes`,
  `010`, `.nan` in names and free text. Control and line-break characters are
  refused; the rest round-trip exactly through YAML, JSON and FASTA headers.
- Repeated options build arrays in the order given; duplicate `--extra` keys are
  refused.
- `x-` keys must match R15; values are strings.
- URI fields must use a scheme R14 accepts (`http`, `https`, `ftp`, `urn:`,
  `doi:`, `info:`); others are refused (stricter than the schema, as a writer).
- Huge FASTA: streamed in chunks; memory grows only with the number of contigs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `bioheaders metadata` MUST write FHR metadata built only from
  supplied options and, with `--stats-from`, statistics computed from a FASTA.
- **FR-002**: Options MUST map to `fhr-2.1.json` fields exactly: `--genome`,
  `--genome-synonym`*, `--taxon-name`, `--taxon-id` (`taxon.uri`
  `https://identifiers.org/taxonomy:<id>`), `--version`, `--metadata-author`*,
  `--assembly-author`* (`Name` or `Name <https://orcid.org/…>`),
  `--date-created`, `--masking`, `--instrument`*, `--assembly-software`*
  (`NAME=VERSION[=URI]`), `--assembly-protocol`, `--documentation`,
  `--accession` and `--accession-url` (`accessionID`), `--identifier`*,
  `--reuse-conditions`, `--related-link`*, `--voucher-specimen`,
  `--scholarly-article`, `--funding`, `--seqcol-id`, `--stat`*, `--extra`*
  (* repeatable).
- **FR-003**: Missing required values MUST be reported together, with exit 1.
- **FR-004**: The record MUST be validated against the bundled schema (checksum
  requirement set aside) before anything is written; failure exits non-zero and
  leaves no output file.
- **FR-005**: `--stats-from` MUST stream plain, gzip or BGZF FASTA (or `-`),
  ignore a leading FAIR-bioHeaders header and ordinary `;` comment lines, and
  compute the statistics defined in plan.md.
- **FR-006**: Output MUST be YAML (default) or JSON (`--format`), to stdout or
  `-o` (written atomically).
- **FR-007**: `--type fhp|fhgff3` MUST fail with a "not supported yet" error.

### Key Entities

- **FHR record**: the metadata object of `fhr-2.1.json`, without `checksum`.
- **Scaffold**: one FASTA record with at least one base. **Contig**: a maximal run of non-`N` bases in
  a scaffold.

## Success Criteria *(mandatory)*

- **SC-001**: `metadata → combine → verify` succeeds for FASTA, gzip and BGZF.
- **SC-002**: statistics equal hand-computed values on the test FASTA.
- **SC-003**: a 1 GB FASTA is processed with memory bounded by the contig count
  (no whole-file buffering).
- **SC-004**: the full test suite, ruff, isort, black and mypy pass.

## Assumptions

- Extension values from the command line are strings.
- `nameType` for authors is not set by this command (a later option can add it).
- Galaxy wrapper and nf-core module changes are separate work.
