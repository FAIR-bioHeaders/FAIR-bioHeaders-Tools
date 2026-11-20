> Current bundle: shared v0.8.0 four-header row and native FHGM0.1 are separate
> released references. Historical owning V7 snapshots retain their draft labels.
> The dated measurements below are not claims that current contracts remain
> unpublished. See [FHGM-MODEL.md](FHGM-MODEL.md).

# Cross-repo pin audit (`bioheaders-pin-audit`)

## Content currency and consumer comparison (#167)

Integrity and currency answer different questions. The existing `FRESH` / `DRIFT`
/ `ABSENT` verdict compares a record with the exact revision it names. The new
opt-in default-content section compares that **verified** record with the same
path at one captured commit of the owning repository's actual default branch.
An old released pin remains a valid historical pin even when default content
is different. This is an advisory observation, not a recommendation to update
it or a requirement that released material match `main`.

```bash
bioheaders-pin-audit --against-default
bioheaders-pin-audit --against-default --consumers --json
bioheaders-pin-audit --against-default --offline
```

| Default-content status | Meaning |
| --- | --- |
| `CURRENT_CONTENT` | Recorded integrity is FRESH and exact SHA-256 matches default content. Different commits with equal bytes remain current content. |
| `SUPERSEDED_CONTENT` | Recorded integrity is FRESH, but default bytes differ. The recorded pin is still honest at its own revision. |
| `UNAVAILABLE` | Integrity is unverified/corrupt, metadata/file response is missing/empty/malformed, or a control failed. No currency verdict is earned. |
| `NOT_APPLICABLE` | A derived subset is not a whole-file pin, or a copied directory has no single same-path file digest. Its separate integrity/relationship report remains authoritative for what was actually checked. |

`--exit-on-drift` concerns integrity only: a DRIFT row, a derived suite whose
declared transform is a MISMATCH, a failed negative control or a merge-conflict
marker. Neither currency nor
consumer differences turn advisory reporting into a gate. No code writes a pin,
fetches into a checkout, rewrites a commit, starts a draft lane or adds an FHGM
reference. `--json` continues to report `"wrote": []`.

HTTPS default-branch discovery uses the GitHub repository and commit metadata,
then reads file bytes at the captured full commit, not a moving raw branch URL.
The metadata backend must return 404 for a nonsense content path; the raw-file backend
has its own negative file control. Redirects, failed controls, missing/empty
responses and invalid identities produce UNAVAILABLE. Local checkouts resolve
`refs/remotes/origin/HEAD`, never the operator's current task branch or uncommitted
files; a clone lacking that default-branch record reports unavailable. The tool
never updates it. Reports name the snapshot source explicitly: a local/fixture
comparison establishes equality only with that supplied snapshot, not a freshly
queried remote head. Offline fixtures use `default-branches.json`, mapping each
`owner/repository` to explicit `branch` and full `commit` values, alongside the
existing `<repository>@<revision>/<path>` authority layout. Offline mode with no
suitable checkout/fixture does not perform or claim network controls.

### Known consumer records

`--consumers` reads this installation/checkout's runtime registry plus these
specific JSON provenance sources at each consumer's captured default commit:

| Consumer | Provenance source |
| --- | --- |
| Tools | Local `bioheaders/schemas/bundled.json`; the audit table remains separately reported, so runtime/audit disagreement stays visible. |
| JavaScript | `drafts/provenance.json` |
| Java | `src/main/resources/org/fairbioheaders/schemas/provenance.json` |
| Julia | `drafts/provenance.json` |
| R | `inst/VENDORED.json` |

Explicit adapters report FHT/FHGM contract and suite identities, recorded digests,
optional **recorded** counts, consumer-source commit and independent integrity /
currency outcomes. Java's explicitly embedded base registry is also shown; bases
held elsewhere are not inferred from an overlay, implementation or another
consumer. This is a bounded comparison of these sources, not the whole-federation
inventory or a native capability/acceptance test. Unknown registry shapes and
unavailable provenance are visible; missing logical records say NOT_RECORDED,
not zero vectors or a passing FHGM implementation.

