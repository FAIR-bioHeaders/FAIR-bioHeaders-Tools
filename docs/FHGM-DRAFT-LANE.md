# FHGM draft lane — pinned development bytes behind an opt-in gate (PREP)

> **Status: preparation, not publication.** This document and the gated lane in
> this branch prepare FAIR-bioHeaders-Tools support for FHGM - the draft gene-model
> record contract carried by the FHGFF3 extension key `x-fhgm-models`, per
> [FAIR-bioHeaders-Specification#204](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/204)
> and [FAIR-bioHeaders-Tools#135](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/135).
> FHGM has **no released contract**: it appears nowhere in the shared
> specification's `schemas/versions.json`, has no `schemaVersion`, no schema URL, no
> release tag and no w3id alias, and nothing here publishes, adopts, releases or
> claims support for it. Publication is a maintainer action, scheduled as shared
> specification `v0.8.0`, and the toolkit release that can cite this lane as shipped
> is a later one: **merged is not released**.

## 1. What FHGM is, and what it is not

FHGM describes one contributed gene model inside an annotation file. It is not a
header family of its own and it is not selected by a record's `schema` URL. A
carrier is an ordinary released FHGFF3 file: it cites a registered FHGFF3 base
release, keeps its exact-byte SHA-512/256, and carries its model records under the
single top-level extension key `x-fhgm-models` that docs/FORMAT.md R15 admits from
FHGFF3 1.1. That is why the lane cannot change any released verdict: the released
FHGFF3 header check, the checksum check and the GFF3 feature-layer check (owned by
`gff3-validator`) all stay where they were, and the FHGM result is a separate block
beside them.

Because the extension key is already admissible under the released contract, a
carrier holding model records validates **today, with this lane closed**, as any
other FHGFF3 file. What the lane adds is the model-level reading - the six rules
that a JSON Schema cannot express - and it adds it only on request.

## 2. The gate

```console
$ bioheaders verify annotation.fhgff3.gff3                     # default: no FHGM output
$ BIOHEADERS_EXPERIMENTAL_FHGM=1 bioheaders verify annotation.fhgff3.gff3
```

`BIOHEADERS_EXPERIMENTAL_FHGM` is read by `bioheaders/fhgm.py` through
`bioheaders.selection.environment_enabled()`, the same value vocabulary as the FHT
lane's `BIOHEADERS_EXPERIMENTAL_FHT` (`1`, `true`, `yes`, `on`, case-insensitive).
The two gates are independent: opening one never opens the other, and a released
family behaves identically under either (`tests/fhgm_test.py` asserts both
directions).

The lane runs only when three things hold: the gate is open, the carrier is GFF3,
and the header actually declares `x-fhgm-models`. A header without the key never
enters it, so the default output - `Checksum verified.` - is byte-for-byte what it
was before #135.

`--fhgm-predecessor FILE` (repeatable) hands `verify` prior annotation snapshots.
It is accepted only with the lane open and only for GFF3 input, because silently
dropping it would turn a missing option into a K6 "unresolvable" verdict.

## 3. What is pinned, and where

Every byte the lane reads is recorded in `bioheaders/schemas/bundled.json` under
`drafts.FHGM`, and every row is also in `bioheaders/pins.json` for
`bioheaders-pin-audit`:

| artifact | repository path | commit | sha256 of the bytes read |
| --- | --- | --- | --- |
| record contract (K2) | `development/model/fhgm-model.schema.json` | `06176262f9824f26d974a15d8feeebde1fbeb0a8` | `b7075e5872e0a5ffce5ae61c590ce182f1f219fa269413cad3b1a966753cfeae` |
| transport overlay (K1) | `development/model/fhgm-draft.schema.json` | `019bc29e32ce225791053dd2ce323bb91f304ce1` | `533b3120f4a86590f1b60a2175487597c99b646b3d092b7818b1f682c6cecf9b` |
| base registry (provenance) | `development/model/base-schemas.json` | `06176262f9824f26d974a15d8feeebde1fbeb0a8` | `8feb36c1957d151e22da9833b7a3421b339b5f18475d054ebe7e54cabcf72eac` |
| development suite (62 vectors) | `development/conformance/manifest.json` | `06176262f9824f26d974a15d8feeebde1fbeb0a8` | `e41f05fd8bb8b8ec175b0192b80832041c84e15c325876aa66a86ba6e59413ce` |
| checker the semantics are matched to | `development/model/validate_fhgm.py` | `06176262f9824f26d974a15d8feeebde1fbeb0a8` | `de4e393d15f89eaa2043d76bcc0dbe445c08af787a748eabdd954715b018f460` |

All five are from `FAIR-bioHeaders/FHGM-Specification`, retrieved 2026-11-19 with
the command recorded in each row, and each commit is a **commit**, never a branch:
`main` of the owning repository moves (it moved on 2026-11-19), and a lane that
chased it would report verdicts nobody pinned. The checker is named for its
semantics and is not vendored or imported.

The two released FHGFF3 bases the registry names are *not* new bytes: they are the
frozen snapshots this package already ships (`schemas/fhgff3-1.1.json` at tag
`v0.5.0`, `schemas/fhgff3-1.2.json` at tag `v0.6.0`), pinned a second time as
`base-carrier` rows so the base the draft selects is audited rather than assumed.
`tests/fhgm_test.py::test_base_rows_are_the_bundled_released_snapshots` checks the
mirrored digests against the shipped files, and
`test_pinned_bytes_are_the_recorded_commit` re-reads every artifact from a
`FHGM_SPECIFICATION` checkout with `git show <pinned revision>:<path>` and refuses a
mismatch. Digest drift inside the package is a refusal, not a fallback: `pinned()`
warns and raises, because the disclosure would otherwise name bytes it did not use.

Re-pinning any of these is a deliberate, dated commit, and the shared 291-vector
conformance ledger is untouched: FHGM's suite is a development record of another
repository, labelled `draft, not acceptance`.

## 4. The rules, and how they are matched

`bioheaders/fhgm.py` implements the model-level rules of the pinned contract:

* **K1 transport** - the cited URL selects exactly one registered base, and those
  bytes - not another release's - judge the carrier and the stated `schemaVersion`.
  A citation no registered base answers to (raw main, a superseded release) is
  refused; an empty `x-fhgm-models` array is refused.
* **K2 record shape** - every record against the pinned native contract, the whole
  record, before any rule reads one of its fields.
* **K3 identity** - `modelId` uniqueness after Unicode NFC normalisation, before
  any per-record rule, so a duplicate is reported as the snapshot defect it is.
* **K4 target** - `featureId` resolves, percent-decoded from the raw row bytes, to
  exactly one local root `gene`/`SO:0000704` row with no `Parent` attribute.
* **K5 reference** - the record's reference shares at least one comparable form with
  the file genome link and never contradicts it.
* **K6 history** - a `predecessor` pointer resolves against the explicitly supplied
  prior snapshots only, and reports `resolvable` or `unresolvable` per claim.

Ordering is part of the semantics, and both directions are tested:
K2 before K3, K3 before the per-record K4/K5, the file-bound checksum (the suite's
`B1`) before any model verdict at all.

Two deliberate differences from the pinned reference, each with a named test:

1. **Strict decoding.** Row IDs are percent-decoded over raw bytes and the decoded
   value must be valid UTF-8; a malformed or truncated escape, or an undecodable
   sequence, is a refusal. The comparison uses the record's `featureId` **as
   written**. A `errors="replace"` read would fold distinct broken spellings into
   U+FFFD and could make a record "resolve" to a row nobody named, so nothing in
   this module substitutes anything into an identity.
2. **Empty `Parent=` refuses.** The pinned checker's `gene_targets()` ignores a
   `Parent` attribute whose value is empty and so treats that row as a root; the
   manifest's own K1/K4 wording requires a row *with no `Parent` attribute*, and an
   attribute that says "Parent" while naming nothing establishes neither reading.
   This lane therefore refuses it as indeterminate. No vector in the pinned suite
   exercises it, and all 62 recorded outcomes are unchanged (see section 6), so this
   is a hardening to report upstream, not a re-interpretation of a recorded case.

Records are validated with `bioheaders.schema_validator.draft_validator()`: the
same corrected ECMA-262 `pattern` and RFC 3339 `full-date` rules the released
headers use, plus `format: uri` - which the released header contracts never state,
and which the stock checker enforces only when an optional dependency happens to be
installed. No module outside the recorded allow-list constructs a stock validator
(`tests/schema_validator_routing_test.py`).

## 5. Reporting: three verdicts, never one

`FHGMReport` keeps the layers the owning suite records apart, and
`bioheaders verify` prints them as an `FHGM draft lane:` block after the released
lines:

```text
Checksum verified.
FHGM draft lane: model result: pass
FHGM draft lane: released FHGFF3 header: pass
FHGM draft lane: file checksum: verify
FHGM draft lane: GFF3 feature syntax/biology: not-run - not run here: GFF3 syntax and biology belong to gff3-validator
FHGM draft lane: base: FAIR-bioHeaders/FAIR-bioHeaders-Specification@v0.6.0 (sha256 1942be4c…)
FHGM draft lane: records: 1; prior snapshots supplied: 0
FHGM draft lane: x-fhgm-models records were read against the bundled FHGM draft contract (…)
```

* A model rejection is labelled `FHGM` and never `FHGFF3`: the released header line
  and `Checksum verified.` keep saying what they said, and `verify` exits 1 for the
  model layer on its own account (`tests/fhgm_test.py::test_model_rejection_does_not_rewrite_the_released_verdict`).
* The feature layer is always `not-run` here. GFF3 syntax, SO semantics and biology
  belong to `gff3-validator`; a lane verdict is never evidence about them, and the
  consumer test asserts that this layer is reported as skipped rather than passed
  when the tool is absent.
* `not-run` is a real value: an unreadable header, a stale checksum (reported as
  `B1`), or a carrier larger than the lane's memory bound each say so instead of
  claiming a verdict. The bound - `MAX_LANE_BYTES`, shrinkable through
  `BIOHEADERS_FHGM_MAX_BYTES` - exists because K4 needs the whole feature-row
  inventory: the bytes are collected inside the checksum's single pass, so a pipe or
  stdin is still read exactly once and no input is opened twice.
* Every run that reads draft bytes warns, and the warning names each pinned commit
  and the SHA-256 of those bytes (rule V7's disclosure duty), the same pair the FHT
  lane and the four sibling libraries publish.

## 6. Evidence measured on 2026-11-19

* `tests/fhgm_conformance_test.py` scores all **62** vectors of the pinned
  development suite through the lane, layer by layer, against the owning
  manifest's recorded outcomes: **17 pass, 45 reject, 0 not-run** for the model
  layer; base **60 accept / 2 reject**; every invalid vector's recorded `reason`
  substring present; checksum layers reproduced independently with `hashlib`. The
  42-of-45 gap-proof figure the owning suite publishes is reproduced exactly (the
  three that are not gap-proof are the two `B1` transport-floor vectors and the
  stale-bytes vector). That run is `127 passed`, exit 0, with the GFF3 feature
  layer reported skipped for every vector because `gff3-validate` was not supplied.
* With `GFF3_VALIDATE` pointing at `gff3-validate` 0.1.0, the same 62 vectors also
  matched their recorded `accept` for the feature layer, and the run is
  `126 passed, 1 skipped` - the skip being the test that asserts the layer is
  reported skipped when that tool is absent. No FHGM verdict rests on the feature
  layer either way, and the owning suite's note says the same.
* Every vector file is re-read from the pinned revision with
  `git show <revision>:<path>` and compared byte-for-byte with the checkout, and
  `test_suite_manifest_matches_pin` compares the manifest digest, size and vector
  count with `drafts.FHGM.suite`, so a pass cannot be quoted against other bytes.
* The FHT lane is unaffected by the FHGM gate: `tests/fht_conformance_test.py`
  still scores the **72** vectors recorded in `drafts.FHT.suite` (revision
  `be9bcc82`) - `83 passed, 62 skipped`, the skips being the parent-link test for
  the vectors that record no parent file. That is what this branch pins; section 7
  records the state of the 82-vector suite on the owning `main`.
* `bioheaders-pin-audit` reports every new FHGM row `FRESH` against the authority
  bytes at the named commit or tag, with a passing 404 control on the backend, and
  the `v0.5.0` base row carries the advisory lag line saying the current release is
  `v0.6.0`. Measured: `6 FRESH, 0 DRIFT, 0 ABSENT of 6` for the FHGM rows, and
  `32 FRESH, 0 DRIFT, 2 ABSENT, 2 NOT_A_FILE_PIN of 36` across the whole table.
* Wheel and sdist evidence (candidate bytes, not a published release):
  `poetry build` artifacts installed into fresh environments outside this checkout
  carry both pinned draft files with digests equal to the registry, the lane is
  closed by default there, and `bioheaders verify` on a real pinned vector prints
  the same layered block; `bioheaders-pin-audit` from the installed wheel reports
  the six FHGM rows `FRESH`. See `.github/workflows/release.yml`, which installs the
  built wheels outside the checkout as its own release smoke test, for the
  published-package version of this check.

## 7. What remains publication-gated

Merging this lane prepares #135 and #155; it closes neither. Outstanding, in the
order the gates fall:

1. **FHGM publication** - the adopted contract must be published as shared
   specification `v0.8.0` with its own `schemaVersion`, `schemas/versions.json` row
   and release URL, and the owning suite promoted from a development record to a
   registered conformance suite. Until then this lane reads pinned commits, and the
   word to use about FHGM is *draft*.
2. **A toolkit release** - the capability matrix's release-evidence rows and the
   pin audit's currency claims are quotable against released bytes. On `main` this
   lane is merged-as-draft, which is not shipped: check `git tag --contains` before
   describing any of it as published.
3. **Released-consumer handoff** - the default-off gate, the `draft, not acceptance`
   labels, the `FHGM_SPECIFICATION`-optional suite consumer and the
   `draft`-marked matrix cells are preparation shapes. Revising them is a separate
   reviewed change after publication, not an automatic consequence of it.
4. **The FHT re-pin is a different dated act.** `drafts.FHT.suite` on this branch
   names revision `be9bcc82` (72 vectors) and `drafts.FHT` names `226f923c`
   (`59ad9641…`). The owning repository's current `main` carries an 82-vector suite
   at `86438f21` whose contract bytes are `4156353a…`, and the four sibling
   libraries pinned that pair on 2026-11-18. Moving this package's FHT axes to those
   bytes is a deliberate, dated commit with its own re-verified evidence - not
   something #135 or a matrix refresh may do in passing, and not something to chase
   while `main` is moving under it.
5. **Curator-side items** the owning repository keeps: the open scope rows
   (`O1`-`O5` of its manifest - transcript-only scope, split/merge, assembly
   migration, companion-file identity, who may mint external model IDs) stay
   questions for curators, and no cell or rule here implies an answer.
