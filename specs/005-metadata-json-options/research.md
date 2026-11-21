# Research: `bioheaders metadata --json`

## R1. How the document reaches the existing checks

- **Decision**: convert each JSON value into the text its command-line option
  would receive and set it on the same argparse namespace; then run the
  existing `_metadata` path unchanged.
- **Rationale**: FR-005 and FR-007 (same checks, identical output) then hold by
  construction, and there is one implementation of every check and message.
  The only conversions are joins: author `{name, orcid}` → `Name <orcid>`,
  software `{name, version, uri}` → `NAME[=VERSION[=URI]]`, `stat`/`extra`
  `{key, value}` → `KEY=VALUE`, an integer taxon id or stat number → its
  decimal text.
- **Alternatives considered**: a parallel builder from structured values
  (duplicates every check and lets the two paths drift); converting the
  document to an argv list and re-parsing it (argparse would read a value
  starting with `-` as an option, and errors would be argparse usage errors).

## R2. Separators the joins rely on

- **Decision**: in JSON, refuse `<` and `>` in an author name and `=` in a
  software name or version, naming the key.
- **Rationale**: the joined text is parsed by the flags' parsers. A name
  holding `<https://orcid.org/...>` would otherwise be read as an ORCID, and
  `=` would move the version/URI boundary. The Galaxy wrapper's validators
  already refuse these characters, and the flags cannot express them either,
  so nothing that worked becomes impossible.
- **Alternatives considered**: escaping (the flags have no escape syntax, so
  output could no longer be compared with them); structured validation (R1).

## R3. Strict JSON reading

- **Decision**: read at most 1 MiB + 1 byte (file or stdin) and refuse larger
  documents; refuse a UTF-8 byte order mark and invalid UTF-8; parse with
  `json.loads` using an `object_pairs_hook` that refuses duplicate keys and a
  `parse_constant` that refuses `NaN`/`Infinity`; turn `RecursionError` into
  "nested too deeply"; require a top-level object; refuse unknown keys at every
  level, suggesting the closest key (`difflib`, after mapping `_` to `-`).
- **Rationale**: constitution III (duplicate keys, ambiguous input, bounded
  resources). 1 MiB is the toolkit's metadata limit (`MAX_HEADER_BYTES`); any
  real options document is a few kilobytes. Python's `json` already refuses raw
  control characters inside strings; escaped ones (`\n`, ` `) reach
  `text()` and are refused there with the option named.
- **Alternatives considered**: a JSON Schema for the document (would duplicate
  the key table and still need the duplicate-key and constant hooks); YAML
  (refused by clarification Q3).

## R4. Absent values

- **Decision**: `null` and `[]` mean "not given"; `""` is passed on and refused
  as on the command line (`the value is empty`, or "missing required value"
  for a required option, exactly as `--genome ""` is).
- **Rationale**: the Galaxy probe (R6) shows that unset optional text
  parameters arrive as `null` and empty repeats as `[]`; treating them as
  absent keeps the wrapper's template free of conditionals. Refusing `""`
  keeps the flags' behaviour.
- **Alternatives considered**: refusing `null` (forces conditionals in every
  template); treating `""` as absent (diverges from the flags and hides
  mistakes).

## R5. Flags together with `--json`

- **Decision** (clarification Q1): refuse any metadata option given on the
  command line with `--json`, naming each one; allow only `-o`/`--output` and
  `--format`. To detect an explicit `--type`, its argparse default becomes
  `None` and the command resolves it to `fhr`.
- **Rationale**: one source of values, no precedence rules to document or test.
- **Alternatives considered**: flags override (needs replace-or-extend rules
  for lists); allow non-overlapping flags.

## R6. Galaxy: building the document in a Cheetah configfile

Question: can a Galaxy `<configfile>` build our JSON shape with `json.dumps`
from nested repeats, sections and conditionals; how do unset values come
through; does it keep user text out of the command line; is the sanitizer
override still needed?

**Probe 1** (`json_configfile_probe`, planemo 0.75.47, Galaxy 26.1, profile
25.0, [research/galaxy-configfile-probe.xml](research/galaxy-configfile-probe.xml);
its two tests fail on purpose so that planemo prints the configfile): a configfile with `#import json`,
lists built in `#for` loops with `#silent $list.append(...)`, and one
`$json.dumps({...})` expression. Results:

