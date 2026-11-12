# FHT selection design — draft lane for the family toolkit (PREP)

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
closes its own `schema` field (rule T2 of the FHT suite) to

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
rules and stays the **default behaviour** of this branch.

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
   (matched / not matched / not checked for `derivedFrom` FHR parents, T3),
   `validate`, `convert` to/from YAML/JSON, required-value and link-scheme
   warnings, R15 extension fields and R11 escaping all key off
   `schema_for(record)` and the generic header text. The gated prototype
   passes **all 65 vectors** of the FHT-Specification suite (see §6).

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
   `FHT: warning: … selects the bundled FHT draft contract (development only,
   not a released schema …)` on stderr (via `schema_warnings`) and emits
   `ExperimentalDraftWarning` to library callers — the
   `fhgff3_microdata.ExperimentalMicrodataWarning` precedent from #141,
   doubled because the *contract itself*, not just a serialization, is draft.
   `selection.supported("FHT")` reports `main (draft, experimental)`; there is
   deliberately no `FHT` key in `current.files`.

7. **Deferred by design** (each needs its own PR or decision, none is silently
   skipped): default-on selection (blocked on §4); assess rubric/conformance
   scoring for FHT records (today: honest `not_assessed`); the
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
| Registry + bundled bytes | `bioheaders/schemas/bundled.json` (`drafts.FHT`, provenance fields), `bioheaders/schemas/fht-draft.json` (byte copy of FHT-Spec `main@b9ad19a`, sha256-pinned) | implemented |
| Schema-selection warnings | `bioheaders/__init__.py`: `schema_warnings()` appends the draft notice; `header_type()` docstrings | implemented |
| Family table | `bioheaders/cli.py`: `validate_header_family()` — FASTA only, gate-gated | implemented |
| Unbound forms | `__init__.py`: `fhr.output_jsonld`, `fhr.output_microdata`, `fhr.input_microdata`; `cli.py`: `_convert` JSON-LD guard | implemented (refusal) |
| FASTA pipeline (`combine`/`verify`/`strip`/checksum/scan/gzip/pipes) | `cli.py` `combined_header`, `SequenceScan`, `strip_header`; `__init__.py` `output_fasta`/`input_fasta` | **no changes needed** — verified by tests |
| verify-links (T3) | `cli.py` `_parent`, `_verify_links` | no changes needed — verified (matched/not matched/not checked, FHR and FHT parents) |
| assess | `assess/conformance.py` (`FHT_URL`, `not_assessed`) | unchanged on purpose; rubric support deferred |
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
that a T3 failure is *not* a `verify` failure.

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

## 7. Steps to a mergeable PR once #29 landed (it has — see below) and §4 is answered

Originally written assuming FHT-Specification PR #29 was open; **it merged as
`b9ad19a` on 2026-11-12**, so the remaining external dependency is only the
§4 coordination answer.

1. Rebase `codex/fht-9-prep` onto current `main` (expect conflicts only in
   `selection.py`/`bundled.json` if the release cycle moved first).
2. Re-check `origin/main:fht.json` of FHT-Specification against the bundled
   draft; if it moved, refresh `fht-draft.json` + `revision` + `retrieved` +
   `sha256` together and re-run §6.
3. Post the PR with: design doc, gate semantics, this checklist, the 65/65
   conformance result, and the #137 warning behaviour unchanged by default;
   `Refs FHT-Specification#9`.
4. If the maintainers choose §4 option (ii) before the PR merges, fold the
   V7/`versions.json`-backed form in instead of the env-gated preview.
5. Add the FHT conformance command to CI only when the shared suite layout is
   pinned (same mechanism as the `fhp-fasta` vectors), otherwise keep it a
   documented opt-in run.
