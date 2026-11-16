# Capability matrix

Generated from package registries, CLI probes and cited native tests.
Toolkit version: `0.11.0` in this checkout. Main may run
ahead of the published package with the same version number.
Released baseline: `v0.6.0`; FHR `2.1`, FHP `1.2`, FHGFF3 `1.2`.

Regenerate with `FHR_SPECIFICATION=/path/to/specification-at-tag python
scripts/render_capability_matrix.py`; add `--check --self-test` to verify
drift and deliberate failure controls. CI installs this checkout, checks
the matrix, then executes all six shared-suite formats independently.

| mark | meaning |
| --- | --- |
| yes | implemented; cited CLI probe or native test |
| no | refused or unimplemented; reason cited |
| n/a | operation does not apply to this representation |
| draft lane | explicit opt-in against pinned development bytes, never released support |
| partial | implemented with a named evidence limit |
| not here | FHGM runtime work remains in #135 |
| not verified | no positive or refusal evidence here |

`read` means validate; `write` covers combine/convert. `verify` checks
file integrity; `links` checks supplied parent identity; `index` is faidx.
The matrix records representative paths, not every option combination.
Evidence footnotes distinguish probes executed during rendering from
tests checked for existence. A cited test is not rerun by rendering.

## The grids

### FHR — contract `'2.1'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e1] | yes[^e2] | yes[^e3] | yes[^e4] | no[^r-family-gate][^e5] | yes[^e6] | yes[^e7] |
| write | yes[^r-document-carries-no-checksum][^e8] | yes[^r-document-carries-no-checksum][^e9] | yes[^e10] | yes[^e11] | no[^r-family-gate][^e5] | yes[^r-document-carries-no-checksum][^e12] | yes[^r-document-carries-no-checksum][^e13] |
| verify | n/a[^r-no-checksum-in-document][^e14] | n/a[^r-no-checksum-in-document][^e15] | yes[^e16] | yes[^e17] | no[^r-family-gate][^e5] | n/a[^r-no-checksum-in-document][^e18] | n/a[^r-no-checksum-in-document][^e19] |
| strip | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e21] | yes[^e22] | yes[^e23] | no[^r-family-gate][^e5] | n/a[^r-no-checksum-in-document][^e24] | n/a[^r-no-checksum-in-document][^e25] |
| links | n/a[^r-no-checksum-in-document][^e26] | n/a[^r-no-checksum-in-document][^e27] | yes[^r-links-verdicts][^e28] | yes[^r-links-verdicts][^e29] | no[^r-family-gate][^e5] | n/a[^r-no-checksum-in-document][^e30] | n/a[^r-no-checksum-in-document][^e31] |
| assess | n/a[^r-assess-documents][^e32] | n/a[^r-assess-documents][^e32] | yes[^e33] | yes[^e34] | no[^r-family-gate][^e5] | n/a[^r-assess-documents][^e32] | n/a[^r-assess-documents][^e32] |
| index | no[^r-index-fasta-only][^e35] | no[^r-index-fasta-only][^e36] | yes[^e37] | no[^r-index-fasta-only][^e38] | no[^r-family-gate][^e5] | no[^r-index-fasta-only][^e39] | no[^r-index-fasta-only][^e40] |

Vendored contract copies (`schemas/bundled.json`): v0.3.0 → `fhr-1.json`; v0.3.1 → `fhr-1.json`; v0.4.0 → `fhr-2.0.json`; v0.4.1 → `fhr-2.0.json`; v0.4.2 → `fhr-2.0.json`; v0.5.0 → `fhr-2.1.json`; v0.6.0 → `fhr-2.1.json`.

### FHP — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e41] | yes[^e42] | yes[^e43] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | yes[^e46] | yes[^e47] |
| write | yes[^r-document-carries-no-checksum][^e48] | yes[^r-document-carries-no-checksum][^e49] | yes[^e50] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | yes[^r-document-carries-no-checksum][^e51] | yes[^r-document-carries-no-checksum][^e52] |
| verify | n/a[^r-no-checksum-in-document][^e53] | n/a[^r-no-checksum-in-document][^e54] | yes[^e55] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | n/a[^r-no-checksum-in-document][^e56] | n/a[^r-no-checksum-in-document][^e57] |
| strip | n/a[^r-no-checksum-in-document][^e58] | n/a[^r-no-checksum-in-document][^e59] | yes[^e60] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | n/a[^r-no-checksum-in-document][^e61] | n/a[^r-no-checksum-in-document][^e62] |
| links | n/a[^r-no-checksum-in-document][^e63] | n/a[^r-no-checksum-in-document][^e64] | yes[^r-links-verdicts][^e65] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | n/a[^r-no-checksum-in-document][^e66] | n/a[^r-no-checksum-in-document][^e67] |
| assess | n/a[^r-assess-documents][^e68] | n/a[^r-assess-documents][^e68] | yes[^e69] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | n/a[^r-assess-documents][^e68] | n/a[^r-assess-documents][^e68] |
| index | no[^r-index-fasta-only][^e35] | no[^r-index-fasta-only][^e36] | partial[^r-index-samtools-fhr-only][^e70] | no[^r-family-gate][^e44] | no[^r-family-gate][^e45] | no[^r-index-fasta-only][^e39] | no[^r-index-fasta-only][^e40] |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhp-1.0.json`; v0.4.1 → `fhp-1.0.json`; v0.4.2 → `fhp-1.0.json`; v0.5.0 → `fhp-1.1.json`; v0.6.0 → `fhp-1.2.json`.

### FHGFF3 — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e71] | yes[^e72] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^e75] | no[^r-no-binding][^e76][^e77] | yes[^r-microdata-experimental][^e78] |
| write | yes[^r-document-carries-no-checksum][^e79] | yes[^r-document-carries-no-checksum][^e80] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^e81] | no[^r-no-binding][^e76][^e77] | yes[^r-microdata-experimental][^e82] |
| verify | n/a[^r-no-checksum-in-document][^e83] | n/a[^r-no-checksum-in-document][^e84] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^r-verify-directives][^e85] | no[^r-no-binding][^e76][^e77] | n/a[^r-no-checksum-in-document][^e86] |
| strip | n/a[^r-no-checksum-in-document][^e87] | n/a[^r-no-checksum-in-document][^e88] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^e89] | no[^r-no-binding][^e76][^e77] | n/a[^r-no-checksum-in-document][^e90] |
| links | n/a[^r-no-checksum-in-document][^e91] | n/a[^r-no-checksum-in-document][^e92] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^r-links-verdicts][^e93] | no[^r-no-binding][^e76][^e77] | n/a[^r-no-checksum-in-document][^e94] |
| assess | n/a[^r-assess-documents][^e95] | n/a[^r-assess-documents][^e95] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | yes[^e96] | no[^r-no-binding][^e76][^e77] | n/a[^r-assess-documents][^e95] |
| index | no[^r-index-fasta-only][^e35] | no[^r-index-fasta-only][^e36] | no[^r-family-gate][^e73] | no[^r-family-gate][^e74] | no[^r-index-fasta-only][^e97] | no[^r-no-binding][^e76][^e77] | no[^r-index-fasta-only][^e40] |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhgff3-1.0.json`; v0.4.1 → `fhgff3-1.0.json`; v0.4.2 → `fhgff3-1.0.json`; v0.5.0 → `fhgff3-1.1.json`; v0.6.0 → `fhgff3-1.2.json`.

