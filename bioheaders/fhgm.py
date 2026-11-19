# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Draft gene-model records FHGM (FAIR-bioHeaders-Tools#135) - PREP, gated.

FHGM describes one contributed gene model inside an annotation file. It is not a
header family of its own: its records ride the released FHGFF3 header under the
single top-level extension key ``x-fhgm-models``
(FAIR-bioHeaders-Specification docs/FORMAT.md R15), so a carrier keeps its
released FHGFF3 identity and its exact-byte checksum. FHGM itself has **no
released contract**: no ``schemaVersion``, no schema URL, no
``schemas/versions.json`` row, no w3id or tag URL and no support claim - selection
rule V7 keeps it that way until the shared publication PR lands. This module reads
development bytes pinned by commit and SHA-256 under ``drafts.FHGM`` in
``schemas/bundled.json``, and only when the operator opts in with
``BIOHEADERS_EXPERIMENTAL_FHGM=1``; the default path is unchanged.

The rules, matched to the owning checker (``FHGM-Specification``
``development/model/validate_fhgm.py`` at the commit recorded in the registry -
the reference this lane is matched to, not code it imports):

* **K1 transport** - the carrier must cite a registered released FHGFF3 base
  (``bases`` below, mirrored from the pinned ``base-schemas.json`` registry) and
  carry a non-empty ``x-fhgm-models`` array. Selection, never substitution: the
  cited URL chooses the bytes, and the selected release's own schema then judges
  the stated ``schemaVersion``. A citation no registered base answers to - raw
  main, a superseded release - is refused, never evaluated against other bytes.
* **K2 record shape** - every record against the pinned native record contract,
  the whole record at once, before any rule reads one of its fields.
* **K3 identity** - ``modelId`` uniqueness after Unicode NFC normalisation,
  before any per-record rule, because a duplicate makes a pointer's target
  unselectable whatever else is wrong with the colliding records.
* **K4 target** - ``featureId`` resolves, percent-decoded from the raw row bytes
  and decoded as **strict** UTF-8 (a malformed escape or an undecodable sequence
  is a refusal, never a U+FFFD substitution that could accidentally match a
  record), to exactly one local root ``gene``/``SO:0000704`` row with no
  ``Parent`` attribute. The record's ``featureId`` is compared as written, and an
  empty ``Parent=`` value leaves a row's root status indeterminate, so it is
  refused rather than guessed.
* **K5 reference** - the record reference shares at least one comparable form
  with the file genome link and never contradicts it.
* **K6 history** - a ``predecessor`` pointer resolves against explicitly supplied
  prior snapshots only. A resolvable pointer identifies a predecessor record; it
  never asserts curator acceptance.

