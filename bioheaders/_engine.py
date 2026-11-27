# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Opt-in Rust engine backend for the Phase 1 read paths (Project 14).

The default backend is the pure-Python reader, unchanged. ``set_engine("rust")``
or ``BIOHEADERS_ENGINE=rust`` (read once, at import) routes reading, validating
and verifying FASTA, GFA, FHP-FASTA and FHGFF3 headers and YAML/JSON metadata
through the ``fair-bioheaders-tools`` engine. Writers, exports, assessment,
FHGM model checks, JSON-LD and microdata stay in Python.

With the engine selected, verdicts, checksums and metadata values come from the
engine. When the engine reports a failure and the input can be read again, the
Python reader is replayed on the same bytes so that the exception class, its
message and a schema error's ``json_path`` stay exactly as they were; where the
Python reader accepts what the engine rejects (the deliberate decision-9
changes: ECMA-262 ``pattern`` and deterministic ``format: uri``), an
engine-derived exception of the same class is raised instead. Selecting the
engine when it is not installed, or is an incompatible version, raises
``ImportError``; there is no silent fallback.
"""

import io
import json
import os
from collections import deque

#: The engine ABI this toolkit release was built against (exact match while 0.x).
REQUIRED_ABI = "0.1"
#: Bytes of a non-seekable input kept for replaying a failure's message.
REPLAY_LIMIT = 64 * 2**20
BACKENDS = ("python", "rust")

_backend = "python"
_engines: dict = {}


def _check_installed():
    try:
        import fair_bioheaders_tools
    except ImportError as error:
        raise ImportError(
            "the rust backend needs the fair-bioheaders-tools engine "
            f"(ABI {REQUIRED_ABI}); install it with: pip install fair-bioheaders-tools"
        ) from error
    if fair_bioheaders_tools.ABI_VERSION != REQUIRED_ABI:
        raise ImportError(
            f"fair-bioheaders-tools {fair_bioheaders_tools.__version__} has engine ABI "
            f"{fair_bioheaders_tools.ABI_VERSION}; this toolkit needs ABI {REQUIRED_ABI}"
        )
    return fair_bioheaders_tools


def set_engine(name):
    """Select the backend for the Phase 1 read paths: ``"python"`` or ``"rust"``."""
    global _backend
    if name not in BACKENDS:
        raise ValueError(f"unknown engine {name!r}; use one of {', '.join(BACKENDS)}")
    if name == "rust":
        _check_installed()
    _backend = name


def engine():
    """The selected backend: ``"python"`` (default) or ``"rust"``."""
    return _backend


def active():
    return _backend == "rust"


#: Toolkit limit constants and the engine limits they set (FORMAT.md defaults).
_LIMITS = {
    "MAX_HEADER_BYTES": ("header_bytes", 2**20),
    "MAX_HEADER_LINES": ("header_lines", 10_000),
    "MAX_YAML_NODES": ("yaml_nodes", 20_000),
    "MAX_YAML_DEPTH": ("yaml_depth", 64),
    "MAX_METADATA_BYTES": ("metadata_bytes", 64 * 2**20),
}


def _native_engine():
    """The engine for the current draft lane and toolkit limits (cached)."""
    import bioheaders

    from . import selection

    lanes = ("fht",) if selection.draft_support_enabled() else ()
    limits = tuple(
        (name, getattr(bioheaders, constant)) for constant, (name, _) in _LIMITS.items()
    )
    key = (lanes, limits)
    if key not in _engines:
        defaults = {name: value for name, value in _LIMITS.values()}
        lower = {name: value for name, value in limits if value <= defaults[name]}
        higher = {name: value for name, value in limits if value > defaults[name]}
        _engines[key] = _check_installed().Engine(
            draft_lanes=lanes, limits=lower, raise_limits=higher
        )
    return _engines[key]


def _initial():
    value = os.environ.get("BIOHEADERS_ENGINE", "").strip().lower()
    if value:
        set_engine(value)


# ----------------------------------------------------------------- input


class _Tee:
    """Read ``stream`` in chunks while keeping up to REPLAY_LIMIT bytes."""

    def __init__(self):
        self.kept = bytearray()
        self.complete = True

    def keep(self, chunk):
        if self.complete:
            if len(self.kept) + len(chunk) > REPLAY_LIMIT:
                self.complete = False
                self.kept = bytearray()
            else:
                self.kept += chunk


def _run(stream, operation, container):
    """Run the engine on bytes, text or a readable stream.

    Returns ``(report, replay)`` where ``replay`` is the input bytes when they
    could be kept for replaying a failure, else None."""
    from . import read_chunks

    fht = _native_engine()
    if isinstance(stream, (bytes, bytearray, memoryview)):
        data = bytes(stream)
        return fht._run(operation, data, container), data
    if isinstance(stream, str):
        data = stream.encode("utf-8")
        return fht._run(operation, data, container), data
    tee = _Tee()
    with fht.stream(operation, container=container) as feed:
        for chunk in read_chunks(stream):
            tee.keep(chunk)
            feed.feed(chunk)
        report = feed.finish()
    # Replay a stream as a stream: the Python reader size-checks streams only.
    return report, (io.BytesIO(bytes(tee.kept)) if tee.complete else None)


def _errors(report, layers):
    return [
        d for d in report.diagnostics if d.severity == "error" and d.layer in layers
    ]


def _raise_engine(diagnostic, schema=None):
    """An exception of the class the Python reader raises for this layer."""
    from . import NonFiniteValueError, selection

    if diagnostic.code == "V4.unsupported-version":
        parsed = selection.parse(schema)
        raise selection.UnsupportedSchemaVersion(schema, parsed[0] if parsed else "FHR")
    if diagnostic.rule == "R13":
        raise NonFiniteValueError(diagnostic.message)
    if diagnostic.layer == "schema":
        raise _validation_error(diagnostic)
    raise ValueError(diagnostic.message)


def _validation_error(diagnostic):
    from jsonschema.exceptions import ValidationError

    path = deque()
    pointer = diagnostic.json_pointer or ""
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        path.append(int(part) if part.isdigit() else part)
    validator = diagnostic.rule if diagnostic.rule in ("R4", "C1") else "pattern"
    message = diagnostic.message
    if diagnostic.rule == "R4" and not message.startswith("R4:"):
        message = f"R4: {message}"
    return ValidationError(
        message, validator=validator, validator_value=True, path=path
    )


def _trace(event, diagnostic):
    """Record a divergence (engine rejects, Python reader accepts) when
    ``BIOHEADERS_ENGINE_TRACE`` names a file; evidence for Tools#208 FR-062."""
    target = os.environ.get("BIOHEADERS_ENGINE_TRACE")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "event": event,
                        "code": diagnostic.code,
                        "rule": diagnostic.rule,
                        "message": diagnostic.message,
                    }
                )
                + "\n"
            )


