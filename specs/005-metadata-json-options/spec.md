# Feature Specification: `bioheaders metadata --json`, metadata options from a JSON document

**Feature Branch**: `005-metadata-json-options`

**Created**: 2026-11-19

**Status**: Draft

**Input**: Issue #197 (Adam Wright). The Galaxy metadata tool
(`galaxy/tools/fair_bioheaders/fair_bioheaders_metadata.{xml,py}`, #195) reads
the tool's form values from a Galaxy inputs configfile (JSON) and ships a
helper script that turns them into `bioheaders metadata` arguments and runs
the command without a shell. In galaxyproject/tools-iuc#8980 the IUC reviewer
suggested this belongs upstream as a `--json` option, so that the wrapper can
call the installed command directly and ship no script. Nextflow and other
pipelines that already hold metadata as JSON benefit too. Proposed for toolkit
0.13.0 (release contents not yet agreed with David; draft #200 also targets a
proposed 0.13.0 and is separate work).

This feature adds an input path to an existing command. It adds no FHR field,
changes no schema and is **not a schema addition**: the record written is the
one `bioheaders metadata` already writes from command-line options
(specs/004-bioheaders-metadata).

## Clarifications

### Session 2026-11-19

Answers from Adam Wright on #197 (the recommended option in each case).

- Q: Metadata options given on the command line together with `--json`? → A:
  **refused.** Only `-o`/`--output` and `--format` may accompany `--json`; any
  metadata option (including `--type`, `--stats-from`, `--stat`, `--extra`)
  given with it is an error naming the option. One source of truth, no
  precedence rules.
- Q: JSON key names? → A: **the command-line option names without the leading
  dashes** (`"genome"`, `"date-created"`, `"taxon-id"`, `"stats-from"`,
  `"assembly-author"`, ...). The mapping to the flags is one to one, error
  messages already name these options, and the document cannot be mistaken
  for an FHR record.
- Q: JSON only, or YAML too? → A: **JSON only.** It is what Galaxy configfiles
  and Nextflow produce; YAML users have the flags.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Write metadata from a JSON options document (Priority: P1)

A pipeline step (Nextflow process, Galaxy tool, script) already holds the
genome name, taxon, version, authors, creation date, masking state and optional
fields as structured data. It writes them to a JSON document in the toolkit's
documented options format and runs `bioheaders metadata --json options.json -o
metadata.yaml`, getting the same metadata file the equivalent command-line
options produce, with no user text on the command line.

**Why this priority**: it is the whole request: one documented input that
workflow engines can produce without building an argument list or a shell
command from user text.

**Independent Test**: for a set of option combinations (required only; every
option; repeated options; hostile text), run the command once with flags and
once with the equivalent JSON document; the outputs are byte-identical and the
exit statuses equal.

**Acceptance Scenarios**:

1. **Given** a JSON document holding every required option, **When**
   `bioheaders metadata --json options.json -o m.yaml` runs, **Then** `m.yaml`
   is byte-identical to the output of the equivalent command-line flags, and
   `combine` + `verify` succeed on it.
2. **Given** a document with two metadata authors (one with an ORCID), two
   assembly software entries (name, version, URI), two `vitalStats` values and
   two `x-` extension fields, **Then** the arrays and fields appear in the order
   given, exactly as with the repeated flags.
3. **Given** the same document on standard input, **When** the command runs
   with `--json -`, **Then** the output is the same as from the file.
4. **Given** a document holding `stats-from` with a FASTA path, **Then**
   `vitalStats` is computed from that FASTA exactly as with `--stats-from`.

---

### User Story 2 - The same validation as the command line (Priority: P1)

Whatever the command line refuses, the JSON document refuses too, with a
message naming the offending option, and nothing is written.

**Why this priority**: a second input path must not become a way around the
checks that keep invented or unsafe values out of headers (constitution
principle III).

**Independent Test**: for each refusal the command-line options already make,
the equivalent JSON document is refused with exit status non-zero, a message
naming the same option, and no output file.

**Acceptance Scenarios**:

1. **Given** a document missing `version` and the assembly authors, **Then** the
   command writes nothing, names both, and exits non-zero.
2. **Given** a value holding a line feed, a carriage return, U+2028, another
   control character or a bidirectional override, **Then** it is refused.
3. **Given** an ORCID with a wrong check digit, a date `2026-02-30`, a taxon id
   `96O6`, an unknown masking value or an extension key that is not an `x-`
   key, **Then** each is refused as on the command line.
4. **Given** a `vitalStats` value that `stats-from` also computes, together with
   `stats-from`, **Then** the document is refused ("give one or the other").

---

### User Story 3 - Reject what the format does not define (Priority: P1)

A document with a misspelled key, a value of the wrong JSON type or malformed
JSON is refused rather than partly read.

**Why this priority**: a silently ignored key (`date_created` for
`date-created`, say) would drop user metadata or, for a required option, be
reported as missing with no hint why; failing closed is the project rule.

**Independent Test**: documents with an unknown top-level key, an unknown key
inside an author or software entry, a duplicate key, a number where text is
expected, a non-object top level and truncated JSON are each refused with a
message naming the key or the position.

**Acceptance Scenarios**:

1. **Given** a document with the key `dateCreated2`, **Then** the command fails
   and names the unknown key (and, where one is close, the key it may mean).
2. **Given** a document in which a key appears twice in the same object,
   **Then** it is refused, not resolved by taking the last value.
3. **Given** `NaN`, `Infinity`, a boolean or an array where a single value is
   expected, **Then** it is refused, naming the key.

---

### User Story 4 - Galaxy calls the installed command (Priority: P2)

The Galaxy metadata wrapper (here and in tools-iuc) maps Galaxy's form layout
to the toolkit's JSON format in a configfile and runs `bioheaders metadata
--json` on it. It ships no helper script, and no user text reaches the shell.

**Why this priority**: the motivating consumer, but the wrapper change follows
the release and the Bioconda update, so it is follow-up work outside this
feature's code change; this feature must make it possible.

**Independent Test**: the wrapper's existing tests (hostile text, every
optional field, statistics) pass with a wrapper whose command line holds only
paths and fixed option names.

**Acceptance Scenarios**:

1. **Given** form values containing quotes, `$`, backticks, `;`, `>`, `@` and
   non-ASCII text, **Then** the metadata holds them exactly and the job's
   command line contains none of them.

---

### Edge Cases

- `--json -` together with `stats-from: "-"`: both cannot read standard input;
  refused.
- Optional values given as `null` or as an empty list are treated as absent, so
  a workflow engine can write every key without conditionals; an empty string
  is refused, as on the command line ("the value is empty").
- A JSON document that is not UTF-8, starts with a byte order mark, or is larger
  than the bounded size the toolkit already applies to metadata (1 MiB) is
  refused before parsing completes.
- Deeply nested JSON is refused with a concise error, never a crash.
- Hostile text (`"`, `\`, `>`, `@`, `: `, `#`, `- `, `{}`, `yes`, `010`,
  `.nan`) round-trips exactly, as with the flags.