The layers stay apart, which is what #135 asks for and what the owning suite
records per vector: :class:`FHGMReport` carries the released FHGFF3 header
verdict, the file-bound checksum verdict, the FHGM model verdict and the GFF3
feature-layer verdict as separate fields, and a layer that could not be run
reports ``not-run`` with its reason - never a pass.
"""

import hashlib
import json
import os
import re
import unicodedata
import warnings
from importlib.resources import files
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from . import HEADER, header_text, load_yaml, selection, sequence_parts
from .schema_validator import draft_validator, validator
from .selection import shown

#: The opt-in gate for this lane, beside - and independent of - FHT's
#: ``BIOHEADERS_EXPERIMENTAL_FHT``: opening one lane never opens the other.
DRAFT_ENV = "BIOHEADERS_EXPERIMENTAL_FHGM"

#: The one top-level extension key that carries FHGM records (docs/FORMAT.md R15).
MODELS = "x-fhgm-models"

#: The owning development repository. Every draft row names it, never a release.
REPOSITORY = "FAIR-bioHeaders/FHGM-Specification"

PASS = "pass"
REJECT = "reject"
NOT_RUN = "not-run"
VERIFY = "verify"
STALE = "stale"

RESOLVABLE = "resolvable"
UNRESOLVABLE = "unresolvable"

GENE_TYPES = (b"gene", b"SO:0000704")

#: The draft lane reads a carrier - and each supplied predecessor - into memory to
#: index its feature rows, because K4 resolves a record against the *whole* row
#: inventory and the owning checker works the same way. This is the bound: above it
#: the released verdict still runs and the model layer reports ``not-run`` with its
#: reason, so opting in to a draft lane can never turn into an unbounded read of a
#: multi-gigabyte annotation.
#:
#: ``BIOHEADERS_FHGM_MAX_BYTES`` shrinks the bound for a test or a memory-limited
#: run; a smaller bound can only report less, never more, because every byte above
#: it turns the model layer into ``not-run``.
MAX_LANE_BYTES = int(os.environ.get("BIOHEADERS_FHGM_MAX_BYTES", "") or 256 * 2**20)

# The feature row's ninth column, and the byte that separates its attributes.
_ATTRIBUTES = 8
_SEPARATOR = b"="


class FHGMLaneError(ValueError):
    """The lane could not report a model verdict at all (unreadable header, digest
    drift, a base release this build does not bundle). A refusal of the *lane*,
    distinct from a model-rule rejection of the *record*: a model rejection is a
    ``reject`` verdict inside an :class:`FHGMReport`, never an exception, so a
    caller can still print every layer."""


class ModelCheckError(FHGMLaneError):
    """A draft FHGM rule rejected the snapshot. ``rule`` names it (K1-K6, or B1
    for the boundary beneath them) and the message is the reported reason."""

    def __init__(self, message: str, rule: str) -> None:
        super().__init__(message)
        self.rule = rule


class FHGMDraftWarning(UserWarning):
    """FHGM support reads unreleased development bytes and may change before FHGM
    publication (FAIR-bioHeaders-Specification#204, FAIR-bioHeaders-Tools#135)."""

    header_type = "FHGM"  # the CLI's message label for it


def draft_support_enabled() -> bool:
    """Whether the operator opted in to the FHGM draft lane with
    ``BIOHEADERS_EXPERIMENTAL_FHGM`` set to 1, true, yes or on (case-insensitive).

    The accepted values are the shared lane vocabulary
    (:func:`bioheaders.selection.environment_enabled`), so the FHGM gate cannot
    drift from the FHT gate."""
    return selection.environment_enabled(DRAFT_ENV)


def draft_entry() -> dict:
    """The ``drafts.FHGM`` registry row of ``schemas/bundled.json``, or ``{}``.

    Empty means this build ships no FHGM draft at all: the lane then reports
    itself unavailable instead of reading bytes nobody pinned."""
    return selection.draft_entry("FHGM") or {}


def carries_models(metadata: object) -> bool:
    """Whether ``metadata`` declares FHGM model records at all.

    A header without the key is a plain released FHGFF3 header: the lane must not
    run, must not warn and must not report anything for it."""
    return isinstance(metadata, dict) and MODELS in metadata


def pinned(kind: str) -> Tuple[str, bytes, dict]:
    """The bundled bytes of one pinned FHGM artifact, digest-checked on read.

    Returns ``(bundled name, raw bytes, registry row)``. Bytes whose recorded
    SHA-256 does not match are refused after a warning: a draft verdict computed
    from unpinned bytes must never be reported as the pinned contract's verdict
    (rule V7's provenance duty - the disclosure would name a commit and digest
    that do not describe the bytes actually used)."""
    row = (draft_entry().get("files") or {}).get(kind)
    if not row or not row.get("file"):
        raise FHGMLaneError(
            f"schemas/bundled.json carries no FHGM draft row for {kind!r}"
        )
    name = str(row["file"])
    raw = files("bioheaders").joinpath(name).read_bytes()
    recorded = row.get("sha256")
    actual = hashlib.sha256(raw).hexdigest()
    if recorded != actual:
        warnings.warn(
            f"the bundled FHGM {kind} bytes {name} have sha256 {actual}, not the "
            f"recorded {recorded}: the commit and digest named for them do not "
            "describe these bytes; reinstall the package or re-pin the draft",
            FHGMDraftWarning,
            stacklevel=3,
        )
        raise FHGMLaneError(
            f"the bundled FHGM {kind} bytes do not match their recorded digest"
        )
    return name, raw, row


def draft_warning() -> Optional[str]:
    """The rule V7 disclosure for bytes this lane just read, or None.

    It names each pinned artifact's commit and the SHA-256 *of those bytes*, and
    nothing else: no version of its own, no release URL, no support claim. The
    sibling libraries disclose the same pair in their draft lanes."""
    entry = draft_entry()
    rows = entry.get("files") or {}
    parts = [
        f"{kind} commit {row['revision']}, sha256 {row['sha256']} of those bytes"
        for kind, row in sorted(rows.items())
        if row.get("revision") and row.get("sha256")
    ]
    if not parts:
        return None
    suite = entry.get("suite") or {}
    tail = (
        f"; its suite is pinned apart from it at commit {suite['revision']}"
        if suite.get("revision")
        else ""
    )
    return (
        f"{MODELS} records were read against the bundled FHGM draft contract "
        f"({'; '.join(parts)}{tail}) - development bytes, no released schema, "
        f"opt-in via {DRAFT_ENV} (see docs/FHGM-DRAFT-LANE.md)"
    )


class ByteSink:
    """Every byte of one pass, kept whole up to a bound - then dropped.

    The draft lane needs the carrier's exact bytes after the released scan has
    streamed them, because K4 resolves a record against the complete feature-row
    inventory. This is how the CLI keeps them without a second read of a pipe: the
    scan's observer feeds each chunk here. Past ``limit`` the copy is released and
    :attr:`dropped` says so, because a bound that silently truncates would let a
    model verdict be computed over an incomplete inventory - the worse failure."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.dropped = False
        self._parts: List[bytes] = []
        self._size = 0

    def feed(self, chunk: bytes) -> None:
        if self.dropped:
            return
        self._size += len(chunk)
        if self._size > self.limit:
            self.dropped = True
            self._parts = []
            self._size = 0
            return
        self._parts.append(chunk)

    def bytes(self) -> Optional[bytes]:
        """The collected exact bytes, or None once the bound was passed."""
        return None if self.dropped else b"".join(self._parts)


# --- K1: the released base a carrier cites -----------------------------------


def base_registry() -> List[dict]:
    """The released FHGFF3 bases this lane accepts as a carrier.

    Rows mirror the owning repository's pinned ``base-schemas.json`` (its
    provenance is recorded under ``drafts.FHGM.registry``); each names one
    release's exact citation URLs, the SHA-256 of that release's bytes and the
    frozen snapshot of them this package already ships. A floating branch is
    never recorded here - released material is named by a tag."""
    rows = list(draft_entry().get("bases") or [])
    if not rows:
        raise FHGMLaneError(
            "schemas/bundled.json records no FHGM base registry, so the lane "
            "cannot say which released FHGFF3 bytes judge a carrier"
        )
    return rows


def base_for(cited: object) -> dict:
    """The registered base release the cited schema URL answers to, or a refusal."""
    if not isinstance(cited, str):
        raise ModelCheckError(
            "the carrier states no schema URL, so no FHGFF3 base release can be "
            "selected; a carrier must cite the released fhgff3.json it follows",
            "K1",
        )
    matches = [row for row in base_registry() if cited in row["schemaUrls"]]
    if len(matches) != 1:
        raise ModelCheckError(
            f"the carrier cites schema {shown(cited)}, which no registered FHGFF3 "
            f"base release answers to; the registered bases are "
            f"{', '.join(sorted(str(row['ref']) for row in base_registry()))}",
            "K1",
        )
    return matches[0]


def base_bytes(row: dict) -> Tuple[bytes, dict]:
    """The bundled bytes of one registered base, verified against the registry.

    The frozen snapshot's digest must equal the registry's: a carrier is judged
    by the release the registry names, and a snapshot that drifted is refused
    rather than silently used."""
    name = str(row["file"])
    raw = files("bioheaders").joinpath(name).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != row.get("sha256"):
        raise FHGMLaneError(
            f"the bundled FHGFF3 base {name} has sha256 {actual}, not the "
            f"{row.get('sha256')} the FHGM base registry records for "
            f"{row.get('ref')}: these are not the bytes that release names"
        )
    return raw, json.loads(raw.decode("utf-8"))


# --- reading a snapshot ------------------------------------------------------


def parse_snapshot(data: Union[bytes, bytearray]) -> dict:
    """The header document of a snapshot's exact bytes, before any validation.

    The same strict reader the released commands use: only the leading ``#~``
    block is header, FORMAT.md R12 scalar typing applies, and a broken header is
    a refusal rather than a partial read."""
    if not isinstance(data, (bytes, bytearray)):
        raise FHGMLaneError("FHGM reads exact file bytes; pass bytes, not text")
    lines = [
        header_text(line, b"#~")
        for kind, line in sequence_parts([bytes(data)], b"#~", gff3=True)
        if kind is HEADER
    ]
    try:
        header = load_yaml("\n".join(lines))
    except Exception as error:  # any reader refusal is an unreadable carrier
        raise ModelCheckError(
            f"the FHGFF3 header cannot be read: {error}", "B1"
        ) from error
    if not isinstance(header, dict):
        raise ModelCheckError("the FHGFF3 header metadata must be an object", "B1")
    return header


def records_of(header: dict) -> List[dict]:
    """The ``x-fhgm-models`` array, once K1 has established it must exist."""
    models = header.get(MODELS)
    if models is None:
        raise ModelCheckError(
            f"the carrier carries no {MODELS} key, so there is no FHGM snapshot",
            "K1",
        )
    if not isinstance(models, list):
        raise ModelCheckError(f"{MODELS} must be an array of model records", "K1")
    return models


# --- K4: the feature rows ----------------------------------------------------


_PERCENT = re.compile(b"%[0-9A-Fa-f]{2}")
_INCOMPLETE = re.compile(b"%([0-9A-Fa-f]?)$")
_BAD_ESCAPE = re.compile(b"%(?![0-9A-Fa-f]{2})")


def decode_row_id(value: bytes, where: str) -> bytes:
    """One raw ``ID`` attribute value, percent-decoded over bytes, strict UTF-8.

    Returns the decoded **bytes** (a record's ``featureId`` is encoded the same
    way for the comparison), and refuses: a malformed escape, a decoded value
    that is not valid UTF-8, and an empty value. Substituting U+FFFD would let a
    broken row identity collide with a record that happens to carry the
    replacement character, so nothing here ever replaces anything."""
    tail = _INCOMPLETE.search(value)
    if tail and not _PERCENT.fullmatch(tail.group(0)):
        raise ModelCheckError(
            f"a feature row declares a truncated percent escape in ID: "
            f"{shown(value.decode('utf-8', 'backslashreplace'))}",
            "K4",
        )
    if _BAD_ESCAPE.search(value):
        raise ModelCheckError(
            f"a feature row declares a malformed percent escape in ID: "
            f"{shown(value.decode('utf-8', 'backslashreplace'))}",
            "K4",
        )
    decoded = b""
    position = 0
    while position < len(value):
        if value[position : position + 1] == b"%":
            decoded += bytes([int(value[position + 1 : position + 3], 16)])
            position += 3
        else:
            decoded += value[position : position + 1]
            position += 1
    try:
        decoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelCheckError(
            f"{where} percent-decodes to bytes that are not valid UTF-8 ({error}): "
            "refusing to substitute a replacement character into a model identity",
            "K4",
        ) from error
    return decoded


class RowIndex:
    """Every ``ID`` the feature rows declare, with its type and root status.

    Attribute keys are matched exactly as written: ``Name=x; ID=toy-a`` has the
    key `` ID`` (leading space), which is not ``ID``, so that row declares no ID
    of its own. Only a percent-decoded value indexes a row; the raw encoded
    spelling never resolves."""

    def __init__(self, data: Union[bytes, bytearray]) -> None:
        self.rows: Dict[bytes, List[Tuple[bytes, bool]]] = {}
        for line in bytes(data).splitlines():
            if line == b"##FASTA":
                break
            if not line.strip() or line.startswith(b"#"):
                continue
            columns = line.split(b"\t")
            if len(columns) != 9:
                raise ModelCheckError(
                    "expected nine columns in each GFF3 feature row", "K4"
                )
            declared = []
            has_parent = False
            for attribute in columns[_ATTRIBUTES].split(b";"):
                key, separator, value = attribute.partition(_SEPARATOR)
                if key == b"ID":
                    if not separator or not value:
                        raise ModelCheckError(
                            "a feature row declares an empty ID= value, so its "
                            "identity is indeterminate",
                            "K4",
                        )
                    declared.append(decode_row_id(value, "a feature row ID"))
                elif key == b"Parent":
                    if not separator or not value:
                        raise ModelCheckError(
                            "a feature row declares an empty Parent= value, so "
                            "whether it is a root row is indeterminate",
                            "K4",
                        )
                    has_parent = True
            for identifier in declared:
                self.rows.setdefault(identifier, []).append((columns[2], has_parent))

    def targets(self, feature_id: str) -> List[Tuple[bytes, bool]]:
        """The rows declaring ``feature_id``, compared exactly as it is written."""
        try:
            wanted = feature_id.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ModelCheckError(
                f"featureId {shown(feature_id)} is not encodable as UTF-8 bytes "
                f"({error})",
                "K4",
            ) from error
        return self.rows.get(wanted, [])


# --- K5/K6: the genome link, as comparable keys ------------------------------


def assembly_keys(header: dict) -> Dict[str, str]:
    """The file's genome link as comparable keys."""
    keys: Dict[str, str] = {}
    reference = header.get("genomeReference")
    if isinstance(reference, dict):
        keys["accession"] = str(reference.get("accession"))
        keys["seqcol_id"] = str(reference.get("seqcol_id"))
    for parent in header.get("derivedFrom") or []:
        if (
            isinstance(parent, dict)
            and parent.get("headerType") == "FHR"
            and parent.get("relationship") == "annotates"
        ):
            keys["fhr_checksum"] = str(parent.get("checksum"))
    return keys


