# FHT publication candidate (unpublished)

The proposed toolkit version is 0.13.0. This branch stages an explicitly enabled
consumer lane; it does not publish a package or assert that specification v0.7.0
exists. The released/current registry stays at v0.6.0. FHGM remains experimental.

Set `BIOHEADERS_CANDIDATE_FHT=1` for candidate validation, verification, JSON/YAML,
FASTA combine/strip, parent links and typed HTML conversion. Normal shared
raw-main, raw-tag v0.7.0 and w3id v0.7.0 citations select the bundled candidate;
unknown versions and older releases without FHT reject. No network fetch or
automatic draft chase occurs. Typed HTML writes the fixed schema `$id`,
`https://w3id.org/fair-bioheaders/fht/v0.7.0`, while its ordinary `schema` property
preserves the supplied selector. Formal aliases are recognized before conflict
detection, including unsupported versions. JSON-LD, GFA/GFF3 FHT headers and the
FHR metadata authoring builder are not additional FHT surfaces.

The historical owning V7 lane retains its own schema and separate
`BIOHEADERS_EXPERIMENTAL_FHT=1` gate, off by default. Frozen historical parents
need that gate when replaying their link fixtures. New shared records can link
without it. Parent matching establishes exact file identity, not derivation.

## Exact inputs and downstream handoff

Candidate schema SHA-256:
`082b0790b7878940c4496c97d7485e32c65de8ba75ecc080e53f04fb44251a43`.
Source: shared commit `1a0792e6f8db1b73959999d30f5e6575b982cbfc`.
`tests/fixtures/fht-publication/provenance.json` pins all 119 input files,
including seven shared JSON/HTML/FASTA triples and 93 release counterparts.
The unchanged published suite and historical owning sources remain distinct.

Website and Nextflow consumers must keep public activation disabled pending
publication. They can test generated HTML/YAML using the installed candidate
commands with the candidate environment variable, then compare converted JSON
with the source metadata (HTML omits x- extensions under M5). Use
`tests/fht_publication_test.py` for installed read/write, strip/recombine,
compressed standard input, arithmetic and link receipts.

## Publication finalization owned by release coordination

Pending fields in `schemas/bundled.json` are explicitly null/false:
actual dereferenced v0.7.0 tag commit, GitHub Release object, archive identifier,
and verified alias. Do not fill them from a proposed tag or local branch.
The guidance-only v0.6.1 release must likewise be verified from actual release
objects and tag bytes before bundling its row. Finalize current/released tables,
frozen schema copies, pins and context catalog only from those actual bytes.
Recheck schema identity, all seven triples, 93 counterparts, the old published
suite, installed wheel/sdist commands, independent different-model review and
current CI. Main merge/default promotion follows actual shared publication;
package publication remains a separate gate. Tools #135 and #155 remain open.
