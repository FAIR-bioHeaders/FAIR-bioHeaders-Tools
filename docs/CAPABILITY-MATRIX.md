# Capability matrix

What this toolkit does, per header type, per operation, per
serialization, at the contract versions it can name. Generated from the
code, the vendored registries and commands run during the render.

```text
generator  scripts/render_capability_matrix.py
check      python scripts/render_capability_matrix.py --check
           (.github/workflows/capability-matrix.yml runs it)
toolkit    fair-bioheaders 0.11.0 (this checkout; the
           number is the package version, and main runs ahead of the
           release that carries it - check the newest tag)
baseline   FAIR-bioHeaders-Specification v0.6.0: FHR '2.1', FHP '1.2', FHGFF3 '1.2'
authority  tag v0.6.0 is commit 0ae18b00ee4bd71ab2dc28bae706b0f9d195076b, and the checkout it was read from is at that commit: released bytes are named by a tag, never by a branch
suite      291 vectors at v0.6.0
types      3 with a released contract, 1 development only, 1 not referenced here
```

The environment is deliberately not in this file: the same commit must
render byte-identically on both interpreters `pytest.yaml` tests, and an
interpreter version is not part of a capability claim.

## How to read a cell

| mark | meaning |
| --- | --- |
| `yes` | the command does it, and the cited probe or test measured it |
| `no` | a rule in the package refuses it, or it was never implemented: |
|      | a refusal with a named reason is a decision, not a gap |
| `n/a` | the dimension does not apply to the pair, and the footnote |
|      | names who owns it |
| `draft lane` | reached only with `BIOHEADERS_EXPERIMENTAL_FHT` set, over |
|      | pinned development bytes; see the draft section |
| `partial` | it runs, but part of the operation's own contract is |
|      | unevidenced here, and the footnote says which part |
| `not here` | this artifact holds no reference to the type at all |
| `not verified` | neither earned nor refused; listed under Not verified |

Each mark can carry two kinds of footnote: an `r-…` one is a reason, an
`e`-numbered one is evidence, and both are written out in full at the
end of the file. The grids are per *operation*: `read` and `write` both
involve `convert`, `verify` is `bioheaders verify` and the
`fhr-*-validate` names, and so on. The command table is next.

## The grids

### FHR — contract `'2.1'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | `yes[^e1]` | `yes[^e2]` | `yes[^e3]` | `yes[^e4]` | `no[^r-family-gate][^e5]` | `yes[^e6]` | `yes[^e7]` |
| write | `yes[^r-document-carries-no-checksum][^e8]` | `yes[^r-document-carries-no-checksum][^e9]` | `yes[^e10]` | `yes[^e11]` | `no[^r-family-gate][^e5]` | `yes[^r-document-carries-no-checksum][^e12]` | `yes[^r-document-carries-no-checksum][^e13]` |
| verify | `n/a[^r-no-checksum-in-document][^e14]` | `n/a[^r-no-checksum-in-document][^e15]` | `yes[^e16]` | `yes[^e17]` | `no[^r-family-gate][^e5]` | `n/a[^r-no-checksum-in-document][^e18]` | `n/a[^r-no-checksum-in-document][^e19]` |
| strip | `n/a[^r-no-checksum-in-document][^e20]` | `n/a[^r-no-checksum-in-document][^e21]` | `yes[^e22]` | `yes[^e23]` | `no[^r-family-gate][^e5]` | `n/a[^r-no-checksum-in-document][^e24]` | `n/a[^r-no-checksum-in-document][^e25]` |
| links | `n/a[^r-no-checksum-in-document][^e26]` | `n/a[^r-no-checksum-in-document][^e27]` | `yes[^r-links-verdicts][^e28]` | `yes[^r-links-verdicts][^e29]` | `no[^r-family-gate][^e5]` | `n/a[^r-no-checksum-in-document][^e30]` | `n/a[^r-no-checksum-in-document][^e31]` |
| assess | `n/a[^r-assess-documents][^e32]` | `n/a[^r-assess-documents][^e32]` | `yes[^e33]` | `yes[^e34]` | `no[^r-family-gate][^e5]` | `n/a[^r-assess-documents][^e32]` | `n/a[^r-assess-documents][^e32]` |
| index | `no[^r-index-fasta-only][^e35]` | `no[^r-index-fasta-only][^e36]` | `yes[^e37]` | `no[^r-index-fasta-only][^e38]` | `no[^r-family-gate][^e5]` | `no[^r-index-fasta-only][^e39]` | `no[^r-index-fasta-only][^e40]` |

Vendored contract copies (`schemas/bundled.json`): v0.3.0 → `fhr-1.json`; v0.3.1 → `fhr-1.json`; v0.4.0 → `fhr-2.0.json`; v0.4.1 → `fhr-2.0.json`; v0.4.2 → `fhr-2.0.json`; v0.5.0 → `fhr-2.1.json`; v0.6.0 → `fhr-2.1.json`.

### FHP — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | `yes[^e41]` | `yes[^e42]` | `yes[^e43]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `yes[^e46]` | `yes[^e47]` |
| write | `yes[^r-document-carries-no-checksum][^e48]` | `yes[^r-document-carries-no-checksum][^e49]` | `yes[^e50]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `yes[^r-document-carries-no-checksum][^e51]` | `yes[^r-document-carries-no-checksum][^e52]` |
| verify | `n/a[^r-no-checksum-in-document][^e53]` | `n/a[^r-no-checksum-in-document][^e54]` | `yes[^e55]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `n/a[^r-no-checksum-in-document][^e56]` | `n/a[^r-no-checksum-in-document][^e57]` |
| strip | `n/a[^r-no-checksum-in-document][^e58]` | `n/a[^r-no-checksum-in-document][^e59]` | `yes[^e60]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `n/a[^r-no-checksum-in-document][^e61]` | `n/a[^r-no-checksum-in-document][^e62]` |
| links | `n/a[^r-no-checksum-in-document][^e63]` | `n/a[^r-no-checksum-in-document][^e64]` | `yes[^r-links-verdicts][^e65]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `n/a[^r-no-checksum-in-document][^e66]` | `n/a[^r-no-checksum-in-document][^e67]` |
| assess | `n/a[^r-assess-documents][^e68]` | `n/a[^r-assess-documents][^e68]` | `yes[^e69]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `n/a[^r-assess-documents][^e68]` | `n/a[^r-assess-documents][^e68]` |
| index | `no[^r-index-fasta-only][^e35]` | `no[^r-index-fasta-only][^e36]` | `partial[^r-index-samtools-fhr-only][^e70]` | `no[^r-family-gate][^e44]` | `no[^r-family-gate][^e45]` | `no[^r-index-fasta-only][^e39]` | `no[^r-index-fasta-only][^e40]` |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhp-1.0.json`; v0.4.1 → `fhp-1.0.json`; v0.4.2 → `fhp-1.0.json`; v0.5.0 → `fhp-1.1.json`; v0.6.0 → `fhp-1.2.json`.

