# Round 16 toolkit maintenance record

Scope: server main `bf3c506d0f3e8f683048fd16a2c4ad9e907aff14`, refreshed
2026-11-20. [Shared tracker and policy](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/211#issuecomment-7042896529).
This packet changes live contributor guidance, human documentation and one
portability defect and a workflow credential-persistence finding. It changes no contracts, registry, pins, release version,
fixture bytes, historical licensing or supported feature set. PR #201 is
independent ongoing work and is deliberately untouched.

## Audit and dispositions

The audit uses Bandit 1.8.6 (default rules, recursively `bioheaders` and `fhr.py`),
gitleaks 8.30.1 (default rules, fully redacted reports, working tree and all locally
available Git history), zizmor 1.16.3 (default audits on all workflows), and pip-audit 2.9.0 against the exact resolved runtime
requirements, including the optional JSON-LD dependency closure. No known runtime vulnerabilities were reported on 2026-11-20. Advisory results
are a dated snapshot, not a warranty or an audit of every supported dependency
resolution. Tool versions, environment, full redacted outputs and branch inventory
are recorded in [the reproducible audit packet](audit-2026-11-20/README.md);
full redacted outputs are also retained in the coordinator's Round 16 evidence.

### Development dependency advisories

The GitHub alert API also reports three open lockfile alerts on 2026-11-20:
Black 25.11.0 on the Python 3.9 development branch has
GHSA-cg8m-r9f2-5wm2 (patched 26.10.1) and GHSA-3936-cmfr-pm3m (patched 26.3.1);
pytest 8.4.2 has GHSA-6w46-j5rx-g56g (patched 9.0.3). Patched versions require
Python 3.10+. The modern Black branch is raised to 26.10.1 or later.
Python 3.9 runtime support is preserved; an upstream unsupported development-tool
patch cannot be claimed. Maintainers own the minimum-runtime/tooling decision.

The Black action-specific vulnerability requires `psf/black` with
`use_pyproject: true`, which these workflows do not use. Its cache-path issue
requires attacker-controlled `--python-cell-magics`, which CI does not accept.
Pytest's shared `/tmp/pytest-of-{user}` directory issue remains relevant on
untrusted multi-user machines; use an isolated user/container or an explicitly
private `--basetemp` directory. These are explicit residual risks, not closed
alerts or a claim that every lockfile branch is advisory-free.

Manual source review covered reader limits and `_Loader` in `bioheaders/__init__.py`,
compression and output paths in `cli.py`, HTML readers/writers, JSON-LD context
loading, `assess/online.py`, related sequence checks, pin audit subprocesses,
package metadata, Dockerfile and all nine GitHub workflow files.

| Finding | Disposition |
| --- | --- |
| Bandit B324: two MD5 sequence identifier calls | Fixed: explicitly `usedforsecurity=False`, supports Python builds that restrict security-use MD5 but still provide MD5 for identifiers. A two-record regression simulates security-use MD5 being disabled for both FASTA and GFA. It is not a test on an actual FIPS provider; a provider with no MD5 implementation can still raise `ValueError`. SHA-512/256 file checksums are unchanged. |
| Zizmor artipacked: Codacy checkout persisted credentials | Fixed: `persist-credentials: false`, consistent with other checkouts. No job requires a credentialed Git checkout. |
| B506: `yaml.load` | False positive: `_Loader` derives from `yaml.SafeLoader` and additionally rejects aliases, tags, duplicate keys and nonportable syntax; byte/node/depth limits apply. Switching to bare `safe_load` would remove required reader controls. |
| B610: `record["assemblySoftware"]` | False positive: dictionary metadata assignment, no SQL engine or query. |
| B105: literal `"pass"` | False positive: a model verdict enum, not a password. |
| B101: faidx assertions | Internal invariant checks; malformed-input validation occurs separately. No user authorization or security boundary depends on an assertion. |
| B404/B603/B607: Git subprocesses | Argument arrays without a shell. Local Git executable/checkout and user-selected audit tables belong to the invoking user's trust boundary. No remote metadata is executed as a shell command. |
| Gitleaks working-tree 20 / history 25 matches | False positives: public accession/SeqCol fixture identifiers and the synthetic `ACCESSION` test constant; reports retain location/commit evidence with values redacted. No fixture bytes or history rewritten. |

Online assessment vets public addresses and redirects, connects through the
checked address and applies deadlines; it remains opt-in. Contract and JSON-LD
contexts are bundled offline. Gzip decompression is chunked; metadata readers
bound decompressed bytes. Sequence processing can still consume time/disk in
proportion to user input; deployments accepting uploads need their own job limits.
Pin-audit network downloads and local Git output are not a hostile-upload service;
run the advisory CLI on trusted audit tables and apply process limits externally.

Workflow review found SHA-pinned action references, read-only default permissions,
no `pull_request_target`, no PR-triggered publication and separate release jobs
with scoped write/OIDC privileges. CI dependency installs still resolve declared
ranges and some developer tools at run time; this audit does not claim hermetic
builds. No publishing workflow is run by this maintenance packet.

## Workplan and branch disposition

The current work is this Round 16 packet and its human review queue. Historical
Round 15 readiness and FHT selection notes are explicitly marked as dated evidence;
they do not define current merge authority or negate published 0.13.1 support.
Existing functional guides remain live references. No instruction embedded in a
frozen published/vendored artifact grants agent merge authority.

The repository has numerous local branches and active worktrees. Inventory is
retained in the coordinator's evidence packet. No preexisting branch was deleted:
this run cannot establish exclusive ownership, worktree cleanliness and absence
of unique/open work for every historical ref. In particular PR #201, task
worktrees, release tags and historical refs are retained. This isolated branch is
eligible for ordinary deletion only after a human merge and a fresh safety check.
No remote branch is deleted speculatively.

Every PR receives review from another actual model (different family preferred),
with real identities recorded. Agents read overall and inline findings, fix in new
commits, reply with dispositions, resolve handled findings and validate the current
head. A human merges; agents never merge, enable auto-merge, queue a merge, proxy a
merge or bypass a PR with a default-branch push. CI and review evidence attach to
the exact head; unavailable checks are not passes. This packet does not authorize
contract adoption, publication or a release.