- A `vitalStats` value given as a JSON number or as text in decimal form gives
  the same output; a boolean is refused.
- `--json` names a missing file or a directory: refused with the path named.
- The document is read in full before any FASTA is read, so an invalid document
  fails fast even with a large `stats-from` FASTA.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `bioheaders metadata` MUST accept `--json FILE`, where `FILE` is
  a path or `-` for standard input, holding one JSON object of metadata
  options. (The frozen `fhr-*` commands have no metadata command and are
  unchanged.)
- **FR-002**: The JSON options format MUST be the toolkit's own, documented in
  the README and the command's help, with an example and a key-by-key mapping
  to the command-line options; it MUST NOT depend on Galaxy's inputs layout.
- **FR-003**: The format MUST accept every metadata option the command line
  accepts (FR-002 of specs/004-bioheaders-metadata, including `type`,
  `stats-from` as a path, `stat` and `extra`), and nothing else. Keys are the
  command-line option names without the leading dashes (`date-created`,
  `taxon-id`, `stats-from`); `--version` is `version`.
  Output selection (`-o`/`--output`, `--format`) stays on the command line.
- **FR-004**: Repeatable options MUST be JSON arrays, kept in the order given:
  genome synonyms, instruments, identifiers and related links as arrays of
  text; metadata and assembly authors as arrays of objects with `name` and an
  optional ORCID URI; assembly software as an array of objects with `name` and
  optional version and URI; `vitalStats` values and `x-` extension fields as
  arrays of key/value objects.
