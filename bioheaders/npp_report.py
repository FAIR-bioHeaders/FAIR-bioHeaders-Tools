# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Verification reports for the adopted NPP/Janeway FHR slice (increment PR-A).

``build_report`` turns one file's bytes into a machine-readable report whose
layers are decided independently and never implied: schema validity (version-aware,
unsupported contracts refused explicitly), file integrity (the header's
SHA-512/256 recomputed over the same bytes), parent links (the documented
``verify-links`` exit-code contract, never message text), and — always separate —
the checks this tool does not run (biology, live services, JATS projection).
Nothing in a report certifies scientific correctness; a parent match confirms
file identity only.

Revision binding: the report digests the PHYSICAL bytes of the file in fixed
chunks (never all at once), scans the LOGICAL carrier through the magic-aware
reader the verifiers already use (``.gz``/``.bgz`` included), and re-digests the
physical bytes before returning; a change detected between those passes marks the
report unstable and failed, so a digest can never certify a revision the scanner
or the parent verifier did not see.

The report binds the input (bytes, sha256, header checksum), the toolkit version,
the cited contract plus the RESOLVED schema (type, release, digest of the schema
bytes actually selected), and the accepted mapping slice (profile name, version,
landed commit, decision record) so a downstream venue can state exactly what was
verified against what. Builds are deterministic: no clocks, no network, no temp
paths in the output; the same bytes always produce the same report.

