# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""FHGM conformance-vector consumer - opt-in draft evidence (gated by default).

The 62 vectors of FHGM-Specification's development suite
(``development/conformance/manifest.json``, #204 lane; the model contract is
FAIR-bioHeaders-Tools#135) are the acceptance gate this toolkit prepares for. Like
the FHT consumer this file copies nothing into the repository: it reads a checkout
whose manifest matches the pin and scores the vectors through
``bioheaders.fhgm``.

Run it with BOTH:

1. ``BIOHEADERS_EXPERIMENTAL_FHGM=1`` - the draft lane (docs/FHGM-DRAFT-LANE.md);
2. ``FHGM_SPECIFICATION=/path/to/FHGM-Specification`` - a checkout holding
   ``development/conformance/manifest.json`` (or a sibling ``FHGM-Specification``
   / ``FHGM`` directory, the fallback the other type tests use).

Semantics, taken from the owning suite's ``run_conformance.py`` and applied here
unchanged. Each vector records four independent layers, and each is scored on its
own terms:

``base``
    the released ``fhgff3.json`` of the lane's own release - v0.5.0 for the sealed
    lane, the bytes every sealed expectation was observed against - over the header
    read by this package's strict reader.
``checksum``
    ``verify`` when the file-bound SHA-512/256 covers these bytes, ``stale`` when
    the header states a digest they no longer produce. It is recomputed here with
    ``hashlib`` directly, beside the toolkit's own implementation, so a shared bug
    cannot hide - the same discipline the owning runner states.
``gff3``
    ``gff3-validate --no-header``, a separate tool. When it is not supplied this
    layer is reported **skipped**, never as a pass: no FHGM rule depends on it.
``model``
    ``bioheaders.fhgm.check_models()`` over the vector's exact bytes plus the
    snapshots its ``context.predecessors`` names, and only those (K6). An invalid
    vector also pins the ``reason`` substring the verdict must contain.

The suite is pinned apart from both contract axes (``drafts.FHGM.suite`` in
``bioheaders/schemas/bundled.json``): the checkout above is whatever revision the
operator happens to have, so ``test_suite_manifest_matches_pin`` names the bytes
this run scored and fails when they are not the pinned ones. A pass is only
quotable together with that test; a suite move is a deliberate, dated commit
(FAIR-bioHeaders-Specification#241).

After actual FHGM publication, revise these gates through the reviewed
released-consumer handoff. Draft recognition stays opt-in under V7; a suite re-pin
does not authorize default-on recognition or a released support claim.
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

import pytest

from bioheaders import HEADER, fhgm, header_text, load_yaml, sequence_parts
from bioheaders.schema_validator import validator

ROOT = Path(__file__).resolve().parents[1]
CHECKSUM_PREFIX = b"#~checksum: "
# The sealed lane's own base release: every recorded expectation was observed
# against these bytes (development/conformance/provenance.json in the owning
# repository), while the checker selects the release each file cites.
SEALED_BASE = "schemas/fhgff3-1.1.json"


def _spec_dir():
    configured = os.environ.get("FHGM_SPECIFICATION")
    candidates = [Path(configured)] if configured else []
    candidates += [ROOT.parent / "FHGM-Specification", ROOT.parent / "FHGM"]
    for candidate in candidates:
        if (candidate / "development" / "conformance" / "manifest.json").is_file():
            return candidate
    return None


def configured_or_default():
    return os.environ.get("FHGM_SPECIFICATION") or (
        f"{ROOT.parent / 'FHGM-Specification'} or {ROOT.parent / 'FHGM'}"
    )


SPEC = _spec_dir()
CONFORMANCE = SPEC / "development" / "conformance" if SPEC else None
MANIFEST_PATH = CONFORMANCE / "manifest.json" if CONFORMANCE else None
HAVE_VECTORS = MANIFEST_PATH is not None and MANIFEST_PATH.is_file()
GATE_OPEN = fhgm.draft_support_enabled()
SKIP_REASON = (
    "FHGM development-suite vectors (FAIR-bioHeaders-Specification#204, "
    "FAIR-bioHeaders-Tools#135) are consumed only with "
    f"{fhgm.DRAFT_ENV}=1 and FHGM_SPECIFICATION pointing at a checkout with "
    f"development/conformance/manifest.json (looked in: "
    f"{configured_or_default()})"
)
if HAVE_VECTORS and not GATE_OPEN:
    SKIP_REASON = (
        f"FHGM conformance vectors found in {SPEC}, but the draft lane is closed: "
        f"run with {fhgm.DRAFT_ENV}=1"
    )

MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if HAVE_VECTORS else {}
VECTORS = [
    vector for vector in MANIFEST.get("vectors", []) if not vector.get("retired")
]
SUITE_PIN = (fhgm.draft_entry().get("suite") or {}) if HAVE_VECTORS else {}
MANIFEST_SHA256 = (
    hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() if HAVE_VECTORS else None
)
GFF3_VALIDATE = os.environ.get("GFF3_VALIDATE") or shutil.which("gff3-validate")

# The layers the owning manifest records, and the only verdicts it ever records
# for them. An unexpected value is a harness defect, not a pass.
LAYERS = ("base", "checksum", "gff3", "model")


def pytest_param_id(vector):
    return vector["id"]


params = [pytest.param(vector, id=vector["id"]) for vector in VECTORS]

# CI's FHGM conformance job sets FHGM_REQUIRE_SUITE so a missing checkout or a
# closed lane fails there instead of skipping the whole file.
if os.environ.get("FHGM_REQUIRE_SUITE") and not (HAVE_VECTORS and GATE_OPEN):
    raise RuntimeError(f"FHGM_REQUIRE_SUITE is set but: {SKIP_REASON}")

pytestmark = pytest.mark.skipif(not (HAVE_VECTORS and GATE_OPEN), reason=SKIP_REASON)


def suite_file(relative_path):
    """One file of the pinned suite, read from the tree only after git-proofing it.

    Vector paths are relative to ``development/conformance/`` and the suite reuses
    committed examples above it (``../examples/...``), so the walk is bounded to
    the owning repository rather than to one directory - and every byte is then
    compared with the pinned revision, exactly as the FHT consumer does."""
    relative = PurePosixPath(relative_path)
    assert (
        relative.parts and not relative.is_absolute() and ".." not in relative.parts[1:]
    ), f"unsafe path in pinned suite manifest: {relative_path}"
    source = CONFORMANCE.joinpath(*relative.parts).resolve()
    assert source.is_relative_to(
        SPEC.resolve()
    ), f"suite path escapes the pinned checkout: {relative_path}"
    repository_path = source.relative_to(SPEC.resolve()).as_posix()
    result = subprocess.run(
        ["git", "-C", str(SPEC), "show", f"{SUITE_PIN['revision']}:{repository_path}"],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"could not read {relative_path} from pinned suite revision "
        f"{SUITE_PIN['revision']}: {result.stderr.decode(errors='replace')}"
    )
    assert source.is_file(), f"missing vector file {relative_path}"
    actual = source.read_bytes()
    assert actual == result.stdout, (
        f"suite file {source} differs from {SUITE_PIN['repository']} "
        f"@ {SUITE_PIN['revision']}"
    )
    return actual


def vector_bytes(vector):
    return suite_file(vector["file"])


def predecessors_of(vector):
    context = vector.get("context") or {}
    return [suite_file(path) for path in context.get("predecessors", [])]


def stated_checksum(data):
    for line in data.splitlines():
        if line.startswith(CHECKSUM_PREFIX):
            return line[len(CHECKSUM_PREFIX) :].decode()
    return None


def recomputed_checksum(data):
    """SHA-512/256 over every byte except the root checksum line and its
    terminator (docs/FORMAT.md R3), computed here beside the toolkit's own
    implementation so a shared bug in either cannot hide."""
    covered = b"".join(
        line
        for line in data.splitlines(keepends=True)
        if not line.startswith(CHECKSUM_PREFIX)
    )
    return base64.b64encode(hashlib.new("sha512_256", covered).digest()).decode()


def parsed_header(data):
    lines = [
        header_text(line, b"#~")
        for kind, line in sequence_parts([data], b"#~", gff3=True)
        if kind is HEADER
    ]
    return load_yaml("\n".join(lines))


@lru_cache(maxsize=None)
def sealed_base_validator():
    return validator(json.loads((ROOT / "bioheaders" / SEALED_BASE).read_bytes()))


def base_layer(data):
    try:
        header = parsed_header(data)
    except Exception as error:  # any reader refusal is a base reject
        return "reject", f"header unreadable by the strict reader: {error}"
    errors = sorted(sealed_base_validator().iter_errors(header), key=str)
    if not errors:
        return "accept", ""
    first = errors[0]
    return "reject", f"{first.json_path}: {first.message}"


def model_layer(vector):
    report = fhgm.check_models(
        vector_bytes(vector), predecessors=predecessors_of(vector)
    )
    if report.model not in ("pass", "reject", "not-run"):
        pytest.fail(f"{vector['id']}: the lane reported an unknown verdict")
    return ("pass" if report.model == "pass" else "reject"), report.text(), report


def gff3_layer(data):
    """``gff3-validate --no-header`` over the feature layer, when it is installed.

    A separate tool with its own rule catalogue: this lane never runs it, so the
    default answer is ``skipped`` and no vector's FHGM verdict rests on it."""
    if not GFF3_VALIDATE:
        return "skipped", ""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "vector.fhgff3.gff3"
        path.write_bytes(data)
        result = subprocess.run(
            [GFF3_VALIDATE, "--no-header", str(path)],
            capture_output=True,
            text=True,
        )
    return (
        ("accept" if result.returncode == 0 else "reject"),
        (result.stdout + result.stderr).strip(),
    )


@pytest.mark.parametrize("vector", params)
def test_vector_layers_match_the_record(vector):
    """Every recorded layer of one vector, scored on its own terms."""
    data = vector_bytes(vector)
    recorded = vector["layers"]
    assert set(recorded) == set(LAYERS), vector["id"]
    assert hashlib.sha256(data).hexdigest() == vector["bytes"]["sha256"]
    assert len(data) == vector["bytes"]["size"]
    stated = stated_checksum(data)
    assert stated == vector["checksum"], "the checksum line is not what was recorded"
    outcome = recomputed_checksum(data)
    if recorded["checksum"] == "verify":
        assert outcome == stated, "recorded as verifying, the bytes do not"
    elif recorded["checksum"] == "stale":
        assert outcome != stated, "recorded as tampered, the digest covers them again"
    else:
        pytest.fail(f"{vector['id']}: unknown recorded checksum outcome")
    base, base_text = base_layer(data)
    assert base == recorded["base"], f"base {base} ({base_text}) != {recorded['base']}"
    model, model_text, report = model_layer(vector)
    assert model == recorded["model"], f"model {model} != {recorded['model']}"
    if vector["expected"] == "valid":
        assert model == "pass", f"expected valid, the lane rejected it: {model_text}"
    else:
        assert model == "reject", "expected invalid, the lane accepted it"
        reason = vector.get("reason")
        assert reason, f"{vector['id']}: an invalid vector must record a reason"
        assert reason in model_text, f"recorded reason {reason!r} not in {model_text}"
    assert report.model == model
    feature, feature_text = gff3_layer(data)
    if feature != "skipped":
        assert feature == recorded["gff3"], f"GFF3 layer {feature}: {feature_text}"


@pytest.mark.parametrize("vector", params)
def test_model_layer_never_borrows_another_layers_verdict(vector):
    """The separation #135 asks for, checked per vector.

    A rejection reported by the model layer does not rewrite the released FHGFF3
    header verdict, and the GFF3 feature layer is never claimed: whatever the
    model says, the report keeps saying ``not-run`` for the layer that belongs to
    ``gff3-validator``."""
    _model, _text, report = model_layer(vector)
    assert report.layers()["feature"] == "not-run", vector["id"]
    assert "gff3-validator" in report.layers()["feature_reason"]
    assert report.header in ("pass", "reject", "not-run"), vector["id"]
    assert report.checksum in ("verify", "stale", "not-run"), vector["id"]
    if report.model == "pass":
        assert report.header == "pass", "a passing model over a rejected header"


def test_gff3_layer_is_reported_not_run_when_the_tool_is_absent():
    # Honest accounting, asserted rather than assumed: without gff3-validate the
    # layer is skipped for every vector, and no vector's pass depends on it.
    if GFF3_VALIDATE:
        pytest.skip("gff3-validate was supplied, so the feature layer ran")
    scored = [gff3_layer(vector_bytes(vector))[0] for vector in VECTORS]
    assert set(scored) == {"skipped"}, set(scored)


def test_suite_manifest_matches_pin():
    """The vectors scored above must be the vectors the pin names.

    ``FHGM_SPECIFICATION`` is a checkout path, not a revision: without this check a
    run would report "62/62 pass" for bytes nobody recorded. This is a gate on the
    harness's own input, not an advisory freshness report about upstream."""
    assert (
        SUITE_PIN
    ), "drafts.FHGM.suite is not recorded in bioheaders/schemas/bundled.json"
    files = {vector["file"] for vector in VECTORS} | {
        path
        for vector in VECTORS
        for path in (vector.get("context") or {}).get("predecessors", [])
    }
    for relative_path in sorted(files):
        suite_file(relative_path)
    detail = (
        f"suite manifest scored from {MANIFEST_PATH}\n"
        f"  measured sha256 {MANIFEST_SHA256} ({MANIFEST_PATH.stat().st_size} bytes, "
        f"{len(VECTORS)} vectors)\n"
        f"  pinned    sha256 {SUITE_PIN['sha256']} "
        f"({SUITE_PIN['repository']} @ {SUITE_PIN['revision']}, "
        f"{SUITE_PIN['bytes']} bytes, {SUITE_PIN['fhgmVectors']} vectors)"
    )
    assert MANIFEST_SHA256 == SUITE_PIN["sha256"], detail
    assert MANIFEST_PATH.stat().st_size == SUITE_PIN["bytes"], detail
    assert len(VECTORS) == SUITE_PIN["fhgmVectors"], detail
    # And the contract axes this suite is scored against are pinned apart from it.
    entry = fhgm.draft_entry()
    for row in entry["files"].values():
        assert (
            row["revision"] != SUITE_PIN["revision"] or row["path"] != SUITE_PIN["path"]
        )


def test_vectors_that_declare_records_are_the_ones_the_lane_reads():
    """Every vector either declares records or is refused for not declaring them.

    That is the boundary the zero-change claim rests on: the lane runs exactly when
    ``x-fhgm-models`` is present, and a carrier without it stays a plain released
    FHGFF3 file - here, no vector of the pinned suite is such a carrier, so the
    refusal wording is what proves the rule rather than a silent pass."""
    declared = 0
    for vector in VECTORS:
        data = vector_bytes(vector)
        header = parsed_header(data)
        present = fhgm.carries_models(header)
        declared += present
        if not present:
            continue
        _model, _text, report = model_layer(vector)
        assert report.records is not None or report.model == "reject", vector["id"]
    assert declared == len(VECTORS), (
        f"{declared} of {len(VECTORS)} vectors declare {fhgm.MODELS}: the suite shape "
        "changed and this file's accounting no longer describes it"
    )