- **FR-005**: Every value MUST pass the same checks as the corresponding
  command-line option, with messages naming the option: no invented required
  values (all missing ones listed together), control-character, line-break and
  invisible-character refusal, ORCID form and check digit, ISO calendar dates,
  NCBI taxonomy ids, masking values, R14 URI schemes, R15 `x-` keys, typed
  `vitalStats` values, `accession-url` needing `accession`, duplicate `stat`
  and `extra` keys, and `stat` keys refused together with `stats-from`.
- **FR-006**: An unknown key at any level, a duplicate key in any object, a
  value of the wrong JSON type, `NaN`/`Infinity`, invalid JSON, invalid UTF-8,
  a byte order mark and a top level other than an object MUST be refused with a
  non-zero exit, a message naming the key or position, and no output.
- **FR-007**: For any set of options, the output (bytes, file or standard
  output) and the exit status of `--json` MUST be identical to those of the
  equivalent command-line options.
- **FR-008**: Metadata options given on the command line together with
  `--json` MUST be refused with a message naming them; only `-o`/`--output`
  and `--format` may accompany `--json`.
- **FR-009**: The input MUST be read as JSON only; YAML is not accepted.
- **FR-010**: Reading the document MUST be bounded (at most 1 MiB, limited
  nesting depth), and the document MUST be fully validated before any
  `stats-from` FASTA is read.
- **FR-011**: The options format MUST be versioned or otherwise stable, so a
  workflow written against it keeps working across toolkit minor releases;
  changes to it follow the public-API rule (constitution principle V).
- **FR-012**: The Galaxy wrapper MUST be able to call `bioheaders metadata
  --json` with a command line holding only paths and fixed option names, and
  drop `fair_bioheaders_metadata.py`. The wrapper change itself is follow-up
  work after the release and the Bioconda update (here and in tools-iuc).

### Key Entities

- **Options document**: one JSON object whose keys are the command's metadata
  options and whose values are text, arrays of text, or arrays of small
  objects (author, software, key/value). It is not FHR metadata and is never
  mistaken for it: it has no `schema` or `schemaVersion`.
- **Author entry**: name and optional ORCID URI (one `--*-author` value).
- **Software entry**: name, optional version, optional URI (one
  `--assembly-software` value).
- **Key/value entry**: one `--stat` or `--extra` value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every option-combination test case, `--json` output and exit
  status equal those of the equivalent flags (100% of cases, byte for byte).
- **SC-002**: Every refusal the command-line options make has a JSON
  counterpart test that is refused with the same option named.
- **SC-003**: A Galaxy wrapper using `--json` passes all of the metadata
  wrapper's existing tests with no helper script and no user text in its
  command line.
- **SC-004**: A Nextflow or shell user can write a valid options document from
  the README alone (example plus mapping), without reading the source.
- **SC-005**: The full test suite, ruff, isort, black and mypy pass on Python
  3.9 and 3.13.

## Assumptions

- Values are JSON strings, as the command line's are text, except that a
  `vitalStats` value may also be a JSON number of the schema's type and a
  taxon id may be a positive JSON integer; this lets JSON producers write
  numbers naturally without changing the output.
- `null` and empty arrays mean "not given", so a workflow engine can emit every
  key; this keeps the Galaxy mapping free of conditionals.
- Author ORCIDs are given as the full `https://orcid.org/...` URI, as on the
  command line.
- `--type` stays limited to `fhr`; `fhp` and `fhgff3` are refused as today.
- Galaxy can build the documented shape from its form values in a Cheetah
  `<configfile>` with `json.dumps` (or a small macro) so that user text only
  reaches a file, never the shell. Whether Galaxy's Cheetah allows the needed
  import and builds nested lists cleanly, and how the configfile's path reaches
  the command, is a research question for the plan.
- A JSON Schema for the options document, if the plan adds one, describes the
  input format only; it is not an FHR contract and needs no specification
  change.
- Release (0.13.0 or later), Bioconda, the tools-iuc wrapper update and the
  nf-core module bump are separate maintainer-gated steps.
