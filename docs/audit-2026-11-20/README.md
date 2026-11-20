# Reproduce the 2026-11-20 toolkit audit

Author source: `bf3c506d0f3e8f683048fd16a2c4ad9e907aff14`; corrected code is
in PR #203. Scanner rules were defaults, with no ignored findings or repository
allowlist. Commands run from the isolated checkout (replace `EVIDENCE` with a
private output directory):

```sh
uv venv --python 3.13 /tmp/round16a-tools-env
uv pip install --python /tmp/round16a-tools-env/bin/python \
  bandit==1.8.6 pip-audit==2.9.0 zizmor==1.16.3 '.[jsonld]'
/tmp/round16a-tools-env/bin/bandit -r bioheaders fhr.py -f json -o "$EVIDENCE/bandit.json"
/tmp/round16a-tools-env/bin/zizmor --format json .github/workflows > "$EVIDENCE/zizmor.json"
gitleaks version  # 8.30.1
# --all includes every locally available ref; a remote's un-fetched history is out of scope.
gitleaks git . --log-opts=--all --redact=100 --report-format json --report-path "$EVIDENCE/history.json"
gitleaks dir . --redact=100 --report-format json --report-path "$EVIDENCE/tree.json"
/tmp/round16a-tools-env/bin/python docs/audit-2026-11-20/runtime_requirements.py > "$EVIDENCE/runtime-requirements.txt"
/tmp/round16a-tools-env/bin/pip-audit -r "$EVIDENCE/runtime-requirements.txt" \
  --no-deps --disable-pip -f json -o "$EVIDENCE/pip-audit.json"
uvx --python 3.13 --from poetry==2.3.2 poetry check --lock
```

The runtime requirements in this directory are **installed distribution
metadata**, not an export from `poetry.lock`: recursively walk
`importlib.metadata.distribution('fair-bioheaders').requires`, parse with
`packaging.requirements.Requirement`, evaluate markers for the Python 3.13 runtime
and the `format`/`jsonld` extras, deduplicate by distribution name and record each
installed version. This measures one actual current resolution and does not
claim to cover all versions allowed by a range. The separate GitHub Dependabot
API review covers the tracked lockfile's older Python branches; the maintenance
record explicitly retains its Python 3.9 development-tool residuals.

Bandit exits 1 for the recorded findings, not a scan failure: zero per-file parse
exceptions across 34 files. Fixed scan has 14 remaining manually dispositioned
findings; its locations are committed here. Zizmor's one original Codacy
credential finding is fixed; final output is `[]`. Gitleaks exits 1 for the
listed public accession/SeqCol/synthetic identifier matches. The all-ref run
covered 402 commits. Committed lists contain locations/commit fingerprints only,
not match values. See [the finding table](../ROUND16-MAINTENANCE.md) for decisions.
No scanner suppression, fixture byte edits or history rewrite hid these findings.

The Black lock update was generated, not edited manually:
`uvx --python 3.13 --from poetry==2.3.2 poetry update black --lock`.
Poetry 2.3.2 is also the repository's release-workflow-pinned tool; its older
version compared with the prior generator is recorded rather than forged in the
lock header. `lock-delta.json` proves that Black's modern-Python branch is the
only package metadata change. `poetry check --lock` and both hosted Python
installation/test jobs validate the generated format/content hash. This does
not require rewriting unrelated locked packages.

Publication receipts: [GitHub v0.13.1 release](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools/releases/tag/v0.13.1),
[PyPI 0.13.1 JSON metadata](https://pypi.org/pypi/fair-bioheaders/0.13.1/json),
and [Zenodo version archive](https://doi.org/10.5281/zenodo.24387470), published
2026-11-20. Actual wheel SHA-256:
`9f600347711ee771c8bc8f8e545438c255685736206b1342413b16076da20a45`.
The coordinator retained byte comparisons of actual PyPI/GitHub artifacts and
archive/tag contents. Those are published artifact receipts, separate from this
unreleased maintenance branch. GitHub's old repository URL was probed without
following redirects; a present redirect does not guarantee future old-name reuse.
