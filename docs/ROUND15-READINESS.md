# Round 15 toolkit prepublication readiness

This packet starts at Tools main `aa9357f2671e9fb9bbd9bc51e055d3369d5ffc19`.
It is a candidate build, not a published toolkit release. Both experimental gates
remain closed by default; no fixed unpublished citation is registered.

- FHT owning contract/suite: `4ddda69cbcbb3920a06ab657173c0198672cd7bf`,
  schema SHA-256 `b62c4e227042e162b43d2c461cfe6c3ece3806636ca88a4cf9b0b2f902fb1fc3`,
  manifest SHA-256 `d0147d3ad97c0fad0ede94ae76340632a86a160f566b01129e592e643fd77492`.
  This is the owning V7 selector package, distinct from shared publication root
  selector bytes. Its 93 validity cases and 10 stated parent-link cases were
  executed: 104 passed, 83 skipped solely because those vectors have no parent
  file. No validity case was skipped. Both completeness arithmetic negatives run.
- FHGM suite: `d9d131a02b042023f4784d842a874232fc891069`, 92 vectors,
  manifest SHA-256 `d42b621165951dc0eb94ec80ff1953aae72c62d668e7a88c5b48541e41d26a64`.
  Actual model outcomes: 24 pass, 67 reject, one not-run; no feature-layer pass
  is claimed without the external validator. Native record/transport/base
  contract bytes remain unchanged. Model, base,
  checksum and feature evidence remain separate. The historical coarse rejection
  for `pointer-into-ambiguous-history` is explicitly separated from selected-file
  model not-run: predecessor K3 failed, so carrier K6 was not executed.
- Typed HTML ports the reviewed owning reference at the accepted FHT commit.
  Packaged commit/digest pins replace git-checkout provenance. Tests exercise
  installed convert/validate/readback outside the checkout, seven owning JSON
  examples, rich nested/zero/absence values, escaping, inert scopes and rejected
  hidden/ambiguous/unsupported selections. JSON-LD stays unsupported. The reader
  probes RCDATA behavior and refuses incompatible runtimes; Python 3.9.25 and
  3.12.15 used here expose that capability.
- Shared adopted reader policy: strict installed-wheel run of all 64 cases at
  shared checker checkout `6dee4c8baba723ec5cad825d521db2dbbc1921ae`: 64 matched,
  zero problems, exit 0. This establishes runtime behavior, not just an oracle.
- Reference audit: 36 FRESH, two ABSENT (the existing unrecorded FHP context and
  copied examples tree), zero QUERY_FAILED. Every performed group has its own
  confirmed-missing control. Changed digest and missing recorded tag-commit
  controls yield DRIFT and ABSENT respectively; no pins were changed by the audit.

R4 rejects historical noncanonical synthetic checksum values. Original examples,
old fixture bytes and the v0.6.0 291-vector ledger are preserved. New active
examples live in `examples/r4-current/` with a complete source/counterpart digest
crosswalk; 15 files change only synthetic checksum pad bits and 30 remain controls.
The accepted shared retirement crosswalk supplies 69 new FHP/FHGFF3 fixture
counterparts in separate paths, selected by their new IDs at runtime. Old local
manifests continue to prove exact v0.6.0 parity. CI independently runs the adopted
current six-format suite plus 64 supplementary policy cases; the support matrix
keeps its frozen released ledger clearly separate.

Full current-head CI, independent different-model approval, shared publication
readiness and actual releases are distinct remaining gates. Tools #135/#155 and
shared #258/#267/#241 remain open until the coordinator reconciles all consumers
and each issue's complete acceptance. No publication/default support is claimed.

## Installed artifact receipts at producer head 536d6ba (2026-11-19)

- Shared adopted current suite: **319 vectors passed**, all six required formats
  through `/tmp/round15-tools-env/bin` from `/tmp`, exit 0. The preserved released
  291 ledger is a distinct historical count. Supplementary reader policy: 64/64
  matched, zero problems, exit 0.
- Combined owning-suite consumers: **291 passed, 83 skipped**. This coincidental
  pass count is not the released 291 ledger: it comprises FHT 104 assertions and
  FHGM 187 assertions; the 83 skips are parentless FHT link parametrizations.
- Focused FHR/FHP follow-up after canonical fixture/directive-policy corrections:
  **135 passed, one skipped** (missing optional shared parity checkout), exit 0.
- The first broad local run was interrupted after finding stale test controls:
  1322 passed, 12 skipped, two matrix-document failures and 11 sandbox local-socket
  setup errors. The matrix was then regenerated successfully; the socket checks
  were not represented as passes. A later broad runtime run was stopped after
  six noncanonical synthetic parent setups and one legacy-fixture recombine
  failed; these were corrected explicitly, then the focused 135-test run above
  passed. Current-head CI remains required for the full regression/OS matrix.

The noneditable wheel resides at `dist/fair_bioheaders-0.12.0-py3-none-any.whl`
locally; this is development-candidate version metadata, not publication of
another 0.12.0 wheel. Package import/commands resolve to the isolated environment's
site-packages outside the checkout.

## Independent review follow-up (2026-11-19)

Terra review 5985572867 correctly distinguished malformed row inventories from
earned K4 rejections. Wrong column counts and truncated/malformed/undecodable
ID escapes now report model/K4 **not-run**, matching existing malformed-ID and
whitespace behavior. Sixteen new status regressions cover each malformed input
with the selected target absent and with a valid target plus an unrelated bad
row. Complete trustworthy empty inventories still earn K4 rejection.

The rebuilt candidate was reinstalled noneditably and tested from `/tmp`, with
`PYTHONPATH` unset and pytest `--import-mode=importlib`; the imported FHGM module
was verified under `/tmp/round15-tools-env/lib/.../site-packages`. Native FHGM
tests plus accepted 92-vector consumer: **278 passed, zero skipped**, exit 0.
This removes the ambiguity of earlier checkout-launched direct-API tests, which
could import source despite the installed CLI. Earlier FHT CLI/64-policy/319-suite
subprocess receipts remain installed-command measurements. The shared base,
checksum and model results stay separate; no external feature pass is implied.

The first CI matrix run also exposed two stale test literals for the historical
FHT 75/62 measurement. Assertions now require the deliberately refreshed actual
104/83 receipt; the ledger and generator already carried that new receipt.
