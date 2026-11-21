> Historical workplan and dated evidence. Current contributor policy is in
> [AGENTS.md](../AGENTS.md): another actual model reviews every PR and only a
> human merges. These older receipts never authorize agent merging. Current
> released behavior is described in [Getting started](GETTING-STARTED.md).

# FHT selection — published support and historical V7 design

Specification v0.7.0 has now published FHT 1.0. Toolkit 0.13.1 bundles
its immutable tag and enables shared publication citations by default. See
[actual publication provenance](FHT-PUBLICATION-CANDIDATE.md) and the generated
[capability matrix](CAPABILITY-MATRIX.md). External redirect deployment remains
independent. The owning raw-main V7 lane stays separately gated, including its
accepted 93-vector historical suite and old fixture bytes. FHT gains no JSON-LD,
context or DCMI profile. Toolkit publication is still pending.

The following text is the archived prepublication design and measurements; its
present-tense statements describe that earlier stage, not the current bundle.

## Archived prepublication design

Current Round 15 state supersedes historical pin/support measurements below:
accepted owning commit `4ddda69cbcbb3920a06ab657173c0198672cd7bf`, 93 vectors,
C1 arithmetic and reviewed typed HTML implemented behind the existing gate.
JSON-LD remains unsupported. See [current evidence](ROUND15-READINESS.md).

