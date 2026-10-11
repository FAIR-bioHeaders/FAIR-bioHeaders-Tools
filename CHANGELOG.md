# Changelog

## Unreleased

- Support the **draft** protein FASTA header FHP (FHR-Specification spec 006):
  - the bundled `fhp_schema.json`, a copy of FHR-Specification `fhp.json`;
  - every command validates a record against the FHP schema when its `schema`
    is an `fhp.json` URL in FHR-Specification, and against FHR otherwise, so FHR
    results and messages are unchanged;
  - `validate` prints `FHP metadata is valid.` for FHP;
  - `combine` names its default output `X.fhp.fasta` for FHP metadata;
  - `.faa` is a FASTA extension;
  - JSON-LD and HTML microdata output are refused for FHP.
  New `bioheaders verify-links` reports each recorded `derivedFrom` parent as
  `matched`, `not matched` or `not checked` against files on disk, by checksums
  computed from their bytes, and never writes. `bioheaders assess` reports FHP
  schema conformance. Tests cover the 23 FHP conformance vectors and byte
  preservation for every residue class.

## 0.5.0 — 2026-10-10

- Add `bioheaders assess` (FHR-Specification feature 010): a FAIR checklist for the header of
  a FASTA, GFF3, GAF, VCF, GFA or other text file against the 41 RDA FAIR Data Maturity Model
  indicators, with the cited header lines and a suggestion in the file's own convention for
  each gap; no score. It reports FAIR-bioHeaders schema conformance separately, verifies
  recorded links against a `--related` file and reports name/length agreement as
  circumstantial evidence. Batch mode (`--recursive`, `--include`, `--exclude`, `--jobs`,
  `--pairs`, `--output`) writes per-file reports and `summary.json`/`.md`/`.tsv`,
  byte-identical on a re-run; 200 synthetic files took about 20 s on a laptop
  (`scripts/bench_assess.py`). Offline by default; `--online` (with `--online-timeout`)
  resolves only header identifiers and URLs, refusing private addresses and never sending
  file contents. The rubric (1.1.0), synonym and reference tables ship in
  `bioheaders/assess/data/`; the `bioheaders.assess` API is provisional. RDA indicator text is
  used under CC BY 4.0 with attribution. No new runtime dependency; existing commands are
  unchanged.
- Add JSON-LD (`.jsonld`, `--from/--to jsonld`) for FHR metadata, following
  FHR-Specification docs/JSONLD.md (feature 011): the record with its own keys, an
  embedded bundled context and typed nodes (`Dataset`, `Taxon`, `Person`/`Organization`/`Agent`
  from the author identifier, `PropertyValue`, `SoftwareApplication`, `VitalStats`). Output
  is byte-identical to the specification's examples. A `documentation` URL is written as
  `subjectOf`. The context also defines the node types at its root, so JSON-LD 1.0 tools such
  as validator.schema.org recognise them. Reading the canonical form (rule J1) needs no new dependency. Other JSON-LD
  forms (expanded, compacted with another context, one record in `@graph`) are read by
  JSON-LD expansion (rules J3 to J5) with the new optional `jsonld` extra (PyLD, Python
  3.10+); terms that map to no FHR field fail the read unless `convert`/`validate` get
  `--ignore-unknown-terms`, which reports them as warnings. Nothing is fetched: contexts
  come only from the bundled copy. `convert --export-context FILE` adds the dataset `@id`, `url` and
  `keywords` and claims Bioschemas Dataset 1.0-RELEASE conformance only when complete
  (provisional). The new `bioheaders.jsonld` API is provisional. Existing formats and
  commands are unchanged.
- Document the MPL-2.0 transition for new project contributions from March 2025 onward, preserve historical permissions and third-party notices, and align README/package/citation licensing. No runtime behavior changes.

## 0.4.0 — 2026-10-08

0.4.0 renames the project; FHR metadata, checksums, and file handling are
unchanged, and every 0.3 command and import keeps working.

- Rename the PyPI distribution `fhr` to `fair-bioheaders` and the Python package
  `fhr` to `bioheaders`; the repository moved from FHR-File-Converter to
  FAIR-bioHeaders-Tools (old URLs redirect). Zenodo DOIs are unchanged.
- Add the `bioheaders` command with `convert`, `validate`, `combine`, `strip`,
  and `verify` (alias `checksum`) subcommands. The sequence subcommands detect
  FASTA or GFA from the file extension, including before `.gz`/`.bgz`, or take
  `--type fasta|gfa` (required for stdin). `python -m bioheaders` runs it.
- Keep the eight `fhr-*` commands with unchanged options, output, and exit
  status; they print no deprecation notice.
- Keep `import fhr` and `fhr.cli` as deprecated aliases: an `fhr` module, installed
  by `fair-bioheaders`, makes them the same module objects as `bioheaders` and
  `bioheaders.cli` and emits one `DeprecationWarning`.
