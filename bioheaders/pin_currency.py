# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/.
"""Read-only default-content and known-consumer reports (#167), not pin policy.

Historical released pins remain valid. A default-content difference recommends no
update, adopts no identifier policy and never changes a recorded revision.
"""

import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .pin_audit import CONTROL_NAME, DRAFT_LABEL, FRESH, NoRedirectHandler

OWNERS = {
    "FHT": "FAIR-bioHeaders/FHT-Specification",
    "FHGM": "FAIR-bioHeaders/FHGM-Specification",
}
CONSUMERS = {
    "JavaScript": "drafts/provenance.json",
    "Java": "src/main/resources/org/fairbioheaders/schemas/provenance.json",
    "Julia": "drafts/provenance.json",
    "R": "inst/VENDORED.json",
}
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
PATHS = {
    "FHT": {"contract": "fht.json", "suite": "conformance/manifest.json"},
    "FHGM": {
        "contract": "development/model/fhgm-model.schema.json",
        "suite": "development/conformance/manifest.json",
    },
}


def _git(checkout, *args):
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode or not result.stdout.strip():
        raise ValueError(result.stderr.strip() or "empty git measurement")
    return result.stdout.strip()


class DefaultContent:
    """Resolve one immutable default-branch snapshot per repository per report.

    HTTPS metadata and raw-file backends both require negative controls. Offline
    fixtures declare snapshots in default-branches.json; checkouts use origin/HEAD,
    never their possibly task-specific checked-out branch. No fetch or git write.
    """

    def __init__(self, auditor):
        self.auditor = auditor
        self.snapshots = {}
        self.controls = []

    def _api(self, repository, suffix=""):
        url = "https://api.github.com/repos/" + repository + suffix
        opener = urllib.request.build_opener(NoRedirectHandler())
        request = urllib.request.Request(
            url, headers={"User-Agent": "bioheaders-pin-audit"}
        )
        try:
            with opener.open(request, timeout=self.auditor.options.timeout) as response:
                return response.read(), response.status
        except urllib.error.HTTPError as error:
            return None, error.code
        except (urllib.error.URLError, OSError):
            return None, None

    def snapshot(self, repository):
        if repository in self.snapshots:
            return self.snapshots[repository]
        result = {
            "repository": repository,
            "branch": None,
            "commit": None,
            "detail": None,
        }
        options = self.auditor.options
        try:
            if options.fixture_dir:
                metadata = json.loads(
                    (Path(options.fixture_dir) / "default-branches.json").read_text()
                )
                value = metadata[repository]
                result.update(branch=value["branch"], commit=value["commit"])
            elif repository in self.auditor.checkouts:
                checkout = self.auditor.checkouts[repository]
                ref = _git(checkout, "symbolic-ref", "refs/remotes/origin/HEAD")
                result.update(
                    branch=ref.removeprefix("refs/remotes/origin/"),
                    commit=_git(checkout, "rev-parse", ref + "^{commit}"),
                )
            elif options.offline:
                raise ValueError(
                    "offline: no checkout/default snapshot for this repository"
                )
            else:
                _, status = self._api(repository, "/contents/" + CONTROL_NAME)
                self.controls.append(
                    {
                        "repository": repository,
                        "backend": "github-metadata",
                        "negative_control_ok": status == 404,
                        "status": status,
                    }
                )
                if status != 404:
                    raise ValueError(
                        "default-branch metadata negative control did not return 404"
                    )
                raw, status = self._api(repository)
                if status != 200 or not raw:
                    raise ValueError("default-branch metadata unavailable or empty")
                branch = json.loads(raw)["default_branch"]
                if not isinstance(branch, str) or not branch:
                    raise ValueError("default branch is empty or malformed")
                # GitHub branch names may contain slashes; preserve them as a ref.
                from urllib.parse import quote

                raw, status = self._api(
                    repository, "/commits/" + quote(branch, safe="")
                )
                if status != 200 or not raw:
                    raise ValueError("default-branch commit unavailable or empty")
                result.update(branch=branch, commit=json.loads(raw)["sha"])
            if not isinstance(result["commit"], str) or not SHA.fullmatch(
                result["commit"]
            ):
                raise ValueError("default snapshot has no full commit identity")
            if not isinstance(result["branch"], str) or not result["branch"]:
                raise ValueError("default snapshot has no branch identity")
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.TimeoutExpired,
        ) as error:
            result.update(commit=None, detail=str(error))
        self.snapshots[repository] = result
        return result

    def read(self, repository, path):
        snapshot = self.snapshot(repository)
        if snapshot["commit"] is None:
            return None, snapshot, snapshot["detail"]
        resolver, control = self.auditor.resolver_for(
            {"repository": repository, "revision": snapshot["commit"]}
        )
        if control[0] is not True:
            return (
                None,
                snapshot,
                "default-file backend control unavailable or failed: " + control[1],
            )
        raw, where, _ = resolver.resolve(repository, snapshot["commit"], path)
        if not raw:
            return None, snapshot, "default bytes unavailable or empty: " + where
        return raw, snapshot, where

    def compare(self, reference, integrity):
        row = {
            "id": reference["id"],
            "class": reference["class"],
            "label": reference.get("label"),
            "repository": reference.get("repository"),
            "path": reference.get("path"),
            "recorded_revision": reference.get("revision"),
            "recorded_sha256": reference.get("sha256"),
            "status": "UNAVAILABLE",
            "default_branch": None,
            "default_commit": None,
            "default_sha256": None,
            "detail": None,
        }
        if reference.get("relationship", {}).get("kind") == "derived-subset":
            row.update(
                status="NOT_APPLICABLE", detail="derived subset is not a whole-file pin"
            )
        elif reference["class"] == "copied-tree":
            row.update(
                status="NOT_APPLICABLE",
                detail="directory relationships have no single file digest; integrity tree report remains separate",
            )
        elif integrity.get("verdict") != FRESH:
            row["detail"] = "recorded integrity is not FRESH; currency verdict withheld"
        else:
            raw, snapshot, detail = self.read(
                reference["repository"], reference["path"]
            )
            row.update(
                default_branch=snapshot["branch"],
                default_commit=snapshot["commit"],
                detail=detail,
            )
            if raw:
                digest = hashlib.sha256(raw).hexdigest()
                row.update(
                    default_sha256=digest,
                    default_bytes=len(raw),
                    status=(
                        "CURRENT_CONTENT"
                        if digest == reference["sha256"]
                        else "SUPERSEDED_CONTENT"
                    ),
                )
        return row


