---
name: fair-bioheaders
description: Add, check, convert or remove FAIR-bioHeaders provenance headers in genome, protein and annotation files - FHR headers in reference genome FASTA or GFA, FHP headers in protein FASTA, FHGFF3 headers in GFF3 - and check file links and FAIR header quality. Use when the user wants to embed metadata or provenance (species, authors, version, checksum) in a FASTA, GFA or GFF3 file, validate or verify a `;~` or `#~` header, strip one so a tool accepts the file, or convert header metadata to JSON, YAML, JSON-LD or HTML.
---

# FAIR-bioHeaders headers

A FAIR-bioHeaders header is a block of YAML lines at the top of a data file:
`;~key: value` lines in FASTA, `#~key: value` lines in GFA and GFF3 (after
`##gff-version 3`). The metadata validates against a JSON Schema, and a
SHA-512/256 checksum covers the whole file except the checksum line.

| Header | File | Schema to cite in `schema` | `schemaVersion` |
| --- | --- | --- | --- |
| FHR | reference genome FASTA or GFA | `https://w3id.org/fair-bioheaders/fhr/v0.4.0` | `'2.0'` |
| FHP | protein FASTA | `https://w3id.org/fair-bioheaders/fhp/v0.4.0` | `'1.0'` |
| FHGFF3 | GFF3 annotation | `https://w3id.org/fair-bioheaders/fhgff3/v0.4.0` | `'1.0'` |

Specification: https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification
(format rules R1 to R11 in `docs/FORMAT.md`).

## Rules

- **Never invent metadata.** Species, authors, ORCIDs, accessions, versions,
  dates, SeqCol digests and parent checksums come from the user or from files
  they point to. Ask for anything missing; do not fill in placeholders.
- **Never compute or edit the checksum by hand.** `bioheaders combine` writes
  it. Any edit to the file after combining invalidates it: change the metadata
  and combine again.
- **Use the tool to write headers.** It escapes `>` and `@` in FASTA header
  values as `\x3E` and `\x40` (rule R11), because kseq-based readers (BWA,
  minimap2, seqtk, samtools dict) otherwise start a bogus record there.
  Reading the header returns the real characters.

## 1. Install

```bash
pip install fair-bioheaders        # command: bioheaders (Python 3.9+)
bioheaders --version
```

## 2. Write the metadata (YAML or JSON)

Fields every type requires: `schema`, `schemaVersion`, `taxon` (`name`, and
`uri` as `https://identifiers.org/taxonomy:<NCBI taxon id>`), `version`,
`metadataAuthor` (list of `name`, optional ORCID `uri` such as
`https://orcid.org/0000-0002-1825-0097`, optional `nameType`: `Personal` or
`Organizational`) and `dateCreated` (`YYYY-MM-DD`). `checksum` is also required
in the finished file, but leave it out of the metadata you give `combine`.

Then by type:

- **FHR:** `genome` (assembly name), `assemblyAuthor` (list, like
  `metadataAuthor`), `masking` (`not-masked`, `hard-masked`, `soft-masked`,
  `repeat-masked` or `unknown`).
- **FHP:** `proteome` (protein set name) and `sourceType`: `predicted`,
  `database` or `mixed`.
- **FHGFF3:** `annotation` (annotation name) and a genome link, one of:
  - `genomeReference` with `accession` (assembly accession with version) and
    `seqcol_id` (its GA4GH SeqCol digest), or
  - a `derivedFrom` item with `headerType: FHR`, `relationship: annotates` and
    the `checksum` of the genome's FHR file.

Example FHR metadata (values must come from the user):

```yaml
schema: https://w3id.org/fair-bioheaders/fhr/v0.4.0
schemaVersion: '2.0'
genome: Example assembly name
taxon:
  name: Homo sapiens
  uri: https://identifiers.org/taxonomy:9606
version: 1.0.0
metadataAuthor:
- name: Metadata Author
assemblyAuthor:
- name: Assembly Author
dateCreated: '2026-01-31'
masking: soft-masked
```

Optional fields (license, accession, software, statistics, SeqCol ID and more)
are listed in the schema. Add them only with values the user supplies.

## 3. Add the header

```bash
bioheaders combine metadata.yaml genome.fa -o genome.fhr.fa           # FHR, FASTA
bioheaders combine metadata.yaml graph.gfa -o graph.fhr.gfa           # FHR, GFA
bioheaders combine metadata.yaml proteins.faa -o proteins.fhp.fasta   # FHP
bioheaders combine metadata.yaml annotation.gff3 -o annotation.fhgff3.gff3   # FHGFF3
```

The type comes from the file extension (`.gz` and `.bgz` are ignored); use
`--type fasta|gfa|gff3` for stdin (`-`) or unusual names. `combine` validates
the metadata and fails with the schema error if a field is wrong.

## 4. Check a file

```bash
bioheaders verify genome.fhr.fa      # metadata valid and checksum verified
bioheaders validate metadata.yaml    # metadata alone (needs a checksum field)
```

`verify` prints `Checksum verified.` on success. A warning about a raw `>` or
`@` (rule R11) does not fail the check; recombine to fix it.

## 5. Check parent links (derivedFrom)

```bash
bioheaders verify-links annotation.fhgff3.gff3 genome.fhr.fa
```

Each recorded parent is reported `matched`, `not matched` or `not checked`.
Exit code 3 means a parent did not match. A match proves file identity only,
not that the annotation is correct.

## 6. Remove the header for tools that reject it

Many FASTA tools reject a leading `;` block: samtools faidx (and htslib,
pysam `FastaFile`, bedtools getfasta), Picard, Bowtie2, HISAT2, STAR, salmon,
UCSC faToTwoBit, pyfaidx and others. Make a plain copy; every other byte is
kept:

```bash
bioheaders strip genome.fhr.fa genome.fa
samtools faidx genome.fa
```

htslib-based tools (samtools faidx with a region, bcftools, pysam `FastaFile`,
bedtools getfasta, JBrowse, VEP) can instead read the FHR file itself through an
index written by `bioheaders faidx` (0.8.3 and later). Write the index
before running them, and again after any change to the file; `samtools faidx
genome.fhr.fa` without a region still fails:

```bash
bioheaders faidx genome.fhr.fa          # genome.fhr.fa.fai (.gzi too for BGZF)
samtools faidx genome.fhr.fa chr1:1-1000
```

In Biopython, read FHR FASTA with `SeqIO.parse(path, "fasta-pearson")`; the
default `"fasta"` format rejects the header. GFF3 and GFA tools generally
accept `#~` lines as comments.

## 7. Convert the metadata

```bash
bioheaders convert genome.fhr.fa metadata.json    # or .yaml, .jsonld, .html
```

## 8. Assess any file's header

```bash
bioheaders assess genome.fa    # FAIR checklist for a FASTA, GFF3, GAF, VCF or GFA header; offline
```

`assess` works on files without an FHR header too and suggests what to add.
