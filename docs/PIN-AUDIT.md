# Cross-repo pin audit (`bioheaders-pin-audit`)

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
   (`ABSENT` with the rule quoted) instead of being silently compared.
2. **Contract pin, suite pin and base pin are three references.** They move
   independently: `FHT-Specification` `fht.json` is byte-identical
   (`59ad9641adcb0e55…`, 29,430 B) at the contract pin `226f923c…` and at the later
   suite commit `24d3b033…`, while `conformance/manifest.json` moved from
   `d9025104675e69b5…` (54,216 B, 65 `fht-fasta` vectors) at `226f923c…` to
   `9b07179497bdc724…` (56,250 B, 66 vectors) at `24d3b033…`. All six digests were
   measured on 2026-11-15 from `git show` and re-read over HTTPS at the same
   revisions.

## The four reference classes

| class | authority | revision kind | toolkit rows |
| --- | --- | --- | --- |
| `released-contract` | a specification release's published bytes | **tag** | 25 |
| `draft-contract` | the owning development repository at a recorded commit | commit | 1 |
| `conformance-suite` | the owning repository's `conformance/manifest.json` at a recorded revision | commit / tag | 3 |
| `base-carrier` | the released schema a draft embeds, at the tag that draft pins | **tag** | 1 |

The table itself is data, not prose: `bioheaders/pins.json`, one row per reference,
each with `repository` / `revision` / `revision_kind` / `path` (the authority),
`local` (this repository's copy), `sha256` / `bytes` (what this repository asserts),
plus `class`, `label`, `note` and `recorded_in` (where the assertion lives). Every
digest in it was measured from the file it names, and
`tests/pin_audit_test.py::test_shipped_digests_are_the_bytes_in_this_checkout`
re-measures all of them on every test run, so an invented or mistyped value cannot
survive.

## What the toolkit holds (measured 2026-11-15)

The audit resolves 26 of the 30 rows and reports **26 FRESH, 0 DRIFT, 4 ABSENT**,
over HTTPS with a negative control on each backend:

```
$ bioheaders-pin-audit
Cross-repo pin audit (FAIR-bioHeaders-Specification#241) — table version 1, 30 references.
  backend https FAIR-bioHeaders/FAIR-bioHeaders-Specification: negative control 404 as expected at 7 revision(s); e.g. GET https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/v0.3.0/pin-audit-404-control.json -> 404
  backend https FAIR-bioHeaders/FHT-Specification: negative control 404 as expected at 2 revision(s); e.g. GET https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/226f923c28b680edb3c546e99a751482d06aef1a/pin-audit-404-control.json -> 404

released-contract — 25 reference(s)
  FRESH   fhr-1@v0.3.0                           fhr.json@v0.3.0                          e3d3843e1a16 e3d3843e1a16
  ...
  FRESH   fhp-1.2@v0.6.0                         fhp.json@v0.6.0                          92a0b3cbcfe6 92a0b3cbcfe6
  FRESH   fhgff3-1.2@v0.6.0                      fhgff3.json@v0.6.0                       1942be4cefc8 1942be4cefc8
  ABSENT  fhp.context.jsonld@unrecorded          jsonld/fhp.context.jsonld@-              recorded - authority -
          detail: no upstream revision recorded: ...
summary: 26 FRESH, 0 DRIFT, 4 ABSENT of 30
advisory only: FRESH/DRIFT/ABSENT change no file and no pin. Re-pinning is a deliberate, dated commit in the repository that holds the pin.
```

The 25 released-contract rows are the seven `releases` entries of
`bioheaders/schemas/bundled.json` (FHR 1 / 2.0 / 2.1, FHP 1.0 / 1.1 / 1.2, FHGFF3
1.0 / 1.1 / 1.2), the three `current` copies, the FHR JSON-LD context and the three
`assess` contract data files, each resolved at the tag its registry entry names.
The four `ABSENT` rows are documented holes, reported rather than passed over:

* `fhp.context.jsonld@unrecorded` — the copy names no commit, so there is nothing
  to resolve it against. Recording one is a maintainer act.
* `fhp-fixtures@v0.6.0-filtered`, `fhgff3-fixtures@v0.6.0-filtered` — the toolkit
  vendors *filtered* per-format copies of the shared suite manifest, so no upstream
  file digest describes them. Their equality with `conformance/manifest.json` at
  `v0.6.0` is enforced fixture-file by fixture-file by
  `tests/{fhp,fhgff3}_test.py::test_fixtures_match_the_specification`, against the
  tag `.github/workflows/pytest.yaml:41` clones.
* `fhgm-base@none` — the toolkit holds **no FHGM reference at all**: no vendored
  FHGM draft, and therefore no FHGFF3 base/carrier pin of its own. Opening that lane
  is [FAIR-bioHeaders-Tools#135](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/issues/135);
  the base pin #241(b) is about lives in FHGM-Specification. The class is
  implemented and tested here so that lane has a gate to plug into, and the row
  keeps the missing axis visible instead of silently absent.

Released material is checked against **tags**; the tags are immutable, so a DRIFT on
a `v0.x.y` row means this repository's record is wrong, not that upstream moved.
`.github/workflows/pin-audit.yml` runs the command on a schedule and on demand,
`continue-on-error: true`, and its steps cannot fail the branch.

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
  before `v0.8.0`, or document that the draft targets 1.1) — a maintainer decision in
  FHGM-Specification.

Container and package-version references (`Dockerfile:17` pins a base image by
digest; `release.yml` and `container.yml` pin released toolkit bytes; `plugins/` and
`galaxy/` version tokens follow the package version) are recorded in the table's
`out_of_scope` list with the reason, because they are not contract bytes.
