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
| observed only | command accepts a diagnostic input with an unsupported binding; not a support claim |

`read` means validate; `write` covers combine/convert. `verify` checks
file integrity; `links` checks supplied parent identity; `index` is faidx.
The matrix records representative paths, not every option combination.
Evidence footnotes distinguish probes executed during rendering from
tests checked for existence. A cited test is not rerun by rendering.

## The grids

### FHR — contract `'2.1'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e1] | yes[^e2] | yes[^e3] | yes[^e4] | observed only[^r-unbound-operation][^e5] | yes[^e6] | yes[^e7] |
| write | yes[^r-document-carries-no-checksum][^e8] | yes[^r-document-carries-no-checksum][^e9] | yes[^e10] | yes[^e11] | no[^r-family-gate][^e12] | yes[^r-document-carries-no-checksum][^e13] | yes[^r-document-carries-no-checksum][^e14] |
| verify | n/a[^r-no-checksum-in-document][^e15] | n/a[^r-no-checksum-in-document][^e16] | yes[^e17] | yes[^e18] | no[^r-family-gate][^e19] | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e21] |
| strip | n/a[^r-no-checksum-in-document][^e22] | n/a[^r-no-checksum-in-document][^e23] | yes[^e24] | yes[^e25] | observed only[^r-unbound-operation][^e26] | n/a[^r-no-checksum-in-document][^e27] | n/a[^r-no-checksum-in-document][^e28] |
| links | n/a[^r-no-checksum-in-document][^e29] | n/a[^r-no-checksum-in-document][^e30] | n/a[^r-links-no-parent-fields][^e31] | n/a[^r-links-no-parent-fields][^e32] | observed only[^r-unbound-operation][^e33] | n/a[^r-no-checksum-in-document][^e34] | n/a[^r-no-checksum-in-document][^e35] |
| assess | n/a[^r-assess-documents][^e36] | n/a[^r-assess-documents][^e36] | yes[^e37] | yes[^e38] | observed only[^r-unbound-operation][^e39] | n/a[^r-assess-documents][^e36] | n/a[^r-assess-documents][^e36] |
| index | no[^r-index-fasta-only][^e40] | no[^r-index-fasta-only][^e41] | yes[^e42][^e43][^e44][^e45] | no[^r-index-fasta-only][^e46] | no[^r-index-fasta-only][^e47] | no[^r-index-fasta-only][^e48] | no[^r-index-fasta-only][^e49] |

Vendored contract copies (`schemas/bundled.json`): v0.3.0 → `fhr-1.json`; v0.3.1 → `fhr-1.json`; v0.4.0 → `fhr-2.0.json`; v0.4.1 → `fhr-2.0.json`; v0.4.2 → `fhr-2.0.json`; v0.5.0 → `fhr-2.1.json`; v0.6.0 → `fhr-2.1.json`.

### FHP — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e50] | yes[^e51] | yes[^e52] | observed only[^r-unbound-operation][^e53] | observed only[^r-unbound-operation][^e54] | yes[^e55] | yes[^e56] |
| write | yes[^r-document-carries-no-checksum][^e57] | yes[^r-document-carries-no-checksum][^e58] | yes[^e59] | no[^r-family-gate][^e60] | no[^r-family-gate][^e61] | yes[^r-document-carries-no-checksum][^e62] | yes[^r-document-carries-no-checksum][^e63] |
| verify | n/a[^r-no-checksum-in-document][^e64] | n/a[^r-no-checksum-in-document][^e65] | yes[^e66] | no[^r-family-gate][^e67] | no[^r-family-gate][^e68] | n/a[^r-no-checksum-in-document][^e69] | n/a[^r-no-checksum-in-document][^e70] |
| strip | n/a[^r-no-checksum-in-document][^e71] | n/a[^r-no-checksum-in-document][^e72] | yes[^e73] | observed only[^r-unbound-operation][^e74] | observed only[^r-unbound-operation][^e75] | n/a[^r-no-checksum-in-document][^e76] | n/a[^r-no-checksum-in-document][^e77] |
| links | n/a[^r-no-checksum-in-document][^e78] | n/a[^r-no-checksum-in-document][^e79] | yes[^r-links-verdicts][^e80][^e81][^e82] | observed only[^r-unbound-operation][^e83] | observed only[^r-unbound-operation][^e84] | n/a[^r-no-checksum-in-document][^e85] | n/a[^r-no-checksum-in-document][^e86] |
| assess | n/a[^r-assess-documents][^e87] | n/a[^r-assess-documents][^e87] | yes[^e88] | observed only[^r-unbound-operation][^e89] | observed only[^r-unbound-operation][^e90] | n/a[^r-assess-documents][^e87] | n/a[^r-assess-documents][^e87] |
| index | no[^r-index-fasta-only][^e40] | no[^r-index-fasta-only][^e41] | yes[^e91][^e92][^e44][^e45] | no[^r-index-fasta-only][^e93] | no[^r-index-fasta-only][^e94] | no[^r-index-fasta-only][^e48] | no[^r-index-fasta-only][^e49] |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhp-1.0.json`; v0.4.1 → `fhp-1.0.json`; v0.4.2 → `fhp-1.0.json`; v0.5.0 → `fhp-1.1.json`; v0.6.0 → `fhp-1.2.json`.

### FHGFF3 — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | yes[^e95] | yes[^e96] | observed only[^r-unbound-operation][^e97] | observed only[^r-unbound-operation][^e98] | yes[^e99] | not verified[^r-unbound-reader] | yes[^r-microdata-experimental][^e100] |
| write | yes[^r-document-carries-no-checksum][^e101] | yes[^r-document-carries-no-checksum][^e102] | no[^r-family-gate][^e103] | no[^r-family-gate][^e104] | yes[^e105] | no[^r-no-binding][^e106][^e107] | yes[^r-microdata-experimental][^e108] |
| verify | n/a[^r-no-checksum-in-document][^e109] | n/a[^r-no-checksum-in-document][^e110] | no[^r-family-gate][^e111] | no[^r-family-gate][^e112] | yes[^r-verify-directives][^e113] | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e114] |
| strip | n/a[^r-no-checksum-in-document][^e115] | n/a[^r-no-checksum-in-document][^e116] | observed only[^r-unbound-operation][^e117] | observed only[^r-unbound-operation][^e118] | yes[^e119] | n/a[^r-no-checksum-in-document][^e27] | n/a[^r-no-checksum-in-document][^e120] |
| links | n/a[^r-no-checksum-in-document][^e121] | n/a[^r-no-checksum-in-document][^e122] | observed only[^r-unbound-operation][^e123] | observed only[^r-unbound-operation][^e124] | yes[^r-links-verdicts][^e125][^e126] | n/a[^r-no-checksum-in-document][^e34] | n/a[^r-no-checksum-in-document][^e127] |
| assess | n/a[^r-assess-documents][^e128] | n/a[^r-assess-documents][^e128] | observed only[^r-unbound-operation][^e129] | observed only[^r-unbound-operation][^e130] | yes[^e131] | n/a[^r-assess-documents][^e36] | n/a[^r-assess-documents][^e128] |
| index | no[^r-index-fasta-only][^e40] | no[^r-index-fasta-only][^e41] | observed only[^r-unbound-operation][^e132] | no[^r-index-fasta-only][^e133] | no[^r-index-fasta-only][^e134] | no[^r-index-fasta-only][^e48] | no[^r-index-fasta-only][^e49] |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhgff3-1.0.json`; v0.4.1 → `fhgff3-1.0.json`; v0.4.2 → `fhgff3-1.0.json`; v0.5.0 → `fhgff3-1.1.json`; v0.6.0 → `fhgff3-1.2.json`.

