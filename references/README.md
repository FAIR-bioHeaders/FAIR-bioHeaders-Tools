# Current declared references

`scripts/audit_declared_references.py` reads current `bioheaders/pins.json`,
`tests/fixtures/r4-crosswalk.json` and FHT HTML fixture provenance on every run.
It verifies the immutable shared checker against `checker.json`, executes only
those verified bytes under isolated Python, and never changes a pin. Existing
`bioheaders-pin-audit` checks remain native installed-toolkit evidence.

Tagged authorities carry recorded dereferenced commits. Commit-kind authorities
retain their declared full immutable revision. Missing declarations report
ABSENT; query/control failures remain QUERY_FAILED. Upstream manifest checks do
not pretend a filtered local manifest is byte-identical: native transform and
fixture-parity tests retain that separate evidence. The two previously declared
holes (FHP context source and copied examples provenance, Tools #163) remain
explicit ABSENT findings, not inferred pins.

```sh
python scripts/audit_declared_references.py --checker-root /checkout/at-6dee4c8 \
  --checkout FAIR-bioHeaders/FAIR-bioHeaders-Specification=/path/to/shared \
  --checkout FAIR-bioHeaders/FHT-Specification=/path/to/fht \
  --checkout FAIR-bioHeaders/FHGM-Specification=/path/to/fhgm \
  --checkout FAIR-bioHeaders/FHP-Specification=/path/to/fhp
```

Without checkout mappings the verified checker probes content-addressed GitHub
bytes and a missing-path control on every reference group. The scheduled workflow
stays advisory; strict mode exists for controlled failures only. The matching
`scripts/check_reference_controls.py` proves a byte-distinct wrong digest yields
DRIFT and a removed recorded tag commit yields ABSENT, while preserving source
bytes. Neither command updates dependencies or follows moving draft main.