def reference_keys(model: dict) -> Dict[str, str]:
    """One record's own ``reference`` as comparable keys."""
    keys: Dict[str, str] = {}
    reference = model.get("reference") or {}
    genome = reference.get("genomeReference")
    if isinstance(genome, dict):
        keys["accession"] = str(genome.get("accession"))
        keys["seqcol_id"] = str(genome.get("seqcol_id"))
    if "annotates" in reference:
        keys["fhr_checksum"] = str(reference["annotates"])
    return keys


def links_conflict(left: Dict[str, str], right: Dict[str, str]) -> bool:
    return any(left[key] != right[key] for key in left.keys() & right.keys())


def links_match(left: Dict[str, str], right: Dict[str, str]) -> bool:
    return bool(left.keys() & right.keys()) and not links_conflict(left, right)


# --- one snapshot through K1-K5 ----------------------------------------------


class Snapshot:
    """A snapshot that passed K1-K5: its header, its records, its chosen base."""

    def __init__(self, header: dict, base: dict, models: Sequence[dict]) -> None:
        self.header = header
        self.base = base
        self.models = {str(model["modelId"]): model for model in models}

    @property
    def checksum(self) -> str:
        return str(self.header.get("checksum"))


def check_snapshot(
    data: Union[bytes, bytearray],
    transport,
    contract,
    rows: Optional[RowIndex] = None,
    checksum: Optional[str] = None,
) -> Snapshot:
    """K1-K5 over one snapshot's exact bytes; raises :class:`ModelCheckError`.

    ``checksum`` is the file-bound SHA-512/256 of these same bytes, recomputed by
    the caller. Passing it is how the B1 boundary is enforced: no model verdict
    exists over bytes whose own digest does not verify."""
    header = parse_snapshot(data)
    row = base_for(header.get("schema"))
    _, schema = base_bytes(row)
    for error in sorted(
        validator(schema).iter_errors(header), key=lambda e: str(e.path)
    ):
        raise ModelCheckError(
            f"the carrier does not satisfy the released FHGFF3 base it cites "
            f"({row['ref']}): {error.json_path}: {error.message}",
            "B1",
        )
    for error in sorted(transport.iter_errors(header), key=lambda e: str(e.path)):
        raise ModelCheckError(
            f"the carrier does not satisfy the FHGM transport overlay: "
            f"{error.json_path}: {error.message}",
            "K1",
        )
    if checksum is not None and checksum != header.get("checksum"):
        raise ModelCheckError(
            f"File checksum mismatch: the header states "
            f"{shown(header.get('checksum'))} and these bytes produce "
            f"{shown(checksum)}",
            "B1",
        )
    models = records_of(header)
    for position, model in enumerate(models):
        for error in sorted(contract.iter_errors(model), key=lambda e: str(e.path)):
            raise ModelCheckError(
                f"model record {position} is invalid under draft contract v0.1: "
                f"{error.json_path}: {error.message}",
                "K2",
            )
    check_unique_ids(models)
    inventory = rows if rows is not None else RowIndex(data)
    file_keys = assembly_keys(header)
    for model in models:
        check_target(model, inventory)
        check_reference(model, file_keys)
    return Snapshot(header, row, models)


