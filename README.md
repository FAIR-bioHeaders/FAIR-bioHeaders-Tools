# FAIR-bioHeaders Tools

[![Tests](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/actions/workflows/pytest.yaml/badge.svg?branch=main)](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/actions/workflows/pytest.yaml)
[![Specification DOI](https://img.shields.io/badge/Specification_DOI-10.5281%2Fzenodo.6762549-blue)](https://doi.org/10.5281/zenodo.6762549)
[![File Converter DOI](https://img.shields.io/badge/File_Converter_DOI-10.5281%2Fzenodo.6762547-blue)](https://doi.org/10.5281/zenodo.6762547)

Convert and validate FAIR-bioHeaders Reference genome (FHR) metadata in JSON,
YAML, JSON-LD, FASTA, GFA, and HTML microdata. See
[FHR-Specification](https://github.com/FAIR-bioHeaders/FHR-Specification) for the
schema and metadata design. This is the `fair-bioheaders` package, version
**0.5.0**, formerly the FHR File Converter (`fhr`); see
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

`combine`, `strip`, and `verify` (also called `checksum`) take the FASTA or GFA
type from the sequence file's extension, ignoring `.gz` or `.bgz`; give
`--type fasta` or `--type gfa` for stdin or other extensions. `bioheaders
--version` prints the version and `bioheaders COMMAND --help` describes each
command. The original commands remain available with the same options and output:

| `bioheaders` command | Original command |
| --- | --- |
| `convert INPUT OUTPUT` | `fhr-convert` |
| `validate INPUT` | `fhr-validate` |
| `combine METADATA SEQUENCE` | `fhr-fasta-combine`, `fhr-gfa-combine` |
| `strip INPUT [OUTPUT]` | `fhr-fasta-strip`, `fhr-gfa-strip` |
| `verify INPUT` | `fhr-fasta-validate`, `fhr-gfa-validate` |

`convert INPUT OUTPUT` detects `.json`, `.yaml`/`.yml`, `.jsonld`, `.fasta`/`.fa`/`.fna`,
`.gfa`, and `.html` from extensions. It validates metadata before writing output;
FASTA/GFA output contains a metadata header only. To include sequence data, use
`combine METADATA SEQUENCE [-o OUTPUT]`, whose default output is `SEQUENCE.fhr.fasta`
or `SEQUENCE.fhr.gfa` with the last extension replaced. Existing FHR header lines
are replaced. Inputs are not overwritten by sequence helpers.

`strip INPUT [OUTPUT]` writes to stdout if OUTPUT is omitted. Only FHR-prefixed
lines are removed; other bytes, including ordinary comments and CRLF endings,
are preserved. `validate` checks metadata, while `verify` (`fhr-fasta-validate`,
`fhr-gfa-validate`) also verifies the exact-byte file checksum. Failures exit
with status 1.

FASTA/GFA commands stream their input in 1 MiB chunks, so memory use does not grow
with file size (about 35 MB peak for a 1 GB FASTA). Validate reads the file once;
combine reads it twice. FHR header lines are limited to 16 MiB in total. Outputs
are written to a temporary file in the destination directory and then renamed,
so a failed command leaves no partial output.

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
`FastaFile`) rejects FASTA files containing `;` lines, compressed or not. Keep
the FHR file as the record of provenance and index a stripped copy:

```sh
bioheaders strip genome.fhr.fa.gz genome.fa.gz   # writes BGZF
samtools faidx genome.fa.gz                       # .fai and .gzi
```

The stripped file has the same sequence bytes; `bioheaders verify` on the FHR
file still checks the original. Which other tools accept FHR files is surveyed in
[TOOL_COMPATIBILITY.md](https://github.com/FAIR-bioHeaders/FHR-Specification/blob/main/docs/TOOL_COMPATIBILITY.md);
support for leading `;` lines in htslib is proposed in
[samtools/htslib#2103](https://github.com/samtools/htslib/issues/2103).

`-` reads stdin or writes stdout: the input of verify, strip, combine (the
sequence), convert, and validate, and the output of strip, convert, and
`combine -o`. Combine of stdin writes stdout by default. Convert and validate
need `--from FORMAT` for stdin and convert needs `--to FORMAT` for stdout
(`json`, `yaml`, `jsonld`, `fasta`, `gfa`, or `html`); the `bioheaders` sequence commands
need `--type` for stdin. Stdin is read
once: combine spools the stripped sequence to a temporary file in `TMPDIR` (as
large as the sequence) while hashing it. Strip from stdin to stdout writes as it
reads, so an error late in the input can follow partial output; check the exit
status. Strip of a file to stdout still checks the whole file before writing.

### JSON-LD

```bash
bioheaders convert examples/example.fhr.json example.fhr.jsonld
bioheaders convert example.fhr.jsonld back.json
bioheaders convert --export-context export.yaml examples/example.fhr.json page.jsonld
```

A `.jsonld` file is the FHR record with its own keys, an embedded JSON-LD context and
`@type` on the record (`Dataset`) and its nested nodes, so the same document is FHR
metadata and schema.org linked data. The format is defined in FHR-Specification
[docs/JSONLD.md](https://github.com/FAIR-bioHeaders/FHR-Specification/blob/main/docs/JSONLD.md),
and `examples/example.fhr.jsonld` is byte-identical to the specification's example. The
context is bundled (`bioheaders/fhr.context.jsonld`, a copy of the specification's
`jsonld/fhr.context.jsonld`) and never fetched; writing and reading the canonical form need no
extra package, and everything works offline.

- Authors are typed `Person` with an ORCID iD, `Organization` with a ROR ID, and otherwise
  `Agent` (not classified). A `documentation` value that is an absolute URL is written as
  `subjectOf`, text as `documentation` (`schema:description`).
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
- Other JSON-LD forms (expanded, compacted with another context such as a schema.org
  `@vocab`, or one record in `@graph`) are read by JSON-LD expansion (rules J3 to J5). This
  needs the `jsonld` extra, PyLD, on Python 3.10 or later:
  `pip install "fair-bioheaders[jsonld]"`. Contexts are served only from the bundled copy, so
  a remote context such as `https://schema.org/` is refused
  (`FHR: JSON-LD context is not available offline: https://schema.org/`). A term that maps to
  no FHR field fails the read
  (`FHR: JSON-LD term not in the FHR mapping: http://schema.org/keywords (at the record)`);
  `convert` and `validate` take `--ignore-unknown-terms` to report such terms as warnings
  instead. The document must describe exactly one record.

### Protein FASTA (draft FHP header)

The tools also read and write the **draft** FAIR header for protein FASTA, FHP
(FHR-Specification [docs/FHP.md](https://github.com/FAIR-bioHeaders/FHR-Specification/blob/main/docs/FHP.md)).
FHP is not released yet. A record whose `schema` is an `fhp.json` URL in
FHR-Specification is validated against the bundled FHP schema. Every other record
is validated as FHR, exactly as before. `.faa` is a FASTA extension.

```bash
bioheaders validate proteins.fhp.json             # FHP metadata is valid.
bioheaders combine proteins.fhp.json proteins.faa # writes proteins.fhp.fasta
bioheaders verify proteins.fhp.fasta
bioheaders strip proteins.fhp.fasta proteins.faa
```

Header handling does not depend on the alphabet. Stops (`*`), U, O, B, Z, J, X,
lower case and gaps are ordinary bytes: they are hashed and preserved exactly.
JSON, YAML and the FASTA header work for FHP. JSON-LD and HTML microdata output
are refused for FHP until the specification defines them.

`bioheaders verify-links FILE PARENT...` checks the parent files recorded in a
header's `derivedFrom` against candidate files on disk. It computes each FASTA or
GFA candidate's FAIR-bioHeaders checksum from its bytes, and reports each recorded
parent as `matched`, `not matched` (a file of that header type has another
checksum) or `not checked`. GFF3 parents are always `not checked`, because GFF3
headers are not specified yet. A match confirms file identity, not correct
translation. The command never writes. Exit status 3 means a parent did not match;
with `--require-all`, a parent that could not be checked also gives 3.

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
FHR-Specification
[docs/FAIR_HEADER_GUIDELINE.md](https://github.com/FAIR-bioHeaders/FHR-Specification/blob/main/docs/FAIR_HEADER_GUIDELINE.md),
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
`bioheaders.jsonld` module is a provisional API: `CONTEXT` (the bundled context),
`KNOWN_CONTEXT_URLS`, `to_jsonld(data, export=None)`,
`from_jsonld(document, *, ignore_unknown_terms=False, warn=None)`,
`is_canonical(document)`, `unmapped_keys(data)` and `bioschemas_missing(document)`.

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

- The eight `fhr-*` commands are unchanged and print no deprecation notices, so
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

- Required fields and `schemaVersion: 1` remain unchanged since v0.3.0.
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

See the [format reference](https://github.com/FAIR-bioHeaders/FHR-Specification/blob/main/docs/FORMAT.md)
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

[`nextflow/modules/nf-core/fairbioheaders`](nextflow/modules/nf-core/fairbioheaders) holds
two modules written to the current nf-core module template, so that pipelines such as
nf-core/genomeassembler can use them and they can be submitted to nf-core/modules:

| Module | Input | Output |
| --- | --- | --- |
| `FAIRBIOHEADERS_COMBINE` | `tuple val(meta), path(metadata), path(sequence)`: FHR metadata (JSON or YAML) and a FASTA or GFA file, plain or gzip/BGZF | `sequence`: `${prefix}.fhr.fa` or `.fhr.gfa` (`.gz` when the input was compressed), with the validated header and its checksum |
| `FAIRBIOHEADERS_VERIFY` | `tuple val(meta), path(sequence)`: a FASTA or GFA file with an FHR header | `report`: `${prefix}.verify.txt`. The task fails when the header is invalid or the checksum does not match |

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

Their tests use the nf-core test data and run with
`cd nextflow && nf-test test --profile docker`
([`nextflow-modules.yml`](.github/workflows/nextflow-modules.yml) runs them in CI against
an image built from the pinned release's wheel). `nf-core modules lint` passes apart from
two checks that wait for Bioconda: the `bioconda::fair-bioheaders` package must exist, and
the container must come from an nf-core registry. Until then the modules use the GHCR
image. Once `fair-bioheaders` is on Bioconda, run `nf-core modules containers create` for
each module to replace the container line with the Seqera/BioContainers URLs, then submit
them to nf-core/modules.

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
