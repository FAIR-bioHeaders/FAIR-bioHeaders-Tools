# Contract: Python binding (`fair-bioheaders-tools`, import `fair_bioheaders_tools`)

CPython ≥ 3.9 (abi3). Pure-Python façade `fair_bioheaders_tools/__init__.py`
over the native module `fair_bioheaders_tools._native`.

```python
__version__: str                 # package version
ENGINE_VERSION: str
ABI_VERSION: str                 # "0.x" (informational; PyO3 does not use the C ABI)

class Engine:
    def __init__(self, profile: str = "python", *, limits: dict[str, int] | None = None,
                 raise_limits: dict[str, int] | None = None,
                 draft_lanes: tuple[str, ...] = (), exact_decimals: bool = False): ...
    def validate(self, source, *, container: str = "auto") -> Report: ...
    def verify(self, source, *, container: str = "auto") -> Report: ...
    def stream(self, operation: str = "verify", *, container: str = "auto") -> Stream: ...
    @property
    def provenance(self) -> dict: ...

# source: bytes | bytearray | memoryview | str | os.PathLike (path) | binary file object
# container: "auto" | "fasta" | "fhp-fasta" | "gfa" | "gff3" | "metadata-yaml" | "metadata-json"

class Stream:
    def feed(self, chunk: bytes) -> bool: ...      # True when complete (validate)
    def finish(self) -> Report: ...
    def cancel(self) -> None: ...                  # thread-safe
    def __enter__/__exit__                          # releases the stream exactly once

class Report:                                      # immutable
    outcome: str            # "valid" | "invalid" | "unsupported" | "limit"
    valid: bool
    layers: dict[str, LayerResult]
    diagnostics: tuple[Diagnostic, ...]
    selection: Selection | None
    checksum: Checksum | None
    metadata: dict | None   # ints exact; decimals float, or Decimal when exact_decimals
    provenance: dict
    def first_error(self) -> Diagnostic | None: ...
    def to_json(self) -> str: ...

class Diagnostic: severity, code, rule, layer, message, header_line, byte_offset,
                  byte_len, json_pointer

class EngineError(Exception)
class InternalError(EngineError)          # contained engine panic
class CancelledError(EngineError)
class IncompatibleEngineError(EngineError, ImportError)
class InvalidArgumentError(EngineError, ValueError)
# Io errors are raised as OSError subclasses with errno where available.
```

Rules: the GIL is released during engine work; one `Engine` may be used from
several threads. Verdicts never raise. Native handles never escape: results are
converted eagerly into Python objects.

## Toolkit opt-in backend (in `fair-bioheaders`, Clarification Q1)

```python
import bioheaders
bioheaders.set_engine("rust")   # or env BIOHEADERS_ENGINE=rust before import
bioheaders.engine()             # -> "python" | "rust"
```

With `"rust"`, the toolkit's Phase 1 read paths (`fhr.input_fasta`,
`input_gfa`, `input_gff3`, `input_yaml`, `input_json`, `fhr_validate`, the CLI
`validate`/`verify` and `fhr-*-validate` commands) call the engine and map the
`Report` back to today's values and exceptions: `ValueError` with today's
message text for framing/YAML/limit failures, `UnsupportedSchemaVersion`,
`NonFiniteValueError`, `jsonschema.ValidationError` (with `json_path`) for
schema failures, `ValueError("Checksum verification failed")` for a mismatch,
and the same warnings on stderr. Engine `InternalError` propagates as itself.
`"rust"` without an installed, version-matched `fair-bioheaders-tools` raises
`ImportError` naming the required version; no fallback.