- Publish `fhr` 0.4.0 as a compatibility distribution without code that requires
  `fair-bioheaders==0.4.0` and declares the `fhr-*` commands, so `pip install fhr`
  and `pip install -U fhr` from 0.3 keep working. It is built from `compat/fhr`.
- The release workflow builds, checks, attaches, and publishes both distributions.
- The packaged schema moves to `bioheaders/fhr_schema.json`; the root and
  `fhr/fhr_schema.json` copies stay for FHR-Specification's release checks.

## 0.3.3 — 2026-10-08 (patch release of v0.3)

- Read gzip, multi-member gzip, and BGZF FASTA/GFA (and metadata) input, detected
  by magic bytes and decompressed as it streams. Checksums cover the decompressed
  bytes, so plain and compressed copies validate with the same checksum. Corrupt
  or truncated gzip input is a concise `FHR:` error. Plain-file behaviour is
  unchanged.
- Write BGZF when an output path ends in `.gz` or `.bgz`, with a small
  standard-library writer (`fhr.cli.BgzfWriter`). Combine without `-o` keeps a
  compressed input's extension. Stdout is never compressed.
- Accept `-` for stdin and stdout in validate, strip, combine, and convert;
  add `--from`/`--to` format options to `fhr-convert` and `--from` to
  `fhr-validate`. Combine spools stdin to a temporary file in `TMPDIR`.
- Add `fhr.cli.open_input` and `fhr.cli.write_to` for compressed and standard
  stream input and output. No new dependencies.

## 0.3.2 — 2026-10-08 (patch release of v0.3)

- Stream FASTA/GFA validate, strip, combine, and convert in 1 MiB chunks with
  bounded memory (#24): about 35 MB peak instead of about 5x the file size, and
  faster. Checksums and outputs are unchanged.
- Limit FHR header lines to 16 MiB in total, with a clear error.
- Write all command outputs atomically through a temporary file and rename.
- Add `fhr.sequence_parts`, `fhr.read_chunks`, `fhr.cli.SequenceScan`,
  `fhr.cli.strip_parts`, and `fhr.cli.write_output` for streaming use; the bytes
  API uses the same code.
- Build and publish releases from a version tag: the GitHub release, and PyPI
  through trusted publishing. This is the first PyPI release since 0.1.1.

## 0.3.1 — 2026-10-08 (patch release of v0.3)

- Reject duplicate mapping keys in FASTA/GFA headers, YAML, and JSON; a later
  `;~`/`#~` line can no longer silently override an earlier header field.
- Reject YAML anchors, aliases, and merge keys (unbounded alias expansion and
  YAML 1.1-only merge semantics).
- Parse FASTA/GFA headers from the same byte lines that are hashed; only header
  lines must be UTF-8. Header lines must not contain U+0085, U+2028, or U+2029,
  which YAML reads as line breaks; the YAML writer escapes them.
- Require the checksum value on the checksum line itself as a single-line scalar.
- Require FHR lines to form the leading header block; reject `;~`/`#~` lines
  after the first FASTA `>` line or GFA record line, including concatenated files.
- Reject FASTA/GFA files that begin with a UTF-8 byte order mark; ignore one at
  the start of JSON, YAML, or HTML metadata.
- Read microdata with HTML implied end tags, whitespace-separated `itemtype` and
  `itemprop` lists, first-wins duplicate attributes, and microdata value attributes
  only on their defining elements. Typed values must match `data-fhr-type`.
- Report schema errors as a JSON path and message; report excessive nesting as an error.
- Development dependencies: pytest 9.0.3+ on Python 3.10+ (CVE-2025-71176) and
  black 24.3.0+ on Python 3.9 (CVE-2024-21503). pytest 9 does not support 3.9.

## 0.3.0 — 2026-10-07 (coordinated FHR v0.3, from v0.2)

- Package metadata moves from the checkout's historical 0.1.1 to the coordinated 0.3.0 target.
- Package the schema and CLI entry points so installed tools work outside the checkout.
- Replace inconsistent format-specific state with a preserved metadata mapping;
  input methods accept text, bytes, or readable streams. Optional fields are not filled with null.
- Validate parsed objects with date/URI format checking. Add assembly provenance,
  protocol, N90/GC, and supplied SeqCol support; preserve legacy software strings.
- Repair YAML output, FASTA/GFA combine and strip inputs, and failure exit codes.
- Preserve non-FHR sequence bytes and comments. Verify exact-byte SHA-512/256 over
  metadata plus sequence, excluding the checksum line. Regenerate old MD5/payload-only checksums.
- Serialize YAML headers safely and HTML with escaped values and explicit types.
- Add regression/installed CLI tests, update CI, guidance, examples, Docker, and Chicago citations.

Constructor keyword fields remain available; obsolete positional arguments need
migration to keywords. Empty optional defaults are no longer emitted. SeqCol
identifiers are preserved, not calculated or checked against sequence contents.
Sequence helpers currently read complete files into memory.
