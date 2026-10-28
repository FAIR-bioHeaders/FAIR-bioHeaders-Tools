# FAIR-bioHeaders Nextflow workflow

> **Moved.** The nf-core-style modules and the Dockstore workflow are now maintained in
> [FAIR-bioHeaders/FAIR-bioHeaders-Nextflow](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Nextflow) (FAIR-bioHeaders/FAIR-bioHeaders-Nextflow#21), which adds
> protein FASTA (FHP) and `FAIRBIOHEADERS_VALIDATE` for standalone metadata. The copies
> under `nextflow/` here are frozen at fair-bioheaders 0.8.2 and receive no further
> changes; they will be removed once the FAIR-bioHeaders-Nextflow workflow is registered on Dockstore.
> This Dockstore entry keeps its versions as history.

A minimal Nextflow DSL2 workflow around the two
[nf-core-style modules](../../modules/nf-core/fairbioheaders) of this repository:

1. `FAIRBIOHEADERS_COMBINE` adds FAIR-bioHeaders metadata (FHR for FASTA and GFA, FHGFF3
   for GFF3) to each sequence file and calculates its checksum;
2. `FAIRBIOHEADERS_VERIFY` checks the headed file against the schema and the checksum.
   The run fails if a file does not verify.

It is registered on [Dockstore](https://dockstore.org) through
[`.dockstore.yml`](../../../.dockstore.yml) at the repository root.

The maintained copy of this workflow, its modules and the full pipeline are in
[FAIR-bioHeaders/FAIR-bioHeaders-Nextflow](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Nextflow) under `workflows/fairbioheaders`.

## Input

Either a samplesheet, a CSV file with the columns `id,metadata,sequence`:

```csv
id,metadata,sequence
genome,genome.fhr.yaml,genome.fa.gz
graph,genome.fhr.json,graph.gfa
annotation,annotation.fhgff3.yaml,annotation.gff3
```

```bash
nextflow run FAIR-bioHeaders/FAIR-bioHeaders-Tools \
    -main-script nextflow/workflows/fairbioheaders/main.nf \
    -profile docker --input samplesheet.csv --outdir results
```

or one file:

```bash
nextflow run FAIR-bioHeaders/FAIR-bioHeaders-Tools \
    -main-script nextflow/workflows/fairbioheaders/main.nf \
    -profile docker --metadata genome.fhr.yaml --sequence genome.fa.gz --outdir results
```

| Parameter | Description |
| --- | --- |
| `--input` | Samplesheet (CSV: `id,metadata,sequence`). Relative paths are relative to the samplesheet, which may be a URL. |
| `--metadata`, `--sequence` | Metadata (JSON, YAML, JSON-LD or HTML microdata) and one FASTA, GFA or GFF3 file, plain or gzip/BGZF, in place of `--input`. |
| `--id` | Output name for `--sequence` (default: its file name without the extension). |
| `--outdir` | Output directory (default `results`). |

The file type comes from the sequence file's extension: `.gfa` is GFA, `.gff3` or `.gff`
is GFF3, anything else is FASTA (`.gz`/`.bgz` ignored). In a clone of the repository, run
`nextflow run nextflow/workflows/fairbioheaders/main.nf ...` in the same way.

## Output

- `<outdir>/combine/<id>.fhr.<ext>` for FASTA and GFA, or
  `<outdir>/combine/<id>.fhgff3.gff3` for GFF3: the sequence file with its metadata
  header (`.gz` when the input was compressed);
- `<outdir>/verify/<id>.verify.txt`: the verification report.

## Profiles

| Profile | Runs `bioheaders` from |
| --- | --- |
| `docker` | the modules' BioContainers image, `quay.io/biocontainers/fair-bioheaders:0.8.2--pyhdfd78af_0` |
| `singularity`, `apptainer` | the modules' Galaxy depot Singularity image of the same build |
| `conda` | [`environment.yml`](environment.yml): `bioconda::fair-bioheaders=0.8.2` |
| `test` | the samplesheet in [`assets/test`](assets/test): a FASTA, a GFA and a GFF3 example, and the FASTA with expanded JSON-LD metadata |
| none | `bioheaders` on the `PATH` (`pip install "fair-bioheaders[jsonld]"`) |

Combine `test` with one of the others, for example `-profile test,docker`.
[`assets/test/params.json`](assets/test/params.json) is the same test as a parameter file
(`-params-file`), reading the samplesheet from GitHub; Dockstore lists it as the test
parameter file.

**Container and conda environment.** Both processes run the modules' container, the
BioContainers image of `fair-bioheaders` 0.8.2 (or the Galaxy depot's Singularity image of
it). The conda profile uses [`environment.yml`](environment.yml), which pins the same
Bioconda package as the modules; keep the two pins equal. From 0.8.2 the Bioconda package,
and so the image, includes `pyld`, the optional dependency (the `jsonld` extra) that
reading JSON-LD metadata in other than the canonical form needs, for example expanded
JSON-LD, so the workflow no longer replaces the modules' image with the project's GHCR
image.

The [`Nextflow workflow`](../../../.github/workflows/nextflow-workflow.yml) CI job checks
that the workflow sets no container and that its Bioconda pin equals the modules', then
runs `-profile test,docker`, including the expanded JSON-LD row of the test samplesheet.
