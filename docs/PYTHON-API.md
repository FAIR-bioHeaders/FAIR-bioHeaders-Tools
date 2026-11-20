# Python API guide

Install `fair-bioheaders` as in [Getting started](GETTING-STARTED.md).
The `bioheaders.fhr` class is the shared metadata container despite its historical
name. Its import is supported; the old `import fhr` emits a deprecation warning.
Prefer the CLI for complete file combine/strip/verify operations.

```python
from pathlib import Path
from bioheaders import fhr

record = fhr()
with Path("metadata.json").open("rb") as stream:
    record.input_json(stream)
record.fhr_validate()
Path("metadata.yaml").write_text(record.output_yaml(), encoding="utf-8")
```

Readers mutate the record; create a fresh instance per document. Loading metadata
and validating it are distinct actions: `input_json`/`input_yaml` parse and enforce
reader rules, while `fhr_validate()` validates the selected bundled contract.
`output_json()` and `output_yaml()` serialize metadata; they do not compute a
sequence checksum. `input_fasta`, `input_gfa` and `input_gff3` extract headers;
corresponding outputs write metadata headers, not complete sequence files.
`input_microdata`/`output_microdata` follow the selected type's HTML binding;
JSON-LD helpers have type-specific limits. See the capability matrix before
choosing a transport. Container metadata is available as `record.__dict__`;
copy it when retaining an independent snapshot.

| Helper | Purpose and boundary |
| --- | --- |
| `bioheaders.header_type(metadata)` | Selects header family from explicit metadata; does not infer sequence biology. |
| `bioheaders.selection.select_record(metadata)` | Record-aware schema selection including compatibility/version rules. |
| `bioheaders.schema_for(metadata)` | Returns selected schema; use the whole record rather than only a citation URL. |
| `bioheaders.cli.SequenceScan` | Internal streaming checksum/header scan used by sequence commands; CLI is the stable file interface. |
| `bioheaders.dcmi.export_assembly(source, context, output_dir)` | Returns a projection/rejection report; filesystem failures raise `OSError`, and an existing output path is refused. See [DCMI guide](DCMI-EXPORT.md). |
| `bioheaders.assess.related` | Internal local sequence/link evidence; VCF MD5 identifiers are not security checksums. |

Parsing/validation errors include `ValueError`, YAML parser errors and
`jsonschema.ValidationError`; filesystem operations can raise `OSError`. Handle
these at your application boundary, retain stderr/report evidence and distinguish
invalid input from unavailable prerequisites. Do not catch every exception and
turn it into a valid/not-run result. The CLI normalizes expected errors to a
nonzero exit status; direct API callers own their exception handling.

Online assessment is opt-in; JSON-LD contexts and contract selection are offline.
Passing metadata validation does not establish checksum validity, parent identity,
biological derivation or native model validity. Preserve original file bytes and
recombine after metadata changes. Internal/private helpers can change; use the
versioned package and CLI contract for a long-lived integration.

Normal released FHT 1.0 needs no switch. Historical owning FHT replay requires
`BIOHEADERS_EXPERIMENTAL_FHT=1`; native FHGM checking independently requires
`BIOHEADERS_EXPERIMENTAL_FHGM=1`. These gates also apply to library callers.
A closed gate or unavailable prerequisite must not become a model pass. See
[the native model guide](FHGM-MODEL.md) for contract selection and layer outcomes.
