# FAIR-bioHeaders Nextflow workflow

A minimal Nextflow DSL2 workflow around the two
[nf-core-style modules](../../modules/nf-core/fairbioheaders) of this repository:

1. `FAIRBIOHEADERS_COMBINE` adds FAIR-bioHeaders metadata (FHR for FASTA and GFA, FHGFF3
   for GFF3) to each sequence file and calculates its checksum;
2. `FAIRBIOHEADERS_VERIFY` checks the headed file against the schema and the checksum.
   The run fails if a file does not verify.

It is registered on [Dockstore](https://dockstore.org) through
[`.dockstore.yml`](../../../.dockstore.yml) at the repository root.

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

- `<outdir>/combine/<id>.fhr.<ext>`: the sequence file with its metadata header
  (`.gz` when the input was compressed);
- `<outdir>/verify/<id>.verify.txt`: the verification report.

## Profiles

| Profile | Runs `bioheaders` from |
| --- | --- |
| `docker` | `ghcr.io/fair-bioheaders/fair-bioheaders:0.8.1` |
| `singularity`, `apptainer` | the same image, converted from Docker |
| `conda` | [`environment.yml`](environment.yml): `fair-bioheaders==0.8.1` from PyPI |
| `test` | the samplesheet in [`assets/test`](assets/test): a FASTA, a GFA and a GFF3 example |
| none | `bioheaders` on the `PATH` (`pip install fair-bioheaders`) |

Combine `test` with one of the others, for example `-profile test,docker`.
[`assets/test/params.json`](assets/test/params.json) is the same test as a parameter file
(`-params-file`), reading the samplesheet from GitHub; Dockstore lists it as the test
parameter file.

**Container and conda versions.** The modules pin the BioContainers image and Bioconda
package of `fair-bioheaders` 0.5.0, the newest on Bioconda, which predates GFF3 support and
the 0.8.1 security fixes. Until BioContainers and Bioconda have 0.8.1, `nextflow.config`
replaces them for both processes (`withName: 'FAIRBIOHEADERS_.*'`) with the project's own
0.8.1 image, built by [`container.yml`](../../../.github/workflows/container.yml) for each
release, and a conda environment that installs 0.8.1 from PyPI. Remove that override when
the modules move to 0.8.1.

The [`Nextflow workflow`](../../../.github/workflows/nextflow-workflow.yml) CI job builds
the 0.8.1 image from the release wheel and runs `-profile test,docker`.