### FHT — draft lane only, opt-in, no claim of any kind

`BIOHEADERS_EXPERIMENTAL_FHT` opens it; nothing else does. The lane reads `fht-draft.json`, pinned at commit `226f923c28b680edb3c546e99a751482d06aef1a` (sha256 `59ad9641adcb0e5591045c2d894c066d1adc9984cca84c5ff6502f8dad88487e` of those bytes), citation `https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json`. It has no entry in the version registry, no alias URL and no version of its own to name, and every read under the opt-in prints that provenance. Its suite is pinned apart from it: commit `7503b26423296ba09357de66995ca3c9508306af`, sha256 `ab72fc985a2629df5e8ea951936be3c3cf65a4f5a1c782f604ea6902a1d29c58`, 68 vectors.

A `draft lane` mark cites existing native tests of the opt-in path. Rendering checks those citations but does not execute the draft suite. It does not claim released support.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | not verified[^r-draft-no-file-evidence] | draft lane[^r-draft-lane-document][^e135] | draft lane[^r-draft-lane][^e136][^e137] | observed only[^r-unbound-operation][^e138] | observed only[^r-unbound-operation][^e139] | no[^r-draft-no-binding][^e140] | no[^r-draft-no-binding][^e140] |
| write | not verified[^r-draft-no-file-evidence] | draft lane[^r-draft-lane-document][^e135] | draft lane[^r-draft-lane][^e135][^e137] | no[^r-family-gate][^e141] | no[^r-family-gate][^e142] | no[^r-draft-no-binding][^e140] | no[^r-draft-no-binding][^e140] |
| verify | n/a[^r-no-checksum-in-document][^e15] | n/a[^r-no-checksum-in-document][^e16] | draft lane[^r-draft-lane][^e143][^e137] | no[^r-family-gate][^e144] | no[^r-family-gate][^e145] | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e21] |
| strip | n/a[^r-no-checksum-in-document][^e15] | n/a[^r-no-checksum-in-document][^e16] | draft lane[^r-draft-lane][^e135][^e137] | observed only[^r-unbound-operation][^e146] | observed only[^r-unbound-operation][^e147] | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e21] |
| links | n/a[^r-no-checksum-in-document][^e15] | n/a[^r-no-checksum-in-document][^e16] | draft lane[^r-draft-lane][^e148][^e137] | observed only[^r-unbound-operation][^e149] | observed only[^r-unbound-operation][^e150] | n/a[^r-no-checksum-in-document][^e20] | n/a[^r-no-checksum-in-document][^e21] |
| assess | n/a[^r-assess-documents][^e36] | n/a[^r-assess-documents][^e36] | no[^r-draft-assess][^e136] | observed only[^r-unbound-operation][^e151] | observed only[^r-unbound-operation][^e152] | n/a[^r-assess-documents][^e36] | n/a[^r-assess-documents][^e36] |
| index | no[^r-index-fasta-only][^e40] | no[^r-index-fasta-only][^e41] | not verified[^r-index-no-evidence] | no[^r-index-fasta-only][^e153] | no[^r-index-fasta-only][^e154] | no[^r-index-fasta-only][^e48] | no[^r-index-fasta-only][^e49] |

### FHGM — this artifact holds no reference to it

`bioheaders/pins.json` row `fhgm-base@none`, class `base-carrier`, label `draft, not acceptance`, is what says so; the audit prints it as `ABSENT`. The whole grid is one value because the whole of this repository is silent about the model draft, and that silence is a decision with a source, not an oversight. See the scope statements below the tables.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| write | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| verify | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| strip | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| links | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| assess | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |
| index | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] | not here[^r-fhgm-scope][^e155] |

## Commands, and the operations they carry

| console script | entry point | what it is |
| --- | --- | --- |
| `bioheaders` | `bioheaders.cli:main` | the umbrella command: 9 subcommands |
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

13 installed commands: `bioheaders`, 11 `fhr-*` compatibility names, and the audit. Their subcommands are `assess`, `combine`, `convert`, `faidx`, `metadata`, `strip`, `validate`, `verify`, `verify-links` with alias `checksum`. Every `fhr-*` name shares an implementation with its `bioheaders` subcommand, which is why the grids above are per operation rather than per command; `tests/bioheaders_test.py` pins that the two sets stay equal.

## Bundled contract versions

Every listed citation is selected by a CLI validation probe.
Wrong-version and unknown-release probes must reject. Pin rows are
recorded provenance, not a live freshness verdict.

| type | specification tag | schemaVersion | bundled file |
| --- | --- | --- | --- |

Read at the tag's root: `fhr.json`, `fhp.json`, `fhgff3.json`. `schemas/fhp.json` does not exist there and the render fails if it appears; `schemas/` holds `core.yaml`, `shared.yaml` and `versions.json` at that revision.
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
Released contracts are root files; `schemas/fhp.json` is not the contract path.

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