def _record(
    consumer, kind, role, revision=None, digest=None, size=None, count=None, path=None
):
    return {
        "id": consumer + ":" + kind + ":" + role,
        "consumer": consumer,
        "logical_reference": kind + ":" + role,
        "label": DRAFT_LABEL,
        "class": "conformance-suite" if role == "suite" else "draft-contract",
        "repository": OWNERS[kind],
        "path": path or PATHS[kind][role],
        "revision": revision,
        "revision_kind": "commit",
        "sha256": digest,
        "bytes": size,
        "recorded_vectors": count,
        "local": None,
    }


def consumer_records(consumer, document):
    """Explicit adapters for existing registries; values remain recorded verbatim.

    This table covers the two draft contracts and suites, not native capability,
    all federation pins, or inferred carriers. No score is inferred from a count.
    """
    rows = []
    for kind in OWNERS:
        if consumer == "R":
            matches = [
                v
                for v in document.get("files", [])
                if v.get("kind") == "draft-contract" and v.get("header_type") == kind
            ]
            entry = matches[0] if len(matches) == 1 else {}
            suite = document.get(
                "draft_vectors" if kind == "FHT" else "draft_fhgm_vectors", {}
            )
            rows.append(
                _record(
                    consumer,
                    kind,
                    "contract",
                    entry.get("commit"),
                    entry.get("sha256"),
                    entry.get("bytes"),
                    path=entry.get("source_path"),
                )
            )
            rows.append(
                _record(
                    consumer,
                    kind,
                    "suite",
                    suite.get("commit"),
                    suite.get("manifest_sha256"),
                    count=suite.get("vectors"),
                )
            )
        elif consumer == "Tools":
            entry = document.get("drafts", {}).get(kind, {})
            suite = entry.get("suite", {})
            rows.append(
                _record(
                    consumer,
                    kind,
                    "contract",
                    entry.get("revision"),
                    entry.get("sha256"),
                    path="fht.json" if kind == "FHT" else None,
                )
            )
            rows.append(
                _record(
                    consumer,
                    kind,
                    "suite",
                    suite.get("revision"),
                    suite.get("sha256"),
                    suite.get("bytes"),
                    suite.get("fhtFastaVectors"),
                )
            )
        else:
            entry = document.get("drafts", {}).get(kind, {})
            contract = next(
                (
                    a
                    for a in entry.get("artifacts", [])
                    if a.get("sourcePath", "").endswith(
                        "fht.json" if kind == "FHT" else "fhgm-model.schema.json"
                    )
                ),
                entry,
            )
            rows.append(
                _record(
                    consumer,
                    kind,
                    "contract",
                    contract.get("commit"),
                    contract.get("sha256"),
                    contract.get("bytes", contract.get("size")),
                    path=contract.get("sourcePath"),
                )
            )
            rows.append(
                _record(
                    consumer,
                    kind,
                    "suite",
                    entry.get("suiteCommit"),
                    entry.get("suiteManifestSha256"),
                    entry.get("suiteManifestBytes"),
                    entry.get(
                        "suiteVectors",
                        entry.get("suitePinAnnotation", {})
                        .get("asRecorded", {})
                        .get("vectors"),
                    ),
                    entry.get("suiteManifest"),
                )
            )
    # Only Java's main provenance file explicitly embeds a base registry here.
    # Other consumers may keep bases elsewhere; this report never infers them.
    if consumer == "Java":
        bases = (
            document.get("drafts", {})
            .get("FHGM", {})
            .get("baseSchemas", {})
            .get("bases", [])
        )
        for base in bases:
            release = base.get("release")
            rows.append(
                {
                    "id": "Java:FHGM:base:" + str(release),
                    "consumer": consumer,
                    "logical_reference": "FHGM:base:" + str(release),
                    "label": DRAFT_LABEL,
                    "class": "base-carrier",
                    "repository": "FAIR-bioHeaders/FAIR-bioHeaders-Specification",
                    "path": base.get("path"),
                    "revision": release,
                    "revision_kind": "tag",
                    "sha256": base.get("sha256"),
                    "bytes": base.get("size"),
                    "recorded_resolved_commit": base.get("commit"),
                    "recorded_vectors": None,
                    "local": None,
                }
            )
    return rows