### FHGFF3 — contract `'1.2'` at v0.6.0

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | `yes[^e71]` | `yes[^e72]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^e75]` | `no[^r-no-binding][^e76][^e77]` | `yes[^r-microdata-experimental][^e78]` |
| write | `yes[^r-document-carries-no-checksum][^e79]` | `yes[^r-document-carries-no-checksum][^e80]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^e81]` | `no[^r-no-binding][^e76][^e77]` | `yes[^r-microdata-experimental][^e82]` |
| verify | `n/a[^r-no-checksum-in-document][^e83]` | `n/a[^r-no-checksum-in-document][^e84]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^r-verify-directives][^e85]` | `no[^r-no-binding][^e76][^e77]` | `n/a[^r-no-checksum-in-document][^e86]` |
| strip | `n/a[^r-no-checksum-in-document][^e87]` | `n/a[^r-no-checksum-in-document][^e88]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^e89]` | `no[^r-no-binding][^e76][^e77]` | `n/a[^r-no-checksum-in-document][^e90]` |
| links | `n/a[^r-no-checksum-in-document][^e91]` | `n/a[^r-no-checksum-in-document][^e92]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^r-links-verdicts][^e93]` | `no[^r-no-binding][^e76][^e77]` | `n/a[^r-no-checksum-in-document][^e94]` |
| assess | `n/a[^r-assess-documents][^e95]` | `n/a[^r-assess-documents][^e95]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `yes[^e96]` | `no[^r-no-binding][^e76][^e77]` | `n/a[^r-assess-documents][^e95]` |
| index | `no[^r-index-fasta-only][^e35]` | `no[^r-index-fasta-only][^e36]` | `no[^r-family-gate][^e73]` | `no[^r-family-gate][^e74]` | `no[^r-index-fasta-only][^e97]` | `no[^r-no-binding][^e76][^e77]` | `no[^r-index-fasta-only][^e40]` |

Vendored contract copies (`schemas/bundled.json`): v0.4.0 → `fhgff3-1.0.json`; v0.4.1 → `fhgff3-1.0.json`; v0.4.2 → `fhgff3-1.0.json`; v0.5.0 → `fhgff3-1.1.json`; v0.6.0 → `fhgff3-1.2.json`.

### FHT — draft lane only, opt-in, no claim of any kind

`BIOHEADERS_EXPERIMENTAL_FHT` opens it; nothing else does. The lane reads `fht-draft.json`, pinned at commit `226f923c28b680edb3c546e99a751482d06aef1a` (sha256 `59ad9641adcb0e5591045c2d894c066d1adc9984cca84c5ff6502f8dad88487e` of those bytes), citation `https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json`. It has no entry in the version registry, no alias URL and no version of its own to name, and every read under the opt-in prints that provenance. Its suite is pinned apart from it: commit `7503b26423296ba09357de66995ca3c9508306af`, sha256 `ab72fc985a2629df5e8ea951936be3c3cf65a4f5a1c782f604ea6902a1d29c58`, 68 vectors.

So a `draft lane` mark below says: with the opt-in set, on a checkout of this branch, that path ran and printed its provenance. It never says anything about status, and neither does `no`: those cells are gates that were asked.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | `not verified[^r-draft-no-file-evidence]` | `draft lane[^r-draft-lane-document][^e98]` | `draft lane[^r-draft-lane][^e99][^e100]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-no-binding][^e102]` | `no[^r-draft-no-binding][^e102]` |
| write | `not verified[^r-draft-no-file-evidence]` | `draft lane[^r-draft-lane-document][^e98]` | `draft lane[^r-draft-lane][^e98][^e100]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-no-binding][^e102]` | `no[^r-draft-no-binding][^e102]` |
| verify | `n/a[^r-no-checksum-in-document][^e14]` | `n/a[^r-no-checksum-in-document][^e15]` | `draft lane[^r-draft-lane][^e103][^e100]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `n/a[^r-no-checksum-in-document][^e18]` | `n/a[^r-no-checksum-in-document][^e19]` |
| strip | `n/a[^r-no-checksum-in-document][^e20]` | `n/a[^r-no-checksum-in-document][^e21]` | `draft lane[^r-draft-lane][^e98][^e100]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `n/a[^r-no-checksum-in-document][^e24]` | `n/a[^r-no-checksum-in-document][^e25]` |
| links | `n/a[^r-no-checksum-in-document][^e26]` | `n/a[^r-no-checksum-in-document][^e27]` | `draft lane[^r-draft-lane][^e104][^e100]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `n/a[^r-no-checksum-in-document][^e30]` | `n/a[^r-no-checksum-in-document][^e31]` |
| assess | `n/a[^r-assess-documents][^e32]` | `n/a[^r-assess-documents][^e32]` | `no[^r-draft-assess][^e99]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `n/a[^r-assess-documents][^e32]` | `n/a[^r-assess-documents][^e32]` |
| index | `no[^r-index-fasta-only][^e35]` | `no[^r-index-fasta-only][^e36]` | `not verified[^r-index-no-evidence]` | `no[^r-draft-carrier][^e101]` | `no[^r-draft-carrier][^e101]` | `no[^r-index-fasta-only][^e39]` | `no[^r-index-fasta-only][^e40]` |

### FHGM — this artifact holds no reference to it

`bioheaders/pins.json` row `fhgm-base@none`, class `base-carrier`, label `draft, not acceptance`, is what says so; the audit prints it as `ABSENT`. The whole grid is one value because the whole of this repository is silent about the model draft, and that silence is a decision with a source, not an oversight. See the scope statements below the tables.

| operation \\ serialization | json | yaml | fasta | gfa | gff3 | jsonld | microdata |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| write | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| verify | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| strip | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| links | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| assess | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |
| index | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` | `not here[^r-fhgm-scope][^e105]` |

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

## The version dimension

Rules V1 to V6 of `docs/SCHEMA-VERSIONS.md` decide which copy a record
gets: the record's own `schema` citation selects it, and a release with
no vendored copy is refused rather than checked against a contract it
does not name. Every row below was selected by running `validate` on a
record citing that release while this file was rendered.

| type | release | contract version | copy here | provenance |
| --- | --- | --- | --- | --- |
| FHR | `v0.3.0` | `1` | `fhr-1.json` | `fhr-1@v0.3.0` FRESH at the tag |
| FHR | `v0.3.1` | `1` | `fhr-1.json` | `fhr-1@v0.3.1` FRESH at the tag |
| FHR | `v0.4.0` | `'2.0'` | `fhr-2.0.json` | `fhr-2.0@v0.4.0` FRESH at the tag |
| FHR | `v0.4.1` | `'2.0'` | `fhr-2.0.json` | `fhr-2.0@v0.4.1` FRESH at the tag |
| FHR | `v0.4.2` | `'2.0'` | `fhr-2.0.json` | `fhr-2.0@v0.4.2` FRESH at the tag |
| FHR | `v0.5.0` | `'2.1'` | `fhr-2.1.json` | `fhr-2.1@v0.5.0` FRESH at the tag |
| FHR | `v0.6.0` | `'2.1'` | `fhr-2.1.json` | `fhr-2.1@v0.6.0` FRESH at the tag |
| FHP | `v0.4.0` | `'1.0'` | `fhp-1.0.json` | `fhp-1.0@v0.4.0` FRESH at the tag |
| FHP | `v0.4.1` | `'1.0'` | `fhp-1.0.json` | `fhp-1.0@v0.4.1` FRESH at the tag |
| FHP | `v0.4.2` | `'1.0'` | `fhp-1.0.json` | `fhp-1.0@v0.4.2` FRESH at the tag |
| FHP | `v0.5.0` | `'1.1'` | `fhp-1.1.json` | `fhp-1.1@v0.5.0` FRESH at the tag |
| FHP | `v0.6.0` | `'1.2'` | `fhp-1.2.json` | `fhp-1.2@v0.6.0` FRESH at the tag |
| FHGFF3 | `v0.4.0` | `'1.0'` | `fhgff3-1.0.json` | `fhgff3-1.0@v0.4.0` FRESH at the tag |
| FHGFF3 | `v0.4.1` | `'1.0'` | `fhgff3-1.0.json` | `fhgff3-1.0@v0.4.1` FRESH at the tag |
| FHGFF3 | `v0.4.2` | `'1.0'` | `fhgff3-1.0.json` | `fhgff3-1.0@v0.4.2` FRESH at the tag |
| FHGFF3 | `v0.5.0` | `'1.1'` | `fhgff3-1.1.json` | `fhgff3-1.1@v0.5.0` FRESH at the tag |
| FHGFF3 | `v0.6.0` | `'1.2'` | `fhgff3-1.2.json` | `fhgff3-1.2@v0.6.0` FRESH at the tag |

