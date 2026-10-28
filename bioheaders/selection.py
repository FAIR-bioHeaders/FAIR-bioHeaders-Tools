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
"""

import json
import re
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


def _read(name):
    return files(__package__).joinpath(name).read_text(encoding="utf-8")


BUNDLED = json.loads(_read("schemas/bundled.json"))
_CACHE: dict[str, dict] = {}


# Rule V6: the last FHR 1 release, and the warning for records it applies to.
FHR1_RELEASE = "v0.3.1"
FHR1_URL = f"https://w3id.org/fair-bioheaders/fhr/{FHR1_RELEASE}"
FHR1_WARNING = (
    f"schemaVersion 1 via the raw-main schema URL is read as FHR 1 ({FHR1_RELEASE}); "
    f'cite {FHR1_URL} or move to schemaVersion "2.0"'
)


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
    return None


def header_type(value):
    """The header type a ``schema`` value names: FHP, FHGFF3 or (rule V5) FHR."""
    parsed = parse(value)
    return parsed[0] if parsed else "FHR"


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
