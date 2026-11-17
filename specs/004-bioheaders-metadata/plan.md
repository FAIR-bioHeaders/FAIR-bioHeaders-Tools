# Implementation Plan: `bioheaders metadata`

**Branch**: `004-bioheaders-metadata` | **Spec**: [spec.md](spec.md) | **Issue**: #171 (Refs; #171 remains open)

## Summary

A new module `bioheaders/metadata.py` turns parsed options into an FHR record
(`build_record`) and computes `vitalStats` from a FASTA stream
(`FastaStats`). `bioheaders metadata` in `cli.py` adds the options, validates
the record against the bundled current FHR schema with the checksum
requirement set aside, and writes YAML or JSON with the existing writers.

## Technical context

Python 3.9+, standard library plus the existing `jsonschema` and `pyyaml`. FASTA
input goes through `open_input` (stdin, gzip and BGZF by magic bytes) and
`strip_parts` (the same header reader `strip`/`combine` use), in 1 MiB chunks.

## Research

- **Contract**: `bioheaders/fhr_schema.json` (`current`, release v0.6.0 in
  `bioheaders/schemas/bundled.json`) is byte-identical to
  `schemas/fhr-2.1.json`. `selection.current_fhr_url()` gives
  `https://w3id.org/fair-bioheaders/fhr/v0.6.0`; the highest `schemaVersion`
  enum value of that schema is `"2.1"`.
- **Field shapes** (all checked against `fhr-2.1.json`): `taxon` {name, uri
  `^https://identifiers\.org/taxonomy:[0-9]+$`}; authors are arrays of {name,
  uri (ORCID pattern), nameType}; `accessionID` {name, url}; `assemblySoftware`
  array of {name (required), version, uri, commandLineOption}; `identifier`
  items `^[A-Za-z0-9._-]+:.+$`; `scholarlyArticle` a bare DOI; `seqcol_id` 32
  base64url characters; `masking` one of `not-masked`, `hard-masked`,
  `soft-masked`, `repeat-masked`, `unknown`; `vitalStats` keys `L50`, `N50`,
  `L90`, `N90`, `totalBasePairs`, `numberContigs`, `numberScaffolds`,
  `readTechnology` (string), `scaffoldN50`, `scaffoldN90`, `scaffoldL50`,
  `scaffoldL90`, `gcContent` (0-100); extension keys
  `^x-[A-Za-z0-9][A-Za-z0-9_.-]*$` (R15).
- **Checksum today**: `combined_header` sets a stand-in checksum, renders,
  hashes, then validates, so `combine` accepts metadata with no `checksum` (or
  with the old all-`A` placeholder) and writes the real one; `validate`
  requires it. The command therefore omits it.
- **YAML writers**: `fhr.output_yaml` applies R12 and escapes YAML-only line
  breaks; `output_fasta` additionally applies R11. The YAML output uses the
  FASTA dumper's text without the `;~` prefix, so it can be embedded as is.
- **Statistics in the specification**: `docs/TERMS.md` and `docs/FORMAT.md`
  (v0.6.0) define N50/L50/N90/L90 as contig statistics over "the assembly
  length", the `scaffold*` variants over scaffolds, `gcContent` as a
  percentage, and require producers to document ambiguous-base handling.
  v0.6.0 defined no gap rule, so it was stated here. FAIR-bioHeaders-Specification
  #253 has since defined one, numbered as FORMAT.md rule R16: any run of one or
  more `N` splits contigs, contig N/L statistics use the summed contig length,
  scaffold N/L statistics `totalBasePairs`, and GC excludes ambiguity letters.
  The definitions below match R16.

## Statistics definitions

- Sequence bytes are every byte of non-header lines after a `>` line, except
  whitespace (space, tab, CR, LF, VT, FF). `;` lines are comments. Allowed
  bytes are the IUPAC nucleotide codes `ACGTUNRYSWKMBDHV` in either case;
  anything else (protein letters, `-`, `*`, digits) is an error naming the
  record, so a protein or malformed file is never summarized.
- **Scaffold**: one FASTA record with at least one base. Records without bases
  are not scaffolds; they are skipped with a warning.
- **totalBasePairs**: sum of scaffold lengths, `N` included.
- **numberScaffolds**: number of scaffolds.
- **Contig**: a maximal run of non-`N`/`n` bases within a scaffold; a run of
  one or more `N` or `n` separates contigs; leading and trailing runs belong to
  no contig. Other ambiguity codes are bases.
- **numberContigs**: number of contigs (0 for an all-`N` assembly).
- **N50 / L50, N90 / L90** (contig): sort contig lengths in decreasing order;
  Lx is the smallest k with `sum(first k) * 100 >= x * C`, where C is the sum of
  all contig lengths (the schema's "assembly length", read as the ungapped
  length for contig statistics; spec.md Clarifications); Nx is the length of
  the k-th contig. Omitted when there are no contigs.
- **scaffoldN50 / L50 / N90 / L90**: the same over scaffold lengths with
  `totalBasePairs`.
- **gcContent**: `100 * (G + C) / (A + C + G + T + U)`, case-insensitive,
  rounded to 2 decimals. `N` and the other ambiguity codes (including `S`) are
  excluded from numerator and denominator. Omitted when the denominator is 0.
- `readTechnology` is never computed; give it with `--stat`.

## Design

- `FastaStats.feed(chunk)` normalizes CR to LF, tracks line starts across
  chunks, skips `>`/`;` lines, and processes sequence segments with
  `bytes.translate` (whitespace removal and alphabet check), `bytes.count` and
  `bytes.find(b"N")` on the upper-cased segment (a regex only finds where a run ends); a contig open at a segment end
  continues into the next. Contig and scaffold lengths are kept in
  `array('Q')`. Work is linear and memory is O(contigs).
- `build_record(args)` collects missing required options first, then parses
  each typed value with a message naming the option. Free text refuses control
  characters (Unicode `Cc`) and U+2028/U+2029/U+0085. ORCID URIs are checked
  against the schema pattern and the ISO 7064 11,2 check digit. URI options
  must have a scheme R14 accepts (`link_scheme_warnings` is reused).
- Validation: `Draft202012Validator` with `FormatChecker` on a copy holding a
  stand-in checksum; the header-size limits (1 MiB, 10,000 lines) are checked
  on the FASTA rendering, so `combine` cannot fail on size later.
- CLI: `bioheaders metadata [--type fhr] [fields…] [--stats-from FASTA]
  [--format yaml|json] [-o OUT]`. Appended after `faidx` so existing help
  output is unchanged. No `fhr-*` name is added (those are frozen).

## Constitution check

I: implements the existing FHR 2.1 contract; no schema change, no new field;
the gap rule is a documented tool choice, not a contract meaning. II: no
sequence bytes are written; checksum stays with `combine`. III: missing,
malformed and hostile input fails closed with a message; memory bounded by the
contig count. IV: absent options are omitted, never null. V: new subcommand
only; regression tests ship with it.

## Verification

`poetry run pytest`, `ruff check .`, `isort . --check-only`, `black . --check`,
`mypy -p bioheaders`; the capability matrix is regenerated against the v0.6.0
suite so its drift check passes.
