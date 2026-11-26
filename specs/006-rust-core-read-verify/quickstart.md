# Quickstart: Phase 1 Rust core (development branch `p14-rust-core`)

Prerequisites: Rust ≥ 1.85 (`rustup`), a C compiler, Python ≥ 3.9 with `uv`
or `pip`, and two specification checkouts for the corpora.

```bash
# corpora (exact commits; the tests verify the manifest SHA-256 before running)
git clone --filter=blob:none https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification spec
git -C spec worktree add ../spec-v0.6.0   0ae18b00ee4bd71ab2dc28bae706b0f9d195076b
git -C spec worktree add ../spec-34bbe21a 34bbe21ac68a99c6e9324cbe7b6a66cd449fbe3b
export FH_SPEC_V060=$PWD/spec-v0.6.0 FH_SPEC_34BBE21A=$PWD/spec-34bbe21a FH_REQUIRE_CORPUS=1

# Rust core: unit, L1 conformance (writes receipts to target/receipts/), C-ABI harness
cargo test --workspace --locked
cat target/receipts/C-FROZEN.json      # expect run 228, passed 228, NOT_RUN 63
cat target/receipts/C-SOURCE.json      # expect run 254, passed 254, NOT_RUN 65
cargo deny check                        # advisories, licences, bans, sources

# Python binding: build the wheel, install outside the checkout, run native acceptance
uv venv /tmp/fhvenv && . /tmp/fhvenv/bin/activate
uv pip install maturin pytest
maturin build --release -m crates/fair-bioheaders-tools-python/Cargo.toml -o /tmp/wheels
uv pip install /tmp/wheels/fair_bioheaders_tools-*.whl
(cd /tmp && pytest -rs $OLDPWD/crates/fair-bioheaders-tools-python/tests)

# Toolkit in both modes (G1 item 3)
uv pip install . pytest
(cd /tmp && pytest -q $OLDPWD/tests)                               # default: pure Python
(cd /tmp && BIOHEADERS_ENGINE=rust pytest -q $OLDPWD/tests)        # opt-in engine
```

Using the library from Python:

```python
import fair_bioheaders_tools as fht
engine = fht.Engine()                     # python profile, specification limits
report = engine.verify("genome.fhr.fasta.gz")
print(report.outcome, report.checksum.computed)
for d in report.diagnostics:
    print(d.severity, d.code, d.rule, d.header_line, d.message)
```

Using it from Rust (pinned tag once a human creates one):

```toml
[dependencies]
fair-bioheaders-tools = { git = "https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Tools", tag = "core-v0.1.0" }
```

Clean build outputs regularly (`cargo clean`) when disk space is tight.