def check_unique_ids(models: Sequence[dict]) -> None:
    """K3 (deviation D4): one NFC-normalised ``modelId`` per snapshot."""
    seen: Dict[str, List[dict]] = {}
    for model in models:
        seen.setdefault(unicodedata.normalize("NFC", str(model["modelId"])), []).append(
            model
        )
    for records in seen.values():
        if len(records) > 1:
            spellings = sorted({str(record["modelId"]) for record in records})
            detail = (
                f" ({len(spellings)} spellings equal under NFC normalisation)"
                if len(spellings) > 1
                else ""
            )
            raise ModelCheckError(
                f"Ambiguous model ID {spellings[0]!r}: {len(records)} records share "
                f"it in one snapshot{detail}",
                "K3",
            )


def check_target(model: dict, rows: RowIndex) -> None:
    """K4: ``featureId`` resolves to exactly one local root gene row."""
    model_id = str(model["modelId"])
    feature_id = str(model["featureId"])
    found = rows.targets(feature_id)
    if len(found) != 1 or found[0][0] not in GENE_TYPES:
        raise ModelCheckError(
            f"Model {model_id!r} must target one local gene row: {feature_id!r}",
            "K4",
        )
    if found[0][1]:
        raise ModelCheckError(
            f"Model {model_id!r} must target one local gene row: {feature_id!r} has "
            "a Parent attribute, so it is not a root gene row",
            "K4",
        )


