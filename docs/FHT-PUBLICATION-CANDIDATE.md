> Current release transition: specification v0.8.0 publishes native FHGM0.1;
> [native selection](FHGM-MODEL.md) is separately bundled beside normal FHT.
> Toolkit0.13 is still under installed-artifact validation before publication.
> Earlier preparation receipts below retain their dated scope.

# Published FHT bundle promotion

This checkout prepares toolkit 0.13.0; no toolkit release is asserted here.
Shared specification v0.6.1 and v0.7.0 are actual published releases. The former
repeats v0.6.0's three contracts. The latter adds FHT 1.0 to those unchanged
contracts and is the current bundled baseline.

| Release | Immutable commit | Archive |
| --- | --- | --- |
| v0.6.1 | 1812c3bf132fe47f4c30aa8bebd59baeb580988a | 10.5281/zenodo.24384147 |
| v0.7.0 | 623c79fe58edeb238a20fb6de518c62dd69b92bc | 10.5281/zenodo.24385024 |

Their GitHub Releases are recorded under `publication` in
`bioheaders/schemas/bundled.json`. FHT schema SHA-256 is
`082b0790b7878940c4496c97d7485e32c65de8ba75ecc080e53f04fb44251a43`.
`tests/fixtures/fht-publication/provenance.json` records all 119 exact tag inputs,
including the publication-neutral manifest and seven HTML/JSON/FASTA triples.
The 93 shared counterparts remain distinct from the owning 93-vector draft suite
and the historical shared 291-vector ledger plus adopted 319-vector/64-policy
corpora. Refreshes do not rewrite those historical sources.

Normal shared raw-main, raw-tag and w3id citations select bundled FHT without a
candidate switch. Unknown releases, older releases without FHT and unsupported
raw refs reject under V4. The historical FHR-Specification alias is not invented
for FHT. Selection uses offline tag bytes, not network resolution. The upstream
w3id redirect change is still pending; no live-alias claim follows from bundling.

Supported FHT surfaces are JSON/YAML, FASTA combine/strip/verification, supplied
parent links and typed HTML. Canonical HTML itemtype remains the schema `$id`,
`https://w3id.org/fair-bioheaders/fht/v0.7.0`, regardless of repeated later family
rows. HTML needs an RCDATA-capable runtime parser; incompatible runtimes refuse.
JSON-LD, FHT GFA/GFF3 headers, FHT context/DCMI adoption and the FHR authoring
builder are outside this support. Parent matching proves exact file identity,
not biological derivation. C1 completeness arithmetic checks both directions.

Owning raw-main V7 remains separately gated by `BIOHEADERS_EXPERIMENTAL_FHT=1`.
Frozen historical parents need that gate to replay their own link fixtures; new
shared records link without it. FHGM remains separately experimental pending
actual v0.8.0 artifacts. One toolkit 0.13.0 publication remains held until both
specification stages and current-head validation/review are complete.