def consumer_report(defaults, runtime):
    rows = []
    for consumer, path in [("Tools", None), *CONSUMERS.items()]:
        snapshot = {"commit": None, "branch": None}
        detail = "local runtime registry, not a fetched branch"
        try:
            if path is None:
                document = runtime
            else:
                repository = "FAIR-bioHeaders/FAIR-bioHeaders-Tools-" + consumer
                raw, snapshot, detail = defaults.read(repository, path)
                if not raw:
                    raise ValueError(detail)
                document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("consumer provenance is not a JSON object")
            records = consumer_records(consumer, document)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            rows.append(
                {
                    "consumer": consumer,
                    "status": "UNAVAILABLE",
                    "detail": str(error),
                    "provenance_path": path,
                    "consumer_commit": snapshot["commit"],
                }
            )
            continue
        for reference in records:
            row = {
                **reference,
                "provenance_path": path or "bioheaders/schemas/bundled.json",
                "consumer_commit": snapshot["commit"],
                "consumer_branch": snapshot["branch"],
                "provenance_detail": detail,
                "integrity": None,
                "currency": None,
            }
            if (
                not isinstance(reference["sha256"], str)
                or not DIGEST.fullmatch(reference["sha256"])
                or not isinstance(reference["revision"], str)
                or not (
                    SHA.fullmatch(reference["revision"])
                    if reference["revision_kind"] == "commit"
                    else re.fullmatch(r"v[0-9]+(?:\.[0-9]+)+", reference["revision"])
                )
            ):
                row.update(
                    status="NOT_RECORDED",
                    detail="no complete commit/digest record; not a pin or acceptance claim",
                )
            else:
                integrity = defaults.auditor.one(reference)
                row.update(
                    integrity=integrity,
                    currency=defaults.compare(reference, integrity),
                    status="RECORDED",
                )
            rows.append(row)
    groups = {}
    for row in rows:
        if (row.get("integrity") or {}).get("verdict") == FRESH:
            key = row["logical_reference"] + ":" + row["sha256"]
            groups.setdefault(key, []).append(
                {"consumer": row["consumer"], "revision": row["revision"]}
            )
    return {
        "scope": "known FHT/FHGM contract/suite records and explicitly embedded Java bases; other carrier records outside these provenance sources are not inventoried; no native acceptance or implementation parity",
        "rows": rows,
        "verified_digest_groups": groups,
    }


def format_extra(currency, consumers, metadata_controls=()):
    lines = []
    for control in metadata_controls:
        lines.append(
            "default metadata control {}: negative={} HTTP={}".format(
                control["repository"], control["negative_control_ok"], control["status"]
            )
        )
    if currency is not None:
        lines.extend(
            [
                "",
                "Default-content comparison (advisory; historical release pins remain valid):",
            ]
        )
        for row in currency:
            lines.append("  {} {}: {}".format(row["status"], row["id"], row["detail"]))
            if row["default_commit"]:
                lines.append(
                    "    recorded {} {}; default {} {} {}".format(
                        row["recorded_revision"],
                        row["recorded_sha256"],
                        row["default_branch"],
                        row["default_commit"],
                        row["default_sha256"],
                    )
                )
    if consumers is not None:
        lines.extend(
            ["", "Known-consumer records — draft, not acceptance:", consumers["scope"]]
        )
        for row in consumers["rows"]:
            lines.append(
                "  {} {} {}: revision={} digest={} recorded-vectors={} integrity={} currency={}".format(
                    row["consumer"],
                    row.get("logical_reference", "provenance"),
                    row["status"],
                    row.get("revision"),
                    row.get("sha256"),
                    row.get("recorded_vectors"),
                    (row.get("integrity") or {}).get("verdict"),
                    (row.get("currency") or {}).get("status"),
                )
            )
            if row.get("detail"):
                lines.append("    " + row["detail"])
        lines.append(
            "Digest-equivalent records preserve their different commit meanings; no commit is rewritten."
        )
    return "\n".join(lines)