### FHT — draft lane only, opt-in, no claim of any kind

`BIOHEADERS_EXPERIMENTAL_FHT` opens it; nothing else does. The lane reads `fht-draft.json`, pinned at commit `226f923c28b680edb3c546e99a751482d06aef1a` (sha256 `59ad9641adcb0e5591045c2d894c066d1adc9984cca84c5ff6502f8dad88487e` of those bytes), citation `https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json`. It has no entry in the version registry, no alias URL and no version of its own to name, and every read under the opt-in prints that provenance. Its suite is pinned apart from it: commit `7503b26423296ba09357de66995ca3c9508306af`, sha256 `ab72fc985a2629df5e8ea951936be3c3cf65a4f5a1c782f604ea6902a1d29c58`, 68 vectors.

A `draft lane` mark cites existing native tests of the opt-in path. Rendering checks those citations but does not execute the draft suite. It does not claim released support.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | not verified[^r-draft-no-file-evidence] | draft lane[^r-draft-lane-document][^e98] | draft lane[^r-draft-lane][^e99][^e100] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | no[^r-draft-no-binding][^e102] | no[^r-draft-no-binding][^e102] |
| write | not verified[^r-draft-no-file-evidence] | draft lane[^r-draft-lane-document][^e98] | draft lane[^r-draft-lane][^e98][^e100] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | no[^r-draft-no-binding][^e102] | no[^r-draft-no-binding][^e102] |
| verify | n/a[^r-no-checksum-in-document][^e14] | n/a[^r-no-checksum-in-document][^e15] | draft lane[^r-draft-lane][^e103][^e100] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | n/a[^r-no-checksum-in-document][^e18] | n/a[^r-no-checksum-in-document][^e19] |
| strip | n/a[^r-no-checksum-in-document][^e14] | n/a[^r-no-checksum-in-document][^e15] | draft lane[^r-draft-lane][^e98][^e100] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | n/a[^r-no-checksum-in-document][^e18] | n/a[^r-no-checksum-in-document][^e19] |
| links | n/a[^r-no-checksum-in-document][^e14] | n/a[^r-no-checksum-in-document][^e15] | draft lane[^r-draft-lane][^e104][^e100] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | n/a[^r-no-checksum-in-document][^e18] | n/a[^r-no-checksum-in-document][^e19] |
| assess | n/a[^r-assess-documents][^e32] | n/a[^r-assess-documents][^e32] | no[^r-draft-assess][^e99] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | n/a[^r-assess-documents][^e32] | n/a[^r-assess-documents][^e32] |
| index | no[^r-index-fasta-only][^e35] | no[^r-index-fasta-only][^e36] | not verified[^r-index-no-evidence] | no[^r-draft-carrier][^e101] | no[^r-draft-carrier][^e101] | no[^r-index-fasta-only][^e39] | no[^r-index-fasta-only][^e40] |

### FHGM — this artifact holds no reference to it

`bioheaders/pins.json` row `fhgm-base@none`, class `base-carrier`, label `draft, not acceptance`, is what says so; the audit prints it as `ABSENT`. The whole grid is one value because the whole of this repository is silent about the model draft, and that silence is a decision with a source, not an oversight. See the scope statements below the tables.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| write | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| verify | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| strip | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| links | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| assess | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |
| index | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] | not here[^r-fhgm-scope][^e105] |

## Commands, and the operations they carry