The FHR rows at `v0.3.0` and `v0.3.1` carry the contract version as a
number, which is the shape rule V6 exists for: a raw-main citation with
`schemaVersion` the number 1 is read as FHR 1, with a deprecation
warning, and
`tests/fhr1_compat_test.py::test_combine_verify_and_strip_keep_fhr_1`
carries that record through `combine`, `verify` and `strip` rather than
only checking the selection. The probe `version-FHR-v0.3.1` selected the
same copy through a `w3id` citation.
`current` is `v0.6.0`, and the registry was
read from the specification at that tag - the same place the contract
digests below came from. Released material is named by a tag, never by
a branch (#241 rule 1): `schemas/versions.json` on `main` is a different
document and is not cited here.

Contract digests at the tag, as this render measured them:

- `fhgff3.json` at `v0.6.0`: sha256 `1942be4cefc8b3a2537942c2252b45fbcef87a5532486e4fd0f5d4c540e0fbf9`
- `fhp.json` at `v0.6.0`: sha256 `92a0b3cbcfe69939ebfaac69f0c5958ce426c005873efe8d3e3eb0fc0dab6de5`
- `fhr.json` at `v0.6.0`: sha256 `694ab5afaf8c3743eacf9e2aacb5551f7cbe37073b6f4afc3ae4a65b47f9d4df`

Those files sit at the repository **root**. `schemas/fhp.json` does not
exist at that tag, and this render checks that it does not: a matrix
that quietly switched to a `schemas/` path would be quoting bytes no
URL resolves to. `schemas/` holds `core.yaml`, `shared.yaml` and
`versions.json` there.

Controls, so the table cannot be vacuous:

- `FHR` asking for `'2.1'` through the `v0.4.0` citation is refused by the contract that release actually holds: probe `version-control-FHR`
- `FHR` citing `v9.9.9` is refused as a version this tool has no copy for (rule V4): probe `version-absent-FHR`
- `FHP` asking for `'1.2'` through the `v0.4.0` citation is refused by the contract that release actually holds: probe `version-control-FHP`
- `FHP` citing `v9.9.9` is refused as a version this tool has no copy for (rule V4): probe `version-absent-FHP`
- `FHGFF3` asking for `'1.2'` through the `v0.4.0` citation is refused by the contract that release actually holds: probe `version-control-FHGFF3`
- `FHGFF3` citing `v9.9.9` is refused as a version this tool has no copy for (rule V4): probe `version-absent-FHGFF3`

## The shared suite, and what this artifact runs of it

Acceptance for a released type is the 291 vectors of the
specification's shared suite at tag `v0.6.0` (sha256
`cdbb79b1fbfda52b…`). Whether a vector can run at all is a
property of the consumer, not of the suite, so the two ledgers that get
read as one are kept apart below: vectors executed **by id** by this
repository's own `pytest` run, and vectors executed **against the
installed commands** by the specification's own checker.

| format | vectors at the tag | valid / invalid | gzip / BGZF | by id here | the test that runs them by id |
| --- | --- | --- | --- | --- | --- |
| `fasta` | 98 | 35 / 63 | 3 / 1 | — | none vendored: this repository holds no filtered manifest of this format |
| `fhgff3` | 38 | 18 / 20 | 1 / 1 | 38 | tests/fhgff3_test.py::test_conformance_vector |
| `fhp-fasta` | 36 | 14 / 22 | 1 / 1 | 36 | tests/fhp_test.py::test_conformance_vector |
| `gfa` | 56 | 20 / 36 | 2 / 1 | — | none vendored: this repository holds no filtered manifest of this format |
| `jsonld` | 37 | 17 / 20 | 0 / 0 | 37 | tests/jsonld_test.py::test_conformance_vectors |
| `microdata` | 26 | 15 / 11 | 0 / 0 | — | none vendored: this repository holds no filtered manifest of this format |
| **total** | **291** | | | **111** | |

That is the measured shape: 111 of 291 vectors run
by id here, and the whole suite passes against the installed commands
(measurement below). Both numbers are narrower than they look, and
three things follow, none of which a grid can show by itself:

- A vector scores reading, validating and the checksum of a valid file.
  It never exercises `strip` byte equality, `links`, `assess` or
  `index`, which is why those rows cite probes written for them.
- `98` `fasta` and 56 `gfa` vectors and 26 `microdata` vectors are not vendored by id here at all. The first two are the genome-header paths this toolkit has carried longest and tests directly (`tests/fhr_test.py`, `tests/streaming_test.py`, `tests/compression_test.py`); `microdata` is measured by `tests/fhgff3_microdata_test.py`, `tests/microdata_shared_test.py` and the FHP microdata tests. The equality of the three vendored manifests with the tag is itself a test: `tests/fhgff3_test.py::test_fixtures_match_the_specification`, `tests/fhp_test.py::test_fixtures_match_the_specification`, `tests/jsonld_test.py::test_vectors_match_the_specification`.
- 228 and 63 are the federation's other numbers, and they belong to the
  four per-language libraries, not to this artifact. Those libraries
  implement no JSON-LD and no microdata reader, so they declare 37 `jsonld` plus 26 `microdata` vectors - 228 executed, 63 not-run out of the same 291. This toolkit has both
  readers, so 63 is a statement about *their* scope. Reading 228 there
  against 291 here as a regression would be exactly the mistake this
  section exists to prevent; per-format executability is a property of
  the consumer.

### Measurements rendering cannot re-run

- **shared suite against the installed commands** — `python3 scripts/check_conformance.py --converter <this checkout's bin> --require-format fasta --require-format gfa --require-format fhp-fasta --require-format fhgff3 --require-format jsonld --require-format microdata`, run from a checkout of the specification at tag `v0.6.0` against commands installed from this branch: `291 vectors passed`, exit status 0, measured 2026-11-16. `--require-format` is what makes the number mean something: without it a format the converter lacks is skipped and reported rather than failing.
- **the draft lane's own suite** — `BIOHEADERS_EXPERIMENTAL_FHT=1 FHT_SPECIFICATION=<checkout at 7503b26> python -m pytest tests/fht_conformance_test.py -q`: `75 passed, 62 skipped` of 137 collected, exit status 0, measured 2026-11-16. The 62 skips are the parent-link test for the 62 vectors that record no parent file; 6 vectors record one, and all 68 validity cases ran. Without the opt-in the same file skips whole, and the default test run never reads those bytes. `test_suite_manifest_matches_pin` is what licenses the number: it fails unless the manifest scored is the one `bundled.json` names.
- **the pin audit** — `bioheaders-pin-audit` on 2026-11-16 printed `summary: 26 FRESH, 0 DRIFT, 5 ABSENT of 31`, exit status 0, advisory. Two of the five ABSENT rows are the filtered per-format copies of the shared manifest vendored under `tests/fixtures/`, one is `fhgm-base@none`, one is the `fhp.context.jsonld` copy with no recorded revision, one is this repository's own unrecorded `examples/` tree. The rows themselves are data, read from `bioheaders/pins.json`; only the verdict counts came from a run against upstream bytes.
- **the model draft this artifact does not hold** — `FHGM-Specification` `origin/main` (`c503ecf`) measured the same day: `development/conformance/manifest.json`, 51,114 bytes, sha256 `0d2790151c4a2955…`, 43 vectors of format `fhgff3`. The per-language libraries vendor and score it (the R library pins commit `d443073` of it in `inst/VENDORED.json`; the Julia library carries `src/fhgm.jl` and `drafts/fhgm-*-draft.json`). This toolkit runs none of those 43, and says why rather than leaving a blank.

