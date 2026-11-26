# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FAIR-bioHeaders read/validate/verify engine (Rust) for Python.

One implementation of header framing, exact SHA-512/256 checksum coverage,
portable YAML/JSON metadata with exact numbers, strict gzip/BGZF input,
record-aware schema selection (V1-V7), JSON Schema 2020-12 validation and
family predicates for FASTA, GFA, FHP-FASTA and FHGFF3 files and YAML/JSON
metadata files. JSON-LD, microdata and model checks are outside this engine
and are reported as not run.

Verdicts are returned in a :class:`Report`; call failures raise
:class:`EngineError` subclasses.
"""

import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version
from typing import Any, Dict, Optional, Tuple

from . import _native

__all__ = [
    "ABI_VERSION",
    "ENGINE_VERSION",
    "CancelledError",
    "Checksum",
    "Diagnostic",
    "Engine",
    "EngineError",
    "IncompatibleEngineError",
    "InternalError",
    "LayerResult",
    "ProfileError",
    "Report",
    "Selection",
    "StateError",
    "Stream",
    "__version__",
]

try:
    __version__ = _version("fair-bioheaders-tools")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0+unknown"

ENGINE_VERSION: str = _native.ENGINE_VERSION
ABI_VERSION: str = _native.ABI_VERSION

EngineError = _native.EngineError
InternalError = _native.InternalError
CancelledError = _native.CancelledError
StateError = _native.StateError
ProfileError = _native.ProfileError


class IncompatibleEngineError(EngineError, ImportError):
    """The installed engine is not the version a caller requires."""


#: Containers accepted by ``container=``.
CONTAINERS = (
    "auto",
    "fasta",
    "fhp-fasta",
    "gfa",
    "gff3",
    "metadata-yaml",
    "metadata-json",
)

#: Bytes read per feed when a file object is given.
CHUNK_SIZE = 1 << 20


@dataclass(frozen=True)
class Diagnostic:
    """A structured diagnostic. ``code`` and ``rule`` are the contract; the
    message is informative English and may change."""

    severity: str
    code: str
    rule: Optional[str]
    layer: str
    message: str
    header_line: Optional[int]
    byte_offset: Optional[int]
    byte_len: Optional[int]
    json_pointer: Optional[str]


@dataclass(frozen=True)
class LayerResult:
    """One pipeline layer's status and, when not run, the reason."""

    layer: str
    status: str
    not_run_reason: Optional[str]


@dataclass(frozen=True)
class Selection:
    """The schema a record selected."""

    header_type: str
    release: str
    schema_file: str
    schema_sha256: str
    rule: str
    draft: bool


@dataclass(frozen=True)
class Checksum:
    """The covered-bytes checksum result."""

    stated: Optional[str]
    computed: Optional[str]
    matches: Optional[bool]
    covered_bytes: int


@dataclass(frozen=True)
class Report:
    """The result of one read."""

    outcome: str
    container: str
    layers: Dict[str, LayerResult]
    diagnostics: Tuple[Diagnostic, ...]
    selection: Optional[Selection]
    checksum: Optional[Checksum]
    metadata: Optional[Dict[str, Any]]
    provenance: Dict[str, Any]

    @property
    def valid(self) -> bool:
        """Whether the outcome is ``valid``."""
        return self.outcome == "valid"

    def first_error(self) -> Optional[Diagnostic]:
        """The first error in pipeline order (what a single-exception caller raises)."""
        return next((d for d in self.diagnostics if d.severity == "error"), None)

    def warnings(self) -> Tuple[Diagnostic, ...]:
        """Warnings in order."""
        return tuple(d for d in self.diagnostics if d.severity == "warning")

    @classmethod
    def _from_native(cls, raw: Dict[str, Any]) -> "Report":
        return cls(
            outcome=raw["outcome"],
            container=raw["container"],
            layers={
                name: LayerResult(name, status, reason)
                for name, status, reason in raw["layers"]
            },
            diagnostics=tuple(Diagnostic(**d) for d in raw["diagnostics"]),
            selection=(
                Selection(**raw["selection"]) if raw["selection"] is not None else None
            ),
            checksum=(
                Checksum(**raw["checksum"]) if raw["checksum"] is not None else None
            ),
            metadata=raw["metadata"],
            provenance=raw["provenance"],
        )


class Stream:
    """A push stream: ``feed`` chunks, then ``finish``. ``cancel`` is safe from
    another thread. Use as a context manager to release it exactly once."""

    def __init__(self, native):
        self._native = native

    def feed(self, chunk) -> bool:
        """Feed bytes; True once a validate-only read may stop reading."""
        return self._native.feed(chunk)

    def finish(self) -> Report:
        """Finish and return the report."""
        return Report._from_native(self._native.finish())

    def cancel(self) -> None:
        """Cancel; a later feed or finish raises :class:`CancelledError`."""
        self._native.cancel()

    def close(self) -> None:
        """Release the stream's state now (idempotent)."""
        self._native.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class Engine:
    """An immutable engine for one consumer support profile.

    ``limits`` lowers bounds (names as in ``provenance["limits_applied"]``,
    for example ``in_memory_decompressed_bytes``); ``raise_limits`` raises
    them above the specification values explicitly. ``draft_lanes`` opens
    opt-in draft lanes allowed by the profile (``("fht",)``).
    ``exact_decimals=True`` returns decimals as :class:`decimal.Decimal`.
    """

    def __init__(
        self,
        profile: str = "python",
        *,
        limits: Optional[Dict[str, int]] = None,
        raise_limits: Optional[Dict[str, int]] = None,
        draft_lanes: Tuple[str, ...] = (),
        exact_decimals: bool = False,
    ):
        self._native = _native.NativeEngine(
            profile,
            list((limits or {}).items()),
            list((raise_limits or {}).items()),
            list(draft_lanes),
            exact_decimals,
        )

    @property
    def provenance(self) -> Dict[str, Any]:
        """Engine, ABI, bundle and profile identities and the applied limits."""
        return self._native.provenance

    def validate(self, source, *, container: str = "auto") -> Report:
        """Every layer except the checksum (the toolkit's ``validate``)."""
        return self._run("validate", source, container)

    def verify(self, source, *, container: str = "auto") -> Report:
        """Every layer including the covered-bytes checksum."""
        return self._run("verify", source, container)

    def stream(self, operation: str = "verify", *, container: str = "auto") -> Stream:
        """A push stream."""
        return Stream(self._native.stream(operation, container))

    def _run(self, operation: str, source, container: str) -> Report:
        if isinstance(source, (bytes, bytearray, memoryview)):
            raw = self._native.verify_bytes(
                operation,
                container,
                bytes(source) if not isinstance(source, bytes) else source,
            )
            return Report._from_native(raw)
        if isinstance(source, (str, os.PathLike)):
            return Report._from_native(
                self._native.verify_path(operation, container, os.fspath(source))
            )
        if hasattr(source, "read"):
            with self.stream(operation, container=container) as stream:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        raise TypeError("expected a binary file object")
                    stream.feed(chunk)
                return stream.finish()
        raise TypeError("source must be bytes, a path or a binary file object")