Vendored by ID: 111 of 291 vectors (manifest counts, not interpreter-specific test outcomes).
Per-format executability is a property of the consumer.
The toolkit implements JSON-LD and microdata readers. The native
libraries' 228 pass / 63 not-run ledger therefore cannot describe this
consumer. Missing vendored formats are exercised by the shared checker,
alongside existing native regression tests. Manifest parity is checked by:
- `tests/fhp_test.py::test_fixtures_match_the_specification` — conditional evidence: it skips when `FHR_SPECIFICATION` names no checkout with `conformance/manifest.json`; `pytest.yaml` clones the release tag, so it runs there and on any machine that passes the same path
- `tests/fhgff3_test.py::test_fixtures_match_the_specification` — conditional evidence: it skips when `FHR_SPECIFICATION` names no checkout with `conformance/manifest.json`, and also predates FHGFF3 in an old checkout
- `tests/jsonld_test.py::test_vectors_match_the_specification` — conditional evidence: it skips when `FHR_SPECIFICATION` names no checkout with `conformance/manifest.json`

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
| faidx | FHR/FHP plain and BGZF interoperability: `tests/faidx_test.py::test_samtools_regions_on_headed_files_match_the_stripped_file` and `tests/faidx_test.py::test_pysam_fetch_on_headed_files_matches_the_stripped_file`; FHT compressed indexing not verified here |
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

## Dated measurements

Three facts about this artifact cannot be re-measured by a render:
one needs a second repository, one a second interpreter, and one is a
property of the other lanes. They are recorded with the command, the
date and the printed result, so they can be repeated and challenged.
None of them sets a cell.

- **the draft lane's own suite** — `BIOHEADERS_EXPERIMENTAL_FHT=1 FHT_SPECIFICATION=<checkout at the pinned suite revision> python -m pytest tests/fht_conformance_test.py -q` on 2026-11-16: `75 passed, 62 skipped` of 137 collected, exit status 0. The same command without the opt-in skips the file whole, and a default `poetry run pytest` never reads those bytes at all.
- **one commit, both interpreters** — `python scripts/render_capability_matrix.py` run from the same commit under Python 3.9.25 and under 3.13.16 wrote byte-identical documents (`cmp`, 2026-11-16). That is why this file quotes no interpreter version: it is not part of a capability claim, and the two `pytest.yaml` lanes would otherwise argue with each other.
- **what one lane of the native suite actually executes** — `tests/jsonld_test.py::test_conformance_vectors` — conditional evidence: it needs `pyld`, which the dev group installs only for Python 3.10 and later: on the 3.13 lane all 37 parametrizations run, on the 3.9 lane they all skip (measured 2026-11-16 with a 3.9 environment: `SKIPPED [37] ... could not import 'pyld'`), so the by-id count this document publishes describes the lane that executes them. The by-id ledger above is therefore 111 of the vectors in the suite on the 3.13 lane and 74 of them on the 3.9 lane. The document is identical in both; the executed count is not, and `--require-format` in the shared-conformance job keeps all six formats covered regardless.

## Not verified