> **Status: preparation, not publication.** This document and the gated
> prototype in this branch prepare FAIR-bioHeaders-Tools support for the FHT
> (transcriptome) header, per the acceptance list of
> [FHT-Specification#9](https://github.com/FAIR-bioHeaders/FHT-Specification/issues/9).
> FHT has **no released contract**: it appears nowhere in the shared
> specification's `schemas/versions.json`, has no release tag and no w3id alias
> (verified against `https://w3id.org/fair-bioheaders/fht/…`, which does not
> resolve, and against FAIR-bioHeaders-Specification `main`, which carries only
> `fhr.json`, `fhp.json` and `fhgff3.json`). Merging is not releasing: the FHT
> contract and its 65 conformance vectors are merged on FHT-Specification
> `main` (PRs #21 and #29), but publication is a maintainer action tracked in
> FHT-Specification#10 and FAIR-bioHeaders-Specification#107 ("lane F" of the
> #55 chain). Nothing here publishes, adopts or releases anything.

## 1. Where FHT citations land today

`bioheaders/selection.py` implements the shared rules V1–V6 of
FAIR-bioHeaders-Specification `docs/SCHEMA-VERSIONS.md`. Its `RAW` pattern
recognises only the shared specification repository (under either of its
names) and only the three files `fhr.json`, `fhp.json`, `fhgff3.json`. A record
citing the FHT draft — by construction it must, because the draft contract
closes its own `schema` field (rule C2 of the FHT suite — the suite's provisional
rule labels `T1`–`T3` were renamed to `C1`–`C3` by FHT-Specification#38) to

```text
https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/(main|vX.Y.Z)/fht.json
https://w3id.org/fair-bioheaders/fht/vX.Y.Z
```

— matches no rule, so **rule V5 reads it as FHR** against the current FHR
schema. Since FAIR-bioHeaders-Tools#137 the silent fallback is at least
legible: `selection.near_miss_warning` prints

```text
FHR: warning: schema …FHT-Specification/main/fht.json is not a FAIR-bioHeaders
schema URL; read as FHR, not FHT, against the current schema (rule V5)
```

and validation then fails, because an FHT record has no `genome`, no
`accessionID` requirement satisfied, and carries FHT-only fields the closed FHR
schema rejects. `bioheaders assess` already names FHT separately
(`assess/conformance.py` reports `header_type: "FHT"`, `not_assessed`,
`unsupported-header-type`). That whole picture is correct under the published
rules and stays the **default behaviour** of this branch. With the lane open,
assess validates an FHT record against the bundled draft, as validate and verify
do.

## 2. What must change for FHT support

1. **A registry entry for the development draft.** `schemas/bundled.json`
   grows a third section beside `current` and `releases`:

   ```json
   "drafts": {
     "FHT": {
       "status": "draft",
       "file": "schemas/fht-draft.json",
       "schemaVersion": "1.0",
       "citation": "https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json",
       "source": "FHT-Specification (development repository; no released contract, …)",
       "revision": "<40-char commit of FHT-Specification main>",
       "retrieved": "YYYY-MM-DD",
       "sha256": "<digest of the bundled bytes>",
       "enable": "BIOHEADERS_EXPERIMENTAL_FHT=1 (opt-in only)"
     }
   }
   ```

   Distinct from both existing sections: `current` entries are raw-main
   *publication* selections per V1 and must stay byte-identical to shared-spec
   `main`; `releases` entries are frozen published snapshots per V2/V3. A draft
   is neither: it is one named revision of a development repository, and the
   registry says so (source/revision/refresh provenance, as FHT-Specification#9
   requires for any eventual bundling). `pyproject.toml` already packages
   `bioheaders/schemas/*.json`, so the draft ships with the distribution.
   **Refresh discipline:** the draft copy is only ever replaced by re-running
   the byte-exact copy from a named FHT-Specification commit, updating
   `revision`, `retrieved` and `sha256` together (`tests/fht_test.py` checks
   the digest against the file on disk). It never rides a `current` refresh.

2. **Selection must return FHT for the raw-main draft URL — only when draft
   support is enabled.** This is the whole coordination question; see §4.

3. **The family table:** `cli.validate_header_family` admits `FHT` for FASTA
   (`;~`) only. FHT is a FASTA-only contract (`fht.json` has no GFA/GFF3
   story), and GFA/GFF3 stay exactly as they are.

4. **The rest of the FASTA pipeline needs no change** — verified, not hoped:
   `;~` block reading/writing (`fhr.input_fasta`/`output_fasta`),
   `SequenceScan`/`checksum` (exact bytes, checksum-line exclusion, CRLF,
   gzip/BGZF, stdin/pipes), `combine`, `strip`, `verify`, `verify-links`
   (matched / not matched / not checked for `derivedFrom` FHR parents, C3),
   `validate`, `convert` to/from YAML/JSON, required-value and link-scheme
   warnings, R15 extension fields and R11 escaping all key off
   `schema_for(record)` and the generic header text. The gated prototype
   passes **all 65 vectors** of the FHT-Specification suite (see §6). That
   count is the suite as it stood when this was written; §6.2 records it moving
   to 66 and then 68; §6.3 records the approved 72-vector pin, and
   [CAPABILITY-MATRIX.md](CAPABILITY-MATRIX.md) is where the current measured
   shape is published, per operation and per serialization, with the draft-lane
   citation labelled as the opt-in it is.

5. **Forms without a reviewed FHT binding must be refused, not stretched.**
   There is no FHT JSON-LD context and no FHT microdata binding (#9 explicitly:
   demonstrate or document-unsupported; #11 owns typed HTML). Following the
   FHGFF3/JSON-LD precedent (#104/#141): `output_jsonld`, `output_microdata`
   and the FHR-itemtype microdata *reader* raise a clear "not available for
   FHT" error whenever a record selects FHT — an FHR-itemtype document citing
   FHT is rejected, never silently read as FHR, and an FHT record is never
   written under the FHR identity. JSON-LD *input* rejects a decoded FHT record
   when the draft lane is enabled, even if it carries the bundled FHR context.

6. **Warnings and labels:** every draft selection prints
   `FHT: warning: … selects the bundled FHT draft contract (commit <full sha>,
   sha256 <digest> of those bytes) (development only,
   not a released schema …)` on stderr (via `schema_warnings`) and emits
   `ExperimentalDraftWarning` to library callers — the
   `fhgff3_microdata.ExperimentalMicrodataWarning` precedent from #141,
   doubled because the *contract itself*, not just a serialization, is draft.
   `selection.supported("FHT")` reports `main (draft, experimental)`; there is
   deliberately no `FHT` key in `current.files`.

7. **Deferred by design** (each needs its own PR or decision, none is silently
   skipped): default-on selection (blocked on §4); the
   `--type`-aware command help and README/plugin/Galaxy surfaces (update at
   release, not at prep); `verify-links` for FHT *as a parent* of future types;
   Nextflow (FHR-Nextflow#7) and website (#15) coverage belong to their
   repositories per #9.

## 3. How draft support is enabled — options

| Option | Pros | Cons |
| --- | --- | --- |
| **(a) Environment variable** `BIOHEADERS_EXPERIMENTAL_FHT=1` — **implemented in the prototype** | One decision per process, so *selection* is consistent across the whole pipeline (`fhr_validate()` has no parameters; selection happens deep inside `schema_for`); works identically for CLI, library, installed wheel and container; trivially wired into the conformance run (§6); default is untouched byte-for-byte | Invisible in `--help`; a user can forget it is set (mitigated: every draft run warns loudly); "library behaviour from environment" is a pattern the toolkit otherwise only uses in tests |
| **(b) Per-command flag** (`--draft-fht` on combine/verify/strip/validate/convert/verify-links) | Discoverable, explicit per invocation | Must be plumbed into every command *and* into library calls that select schemas (`fhr_validate`, `assess`), or CLI and library diverge; the eight `fhr-*` entry points share `_combine`/`_verify` with the subcommands and would need the flag or an equivalent global; forgetting it on one step of a multi-step workflow gives contradictory results between steps |
| **(c) `--type fht`** on sequence commands | Reuses existing `--type` plumbing | Wrong semantics: `--type` names the *file format*, and `verify`/`strip` must read the family **from the file's bytes** — a caller-chosen family would let `verify` check an FHR file against FHT rules and would make the *selection URL* caller-overridable, which rules V1–V5 deliberately are not |
| **(d) Separate `bioheaders fht …` subcommand tree or second tool | Obvious isolation | Contradicts #9's own boundary ("the single family toolkit; do not silently revive a second implementation") and duplicates the pipeline for no behavior gain |
| **(e) Configuration file** | Persistent, discoverable | The toolkit has no config machinery; building one for a draft preview is the speculative framework AGENTS.md warns against |

Recommendation: **(a) for the prep/preview stage, exactly as prototyped.** If
maintainers want CLI discoverability later, layer **(b)** on top as sugar that
sets the same gate (one `add_argument` plus one `os.environ` write per command
is enough — the decision stays process-wide); never **(c)**.

## 4. The V5 / SCHEMA-VERSIONS question (for the spec maintainers)

**Question, precisely.** Recognizing
`https://raw.githubusercontent.com/FAIR-bioHeaders/FHT-Specification/main/fht.json`
as a *schema-selection* URL changes the effective meaning of published rule V5
("Any other value … is **FHR**, checked against the current FHR schema") for
every FHT record written since the draft merged, and requires the registry
concept of a *type-repository draft* — a selectable schema that is not any
release's and not `main` of the shared publication tree — to be added to
`docs/SCHEMA-VERSIONS.md` and given a shape in `schemas/versions.json`
(today's `files`/`w3id` maps are three-type, shared-repo only). Is that a
SCHEMA-VERSIONS change requiring shared-spec coordination, or implementable
consumer intelligence like the V6 carve-out and the #125/#137 near-miss
warning?

The two existing counterexamples cut against "mere consumer intelligence":
V6 changed *which release* an existing V1 URL selects for one legacy shape,
and the near-miss warning changes *no selection at all*. The FHT lane would
add a new (repo, file) selection tuple with a fourth header type — V1's
opening sentence ("`<file>` is `fhr.json`, `fhp.json` or `fhgff3.json`") would
stop being true. Meanwhile the FHT conformance suite already *assumes* the
change: its README applies "V1/V4" to transcriptome files, and the suite's 21+4
valid vectors **fail** under literal published V5 (they are rejected when read
as FHR). The contradiction is normative, not implementation slippage:
FHT-Specification's merged contract and the shared selection rules currently
disagree about what a valid FHT file is, and a toolkit choice between them is
exactly the kind of cross-implementation divergence (toolkit vs
gff3-validator vs website, which all follow SCHEMA-VERSIONS) that V1–V6 exist
to prevent. The plan's own gate — "FHT contract merge ≠ publication" — points
the same way: the publication step is shared-spec work, so the *default*
recognition is too.

**Recommendation.** Treat it as a shared-spec coordination item, and ship the
preview strictly opt-in:

1. Open the coordination issue in FAIR-bioHeaders-Specification (referencing
   #107 lane F and FHT-Specification#9/#10) proposing an explicit **draft
   lane** rule — e.g. **V7**: *A raw-main URL of a type-development repository
   for a header type with no released contract MAY be recognized by readers
   that explicitly enable draft support; with draft support off, rule V5
   applies unchanged. Release-tag and w3id forms of such a URL are
   unsupported-version once the type is published (V2/V3/V4) and near-miss
   until then, and no draft selection may be silent: readers must warn that
   the contract is unreleased.* The issue should decide between (i) documenting
   that opt-in preview as *toolkit behaviour outside the V-rules* (what this
   branch does — lawful under "readers may do more than the minimum, as long
   as published semantics never change silently"), and (ii) amending V1 and
   `versions.json` (e.g. a `drafts` map) so the behaviour becomes *published*
   selection semantics. **(i) now, (ii) at FHT publication is the cleanest
   sequence**: publication already has its own cycle, and option (i) keeps
   every already-published byte immutable.
2. Keep this prototype default-off, loud (stderr warning +
   `ExperimentalDraftWarning`), exit-code-neutral, and reversible by deleting
   the gate; it claims no spec conformance and cites this document from every
   user-visible message.
3. Do **not** touch the near-miss FHT entries: with the gate off they are the
   published behavior, and with the gate on they still correctly fire for the
   `w3id …/fht/vX.Y.Z` and FHT tag URL forms, which name URLs that do not
   exist yet.
4. At publication (a shared release whose `versions.json` lists FHT): add FHT
   to `TYPES`/`RAW`/`W3ID` properly per V1–V3, move `schemas/fht-draft.json`
   to the release snapshot layout, freeze the draft entry into `releases`,
   retire the environment gate in a clearly labelled commit, and only then
   make the conformance suite an unconditional CI gate.

## 5. Integration-point map (file / function level)

| Integration point | Location | State in this branch |
| --- | --- | --- |
| Draft URL pattern, gate, warning text | `bioheaders/selection.py`: `FHT_DRAFT_RAW`, `DRAFT_ENV`, `draft_support_enabled()`, `ExperimentalDraftWarning`, `draft_warning()`, `draft_entry()`, `_draft_file()`, `_warn_draft()` | implemented (gated) |
| Selection rules | `selection.parse()` (draft branch), `selection._file()` (FHT branch + warning), `supported("FHT")` | implemented (gated) |
| Registry + bundled bytes | `bioheaders/schemas/bundled.json` (`drafts.FHT`, provenance fields), `bioheaders/schemas/fht-draft.json` (byte copy of FHT-Spec `main@226f923`, sha256-pinned) | implemented |
| Schema-selection warnings | `bioheaders/__init__.py`: `schema_warnings()` appends the draft notice; `header_type()` docstrings | implemented |
| Family table | `bioheaders/cli.py`: `validate_header_family()` — FASTA only, gate-gated | implemented |
| Unbound forms | `__init__.py`: `fhr.output_jsonld`, `fhr.output_microdata`, `fhr.input_microdata`; `cli.py`: `_convert` JSON-LD guard | implemented (refusal) |
| FASTA pipeline (`combine`/`verify`/`strip`/checksum/scan/gzip/pipes) | `cli.py` `combined_header`, `SequenceScan`, `strip_header`; `__init__.py` `output_fasta`/`input_fasta` | **no changes needed** — verified by tests |
| verify-links (C3) | `cli.py` `_parent`, `_verify_links` | no changes needed — verified (matched/not matched/not checked, FHR and FHT parents) |
| assess | `assess/conformance.py` (`FHT_URL`) | lane closed: `not_assessed` (`unsupported-header-type`); lane open: validated against the bundled draft like validate/verify, `schema_used` naming the pinned commit, with the V7 draft warning |
| Conformance vectors | `tests/fht_conformance_test.py` | consumer stub, auto-skipped, proven green (§6) |
| Unit/regression tests | `tests/fht_test.py` (18 tests) | implemented |
| Docs/help/plugin/Galaxy surfaces | `README.md`, `cli.py` help strings, `plugins/`, `galaxy/`, site | deferred to the release PR (this is prep) |

## 6. Fixture consumption (the 65-vector suite)

FHT-Specification PR #29 merged as `b9ad19a` on 2026-11-12: 65 byte-exact
`fht-fasta` vectors plus manifest and parent fixtures now live on that
repository's `main`. This branch copies **no** fixture bytes into the toolkit.
`tests/fht_conformance_test.py` is the complete consumer: it reads
`<FHT-Specification>/conformance/manifest.json` (path from the
`FHT_SPECIFICATION` environment variable, falling back to a sibling checkout,
the same pattern `tests/fhp_test.py` uses for the shared suite), runs every
vector through `bioheaders verify` / `verify-links` under the open gate, and
asserts the manifest's `expected`, `checksum`, `selfChecksum`
(matches/broken/unreachable) and `parentLink` (checked-pass / checked-fail /
unchecked) semantics — including the `fht-fasta-parent-mismatched` subtlety
that a C3 failure is *not* a `verify` failure.

Provenance of the verification run recorded on 2026-11-12: vectors materialised
read-only from `FHT-Specification origin/main` (`git archive`, nothing
extracted into this repository); result **65/65 pass** (70 test items pass, 60
per-vector parent-link items skip where the manifest records no parent).

Command:

```bash
BIOHEADERS_EXPERIMENTAL_FHT=1 \
FHT_SPECIFICATION=/path/to/FHT-Specification \
poetry run pytest tests/fht_conformance_test.py
```

Refresh 2026-11-14 (step 2 of §7): FHT-Specification PR #34 merged as
`226f923`, widening the draft `completeness.lineageDataset` pattern to dotted
BUSCO dataset versions per shared #170. `fht-draft.json`, `revision`,
`retrieved` and `sha256` were refreshed together from the raw bytes of that
commit, and the suite above was re-run read-only against the same revision:
**65/65 vectors pass** (70 test items pass, 60 per-vector parent-link items
skip where the manifest records no parent), Python 3.13.16. The paired
re-pin of the shared repository's CEDAR draft snapshot is the coordinated
FAIR-bioHeaders-Specification PR cross-linked in the PR that carries this
refresh. No release-shape change: FHT stays an opt-in draft (rule V7).

### 6.1 Pin audit of 2026-11-15 (`drafts.FHT`, FAIR-bioHeaders-Tools#153)

A pilot run reported the bundled FHT draft pin as stale (`11c69d66…` at
`b9ad19a6…` against live `59ad9641…`, differing "only in the BUSCO
`lineageDataset` pattern"). Re-measured on 2026-11-15 against `main` and the
released wheel, with the vendored file and the registry text checked
separately:

| Reference | Revision | Recorded | Measured | State |
| --- | --- | --- | --- | --- |
| `main` `bioheaders/schemas/bundled.json → drafts.FHT` | `226f923c28b680ed…` | `59ad9641adcb0e55…` | `59ad9641adcb0e55…` (29,430 B) at `226f923c`, at `origin/main` `6e5af27a`, and in the vendored `schemas/fht-draft.json` — all three byte-identical (`cmp`) | **fresh** |
| `origin/main` of FHT-Specification (`fht.json`) | `6e5af27af730147c…` | — | `59ad9641adcb0e55…` (29,430 B) | equals the pin |
| `main` `drafts.FHT.suite` (added by this PR) | `24d3b033ab951ef7…` | `9b07179497bdc724…` (56,250 B, 66 `fht-fasta` vectors) | same at `24d3b03`, at `origin/main` `6e5af27a`, and in the scored checkout (`cmp`) | **fresh as measured; superseded later the same day by §6.2** |
| released wheel `fair-bioheaders 0.11.0` | `b9ad19a62772092e…` | `11c69d6647736695…` (29,199 B) | `11c69d6647736695…` in `fair_bioheaders-0.11.0-py3-none-any.whl` (sha256 `c89aa572…`) | **stale, by design** |
| local checkout `FAIR-bioHeaders-Tools` (this workspace, `c8582bd`) | `b9ad19a62772092e…` | `11c69d6647736695…` | matches its own bytes | pre-`fdc9677` branch, not `main` |

So the reported digests are exactly the **pre-#154 state**: `fdc9677` (PR #154,
merged 2026-11-14) already refreshed `main`, and the two places that still carry
`11c69d66…` are the immutable 0.11.0 release and a stale local checkout. Nothing
was re-pinned here for the contract axis; the pin moved on 2026-11-14 by its own
dated commit.

**The released wheel is a decision, not a fix.** `0.11.0` still answers an
opt-in FHT citation with the `b9ad19a` draft bytes, so an FHT record citing
`…/main/fht.json` and carrying a dotted lineage (`enterobacterales_odb12.2`) is
rejected by the released toolkit and accepted by `main`. The pattern difference
is the whole semantic difference: `^[a-z0-9_]+_odb[0-9]+$` became
`^[a-z0-9_]+_odb[0-9]+(\.[0-9]+)*$`, with three description strings for the same
field (4 hunks in `git diff b9ad19a 226f923 -- fht.json`). Verified by running,
not reasoning: the same `fht-fasta-rich` record validated with
`jsonschema.Draft202012Validator` against both byte sets is rejected only by the
old bytes, and the 66-vector suite scored 72 passed / 60 skipped under **both**
byte sets — no vector changes verdict, because the suite's only `completeness`
vector uses the undotted `primates_odb10`. Releases are immutable and shared CI
pins released toolkit bytes, so closing this needs the next toolkit release; the
choice (release now vs. let the next scheduled release carry it) is a maintainer
act (FAIR-bioHeaders-Tools#155).

**Which axes the recorded digests belong to, and who reads them.** `drafts.FHT
.sha256` is the **contract** axis (the `fht.json` bytes at a commit); the digest
added here (`drafts.FHT.suite.sha256`) is the **suite** axis
(`conformance/manifest.json` at a suite commit) — they are not interchangeable,
and the toolkit had the first and no second. Readers: `selection.py` consumes
only `status` and `file` and never reads either digest, so the contract digest
had exactly one reader (`tests/fht_test.py`), and the suite axis had none —
`tests/fht_conformance_test.py` scored whatever manifest its `FHT_SPECIFICATION`
path happened to hold, which is the FAIR-bioHeaders-Specification#241 `suiteCommit`
failure mode. `test_suite_manifest_matches_pin` gives the suite axis a reader.
The toolkit holds **no FHGM reference at all** (nothing pins the FHGM draft or
its FHGFF3 base/carrier schema; that is the open FAIR-bioHeaders-Tools#135), so
`base-carrier` reporting for FHGM is covered by the #241 gate's tests rather than
by a toolkit pin.

### 6.2 Refresh of 2026-11-15, later the same day: the suite pin moved, the contract pin did not

`FHT-Specification#46` merged at 2026-11-16T00:25:37Z as
`7503b26423296ba09357de66995ca3c9508306af` ("rule accountability, gzip stream
cases, and the named-toolkit lane", refs its #8) — about twenty minutes after the
merge of the PR that recorded the §6.1 values. This section supersedes the **suite**
row of §6.1; §6.1 stands as the measurement it was, dated.

| reference | revision | digest | size | `fht-fasta` vectors | state |
| --- | --- | --- | --- | --- | --- |
| `fht.json` (contract) | `226f923c…`, still the pin | `59ad9641adcb0e55…` | 29,430 B | — | unchanged: `fht.json` is also `59ad9641…` at `7503b264`, so **no contract byte moves** |
| `conformance/manifest.json` (suite) | `24d3b033…` (the §6.1 value) | `9b07179497bdc724…` | 56,250 B | 66 | **behind live `main`** |
| `conformance/manifest.json` (suite) | `7503b264…` (= live `main`) | `ab72fc985a2629df…` | 59,791 B | 68 | the new pin |

Both readings are `git show <rev>:<path>` re-read over HTTPS at the same revision
and `cmp`-verified, `curl` with no `-L`, each with a nonsense-path 404 control. The
manifest delta is additive: `+fht-fasta-gzip-multimember` (valid, R1) and
`+fht-fasta-gzip-sequence-tampered` (invalid, R3); nothing removed, and no
pre-existing vector entry changed any field (compared key by key).

Scored, not reasoned — the vendored contract bytes stay at `59ad9641…` and only the
checked-out suite revision changes:

| suite revision scored | result |
| --- | --- |
| `7503b264` (the new pin) | **75 passed, 62 skipped** — green, including both new vectors and `test_suite_manifest_matches_pin` |
| `24d3b033` (the old pin) | **1 failed, 72 passed, 60 skipped** — the pin test, naming measured `9b071794…`/56,250 B/66 against pinned `ab72fc98…`/59,791 B/68 |

So the guard added in §6.1 was right inside its first hour: it refused to let a pass
be quoted for bytes nobody had recorded, and turned an unnoticed upstream merge into
a dated, checkable finding. `drafts.FHT.suite` now names `7503b264…`; the contract
row is untouched.

Two lessons from this refresh for the advisory freshness reporting discussed in
[shared #241](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/241):

1. **A digest, never a count.** Measured the same day,
   `FHGM-Specification/development/conformance/manifest.json` moved from
   `31f14f022ff08581…` (35,269 B) at its #15 `ac3d37b3` to `5620f00cbb4bcb4b…`
   (36,001 B) at its #17 `5d15ccc1` with **31 vectors and identical `expected`
   outcomes in both** (`cmp`: differs from byte 846). "The manifest is present and
   says 31" reports FRESH against the wrong bytes. The assertion order is digest,
   then size, then count, and `tests/fht_conformance_test.py` now asserts all three.
2. **Input integrity is not live freshness.** The conformance test checks the
   supplied checkout against the recorded pin; if both stay at `24d3b033`, it
   still passes after upstream `main` moves. Detecting that drift requires a
   separate advisory `live` comparison for draft and suite rows against the owning
   repository's default branch. This PR does not add that comparison; released
   rows must continue to compare against their named tags, not `main`.

**FHGM stays unpinned, deliberately.** The toolkit holds no FHGM reference (no
vendored draft, no base/carrier pin — that lane is #135), and
`FHGM-Specification#18` is open to promote ten real-data cases to normative vectors,
which will move that manifest again. Recording nothing and reporting `ABSENT` is the
honest state; advancing a pin to bytes known to be about to change would make this
repository read as authoritative about a draft it does not support.

Rule V7 is unchanged by either section: FHT has no released contract, no
`versions.json` row, no tag and no w3id alias, and every draft row says
`draft, not acceptance`.

## 7. Steps to a mergeable PR once #29 landed (it has — see below) and §4 is answered

Originally written assuming FHT-Specification PR #29 was open; **it merged as
`b9ad19a` on 2026-11-12**, so the remaining external dependency is only the
§4 coordination answer.

1. Rebase `codex/fht-9-prep` onto current `main` (expect conflicts only in
   `selection.py`/`bundled.json` if the release cycle moved first).
2. Re-check `origin/main:fht.json` of FHT-Specification against the bundled
   draft; if it moved, refresh `fht-draft.json` + `revision` + `retrieved` +
   `sha256` together and re-run §6. Re-check
   `origin/main:conformance/manifest.json` against `drafts.FHT.suite` the same
   way: the contract and the suite move independently, so a suite-only move
   refreshes `suite.revision`/`retrieved`/`sha256`/`bytes`/`fhtFastaVectors` and
   nothing else, and `tests/fht_conformance_test.py` reports which bytes it scored.
3. Post the PR with: design doc, gate semantics, this checklist, the 65/65
   conformance result, and the #137 warning behaviour unchanged by default;
   `Refs FHT-Specification#9`.
4. If the maintainers choose §4 option (ii) before the PR merges, fold the
   V7/`versions.json`-backed form in instead of the env-gated preview.
5. Add the FHT conformance command to CI only when the shared suite layout is
   pinned (same mechanism as the `fhp-fasta` vectors), otherwise keep it a
   documented opt-in run.


### 6.3 Dated approved reconciliation — 2026-11-16 (Tools #167)

The maintainer explicitly approved the measured runtime/audit proposal during
Round 12. This is a deliberate human-reviewed pin update, separate from the
read-only reporting implementation. The runtime 68-vector suite at `7503b264` and audit
66-vector suite at `24d3b033` both move to:

- suite revision `be9bcc825f55db92852fd882ffba4c1c214f53db`;
- SHA-256 `9fd8c0b2a4638d5ddc0bf9b5d1e96c66778b26bcf8f93975aafb707d8f2b702c`;
- **65,615 downloaded bytes, 72 fht-fasta vectors**.

The owning default tip `a06ea0c0f292a978e55c5872e89627b5a267fc75` has the same
manifest bytes; `be9bcc82` is the last commit that modified that manifest. This
choice records evidence for this update, not adoption of a new federation-wide
suiteCommit convention or a reason to rewrite digest-equivalent consumer pins.
The contract stays at `226f923c28b680edb3c546e99a751482d06aef1a`, SHA-256
`59ad9641adcb0e5591045c2d894c066d1adc9984cca84c5ff6502f8dad88487e`.

The prior §6.1/6.2 runs and their open-issue statements are dated history. In
particular, FHGM #18 subsequently merged; this toolkit still holds no FHGM
implementation/pin (#135), and this FHT reconciliation invents none. FHT remains
opt-in draft evidence, with no released alias, registry row or publication claim.
The advisory currency command never applies this change or any later update.

## 7. Deliberate Round 15 readiness refresh (2026-11-19)

The contract and suite axes now name accepted owning commit `4ddda69cbcbb3920a06ab657173c0198672cd7bf` independently. The contract SHA-256 is
`b62c4e227042e162b43d2c461cfe6c3ece3806636ca88a4cf9b0b2f902fb1fc3`;
the 93-vector manifest SHA-256 is
`d0147d3ad97c0fad0ede94ae76340632a86a160f566b01129e592e643fd77492`.
These are the owning V7 raw-main bytes, distinct from a shared publication
candidate's root selector bytes. They remain unreleased. Earlier section 6
measurements are historical and do not describe the current pin.

`bioheaders/fht_microdata.py` ports the reviewed owning reference at that commit;
packaged registry digests replace checkout/git discovery. It preserves the
reference visibility/inert-content/typed-container/escaping rules and RCDATA
capability refusal, while the toolkit validator supplies its own date, pattern,
R4 and C1 checks. The standard library only parses local text; no URI is fetched.
Installed `convert`/`validate` use that binding under the existing FHT opt-in.
The FHR itemtype still cannot identify an FHT record. JSON-LD remains refused.