`verified_digest_groups` groups only integrity-verified records by logical
reference and exact digest. Commit fields remain verbatim: equal content at a
last-toucher and at an observation-time tip does not justify rewriting either
record. A recorded vector count does not establish a run, acceptance result or
content equivalence. Every FHT/FHGM row remains **draft, not acceptance** under V7.

### Derived subsets within the conformance-suite class

The two existing FHP/FHGFF3 manifest rows now explicitly declare a
`relationship.kind: derived-subset`, their format filter, and the complete parent
manifest's existing `v0.6.0` tag identity/digest/byte count. Their old whole-file
`sha256` values remain null: they are not exact copies of that parent file.
They report **NOT_A_FILE_PIN**, separately counted from ABSENT and FRESH.

Before comparing selected vector objects, the checker verifies the entire parent
manifest against the declared source digest and length. It then compares the
complete selected vector list in source order, including nested values, with the
local manifest. MATCH means this declared transformation matched; MISMATCH and
NOT_PERFORMED explain differences or unavailable evidence. It does **not** verify
fixture payload files, execute vectors or claim conformance. Existing native
fixture-parity tests own payload-byte comparisons. Unknown/empty filters never
silently pass, and local annotations outside the vector list are not part of this
explicit transform.

### Deliberately approved pin reconciliation — 2026-11-16

Before this approved update, the runtime record named FHT suite `7503b264` / 68 vectors /
59,791 bytes / `ab72fc985a26…`; the audit record named `24d3b033` / 66 / 56,250 /
`9b07179497bd…`. The owning default branch has 72 / 65,615 / `9fd8c0b2a463…`,
identical at its `a06ea0c0` tip and manifest last-change `be9bcc82`.
These exact downloaded-byte measurements informed a separate dated proposal.
The maintainer explicitly approved that proposal: runtime and audit now both
name `be9bcc825f55db92852fd882ffba4c1c214f53db`, SHA-256
`9fd8c0b2a4638d5ddc0bf9b5d1e96c66778b26bcf8f93975aafb707d8f2b702c`,
65,615 bytes / 72 vectors. This dated change is separate from reporting code;
no command applies it automatically. The FHT contract remains independently
pinned at `226f923c`; no other pin or consumer convention moves.

The scheduled advisory job probes once into JSON, then renders text from the same
captured data. Tests cover honest historical pins with changed defaults,
digest-equivalent commits, corrupt-record withholding, metadata/file controls,
offline behavior, a task checkout with modified bytes, consumer gaps/equivalence,
whole-parent and nested-order transform failures, and byte-identical inputs after
a command. Identifier-policy disposition under specification #246/#241 and actual
federation-wide wiring remain outside this packet; none is silently adopted here.

The older dated measurements below describe the earlier integrity-only report.
Their 5-ABSENT totals precede derived-subset classification; they are historical
measurements, not current aggregate results.


