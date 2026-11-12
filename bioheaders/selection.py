# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Choose the schema a record is validated against from its ``schema`` URL.

This implements FAIR-bioHeaders-Specification docs/SCHEMA-VERSIONS.md (rules V1-V5):

- V1: the raw-main URL of ``fhr.json``, ``fhp.json`` or ``fhgff3.json`` selects the
  bundled copy of that type's schema on FAIR-bioHeaders-Specification ``main``;
- V2, V3: a release's raw tag URL, or ``https://w3id.org/fair-bioheaders/<type>/vX.Y.Z``,
  selects the bundled copy of that release's schema;
- V4: a release this package does not bundle, a release without that header type,
  or a raw URL with any other ref raises :class:`UnsupportedSchemaVersion`;
- V5: any other value is FHR, validated against the current FHR schema;
- V6 (compatibility): an FHR record citing the raw-main ``fhr.json`` URL whose
  ``schemaVersion`` is the number 1 (``1`` or ``1.0``, not the string ``"1"`` or a
  boolean) is an FHR 1 record written before v0.4.0, read against the bundled v0.3.1
  schema; the citation is deprecated (:data:`FHR1_WARNING`), not invalid.

Rules V1-V5 look only at the ``schema`` value (:func:`select`); V6 also needs the
record's ``schemaVersion``, so code that has the record uses :func:`select_record`.

Schemas are never fetched; ``schemas/bundled.json`` lists the bundled copies.

Rule V5 also has a toolkit-side convenience check (FAIR-bioHeaders-Tools#125, not a
spec rule): :func:`near_miss` recognises a V5 value that carries a FAIR-bioHeaders
URL prefix yet matches no rule, and :func:`near_miss_warning` words the
informational warning ``bioheaders.schema_warnings`` appends for it. Nothing about
V5 changes: the record is still read as FHR and stays as valid or invalid as before.