## Compression and streaming

Input compression is detected from the gzip magic bytes, not from the
extension, over single-member gzip, multi-member gzip and BGZF. Output to
a path ending `.gz` or `.bgz` is BGZF, which `gunzip` reads. A checksum
always covers the decompressed bytes, which is why the same header and
body produce one checksum plain or compressed.

| type | carrier | read compressed | written | evidence |
| --- | --- | --- | --- | --- |
| FHR | `fasta` | single-member gzip, multi-member gzip and BGZF | BGZF on a `fasta.gz` path | `gzip-read-FHR-fasta`, `gzip-strip-FHR-fasta`, `gzip-write-FHR-fasta`; the suite holds 3 gzip and 1 BGZF vectors of format `fasta`, not vendored by id here: see the suite ledger |
| FHR | `gfa` | single-member gzip, multi-member gzip and BGZF | BGZF on a `gfa.gz` path | `gzip-read-FHR-gfa`, `gzip-strip-FHR-gfa`, `gzip-write-FHR-gfa`; the suite holds 2 gzip and 1 BGZF vectors of format `gfa`, not vendored by id here: see the suite ledger |
| FHP | `fasta` | single-member gzip, multi-member gzip and BGZF | BGZF on a `fasta.gz` path | `gzip-read-FHP-fasta`, `gzip-strip-FHP-fasta`, `gzip-write-FHP-fasta`; the suite holds 1 gzip and 1 BGZF vectors of format `fhp-fasta`, 36 of them run by id here |
| FHGFF3 | `gff3` | single-member gzip, multi-member gzip and BGZF | BGZF on a `gff3.gz` path | `gzip-read-FHGFF3-gff3`, `gzip-strip-FHGFF3-gff3`, `gzip-write-FHGFF3-gff3`; the suite holds 1 gzip and 1 BGZF vectors of format `fhgff3`, 38 of them run by id here |
| FHR | `jsonld` | a gzip member reads (probe `gzip-read-FHR-jsonld`) | `convert` to `.gz` writes BGZF | the shared suite has no compressed vector of this format, so this row is a probe and nothing more |
| FHR | `microdata` | a gzip member reads (probe `gzip-read-FHR-microdata`) | `convert` to `.gz` writes BGZF | the shared suite has no compressed vector of this format, so this row is a probe and nothing more |
| any | stdin / stdout | yes: magic bytes on a pipe | yes | `tests/compression_test.py::test_stdin_and_stdout`, `tests/streaming_test.py` |
| FHR | BGZF `.gzi` | — | yes | `tests/faidx_test.py` (needs samtools and bgzip installed, so it is opt-in and skips without them) |

## The draft lane is opt-in and is never a claim

`BIOHEADERS_EXPERIMENTAL_FHT` is read by `bioheaders/selection.py`. Unset - the
default, and what every installed command does today - a record citing
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

## Scope statements

- **FHGM: no reference here, on purpose.** `fhgm-base@none`, class `base-carrier`, label `draft, not acceptance`, is printed as `ABSENT` by the audit, and `bioheaders/pins.json` records why: the toolkit holds no FHGM reference at all: it vendors no FHGM draft and pins no FHGFF3 base/carrier schema for one, so there is nothing here to compare with v0.5.0 or v0.6.0. Opening an FHGM lane is FAIR-bioHeaders-Tools#135; the base pin #241(b) is about lives in FHGM-Specification. The class is implemented and tested here (tests/pin_audit_test.py) so that lane has a gate to plug into, and this row keeps the missing axis visible instead of silently absent.
- **fhp-fixtures@v0.6.0-filtered` and `fhgff3-fixtures@v0.6.0-filtered are `ABSENT` by construction.** This repository vendors a *filtered* per-format copy of the shared manifest, so no single upstream file digest describes it; equality with the tag is enforced fixture by fixture by the parity tests named in the suite ledger above. Reporting them as absent is the audit refusing to call a different byte string fresh.
- **`assess` is not a metadata-document reader.** It reports
  `unknown-text` for a bare JSON or YAML document and publishes no
  conformance section, so those cells say `n/a` instead of banking an
  exit status 0.
- **The annotation header's microdata binding is still open
  upstream.** `bioheaders/fhgff3_microdata.py` sets `EXPERIMENTAL
  = True` and warns on every read and write, pending FHGFF3#16.
  The `yes` in those cells means implemented and measured here; it
  is not a published serialization, which is a different claim from
  the draft-contract ones above and is kept separate.
- **JSON-LD for the protein header is canonical only.** The export
  profile is refused by name (probe `refuse-FHP-export`), and the CLI
  marks both facts provisional in its own help text.

## Not verified

- `index` for FHT, and `assess` for a draft-carrying FASTA beyond its `not_assessed` verdict — no probe or test measures either; the gate is asked in-process, but nothing runs a draft header through `faidx`
- `index` offsets for the protein header against samtools — `tests/faidx_test.py` compares `.fai` bytes with samtools and pysam for FHR FASTA only. The FHP cell is earned by an independent recomputation of every field during this render, which is weaker than the samtools comparison and is labelled as such
- gzip and BGZF for JSON-LD and microdata as a documented contract — the shared suite holds no compressed vector of either format, and `open_input` detects compression by magic bytes on any input. The probes show a gzip member of each is readable; nobody has specified what compressed metadata documents mean for the checksum, because they carry no body
- `assess --online` identifier resolution — opt-in and makes network calls; deliberately not exercised here
- the Galaxy wrappers and the container images — `galaxy/tools/fair_bioheaders` is linted by `galaxy-tools.yml` with `planemo`, which this render does not run, and `Dockerfile` and `container.yml` build from a *released* wheel. Nothing in this file says a word about either
- the Python 3.9 lane, and the 3.13 lane separately — this render ran on one interpreter. `pytest.yaml` tests both, and the JSON-LD vectors import `pyld`, which needs 3.10 or later, so on 3.9 those 37 tests skip and the by-id ledger below is smaller by exactly that much
- the opt-in large-file memory test — `FHR_MEMORY_TEST=1 pytest -k memory` was not run: it writes about 1 GB

## Probes run for this render