- `#import json` and `$json.dumps` work in a configfile.
- `$param.value` is the **raw** value: quotes, `\`, `$(...)`, backticks, `;`,
  `#`, `@`, `<`, `>` and non-ASCII arrive unchanged, with the default
  sanitizer still on. `str($param)` is sanitized (`q__sq__ d__dq__ bX X(x)...`)
  unless `<sanitizer sanitize="false"/>` is set. So the wrapper reads
  `.value` and can drop the sanitizer override.
- A text area value with a line break arrives as `"line one\nline two"`
  (refused later by bioheaders, as intended).
- Unset optional text → `null`; unset optional select → `null`; empty repeat
  → `[]`; nested repeat items are `{"name": ..., "orcid": null}`.
- A data parameter in a conditional: `str($statistics.fasta)` is the dataset
  path; `None` when the `when` branch is not taken.
- The job's command line held only the configfile and output paths.

**Probe 2** (the planned wrapper, built locally from the current wrapper): the
current `fair_bioheaders_metadata.xml` with its command and `<inputs>`
configfile replaced by the design below, the helper script deleted, the
sanitizer override removed, and the hostile-text tests' command assertion
changed from the script name to `--json` (their `assert_stderr` on the echoed
argv dropped, as nothing echoes it). Run with this branch's `bioheaders` on
`PATH` (`planemo test --no_dependency_resolution`): **13/13 tests pass**,
including the backslash/quote/`$(...)`/backtick round trips in JSON and YAML
(tests 12 and 13), the ORCID check-digit and impossible-date failures, and
statistics from FASTA with a header. `planemo lint` is clean. Every job's
command line is `bioheaders metadata --json '<configfile>' --format '<fmt>'
--output '<path>'`.

- **Decision**: after the release and the Bioconda update, the wrapper (here
  and in tools-iuc) uses:

  ```xml
  <command><![CDATA[
  bioheaders metadata --json '$options' --format '$output_format' --output '$output'
  ]]></command>
  <configfiles>
      <configfile name="options"><![CDATA[#import json
  #set $assembly_author = []
  #for $item in $assembly_authors
  #silent $assembly_author.append({'name': $item.name.value, 'orcid': $item.orcid.value})
  #end for
  ## ... one loop per repeat (synonyms, metadata authors, instruments,
  ## software, identifiers, related links, stats, extras) ...
  $json.dumps({
      'genome': $genome.value,
      'taxon-id': str($taxon_id),
      'stats-from': str($statistics.fasta) if str($statistics.compute) == 'yes' else None,
      'documentation': $optional_fields.documentation.value,
      ## ... every key of contracts/metadata-options.md ...
      'assembly-author': $assembly_author,
  })
  ]]></configfile>
  </configfiles>
  ```

  and deletes `fair_bioheaders_metadata.py`. The full command and configfile are
  [research/galaxy-wrapper-command.xml](research/galaxy-wrapper-command.xml).
- **Rationale**: user text reaches only a file written by Galaxy and read by
  bioheaders; the command line holds Galaxy-controlled paths and a select
  value. `json.dumps` escapes everything (ASCII output), and `.value` bypasses
  the sanitizer, so the override and its warning comment can go. bioheaders
  repeats every check the Galaxy validators make, so values connected in a
  workflow (where validators may not run) are still refused.
- **Alternatives considered**: keep the helper script (what the IUC reviewer
  asked to remove); `<inputs>` configfile with Galaxy's own layout (ties the
  toolkit to Galaxy's parameter names, refused by FR-002); building JSON with
  string templates (escaping errors).

## R7. Documentation and stability

- **Decision**: document the format in the README, the command's help epilog
  (with a runnable example tested in CI) and
  `contracts/metadata-options.md`; treat it as public API (FR-011): keys are
  added, never renamed or removed, within a major version.
- **Rationale**: Nextflow and Galaxy templates pin the key names.
- **Alternatives considered**: a `version` key in the document (the format has
  one version so far; adding one later stays compatible because unknown keys
  are refused today).