Reference implementation of the gate proposed in
[FAIR-bioHeaders-Specification#241](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/241):
one command that takes every cross-repo contract reference a repository holds and
compares it with **the authoritative bytes at the exact revision that reference
names**, then reports `FRESH` / `DRIFT` / `ABSENT` per reference.

It is advisory, standard-library-only, and it never writes a pin.

## Why this exists

Two independent defects found on 2026-11-15 turned out to be the same defect, and
neither was the question the existing `draft-pin-freshness` jobs answer ("do the
draft bytes I vendored still match the owning repository's live `main`?"):

* **#241(a) — a released contract, stale in the tree that owns it.**
  `FHP-Specification/fhp.json` held the bytes of specification tag `v0.5.0`
  (`21,806 B`, sha256 `2409739d4a223164ca368f93afa78c8f1e3809fb04ec46cc9a793cc5aaaba427`)
  while the released authority at tag `v0.6.0` was FHP 1.2
  (`24,681 B`, sha256 `92a0b3cbcfe69939ebfaac69f0c5958ce426c005873efe8d3e3eb0fc0dab6de5`).
  Model and generated schema lagged *together*, so `check_linkml`,
  `check_schema_drift` and `check_release.py` all passed: **a self-consistency gate
  cannot detect drift that both sides of the comparison share**, and comparing with
  `main` would not have caught it either.
* **#241(b) — a released carrier rejected by a draft harness.** FHGM pins FHGFF3
  `v0.5.0` as its base schema, whose `schemaVersion` enum is `['1.0','1.1']`, so a
  real FHGM payload inside a released 1.2 header fails the draft's own harness. The
  pin that went stale was the **base/carrier** pin, an axis nothing tracked.

The two rules that fall out of those measurements are built into the design rather
than added later:

1. **Anything released is named by a tag, never by `main`.** A `released-contract`
   or `base-carrier` row whose `revision_kind` is not `tag` is reported as unusable
   (`ABSENT` with the rule quoted) instead of being silently compared. Rule 1 holds
   for `copied-tree` rows too (FAIR-bioHeaders-Tools#163): FHGM's
   `header/provenance.json` records `source.ref = "main"`, and the tree it pins
   models the *released* FHGFF3 header — so it must be tag-pinned, and scoring it
   against `main` would prove nothing.
2. **Contract pin, suite pin and base pin are three references.** They move
   independently: `FHT-Specification` `fht.json` is byte-identical
   (`59ad9641adcb0e55…`, 29,430 B) at the contract pin `226f923c…` and at the later
   suite commit `24d3b033…`, while `conformance/manifest.json` moved from
   `d9025104675e69b5…` (54,216 B, 65 `fht-fasta` vectors) at `226f923c…` to
   `9b07179497bdc724…` (56,250 B, 66 vectors) at `24d3b033…`. All six digests were
   measured on 2026-11-15 from `git show` and re-read over HTTPS at the same
   revisions.

## The five reference classes

| class | authority | revision kind | toolkit rows |
| --- | --- | --- | --- |
| `released-contract` | a specification release's published bytes | **tag** | 25 |
| `draft-contract` | the owning development repository at a recorded commit | commit | 1 |
| `conformance-suite` | the owning repository's `conformance/manifest.json` at a recorded revision | commit / tag | 3 |
| `base-carrier` | the released schema a draft embeds, at the tag that draft pins | **tag** | 1 |
| `copied-tree` | a byte-copied upstream directory under one provenance record: (repository, revision, record) | **tag**, or commit for a labelled draft tree | 1 |

The table itself is data, not prose: `bioheaders/pins.json`, one row per reference,
each with `repository` / `revision` / `revision_kind` / `path` (the authority),
`local` (this repository's copy), `sha256` / `bytes` (what this repository asserts),
plus `class`, `label`, `note` and `recorded_in` (where the assertion lives). A
`copied-tree` row names a consumer `provenance` record instead of one `path`: the
record's `copied[]` entries are the per-path assertions. Of the 31 rows, 25 are a
vendored copy plus its recorded digest, 1 (`fht-manifest@24d3b03`) is a digest
measured from the authority with no vendored copy, and 5 carry no digest at all and
report `ABSENT` with the reason.
`tests/pin_audit_test.py::test_shipped_digests_are_the_bytes_in_this_checkout`
re-measures all 25 local digests against their files on every test run, so an
invented or mistyped value cannot survive.

## What the toolkit holds (measured 2026-11-15, re-measured 2026-11-16 with the fifth class)

The audit resolves 26 of the 31 rows and reports **26 FRESH, 0 DRIFT, 5 ABSENT**,
over HTTPS with a negative control on each backend. The transcript below is
abridged to its header, one sample row of each shape, and the footer.

```
$ bioheaders-pin-audit
Cross-repo pin audit (FAIR-bioHeaders-Specification#241) — table version 2, 31 references.
  backend https FAIR-bioHeaders/FAIR-bioHeaders-Specification: negative control 404 as expected at 7 revision(s); e.g. GET https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/v0.3.0/pin-audit-404-control.json -> 404
  backend https FAIR-bioHeaders/FHT-Specification: negative control 404 as expected at 2 revision(s); e.g. GET https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/226f923c28b680edb3c546e99a751482d06aef1a/pin-audit-404-control.json -> 404

released-contract — 25 reference(s)
  FRESH   fhr-1@v0.3.0                           fhr.json@v0.3.0                          e3d3843e1a16 e3d3843e1a16
  ...
  FRESH   fhp-1.2@v0.6.0                         fhp.json@v0.6.0                          92a0b3cbcfe6 92a0b3cbcfe6
  FRESH   fhgff3-1.2@v0.6.0                      fhgff3.json@v0.6.0                       1942be4cefc8 1942be4cefc8
  ABSENT  fhp.context.jsonld@unrecorded          jsonld/fhp.context.jsonld@-              recorded - authority -
          detail: no upstream revision recorded: ...
summary: 26 FRESH, 0 DRIFT, 5 ABSENT of 31
advisory only: FRESH/DRIFT/ABSENT change no file and no pin. Re-pinning is a deliberate, dated commit in the repository that holds the pin.
```

### Measured 2026-11-19 — with the FHGM draft lane (#135)

```
$ bioheaders-pin-audit
Cross-repo pin audit (FAIR-bioHeaders-Specification#241) — table version 2, 36 references.
  backend https FAIR-bioHeaders/FAIR-bioHeaders-Specification: negative control 404 as expected at 7 revision(s); ...
  backend https FAIR-bioHeaders/FHT-Specification: negative control 404 as expected at 2 revision(s); ...
  backend https FAIR-bioHeaders/FHGM-Specification: negative control 404 as expected at 2 revision(s); ...
  ...released-contract rows unchanged (all FRESH)...
draft-contract — 4 reference(s)
  FRESH   fht-draft@226f923                      fht.json@226f923c28b6 59ad9641adcb 59ad9641adcb  [draft, not acceptance]
  FRESH   fhgm-record-draft@0617626              development/model/fhgm-model.schema.json@06176262f982  b7075e5872e0 b7075e5872e0  [draft, not acceptance]
  FRESH   fhgm-transport-draft@019bc29           development/model/fhgm-draft.schema.json@019bc29e32ce  533b3120f4a8 533b3120f4a8  [draft, not acceptance]
  FRESH   fhgm-base-registry@0617626             development/model/base-schemas.json@06176262f982 8feb36c1957d 8feb36c1957d  [draft, not acceptance]
conformance-suite — 4 reference(s)
  FRESH   fht-manifest@be9bcc8                   conformance/manifest.json@be9bcc825f55 9fd8c0b2a463 9fd8c0b2a463  [draft, not acceptance]
  NOT_A_FILE_PIN fhp-fixtures@v0.6.0-filtered    conformance/manifest.json@v0.6.0   recorded - authority cdbb79b1fbfd
  NOT_A_FILE_PIN fhgff3-fixtures@v0.6.0-filtered conformance/manifest.json@v0.6.0   recorded - authority cdbb79b1fbfd
  FRESH   fhgm-suite@0617626                     development/conformance/manifest.json@06176262f982 e41f05fd8bb8 e41f05fd8bb8  [draft, not acceptance]
base-carrier — 2 reference(s)
  FRESH   fhgm-base@v0.5.0                       fhgff3.json@v0.5.0     20ce320f5d70 20ce320f5d70  [draft, not acceptance]
          lag: pinned v0.5.0, current release is v0.6.0
  FRESH   fhgm-base@v0.6.0                       fhgff3.json@v0.6.0     1942be4cefc8 1942be4cefc8  [draft, not acceptance]
copied-tree — 1 reference(s)
  ABSENT  spec-examples-tree@unrecorded          (no provenance record) @ v0.6.0
summary: 32 FRESH, 0 DRIFT, 2 ABSENT, 2 NOT_A_FILE_PIN of 36
```

Every FHGM row resolves at the commit or tag its own row names, and the `v0.5.0`
base row carries the advisory lag line: it is a correct historical pin, one release
behind, and nothing re-points it automatically. The two `ABSENT` rows are the
declared holes above (`fhp.context.jsonld@unrecorded`, `spec-examples-tree@unrecorded`);
`fhgm-base@none` is gone because the axis it declared missing is now recorded.

The 25 released-contract rows are the seven `releases` entries of
`bioheaders/schemas/bundled.json` (FHR 1 / 2.0 / 2.1, FHP 1.0 / 1.1 / 1.2, FHGFF3
1.0 / 1.1 / 1.2), the three `current` copies, the FHR JSON-LD context and the three
`assess` contract data files, each resolved at the tag its registry entry names.
The five `ABSENT` rows are documented holes, reported rather than passed over:

* `fhp.context.jsonld@unrecorded` — the copy names no commit, so there is nothing
  to resolve it against. Recording one is a maintainer act.
* `fhp-fixtures@v0.6.0-filtered`, `fhgff3-fixtures@v0.6.0-filtered` — the toolkit
  vendors *filtered* per-format copies of the shared suite manifest, so no upstream
  file digest describes them. Their equality with `conformance/manifest.json` at
  `v0.6.0` is enforced fixture-file by fixture-file by
  `tests/{fhp,fhgff3}_test.py::test_fixtures_match_the_specification`, against the
  tag `.github/workflows/pytest.yaml:41` clones.
The 2026-11-16 measurement above listed a fifth `ABSENT` row, `fhgm-base@none`,
whose `no_pin_detail` said the toolkit held no FHGM reference of any kind. That hole
is now filled by dated rows rather than deleted: opening the FHGM lane
([FAIR-bioHeaders-Tools#135](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/135))
added six, all labelled `draft, not acceptance`, and the measured table below reports
them. Two carry no local copy **by declaration**, which is the same class of finding
as the rows above: `fhgm-base-registry@0617626` pins the owning repository's base
registry as provenance while the two released bases it names are vendored and pinned
in their own right, and `fhgm-suite@0617626` pins a manifest that is read from a
`FHGM_SPECIFICATION` checkout rather than copied in. Neither is a silent pass, and
neither turns a fresh digest into acceptance: FHGM has no released contract, no
`schemaVersion`, no registry row, no tag and no w3id alias, and rule V7 keeps it
that way until the shared publication PR lands.
* `spec-examples-tree@unrecorded` — the fifth class turned on this repository
  itself: the toolkit vendors **all 26 `examples/` files of tag `v0.6.0`
  byte-identically** (measured 2026-11-16: `git ls-tree -r v0.6.0 -- examples`
  against this checkout, 26/26 digests equal) and holds no copied-tree provenance
  record for them. Under the class's own rule — a consumer that vendors bytes with
  no record reports `ABSENT`, because absence is the finding, not a pass — that is
  a hole, and the row keeps it visible. Writing the record (or reclassifying the
  files) is a maintainer act.

Read any draft row together with
[CAPABILITY-MATRIX.md](CAPABILITY-MATRIX.md) and
[FHGM-DRAFT-LANE.md](FHGM-DRAFT-LANE.md): this command answers "is the byte I hold
still the byte they published at the revision I named?", and the matrix answers
"what can this toolkit do?" Neither may be read as the other. A `FRESH` FHGM row is
not support, not adoption and not release — and the matrix states the lane's
capability in its own grid rather than inferring it from a `FRESH` row here.

## The `copied-tree` class (FAIR-bioHeaders-Tools#163)

The four original classes all describe **one file per reference**. The fifth
class exists because the federation's largest measured divergence is not a file:
`FHGM-Specification` and `FHGFF3` each vendor a whole `header/` directory under
one `header/provenance.json` record (`source` plus `copied[]` entries of
`local`/`upstream`/`size`/`sha256`). A row's authority is the
(repository, revision, consumer-record) triple; per path the audit resolves the
**authority bytes at the revision the row names** and compares SHA-256 digests —
never sizes, because the measured case contains **eight files of identical
size and different digest**, the ordinary shape of an in-place value edit.

Three set axes go beyond what any per-file digest sweep can see:

* `missing_local` — the record lists a path with no bytes in the tree;
* `unrecorded_local` — a file inside the recorded `tree` that no `copied[]`
  entry claims and the row does not declare under `ignore` (consumer-authored
  prose must be *declared*, never inferred by a name heuristic); vendored bytes
  with no record at all produce `ABSENT` — absence is the finding, not a pass;
* `only_authority` — paths present when the authority's own tree is enumerated
  under a declared `prefixes` entry (`git ls-tree` in a `--checkout`, or a
  fixture walk; the HTTPS backend serves files, not listings, and says so).

`against_provenance` compares the consumer's recorded path set with a **second
consumer's record** and prints the paths present on only one side — the shape
of the motivating measurement, run 2026-11-16 against a local checkout of the
specification, with `--root` set to the workspace holding both consumers:

```
copied-tree — 3 reference(s)
  ABSENT  fhgm-header-tree@its-own-record        - @ main                    a copied tree of released material must be named by a tag, not 'main' (FAIR-bioHeaders-Specification#241 rule 1, applied by FAIR-bioHeaders-Tools#163)
  DRIFT   fhgm-header-tree@v0.6.0                header/provenance.json @ v0.6.0   39 record entries, 29 identical, 10 DRIFT-DIGEST (8 same-size), sibling record: 0 only here, 10 only there
      DRIFT-DIGEST fhgff3_linkml.yml authority f09249cfd2f4 local cc71178b8c6a recorded cc71178b8c6a (5527 vs 5391 bytes)
      DRIFT-DIGEST examples/fhgff3/annotation.fhgff3.gff3 authority 7754357bd228 local e8dab46b7d94 recorded e8dab46b7d94 (same size, different digest)
      ... (10 per-path DRIFT-DIGEST findings in total, then:)
      sibling record .../FHGFF3/header/provenance.json (49 entries): 0 only here, 10 only there
        only-there conformance/invalid/fhgff3-busco-lineage-trailing-dot.fhgff3.gff3
        ... (all 10 names printed)
          record pins main at bdcaecf759b5
  FRESH   fhgff3-header-tree@v0.6.0              header/provenance.json @ v0.6.0   49 record entries, 49 identical

summary: 1 FRESH, 1 DRIFT, 1 ABSENT of 3
```

Read that as the whole point of the class at once. The FHGM tree scores
29-identical / 10-drift against the released FHGFF3 material it models — while
passing its *own* parity lane, which verifies the copy against its own recorded
pin (a stale-but-faithful tree passes it: exactly why the cross-repo audit, not
the holder's parity check, must own this class). The model itself
(`fhgff3_linkml.yml`) differs at `5,391 B cc71178b…` vs `5,527 B f09249cf…`, and
ten files exist on the FHGFF3 side only — the digest facts and the set-shape
fact are both needed, and neither is expressible as one file reference. And
FHGM's own record (`ref: "main"` at `bdcaecf759b5…`) is **unusable as pinned**,
per rule 1: the audit refuses to score released tree material against a branch.
Note also what this gate does **not** become: reading a vendored model tree is
not a feature-row resolver — deciding the semantics of carrier-layer verdicts
stays `gff3-validator#31` and the suite's job (the FHGM-Specification#22
`K4`-vector split), not this module's.

The verdict stays advisory (`exit 0` without `--exit-on-drift`, `"wrote": []`
in JSON): **a tree check never refreshes a tree**. `FRESH`/`DRIFT`/`ABSENT`
count paths and name digests; moving a pin — or writing the missing provenance
record above — remains a dated human commit in the repository that holds it.

Released material is checked against **tags**; the tags are immutable, so a DRIFT on
a `v0.x.y` row means this repository's record is wrong, not that upstream moved.
`.github/workflows/pin-audit.yml` runs the command on a schedule and on demand.
Findings cannot fail it (the command exits 0 without `--exit-on-drift`); a crash
of the audit itself exits 2 and does, so an audit that did not run never looks
like a clean one.

## Draft output never reads as released (rule V7)

Every draft row carries `label: "draft, not acceptance"`, which is printed in the
text report, present in the JSON, and repeated in a closing line:

```
draft rows are draft, not acceptance, listed as the references they are: development
bytes at a commit, with no release tag, no w3id alias, no row in
schemas/versions.json and no acceptance implied (rule V7 of docs/SCHEMA-VERSIONS.md).
```

Reporting that FHT or FHGM bytes are fresh says nothing about whether they are
accepted. FHT and FHGM get no `schemaVersion` row, no `versions.json` entry, no w3id
alias and no support claim from anything in this module.

## Proving it can fail

The gate is only worth running if it can report a problem, so each state is
produced in `tests/pin_audit_test.py` from **real bytes in this checkout** —
`schemas/fhp-1.1.json` and `schemas/fhp-1.2.json` are the released `v0.5.0` and
`v0.6.0` bytes, verified against the tags with `git show` and re-read over HTTPS.

| case | input | report |
| --- | --- | --- |
| `test_a_wrong_recorded_digest_reports_drift` | one recorded digest changed from `92a0b3cb…` to `12a0b3cb…`, mutation proved non-vacuous by comparing the written table against the shipped one | `DRIFT`, and exit status stays 0 |
| `test_uniformly_stale_tree_is_drift_not_fresh` | #241(a): the `v0.5.0` bytes *and* the `v0.5.0` digest, asked of the `v0.6.0` authority | `DRIFT` with `local status: MATCHES RECORD` — the tree agrees with itself and is still wrong |
| same test, second half | the same record asked of the `v0.5.0` authority it names | `FRESH` |
| `test_drift_can_also_be_a_size_change_under_a_matching_digest` | recorded `bytes` set to 1, digest left correct | `DRIFT` on the size |
| `test_absent_when_the_named_revision_has_no_bytes` | `revision: v9.9.9` | `ABSENT`, `authority unavailable` |
| `test_released_class_naming_a_branch_is_not_scored` | a `released-contract` row at `main` | `ABSENT`, rule 1 quoted, no comparison attempted |
| `test_base_carrier_lag_is_reported_as_advisory_text` | #241(b): a base pin at `v0.5.0` while `current_release` is `v0.6.0` | `FRESH` **plus** `lag: pinned v0.5.0, current release is v0.6.0` |
| `test_a_permissive_backend_fails_its_control` | an authority that answers the nonsense path | `ABSENT`, `not trustworthy` — a green-looking verdict is withheld from a backend that cannot produce a negative |
| `test_the_gate_never_writes_a_pin` | any run | table, vendored schemas and authority bytes all byte-identical afterwards; JSON reports `"wrote": []` |

Live, against the real authority, the mutation and both halves of #241(a) were run
on 2026-11-15 (`cmp` reported the mutated table differs from the shipped one at byte
1327, and the shipped file was never rewritten):

```
  DRIFT   fhp-1.2@v0.6.0        fhp.json@v0.6.0   recorded 12a0b3cbcfe6 authority 92a0b3cbcfe6
          detail: recorded 12a0b3cbcfe69939… != authority 92a0b3cbcfe69939…
          local status: DIFFERS FROM RECORD
  DRIFT   241a-worked-drift     fhp.json@v0.6.0   recorded 2409739d4a22 authority 92a0b3cbcfe6
          local status: MATCHES RECORD
  FRESH   241a-worked-fresh     fhp.json@v0.5.0   2409739d4a22 2409739d4a22
summary: 1 FRESH, 2 DRIFT, 0 ABSENT of 3
```

## The conflict-marker probe

`--conflicts PATH` runs `git grep -I -n -e '^<<<<<<< ' -e '^>>>>>>> '` in each
repository and reports `NONE` / `MARKERS` / `SKIPPED`. The precedent is concrete:
`FHP-Specification/CHANGELOG.md` carried an unresolved merge conflict on `main` for
about three and a half weeks — introduced by `5cf0613` (PR #12, merged 2026-10-22)
and closed only by that repository's #34 — and a scan of all fourteen federation
repositories found exactly one file with one occurrence and **no gate anywhere that
looked for conflict markers at all**. One grep is the cheapest integrity probe
available, so the gate carries it. A bare `=======` line is deliberately not probed:
in Markdown and setext documentation it is a heading underline, and matching it would
make the probe noise. `test_conflict_probe_is_clean_before_and_loud_after` proves the
probe is non-vacuous by writing both arms into a committed file and requiring two
hits; `test_conflict_probe_ignores_a_sext_heading` proves the pattern is not
over-broad.

## Running it

```bash
bioheaders-pin-audit                       # advisory text table, exit 0
bioheaders-pin-audit --json                # machine-readable, "wrote": []
bioheaders-pin-audit --class base-carrier  # one class (or --only fhp for an id substring)
bioheaders-pin-audit --offline             # resolve nothing, report why
bioheaders-pin-audit --checkout FAIR-bioHeaders/FAIR-bioHeaders-Specification=/path/to/clone
bioheaders-pin-audit --fixture-dir /path/to/dir   # offline, <repo>@<revision>/<path>
bioheaders-pin-audit --conflicts . --conflicts ../FHP-Specification
bioheaders-pin-audit --exit-on-drift       # opt-in, for a consumer that wants to gate
```

`--checkout` uses `git show <revision>:<path>`, so the local clone must actually
contain the revision named by each row; a missing revision is `ABSENT`, never a
guess. `--root` controls where the table's `local` paths resolve, and is what makes
the report honest about a *uniformly* stale tree.

## Out of scope for this gate

`#241` asks for more than one repository can deliver on its own, and this PR does
not claim otherwise:

* acceptance 1 for the **whole** federation (the enumeration of
  `FAIR-bioHeaders-Specification`, the five type repositories, `FHGM-Specification`,
  the four `Tools-*` libraries and this toolkit) — this PR enumerates the toolkit's
  rows;
* acceptance 2's **per-repository wiring** of the scheduled advisory run, which
  belongs in each consumer repository's CI;
* acceptance 4 (`#241(a)`'s fix in `FHP-Specification`: advance `fhp_linkml.yml` and
  regenerate, never paste bytes) — done in that repository's #32, not here;
* acceptance 5 (`#241(b)`'s FHGM base-pin decision: advance to FHGFF3 1.2 / `v0.6.0`
  before `v0.8.0`, or document the intended scope) — subsequently dispositioned
  as dual-base selection and implemented in FHGM-Specification#17; this reporting
  command does not adopt or replace that decision.

Container and package-version references (`Dockerfile:17` pins a base image by
digest; `release.yml` and `container.yml` pin released toolkit bytes; `plugins/` and
`galaxy/` version tokens follow the package version) are recorded in the table's
`out_of_scope` list with the reason, because they are not contract bytes.