| probe | command | expected | observed |
| --- | --- | --- | --- |
| `assess-FHGFF3-gff3` | `bioheaders assess examples/fhgff3/annotation.fhgff3.gff3 --format json --output <tmp>/assess-FHGFF3-gff3` | 0 | 0 |
| `assess-FHP-fasta` | `bioheaders assess examples/fhp/example.fhp.fasta --format json --output <tmp>/assess-FHP-fasta` | 0 | 0 |
| `assess-FHR-fasta` | `bioheaders assess examples/example.fhr.fasta --format json --output <tmp>/assess-FHR-fasta` | 0 | 0 |
| `assess-FHR-gfa` | `bioheaders assess examples/example.fhr.gfa --format json --output <tmp>/assess-FHR-gfa` | 0 | 0 |
| `assess-doc-FHGFF3` | `bioheaders assess examples/fhgff3/minimal-reference.fhgff3.json --format json --output <tmp>/assessdoc-FHGFF3` | 0 | 0 |
| `assess-doc-FHP` | `bioheaders assess examples/fhp/minimal-predicted.fhp.json --format json --output <tmp>/assessdoc-FHP` | 0 | 0 |
| `assess-doc-FHR` | `bioheaders assess examples/example.fhr.json --format json --output <tmp>/assessdoc-FHR` | 0 | 0 |
| `gzip-read-FHGFF3-gff3` | `bioheaders verify <tmp>/gzip-FHGFF3-gff3.gff3.gz` | 0 | 0 |
| `gzip-read-FHP-fasta` | `bioheaders verify <tmp>/gzip-FHP-fasta.fasta.gz` | 0 | 0 |
| `gzip-read-FHR-fasta` | `bioheaders verify <tmp>/gzip-FHR-fasta.fasta.gz` | 0 | 0 |
| `gzip-read-FHR-gfa` | `bioheaders verify <tmp>/gzip-FHR-gfa.gfa.gz` | 0 | 0 |
| `gzip-read-FHR-jsonld` | `bioheaders validate <tmp>/docgz-FHR.jsonld.gz` | 0 | 0 |
| `gzip-read-FHR-microdata` | `bioheaders validate <tmp>/docgz-FHR.html.gz` | 0 | 0 |
| `gzip-strip-FHGFF3-gff3` | `bioheaders strip <tmp>/gzip-FHGFF3-gff3.gff3.gz <tmp>/plain-FHGFF3-gff3` | 0 | 0 |
| `gzip-strip-FHP-fasta` | `bioheaders strip <tmp>/gzip-FHP-fasta.fasta.gz <tmp>/plain-FHP-fasta` | 0 | 0 |
| `gzip-strip-FHR-fasta` | `bioheaders strip <tmp>/gzip-FHR-fasta.fasta.gz <tmp>/plain-FHR-fasta` | 0 | 0 |
| `gzip-strip-FHR-gfa` | `bioheaders strip <tmp>/gzip-FHR-gfa.gfa.gz <tmp>/plain-FHR-gfa` | 0 | 0 |
| `gzip-write-FHGFF3-gff3` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/written-FHGFF3-gff3.gff3.gz` | 0 | 0 |
| `gzip-write-FHP-fasta` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/written-FHP-fasta.fasta.gz` | 0 | 0 |
| `gzip-write-FHR-fasta` | `bioheaders convert examples/example.fhr.json <tmp>/written-FHR-fasta.fasta.gz` | 0 | 0 |
| `gzip-write-FHR-gfa` | `bioheaders convert examples/example.fhr.json <tmp>/written-FHR-gfa.gfa.gz` | 0 | 0 |
| `index-FHP` | `bioheaders faidx examples/fhp/example.fhp.fasta -o <tmp>/index-FHP.fai` | 0 | 0 |
| `index-FHR` | `bioheaders faidx examples/example.fhr.fasta -o <tmp>/index-FHR.fai` | 0 | 0 |
| `index-reject-gfa` | `bioheaders faidx examples/example.fhr.gfa -o <tmp>/index-reject-gfa.fai` | 1 | 1 |
| `index-reject-gff3` | `bioheaders faidx examples/fhgff3/annotation.fhgff3.gff3 -o <tmp>/index-reject-gff3.fai` | 1 | 1 |
| `index-reject-json` | `bioheaders faidx examples/example.fhr.json -o <tmp>/index-reject-json.fai` | 1 | 1 |
| `index-reject-jsonld` | `bioheaders faidx examples/example.fhr.jsonld -o <tmp>/index-reject-jsonld.fai` | 1 | 1 |
| `index-reject-microdata` | `bioheaders faidx examples/example.microdata.fhr.html -o <tmp>/index-reject-microdata.fai` | 1 | 1 |
| `index-reject-yaml` | `bioheaders faidx examples/example.fhr.yaml -o <tmp>/index-reject-yaml.fai` | 1 | 1 |
| `links-FHGFF3-gff3` | `bioheaders verify-links examples/fhgff3/annotation.fhgff3.gff3` | 0 | 0 |
| `links-FHP-fasta` | `bioheaders verify-links examples/fhp/example.fhp.fasta` | 0 | 0 |
| `links-FHR-fasta` | `bioheaders verify-links examples/example.fhr.fasta` | 0 | 0 |
| `links-FHR-gfa` | `bioheaders verify-links examples/example.fhr.gfa` | 0 | 0 |
| `links-doc-FHGFF3-json` | `bioheaders verify-links examples/fhgff3/minimal-reference.fhgff3.json` | 1 | 1 |
| `links-doc-FHGFF3-microdata` | `bioheaders verify-links examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 | 1 |
| `links-doc-FHGFF3-yaml` | `bioheaders verify-links examples/fhgff3/rich.fhgff3.yaml` | 1 | 1 |
| `links-doc-FHP-json` | `bioheaders verify-links examples/fhp/minimal-predicted.fhp.json` | 1 | 1 |
| `links-doc-FHP-jsonld` | `bioheaders verify-links examples/fhp/minimal-predicted.fhp.jsonld` | 1 | 1 |
| `links-doc-FHP-microdata` | `bioheaders verify-links examples/fhp/rich-microdata.microdata.fhp.html` | 1 | 1 |
| `links-doc-FHP-yaml` | `bioheaders verify-links examples/fhp/rich-mixed.fhp.yaml` | 1 | 1 |
| `links-doc-FHR-json` | `bioheaders verify-links examples/example.fhr.json` | 1 | 1 |
| `links-doc-FHR-jsonld` | `bioheaders verify-links examples/example.fhr.jsonld` | 1 | 1 |
| `links-doc-FHR-microdata` | `bioheaders verify-links examples/example.microdata.fhr.html` | 1 | 1 |
| `links-doc-FHR-yaml` | `bioheaders verify-links examples/example.fhr.yaml` | 1 | 1 |
| `read-FHGFF3-gff3` | `bioheaders validate examples/fhgff3/annotation.fhgff3.gff3` | 0 | 0 |
| `read-FHGFF3-json` | `bioheaders validate examples/fhgff3/minimal-reference.fhgff3.json` | 0 | 0 |
| `read-FHGFF3-microdata` | `bioheaders validate examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 0 | 0 |
| `read-FHGFF3-yaml` | `bioheaders validate examples/fhgff3/rich.fhgff3.yaml` | 0 | 0 |
| `read-FHP-fasta` | `bioheaders validate examples/fhp/example.fhp.fasta` | 0 | 0 |
| `read-FHP-json` | `bioheaders validate examples/fhp/minimal-predicted.fhp.json` | 0 | 0 |
| `read-FHP-jsonld` | `bioheaders validate examples/fhp/minimal-predicted.fhp.jsonld` | 0 | 0 |
| `read-FHP-microdata` | `bioheaders validate examples/fhp/rich-microdata.microdata.fhp.html` | 0 | 0 |
| `read-FHP-yaml` | `bioheaders validate examples/fhp/rich-mixed.fhp.yaml` | 0 | 0 |
| `read-FHR-fasta` | `bioheaders validate examples/example.fhr.fasta` | 0 | 0 |
| `read-FHR-gfa` | `bioheaders validate examples/example.fhr.gfa` | 0 | 0 |
| `read-FHR-json` | `bioheaders validate examples/example.fhr.json` | 0 | 0 |
| `read-FHR-jsonld` | `bioheaders validate examples/example.fhr.jsonld` | 0 | 0 |
| `read-FHR-microdata` | `bioheaders validate examples/example.microdata.fhr.html` | 0 | 0 |
| `read-FHR-yaml` | `bioheaders validate examples/example.fhr.yaml` | 0 | 0 |
| `refuse-FHGFF3-fasta` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-fasta.fasta` | 1 | 1 |
| `refuse-FHGFF3-gfa` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-gfa.gfa` | 1 | 1 |
| `refuse-FHGFF3-jsonld` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/refuse-FHGFF3-jsonld.jsonld` | 1 | 1 |
| `refuse-FHP-export` | `bioheaders convert --jsonld-profile export examples/fhp/minimal-predicted.fhp.json <tmp>/export.fhp.jsonld` | 1 | 1 |
| `refuse-FHP-gfa` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gfa.gfa` | 1 | 1 |
| `refuse-FHP-gff3` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/refuse-FHP-gff3.gff3` | 1 | 1 |
| `refuse-FHR-gff3` | `bioheaders convert examples/example.fhr.json <tmp>/refuse-FHR-gff3.gff3` | 1 | 1 |
| `roundtrip-FHGFF3-gff3` | `bioheaders verify <tmp>/write-FHGFF3-gff3.gff3` | 0 | 0 |
| `roundtrip-FHP-fasta` | `bioheaders verify <tmp>/write-FHP-fasta.fasta` | 0 | 0 |
| `roundtrip-FHR-fasta` | `bioheaders verify <tmp>/write-FHR-fasta.fasta` | 0 | 0 |
| `roundtrip-FHR-gfa` | `bioheaders verify <tmp>/write-FHR-gfa.gfa` | 0 | 0 |
| `strip-FHGFF3-gff3` | `bioheaders strip examples/fhgff3/annotation.fhgff3.gff3 <tmp>/strip-FHGFF3-gff3.gff3` | 0 | 0 |
| `strip-FHP-fasta` | `bioheaders strip examples/fhp/example.fhp.fasta <tmp>/strip-FHP-fasta.fasta` | 0 | 0 |
| `strip-FHR-fasta` | `bioheaders strip examples/example.fhr.fasta <tmp>/strip-FHR-fasta.fasta` | 0 | 0 |
| `strip-FHR-gfa` | `bioheaders strip examples/example.fhr.gfa <tmp>/strip-FHR-gfa.gfa` | 0 | 0 |
| `strip-doc-FHGFF3-json` | `bioheaders strip examples/fhgff3/minimal-reference.fhgff3.json` | 1 | 1 |
| `strip-doc-FHGFF3-microdata` | `bioheaders strip examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 | 1 |
| `strip-doc-FHGFF3-yaml` | `bioheaders strip examples/fhgff3/rich.fhgff3.yaml` | 1 | 1 |
| `strip-doc-FHP-json` | `bioheaders strip examples/fhp/minimal-predicted.fhp.json` | 1 | 1 |
| `strip-doc-FHP-jsonld` | `bioheaders strip examples/fhp/minimal-predicted.fhp.jsonld` | 1 | 1 |
| `strip-doc-FHP-microdata` | `bioheaders strip examples/fhp/rich-microdata.microdata.fhp.html` | 1 | 1 |
| `strip-doc-FHP-yaml` | `bioheaders strip examples/fhp/rich-mixed.fhp.yaml` | 1 | 1 |
| `strip-doc-FHR-json` | `bioheaders strip examples/example.fhr.json` | 1 | 1 |
| `strip-doc-FHR-jsonld` | `bioheaders strip examples/example.fhr.jsonld` | 1 | 1 |
| `strip-doc-FHR-microdata` | `bioheaders strip examples/example.microdata.fhr.html` | 1 | 1 |
| `strip-doc-FHR-yaml` | `bioheaders strip examples/example.fhr.yaml` | 1 | 1 |
| `verify-FHGFF3-gff3` | `bioheaders verify examples/fhgff3/annotation.fhgff3.gff3` | 0 | 0 |
| `verify-FHP-fasta` | `bioheaders verify examples/fhp/example.fhp.fasta` | 0 | 0 |
| `verify-FHR-fasta` | `bioheaders verify examples/example.fhr.fasta` | 0 | 0 |
| `verify-FHR-gfa` | `bioheaders verify examples/example.fhr.gfa` | 0 | 0 |
| `verify-doc-FHGFF3-json` | `bioheaders verify examples/fhgff3/minimal-reference.fhgff3.json` | 1 | 1 |
| `verify-doc-FHGFF3-microdata` | `bioheaders verify examples/fhgff3/rich-microdata.microdata.fhgff3.html` | 1 | 1 |
| `verify-doc-FHGFF3-yaml` | `bioheaders verify examples/fhgff3/rich.fhgff3.yaml` | 1 | 1 |
| `verify-doc-FHP-json` | `bioheaders verify examples/fhp/minimal-predicted.fhp.json` | 1 | 1 |
| `verify-doc-FHP-jsonld` | `bioheaders verify examples/fhp/minimal-predicted.fhp.jsonld` | 1 | 1 |
| `verify-doc-FHP-microdata` | `bioheaders verify examples/fhp/rich-microdata.microdata.fhp.html` | 1 | 1 |
| `verify-doc-FHP-yaml` | `bioheaders verify examples/fhp/rich-mixed.fhp.yaml` | 1 | 1 |
| `verify-doc-FHR-json` | `bioheaders verify examples/example.fhr.json` | 1 | 1 |
| `verify-doc-FHR-jsonld` | `bioheaders verify examples/example.fhr.jsonld` | 1 | 1 |
| `verify-doc-FHR-microdata` | `bioheaders verify examples/example.microdata.fhr.html` | 1 | 1 |
| `verify-doc-FHR-yaml` | `bioheaders verify examples/example.fhr.yaml` | 1 | 1 |
| `version-FHGFF3-v0.4.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.0.json` | 0 | 0 |
| `version-FHGFF3-v0.4.1` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.1.json` | 0 | 0 |
| `version-FHGFF3-v0.4.2` | `bioheaders validate <tmp>/version-FHGFF3-v0.4.2.json` | 0 | 0 |
| `version-FHGFF3-v0.5.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.5.0.json` | 0 | 0 |
| `version-FHGFF3-v0.6.0` | `bioheaders validate <tmp>/version-FHGFF3-v0.6.0.json` | 0 | 0 |
| `version-FHP-v0.4.0` | `bioheaders validate <tmp>/version-FHP-v0.4.0.json` | 0 | 0 |
| `version-FHP-v0.4.1` | `bioheaders validate <tmp>/version-FHP-v0.4.1.json` | 0 | 0 |
| `version-FHP-v0.4.2` | `bioheaders validate <tmp>/version-FHP-v0.4.2.json` | 0 | 0 |
| `version-FHP-v0.5.0` | `bioheaders validate <tmp>/version-FHP-v0.5.0.json` | 0 | 0 |
| `version-FHP-v0.6.0` | `bioheaders validate <tmp>/version-FHP-v0.6.0.json` | 0 | 0 |
| `version-FHR-v0.3.0` | `bioheaders validate <tmp>/version-FHR-v0.3.0.json` | 0 | 0 |
| `version-FHR-v0.3.1` | `bioheaders validate <tmp>/version-FHR-v0.3.1.json` | 0 | 0 |
| `version-FHR-v0.4.0` | `bioheaders validate <tmp>/version-FHR-v0.4.0.json` | 0 | 0 |
| `version-FHR-v0.4.1` | `bioheaders validate <tmp>/version-FHR-v0.4.1.json` | 0 | 0 |
| `version-FHR-v0.4.2` | `bioheaders validate <tmp>/version-FHR-v0.4.2.json` | 0 | 0 |
| `version-FHR-v0.5.0` | `bioheaders validate <tmp>/version-FHR-v0.5.0.json` | 0 | 0 |
| `version-FHR-v0.6.0` | `bioheaders validate <tmp>/version-FHR-v0.6.0.json` | 0 | 0 |
| `version-absent-FHGFF3` | `bioheaders validate <tmp>/version-absent-FHGFF3.json` | 1 | 1 |
| `version-absent-FHP` | `bioheaders validate <tmp>/version-absent-FHP.json` | 1 | 1 |
| `version-absent-FHR` | `bioheaders validate <tmp>/version-absent-FHR.json` | 1 | 1 |
| `version-control-FHGFF3` | `bioheaders validate <tmp>/version-control-FHGFF3.json` | 1 | 1 |
| `version-control-FHP` | `bioheaders validate <tmp>/version-control-FHP.json` | 1 | 1 |
| `version-control-FHR` | `bioheaders validate <tmp>/version-control-FHR.json` | 1 | 1 |
| `write-FHGFF3-gff3` | `bioheaders combine examples/fhgff3/minimal-reference.fhgff3.json <tmp>/strip-FHGFF3-gff3.gff3 -o <tmp>/write-FHGFF3-gff3.gff3` | 0 | 0 |
| `write-FHGFF3-json` | `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.json` | 0 | 0 |
| `write-FHGFF3-microdata` | `bioheaders convert examples/fhgff3/minimal-reference.fhgff3.json <tmp>/write-FHGFF3-microdata.html` | 0 | 0 |
| `write-FHGFF3-yaml` | `bioheaders convert examples/fhgff3/annotation.fhgff3.gff3 <tmp>/meta-FHGFF3.yaml` | 0 | 0 |
| `write-FHP-fasta` | `bioheaders combine examples/fhp/minimal-predicted.fhp.json <tmp>/strip-FHP-fasta.fasta -o <tmp>/write-FHP-fasta.fasta` | 0 | 0 |
| `write-FHP-json` | `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.json` | 0 | 0 |
| `write-FHP-jsonld` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-jsonld.jsonld` | 0 | 0 |
| `write-FHP-microdata` | `bioheaders convert examples/fhp/minimal-predicted.fhp.json <tmp>/write-FHP-microdata.html` | 0 | 0 |
| `write-FHP-yaml` | `bioheaders convert examples/fhp/example.fhp.fasta <tmp>/meta-FHP.yaml` | 0 | 0 |
| `write-FHR-fasta` | `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-fasta.fasta -o <tmp>/write-FHR-fasta.fasta` | 0 | 0 |
| `write-FHR-gfa` | `bioheaders combine examples/example.fhr.json <tmp>/strip-FHR-gfa.gfa -o <tmp>/write-FHR-gfa.gfa` | 0 | 0 |
| `write-FHR-json` | `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.json` | 0 | 0 |
| `write-FHR-jsonld` | `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-jsonld.jsonld` | 0 | 0 |
| `write-FHR-microdata` | `bioheaders convert examples/example.fhr.json <tmp>/write-FHR-microdata.html` | 0 | 0 |
| `write-FHR-yaml` | `bioheaders convert examples/example.fhr.fasta <tmp>/meta-FHR.yaml` | 0 | 0 |