def _replay(python_reader, replay, diagnostic):
    """Replay the Python reader for its exact exception; fall back to the
    engine's diagnostic when Python accepts or the bytes are gone."""
    if replay is not None:
        python_reader(replay)  # raises the reference exception if Python agrees
        _trace("python-accepted", diagnostic)
    _raise_engine(diagnostic)


def _metadata(report):
    """Engine metadata as the Python reader returns it."""
    return report.metadata


# --------------------------------------------------------- the read hooks


def input_header(record, stream, prefix, gff3, python_reader):
    """``fhr._input_header`` through the engine (framing and YAML only)."""
    container = "fasta" if prefix == ";~" else ("gff3" if gff3 else "gfa")
    report, replay = _run(stream, "validate", container)
    errors = _errors(report, ("framing", "yaml"))
    if errors:
        _replay(python_reader, replay, errors[0])
    return _install(record, _metadata(report))


def input_metadata(record, stream, json_input, python_reader):
    """``fhr.input_yaml`` / ``fhr.input_json`` through the engine."""
    container = "metadata-json" if json_input else "metadata-yaml"
    report, replay = _run(stream, "validate", container)
    errors = _errors(report, ("framing", "yaml"))
    if errors:
        _replay(python_reader, replay, errors[0])
    return _install(record, _metadata(report))


def _install(record, metadata):
    if not isinstance(metadata, dict):
        raise ValueError("FHR metadata must be an object with string keys")
    record.__dict__.clear()
    record.__dict__.update(metadata)


def validate(record, python_validate):
    """``fhr.fhr_validate`` through the engine (selection, schema, R4, C1).

    Success needs the engine's ``valid`` outcome: every required layer passed.
    Any other outcome (an error in any layer, including a framing-layer limit
    such as ``metadata_bytes`` on the serialised record, or a required layer
    that did not run) raises: the Python reader's exception when it rejects
    the record too, else the engine's first error."""
    data = record.__dict__
    try:
        text = json.dumps(data, allow_nan=False)
    except (TypeError, ValueError):
        return python_validate()  # not JSON data: the Python checks report it
    report = _native_engine()._run("validate", text.encode("utf-8"), "metadata-json")
    if report.valid:
        return None
    error = report.first_error()
    python_validate()  # raises the reference exception when Python agrees
    if error is None:  # not reachable: a non-valid outcome carries an error
        raise ValueError(f"metadata validation outcome: {report.outcome}")
    _trace("python-accepted", error)
    _raise_engine(error, data.get("schema"))


def verify(path, kind, open_input, python_verify):
    """The ``verify`` command's scan, parse, validation and checksum through the
    engine. Returns ``(metadata, warnings)`` for the CLI's output, where
    ``warnings`` are the engine's R11 and FHGFF3 directive warnings in order."""
    container = {"fasta": "fasta", "gfa": "gfa", "gff3": "gff3"}[kind]
    if path != "-" and os.path.isfile(path):
        # The engine reads (and decompresses) the file itself: no Python loop.
        report = _native_engine().verify(path, container=container)
    else:
        with open_input(path) as stream:
            report, _ = _run(stream, "verify", container)
    if not report.valid:
        error = report.first_error()
        if path != "-":
            python_verify()  # raises the reference exception when Python agrees
            _trace("python-accepted", error)
        if error.layer == "checksum" and error.code == "R3.checksum-mismatch":
            raise ValueError("Checksum verification failed")
        _raise_engine(error, (report.metadata or {}).get("schema"))
    warnings = [
        d.message
        for d in report.warnings()
        if d.code in ("R11.record-marker", "FHGFF3.directive-mismatch")
    ]
    return report.metadata, warnings


_initial()