| console script | entry point | what it is |
| --- | --- | --- |
| `bioheaders` | `bioheaders.cli:main` | the umbrella command: 8 subcommands |
| `bioheaders-pin-audit` | `bioheaders.pin_audit:main` | advisory cross-repo pin audit; reports, writes nothing, and takes no part in the grids above |
| `fhr-convert` | `bioheaders.cli:convert_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-fasta-combine` | `bioheaders.cli:fasta_combine_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-fasta-strip` | `bioheaders.cli:fasta_strip_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-fasta-validate` | `bioheaders.cli:fasta_validate_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gfa-combine` | `bioheaders.cli:gfa_combine_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gfa-strip` | `bioheaders.cli:gfa_strip_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gfa-validate` | `bioheaders.cli:gfa_validate_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gff3-combine` | `bioheaders.cli:gff3_combine_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gff3-strip` | `bioheaders.cli:gff3_strip_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-gff3-validate` | `bioheaders.cli:gff3_validate_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |
| `fhr-validate` | `bioheaders.cli:validate_main` | public compatibility name; frozen, and mirrored by the `fhr` distribution built from `compat/fhr` |

13 installed commands: `bioheaders`, 11 `fhr-*` compatibility names, and the audit. Their subcommands are `assess`, `combine`, `convert`, `faidx`, `strip`, `validate`, `verify`, `verify-links` with alias `checksum`. Every `fhr-*` name shares an implementation with its `bioheaders` subcommand, which is why the grids above are per operation rather than per command; `tests/bioheaders_test.py` pins that the two sets stay equal.

## Bundled contract versions

Every listed citation is selected by a CLI validation probe.
Wrong-version and unknown-release probes must reject. Pin rows are
recorded provenance, not a live freshness verdict.

| type | specification tag | schemaVersion | bundled file |
| --- | --- | --- | --- |
| FHR | `v0.3.0` | `1` | `schemas/fhr-1.json` |
| FHR | `v0.3.1` | `1` | `schemas/fhr-1.json` |
| FHR | `v0.4.0` | `'2.0'` | `schemas/fhr-2.0.json` |
| FHR | `v0.4.1` | `'2.0'` | `schemas/fhr-2.0.json` |
| FHR | `v0.4.2` | `'2.0'` | `schemas/fhr-2.0.json` |
| FHR | `v0.5.0` | `'2.1'` | `schemas/fhr-2.1.json` |
| FHR | `v0.6.0` | `'2.1'` | `schemas/fhr-2.1.json` |
| FHP | `v0.4.0` | `'1.0'` | `schemas/fhp-1.0.json` |
| FHP | `v0.4.1` | `'1.0'` | `schemas/fhp-1.0.json` |
| FHP | `v0.4.2` | `'1.0'` | `schemas/fhp-1.0.json` |
| FHP | `v0.5.0` | `'1.1'` | `schemas/fhp-1.1.json` |
| FHP | `v0.6.0` | `'1.2'` | `schemas/fhp-1.2.json` |
| FHGFF3 | `v0.4.0` | `'1.0'` | `schemas/fhgff3-1.0.json` |
| FHGFF3 | `v0.4.1` | `'1.0'` | `schemas/fhgff3-1.0.json` |
| FHGFF3 | `v0.4.2` | `'1.0'` | `schemas/fhgff3-1.0.json` |
| FHGFF3 | `v0.5.0` | `'1.1'` | `schemas/fhgff3-1.1.json` |
| FHGFF3 | `v0.6.0` | `'1.2'` | `schemas/fhgff3-1.2.json` |

Release inputs are byte-checked against git tag `v0.6.0`.
The generator refuses a modified manifest, registry or root contract.

## Shared conformance scope

Manifest: `v0.6.0`, 291 vectors, SHA-256
`cdbb79b1fbfda52b27a9f54b73d3bae1efb662efcbb4c41ba02b9e3be40a51e1`.

Counts below are read from manifests; rendering does not execute the
normative suite. The CI checker separately runs all six formats against
installed commands and fails if any format is unsupported.

| format | shared vectors | valid / invalid | gzip / BGZF | vendored by ID here |
| --- | --- | --- | --- | --- |
| fasta | 98 | 35 / 63 | 3 / 1 | 0 |
| fhgff3 | 38 | 18 / 20 | 1 / 1 | 38 |
| fhp-fasta | 36 | 14 / 22 | 1 / 1 | 36 |
| gfa | 56 | 20 / 36 | 2 / 1 | 0 |
| jsonld | 37 | 17 / 20 | 0 / 0 | 37 |
| microdata | 26 | 15 / 11 | 0 / 0 | 0 |

The toolkit implements JSON-LD and microdata readers. The native
libraries' 228 pass / 63 not-run ledger therefore cannot describe this
consumer. Missing vendored formats are exercised by the shared checker,
alongside existing native regression tests. Manifest parity is checked by:
- `tests/fhp_test.py::test_fixtures_match_the_specification`
- `tests/fhgff3_test.py::test_fixtures_match_the_specification`
- `tests/jsonld_test.py::test_vectors_match_the_specification`

The matrix probes separately exercise strip payload equality, writing,
parent-link handling, assessment and indexing. A successful validation
vector alone does not establish these operations.

## Compression by operation

Checksums cover decompressed exact bytes. Compression is detected from
gzip magic bytes; output to .gz/.bgz uses BGZF. The shared manifest
contains 11 gzip/BGZF vectors, shown by format above.

| operation | evidence and limits |
| --- | --- |
| read/validate | shared compressed vectors; native compression tests |
| verify | gzip probe per implemented released carrier; shared gzip/BGZF vectors |
| strip | gzip input to plain output per released carrier; payload bytes compared |
| combine | FHR FASTA/GFA input/output: `tests/compression_test.py::test_combine_to_gz_then_validate_and_strip`; other types not verified here |
| convert | JSON metadata to BGZF output per implemented released carrier; magic checked |
| verify-links | compressed input not verified by this generator |
| assess | compressed input not verified by this generator |
| faidx | FHR interoperability tests require samtools/bgzip; FHP/FHT compressed indexing not verified here |
| FHT draft | declared pinned suite only; rendering does not execute that suite |

Executed compression probes:
- `gzip-read-FHR-fasta`
- `gzip-strip-FHR-fasta`
- `gzip-write-FHR-fasta`
- `gzip-read-FHR-gfa`
- `gzip-strip-FHR-gfa`
- `gzip-write-FHR-gfa`
- `gzip-read-FHP-fasta`
- `gzip-strip-FHP-fasta`
- `gzip-write-FHP-fasta`
- `gzip-read-FHGFF3-gff3`
- `gzip-strip-FHGFF3-gff3`
- `gzip-write-FHGFF3-gff3`
- `gzip-read-FHR-jsonld`
- `gzip-read-FHR-microdata`

FHR gzip JSON-LD and microdata input is probed. Other compressed
metadata-document operations are not verified by this generator.
`tests/compression_test.py::test_stdin_and_stdout` covers pipes for
FHR FASTA/GFA. It does not establish pipe parity for every type.

## The draft lane is opt-in and is never a claim

`BIOHEADERS_EXPERIMENTAL_FHT` is read by `bioheaders/selection.py`. Unset - the
default - a record citing
the draft's raw URL is rule V5: read as a genome header, with a
near-miss warning saying so. Set, the citation selects pinned
development bytes and every read prints their provenance, which since
#165 carries the commit and the SHA-256 of exactly those bytes:

```text
citation  https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json
commit    226f923c28b680edb3c546e99a751482d06aef1a
sha256    59ad9641adcb0e5591045c2d894c066d1adc9984cca84c5ff6502f8dad88487e
suite     7503b26423296ba09357de66995ca3c9508306af (sha256 ab72fc985a2629df5e8ea951936be3c3cf65a4f5a1c782f604ea6902a1d29c58, 68 vectors)
contract  FHT-Specification (development repository; no released contract, no w3id alias, not in schemas/versions.json)
```

That block is provenance about bytes at a commit. It is not a release,
and no cell above uses it as one. The lane is also not a licence to
relax anything else: the released contracts stay at the tag named in the
header, and `tests/fht_test.py` asserts that with the gate open the
released families behave exactly as they do with it shut.

## Scope and existing provenance gaps

- FHGM model validation is unimplemented in this toolkit (#135). Its
  audit row `fhgm-base@none` is absent by declared scope. Parsing an
  FHGFF3 extension does not evaluate FHGM model rules.
- FHT has two different existing suite records. Runtime registry
  `bundled.json`: `7503b26423296ba09357de66995ca3c9508306af`,
  SHA-256 `ab72fc985a2629df5e8ea951936be3c3cf65a4f5a1c782f604ea6902a1d29c58`, 68 vectors.
  Advisory `pins.json` row `fht-manifest@24d3b03`: `24d3b033ab951ef79ee9f6d17419d8ba700f1b0a`,
  SHA-256 `9b07179497bdc7247d6ead2404d9d5fdee48308a58b385bd4cd9a7e91450053a`. This matrix follows the runtime
  registry. Neither record is changed; #167 owns the reporting follow-up.
- Filtered fixture manifests are derived subsets, not byte copies of
  the whole shared manifest. Their parity tests are named above.
- `assess` reports bare metadata documents as unknown-text, without
  a header-conformance verdict. Exit zero does not establish assessment.
- FHGFF3 microdata is implemented with an experimental binding warning;
  its status is separate from the released FHGFF3 header contract.
- FHP JSON-LD is canonical only. Its schema.org export profile is refused.

## Not verified

- `index` for FHT, and `assess` for a draft-carrying FASTA beyond its `not_assessed` verdict — no probe or test measures either; the gate is asked in-process, but nothing runs a draft header through `faidx`
- `index` offsets for the protein header against samtools — `tests/faidx_test.py` compares `.fai` bytes with samtools and pysam for FHR FASTA only. The FHP cell is earned by an independent recomputation of every field during this render, which is weaker than the samtools comparison and is labelled as such
- gzip and BGZF for JSON-LD and microdata as a documented contract — the shared suite holds no compressed vector of either format, and `open_input` detects compression by magic bytes on any input. The probes show a gzip member of each is readable; nobody has specified what compressed metadata documents mean for the checksum, because they carry no body
- `assess --online` identifier resolution — opt-in and makes network calls; deliberately not exercised here
- the Galaxy wrappers and the container images — `galaxy/tools/fair_bioheaders` is linted by `galaxy-tools.yml` with `planemo`, which this render does not run, and `Dockerfile` and `container.yml` build from a *released* wheel. Nothing in this file says a word about either
- the Python 3.9 lane, and the 3.13 lane separately — rendering uses one interpreter. The native pytest workflow covers both; the separate shared-conformance job uses Python 3.13 and requires all six formats. No interpreter-specific skipped-test count is inferred here
- the opt-in large-file memory test — `FHR_MEMORY_TEST=1 pytest -k memory` was not run: it writes about 1 GB

## Executed probes

Each probe must meet its expected exit status and any output/byte checks.
A failed probe aborts before the document is written.

| probe | command | exit (expected = observed) |
| --- | --- | --- |
| `assess-FHGFF3-gff3` | `bioheaders assess examples/fhgff3/annotation.fhgff3.gff3 --format json --output <tmp>/assess-FHGFF3-gff3` | 0 |
| `assess-FHP-fasta` | `bioheaders assess examples/fhp/example.fhp.fasta --format json --output <tmp>/assess-FHP-fasta` | 0 |
| `assess-FHR-fasta` | `bioheaders assess examples/example.fhr.fasta --format json --output <tmp>/assess-FHR-fasta` | 0 |
| `assess-FHR-gfa` | `bioheaders assess examples/example.fhr.gfa --format json --output <tmp>/assess-FHR-gfa` | 0 |
| `assess-doc-FHGFF3` | `bioheaders assess examples/fhgff3/minimal-reference.fhgff3.json --format json --output <tmp>/assessdoc-FHGFF3` | 0 |
| `assess-doc-FHP` | `bioheaders assess examples/fhp/minimal-predicted.fhp.json --format json --output <tmp>/assessdoc-FHP` | 0 |
| `assess-doc-FHR` | `bioheaders assess examples/example.fhr.json --format json --output <tmp>/assessdoc-FHR` | 0 |
| `gzip-read-FHGFF3-gff3` | `bioheaders verify <tmp>/gzip-FHGFF3-gff3.gff3.gz` | 0 |
| `gzip-read-FHP-fasta` | `bioheaders verify <tmp>/gzip-FHP-fasta.fasta.gz` | 0 |
| `gzip-read-FHR-fasta` | `bioheaders verify <tmp>/gzip-FHR-fasta.fasta.gz` | 0 |
| `gzip-read-FHR-gfa` | `bioheaders verify <tmp>/gzip-FHR-gfa.gfa.gz` | 0 |
| `gzip-read-FHR-jsonld` | `bioheaders validate <tmp>/docgz-FHR.jsonld.gz` | 0 |
| `gzip-read-FHR-microdata` | `bioheaders validate <tmp>/docgz-FHR.html.gz` | 0 |
| `gzip-strip-FHGFF3-gff3` | `bioheaders strip <tmp>/gzip-FHGFF3-gff3.gff3.gz <tmp>/plain-FHGFF3-gff3` | 0 |
| `gzip-strip-FHP-fasta` | `bioheaders strip <tmp>/gzip-FHP-fasta.fasta.gz <tmp>/plain-FHP-fasta` | 0 |
| `gzip-strip-FHR-fasta` | `bioheaders strip <tmp>/gzip-FHR-fasta.fasta.gz <tmp>/plain-FHR-fasta` | 0 |
| `gzip-strip-FHR-gfa` | `bioheaders strip <tmp>/gzip-FHR-gfa.gfa.gz <tmp>/plain-FHR-gfa` | 0 |
| `gzip-write-FHGFF3-gff3` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/written-FHGFF3-gff3.gff3.gz` | 0 |
| `gzip-write-FHP-fasta` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/written-FHP-fasta.fasta.gz` | 0 |
| `gzip-write-FHR-fasta` | `bioheaders convert examples/example.fhr.json <tmp>/written-FHR-fasta.fasta.gz` | 0 |
| `gzip-write-FHR-gfa` | `bioheaders convert examples/example.fhr.json <tmp>/written-FHR-gfa.gfa.gz` | 0 |
| `index-FHP` | `bioheaders faidx examples/fhp/example.fhp.fasta -o <tmp>/index-FHP.fai` | 0 |
| `index-FHR` | `bioheaders faidx examples/example.fhr.fasta -o <tmp>/index-FHR.fai` | 0 |
| `index-reject-gfa` | `bioheaders faidx examples/example.fhr.gfa -o <tmp>/index-reject-gfa.fai` | 1 |
| `index-reject-gff3` | `bioheaders faidx examples/fhgff3/annotation.fhgff3.gff3 -o <tmp>/index-reject-gff3.fai` | 1 |
| `index-reject-json` | `bioheaders faidx examples/example.fhr.json -o <tmp>/index-reject-json.fai` | 1 |
| `index-reject-jsonld` | `bioheaders faidx examples/example.fhr.jsonld -o <tmp>/index-reject-jsonld.fai` | 1 |
| `index-reject-microdata` | `bioheaders faidx examples/example.microdata.fhr.html -o <tmp>/index-reject-microdata.fai` | 1 |
| `index-reject-yaml` | `bioheaders faidx examples/example.fhr.yaml -o <tmp>/index-reject-yaml.fai` | 1 |
| `links-FHGFF3-gff3` | `bioheaders verify-links examples/fhgff3/annotation.fhgff3.gff3` | 0 |
| `links-FHP-fasta` | `bioheaders verify-links examples/fhp/example.fhp.fasta` | 0 |
| `links-FHR-fasta` | `bioheaders verify-links examples/example.fhr.fasta` | 0 |
| `links-FHR-gfa` | `bioheaders verify-links examples/example.fhr.gfa` | 0 |
| `links-doc-FHGFF3-json` | `bioheaders verify-links examples/fhgff3/minimal-reference.fhgff3.json` | 1 |
| `links-doc-FHGFF3-microdata` | `bioheaders verify-links examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 |
| `links-doc-FHGFF3-yaml` | `bioheaders verify-links examples/fhgff3/rich.fhgff3.yaml` | 1 |
| `links-doc-FHP-json` | `bioheaders verify-links examples/fhp/minimal-predicted.fhp.json` | 1 |
| `links-doc-FHP-jsonld` | `bioheaders verify-links examples/fhp/minimal-predicted.fhp.jsonld` | 1 |
| `links-doc-FHP-microdata` | `bioheaders verify-links examples/fhp/rich-microdata.microdata.fhp.html` | 1 |
| `links-doc-FHP-yaml` | `bioheaders verify-links examples/fhp/rich-mixed.fhp.yaml` | 1 |
| `links-doc-FHR-json` | `bioheaders verify-links examples/example.fhr.json` | 1 |
| `links-doc-FHR-jsonld` | `bioheaders verify-links examples/example.fhr.jsonld` | 1 |
| `links-doc-FHR-microdata` | `bioheaders verify-links examples/example.microdata.fhr.html` | 1 |
| `links-doc-FHR-yaml` | `bioheaders verify-links examples/example.fhr.yaml` | 1 |
| `read-FHGFF3-gff3` | `bioheaders validate examples/fhgff3/annotation.fhgff3.gff3` | 0 |
| `read-FHGFF3-json` | `bioheaders validate examples/fhgff3/minimal-reference.fhgff3.json` | 0 |
| `read-FHGFF3-microdata` | `bioheaders validate examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 0 |
| `read-FHGFF3-yaml` | `bioheaders validate examples/fhgff3/rich.fhgff3.yaml` | 0 |
| `read-FHP-fasta` | `bioheaders validate examples/fhp/example.fhp.fasta` | 0 |
| `read-FHP-json` | `bioheaders validate examples/fhp/minimal-predicted.fhp.json` | 0 |
| `read-FHP-jsonld` | `bioheaders validate examples/fhp/minimal-predicted.fhp.jsonld` | 0 |
| `read-FHP-microdata` | `bioheaders validate examples/fhp/rich-microdata.microdata.fhp.html` | 0 |
| `read-FHP-yaml` | `bioheaders validate examples/fhp/rich-mixed.fhp.yaml` | 0 |
| `read-FHR-fasta` | `bioheaders validate examples/example.fhr.fasta` | 0 |
| `read-FHR-gfa` | `bioheaders validate examples/example.fhr.gfa` | 0 |
| `read-FHR-json` | `bioheaders validate examples/example.fhr.json` | 0 |
| `read-FHR-jsonld` | `bioheaders validate examples/example.fhr.jsonld` | 0 |
| `read-FHR-microdata` | `bioheaders validate examples/example.microdata.fhr.html` | 0 |
| `read-FHR-yaml` | `bioheaders validate examples/example.fhr.yaml` | 0 |
| `readback-FHGFF3-microdata` | `bioheaders validate <tmp>/write-FHGFF3-microdata.html` | 0 |
| `readback-FHP-jsonld` | `bioheaders validate <tmp>/write-FHP-jsonld.jsonld` | 0 |
| `readback-FHP-microdata` | `bioheaders validate <tmp>/write-FHP-microdata.html` | 0 |
| `readback-FHR-jsonld` | `bioheaders validate <tmp>/write-FHR-jsonld.jsonld` | 0 |
| `readback-FHR-microdata` | `bioheaders validate <tmp>/write-FHR-microdata.html` | 0 |
| `refuse-FHGFF3-fasta` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-fasta.fasta` | 1 |
| `refuse-FHGFF3-gfa` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-gfa.gfa` | 1 |
| `refuse-FHGFF3-jsonld` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-jsonld.jsonld` | 1 |
| `refuse-FHP-export` | `bioheaders convert --jsonld-profile export examples/fhp/minimal-predicted.fhp.json <tmp>/export.fhp.jsonld` | 1 |
| `refuse-FHP-gfa` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gfa.gfa` | 1 |
| `refuse-FHP-gff3` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gff3.gff3` | 1 |
| `refuse-FHR-gff3` | `bioheaders convert examples/example.fhr.json <tmp>/refuse-FHR-gff3.gff3` | 1 |
| `roundtrip-FHGFF3-gff3` | `bioheaders verify <tmp>/write-FHGFF3-gff3.gff3` | 0 |
| `roundtrip-FHP-fasta` | `bioheaders verify <tmp>/write-FHP-fasta.fasta` | 0 |
| `roundtrip-FHR-fasta` | `bioheaders verify <tmp>/write-FHR-fasta.fasta` | 0 |
| `roundtrip-FHR-gfa` | `bioheaders verify <tmp>/write-FHR-gfa.gfa` | 0 |
| `strip-FHGFF3-gff3` | `bioheaders strip examples/fhgff3/annotation.fhgff3.gff3 <tmp>/strip-FHGFF3-gff3.gff3` | 0 |
| `strip-FHP-fasta` | `bioheaders strip examples/fhp/example.fhp.fasta <tmp>/strip-FHP-fasta.fasta` | 0 |
| `strip-FHR-fasta` | `bioheaders strip examples/example.fhr.fasta <tmp>/strip-FHR-fasta.fasta` | 0 |
| `strip-FHR-gfa` | `bioheaders strip examples/example.fhr.gfa <tmp>/strip-FHR-gfa.gfa` | 0 |
| `strip-doc-FHGFF3-json` | `bioheaders strip examples/fhgff3/minimal-reference.fhgff3.json` | 1 |
| `strip-doc-FHGFF3-microdata` | `bioheaders strip examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 |
| `strip-doc-FHGFF3-yaml` | `bioheaders strip examples/fhgff3/rich.fhgff3.yaml` | 1 |
| `strip-doc-FHP-json` | `bioheaders strip examples/fhp/minimal-predicted.fhp.json` | 1 |
| `strip-doc-FHP-jsonld` | `bioheaders strip examples/fhp/minimal-predicted.fhp.jsonld` | 1 |
| `strip-doc-FHP-microdata` | `bioheaders strip examples/fhp/rich-microdata.microdata.fhp.html` | 1 |
| `strip-doc-FHP-yaml` | `bioheaders strip examples/fhp/rich-mixed.fhp.yaml` | 1 |
| `strip-doc-FHR-json` | `bioheaders strip examples/example.fhr.json` | 1 |
| `strip-doc-FHR-jsonld` | `bioheaders strip examples/example.fhr.jsonld` | 1 |
| `strip-doc-FHR-microdata` | `bioheaders strip examples/example.microdata.fhr.html` | 1 |
| `strip-doc-FHR-yaml` | `bioheaders strip examples/example.fhr.yaml` | 1 |
| `verify-FHGFF3-gff3` | `bioheaders verify examples/fhgff3/annotation.fhgff3.gff3` | 0 |
| `verify-FHP-fasta` | `bioheaders verify examples/fhp/example.fhp.fasta` | 0 |
| `verify-FHR-fasta` | `bioheaders verify examples/example.fhr.fasta` | 0 |
| `verify-FHR-gfa` | `bioheaders verify examples/example.fhr.gfa` | 0 |
| `verify-doc-FHGFF3-json` | `bioheaders verify examples/fhgff3/minimal-reference.fhgff3.json` | 1 |
| `verify-doc-FHGFF3-microdata` | `bioheaders verify examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 |
| `verify-doc-FHGFF3-yaml` | `bioheaders verify examples/fhgff3/rich.fhgff3.yaml` | 1 |
| `verify-doc-FHP-json` | `bioheaders verify examples/fhp/minimal-predicted.fhp.json` | 1 |
| `verify-doc-FHP-jsonld` | `bioheaders verify examples/fhp/minimal-predicted.fhp.jsonld` | 1 |
| `verify-doc-FHP-microdata` | `bioheaders verify examples/fhp/rich-microdata.microdata.fhp.html` | 1 |
| `verify-doc-FHP-yaml` | `bioheaders verify examples/fhp/rich-mixed.fhp.yaml` | 1 |
| `verify-doc-FHR-json` | `bioheaders verify examples/example.fhr.json` | 1 |
| `verify-doc-FHR-jsonld` | `bioheaders verify examples/example.fhr.jsonld` | 1 |
| `verify-doc-FHR-microdata` | `bioheaders verify examples/example.microdata.fhr.html` | 1 |
| `verify-doc-FHR-yaml` | `bioheaders verify examples/example.fhr.yaml` | 1 |
| `version-FHGFF3-v0.4.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.0.json` | 0 |
| `version-FHGFF3-v0.4.1` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.1.json` | 0 |
| `version-FHGFF3-v0.4.2` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.2.json` | 0 |
| `version-FHGFF3-v0.5.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.5.0.json` | 0 |
| `version-FHGFF3-v0.6.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.6.0.json` | 0 |
| `version-FHP-v0.4.0` | `bioheaders validate <tmp>/version-FHP-v0.4.0.json` | 0 |
| `version-FHP-v0.4.1` | `bioheaders validate <tmp>/version-FHP-v0.4.1.json` | 0 |
| `version-FHP-v0.4.2` | `bioheaders validate <tmp>/version-FHP-v0.4.2.json` | 0 |
| `version-FHP-v0.5.0` | `bioheaders validate <tmp>/version-FHP-v0.5.0.json` | 0 |
| `version-FHP-v0.6.0` | `bioheaders validate <tmp>/version-FHP-v0.6.0.json` | 0 |
| `version-FHR-v0.3.0` | `bioheaders validate <tmp>/version-FHR-v0.3.0.json` | 0 |
| `version-FHR-v0.3.1` | `bioheaders validate <tmp>/version-FHR-v0.3.1.json` | 0 |
| `version-FHR-v0.4.0` | `bioheaders validate <tmp>/version-FHR-v0.4.0.json` | 0 |
| `version-FHR-v0.4.1` | `bioheaders validate <tmp>/version-FHR-v0.4.1.json` | 0 |
| `version-FHR-v0.4.2` | `bioheaders validate <tmp>/version-FHR-v0.4.2.json` | 0 |
| `version-FHR-v0.5.0` | `bioheaders validate <tmp>/version-FHR-v0.5.0.json` | 0 |
| `version-FHR-v0.6.0` | `bioheaders validate <tmp>/version-FHR-v0.6.0.json` | 0 |
| `version-absent-FHGFF3` | `bioheaders validate <tmp>/version-absent-FHGFF3.json` | 1 |
| `version-absent-FHP` | `bioheaders validate <tmp>/version-absent-FHP.json` | 1 |
| `version-absent-FHR` | `bioheaders validate <tmp>/version-absent-FHR.json` | 1 |
| `version-control-FHGFF3` | `bioheaders validate <tmp>/version-control-FHGFF3.json` | 1 |
| `version-control-FHP` | `bioheaders validate <tmp>/version-control-FHP.json` | 1 |
| `version-control-FHR` | `bioheaders validate <tmp>/version-control-FHR.json` | 1 |
| `write-FHGFF3-gff3` | `bioheaders combine examples/fhgff3/minimal-reference.fhgff3.json <tmp>/strip-FHGFF3-gff3.gff3 -o <tmp>/write-FHGFF3-gff3.gff3` | 0 |
| `write-FHGFF3-json` | `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.json` | 0 |
| `write-FHGFF3-microdata` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/write-FHGFF3-microdata.html` | 0 |
| `write-FHGFF3-yaml` | `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.yaml` | 0 |
| `write-FHP-fasta` | `bioheaders combine examples/fhp/minimal-predicted.fhp.json <tmp>/strip-FHP-fasta.fasta -o <tmp>/write-FHP-fasta.fasta` | 0 |
| `write-FHP-json` | `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.json` | 0 |
| `write-FHP-jsonld` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-jsonld.jsonld` | 0 |
| `write-FHP-microdata` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-microdata.html` | 0 |
| `write-FHP-yaml` | `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.yaml` | 0 |
| `write-FHR-fasta` | `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-fasta.fasta -o <tmp>/write-FHR-fasta.fasta` | 0 |
| `write-FHR-gfa` | `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-gfa.gfa -o <tmp>/write-FHR-gfa.gfa` | 0 |
| `write-FHR-json` | `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.json` | 0 |
| `write-FHR-jsonld` | `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-jsonld.jsonld` | 0 |
| `write-FHR-microdata` | `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-microdata.html` | 0 |
| `write-FHR-yaml` | `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.yaml` | 0 |

## Reasons, in full

[^r-family-gate]: refused by `validate_header_family` in `bioheaders/cli.py`, which admits each sequence serialization to named header families only. The probe asked `convert`, and the gate's own words are quoted in the probe list, so this is the rule, not a summary of it
[^r-document-carries-no-checksum]: written from a carrier; a bare metadata document has no sequence bytes for the checksum to cover, so it is metadata, not a file-bound header
[^r-no-checksum-in-document]: the file-bound SHA-512/256 covers a header block plus body bytes. A metadata document has no body, so the command names the input formats it takes and stops: a vacuous pass would be worse than an `n/a`. The probe shows the refusal, and the gate is about the serialization, not the type
[^r-links-verdicts]: exit 0 with nothing recorded is `not checked`, which is not a match: the command never invents or recomputes a parent checksum. Vectors that do record parents are scored by name in the shared suite
[^r-assess-documents]: `assess` scores the header block of a *data* file. Given a bare metadata document it reports `unknown-text`, reads 0 header lines and publishes no conformance section; the probe asserts exactly that, so its exit status 0 is not read as an assessment
[^r-index-fasta-only]: `faidx` parses FASTA. Anything else fails as a format error, which is the honest outcome: an index of bytes samtools cannot read is worse than no index
[^r-index-samtools-fhr-only]: every `.fai` field was recomputed from the file bytes during this render and matched, but the samtools and pysam byte comparisons in `tests/faidx_test.py` are written for the genome header only
[^r-no-binding]: no reviewed binding for that pair is published, and the writer refuses instead of borrowing another type's identity
[^r-microdata-experimental]: the binding itself is still open upstream (`EXPERIMENTAL = True` in `bioheaders/fhgff3_microdata.py`, which warns on every read and write, pending FHGFF3#16): implemented and measured here, not a published serialization
[^r-verify-directives]: for an annotation header the command also cross-checks the GFF3 directives against the header block, which no other carrier has
[^r-draft-no-file-evidence]: no file-level probe or test covers the draft lane here, so the cell stays unearned rather than being closed by analogy with FASTA
[^r-draft-lane-document]: the lane carries the header between a FASTA carrier and YAML: `convert` writes it, `combine` reads it back and re-verifies. The carrier still holds the checksum, so the document is metadata only
[^r-draft-lane]: reached only with `BIOHEADERS_EXPERIMENTAL_FHT` set, against `fht-draft.json` pinned at commit `226f923c28b6…` (sha256 `59ad9641adcb…`). A lane over pinned development bytes is a preview: it is not a claim about the type's status, and the default run does not take it
[^r-draft-carrier]: the draft contract is FASTA-only, and the gate keeps GFA for the genome header and GFF3 for the annotation header: the gate was asked with the opt-in set, and said no
[^r-draft-no-binding]: the lane refuses rather than stretching a published identity over development bytes: no binding for that pair has been reviewed
[^r-draft-assess]: `assess` reads the citation and reports its conformance section as `not_assessed`: the rubric follows the released contracts, and the lane deliberately leaves that alone
[^r-index-no-evidence]: neither measured nor refused: no probe and no test covers it, so no mark is invented
[^r-fhgm-scope]: this artifact has no model implementation: no vendored draft contract, and no base or carrier pin of its own, which `bioheaders-pin-audit` reports as `fhgm-base@none` / `ABSENT` with the reason recorded in `bioheaders/pins.json`. A scope statement, not a hole this document fills: the lane is FAIR-bioHeaders-Tools#135, and the cell is unrun rather than run and unrecorded

## Evidence, in full

[^e1]: probe `read-FHR-json` — `bioheaders validate examples/example.fhr.json`, expected exit 0, observed 0
[^e2]: probe `read-FHR-yaml` — `bioheaders validate examples/example.fhr.yaml`, expected exit 0, observed 0
[^e3]: probe `read-FHR-fasta` — `bioheaders validate examples/example.fhr.fasta`, expected exit 0, observed 0
[^e4]: probe `read-FHR-gfa` — `bioheaders validate examples/example.fhr.gfa`, expected exit 0, observed 0
[^e5]: probe `refuse-FHR-gff3` — `bioheaders convert examples/example.fhr.json <tmp>/refuse-FHR-gff3.gff3`, expected exit 1, observed 1
[^e6]: probe `read-FHR-jsonld` — `bioheaders validate examples/example.fhr.jsonld`, expected exit 0, observed 0
[^e7]: probe `read-FHR-microdata` — `bioheaders validate examples/example.microdata.fhr.html`, expected exit 0, observed 0
[^e8]: probe `write-FHR-json` — `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.json`, expected exit 0, observed 0
[^e9]: probe `write-FHR-yaml` — `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.yaml`, expected exit 0, observed 0
[^e10]: probe `write-FHR-fasta` — `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-fasta.fasta -o <tmp>/write-FHR-fasta.fasta`, expected exit 0, observed 0
[^e11]: probe `write-FHR-gfa` — `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-gfa.gfa -o <tmp>/write-FHR-gfa.gfa`, expected exit 0, observed 0
[^e12]: probe `write-FHR-jsonld` — `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-jsonld.jsonld`, expected exit 0, observed 0
[^e13]: probe `write-FHR-microdata` — `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-microdata.html`, expected exit 0, observed 0
[^e14]: probe `verify-doc-FHR-json` — `bioheaders verify examples/example.fhr.json`, expected exit 1, observed 1
[^e15]: probe `verify-doc-FHR-yaml` — `bioheaders verify examples/example.fhr.yaml`, expected exit 1, observed 1
[^e16]: probe `verify-FHR-fasta` — `bioheaders verify examples/example.fhr.fasta`, expected exit 0, observed 0
[^e17]: probe `verify-FHR-gfa` — `bioheaders verify examples/example.fhr.gfa`, expected exit 0, observed 0
[^e18]: probe `verify-doc-FHR-jsonld` — `bioheaders verify examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e19]: probe `verify-doc-FHR-microdata` — `bioheaders verify examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e20]: probe `strip-doc-FHR-json` — `bioheaders strip examples/example.fhr.json`, expected exit 1, observed 1
[^e21]: probe `strip-doc-FHR-yaml` — `bioheaders strip examples/example.fhr.yaml`, expected exit 1, observed 1
[^e22]: probe `strip-FHR-fasta` — `bioheaders strip examples/example.fhr.fasta <tmp>/strip-FHR-fasta.fasta`, expected exit 0, observed 0
[^e23]: probe `strip-FHR-gfa` — `bioheaders strip examples/example.fhr.gfa <tmp>/strip-FHR-gfa.gfa`, expected exit 0, observed 0
[^e24]: probe `strip-doc-FHR-jsonld` — `bioheaders strip examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e25]: probe `strip-doc-FHR-microdata` — `bioheaders strip examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e26]: probe `links-doc-FHR-json` — `bioheaders verify-links examples/example.fhr.json`, expected exit 1, observed 1
[^e27]: probe `links-doc-FHR-yaml` — `bioheaders verify-links examples/example.fhr.yaml`, expected exit 1, observed 1
[^e28]: probe `links-FHR-fasta` — `bioheaders verify-links examples/example.fhr.fasta`, expected exit 0, observed 0
[^e29]: probe `links-FHR-gfa` — `bioheaders verify-links examples/example.fhr.gfa`, expected exit 0, observed 0
[^e30]: probe `links-doc-FHR-jsonld` — `bioheaders verify-links examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e31]: probe `links-doc-FHR-microdata` — `bioheaders verify-links examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e32]: probe `assess-doc-FHR` — `bioheaders assess examples/example.fhr.json --format json --output <tmp>/assessdoc-FHR`, expected exit 0, observed 0
[^e33]: probe `assess-FHR-fasta` — `bioheaders assess examples/example.fhr.fasta --format json --output <tmp>/assess-FHR-fasta`, expected exit 0, observed 0
[^e34]: probe `assess-FHR-gfa` — `bioheaders assess examples/example.fhr.gfa --format json --output <tmp>/assess-FHR-gfa`, expected exit 0, observed 0
[^e35]: probe `index-reject-json` — `bioheaders faidx examples/example.fhr.json -o <tmp>/index-reject-json.fai`, expected exit 1, observed 1
[^e36]: probe `index-reject-yaml` — `bioheaders faidx examples/example.fhr.yaml -o <tmp>/index-reject-yaml.fai`, expected exit 1, observed 1
[^e37]: probe `index-FHR` — `bioheaders faidx examples/example.fhr.fasta -o <tmp>/index-FHR.fai`, expected exit 0, observed 0
[^e38]: probe `index-reject-gfa` — `bioheaders faidx examples/example.fhr.gfa -o <tmp>/index-reject-gfa.fai`, expected exit 1, observed 1
[^e39]: probe `index-reject-jsonld` — `bioheaders faidx examples/example.fhr.jsonld -o <tmp>/index-reject-jsonld.fai`, expected exit 1, observed 1
[^e40]: probe `index-reject-microdata` — `bioheaders faidx examples/example.microdata.fhr.html -o <tmp>/index-reject-microdata.fai`, expected exit 1, observed 1
[^e41]: probe `read-FHP-json` — `bioheaders validate examples/fhp/minimal-predicted.fhp.json`, expected exit 0, observed 0
[^e42]: probe `read-FHP-yaml` — `bioheaders validate examples/fhp/rich-mixed.fhp.yaml`, expected exit 0, observed 0
[^e43]: probe `read-FHP-fasta` — `bioheaders validate examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e44]: probe `refuse-FHP-gfa` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gfa.gfa`, expected exit 1, observed 1
[^e45]: probe `refuse-FHP-gff3` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gff3.gff3`, expected exit 1, observed 1
[^e46]: probe `read-FHP-jsonld` — `bioheaders validate examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 0, observed 0
[^e47]: probe `read-FHP-microdata` — `bioheaders validate examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 0, observed 0
[^e48]: probe `write-FHP-json` — `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.json`, expected exit 0, observed 0
[^e49]: probe `write-FHP-yaml` — `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.yaml`, expected exit 0, observed 0
[^e50]: probe `write-FHP-fasta` — `bioheaders combine examples/fhp/minimal-predicted.fhp.json <tmp>/strip-FHP-fasta.fasta -o <tmp>/write-FHP-fasta.fasta`, expected exit 0, observed 0
[^e51]: probe `write-FHP-jsonld` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-jsonld.jsonld`, expected exit 0, observed 0
[^e52]: probe `write-FHP-microdata` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-microdata.html`, expected exit 0, observed 0
[^e53]: probe `verify-doc-FHP-json` — `bioheaders verify examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e54]: probe `verify-doc-FHP-yaml` — `bioheaders verify examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e55]: probe `verify-FHP-fasta` — `bioheaders verify examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e56]: probe `verify-doc-FHP-jsonld` — `bioheaders verify examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e57]: probe `verify-doc-FHP-microdata` — `bioheaders verify examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e58]: probe `strip-doc-FHP-json` — `bioheaders strip examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e59]: probe `strip-doc-FHP-yaml` — `bioheaders strip examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e60]: probe `strip-FHP-fasta` — `bioheaders strip examples/fhp/example.fhp.fasta <tmp>/strip-FHP-fasta.fasta`, expected exit 0, observed 0
[^e61]: probe `strip-doc-FHP-jsonld` — `bioheaders strip examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e62]: probe `strip-doc-FHP-microdata` — `bioheaders strip examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e63]: probe `links-doc-FHP-json` — `bioheaders verify-links examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e64]: probe `links-doc-FHP-yaml` — `bioheaders verify-links examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e65]: probe `links-FHP-fasta` — `bioheaders verify-links examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e66]: probe `links-doc-FHP-jsonld` — `bioheaders verify-links examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e67]: probe `links-doc-FHP-microdata` — `bioheaders verify-links examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e68]: probe `assess-doc-FHP` — `bioheaders assess examples/fhp/minimal-predicted.fhp.json --format json --output <tmp>/assessdoc-FHP`, expected exit 0, observed 0
[^e69]: probe `assess-FHP-fasta` — `bioheaders assess examples/fhp/example.fhp.fasta --format json --output <tmp>/assess-FHP-fasta`, expected exit 0, observed 0
[^e70]: probe `index-FHP` — `bioheaders faidx examples/fhp/example.fhp.fasta -o <tmp>/index-FHP.fai`, expected exit 0, observed 0
[^e71]: probe `read-FHGFF3-json` — `bioheaders validate examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 0, observed 0
[^e72]: probe `read-FHGFF3-yaml` — `bioheaders validate examples/fhgff3/rich.fhgff3.yaml`, expected exit 0, observed 0
[^e73]: probe `refuse-FHGFF3-fasta` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-fasta.fasta`, expected exit 1, observed 1
[^e74]: probe `refuse-FHGFF3-gfa` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-gfa.gfa`, expected exit 1, observed 1
[^e75]: probe `read-FHGFF3-gff3` — `bioheaders validate examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e76]: probe `refuse-FHGFF3-jsonld` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-jsonld.jsonld`, expected exit 1, observed 1
[^e77]: `bioheaders convert --help: FHGFF3 supports HTML microdata, not JSON-LD` — this phrase was required to appear in the package (in the file named, or in the help text quoted) while rendering; a refusal is only evidence in the tool's own words
[^e78]: probe `read-FHGFF3-microdata` — `bioheaders validate examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 0, observed 0
[^e79]: probe `write-FHGFF3-json` — `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.json`, expected exit 0, observed 0
[^e80]: probe `write-FHGFF3-yaml` — `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.yaml`, expected exit 0, observed 0
[^e81]: probe `write-FHGFF3-gff3` — `bioheaders combine examples/fhgff3/minimal-reference.fhgff3.json <tmp>/strip-FHGFF3-gff3.gff3 -o <tmp>/write-FHGFF3-gff3.gff3`, expected exit 0, observed 0
[^e82]: probe `write-FHGFF3-microdata` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/write-FHGFF3-microdata.html`, expected exit 0, observed 0
[^e83]: probe `verify-doc-FHGFF3-json` — `bioheaders verify examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e84]: probe `verify-doc-FHGFF3-yaml` — `bioheaders verify examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e85]: probe `verify-FHGFF3-gff3` — `bioheaders verify examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e86]: probe `verify-doc-FHGFF3-microdata` — `bioheaders verify examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e87]: probe `strip-doc-FHGFF3-json` — `bioheaders strip examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e88]: probe `strip-doc-FHGFF3-yaml` — `bioheaders strip examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e89]: probe `strip-FHGFF3-gff3` — `bioheaders strip examples/fhgff3/annotation.fhgff3.gff3 <tmp>/strip-FHGFF3-gff3.gff3`, expected exit 0, observed 0
[^e90]: probe `strip-doc-FHGFF3-microdata` — `bioheaders strip examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e91]: probe `links-doc-FHGFF3-json` — `bioheaders verify-links examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e92]: probe `links-doc-FHGFF3-yaml` — `bioheaders verify-links examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e93]: probe `links-FHGFF3-gff3` — `bioheaders verify-links examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e94]: probe `links-doc-FHGFF3-microdata` — `bioheaders verify-links examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e95]: probe `assess-doc-FHGFF3` — `bioheaders assess examples/fhgff3/minimal-reference.fhgff3.json --format json --output <tmp>/assessdoc-FHGFF3`, expected exit 0, observed 0
[^e96]: probe `assess-FHGFF3-gff3` — `bioheaders assess examples/fhgff3/annotation.fhgff3.gff3 --format json --output <tmp>/assess-FHGFF3-gff3`, expected exit 0, observed 0
[^e97]: probe `index-reject-gff3` — `bioheaders faidx examples/fhgff3/annotation.fhgff3.gff3 -o <tmp>/index-reject-gff3.fai`, expected exit 1, observed 1
[^e98]: `tests/fht_test.py::test_strip_and_convert` — re-found in the tree while rendering; run by `poetry run pytest`
[^e99]: `tests/fht_test.py::test_validate_and_assess_stay_draft_aware` — re-found in the tree while rendering; run by `poetry run pytest`
[^e100]: `tests/fht_conformance_test.py::test_vector_validity` — re-found in the tree while rendering; run by `poetry run pytest`
[^e101]: `tests/fht_test.py::test_family_table_opens_only_fasta` — re-found in the tree while rendering; run by `poetry run pytest`
[^e102]: `tests/fht_test.py::test_unbound_forms_are_refused_not_stretched` — re-found in the tree while rendering; run by `poetry run pytest`
[^e103]: `tests/fht_test.py::test_verify_cli_accepts_and_rejects` — re-found in the tree while rendering; run by `poetry run pytest`
[^e104]: `tests/fht_test.py::test_verify_links_three_verdicts` — re-found in the tree while rendering; run by `poetry run pytest`
[^e105]: `bioheaders/pins.json` row `fhgm-base@none` — printed `ABSENT` by `bioheaders-pin-audit`

Digest of the grid: `9bf2c3d66480d3195b1f521f71629a22` (245 cells = 5 types x 7 operations x 7 serializations).
