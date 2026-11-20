# Getting started with the Python toolkit

The published package is **fair-bioheaders 0.13.1** (Python 3.9+). Install it in
an isolated environment; the command is `bioheaders`, the import is `bioheaders`.
The old `fhr` package/import is a compatibility route, not a second implementation.
For reproducible work record `bioheaders --version` with your inputs and report.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install fair-bioheaders==0.13.1
bioheaders --version
bioheaders --help
```

Use `python -m pip install 'fair-bioheaders[jsonld]==0.13.1'` on Python 3.10+
when noncanonical JSON-LD input needs PyLD. Canonical JSON-LD uses bundled
contexts without network access. FHT and FHGFF3 JSON-LD are unsupported.
See [distribution choices](DISTRIBUTION.md) for containers and integrations;
a source checkout ahead of a release does not establish shipped behavior.

## Try a complete offline round trip

From a checkout of this repository, after installation:

```sh
demo_dir=$(mktemp -d "${TMPDIR:-/tmp}/bioheaders-demo.XXXXXX")
printf '>demo\nACGT\n' > "$demo_dir/sequence.fa"
bioheaders convert examples/example.fhr.yaml "$demo_dir/metadata.json"
bioheaders validate "$demo_dir/metadata.json"
bioheaders combine "$demo_dir/metadata.json" "$demo_dir/sequence.fa" -o "$demo_dir/sequence.fhr.fa"
bioheaders verify "$demo_dir/sequence.fhr.fa"
bioheaders strip "$demo_dir/sequence.fhr.fa" "$demo_dir/stripped.fa"
cmp "$demo_dir/sequence.fa" "$demo_dir/stripped.fa"
```

These are synthetic demonstration metadata and sequence bytes, not an assertion
about a biological assembly. Supply your own measured metadata for real files.
`combine` writes the checksum. Editing any resulting bytes requires recombining;
never hand-edit the checksum. Outputs here use explicit paths; rerunning overwrites
those demonstration outputs. Do not use input paths as outputs.

## Choose the right check

| Command | Purpose (use `COMMAND --help` for exact options) |
| --- | --- |
| `convert INPUT OUTPUT` | Reads and validates supported metadata before serialization; sequence-format output contains a header only. |
| `validate INPUT` | Metadata contract validity; it does not check whole-file identity or biology. |
| `combine METADATA SEQUENCE -o OUTPUT` | Writes metadata plus sequence with a computed file checksum. |
| `verify INPUT` | Metadata validity and exact-byte file checksum; not biological derivation. |
| `strip INPUT OUTPUT` | Removes metadata header lines while preserving ordinary sequence bytes. |
| `verify-links` | Checks explicitly supplied local parent files; identifiers alone do not establish derivation. |
| `faidx INPUT` | Builds header-aware indexes; strict readers may instead need a stripped file. |
| `metadata` | Builds metadata from explicitly supplied values; no invented provenance. |
| `assess INPUT` | Reports header quality and link evidence; online resolution is explicitly opt-in. |
| `export-dcmi` | Narrow, lossy descriptive export with its own context and rejection report. |
| `bioheaders-pin-audit` | Read-only advisory provenance audit; never changes pins. |

Use `bioheaders COMMAND --help` for exact options. CLI failures return status 1;
usage errors are reported by argparse. Warnings do not automatically mean failure.
Check stderr and structured reports, including unsupported and not-run outcomes.
For complete type/serialization/version support consult the
[capability matrix](CAPABILITY-MATRIX.md), not a success on a different type.

FHT 1.0 uses normal released validation. [Native FHGM 0.1](FHGM-MODEL.md) remains
an explicit implementation opt-in and reports model/base/checksum/feature layers
separately. A feature layer marked not-run never becomes a biological pass.
Historical draft replay is documented separately in [the draft guide](FHGM-DRAFT-LANE.md).

Metadata size, nesting, duplicate keys and unsafe YAML constructs are bounded or
refused. Sequence operations stream; metadata and native-model operations have
separate limits. Gzip input does not waive decompressed metadata limits. A large
sequence or hostile compression can still consume CPU, disk or elapsed time;
apply job limits when processing untrusted uploads. Online assessment is an
explicit network operation; ordinary contract selection uses bundled schemas.

## Develop and contribute

Clone the repository, install Poetry and run the checks in [AGENTS.md](../AGENTS.md).
Do not run a checkout as proof of an installed wheel: build/install in an isolated
environment and run from outside the checkout. Some full tests require samtools,
bgzip, pysam and exact external conformance checkouts; report missing checks.
Every PR receives another actual model's review, CI failures/findings are fixed,
and a human merges. The [maintenance record](ROUND16-MAINTENANCE.md) describes the
current audit and handoff; it does not authorize a release or schema update.

HTML readers implement the specified bounded inline-style rules, not a browser
CSS cascade or arbitrary visual-concealment detection. Inspect rendered pages
for publication; external CSS/classes can change appearance. Compression labels
from a short stdin peek are advisory; validation still inspects and reads bytes.
