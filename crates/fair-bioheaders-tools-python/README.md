# fair-bioheaders-tools

The FAIR-bioHeaders read/validate/verify engine (Rust) for Python: header
framing, exact SHA-512/256 checksum coverage, portable YAML/JSON metadata with
exact numbers, strict gzip/BGZF input, record-aware schema selection (V1-V7)
over digest-pinned bundles, JSON Schema 2020-12 validation and family
predicates for FASTA, GFA, FHP-FASTA and FHGFF3 files and YAML/JSON metadata.

```python
import fair_bioheaders_tools as fht

engine = fht.Engine()
report = engine.verify("genome.fhr.fasta.gz")
print(report.outcome, report.checksum.computed)
for d in report.diagnostics:
    print(d.severity, d.code, d.rule, d.header_line, d.message)
```

Verdicts are returned, never raised. Integers are exact `int`; decimals are
`float` unless `Engine(exact_decimals=True)` returns `decimal.Decimal`. The
default limits follow FAIR-bioHeaders-Specification docs/FORMAT.md; the 1 GiB
`in_memory_decompressed_bytes` bound for buffered input can be lowered with
`Engine(limits={"in_memory_decompressed_bytes": n})` or raised with
`raise_limits=`.

This is a development build of Project 14 Phase 1; it is not published.