def check_reference(model: dict, file_keys: Dict[str, str]) -> None:
    """K5: comparable with, and never contradicting, the file genome link."""
    model_id = str(model["modelId"])
    keys = reference_keys(model)
    if links_conflict(keys, file_keys):
        raise ModelCheckError(
            f"Model {model_id!r} carries a reference that contradicts the file "
            "genome link",
            "K5",
        )
    if not links_match(keys, file_keys):
        raise ModelCheckError(
            f"Model {model_id!r} has no reference form comparable with the file "
            "genome link",
            "K5",
        )


# --- K6: a revision pointer, against supplied history only -------------------


def resolve_predecessor(
    model_id: str,
    model: dict,
    carrier: Snapshot,
    history: Dict[str, Snapshot],
) -> Tuple[str, str]:
    """``(verdict, detail)`` for one revision pointer. Never raises.

    Only the supplied ``history`` resolves anything: an unsupplied snapshot, the
    current file itself, a pointer naming another model (deviation D2), a version
    the predecessor does not record, a revision reusing the predecessor version,
    a recorded successor skipped over inside the supplied set (deviation D3), or a
    missing assembly/record link are all ``unresolvable``. ``resolvable``
    identifies a predecessor record and nothing more."""
    pointer = model["predecessor"]
    snapshot = str(pointer["annotationChecksum"])
    if snapshot == carrier.checksum or snapshot not in history:
        return (
            UNRESOLVABLE,
            "the predecessor snapshot is the current file or was not supplied",
        )
    if str(pointer["modelId"]) != model_id:
        return (
            UNRESOLVABLE,
            f"the pointer names another model ID {str(pointer['modelId'])!r}",
        )
    prior = history[snapshot]
    prior_model = prior.models.get(model_id)
    if prior_model is None:
        return UNRESOLVABLE, f"the predecessor snapshot has no model {model_id!r}"
    if prior_model["modelVersion"] != pointer["modelVersion"]:
        return UNRESOLVABLE, (
            f"the predecessor records version "
            f"{prior_model['modelVersion']!r}, not {pointer['modelVersion']!r}"
        )
    if prior_model["modelVersion"] == model["modelVersion"]:
        return UNRESOLVABLE, "the revision reuses the predecessor model version"
    for other_checksum, other in history.items():
        if other_checksum == snapshot:
            continue
        other_model = other.models.get(model_id) or {}
        other_pointer = other_model.get("predecessor")
        if (
            other_pointer
            and other_model
            and other_pointer["annotationChecksum"] == snapshot
            and other_pointer["modelId"] == model_id
            and other_pointer["modelVersion"] == pointer["modelVersion"]
            and other_model["modelVersion"] != prior_model["modelVersion"]
            and links_match(assembly_keys(other.header), assembly_keys(prior.header))
            and links_match(reference_keys(other_model), reference_keys(prior_model))
        ):
            return UNRESOLVABLE, (
                "the pointed record already has a recorded successor in supplied "
                f"snapshot {other_checksum[:8]}..."
            )
    if not links_match(assembly_keys(carrier.header), assembly_keys(prior.header)):
        return UNRESOLVABLE, "no matching assembly link with the predecessor snapshot"
    if not links_match(reference_keys(model), reference_keys(prior_model)):
        return UNRESOLVABLE, "no matching record reference with the predecessor record"
    return (
        RESOLVABLE,
        f"predecessor {snapshot[:8]}... version {pointer['modelVersion']!r}",
    )