138 probes. Any one of them disagreeing with
the expectation recorded in the generator aborts the render before it
writes a byte, which is the same rule `--check` runs under.

## Evidence index

| evidence | warranted |
| --- | --- |
| probe `read-FHR-json` | FHR/read/json |
| probe `read-FHR-yaml` | FHR/read/yaml |
| probe `read-FHR-fasta` | FHR/read/fasta |
| probe `read-FHR-gfa` | FHR/read/gfa |
| probe `refuse-FHR-gff3` | FHR/assess/gff3, FHR/index/gff3, FHR/links/gff3 (+4 more) |
| probe `read-FHR-jsonld` | FHR/read/jsonld |
| probe `read-FHR-microdata` | FHR/read/microdata |
| probe `write-FHR-json` | FHR/write/json |
| probe `write-FHR-yaml` | FHR/write/yaml |
| probe `write-FHR-fasta` | FHR/write/fasta |
| probe `write-FHR-gfa` | FHR/write/gfa |
| probe `write-FHR-jsonld` | FHR/write/jsonld |
| probe `write-FHR-microdata` | FHR/write/microdata |
| probe `verify-doc-FHR-json` | FHR/verify/json, FHT/verify/json |
| probe `verify-doc-FHR-yaml` | FHR/verify/yaml, FHT/verify/yaml |
| probe `verify-FHR-fasta` | FHR/verify/fasta |
| probe `verify-FHR-gfa` | FHR/verify/gfa |
| probe `verify-doc-FHR-jsonld` | FHR/verify/jsonld, FHT/verify/jsonld |
| probe `verify-doc-FHR-microdata` | FHR/verify/microdata, FHT/verify/microdata |
| probe `strip-doc-FHR-json` | FHR/strip/json, FHT/strip/json |
| probe `strip-doc-FHR-yaml` | FHR/strip/yaml, FHT/strip/yaml |
| probe `strip-FHR-fasta` | FHR/strip/fasta |
| probe `strip-FHR-gfa` | FHR/strip/gfa |
| probe `strip-doc-FHR-jsonld` | FHR/strip/jsonld, FHT/strip/jsonld |
| probe `strip-doc-FHR-microdata` | FHR/strip/microdata, FHT/strip/microdata |
| probe `links-doc-FHR-json` | FHR/links/json, FHT/links/json |
| probe `links-doc-FHR-yaml` | FHR/links/yaml, FHT/links/yaml |
| probe `links-FHR-fasta` | FHR/links/fasta |
| probe `links-FHR-gfa` | FHR/links/gfa |
| probe `links-doc-FHR-jsonld` | FHR/links/jsonld, FHT/links/jsonld |
| probe `links-doc-FHR-microdata` | FHR/links/microdata, FHT/links/microdata |
| probe `assess-doc-FHR` | FHR/assess/json, FHR/assess/jsonld, FHR/assess/microdata (+5 more) |
| probe `assess-FHR-fasta` | FHR/assess/fasta |
| probe `assess-FHR-gfa` | FHR/assess/gfa |
| probe `index-reject-json` | FHGFF3/index/json, FHP/index/json, FHR/index/json (+1 more) |
| probe `index-reject-yaml` | FHGFF3/index/yaml, FHP/index/yaml, FHR/index/yaml (+1 more) |
| probe `index-FHR` | FHR/index/fasta |
| probe `index-reject-gfa` | FHR/index/gfa |
| probe `index-reject-jsonld` | FHP/index/jsonld, FHR/index/jsonld, FHT/index/jsonld |
| probe `index-reject-microdata` | FHGFF3/index/microdata, FHP/index/microdata, FHR/index/microdata (+1 more) |
| probe `read-FHP-json` | FHP/read/json |
| probe `read-FHP-yaml` | FHP/read/yaml |
| probe `read-FHP-fasta` | FHP/read/fasta |
| probe `refuse-FHP-gfa` | FHP/assess/gfa, FHP/index/gfa, FHP/links/gfa (+4 more) |
| probe `refuse-FHP-gff3` | FHP/assess/gff3, FHP/index/gff3, FHP/links/gff3 (+4 more) |
| probe `read-FHP-jsonld` | FHP/read/jsonld |
| probe `read-FHP-microdata` | FHP/read/microdata |
| probe `write-FHP-json` | FHP/write/json |
| probe `write-FHP-yaml` | FHP/write/yaml |
| probe `write-FHP-fasta` | FHP/write/fasta |
| probe `write-FHP-jsonld` | FHP/write/jsonld |
| probe `write-FHP-microdata` | FHP/write/microdata |
| probe `verify-doc-FHP-json` | FHP/verify/json |
| probe `verify-doc-FHP-yaml` | FHP/verify/yaml |
| probe `verify-FHP-fasta` | FHP/verify/fasta |
| probe `verify-doc-FHP-jsonld` | FHP/verify/jsonld |
| probe `verify-doc-FHP-microdata` | FHP/verify/microdata |
| probe `strip-doc-FHP-json` | FHP/strip/json |
| probe `strip-doc-FHP-yaml` | FHP/strip/yaml |
| probe `strip-FHP-fasta` | FHP/strip/fasta |
| probe `strip-doc-FHP-jsonld` | FHP/strip/jsonld |
| probe `strip-doc-FHP-microdata` | FHP/strip/microdata |
| probe `links-doc-FHP-json` | FHP/links/json |
| probe `links-doc-FHP-yaml` | FHP/links/yaml |
| probe `links-FHP-fasta` | FHP/links/fasta |
| probe `links-doc-FHP-jsonld` | FHP/links/jsonld |
| probe `links-doc-FHP-microdata` | FHP/links/microdata |
| probe `assess-doc-FHP` | FHP/assess/json, FHP/assess/jsonld, FHP/assess/microdata (+1 more) |
| probe `assess-FHP-fasta` | FHP/assess/fasta |
| probe `index-FHP` | FHP/index/fasta |
| probe `read-FHGFF3-json` | FHGFF3/read/json |
| probe `read-FHGFF3-yaml` | FHGFF3/read/yaml |
| probe `refuse-FHGFF3-fasta` | FHGFF3/assess/fasta, FHGFF3/index/fasta, FHGFF3/links/fasta (+4 more) |
| probe `refuse-FHGFF3-gfa` | FHGFF3/assess/gfa, FHGFF3/index/gfa, FHGFF3/links/gfa (+4 more) |
| probe `read-FHGFF3-gff3` | FHGFF3/read/gff3 |
| probe `refuse-FHGFF3-jsonld` | FHGFF3/assess/jsonld, FHGFF3/index/jsonld, FHGFF3/links/jsonld (+4 more) |
| source `bioheaders convert --help: FHGFF3 supports HTML microdata, not JSON-LD` | FHGFF3/assess/jsonld, FHGFF3/index/jsonld, FHGFF3/links/jsonld (+4 more) |
| probe `read-FHGFF3-microdata` | FHGFF3/read/microdata |
| probe `write-FHGFF3-json` | FHGFF3/write/json |
| probe `write-FHGFF3-yaml` | FHGFF3/write/yaml |
| probe `write-FHGFF3-gff3` | FHGFF3/write/gff3 |
| probe `write-FHGFF3-microdata` | FHGFF3/write/microdata |
| probe `verify-doc-FHGFF3-json` | FHGFF3/verify/json |
| probe `verify-doc-FHGFF3-yaml` | FHGFF3/verify/yaml |
| probe `verify-FHGFF3-gff3` | FHGFF3/verify/gff3 |
| probe `verify-doc-FHGFF3-microdata` | FHGFF3/verify/microdata |
| probe `strip-doc-FHGFF3-json` | FHGFF3/strip/json |
| probe `strip-doc-FHGFF3-yaml` | FHGFF3/strip/yaml |
| probe `strip-FHGFF3-gff3` | FHGFF3/strip/gff3 |
| probe `strip-doc-FHGFF3-microdata` | FHGFF3/strip/microdata |
| probe `links-doc-FHGFF3-json` | FHGFF3/links/json |
| probe `links-doc-FHGFF3-yaml` | FHGFF3/links/yaml |
| probe `links-FHGFF3-gff3` | FHGFF3/links/gff3 |
| probe `links-doc-FHGFF3-microdata` | FHGFF3/links/microdata |
| probe `assess-doc-FHGFF3` | FHGFF3/assess/json, FHGFF3/assess/microdata, FHGFF3/assess/yaml |
| probe `assess-FHGFF3-gff3` | FHGFF3/assess/gff3 |
| probe `index-reject-gff3` | FHGFF3/index/gff3 |
| test `tests/fht_test.py::test_strip_and_convert` | FHT/read/yaml, FHT/strip/fasta, FHT/write/fasta (+1 more) |
| test `tests/fht_test.py::test_validate_and_assess_stay_draft_aware` | FHT/assess/fasta, FHT/read/fasta |
| opt-in `tests/fht_conformance_test.py::test_vector_validity` | FHT/links/fasta, FHT/read/fasta, FHT/strip/fasta (+2 more) |
| test `tests/fht_test.py::test_family_table_opens_only_fasta` | FHT/assess/gfa, FHT/assess/gff3, FHT/index/gfa (+11 more) |
| test `tests/fht_test.py::test_unbound_forms_are_refused_not_stretched` | FHT/read/jsonld, FHT/read/microdata, FHT/write/jsonld (+1 more) |
| test `tests/fht_test.py::test_verify_cli_accepts_and_rejects` | FHT/verify/fasta |
| test `tests/fht_test.py::test_verify_links_three_verdicts` | FHT/links/fasta |
| pin `fhgm-base@none` | FHGM/assess/fasta, FHGM/assess/gfa, FHGM/assess/gff3 (+46 more) |