**Draft-lane exception (toolkit prep, not a spec rule).** FHT has no released
contract: its development schema lives on ``main`` of the FHT-Specification
repository, is absent from the shared specification's ``versions.json``, and by
published rules V1-V5 a record citing it is read as FHR (with the near-miss
warning). While that is the only spec-conformant behaviour, the toolkit can
optionally recognise exactly one draft value — the raw-main ``fht.json`` URL of
FHT-Specification — when the operator opts in with
``BIOHEADERS_EXPERIMENTAL_FHT=1`` (:func:`draft_support_enabled`). This is a
preview of, not a substitute for, FHT publication, and it needs shared
SCHEMA-VERSIONS coordination before it can become default behaviour
(FAIR-bioHeaders-Tools docs/FHT-SELECTION-DESIGN.md, FHT-Specification#9).
"""

import json
import os
import re
import warnings
from importlib.resources import files

# Raw URLs under either name of the specification repository: FAIR-bioHeaders-
# Specification since its #108, or FHR-Specification before (a supported alias).
RAW = re.compile(
    r"https://raw\.githubusercontent\.com/FAIR-bioHeaders/"
    r"(?:FHR|FAIR-bioHeaders)-Specification/(.+?)/(fhr|fhp|fhgff3)\.json"
)
W3ID = re.compile(
    r"https://w3id\.org/fair-bioheaders/(fhr|fhp|fhgff3)/(v[0-9]+\.[0-9]+\.[0-9]+)/?"
)
RELEASE = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
TYPES = {"fhr": "FHR", "fhp": "FHP", "fhgff3": "FHGFF3"}
UNSUPPORTED = "unsupported schema version"
# The prefixes only FAIR-bioHeaders URLs use; a value starting with one of these
# and matching no rule is a near-miss (see ``near_miss`` below).
W3ID_PREFIX = "https://w3id.org/fair-bioheaders/"
RAW_PREFIX = "https://raw.githubusercontent.com/FAIR-bioHeaders/"


def _read(name):
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


BUNDLED = json.loads(_read("schemas/bundled.json"))
_CACHE: dict[str, dict] = {}


# Rule V6: the last FHR 1 release, and the warning for records it applies to.
FHR1_RELEASE = "v0.3.1"
FHR1_URL = f"{W3ID_PREFIX}fhr/{FHR1_RELEASE}"
FHR1_WARNING = (
    f"schemaVersion 1 via the raw-main schema URL is read as FHR 1 ({FHR1_RELEASE}); "
    f'cite {FHR1_URL} or move to schemaVersion "2.0"'
)

# Rule V5 near-miss (FAIR-bioHeaders-Tools#125): a ``schema`` value under one of the
# FAIR-bioHeaders URL prefixes that matches no rule V1-V4 form is usually a mistyped
# schema URL — the w3id path form, another header type's file, a non-schema file such
# as ``core.yaml``, or a mistyped tag — and is silently read as FHR. ``near_miss``
# flags those values so the CLI and the assess report can say so; arbitrary
# third-party URLs (profile citations) are not near-misses and stay silent. The
# caveat recorded with maintainers: a future profile (FAIR-bioHeaders-Specification
# #51/#56) may legitimately be cited under these very prefixes, so the warning is
# informational — it explains how the record is read and never calls the value
# invalid, and it changes no selection, no validity and no exit code.
NEAR_MISS_PREFIXES = (W3ID_PREFIX, RAW_PREFIX)
# A near-miss path naming another header type's file. FHT is included although it
# has no released contract: unless the draft lane is enabled (see FHT_DRAFT_RAW),
# such a value is read as FHR, and the warning must never suggest that an FHT (or
# FHP) release URL "works" for that file.
NEAR_MISS_TYPES = {"fhp": "FHP", "fhgff3": "FHGFF3", "fht": "FHT"}
NEAR_MISS_TYPE = re.compile(r"(?:^|[/._-])(fhp|fhgff3|fht)(?:[/._-]|$)")

# Draft lane (see the module docstring): the one citation recognised only while
# draft support is enabled. Deliberately NOT added to TYPES/RAW — those encode
# the published rules V1-V3 for the shared specification repository (under
# either of its names), and FHT has no release, no w3id alias and no entry in
# schemas/versions.json. Only the literal raw-main form is recognised; a
# FHT-Specification tag URL or a w3id ``…/fht/vX.Y.Z`` URL does not exist as a
# published target and stays rule V5 with its near-miss warning, even when the
# gate is open.
DRAFT_ENV = "BIOHEADERS_EXPERIMENTAL_FHT"
FHT_DRAFT_RAW = re.compile(
    r"https://raw\.githubusercontent\.com/FAIR-bioHeaders/"
    r"FHT-Specification/main/fht\.json"
)


class ExperimentalDraftWarning(UserWarning):
    """FHT support reads an unreleased draft contract and may change before
    FHT publication (FHT-Specification#9)."""


def draft_support_enabled():
    """Whether the operator opted in to the FHT draft lane with
    ``BIOHEADERS_EXPERIMENTAL_FHT`` set to 1, true, yes or on (case-insensitive)."""
    return os.environ.get(DRAFT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def draft_entry(header_type_name):
    """The ``drafts`` registry entry of ``schemas/bundled.json``, or None."""
    return BUNDLED.get("drafts", {}).get(header_type_name)


def _draft_file(kind):
    entry = draft_entry(kind)
    if entry is None:  # Registry drift: parse() named a draft nobody bundled.
        raise UnsupportedSchemaVersion(FHT_DRAFT_RAW.pattern, kind)
    if entry.get("status") != "draft":
        raise ValueError(f"bundled draft registry entry for {kind} lacks status: draft")
    return entry["file"]


def _warn_draft():
    warnings.warn(
        "FHT support is experimental and reads the draft contract on "
        "FHT-Specification main (no released schema, no w3id alias); selection, "
        "messages and the contract itself may change before publication "
        "(FHT-Specification#9)",
        ExperimentalDraftWarning,
        stacklevel=4,
    )


def draft_warning(value):
    """The informational warning for a citation the draft lane just recognised,
    or None. Like every ``schema_warnings`` message it changes no validity and
    no exit code; it exists because a draft citation is development material,
    not a published contract, and every run must say so."""
    if (
        draft_support_enabled()
        and isinstance(value, str)
        and FHT_DRAFT_RAW.fullmatch(value)
    ):
        return (
            f"schema {value} selects the bundled FHT draft contract "
            "(development only, not a released schema; experimental opt-in via "
            f"{DRAFT_ENV}, see docs/FHT-SELECTION-DESIGN.md)"
        )
    return None


class UnsupportedSchemaVersion(ValueError):
    """The ``schema`` URL names a version this package does not bundle (rule V4)."""

    def __init__(self, value, header_type):
        self.value, self.header_type = value, header_type
        super().__init__(
            f"{UNSUPPORTED}: {value} (this tool has {header_type} schemas for "
            f"{', '.join(supported(header_type))})"
        )


def supported(header_type):
    """The releases (and ``main``) whose ``header_type`` schema is bundled."""
    if header_type == "FHT":  # draft lane only; never a released schema
        return ["main (draft, experimental)"]
    current = BUNDLED["current"]["release"]
    names = [f"main ({current})" if current else "main"]
    names += [tag for tag, types in BUNDLED["releases"].items() if header_type in types]
    return names


def parse(value):
    """Return ``(header type, ref)`` for a FAIR-bioHeaders schema URL, else None.

    ``ref`` is the literal path segment after the repository name: ``"main"``, a
    release tag, or another raw GitHub ref. Multi-segment refs such as
    ``refs/tags/v0.4.0`` are kept whole, so only the short ``main`` and release
    tag forms select a schema (rule V4 rejects the rest)."""
    if not isinstance(value, str):
        return None
    raw = RAW.fullmatch(value)
    if raw:
        return TYPES[raw.group(2)], raw.group(1)
    w3id = W3ID.fullmatch(value)
    if w3id:
        return TYPES[w3id.group(1)], w3id.group(2)
    if draft_support_enabled() and FHT_DRAFT_RAW.fullmatch(value):
        return "FHT", "main"
    return None


def header_type(value):
    """The header type a ``schema`` value names: FHP, FHGFF3, (draft lane, when
    enabled) FHT, or (rule V5) FHR."""
    parsed = parse(value)
    return parsed[0] if parsed else "FHR"


def near_miss(value):
    """Whether ``value`` is read as FHR by rule V5 but looks like a FAIR-bioHeaders URL.

    True when the value matches none of the rules V1-V3 (so :func:`parse` returns
    ``None``; a value that matches their form but names an unbundled release is V4
    and fails loudly, never silently) and starts with one of the
    :data:`NEAR_MISS_PREFIXES`, compared case-insensitively like GitHub org and repo
    names. Any other value — a third-party profile URL, a non-https or foreign-scheme
    URL, a missing or non-string ``schema`` — is False and stays silent."""
    if not isinstance(value, str) or parse(value) is not None:
        return False
    lowered = value.lower()
    return any(lowered.startswith(prefix.lower()) for prefix in NEAR_MISS_PREFIXES)


def current_fhr_url():
    """The canonical w3id URL of the bundled current FHR release (from
    ``schemas/bundled.json``), or ``None`` when main is ahead of every release."""
    release = BUNDLED["current"]["release"]
    return f"{W3ID_PREFIX}fhr/{release}" if release else None


def near_miss_warning(value):
    """The informational rule V5 warning for a near-miss ``value``, or ``None``.

    Mirrors the wording of FAIR-bioHeaders-Tools#125. The suggested URL is derived
    from the bundled version registry, never hard-coded. A value naming another
    header type's file is reported as read as FHR and gets no URL suggestion: the
    released URL of the named type does not make that file a schema citation, and
    no FHT contract is released."""
    if not near_miss(value):
        return None
    named = NEAR_MISS_TYPE.search(value.lower())
    if named:
        kind = NEAR_MISS_TYPES[named.group(1)]
        return (
            f"schema {value} is not a FAIR-bioHeaders schema URL; read as FHR, "
            f"not {kind}, against the current schema (rule V5)"
        )
    message = (
        f"schema {value} is not a FAIR-bioHeaders schema URL; read as FHR "
        "against the current schema (rule V5)"
    )
    suggestion = current_fhr_url()
    return f"{message}; did you mean {suggestion}?" if suggestion else message


def is_fhr1_version(version):
    """Whether ``version`` is the FHR 1 ``schemaVersion``: the number 1.

    ``1`` and ``1.0`` are the same JSON number (FHR 1 examples wrote ``1.0``). The
    string ``"1"`` was never valid FHR 1, and a boolean is not a number, even though
    Python's ``True == 1``."""
    return (
        isinstance(version, (int, float))
        and not isinstance(version, bool)
        and version == 1
    )


def reads_as_fhr1(metadata):
    """Rule V6: whether ``metadata`` cites raw-main ``fhr.json`` with schemaVersion 1."""
    return (
        isinstance(metadata, dict)
        and parse(metadata.get("schema")) == ("FHR", "main")
        and is_fhr1_version(metadata.get("schemaVersion"))
    )


def _file(value):
    parsed = parse(value)
    if parsed is None:
        return "FHR", "main", BUNDLED["current"]["files"]["FHR"]
    kind, ref = parsed
    if kind == "FHT":  # draft lane: only "main" can be parsed (see FHT_DRAFT_RAW)
        _warn_draft()
        return kind, ref, _draft_file(kind)
    if ref == "main":
        return kind, ref, BUNDLED["current"]["files"][kind]
    if RELEASE.fullmatch(ref) and kind in BUNDLED["releases"].get(ref, {}):
        return kind, ref, BUNDLED["releases"][ref][kind]
    raise UnsupportedSchemaVersion(value, kind)


def select(value):
    """Return ``(header type, release or "main", schema)`` for a ``schema`` value.

    Raises :class:`UnsupportedSchemaVersion` for rule V4."""
    kind, ref, name = _file(value)
    if name not in _CACHE:
        _CACHE[name] = json.loads(_read(name))
    return kind, ref, _CACHE[name]


def bundled_file(value):
    """The bundled file name the ``schema`` value selects (raises like :func:`select`)."""
    return _file(value)[2]


def _record_file(metadata):
    if reads_as_fhr1(metadata):
        return "FHR", FHR1_RELEASE, BUNDLED["releases"][FHR1_RELEASE]["FHR"]
    return _file(metadata.get("schema") if isinstance(metadata, dict) else None)


def select_record(metadata):
    """Return ``(header type, release or "main", schema)`` for a record (V1-V6).

    Like :func:`select` on the record's ``schema``, except that rule V6 reads an FHR 1
    record citing raw-main as release v0.3.1."""
    kind, ref, name = _record_file(metadata)
    if name not in _CACHE:
        _CACHE[name] = json.loads(_read(name))
    return kind, ref, _CACHE[name]


def record_file(metadata):
    """The bundled file name a record selects (raises like :func:`select`)."""
    return _record_file(metadata)[2]