- `index` for FHT, and `assess` for a draft-carrying FASTA beyond its `not_assessed` verdict — no probe or test measures either; the gate is asked in-process, but nothing runs a draft header through `faidx`
- external samtools and pysam interoperability during rendering — the native faidx tests cover FHR and FHP, plain and BGZF. Rendering checks those citations and recomputes index fields, but does not run the external tools; the native CI workflow installs them
- gzip and BGZF for JSON-LD and microdata as a documented contract — the shared suite holds no compressed vector of either format, and `open_input` detects compression by magic bytes on any input. The probes show a gzip member of each is readable; nobody has specified what compressed metadata documents mean for the checksum, because they carry no body
- `assess --online` identifier resolution — opt-in and makes network calls; deliberately not exercised here
- the Galaxy wrappers and the container images — `galaxy/tools/fair_bioheaders` is linted by `galaxy-tools.yml` with `planemo`, which this render does not run, and `Dockerfile` and `container.yml` build from a *released* wheel. Nothing in this file says a word about either
- the `assess` conformance section for a *draft* header beyond its recorded `not_assessed` verdict — the rubric follows the released contracts, and the draft lane deliberately changes nothing there; nothing measures a draft-scored assessment
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
| `cross-FHGFF3-fasta-assess` | `bioheaders assess <tmp>/cross-FHGFF3.fasta --format json --output <tmp>/cross-FHGFF3-fasta-assessment` | 0 |
| `cross-FHGFF3-fasta-index` | `bioheaders faidx <tmp>/cross-FHGFF3.fasta -o <tmp>/cross-FHGFF3-fasta.fai` | 0 |
| `cross-FHGFF3-fasta-links` | `bioheaders verify-links <tmp>/cross-FHGFF3.fasta` | 0 |
| `cross-FHGFF3-fasta-read` | `bioheaders validate <tmp>/cross-FHGFF3.fasta` | 0 |
| `cross-FHGFF3-fasta-strip` | `bioheaders strip <tmp>/cross-FHGFF3.fasta <tmp>/cross-FHGFF3-fasta-stripped` | 0 |
| `cross-FHGFF3-fasta-verify` | `bioheaders verify <tmp>/cross-FHGFF3.fasta` | 1 |
| `cross-FHGFF3-gfa-assess` | `bioheaders assess <tmp>/cross-FHGFF3.gfa --format json --output <tmp>/cross-FHGFF3-gfa-assessment` | 0 |
| `cross-FHGFF3-gfa-index` | `bioheaders faidx <tmp>/cross-FHGFF3.gfa -o <tmp>/cross-FHGFF3-gfa.fai` | 1 |
| `cross-FHGFF3-gfa-links` | `bioheaders verify-links <tmp>/cross-FHGFF3.gfa` | 0 |
| `cross-FHGFF3-gfa-read` | `bioheaders validate <tmp>/cross-FHGFF3.gfa` | 0 |
| `cross-FHGFF3-gfa-strip` | `bioheaders strip <tmp>/cross-FHGFF3.gfa <tmp>/cross-FHGFF3-gfa-stripped` | 0 |
| `cross-FHGFF3-gfa-verify` | `bioheaders verify <tmp>/cross-FHGFF3.gfa` | 1 |
| `cross-FHP-gfa-assess` | `bioheaders assess <tmp>/cross-FHP.gfa --format json --output <tmp>/cross-FHP-gfa-assessment` | 0 |
| `cross-FHP-gfa-index` | `bioheaders faidx <tmp>/cross-FHP.gfa -o <tmp>/cross-FHP-gfa.fai` | 1 |
| `cross-FHP-gfa-links` | `bioheaders verify-links <tmp>/cross-FHP.gfa` | 0 |
| `cross-FHP-gfa-read` | `bioheaders validate <tmp>/cross-FHP.gfa` | 0 |
| `cross-FHP-gfa-strip` | `bioheaders strip <tmp>/cross-FHP.gfa <tmp>/cross-FHP-gfa-stripped` | 0 |
| `cross-FHP-gfa-verify` | `bioheaders verify <tmp>/cross-FHP.gfa` | 1 |
| `cross-FHP-gff3-assess` | `bioheaders assess <tmp>/cross-FHP.gff3 --format json --output <tmp>/cross-FHP-gff3-assessment` | 0 |
| `cross-FHP-gff3-index` | `bioheaders faidx <tmp>/cross-FHP.gff3 -o <tmp>/cross-FHP-gff3.fai` | 1 |
| `cross-FHP-gff3-links` | `bioheaders verify-links <tmp>/cross-FHP.gff3` | 0 |
| `cross-FHP-gff3-read` | `bioheaders validate <tmp>/cross-FHP.gff3` | 0 |
| `cross-FHP-gff3-strip` | `bioheaders strip <tmp>/cross-FHP.gff3 <tmp>/cross-FHP-gff3-stripped` | 0 |
| `cross-FHP-gff3-verify` | `bioheaders verify <tmp>/cross-FHP.gff3` | 1 |
| `cross-FHR-gff3-assess` | `bioheaders assess <tmp>/cross-FHR.gff3 --format json --output <tmp>/cross-FHR-gff3-assessment` | 0 |
| `cross-FHR-gff3-index` | `bioheaders faidx <tmp>/cross-FHR.gff3 -o <tmp>/cross-FHR-gff3.fai` | 1 |
| `cross-FHR-gff3-links` | `bioheaders verify-links <tmp>/cross-FHR.gff3` | 0 |
| `cross-FHR-gff3-read` | `bioheaders validate <tmp>/cross-FHR.gff3` | 0 |
| `cross-FHR-gff3-strip` | `bioheaders strip <tmp>/cross-FHR.gff3 <tmp>/cross-FHR-gff3-stripped` | 0 |
| `cross-FHR-gff3-verify` | `bioheaders verify <tmp>/cross-FHR.gff3` | 1 |
| `cross-FHT-gfa-assess` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders assess <tmp>/cross-FHT.gfa --format json --output <tmp>/cross-FHT-gfa-assessment` | 0 |
| `cross-FHT-gfa-index` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders faidx <tmp>/cross-FHT.gfa -o <tmp>/cross-FHT-gfa.fai` | 1 |
| `cross-FHT-gfa-links` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify-links <tmp>/cross-FHT.gfa` | 0 |
| `cross-FHT-gfa-read` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders validate <tmp>/cross-FHT.gfa` | 0 |
| `cross-FHT-gfa-strip` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders strip <tmp>/cross-FHT.gfa <tmp>/cross-FHT-gfa-stripped` | 0 |
| `cross-FHT-gfa-verify` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify <tmp>/cross-FHT.gfa` | 1 |
| `cross-FHT-gfa-write` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders convert <tmp>/cross-FHT-gfa.json <tmp>/cross-FHT-gfa-output.gfa` | 1 |
| `cross-FHT-gff3-assess` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders assess <tmp>/cross-FHT.gff3 --format json --output <tmp>/cross-FHT-gff3-assessment` | 0 |
| `cross-FHT-gff3-index` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders faidx <tmp>/cross-FHT.gff3 -o <tmp>/cross-FHT-gff3.fai` | 1 |
| `cross-FHT-gff3-links` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify-links <tmp>/cross-FHT.gff3` | 0 |
| `cross-FHT-gff3-read` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders validate <tmp>/cross-FHT.gff3` | 0 |
| `cross-FHT-gff3-strip` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders strip <tmp>/cross-FHT.gff3 <tmp>/cross-FHT-gff3-stripped` | 0 |
| `cross-FHT-gff3-verify` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify <tmp>/cross-FHT.gff3` | 1 |
| `cross-FHT-gff3-write` | `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders convert <tmp>/cross-FHT-gff3.json <tmp>/cross-FHT-gff3-output.gff3` | 1 |
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
| `index-wrap-build-FHP` | `bioheaders combine examples/fhp/minimal-predicted.fhp.json <tmp>/wrap-body-FHP.fasta -o <tmp>/wrap-FHP.fasta` | 0 |
| `index-wrap-build-FHR` | `bioheaders combine examples/example.fhr.json <tmp>/wrap-body-FHR.fasta -o <tmp>/wrap-FHR.fasta` | 0 |
| `index-wrapped-FHP` | `bioheaders faidx <tmp>/wrap-FHP.fasta -o <tmp>/index-wrapped-FHP.fai` | 0 |
| `index-wrapped-FHR` | `bioheaders faidx <tmp>/wrap-FHR.fasta -o <tmp>/index-wrapped-FHR.fai` | 0 |
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

[^r-unbound-operation]: the command accepts this diagnostic input, but the header-type/carrier pair has no supported binding. This is observed command behavior only, not contract support. A permissive strip or metadata reader is not a writer or verifier: each operation has its own probe
[^r-document-carries-no-checksum]: written from a carrier; a bare metadata document has no sequence bytes for the checksum to cover, so it is metadata, not a file-bound header
[^r-family-gate]: this operation refuses the header-type/carrier pair through `validate_header_family` in `bioheaders/cli.py`. Its own CLI probe records the refusal; other operations have separate probes
[^r-no-checksum-in-document]: the file-bound SHA-512/256 covers a header block plus body bytes. A metadata document has no body, so the command names the input formats it takes and stops: a vacuous pass would be worse than an `n/a`. The probe shows the refusal, and the gate is about the serialization, not the type
[^r-links-no-parent-fields]: the current contract has neither derivedFrom nor genomeReference parent fields. verify-links accepts the file but reports no parent files recorded; it makes no parent comparison
[^r-assess-documents]: `assess` scores the header block of a *data* file. Given a bare metadata document it reports `unknown-text`, reads 0 header lines and publishes no conformance section; the probe asserts exactly that, so its exit status 0 is not read as an assessment
[^r-index-fasta-only]: `faidx` parses FASTA. Anything else fails as a format error, which is the honest outcome: an index of bytes samtools cannot read is worse than no index
[^r-links-verdicts]: these render probes supply no parent files, so they do not earn matched/stale-parent verdicts. The cited native tests exercise those comparisons. Supplied parent files are rehashed and verified before comparison with the child's recorded digest; the command does not invent a recorded parent identity or a SeqCol identifier
[^r-unbound-reader]: no reader binding or representative input is established for this pair. The writer's refusal does not establish reader behavior
[^r-microdata-experimental]: the binding itself is not adopted or released (`EXPERIMENTAL = True` in `bioheaders/fhgff3_microdata.py`, which warns on every read and write; merged FHGFF3#16 recorded canonical documentation only): implemented and measured here, not a published serialization
[^r-no-binding]: no reviewed binding for that pair is published, and the writer refuses instead of borrowing another type's identity
[^r-verify-directives]: for an annotation header the command also cross-checks the GFF3 directives against the header block, which no other carrier has
[^r-draft-no-file-evidence]: no file-level probe or test covers the draft lane here, so the cell stays unearned rather than being closed by analogy with FASTA
[^r-draft-lane-document]: the lane carries the header between a FASTA carrier and YAML: `convert` writes it, `combine` reads it back and re-verifies. The carrier still holds the checksum, so the document is metadata only
[^r-draft-lane]: reached only with `BIOHEADERS_EXPERIMENTAL_FHT` set, against `fht-draft.json` pinned at commit `226f923c28b6…` (sha256 `59ad9641adcb…`). A lane over pinned development bytes is a preview: it is not a claim about the type's status, and the default run does not take it
[^r-draft-no-binding]: the lane refuses rather than stretching a published identity over development bytes: no binding for that pair has been reviewed
[^r-draft-assess]: `assess` reads the citation and reports its conformance section as `not_assessed`: the rubric follows the released contracts, and the lane deliberately leaves that alone
[^r-index-no-evidence]: neither measured nor refused: no probe and no test covers it, so no mark is invented
[^r-fhgm-scope]: this artifact has no model implementation: no vendored draft contract, and no base or carrier pin of its own, which `bioheaders-pin-audit` reports as `fhgm-base@none` / `ABSENT` with the reason recorded in `bioheaders/pins.json`. A scope statement, not a hole this document fills: the lane is FAIR-bioHeaders-Tools#135, and the cell is unrun rather than run and unrecorded

## Evidence, in full

[^e1]: probe `read-FHR-json` — `bioheaders validate examples/example.fhr.json`, expected exit 0, observed 0
[^e2]: probe `read-FHR-yaml` — `bioheaders validate examples/example.fhr.yaml`, expected exit 0, observed 0
[^e3]: probe `read-FHR-fasta` — `bioheaders validate examples/example.fhr.fasta`, expected exit 0, observed 0
[^e4]: probe `read-FHR-gfa` — `bioheaders validate examples/example.fhr.gfa`, expected exit 0, observed 0
[^e5]: probe `cross-FHR-gff3-read` — `bioheaders validate <tmp>/cross-FHR.gff3`, expected exit 0, observed 0
[^e6]: probe `read-FHR-jsonld` — `bioheaders validate examples/example.fhr.jsonld`, expected exit 0, observed 0
[^e7]: probe `read-FHR-microdata` — `bioheaders validate examples/example.microdata.fhr.html`, expected exit 0, observed 0
[^e8]: probe `write-FHR-json` — `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.json`, expected exit 0, observed 0
[^e9]: probe `write-FHR-yaml` — `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.yaml`, expected exit 0, observed 0
[^e10]: probe `write-FHR-fasta` — `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-fasta.fasta -o <tmp>/write-FHR-fasta.fasta`, expected exit 0, observed 0
[^e11]: probe `write-FHR-gfa` — `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-gfa.gfa -o <tmp>/write-FHR-gfa.gfa`, expected exit 0, observed 0
[^e12]: probe `refuse-FHR-gff3` — `bioheaders convert examples/example.fhr.json <tmp>/refuse-FHR-gff3.gff3`, expected exit 1, observed 1
[^e13]: probe `write-FHR-jsonld` — `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-jsonld.jsonld`, expected exit 0, observed 0
[^e14]: probe `write-FHR-microdata` — `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-microdata.html`, expected exit 0, observed 0
[^e15]: probe `verify-doc-FHR-json` — `bioheaders verify examples/example.fhr.json`, expected exit 1, observed 1
[^e16]: probe `verify-doc-FHR-yaml` — `bioheaders verify examples/example.fhr.yaml`, expected exit 1, observed 1
[^e17]: probe `verify-FHR-fasta` — `bioheaders verify examples/example.fhr.fasta`, expected exit 0, observed 0
[^e18]: probe `verify-FHR-gfa` — `bioheaders verify examples/example.fhr.gfa`, expected exit 0, observed 0
[^e19]: probe `cross-FHR-gff3-verify` — `bioheaders verify <tmp>/cross-FHR.gff3`, expected exit 1, observed 1
[^e20]: probe `verify-doc-FHR-jsonld` — `bioheaders verify examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e21]: probe `verify-doc-FHR-microdata` — `bioheaders verify examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e22]: probe `strip-doc-FHR-json` — `bioheaders strip examples/example.fhr.json`, expected exit 1, observed 1
[^e23]: probe `strip-doc-FHR-yaml` — `bioheaders strip examples/example.fhr.yaml`, expected exit 1, observed 1
[^e24]: probe `strip-FHR-fasta` — `bioheaders strip examples/example.fhr.fasta <tmp>/strip-FHR-fasta.fasta`, expected exit 0, observed 0
[^e25]: probe `strip-FHR-gfa` — `bioheaders strip examples/example.fhr.gfa <tmp>/strip-FHR-gfa.gfa`, expected exit 0, observed 0
[^e26]: probe `cross-FHR-gff3-strip` — `bioheaders strip <tmp>/cross-FHR.gff3 <tmp>/cross-FHR-gff3-stripped`, expected exit 0, observed 0
[^e27]: probe `strip-doc-FHR-jsonld` — `bioheaders strip examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e28]: probe `strip-doc-FHR-microdata` — `bioheaders strip examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e29]: probe `links-doc-FHR-json` — `bioheaders verify-links examples/example.fhr.json`, expected exit 1, observed 1
[^e30]: probe `links-doc-FHR-yaml` — `bioheaders verify-links examples/example.fhr.yaml`, expected exit 1, observed 1
[^e31]: probe `links-FHR-fasta` — `bioheaders verify-links examples/example.fhr.fasta`, expected exit 0, observed 0
[^e32]: probe `links-FHR-gfa` — `bioheaders verify-links examples/example.fhr.gfa`, expected exit 0, observed 0
[^e33]: probe `cross-FHR-gff3-links` — `bioheaders verify-links <tmp>/cross-FHR.gff3`, expected exit 0, observed 0
[^e34]: probe `links-doc-FHR-jsonld` — `bioheaders verify-links examples/example.fhr.jsonld`, expected exit 1, observed 1
[^e35]: probe `links-doc-FHR-microdata` — `bioheaders verify-links examples/example.microdata.fhr.html`, expected exit 1, observed 1
[^e36]: probe `assess-doc-FHR` — `bioheaders assess examples/example.fhr.json --format json --output <tmp>/assessdoc-FHR`, expected exit 0, observed 0
[^e37]: probe `assess-FHR-fasta` — `bioheaders assess examples/example.fhr.fasta --format json --output <tmp>/assess-FHR-fasta`, expected exit 0, observed 0
[^e38]: probe `assess-FHR-gfa` — `bioheaders assess examples/example.fhr.gfa --format json --output <tmp>/assess-FHR-gfa`, expected exit 0, observed 0
[^e39]: probe `cross-FHR-gff3-assess` — `bioheaders assess <tmp>/cross-FHR.gff3 --format json --output <tmp>/cross-FHR-gff3-assessment`, expected exit 0, observed 0
[^e40]: probe `index-reject-json` — `bioheaders faidx examples/example.fhr.json -o <tmp>/index-reject-json.fai`, expected exit 1, observed 1
[^e41]: probe `index-reject-yaml` — `bioheaders faidx examples/example.fhr.yaml -o <tmp>/index-reject-yaml.fai`, expected exit 1, observed 1
[^e42]: probe `index-FHR` — `bioheaders faidx examples/example.fhr.fasta -o <tmp>/index-FHR.fai`, expected exit 0, observed 0
[^e43]: probe `index-wrapped-FHR` — `bioheaders faidx <tmp>/wrap-FHR.fasta -o <tmp>/index-wrapped-FHR.fai`, expected exit 0, observed 0
[^e44]: `tests/faidx_test.py::test_samtools_regions_on_headed_files_match_the_stripped_file` — re-found in the tree while rendering; conditional evidence: it needs `samtools` and `bgzip` on PATH: `pytest.yaml` installs them, and a machine without them skips the test. Citing it here claims the evidence exists, not that a default run collected it
[^e45]: `tests/faidx_test.py::test_pysam_fetch_on_headed_files_matches_the_stripped_file` — re-found in the tree while rendering; conditional evidence: it needs `pysam`: `pytest.yaml` installs it, and a machine without it skips the test. Citing it here claims the evidence exists, not that a default run collected it
[^e46]: probe `index-reject-gfa` — `bioheaders faidx examples/example.fhr.gfa -o <tmp>/index-reject-gfa.fai`, expected exit 1, observed 1
[^e47]: probe `cross-FHR-gff3-index` — `bioheaders faidx <tmp>/cross-FHR.gff3 -o <tmp>/cross-FHR-gff3.fai`, expected exit 1, observed 1
[^e48]: probe `index-reject-jsonld` — `bioheaders faidx examples/example.fhr.jsonld -o <tmp>/index-reject-jsonld.fai`, expected exit 1, observed 1
[^e49]: probe `index-reject-microdata` — `bioheaders faidx examples/example.microdata.fhr.html -o <tmp>/index-reject-microdata.fai`, expected exit 1, observed 1
[^e50]: probe `read-FHP-json` — `bioheaders validate examples/fhp/minimal-predicted.fhp.json`, expected exit 0, observed 0
[^e51]: probe `read-FHP-yaml` — `bioheaders validate examples/fhp/rich-mixed.fhp.yaml`, expected exit 0, observed 0
[^e52]: probe `read-FHP-fasta` — `bioheaders validate examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e53]: probe `cross-FHP-gfa-read` — `bioheaders validate <tmp>/cross-FHP.gfa`, expected exit 0, observed 0
[^e54]: probe `cross-FHP-gff3-read` — `bioheaders validate <tmp>/cross-FHP.gff3`, expected exit 0, observed 0
[^e55]: probe `read-FHP-jsonld` — `bioheaders validate examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 0, observed 0
[^e56]: probe `read-FHP-microdata` — `bioheaders validate examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 0, observed 0
[^e57]: probe `write-FHP-json` — `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.json`, expected exit 0, observed 0
[^e58]: probe `write-FHP-yaml` — `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.yaml`, expected exit 0, observed 0
[^e59]: probe `write-FHP-fasta` — `bioheaders combine examples/fhp/minimal-predicted.fhp.json <tmp>/strip-FHP-fasta.fasta -o <tmp>/write-FHP-fasta.fasta`, expected exit 0, observed 0
[^e60]: probe `refuse-FHP-gfa` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gfa.gfa`, expected exit 1, observed 1
[^e61]: probe `refuse-FHP-gff3` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gff3.gff3`, expected exit 1, observed 1
[^e62]: probe `write-FHP-jsonld` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-jsonld.jsonld`, expected exit 0, observed 0
[^e63]: probe `write-FHP-microdata` — `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-microdata.html`, expected exit 0, observed 0
[^e64]: probe `verify-doc-FHP-json` — `bioheaders verify examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e65]: probe `verify-doc-FHP-yaml` — `bioheaders verify examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e66]: probe `verify-FHP-fasta` — `bioheaders verify examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e67]: probe `cross-FHP-gfa-verify` — `bioheaders verify <tmp>/cross-FHP.gfa`, expected exit 1, observed 1
[^e68]: probe `cross-FHP-gff3-verify` — `bioheaders verify <tmp>/cross-FHP.gff3`, expected exit 1, observed 1
[^e69]: probe `verify-doc-FHP-jsonld` — `bioheaders verify examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e70]: probe `verify-doc-FHP-microdata` — `bioheaders verify examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e71]: probe `strip-doc-FHP-json` — `bioheaders strip examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e72]: probe `strip-doc-FHP-yaml` — `bioheaders strip examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e73]: probe `strip-FHP-fasta` — `bioheaders strip examples/fhp/example.fhp.fasta <tmp>/strip-FHP-fasta.fasta`, expected exit 0, observed 0
[^e74]: probe `cross-FHP-gfa-strip` — `bioheaders strip <tmp>/cross-FHP.gfa <tmp>/cross-FHP-gfa-stripped`, expected exit 0, observed 0
[^e75]: probe `cross-FHP-gff3-strip` — `bioheaders strip <tmp>/cross-FHP.gff3 <tmp>/cross-FHP-gff3-stripped`, expected exit 0, observed 0
[^e76]: probe `strip-doc-FHP-jsonld` — `bioheaders strip examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e77]: probe `strip-doc-FHP-microdata` — `bioheaders strip examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e78]: probe `links-doc-FHP-json` — `bioheaders verify-links examples/fhp/minimal-predicted.fhp.json`, expected exit 1, observed 1
[^e79]: probe `links-doc-FHP-yaml` — `bioheaders verify-links examples/fhp/rich-mixed.fhp.yaml`, expected exit 1, observed 1
[^e80]: probe `links-FHP-fasta` — `bioheaders verify-links examples/fhp/example.fhp.fasta`, expected exit 0, observed 0
[^e81]: `tests/fhp_test.py::test_links_matched_and_not_checked` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e82]: `tests/fhp_test.py::test_links_not_matched` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e83]: probe `cross-FHP-gfa-links` — `bioheaders verify-links <tmp>/cross-FHP.gfa`, expected exit 0, observed 0
[^e84]: probe `cross-FHP-gff3-links` — `bioheaders verify-links <tmp>/cross-FHP.gff3`, expected exit 0, observed 0
[^e85]: probe `links-doc-FHP-jsonld` — `bioheaders verify-links examples/fhp/minimal-predicted.fhp.jsonld`, expected exit 1, observed 1
[^e86]: probe `links-doc-FHP-microdata` — `bioheaders verify-links examples/fhp/rich-microdata.microdata.fhp.html`, expected exit 1, observed 1
[^e87]: probe `assess-doc-FHP` — `bioheaders assess examples/fhp/minimal-predicted.fhp.json --format json --output <tmp>/assessdoc-FHP`, expected exit 0, observed 0
[^e88]: probe `assess-FHP-fasta` — `bioheaders assess examples/fhp/example.fhp.fasta --format json --output <tmp>/assess-FHP-fasta`, expected exit 0, observed 0
[^e89]: probe `cross-FHP-gfa-assess` — `bioheaders assess <tmp>/cross-FHP.gfa --format json --output <tmp>/cross-FHP-gfa-assessment`, expected exit 0, observed 0
[^e90]: probe `cross-FHP-gff3-assess` — `bioheaders assess <tmp>/cross-FHP.gff3 --format json --output <tmp>/cross-FHP-gff3-assessment`, expected exit 0, observed 0
[^e91]: probe `index-FHP` — `bioheaders faidx examples/fhp/example.fhp.fasta -o <tmp>/index-FHP.fai`, expected exit 0, observed 0
[^e92]: probe `index-wrapped-FHP` — `bioheaders faidx <tmp>/wrap-FHP.fasta -o <tmp>/index-wrapped-FHP.fai`, expected exit 0, observed 0
[^e93]: probe `cross-FHP-gfa-index` — `bioheaders faidx <tmp>/cross-FHP.gfa -o <tmp>/cross-FHP-gfa.fai`, expected exit 1, observed 1
[^e94]: probe `cross-FHP-gff3-index` — `bioheaders faidx <tmp>/cross-FHP.gff3 -o <tmp>/cross-FHP-gff3.fai`, expected exit 1, observed 1
[^e95]: probe `read-FHGFF3-json` — `bioheaders validate examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 0, observed 0
[^e96]: probe `read-FHGFF3-yaml` — `bioheaders validate examples/fhgff3/rich.fhgff3.yaml`, expected exit 0, observed 0
[^e97]: probe `cross-FHGFF3-fasta-read` — `bioheaders validate <tmp>/cross-FHGFF3.fasta`, expected exit 0, observed 0
[^e98]: probe `cross-FHGFF3-gfa-read` — `bioheaders validate <tmp>/cross-FHGFF3.gfa`, expected exit 0, observed 0
[^e99]: probe `read-FHGFF3-gff3` — `bioheaders validate examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e100]: probe `read-FHGFF3-microdata` — `bioheaders validate examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 0, observed 0
[^e101]: probe `write-FHGFF3-json` — `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.json`, expected exit 0, observed 0
[^e102]: probe `write-FHGFF3-yaml` — `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.yaml`, expected exit 0, observed 0
[^e103]: probe `refuse-FHGFF3-fasta` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-fasta.fasta`, expected exit 1, observed 1
[^e104]: probe `refuse-FHGFF3-gfa` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-gfa.gfa`, expected exit 1, observed 1
[^e105]: probe `write-FHGFF3-gff3` — `bioheaders combine examples/fhgff3/minimal-reference.fhgff3.json <tmp>/strip-FHGFF3-gff3.gff3 -o <tmp>/write-FHGFF3-gff3.gff3`, expected exit 0, observed 0
[^e106]: probe `refuse-FHGFF3-jsonld` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-jsonld.jsonld`, expected exit 1, observed 1
[^e107]: `bioheaders convert --help: FHGFF3 supports HTML microdata, not JSON-LD` — this phrase was required to appear in the package (in the file named, or in the help text quoted) while rendering; a refusal is only evidence in the tool's own words
[^e108]: probe `write-FHGFF3-microdata` — `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/write-FHGFF3-microdata.html`, expected exit 0, observed 0
[^e109]: probe `verify-doc-FHGFF3-json` — `bioheaders verify examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e110]: probe `verify-doc-FHGFF3-yaml` — `bioheaders verify examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e111]: probe `cross-FHGFF3-fasta-verify` — `bioheaders verify <tmp>/cross-FHGFF3.fasta`, expected exit 1, observed 1
[^e112]: probe `cross-FHGFF3-gfa-verify` — `bioheaders verify <tmp>/cross-FHGFF3.gfa`, expected exit 1, observed 1
[^e113]: probe `verify-FHGFF3-gff3` — `bioheaders verify examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e114]: probe `verify-doc-FHGFF3-microdata` — `bioheaders verify examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e115]: probe `strip-doc-FHGFF3-json` — `bioheaders strip examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e116]: probe `strip-doc-FHGFF3-yaml` — `bioheaders strip examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e117]: probe `cross-FHGFF3-fasta-strip` — `bioheaders strip <tmp>/cross-FHGFF3.fasta <tmp>/cross-FHGFF3-fasta-stripped`, expected exit 0, observed 0
[^e118]: probe `cross-FHGFF3-gfa-strip` — `bioheaders strip <tmp>/cross-FHGFF3.gfa <tmp>/cross-FHGFF3-gfa-stripped`, expected exit 0, observed 0
[^e119]: probe `strip-FHGFF3-gff3` — `bioheaders strip examples/fhgff3/annotation.fhgff3.gff3 <tmp>/strip-FHGFF3-gff3.gff3`, expected exit 0, observed 0
[^e120]: probe `strip-doc-FHGFF3-microdata` — `bioheaders strip examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e121]: probe `links-doc-FHGFF3-json` — `bioheaders verify-links examples/fhgff3/minimal-reference.fhgff3.json`, expected exit 1, observed 1
[^e122]: probe `links-doc-FHGFF3-yaml` — `bioheaders verify-links examples/fhgff3/rich.fhgff3.yaml`, expected exit 1, observed 1
[^e123]: probe `cross-FHGFF3-fasta-links` — `bioheaders verify-links <tmp>/cross-FHGFF3.fasta`, expected exit 0, observed 0
[^e124]: probe `cross-FHGFF3-gfa-links` — `bioheaders verify-links <tmp>/cross-FHGFF3.gfa`, expected exit 0, observed 0
[^e125]: probe `links-FHGFF3-gff3` — `bioheaders verify-links examples/fhgff3/annotation.fhgff3.gff3`, expected exit 0, observed 0
[^e126]: `tests/fhgff3_test.py::test_links_matched_and_stale` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e127]: probe `links-doc-FHGFF3-microdata` — `bioheaders verify-links examples/fhgff3/rich-microdata.microdata.fhgff3.html`, expected exit 1, observed 1
[^e128]: probe `assess-doc-FHGFF3` — `bioheaders assess examples/fhgff3/minimal-reference.fhgff3.json --format json --output <tmp>/assessdoc-FHGFF3`, expected exit 0, observed 0
[^e129]: probe `cross-FHGFF3-fasta-assess` — `bioheaders assess <tmp>/cross-FHGFF3.fasta --format json --output <tmp>/cross-FHGFF3-fasta-assessment`, expected exit 0, observed 0
[^e130]: probe `cross-FHGFF3-gfa-assess` — `bioheaders assess <tmp>/cross-FHGFF3.gfa --format json --output <tmp>/cross-FHGFF3-gfa-assessment`, expected exit 0, observed 0
[^e131]: probe `assess-FHGFF3-gff3` — `bioheaders assess examples/fhgff3/annotation.fhgff3.gff3 --format json --output <tmp>/assess-FHGFF3-gff3`, expected exit 0, observed 0
[^e132]: probe `cross-FHGFF3-fasta-index` — `bioheaders faidx <tmp>/cross-FHGFF3.fasta -o <tmp>/cross-FHGFF3-fasta.fai`, expected exit 0, observed 0
[^e133]: probe `cross-FHGFF3-gfa-index` — `bioheaders faidx <tmp>/cross-FHGFF3.gfa -o <tmp>/cross-FHGFF3-gfa.fai`, expected exit 1, observed 1
[^e134]: probe `index-reject-gff3` — `bioheaders faidx examples/fhgff3/annotation.fhgff3.gff3 -o <tmp>/index-reject-gff3.fai`, expected exit 1, observed 1
[^e135]: `tests/fht_test.py::test_strip_and_convert` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e136]: `tests/fht_test.py::test_validate_and_assess_stay_draft_aware` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e137]: `tests/fht_conformance_test.py::test_vector_validity` — re-found in the tree while rendering; conditional evidence: it skips unless `BIOHEADERS_EXPERIMENTAL_FHT=1` is set *and* `FHT_SPECIFICATION` points at a checkout with `conformance/manifest.json`; measured on 2026-11-16 against the suite revision pinned under `drafts.FHT.suite` in `bioheaders/schemas/bundled.json`: `75 passed, 62 skipped` of 137 collected, exit status 0, where the 62 skips are the parent-link test for the vectors that record no parent file. Citing it here claims the evidence exists, not that a default run collected it
[^e138]: probe `cross-FHT-gfa-read` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders validate <tmp>/cross-FHT.gfa`, expected exit 0, observed 0
[^e139]: probe `cross-FHT-gff3-read` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders validate <tmp>/cross-FHT.gff3`, expected exit 0, observed 0
[^e140]: `tests/fht_test.py::test_unbound_forms_are_refused_not_stretched` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e141]: probe `cross-FHT-gfa-write` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders convert <tmp>/cross-FHT-gfa.json <tmp>/cross-FHT-gfa-output.gfa`, expected exit 1, observed 1
[^e142]: probe `cross-FHT-gff3-write` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders convert <tmp>/cross-FHT-gff3.json <tmp>/cross-FHT-gff3-output.gff3`, expected exit 1, observed 1
[^e143]: `tests/fht_test.py::test_verify_cli_accepts_and_rejects` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e144]: probe `cross-FHT-gfa-verify` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify <tmp>/cross-FHT.gfa`, expected exit 1, observed 1
[^e145]: probe `cross-FHT-gff3-verify` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify <tmp>/cross-FHT.gff3`, expected exit 1, observed 1
[^e146]: probe `cross-FHT-gfa-strip` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders strip <tmp>/cross-FHT.gfa <tmp>/cross-FHT-gfa-stripped`, expected exit 0, observed 0
[^e147]: probe `cross-FHT-gff3-strip` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders strip <tmp>/cross-FHT.gff3 <tmp>/cross-FHT-gff3-stripped`, expected exit 0, observed 0
[^e148]: `tests/fht_test.py::test_verify_links_three_verdicts` — re-found in the tree while rendering; a default `poetry run pytest` selects it
[^e149]: probe `cross-FHT-gfa-links` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify-links <tmp>/cross-FHT.gfa`, expected exit 0, observed 0
[^e150]: probe `cross-FHT-gff3-links` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders verify-links <tmp>/cross-FHT.gff3`, expected exit 0, observed 0
[^e151]: probe `cross-FHT-gfa-assess` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders assess <tmp>/cross-FHT.gfa --format json --output <tmp>/cross-FHT-gfa-assessment`, expected exit 0, observed 0
[^e152]: probe `cross-FHT-gff3-assess` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders assess <tmp>/cross-FHT.gff3 --format json --output <tmp>/cross-FHT-gff3-assessment`, expected exit 0, observed 0
[^e153]: probe `cross-FHT-gfa-index` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders faidx <tmp>/cross-FHT.gfa -o <tmp>/cross-FHT-gfa.fai`, expected exit 1, observed 1
[^e154]: probe `cross-FHT-gff3-index` — `BIOHEADERS_EXPERIMENTAL_FHT=1 bioheaders faidx <tmp>/cross-FHT.gff3 -o <tmp>/cross-FHT-gff3.fai`, expected exit 1, observed 1
[^e155]: `bioheaders/pins.json` row `fhgm-base@none` — printed `ABSENT` by `bioheaders-pin-audit`

Digest of the grid: `4c833b4659ad45a400f9cf570851669c` (245 cells = 5 types x 7 operations x 7 serializations).
