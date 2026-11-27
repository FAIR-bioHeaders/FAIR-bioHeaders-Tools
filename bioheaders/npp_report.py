# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Verification reports for the adopted NPP/Janeway FHR slice (increment PR-A).

``build_report`` turns one file's exact bytes into a machine-readable report whose
layers are decided independently and never implied: schema validity (version-aware,
unsupported contracts refused explicitly), file integrity (the header's
SHA-512/256 recomputed over the same bytes), parent links (the documented
``verify-links`` exit-code contract, never message text), and — always separate —
the checks this tool does not run (biology, live services, JATS projection).
Nothing in a report certifies scientific correctness; a parent match confirms
file identity only.

The report binds the input (bytes, sha256, header checksum), the toolkit version,
the selected schema contract, and the accepted mapping slice (profile name,
version, landed commit, decision record) so a downstream venue can state exactly
what was verified against what. Builds are deterministic: no clocks, no network,
no temp paths in the output; the same bytes always produce the same report.

Scope notes (FAIR-bioHeaders-Tools#169, specification #249/#292):
- the profile constants record the maintainer's dated acceptance of
  ``mappings/proposals/npp-fhr-publication.yml``; they identify the reviewed
  crosswalk, they do NOT implement its JATS table projection (PR-B) or the HTML
  microdata preview and CLI documentation pass (PR-C);
- Q3b production-toolchain verification remains an open compatibility gate
  (specification #292, round NPP-3); nothing here claims production Janeway
  compatibility;
- the Python API is provisional; the command ``bioheaders npp`` is the supported
  interface.
"""

import hashlib
import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__, fhr, read_chunks
from .selection import UnsupportedSchemaVersion

PROFILE_NAME = "npp-fhr-publication"
# The accepted version/commit pair is the maintainer's record on specification
# #249; a profile change means a new dated acceptance, and this module's
# constants move with it (tests assert the pairing, not just the strings).
PROFILE_VERSION = "0.1.0-draft.2"
PROFILE_COMMIT = "efa67d71fecb90a7b47e47f6c036324d2f71d19b"
PROFILE_DECISION = (
    "https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/249"
    "#issuecomment-7219909539"
)
PROFILE_CROSSWALK = "mappings/proposals/npp-fhr-publication.yml"

NOT_RUN = "not-run"

# verify-links exit-code contract (documented in cli help; the ONLY interface
# this module reads from that command — message text is captured as data).
_LINKS_OUTCOMES = {
    0: "pass",
    1: "input-error",
    2: "usage-error",
    3: "mismatch-or-unchecked",
}


def _binding(path):
    """Bind the report to the exact input bytes (sha256 + size). Read once."""
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for chunk in read_chunks(stream):
            size += len(chunk)
            digest.update(chunk)
    return {
        "file": str(path),
        "bytes": size,
        "sha256": digest.hexdigest(),
    }


def _schema_provenance():
    bundled = files("bioheaders") / "schemas" / "bundled.json"
    raw = bundled.read_bytes()
    doc = json.loads(raw)
    return {
        "bundled_sha256": hashlib.sha256(raw).hexdigest(),
        "bundled_current": doc.get("current"),
    }


def build_report(path, parents=(), require_all=True, kind=None):
    """Return the layered verification report dict for one file.

    ``parents`` are candidate parent files handed to ``verify-links``;
    with ``require_all`` an unchecked recorded parent is a failure, exactly
    as the documented command defines it. ``kind`` overrides format detection
    (``fasta``/``gfa``/``gff3``); by default the file suffix decides, like every
    other command.
    """
    # Imported here on purpose: bioheaders.cli assembles the subcommand table
    # and may import this module in the future; a function-level import keeps
    # the package import graph acyclic while reusing the real scanners, not a
    # second implementation of them.
    from .cli import SequenceScan, file_format, validate_header_family

    target = Path(path)
    if not target.is_file():
        raise ValueError(f"{path}: not a readable file (the report binds exact bytes)")
    kind = kind or file_format(str(target))
    report = {
        "tool": {"name": "fair-bioheaders", "version": __version__},
        "profile": {
            "name": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "accepted_commit": PROFILE_COMMIT,
            "adoption_decision": PROFILE_DECISION,
            "crosswalk": PROFILE_CROSSWALK,
        },
        "input": _binding(path),
        "carrier": kind,
        "layers": {},
        "not_run": {
            "biological_checks": (
                f"{NOT_RUN}: feature/coordinate/translation biology is not a header "
                "property; run gff3-validator or the agreed biological tool separately"
            ),
            "external_services": f"{NOT_RUN}: no accession, URL or identifier resolution",
            "jats_projection": f"{NOT_RUN}: PR-B increment (Tools #169); not built here",
        },
        "certification": (
            "None implied: this report states schema validity, byte integrity and "
            "parent-file identity for the bound input revision only"
        ),
    }

    from .cli import open_input

    with open_input(str(target)) as stream:
        scan = SequenceScan(read_chunks(stream), kind)
    data = fhr()
    data._input_header_lines(scan.header, scan.prefix)
    header_type = data.header_type()
    report["input"]["header_type"] = header_type
    report["input"]["recorded_checksum"] = data.checksum
    from .selection import draft_entry, record_file, select_record

    provenance = _schema_provenance()
    provenance["registry_sha256"] = provenance.pop("bundled_sha256")
    provenance["citation"] = data.__dict__.get("schema")
    provenance["selected_contract"] = None
    provenance["bundled_sha256"] = None
    try:
        selected_type, selected_ref, selected_schema = select_record(data.__dict__)
        selected_file = record_file(data.__dict__)
    except UnsupportedSchemaVersion:
        pass  # The schema layer records the refusal below.
    else:
        raw_schema = files("bioheaders").joinpath(selected_file).read_bytes()
        draft = draft_entry(selected_type) or {}
        if draft.get("file") == selected_file:
            revision = draft.get("revision")
        elif selected_ref == "main":
            revision = provenance["bundled_current"]["release"]
        else:
            revision = selected_ref
        provenance["selected_contract"] = {
            "header_type": selected_type,
            "revision": revision,
            "id": selected_schema.get("$id"),
            "file": selected_file,
        }
        provenance["bundled_sha256"] = hashlib.sha256(raw_schema).hexdigest()
    report["schema_provenance"] = provenance

    # --- layer 1: schema validity (version-aware; unsupported contracts refused)
    schema = {"outcome": None}
    try:
        data.fhr_validate()
        validate_header_family(data, kind)
        schema["outcome"] = "valid"
    except UnsupportedSchemaVersion as error:
        schema["outcome"] = "refused-unsupported-schema"
        schema["detail"] = str(error)
    except ValueError as error:
        schema["outcome"] = "invalid"
        schema["detail"] = str(error)
    except (
        Exception
    ) as error:  # a broken candidate must be a layer outcome, not a crash
        schema["outcome"] = "invalid"
        schema["detail"] = f"{type(error).__name__}: {error}"
    report["layers"]["schema"] = schema

    # --- layer 2: integrity (independent of layer 1: computed even if schema invalid)
    recomputed = scan.checksum()
    report["layers"]["integrity"] = {
        "recomputed_sha512_256": recomputed,
        "outcome": (
            "pass"
            if recomputed and recomputed == data.checksum
            else "absent" if not data.checksum else "fail"
        ),
    }

    # --- layer 3: parent links (documented exit codes; text captured as evidence)
    if not parents:
        report["layers"]["parent_links"] = {
            "outcome": NOT_RUN,
            "reason": "no candidate parent files supplied",
        }
    else:
        argv = [
            sys.executable,
            "-m",
            "bioheaders",
            "verify-links",
            str(target),
            *[str(p) for p in parents],
        ]
        if require_all:
            argv.append("--require-all")
        done = subprocess.run(argv, capture_output=True, text=True)
        report["layers"]["parent_links"] = {
            "outcome": _LINKS_OUTCOMES.get(done.returncode, f"exit-{done.returncode}"),
            "exit_code": done.returncode,
            "require_all": require_all,
            "candidates": [str(p) for p in parents],
            "output_lines": (done.stdout or "").splitlines(),
        }

    executed = [
        report["layers"]["schema"]["outcome"],
        report["layers"]["integrity"]["outcome"],
    ]
    links = report["layers"]["parent_links"]["outcome"]
    if (
        "invalid" in executed
        or "refused-unsupported-schema" in executed
        or "fail" in executed
    ):
        overall = "fail"
    elif links not in ("pass", NOT_RUN):
        overall = "fail"
    elif links == NOT_RUN:
        overall = "pass-unchecked-parents"
    else:
        overall = "pass"
    report["outcome"] = overall
    return report


def outcome_exit_code(report):
    """Map a report to the toolkit's documented exit-code family."""
    return {"pass": 0, "pass-unchecked-parents": 0}.get(report["outcome"], 1)


def render_text(report):
    lines = [
        f"input: {report['input']['file']} ({report['input']['bytes']} B, "
        f"sha256 {report['input']['sha256'][:16]}…)",
        f"header: {report['input'].get('header_type') or '(none)'} "
        f"carrier={report['carrier']}",
        f"schema: {report['layers']['schema']['outcome']}"
        + (
            f" ({report['layers']['schema'].get('detail', '')})"
            if report["layers"]["schema"]["outcome"] not in (None, "valid")
            else ""
        ),
        f"integrity: {report['layers']['integrity']['outcome']}",
        f"parent links: {report['layers']['parent_links']['outcome']}",
        f"not run: {', '.join(report['not_run'])}",
        f"profile: {report['profile']['name']} {report['profile']['profile_version']} "
        f"@ {report['profile']['accepted_commit'][:9]}",
        f"outcome: {report['outcome']}",
    ]
    from .selection import escape_controls

    return escape_controls("\n".join(lines))