# --- the layered report ------------------------------------------------------


class FHGMReport:
    """One lane run, with every layer kept apart.

    ``header`` is the *released* FHGFF3 verdict on this carrier, ``checksum`` the
    file-bound SHA-512/256 verdict, ``model`` the FHGM draft verdict and
    ``feature`` what the GFF3 syntax/biology checker would say - a layer this
    package never runs, since that belongs to ``gff3-validator``. ``reason`` and
    ``rule`` describe a ``reject`` or a ``not-run``; ``pointers`` holds one verdict
    per revision claim. No layer is ever summed into another, and a ``not-run``
    layer is never presented as a pass."""

    def __init__(self) -> None:
        self.model: str = NOT_RUN
        self.header: str = NOT_RUN
        self.checksum: str = NOT_RUN
        self.feature: str = NOT_RUN
        self.feature_reason: str = (
            "not run here: GFF3 syntax and biology belong to gff3-validator"
        )
        self.rule: Optional[str] = None
        self.reason: Optional[str] = None
        self.base: Optional[str] = None
        self.base_sha256: Optional[str] = None
        self.records: Optional[int] = None
        self.pointers: List[Dict[str, str]] = []
        self.history: int = 0
        self.disclosure: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Whether the model layer passed. The other layers say their own piece."""
        return self.model == PASS

    def refused(self, rule: str, reason: str) -> "FHGMReport":
        """Mark the model layer rejected by ``rule`` for ``reason`` (chainable)."""
        self.model = REJECT
        self.rule = rule
        self.reason = reason
        return self

    def layers(self) -> Dict[str, object]:
        """The layered result, as data (what ``--json`` and the tests read)."""
        return {
            "model": self.model,
            "header": self.header,
            "checksum": self.checksum,
            "feature": self.feature,
            "rule": self.rule,
            "reason": self.reason,
            "base": self.base,
            "base_sha256": self.base_sha256,
            "records": self.records,
            "pointers": self.pointers,
            "history": self.history,
            "feature_reason": self.feature_reason,
            "disclosure": self.disclosure,
        }

    def lines(self) -> List[str]:
        """The report block, one line per layer, every line prefixed ``FHGM``.

        Printing is where the separation is visible: the FHGFF3 header line and
        the GFF3 feature line are stated as what they are, and the FHGM verdict
        never borrows their authority."""
        records = "unread" if self.records is None else str(self.records)
        out = [
            f"FHGM draft lane: model result: {self.model}"
            + (f" ({self.rule}): {self.reason}" if self.reason else ""),
            f"FHGM draft lane: released FHGFF3 header: {self.header}",
            f"FHGM draft lane: file checksum: {self.checksum}",
            f"FHGM draft lane: GFF3 feature syntax/biology: {self.feature} "
            f"- {self.feature_reason}",
            f"FHGM draft lane: base: {self.base or 'not selected'}"
            + (f" (sha256 {self.base_sha256})" if self.base_sha256 else ""),
            f"FHGM draft lane: records: {records}; prior snapshots supplied: "
            f"{self.history}",
        ]
        for pointer in self.pointers:
            out.append(
                f"FHGM draft lane: model {pointer['modelId']!r} predecessor is "
                f"{pointer['verdict']}: {pointer['detail']}"
            )
        if self.pointers:
            out.append(
                "FHGM draft lane: a resolvable pointer identifies a predecessor "
                "record; it never asserts curator acceptance"
            )
        if self.disclosure:
            out.append(f"FHGM draft lane: {self.disclosure}")
        return out

    def text(self) -> str:
        return "\n".join(self.lines())


def check_models(
    data: Union[bytes, bytearray],
    predecessors: Iterable[Union[bytes, bytearray]] = (),
) -> FHGMReport:
    """Run the FHGM draft lane over one carrier's exact bytes.

    ``predecessors`` are prior snapshots' exact bytes and the *only* history a
    revision pointer resolves against (K6); supplying none makes a pointer claim
    ``unresolvable``, which is a report, never a guess about a file nobody handed
    over.

    The file-bound SHA-512/256 is recomputed here with the toolkit's own checksum
    rule, because the model verdict only exists above a verifying checksum: a
    carrier whose header states a digest its bytes no longer produce reports
    ``checksum: stale`` and a ``reject`` under ``B1`` - the suite's boundary rule,
    which says the floor failed, not that a model rule did. No K-rule verdict is
    claimed over such bytes, and none is inferred from them.

    Returns a layered :class:`FHGMReport`. It raises :class:`FHGMLaneError` only
    when the lane cannot report at all (no bundled draft, digest drift, the gate
    closed); a model-rule rejection is a ``reject`` verdict inside the report, so a
    caller still prints every layer."""
    report = FHGMReport()
    entry = draft_entry()
    if not entry:
        raise FHGMLaneError(
            "this build bundles no FHGM draft: schemas/bundled.json carries no "
            f"drafts.FHGM row, so {DRAFT_ENV} opens nothing"
        )
    if not draft_support_enabled():
        raise FHGMLaneError(
            f"the FHGM draft lane is closed: set {DRAFT_ENV}=1 to read the pinned "
            "development bytes (default behaviour is unchanged without it)"
        )
    _warn_draft(entry)
    report.disclosure = draft_warning()
    _, transport_bytes, _ = pinned("transport")
    _, record_bytes, _ = pinned("record")
    transport = draft_validator(json.loads(transport_bytes.decode("utf-8")))
    contract = draft_validator(json.loads(record_bytes.decode("utf-8")))
    raw = bytes(data)
    try:
        header = parse_snapshot(raw)
    except ModelCheckError as refusal:
        # An unreadable or non-object header is a refusal of this carrier, not of
        # the lane: the layers are still reported, with the model verdict marked.
        return report.refused(refusal.rule, str(refusal))
    # The released FHGFF3 header layer, stated apart from anything FHGM says.
    report.header = released_verdict(header)
    try:
        recomputed = _checksum(raw)
    except ValueError as error:
        report.checksum = NOT_RUN
        report.reason = f"no file checksum could be computed: {error}"
        return report
    stated = header.get("checksum")
    report.checksum = VERIFY if stated == recomputed else STALE
    if report.checksum != VERIFY:
        # The B1 boundary: the released base and the digest question come first,
        # so a stale carrier is a *rejection* reported under B1, exactly as the
        # owning suite records it - never a model-level gap, and never a pass.
        report.refused(
            "B1",
            f"File checksum mismatch: the header states {shown(stated)} and these "
            "bytes produce "
            f"{shown(recomputed)}; no FHGM model verdict is claimed over them",
        )
        return report
    try:
        rows = RowIndex(raw)
        carrier = check_snapshot(
            raw, transport, contract, rows=rows, checksum=recomputed
        )
        history: Dict[str, Snapshot] = {}
        for prior in predecessors:
            snapshot = check_snapshot(
                bytes(prior), transport, contract, checksum=_checksum(bytes(prior))
            )
            history[snapshot.checksum] = snapshot
    except ModelCheckError as refusal:
        report.refused(refusal.rule, str(refusal))
        # Even a rejection names the bytes that produced it, whenever the
        # citation resolves: "base: not selected" would hide which release said
        # no, and the record count the caller has to look at.
        try:
            row = base_for(header.get("schema"))
            report.base = f"{row['repository']}@{row['ref']}"
            report.base_sha256 = str(row["sha256"])
        except FHGMLaneError:
            pass
        declared = header.get(MODELS)
        report.records = len(declared) if isinstance(declared, list) else None
        return report
    report.base = f"{carrier.base['repository']}@{carrier.base['ref']}"
    report.base_sha256 = str(carrier.base["sha256"])
    report.records = len(carrier.models)
    report.history = len(history)
    report.model = PASS
    for model_id, model in carrier.models.items():
        if "predecessor" not in model:
            continue
        verdict, detail = resolve_predecessor(model_id, model, carrier, history)
        report.pointers.append(
            {"modelId": model_id, "verdict": verdict, "detail": detail}
        )
        if verdict != RESOLVABLE:
            report.model = REJECT
            report.rule = "K6"
            report.reason = f"Model {model_id!r} predecessor is {verdict}: {detail}"
    return report


def released_verdict(header: dict) -> str:
    """The *released* FHGFF3 verdict on ``header``, by the base it cites.

    A refusal to select a base is a rejection of this layer too - it says the
    citation is not a registered release - and it never changes the model layer's
    own verdict, which is reported apart."""
    try:
        base = base_for(header.get("schema"))
    except ModelCheckError:
        return REJECT
    try:
        _, schema = base_bytes(base)
    except FHGMLaneError:
        return NOT_RUN
    problems = list(validator(schema).iter_errors(header))
    return REJECT if problems else PASS


def _warn_draft(entry: dict) -> None:
    """Every run that reads draft bytes says so, naming its pinned provenance."""
    suite = entry.get("suite") or {}
    checker = suite.get("checker") or {}
    warnings.warn(
        "FHGM support is experimental and reads the draft contract on "
        f"{REPOSITORY} (record contract commit "
        f"{(entry.get('files') or {}).get('record', {}).get('revision')}, "
        "transport overlay commit "
        f"{(entry.get('files') or {}).get('transport', {}).get('revision')}): no "
        "released schema, no schemaVersion, no w3id alias; the checker semantics "
        f"are matched to commit {checker.get('revision')} (sha256 "
        f"{checker.get('sha256')}); selection, messages and the contract itself may "
        "change before publication (FAIR-bioHeaders-Specification#204, "
        "FAIR-bioHeaders-Tools#135)",
        FHGMDraftWarning,
        stacklevel=3,
    )


def _checksum(data: bytes) -> str:
    """The toolkit's own file-bound SHA-512/256 of ``data`` as a GFF3 carrier."""
    from .cli import checksum  # local: cli imports this module

    return checksum(data, "gff3")


def lane_provenance() -> dict:
    """The lane's recorded provenance, as data: no network, no writes.

    Every value is read back out of ``schemas/bundled.json``, so a report can name
    the exact bytes it used without the caller parsing the registry itself."""
    entry = draft_entry()
    return {
        "repository": REPOSITORY,
        "enable": DRAFT_ENV,
        "carrier": entry.get("carrier"),
        "status": entry.get("status"),
        "files": {
            kind: {
                "file": row.get("file"),
                "repository": row.get("repository"),
                "path": row.get("path"),
                "revision": row.get("revision"),
                "sha256": row.get("sha256"),
                "bytes": row.get("bytes"),
                "retrieved": row.get("retrieved"),
            }
            for kind, row in (entry.get("files") or {}).items()
        },
        "registry": entry.get("registry"),
        "bases": [
            {
                "ref": row.get("ref"),
                "schemaVersion": row.get("schemaVersion"),
                "file": row.get("file"),
                "sha256": row.get("sha256"),
            }
            for row in entry.get("bases") or []
        ],
        "suite": entry.get("suite"),
        "limits": entry.get("limits"),
    }
