# FAIR-bioHeaders Tools

[![Tests](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/actions/workflows/pytest.yaml/badge.svg?branch=main)](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/actions/workflows/pytest.yaml)
[![Specification DOI](https://img.shields.io/badge/Specification_DOI-10.5281%2Fzenodo.6762549-blue)](https://doi.org/10.5281/zenodo.6762549)
[![File Converter DOI](https://img.shields.io/badge/File_Converter_DOI-10.5281%2Fzenodo.6762547-blue)](https://doi.org/10.5281/zenodo.6762547)

Convert and validate FAIR-bioHeaders Reference genome (FHR) metadata in JSON,
YAML, JSON-LD, FASTA, GFA, GFF3, and HTML microdata. See
[FAIR-bioHeaders-Specification](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification) for the
schema and metadata design. This is the `fair-bioheaders` package, version
**0.8.5**, formerly the FHR File Converter (`fhr`); see
[Renamed from fhr](#renamed-from-fhr).

## Install

For a published release:

```bash
python -m pip install fair-bioheaders
```

For this checkout and its development checks (Python 3.9 or later):

```bash
python -m pip install poetry
poetry install
poetry run pytest
poetry run ruff check .
poetry run isort . --check-only
poetry run black . --check
poetry run mypy -p bioheaders
```

## Commands

```bash
bioheaders convert examples/example.fhr.yaml /tmp/example.fhr.json
bioheaders validate /tmp/example.fhr.json
bioheaders combine examples/example.fhr.yaml genome.fasta -o genome.fhr.fasta
bioheaders verify genome.fhr.fasta
bioheaders strip genome.fhr.fasta genome.stripped.fasta
bioheaders combine examples/example.fhr.yaml assembly.gfa -o assembly.fhr.gfa
bioheaders verify assembly.fhr.gfa
bioheaders strip assembly.fhr.gfa assembly.stripped.gfa
```

`combine`, `strip`, and `verify` (also called `checksum`) take the FASTA, GFA, or
GFF3 type from the sequence file's extension, ignoring `.gz` or `.bgz`; give
`--type fasta`, `--type gfa`, or `--type gff3` for stdin or other extensions. `bioheaders
--version` prints the version and `bioheaders COMMAND --help` describes each
command. The original commands remain available with the same options and output:

| `bioheaders` command | Original command |
| --- | --- |
| `convert INPUT OUTPUT` | `fhr-convert` |
| `validate INPUT` | `fhr-validate` |
| `combine METADATA SEQUENCE` | `fhr-fasta-combine`, `fhr-gfa-combine`, `fhr-gff3-combine` |
| `strip INPUT [OUTPUT]` | `fhr-fasta-strip`, `fhr-gfa-strip`, `fhr-gff3-strip` |
| `verify INPUT` | `fhr-fasta-validate`, `fhr-gfa-validate`, `fhr-gff3-validate` |

`combine` and `verify` require the metadata's header family to match the file
format: FHR supports FASTA and GFA, FHP supports FASTA, and FHGFF3
supports GFF3. A mismatch exits with status 1, even if the checksum matches.
The family is selected from the metadata's `schema` URL; sequence residues are
not used to infer the family, so the protein/nucleotide distinction is not enforced.

`convert INPUT OUTPUT` detects `.json`, `.yaml`/`.yml`, `.jsonld`,
`.fasta`/`.fa`/`.fas`/`.fna`/`.faa`/`.ffn`/`.frn`/`.fsa`/`.mpfa`, `.gfa`,
`.gff3`/`.gff`, and `.html` from extensions (the same sequence extensions are
inferred by `combine`, `strip`, `verify` and `validate`). It validates metadata before writing
output; FASTA, GFA, and GFF3 output contains a metadata header only, and GFF3 output
begins with `##gff-version 3` so that `validate` reads it back. GFF3 output is
available only for FHGFF3 metadata. To include sequence data,
use `combine METADATA SEQUENCE [-o OUTPUT]`, whose default output replaces a known
sequence extension (`.fa`, `.fasta`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn`,
`.fsa`, `.mpfa`, `.gfa`, `.gff3`, `.gff`) with `.fhr.fasta` or `.fhr.gfa` for FHR, `.fhp.fasta` for FHP, or
`.fhgff3.gff3` for FHGFF3 (for example, `genes.gff3` becomes
`genes.fhgff3.gff3`). Any other suffix is kept and the output extension is
appended, so `GCF_000001405.39` and `GCF_000001405.40` become distinct files
instead of overwriting one another. A trailing `.gz` or `.bgz` is preserved. If
the default output already exists, `combine` stops instead of overwriting it;
give `-o` to write to that path anyway (an explicit `-o` writes through a symlink
rather than replacing it). A non-regular input (stdin, `/dev/stdin`, process
substitution or a FIFO) writes stdout when `-o` is omitted. Existing FHR header
lines are replaced. Inputs are not overwritten by sequence helpers.

`strip INPUT [OUTPUT]` writes to stdout if OUTPUT is omitted. Only FHR-prefixed
lines are removed; other bytes, including ordinary comments and CRLF endings,
are preserved. `validate` checks metadata, while `verify` (`fhr-fasta-validate`,
`fhr-gfa-validate`, `fhr-gff3-validate`) also verifies the exact-byte file checksum.
Failures exit with status 1. Both commands, and `combine` and `convert`, reject
NaN and infinite numbers (FORMAT.md R13), naming the field. They also print a
warning, without changing the exit status, when a required value is empty in
schemaVersion 2.0 or 1.0 metadata (until the next major schemaVersion), naming
each empty string, list or object, an author without a non-empty `name`, or a
taxon with neither a non-empty `name` nor `uri`.

FASTA/GFA/GFF3 commands stream their input in 1 MiB chunks, so memory use does not grow
with file size (about 35 MB peak for a 1 GB FASTA). Validate reads the file once;
combine reads a regular file twice (input that can't be read twice, such as
stdin, a pipe or a FIFO, is spooled to a temporary file). FHR header lines are
limited to 1 MiB and 10,000 lines in total, header YAML to 20,000 nodes nested at
most 64 deep, and metadata files to 64 MiB after decompression. Outputs are
written to a temporary file in the destination directory and then renamed, so a
failed command leaves no partial output.

### Compressed files and pipes

```bash
bioheaders combine examples/example.fhr.yaml genome.fa.gz    # writes genome.fhr.fasta.gz
bioheaders verify genome.fhr.fasta.gz
bioheaders strip genome.fhr.fasta.gz genome.stripped.fa.gz
zcat genome.fa.gz | bioheaders combine --type fasta examples/example.fhr.yaml - > genome.fhr.fasta
curl -sL https://example.org/genome.fhr.fasta.gz | bioheaders verify --type fasta -
bioheaders convert genome.fhr.fasta.gz - --to json
bioheaders convert - metadata.yaml --from json < metadata.json
```

Gzip input, including multi-member gzip and BGZF, is recognized by its magic
bytes rather than its extension and decompressed as it streams. The checksum
covers the decompressed FASTA/GFA bytes, so `genome.fa` and any gzip or BGZF
compression of it have the same checksum. A corrupt or truncated gzip file is an
error. Formats are taken from the extension before `.gz` or `.bgz`.

Outputs whose path ends in `.gz` or `.bgz` are written as BGZF, which `gzip`,
`zcat`, `bgzip`, and htslib read. A combine without `-o` keeps the input's
compression extension. Other outputs, and stdout, are never compressed. Note that
`samtools faidx` (and tools built on htslib, such as `bcftools` and pysam's
`FastaFile`) cannot build an index for FASTA files containing `;` lines,
compressed or not; write the index with [`bioheaders faidx`](#indexing-fasta-with-a-header-for-htslib-tools-faidx)
instead, or index a stripped copy:

```sh
bioheaders strip genome.fhr.fa.gz genome.fa.gz   # writes BGZF
samtools faidx genome.fa.gz                       # .fai and .gzi
```

The stripped file has the same sequence bytes; `bioheaders verify` on the FHR
file still checks the original. Which other tools accept FHR files is surveyed in
[TOOL_COMPATIBILITY.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/TOOL_COMPATIBILITY.md);
support for leading `;` lines in htslib is proposed in
[samtools/htslib#2103](https://github.com/samtools/htslib/issues/2103).

`-` reads stdin or writes stdout: the input of verify, strip, combine (the
sequence), convert, and validate, and the output of strip, convert, and
`combine -o`. Combine of stdin, or another non-regular sequence input, writes
stdout by default; give `-o` to write a file. Convert and validate need
`--from FORMAT` for stdin and convert needs `--to FORMAT` for stdout
(`json`, `yaml`, `jsonld`, `fasta`, `gfa`, `gff3`, or `html`); the `bioheaders` sequence commands
need `--type` for stdin. Stdin is read once: combine spools the stripped sequence
to a temporary file in `TMPDIR` (as large as the sequence) while hashing it.
Other inputs that cannot be read twice (`/dev/stdin`, process substitution and
named pipes) are copied to a temporary file before the command reads them. Strip
from stdin to stdout writes as it reads, so an error late in the input can follow
partial output; check the exit status. Strip of a file to stdout still checks the
whole file before writing.

### Indexing FASTA with a header for htslib tools (`faidx`)

```bash
bioheaders faidx genome.fhr.fa          # writes genome.fhr.fa.fai
bioheaders faidx genome.fhr.fa.gz       # BGZF: genome.fhr.fa.gz.fai and .gzi
samtools faidx genome.fhr.fa chr1:1000-2000
```

htslib refuses to build an index for a FASTA file that starts with `;` lines,
but it uses an existing `.fai` (and `.gzi` for BGZF) instead of building one.
`bioheaders faidx INPUT` writes that index: the one `samtools faidx` would write,
with offsets that count the header bytes, so the tools read the sequences
straight from the FHR (or FHP) file. With an index in place these work on the
file with a header:

- `samtools faidx genome.fhr.fa REGION...` (with regions, or `-r regions.txt`)
- `bcftools` commands that load a reference (`bcftools norm -f`, `bcftools
  consensus -f`, `bcftools mpileup -f`)
- pysam `FastaFile(path).fetch(...)`
- `bedtools getfasta -fi genome.fhr.fa`
- JBrowse `jbrowse add-assembly genome.fhr.fa --load copy`, with
  `genome.fhr.fa.fai` next to it (the index is copied with the file)
- Ensembl VEP `--fasta genome.fhr.fa` (through `Bio::DB::HTS`)

Run `bioheaders faidx` first: a tool that finds no index tries to build one and
fails on the header. `samtools faidx genome.fhr.fa` with no region always
rebuilds the index, so it still fails (it leaves the existing index in place).
Re-run `bioheaders faidx` after `combine` or any other change to the file, since
a new header moves every offset.

The header is skipped exactly as `strip` removes it, together with any ordinary
`;` comment and blank lines before the first record, and the header's size limits
apply. Every later byte is indexed by the rules of htslib's `fai_build_core`, so
for a file without a header the `.fai` and `.gzi` are byte-identical to
`samtools faidx` output, and the same malformed files are rejected (line lengths
that differ within a record, a lone carriage return between records, other text
before the first record). Records without sequence are omitted, as samtools
does, with a warning (the first 10 are named), and a name ends at a NUL byte, as
in samtools. The deliberate differences from samtools:

- a duplicate sequence name is an error (samtools warns and indexes only the
  first, so the later records cannot be reached);
- a name over 64 KiB, too long for htslib to read back from the index, is an
  error;
- `;` comment lines before the first record are accepted (samtools rejects
  them; this is what lets the header through);
- a BGZF block whose ISIZE (uncompressed length) field is wrong is an error
  (samtools ignores the field);
- plain gzip data appended after BGZF blocks is an error (samtools silently
  drops the records in it).

Plain gzip input is an error ("Cannot index files compressed with gzip, please
use bgzip"); FASTQ is not supported. `-o` sets the `.fai` path (`-` for stdout)
and `--gzi` the `.gzi` path (a file; not stdout). The input must be a regular
file; outputs are written atomically, only after the whole index is built (on
an error neither is written), and never replace the input.
`faidx` reads the file once, in bounded memory; it does not validate the header,
so run `bioheaders verify` as well.

### JSON-LD

```bash
bioheaders convert examples/example.fhr.json example.fhr.jsonld
bioheaders convert example.fhr.jsonld back.json
bioheaders convert --export-context export.yaml examples/example.fhr.json page.jsonld
```

A `.jsonld` file is the FHR record with its own keys, an embedded JSON-LD context and
`@type` on the record (`Dataset`) and its nested nodes, so the same document is FHR
metadata and schema.org linked data. The format is defined in FAIR-bioHeaders-Specification
[docs/JSONLD.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/JSONLD.md),
and `examples/example.fhr.jsonld` is byte-identical to the specification's example. The
context is bundled (`bioheaders/fhr.context.jsonld`, a copy of the specification's
`jsonld/fhr.context.jsonld`) and never fetched; writing and reading the canonical form need no
extra package, and everything works offline.

- Authors are typed from an explicit `nameType` first (`Personal` as `Person`,
  `Organizational` as `Organization`); otherwise `Person` with an ORCID iD,
  `Organization` with a ROR ID, and otherwise `Agent` (not classified). The
  schema.org export uses the same typing and writes `nameType` only as the node's
  `@type`. A `documentation` value that is an absolute `http`, `https` or `ftp` URL is
  written as `subjectOf`, anything else as `documentation` (`schema:description`).
- Link fields (`relatedLink`, `assemblyProtocol`, `accessionID.url`, a software `uri`, and
  the FHP counterparts) are written as IRIs only with an `http`, `https`, `ftp`, `urn`,
  `doi` or `info` scheme (specification rule R14). A record with another scheme, such as
  `javascript:` or `file:`, is refused by the JSON-LD writers and the export, and
  `validate`, `convert`, `combine` and `verify` print a warning for it, for example
  `FHR: warning: relatedLink[0] uses the URI scheme 'javascript'; links should use http or
  https (...)`; it stays schema-valid.
- Nested keys that the context does not define, such as `taxon.checksum`, are kept and
  reported: `FHR: JSON-LD: taxon.checksum has no JSON-LD term; linked-data consumers will
  ignore it`.
- `--export-context FILE` (JSON-LD output only, provisional) reads a YAML or JSON mapping
  with the dataset's `id`, landing-page `url` and `keywords`, which are not FHR fields. The
  output then claims Bioschemas Dataset 1.0-RELEASE conformance (`conformsTo`) only when every
  minimum property is present, and otherwise names the missing ones.
- Reading accepts the canonical form (rule J1): the bundled context, embedded or by its
  raw-main URL, and no JSON-LD keyword except `@type` (and a root `@id`). `@context` and
  `@type` are set aside, `subjectOf` becomes `documentation`, and the export terms are set
  aside with a warning; the rest is validated like JSON.
- Other JSON-LD forms that use the FHR context or none (expanded, with value objects or
  explicit IRIs, or one record in `@graph`) are read by JSON-LD expansion (rules J3 to J5).
  The only context allowed is the FHR context, by its URL or as an embedded copy, alone and on
  the top-level object. Any other context (an extra or changed term, `@vocab`, `@import`, a
  nested `@context`), and `@nest`, are refused before expansion, because it could give an FHR key another
  field's meaning: `FHR: JSON-LD: the @context is an embedded context that is not the FHR
  context; ...`. Reading expanded or other forms needs the `jsonld` extra, PyLD, on Python
  3.10 or later:
  `pip install "fair-bioheaders[jsonld]"`. Contexts are served only from the bundled copy, so
  a remote context such as `https://schema.org/` is refused
  (`FHR: JSON-LD context is not available offline: https://schema.org/`). A term that maps to
  no FHR field fails the read
  (`FHR: JSON-LD term not in the FHR mapping: http://schema.org/keywords (at the record)`);
  `convert` and `validate` take `--ignore-unknown-terms` to report such terms as warnings
  instead. The document must describe exactly one record.
- `--jsonld-profile export` (JSON-LD output only, provisional) writes the one-way
  [schema.org export](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/SCHEMAORG-EXPORT.md)
  instead of the canonical form. It splits the record into the assembly (`Dataset`), the
  metadata record (`CreativeWork`), a `CreateAction` for the assembly software, one
  `Observation` per statistic, a `Grant` and a `ScholarlyArticle`, for search engines and
  Bioschemas tools. Nothing is added that the record does not say. The export context may
  also set `"assemblyProtocolHowTo": true` to write the protocol as a `HowTo`. An export
  cannot be read back: reading one fails with `this is a one-way schema.org export`.

  ```bash
  bioheaders convert examples/example.fhr.json page.jsonld --jsonld-profile export
  ```
- To put JSON-LD in a web page, use `bioheaders.jsonld.script_element(document)`: it writes
  the `<script type="application/ld+json">` element with `<`, `>` and `&` escaped as
  `\u003c`, `\u003e` and `\u0026` (rule J8), so no value can close the element.

FHP uses the same commands with its own context:

```bash
bioheaders convert proteins.fhp.json proteins.fhp.jsonld
bioheaders convert proteins.fhp.jsonld back.json
bioheaders convert proteins.fhp.json proteins.fhp.html
```

FHP canonical JSON-LD embeds the bundled FHP context (or a known FHP raw-main
context URL) and is read back losslessly. A reader rejects an unknown context, a
JSON-LD `@version` other than 1.1, a wrong or missing `@type` on the record or a
nested object, and an author `@type` that contradicts its explicit `nameType` or
its ORCID/ROR identifier. There is no FHP schema.org export: `--jsonld-profile
export` and `--export-context` fail clearly for FHP instead of writing an FHR
graph. FHP HTML microdata writes the typed metadata block and a readable table;
its reader rejects the FHR itemtype, an unsupported release, repeated scalar or
array-container properties, and content that exists only inside a `script` or
`template`. FHGFF3 continues to refuse both formats.

### Schema versions and which schema is used

A record's `schema` URL chooses the schema it is validated against, as
FAIR-bioHeaders-Specification [docs/SCHEMA-VERSIONS.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/SCHEMA-VERSIONS.md)
describes. Nothing is fetched; the package bundles the schemas.

| `schema` | Schema used |
| --- | --- |
| `https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/fhr.json` (or `fhp.json`, `fhgff3.json`) | The bundled copy of that type's schema on `main` (v0.4.0: FHR 2.0, FHP 1.0, FHGFF3 1.0) |
| The raw-main `fhr.json` URL (either repository name) with `schemaVersion` the number 1 (`1` or `1.0`) | The bundled v0.3.1 schema (FHR 1), with a deprecation warning (rule V6) |
| `https://w3id.org/fair-bioheaders/fhr/vX.Y.Z` (or `fhp`, `fhgff3`), or the raw URL at tag `vX.Y.Z` | The bundled copy of that release's schema: v0.3.0 and v0.3.1 (FHR 1), v0.4.0, v0.4.1 and v0.4.2 |
| A release that is not bundled, a release without that header type, or a raw URL at a branch or commit | Error: `FHR: unsupported schema version: … (this tool has … schemas for …)` |
| Anything else | FHR, the current schema |

From v0.4 `schemaVersion` is a string, `'2.0'` for FHR and `'1.0'` for FHP and
FHGFF3; the tools quote it when they write YAML.

FHR 1 (releases up to v0.3.1) told writers to cite the raw-main URL with
`schemaVersion: 1`, a number. Such a file is an FHR 1 file: every command that
validates (`validate`, `verify`, `convert`, `combine`, `verify-links`, `assess`)
checks it against the bundled v0.3.1 schema, the result follows that schema, and
the command prints

```text
FHR: warning: schemaVersion 1 via the raw-main schema URL is read as FHR 1 (v0.3.1); cite https://w3id.org/fair-bioheaders/fhr/v0.3.1 or move to schemaVersion "2.0"
```

`1` and `1.0` are the same number. The string `'1'`, a boolean or any other version
under raw-main is checked against the current schema as before, and so is
`schemaVersion: 1` under any other `schema` value. HTML microdata without
`data-fhr-type` reads `schemaVersion` 1 as the number. To clear the warning, cite
`https://w3id.org/fair-bioheaders/fhr/v0.3.1` to stay on FHR 1, or update the file
to v0.4, and recompute its checksum (`convert`, edit, `strip`, `combine`). The tools
keep a file's `schema` and `schemaVersion` as written; they never rewrite them, so
`combine` keeps an FHR 1 record FHR 1.
`bioheaders.selection` exposes the rule to Python code.

### Protein FASTA (draft FHP header)

The tools also read and write the **draft** FAIR header for protein FASTA, FHP
(FAIR-bioHeaders-Specification [docs/FHP.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/FHP.md)).
FHP is not released yet. A record whose `schema` is an FHP schema URL (an
`fhp.json` URL in FAIR-bioHeaders-Specification at `main` or a release tag, or
`https://w3id.org/fair-bioheaders/fhp/vX.Y.Z`) is validated against the bundled FHP
schema of that version. Every other record is validated as FHR. `.faa` is a FASTA extension.

```bash
bioheaders validate proteins.fhp.json             # FHP metadata is valid.
bioheaders combine proteins.fhp.json proteins.faa # writes proteins.fhp.fasta
bioheaders verify proteins.fhp.fasta
bioheaders strip proteins.fhp.fasta proteins.faa
```

Header handling does not depend on the alphabet. Stops (`*`), U, O, B, Z, J, X,
lower case and gaps are ordinary bytes: they are hashed and preserved exactly.
JSON, YAML, the FASTA header, canonical JSON-LD and standalone HTML microdata all
work for FHP. FHP canonical JSON-LD uses the reviewed FHP-Specification context
and is loss-preserving (ordered authors/sources/parents/software, nested objects,
typed scalars and absent optional fields survive a round trip); it has no
schema.org export profile. FHP microdata uses the FHP itemtype (never the FHR
itemtype), selects the fixed v0.4.0/v0.4.1/v0.4.2 contracts or the bundled current
contract for the raw-main URL, and writes escaped, inert HTML with a readable
table beside the typed metadata. FHGFF3 still has no JSON-LD or microdata form.

The bundled FHP schema (`bioheaders/fhp_schema.json`) is FHP 1.0 from
FAIR-bioHeaders-Specification v0.4.0 (release commit
`84c2f90ab0e97c81d8afbf33eafe80ebade7a009`, SHA-256
`e3f8f45260b833f931644e87ff7530cb9b4151e67094023dd96edde9a1d90366`). The
bundled FHP context (`bioheaders/fhp.context.jsonld`) is a byte-identical copy
from FHP-Specification `main` at commit
`9931a30cd6cb77619cd8d53b91ab41b5aae95eca` (SHA-256
`cb0b91c6bd55ff6026f0a3e7a30524c3a1d800922dbbf7117f6fe79c7760a984`), which
reuses the shared v0.4.0 vocabulary (`jsonld/terms.ttl`, SHA-256
`0c641879818a1ce02ed10348b344cb11c37fd86c8a120a9f9bfe8e618d32042c`) rather than
redefining it. Publication is coordinated through
FAIR-bioHeaders-Specification#107; the runtime reader and writer are
FAIR-bioHeaders-Tools#58. Nothing is fetched at run time.

`bioheaders verify-links FILE PARENT...` checks the parent files recorded in a
header's `derivedFrom` against candidate files on disk. It computes each FASTA, GFA
or GFF3 candidate's FAIR-bioHeaders checksum from its bytes, and reports each
recorded parent as `matched`, `not matched` (a file of that header type has another
checksum) or `not checked`. A match confirms file identity, not correct
translation. The command never writes. Exit status 3 means a parent did not match;
with `--require-all`, a parent that could not be checked also gives 3.

### GFF3 annotations (draft FHGFF3 header)

The tools also read and write the **draft** FAIR header for GFF3, FHGFF3
(FAIR-bioHeaders-Specification [docs/FHGFF3.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/FHGFF3.md)).
FHGFF3 is not released yet. `.gff3` and `.gff` files (plain, gzip or BGZF) are
GFF3. The `#~` header goes after `##gff-version 3` (optionally with a `.x.y`
version and trailing spaces or tabs), and the header block ends at the
first feature or `##FASTA`. Native directives such as `##sequence-region` may sit
among the header lines. A record whose `schema` is an `fhgff3.json` URL in
FAIR-bioHeaders-Specification is validated against the bundled FHGFF3 schema, which requires a
genome link: an `annotates` item in `derivedFrom` naming the FHR genome's checksum,
a `genomeReference` (assembly accession plus SeqCol digest), or both.

```bash
bioheaders combine annotation.yaml genes.gff3       # writes genes.fhgff3.gff3
fhr-gff3-validate genes.fhgff3.gff3                 # Checksum verified.
bioheaders verify-links genes.fhgff3.gff3 genome.fhr.fasta
fhr-gff3-strip genes.fhgff3.gff3 plain.gff3         # removes exactly the #~ lines
```

`combine` keeps line 1 (`##gff-version 3`, optionally with a `.x.y` version) first
and refuses a body without a valid version line.
`verify` and `fhr-gff3-validate` compare the header with the native
`##species`, `##genome-build`, `#!genome-build` and `#!genome-build-accession`
lines and print a `FHR: warning:` line for each disagreement; warnings never change
the result and nothing is rewritten. The first value of each compared directive
wins. A compared directive line longer than 64 KiB (`MAX_DIRECTIVE_BYTES`) is
ignored, though it is still hashed, so a later shorter line with the same name is
compared instead. `verify-links` checks the `annotates` checksum
against a supplied genome. A `genomeReference` is matched only against a supplied
FHR genome whose header records the same `seqcol_id`; the tools never compute
SeqCol digests. The gff3-validator uses `bioheaders.gff3.header_report(path,
genome)` for its header rules. JSON-LD and HTML microdata output are refused for
FHGFF3.

### `>` and `@` in FASTA headers

kseq-based FASTA readers (BWA, minimap2, seqtk, `samtools dict`, pysam `FastxFile`)
start a record at a `>` or `@` anywhere in a line, so a raw `>` or `@` in a FASTA
header line (an email address, `contigs > 1000 bp`) makes them read a bogus record.
Following FAIR-bioHeaders-Specification docs/FORMAT.md rule R11, the FASTA header
writer (`combine` for FHR and FHP) writes such a value as a double-quoted YAML
string with `\x3E` and `\x40`; reading the header gives back the real characters,
and JSON, YAML, JSON-LD, microdata, GFA and GFF3 output holds them unchanged.
Metadata without these characters is written exactly as before. `verify`,
`fhr-fasta-validate` and `validate` (FASTA input) print a `FHR: warning:` line for
a header line with a raw `>` or `@`; the result is unchanged.

### FAIR header assessment

```bash
bioheaders assess GCF_000002985.6_WBcel235_genomic.gff.gz          # terminal report
bioheaders assess --format json annotations.gff3.gz > report.json   # machine-readable
bioheaders assess --related genomic.fa.gz annotations.gff3.gz       # check the recorded genome link
bioheaders assess --recursive --pairs pairs.tsv --output reports/9.1.0 release-9.1.0/
```

`assess` reads the header of a FASTA, GFF3, GAF, VCF, GFA or other text file (gzip and BGZF
too) and reports, for each of the 41 RDA FAIR Data Maturity Model indicators, a status
(`evidenced`, `partially evidenced`, `not evidenced`, `not applicable` or `not assessed`) with
the header lines it rests on and, for each gap, a line to add in the file's own convention. It
is a checklist, not a score: nothing adds the statuses up. The guideline behind it is
FAIR-bioHeaders-Specification
[docs/FAIR_HEADER_GUIDELINE.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/FAIR_HEADER_GUIDELINE.md),
and the specification's `assessment/` fixtures pin the expected results
(feature 010).

- A FAIR-bioHeaders header gets a separate conformance result against the bundled schema; the
  schema URL in the header is never fetched.
- `--related FILE` verifies the links the header records (FHR checksum, SeqCol digest, VCF
  `##contig` MD5s, assembly accessions) against a related file, usually the genome, and
  reports name and length agreement separately as circumstantial evidence.
- Batch mode (several files, or a directory with `--recursive`) needs `--output DIR`. It
  writes one JSON and one Markdown report per file, mirroring the input tree, and
  `summary.json`, `summary.md` and `summary.tsv` with per-indicator counts. `--pairs` maps
  derived files to related files (`derived<TAB>related`, relative to the directory);
  `--include`/`--exclude` select files and `--jobs` sets the number of processes. Re-running on
  unchanged files gives byte-identical output, so `diff` shows what changed between releases.
- **Offline by default.** No network access is made unless `--online` is given. Then only the
  identifiers and URLs found in the header are resolved (DOIs through doi.org, CURIEs through
  identifiers.org, http(s) URLs as given), never file contents; private and loopback
  addresses are refused, and the report marks the results as time-dependent.
- Exit codes: 0 assessed (whatever the statuses), 1 an input could not be read, 2 usage error,
  3 with `--fail-on-mismatch` when a recorded link does not match the related file.

`scripts/bench_assess.py` (checkout only) times batch mode on a synthetic 200-file release.

Indicator identifiers and titles from: FAIR Data Maturity Model Working Group (2020). FAIR Data
Maturity Model. Specification and Guidelines. Research Data Alliance. doi:10.15497/rda00050.
Licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). File-header interpretations
are adaptations by FAIR-bioHeaders and are not endorsed by the RDA.

## Claude Code plugin

[`plugins/fair-bioheaders`](plugins/fair-bioheaders) is a Claude Code plugin with a skill
that tells Claude how to add, verify, convert and strip FAIR-bioHeaders headers with
these commands, without inventing metadata or editing checksums by hand. To install it
in Claude Code:

```text
/plugin marketplace add FAIR-bioHeaders/FAIR-bioHeaders-Tools
/plugin install fair-bioheaders@fair-bioheaders
```

## Python

```python
from bioheaders import fhr

metadata = fhr()
with open("examples/example.fhr.yaml", encoding="utf-8") as stream:
    metadata.input_yaml(stream)
metadata.fhr_validate()
print(metadata.output_json())
```

Input methods accept text, UTF-8 bytes, or readable streams. Optional fields stay
absent until supplied. The mapping is preserved across supported format round
trips; HTML values are escaped and explicitly typed. Keywords can initialize an
instance (`fhr(genome="example")`), and fields remain accessible as attributes.
The installed schema is loaded from package resources rather than the working
directory, so commands work outside the checkout. No schema is downloaded at runtime.
`bioheaders.cli` holds the command implementations and the byte-level helpers
(`checksum`, `combine`, `strip_header`, `open_input`, `write_to`, and others).

JSON-LD uses `output_jsonld(export=None)` and
`input_jsonld(stream, ignore_unknown_terms=False, warn=None)`. The
`bioheaders.jsonld` module is a provisional API: `CONTEXT` (the bundled FHR
context), `FHP_CONTEXT` (the bundled FHP context), `KNOWN_CONTEXT_URLS`,
`FHP_KNOWN_CONTEXT_URLS`, `to_jsonld(data, export=None)`,
`from_jsonld(document, *, ignore_unknown_terms=False, warn=None)`,
`fhp_to_jsonld(data)`, `fhp_canonical_record(document, warn=None)`,
`is_canonical(document)`, `fhp_is_canonical(document)`, `unmapped_keys(data)`,
`fhp_unmapped_keys(data)` and `bioschemas_missing(document)`.
`bioheaders.fhp_microdata` is the FHP microdata reader/writer used by
`input_microdata` and `output_microdata`: `read_page`, `extract`,
`write_page`, `resolve_schema` and `has_fhp_scope`.

`bioheaders.assess` is a provisional API: `assess_file(path, related=None, online=False,
record_limit=1000)` returns one report and `assess_release(paths, output_dir, pairs=None,
jobs=None, online=False)` writes a release's reports and returns its summary, as plain dicts
that follow the JSON Schemas in `bioheaders/assess/data/`.

## Renamed from fhr

In 0.4.0 the PyPI package `fhr` was renamed `fair-bioheaders`, the Python package
`fhr` was renamed `bioheaders`, and the repository moved from FHR-File-Converter
to [FAIR-bioHeaders-Tools](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools)
(old links redirect). The new names leave room for other FAIR-bioHeaders header
types. Nothing that worked with 0.3 stops working:

- The `fhr-*` commands are unchanged and print no deprecation notices, so
  scripts and pipelines that read their output or stderr keep working. They are
  not deprecated, but new scripts can use `bioheaders`.
- `import fhr`, `from fhr import fhr`, and `from fhr.cli import ...` still work:
  `fhr` and `fhr.cli` are the same module objects as `bioheaders` and
  `bioheaders.cli`. Importing `fhr` emits one `DeprecationWarning`; replace
  `fhr` with `bioheaders` in imports. The `fhr` metadata class keeps its name.
- `pip install fhr` installs `fhr`, a compatibility package without code
  that requires the same version of `fair-bioheaders`, so existing requirements
  and `pip install -U fhr` keep working. Prefer `fair-bioheaders` in new
  requirements. The compatibility package also installs the `fhr-*` commands, so
  if you uninstall `fhr` 0.4 later, restore them with
  `python -m pip install --force-reinstall --no-deps fair-bioheaders`.
- In an environment that still has `fhr` 0.3, run `python -m pip uninstall fhr`
  before `python -m pip install fair-bioheaders` (or upgrade with
  `python -m pip install -U fhr`); otherwise the old `fhr` package files shadow
  the new compatibility module.
- Citations and Zenodo DOIs are unchanged.

Checksum helpers require SHA-512/256 support in the Python build. Some Apple
system Python builds omit it; use an OpenSSL-enabled Python distribution.
Metadata conversion and validation do not require that hash implementation.

## v0.3 compatibility and identity

- Required fields and `schemaVersion: 1` remain unchanged since v0.3.0. FHR v0.4
  (`schemaVersion: '2.0'`) tightens constraints; files that cite a v0.3 release, or
  the raw-main URL with `schemaVersion: 1`, are still checked against it (see
  [schema versions](#schema-versions-and-which-schema-is-used)).
- `assemblySoftware` accepts a legacy string or optional structured software
  objects with name, URI, version, and command options. `assemblyProtocol` is a URI.
- `vitalStats.N90` is base pairs; `vitalStats.gcContent` is 0–100 percent.
- Optional `seqcol_id` stores a supplied 32-character base64url top-level refget
  digest. The converter preserves it; it does not compute or verify SeqCol identity.
- Checksums use base64 SHA-512/256 of all original file bytes except the one scalar
  checksum header line, including its newline. Metadata is covered. MD5 hex and
  payload-only checksums from old examples are not valid v0.3 checksums; recombine
  metadata with the original sequence file to calculate the new value.
- The checksum value must be a single-line scalar on the checksum line. Header
  lines must be UTF-8 and must not contain U+0085, U+2028, or U+2029. FASTA/GFA
  files must not begin with a UTF-8 byte order mark. Other sequence bytes may use
  any encoding.
- Metadata must be JSON-compatible: duplicate keys, YAML anchors, aliases, and
  merge keys are rejected.
- `;~`/`#~` lines must form the leading header block, before the first FASTA `>`
  line or the first GFA record line; ordinary comments and blank lines may be
  mixed in. A `;~`/`#~` line after sequence data, including a concatenated
  second file, is an error.
- HTML exports use FHR item scopes and `data-fhr-type` annotations for lossless
  arrays, numbers, objects, and strings. External microdata must represent nested
  items properly; incomplete legacy markup may need regeneration.
- Incomplete constructors now emit missing fields rather than empty defaults.
  Validate after loading to obtain actionable schema errors. Obsolete positional
  constructor arguments should be converted to keywords.

See the [format reference](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/FORMAT.md)
and [release notes](CHANGELOG.md). JSON/YAML/HTML example identifiers are synthetic.
The FASTA/GFA fixtures contain verified FHR checksums; their SeqCol IDs are placeholders.

## Container image

Each release from 0.5.0 on has a container image, built from the release's wheel by
[`container.yml`](.github/workflows/container.yml) for `linux/amd64` and `linux/arm64`:

- `ghcr.io/fair-bioheaders/fair-bioheaders:X.Y.Z` (also `X.Y`, and `latest` for the
  newest release);
- the same tags on Docker Hub, once the maintainers add the Docker Hub secrets (see
  [Releasing the image](#releasing-the-image)).

The image has no entrypoint, so that workflow managers can run shell scripts in it; give
the command:

```bash
docker run --rm -v "$PWD:/data" -w /data ghcr.io/fair-bioheaders/fair-bioheaders:0.5.0 \
    bioheaders combine metadata.yaml assembly.fa.gz -o assembly.fhr.fa.gz
```

It runs as an unprivileged user (uid 1000) and includes the optional JSON-LD reader. To
build it locally from a checkout:

```bash
poetry build -f wheel
docker build --build-arg VERSION="$(poetry version --short)" -t fair-bioheaders .
```

The runtime dependencies are hash-locked in [`docker/requirements.txt`](docker/requirements.txt),
compiled from [`docker/requirements.in`](docker/requirements.in); the wheel is installed
on top of them with `--no-deps`, and `pip check` fails the build if they no longer fit.

### Nextflow modules

> **Moved.** The nf-core-style modules and the Dockstore workflow are now maintained in
> [FAIR-bioHeaders/FAIR-bioHeaders-Nextflow](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Nextflow) (FAIR-bioHeaders/FAIR-bioHeaders-Nextflow#21), which adds
> protein FASTA (FHP) and `FAIRBIOHEADERS_VALIDATE` for standalone metadata. The copies
> under `nextflow/` here are frozen at fair-bioheaders 0.8.2 and receive no further
> changes; they will be removed once the FAIR-bioHeaders-Nextflow workflow is registered on Dockstore.
> The Dockstore entry below keeps its versions as history.

[`nextflow/modules/nf-core/fairbioheaders`](nextflow/modules/nf-core/fairbioheaders) holds
two modules written to the current nf-core module template, so that pipelines such as
nf-core/genomeassembler can use them and they can be submitted to nf-core/modules:

| Module | Input | Output |
| --- | --- | --- |
| `FAIRBIOHEADERS_COMBINE` | `tuple val(meta), path(metadata), path(sequence)`: FHR or FHGFF3 metadata (JSON or YAML) and a FASTA, GFA or GFF3 file (`.gff3`/`.gff`), plain or gzip/BGZF | `sequence`: `${prefix}.fhr.fa`, `.fhr.gfa` or `.fhgff3.gff3` (`.gz` when the input was compressed), with the validated header and its checksum |
| `FAIRBIOHEADERS_VERIFY` | `tuple val(meta), path(sequence)`: a FASTA, GFA or GFF3 file with an FHR or FHGFF3 header | `report`: `${prefix}.verify.txt`. The task fails when the header is invalid or the checksum does not match |

Both emit their version on the `versions` topic, and accept `task.ext.args` and
`task.ext.prefix`. These two cover what an assembly pipeline needs: attach metadata to each
assembly it publishes, and check published files. Metadata creation stays in the pipeline,
which knows the sample's provenance.

To use them before they are in nf-core/modules, copy the `fairbioheaders` directory into
the pipeline's `modules/nf-core/` and include them as usual:

```nextflow
include { FAIRBIOHEADERS_COMBINE } from './modules/nf-core/fairbioheaders/combine/main'
include { FAIRBIOHEADERS_VERIFY  } from './modules/nf-core/fairbioheaders/verify/main'
```

They install `bioconda::fair-bioheaders` with conda, or run its BioContainers image
(`quay.io/biocontainers/fair-bioheaders`, or the Galaxy depot's Singularity image), both
pinned to 0.8.2, which includes `pyld` (the `jsonld` extra), so they also read JSON-LD
metadata that is not in the canonical form, such as expanded JSON-LD.
Their tests use the nf-core test data and run with
`cd nextflow && nf-test test --profile docker`
([`nextflow-modules.yml`](.github/workflows/nextflow-modules.yml) runs them in CI and
checks that each module's container and Bioconda pin name the same version).
`nf-core modules lint` passes the Bioconda and container registry checks. Before
submitting the modules to nf-core/modules, run `nf-core modules containers create` for
each module if reviewers ask for Seqera containers in place of BioContainers.

### Nextflow workflow and Dockstore

[`nextflow/workflows/fairbioheaders`](nextflow/workflows/fairbioheaders) is a minimal
workflow that runs the two modules in turn: combine metadata with each FASTA, GFA or GFF3
file in a samplesheet (or one `--metadata`/`--sequence` pair), then verify the result.
It has `docker`, `singularity`, `apptainer`, `conda` and `test` profiles and runs
`fair-bioheaders` 0.8.2 from the modules' BioContainers image, or under conda from the
same Bioconda package; both include `pyld`, so the workflow also reads JSON-LD metadata
that is not in the canonical form. [`.dockstore.yml`](.dockstore.yml) registers it on
[Dockstore](https://dockstore.org) as
[`github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/fair-bioheaders`](https://dockstore.org/workflows/github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/fair-bioheaders);
see its [README](nextflow/workflows/fairbioheaders/README.md). The toolkit is also listed on
bio.tools as [`fair-bioheaders`](https://bio.tools/fair-bioheaders).

For the maintained modules, this workflow and the full pipeline (metadata creation,
conversion, stripping, GFF3 validation and FHP protein FASTA), see
[FAIR-bioHeaders/FAIR-bioHeaders-Nextflow](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Nextflow).

```bash
nextflow run FAIR-bioHeaders/FAIR-bioHeaders-Tools \
    -main-script nextflow/workflows/fairbioheaders/main.nf \
    -profile docker --input samplesheet.csv --outdir results
```

### Galaxy tools

[`galaxy/tools/fair_bioheaders`](galaxy/tools/fair_bioheaders) holds Galaxy wrappers for
`combine`, `verify` (with `validate`), `strip` and `convert`, for plain and gzip FASTA,
GFA and GFF3 datasets. They are in [galaxyproject/tools-iuc](https://github.com/galaxyproject/tools-iuc/tree/main/tools/fair_bioheaders) (the canonical copy) and on the main Galaxy Tool Shed as [`suite_fair_bioheaders`](https://toolshed.g2.bx.psu.edu/view/iuc/suite_fair_bioheaders) (owner `iuc`). They require `fair-bioheaders` from Bioconda. [`galaxy-tools.yml`](.github/workflows/galaxy-tools.yml) lints them with planemo
and runs their tests against this checkout; see [`galaxy/README.md`](galaxy/README.md).

### Releasing the image

Pushing a release tag runs [`release.yml`](.github/workflows/release.yml), which calls
`container.yml` after the GitHub release is created. That builds the image from the
release wheel, smoke-tests it on both platforms and pushes it. To publish the image of an
existing release, such as 0.5.0, run the **Container image** workflow by hand with that
tag.

GHCR needs no setup. For Docker Hub, a maintainer adds two repository secrets,
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub access token with read and write
access), and optionally the repository variable `DOCKERHUB_NAMESPACE` when the images belong
to an organisation rather than that user. Without the secrets the workflow pushes to GHCR
only and says so. After the first push, make the GHCR package public in the organisation's
package settings if it is not already.

See [CONTRIBUTING](CONTRIBUTING.md), [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md),
[SECURITY](SECURITY.md), and [AGENTS](AGENTS.md) for project guidance.

## Citing FHR

Chicago bibliography entries are used below. Cite the published paper for a
general description of FHR; cite the specification or converter when using that
resource directly. The software and specification links are concept DOIs; for a
specific release, use the corresponding version DOI from Zenodo. Authors and
years follow the records resolved by the concept DOIs at the v0.3 documentation
update, and can change as later records are published.

### Published paper

Wright, Adam, Mark D. Wilkinson, Christopher Mungall, Scott Cain, Stephen Richards, Paul Sternberg, Ellen Provin, Jonathan L. Jacobs, Scott Geib, Daniela Raciti, Karen Yook, Lincoln Stein, and David C. Molik. “FAIR Header Reference Genome: A TRUSTworthy Standard.” *Briefings in Bioinformatics* 25, no. 3 (2024): bbae122. https://doi.org/10.1093/bib/bbae122.

### Specification

Molik, David. *FHR Specification*. Data set. 2022. https://doi.org/10.5281/zenodo.6762549.

### Converter

Molik, David, and Adam Wright. *FHR File Converter*. Computer software. 2024. https://doi.org/10.5281/zenodo.6762547.

Machine-readable entries are maintained in
[FHR-Citation](https://github.com/FAIR-bioHeaders/FHR-Citation/blob/main/citation.bib).

## Licensing

[![License: MPL-2.0](https://img.shields.io/badge/License-MPL--2.0-blue.svg)](LICENSE)

New project contributions from March 2025 onward use [MPL-2.0](LICENSE). David Molik left USDA in February 2025. Historical USDA public-domain material remains public domain within the United States; its original notice is preserved in LICENSE. Previously granted permissions and third-party terms remain intact. The project includes both historical material and subsequent MPL-2.0 contributions; file notices and history identify provenance.