Each test above was re-found as a `def` in the file it names, in this
run. Each probe is in the table immediately above, with the command and
both exit statuses.

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
[^r-fhgm-scope]: nothing in this artifact names the model draft: no vendored draft contract, and no base or carrier pin of its own, which `bioheaders-pin-audit` reports as `fhgm-base@none` / `ABSENT` with the reason recorded in `bioheaders/pins.json`. A scope statement, not a hole this document fills: the lane is FAIR-bioHeaders-Tools#135, and the cell is unrun rather than run and unrecorded

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
[^e98]: `tests/fht_test.py::test_strip_and_convert` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e99]: `tests/fht_test.py::test_validate_and_assess_stay_draft_aware` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e100]: `tests/fht_conformance_test.py::test_vector_validity` — re-found in the tree, and it is *not* part of a default run: it consumes the draft lane's suite and so skips unless `BIOHEADERS_EXPERIMENTAL_FHT` is set and a pinned FHT-Specification checkout is given. That is why the lane is described as opt-in rather than counted as coverage
[^e101]: `tests/fht_test.py::test_family_table_opens_only_fasta` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e102]: `tests/fht_test.py::test_unbound_forms_are_refused_not_stretched` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e103]: `tests/fht_test.py::test_verify_cli_accepts_and_rejects` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e104]: `tests/fht_test.py::test_verify_links_three_verdicts` — re-found in the tree while rendering; `poetry run pytest` runs it
[^e105]: `bioheaders/pins.json` row `fhgm-base@none` — printed `ABSENT` by `bioheaders-pin-audit`

Digest of the grid: `9bf2c3d66480d3195b1f521f71629a22` (245 cells = 5 types x 7 operations x 7 serializations).