Scope notes (FAIR-bioHeaders-Tools#169, specification #249/#292):
- the profile constants record the maintainer's dated acceptance of
  ``mappings/proposals/npp-fhr-publication.yml``; they identify the reviewed
  crosswalk, they do NOT implement its JATS table projection (PR-B) or the HTML
  microdata preview and CLI documentation pass (PR-C);
- Q3b production-toolchain verification remains an open compatibility gate
  (specification #292, round NPP-3); nothing here claims production Janeway
  compatibility;
- the Python API is provisional; the command ``bioheaders npp`` is the supported
  interface, and the human summary escapes terminal control characters from
  untrusted input (rule V5's ``selection.escape_controls``).
"""

import hashlib
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__, fhr, read_chunks, selection
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
_CHUNK = 1 << 20

# verify-links exit codes this report ACCEPTS as a pass. Every other outcome -
# including a negative code (signal death) or a code outside {0,1,2,3} - is a
# failure of the parent-link layer; nothing outside this set can read as success.
_LINKS_ACCEPTED = {0: "pass"}
_LINKS_KNOWN_FAILURES = {
    1: "input-error",
    2: "usage-error",
    3: "mismatch-or-unchecked",
}
_SCHEMA_FAILURES = {"invalid", "refused-unsupported-schema"}
_INTEGRITY_FAILURES = {"fail", "absent", "error"}


def _digest(path):
    """(sha256 of physical bytes, byte count) in fixed chunks: constant memory."""
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _schema_provenance(citation):
    """Citation, registry digest, AND the resolved schema actually selected.

    ``bundled_registry_sha256`` describes the registry file; it is deliberately
    separate from ``selected_schema_sha256``, which hashes the schema bytes the
    record-aware selection resolved for THIS citation (type and release included).
    A registry edit that changes schema bytes therefore moves the per-report
    digest, and FHR-1 / main / historical citations resolve distinctly.
    """
    registry = files("bioheaders") / "schemas" / "bundled.json"
    raw = registry.read_bytes()
    prov = {
        "cited_contract": citation,
        "bundled_registry_sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        kind, ref, filename = selection._file(citation)
    except UnsupportedSchemaVersion:
        prov["resolved"] = None  # the schema layer records the refusal
        return prov
    try:
        schema_bytes = files("bioheaders").joinpath(filename).read_bytes()
        prov["resolved"] = {
            "header_type": kind,
            "release": ref,
            "schema_file": filename,
            "selected_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        }
    except OSError:
        prov["resolved"] = {
            "header_type": kind,
            "release": ref,
            "schema_file": filename,
            "selected_schema_sha256": None,
        }
    return prov


def build_report(path, parents=(), require_all=True, kind=None):
    """Return the layered verification report dict for one file.

    ``parents`` are candidate parent files handed to ``verify-links``;
    with ``require_all`` an unchecked recorded parent is a failure, exactly
    as the documented command defines it. ``kind`` overrides format detection
    (``fasta``/``gfa``/``gff3``); by default the file suffix decides, like every
    other command. Compressed carriers are scanned logically through the same
    magic-aware reader ``verify`` uses, while the bound sha256 stays the
    physical compressed bytes - both are labelled explicitly.
    """
    # Imported here on purpose: bioheaders.cli assembles the subcommand table
    # and may import this module in the future; a function-level import keeps
    # the package import graph acyclic while reusing the real scanners, not a
    # second implementation of them.
    from .cli import SequenceScan, file_format, open_input, validate_header_family

    target = Path(path)
    if not target.is_file():
        raise ValueError(f"{path}: not a readable file (the report binds exact bytes)")
    kind = kind or file_format(str(target))

    sha_before, size = _digest(path)
    report = {
        "tool": {"name": "fair-bioheaders", "version": __version__},
        "profile": {
            "name": PROFILE_NAME,
            "profile_version": PROFILE_VERSION,
            "accepted_commit": PROFILE_COMMIT,
            "adoption_decision": PROFILE_DECISION,
            "crosswalk": PROFILE_CROSSWALK,
        },
        "input": {
            "file": str(path),
            "bytes": size,
            "sha256_physical": sha_before,
        },
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

    # --- logical scan: magic-aware, exactly like the existing verifiers
    scan = data = None
    scan_error = None
    try:
        with open_input(str(target)) as stream:
            scan = SequenceScan(read_chunks(stream), kind)
        data = fhr()
        data._input_header_lines(scan.header, scan.prefix)
        report["input"]["header_type"] = data.header_type()
    except Exception as error:
        scan_error = f"{type(error).__name__}: {error}"
        report["input"]["header_type"] = None
    citation = data.__dict__.get("schema") if data is not None else None
    report["schema_provenance"] = _schema_provenance(citation)

    # --- layer 1: schema validity (version-aware; unsupported contracts refused)
    schema = {"outcome": None}
    if data is None:
        schema["outcome"] = "invalid"
        schema["detail"] = f"header could not be read: {scan_error}"
    else:
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
        except Exception as error:  # a broken candidate is a layer outcome, not a crash
            schema["outcome"] = "invalid"
            schema["detail"] = f"{type(error).__name__}: {error}"
    report["layers"]["schema"] = schema

    # --- layer 2: integrity (independent of layer 1; never crashes the report)
    recorded = data.__dict__.get("checksum") if data is not None else None
    integrity = {"recorded_checksum": recorded}
    if scan is None:
        integrity.update(outcome="error", detail="no scan available")
    elif not recorded:
        integrity["outcome"] = "absent"
    else:
        try:
            recomputed = scan.checksum()
        except Exception as error:
            recomputed = None
            integrity.update(outcome="error", detail=f"{type(error).__name__}: {error}")
        if recomputed is not None:
            integrity["recomputed_sha512_256"] = recomputed
            integrity["outcome"] = "pass" if recomputed == recorded else "fail"
    report["layers"]["integrity"] = integrity

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
            "outcome": _LINKS_ACCEPTED.get(
                done.returncode,
                _LINKS_KNOWN_FAILURES.get(
                    done.returncode, f"error-exit-{done.returncode}"
                ),
            ),
            "exit_code": done.returncode,
            "require_all": require_all,
            "candidates": [str(p) for p in parents],
            "output_lines": (done.stdout or "").splitlines(),
        }

    # --- revision stability: the physical bytes seen at start must be the bytes
    # the parent verifier and this function finished with.
    sha_after, size_after = _digest(path)
    stable = sha_after == sha_before and size_after == size
    report["input"]["stable_during_report"] = stable
    if not stable:
        report["input"]["sha256_at_end"] = sha_after

    links = report["layers"]["parent_links"]["outcome"]
    schema_ok = schema["outcome"] == "valid"
    integrity_ok = integrity["outcome"] == "pass"
    links_ok = links in ("pass", NOT_RUN)
    if not stable:
        report["outcome"] = "fail"
        report["failure"] = "input-changed-during-report"
    elif not schema_ok or not integrity_ok or not links_ok:
        report["outcome"] = "fail"
    elif links == NOT_RUN:
        report["outcome"] = "pass-unchecked-parents"
    else:
        report["outcome"] = "pass"
    return report


def outcome_exit_code(report):
    """Map a report to the toolkit's documented exit-code family."""
    return 0 if report["outcome"] in ("pass", "pass-unchecked-parents") else 1


def render_text(report):
    """Human summary with every untrusted value escaped for terminals.

    Filenames, schema details and parent output originate in submitted files;
    control characters are neutralized by the same helper rule V5 warnings use,
    so a crafted name can clear or rewrite the viewer's terminal in no path.
    """
    fields = [
        f"input: {report['input']['file']} ({report['input']['bytes']} B, "
        f"sha256 {report['input']['sha256_physical'][:16]}…)",
        f"header: {report['input'].get('header_type') or '(none)'} "
        f"carrier={report['carrier']}",
        "schema: "
        + (
            f"{report['layers']['schema']['outcome']}"
            + (
                f" ({report['layers']['schema'].get('detail', '')})"
                if report["layers"]["schema"]["outcome"] != "valid"
                else ""
            )
        ),
        f"integrity: {report['layers']['integrity']['outcome']}"
        + (
            f" ({report['layers']['integrity'].get('detail', '')})"
            if report["layers"]["integrity"].get("detail")
            else ""
        ),
        f"parent links: {report['layers']['parent_links']['outcome']}",
        f"stable during report: {report['input']['stable_during_report']}",
        f"not run: {', '.join(report['not_run'])}",
        f"profile: {report['profile']['name']} {report['profile']['profile_version']} "
        f"@ {report['profile']['accepted_commit'][:9]}",
        f"outcome: {report['outcome']}",
    ]
    return "\n".join(selection.escape_controls(line) for line in fields)
