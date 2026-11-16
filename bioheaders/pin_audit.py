# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Advisory cross-repo pin audit — the reference gate of FAIR-bioHeaders-Specification#241.

Every FAIR-bioHeaders repository holds copies of bytes owned elsewhere: released
schemas, draft schemas, conformance manifests, and the base (carrier) schema a
draft embeds. The libraries' ``draft-pin-freshness`` jobs answer one question —
*do the draft bytes I vendored still match the owning repository's live
``main``?* Two defects found on 2026-11-15 were not that question, which is why
both passed a federation whose freshness machinery was green:

* **a released contract, stale in the tree that owns it.** ``FHP-Specification``
  held ``fhp.json`` at the bytes of specification tag ``v0.5.0`` while the
  released authority at tag ``v0.6.0`` had moved to FHP 1.2. The tree was
  *uniformly* stale, so ``check_linkml``, ``check_schema_drift`` and
  ``check_release.py`` all passed: a self-consistency gate cannot detect drift
  that both sides of the comparison share, and comparing against ``main`` would
  not have caught it either.
* **a released carrier rejected by a draft harness.** FHGM pins FHGFF3
  ``v0.5.0`` as its base schema, so a real FHGM payload inside a released 1.2
  header fails the draft's own harness. The stale pin was the base/carrier one:
  an axis nothing tracked.

This module checks **four reference classes** against the authoritative bytes at
the exact revision each reference names (the table is ``pins.json`` beside this
module, and docs/PIN-AUDIT.md lists every row with its measurement):

====================  ===========================================  ==============
class                 authority                                    revision kind
====================  ===========================================  ==============
``released-contract`` a specification release's published schema    **tag**
``draft-contract``    the owning development repository's           commit
                      schema at a recorded commit
``conformance-suite`` the owning repository's                       suite commit
                      ``conformance/manifest.json`` at a commit
``base-carrier``      the released schema a draft embeds, at the    **tag**
                      tag that draft pins
====================  ===========================================  ==============

Two rules are structural, not optional (both from #241):

1. **Anything released is named by a tag, never by ``main``.** A row in a
   released class whose revision is not a tag is reported as unusable, not
   silently compared.
2. **Contract pin, suite pin and base pin are three references.** They move
   independently — the FHT contract is byte-identical at ``226f923`` and
   ``24d3b03`` while its suite gained a vector between them — so each gets a row.

The report is **advisory**: it prints ``FRESH`` / ``DRIFT`` / ``ABSENT`` with the
recorded digest, the measured digest and the revision; it never writes a pin
(nothing here opens a file for writing, and ``--json`` carries ``"wrote": []``);
and its exit status is 0 whatever it finds unless the operator opts in with
``--exit-on-drift``. Re-pinning stays a deliberate, dated commit in the repository
that holds the pin.

Draft material keeps its draft label in every output form: an FHT or FHGM row
says ``draft, not acceptance`` and never reads as a released contract (rule V7 of
the shared docs/SCHEMA-VERSIONS.md).

Every backend also runs a **negative control**: it is asked for bytes that must
not exist, and a backend that answers them fails its control, which downgrades
that backend's verdicts to ``ABSENT`` with the reason. A backend that returns 200
for everything would otherwise turn ``DRIFT`` into ``FRESH`` silently. Redirects
are never followed: for a gate that asks whether *these bytes at this revision*
still exist, a 301 is a finding, not a success.

Usage::

    bioheaders-pin-audit                # advisory text table, exit 0
    bioheaders-pin-audit --json         # machine-readable
    bioheaders-pin-audit --only fhp     # id substring filter, or --class base-carrier
    bioheaders-pin-audit --checkout FAIR-bioHeaders/FAIR-bioHeaders-Specification=/path
    bioheaders-pin-audit --fixture-dir /path/to/authority  # offline, <repo>@<rev>/<path>
    bioheaders-pin-audit --conflicts .  # unresolved merge-marker probe

Standard library only: no dependency and no install surface beyond the
``bioheaders-pin-audit`` console script of this same distribution.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from importlib.resources import files
from pathlib import Path

#: The reference classes of FAIR-bioHeaders-Specification#241, in report order.
CLASSES = (
    "released-contract",
    "draft-contract",
    "conformance-suite",
    "base-carrier",
)
#: Classes whose authority is a release, so rule 1 requires a tag.
RELEASED_CLASSES = {"released-contract", "base-carrier"}
FRESH = "FRESH"
DRIFT = "DRIFT"
ABSENT = "ABSENT"
#: A file name that must not exist at any revision. Asked of every backend on
#: every run (the family's 404 control), so a permissive backend is visible.
CONTROL_NAME = "pin-audit-404-control.json"
DRAFT_LABEL = "draft, not acceptance"
RELEASED_LABEL = "released"
RAW_BASE = "https://raw.githubusercontent.com"
#: Unresolved merge-conflict markers, anchored at column 0 with the trailing
#: space, as ``git grep -I`` looks for them. A bare ``=======`` line is not
#: probed: in Markdown and setext documentation it is a valid heading underline.
CONFLICT_PATTERNS = ("^<<<<<<< ", "^>>>>>>> ")


def _slug(repository):
    """``owner/name`` to its repository name, used for URL and fixture paths."""
    return repository.rsplit("/", 1)[-1]


def _guess_root():
    """A checkout root when running from a clone, the package's parent otherwise.

    ``local`` entries in the table are checkout paths; against an installed wheel
    they resolve only as far as the package data, which is why the status they
    produce is reported separately from the verdict."""
    candidate = Path(__file__).resolve().parents[1]
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return Path.cwd()


class HttpsResolver:
    """``raw.githubusercontent.com`` at a literal ref, redirects refused."""

    name = "https"

    def __init__(self, timeout):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirectHandler())

    def resolve(self, repository, revision, path):
        url = "{}/{}/{}/{}".format(
            RAW_BASE, repository, revision, urllib.parse.quote(path)
        )
        request = urllib.request.Request(
            url, headers={"User-Agent": "bioheaders-pin-audit"}
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.read(), "GET {} -> {}".format(url, response.status)
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location") if error.headers else None
            arrow = " -> {}".format(location) if location else ""
            return None, "GET {} -> {}{}".format(url, error.code, arrow)
        except (urllib.error.URLError, OSError) as error:
            return None, "GET {} unreachable: {}".format(url, error)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Let a 3xx surface as an :class:`urllib.error.HTTPError`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CheckoutResolver:
    """``git show <revision>:<path>`` in a local clone: bytes at the named revision."""

    name = "checkout"

    def __init__(self, checkout):
        self.checkout = checkout

    def resolve(self, repository, revision, path):
        if not Path(self.checkout).is_dir():
            return None, "no checkout at {}".format(self.checkout)
        spec = "{}:{}".format(revision, path)
        try:
            result = subprocess.run(
                ["git", "-C", str(self.checkout), "show", spec], capture_output=True
            )
        except OSError as error:
            return None, "git show {} unavailable: {}".format(spec, error)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", "replace").strip().splitlines()
            return None, "git show {} failed: {}".format(
                spec, stderr[0] if stderr else "no stderr"
            )
        return result.stdout, "git show {}".format(spec)


class FixtureResolver:
    """Offline bytes laid out as ``<dir>/<repo-name>@<revision>/<path>``.

    The revision is part of the directory name on purpose: an authority that
    ignored it could not express "the bytes *at that revision*", which is the
    whole point of the gate."""

    name = "fixture"

    def __init__(self, fixture_dir):
        self.fixture_dir = fixture_dir

    def resolve(self, repository, revision, path):
        target = (
            Path(self.fixture_dir) / "{}@{}".format(_slug(repository), revision) / path
        )
        if not target.is_file():
            return None, "no bytes at {}".format(target)
        return target.read_bytes(), "read {}".format(target)


class OfflineResolver:
    """Refuses to resolve anything, with the reason it refused."""

    name = "offline"

    def __init__(self, reason):
        self.reason = reason

    def resolve(self, repository, revision, path):
        return None, self.reason


class Auditor:
    """Score every reference of a table against the bytes its revision names."""

    def __init__(self, options, root=None):
        self.options = options
        self.root = Path(root) if root else _guess_root()
        self.checkouts = dict(options.checkouts or {})
        self._resolvers = {}
        self._controls = {}

    def resolver_for(self, reference):
        repository = reference["repository"]
        if self.options.fixture_dir:
            resolver = FixtureResolver(self.options.fixture_dir)
        elif repository in self.checkouts:
            resolver = CheckoutResolver(self.checkouts[repository])
        elif self.options.offline:
            resolver = OfflineResolver(
                "--offline: no --checkout mapping for {}".format(repository)
            )
        else:
            resolver = HttpsResolver(self.options.timeout)
        key = (resolver.name, repository, reference.get("revision"))
        self._resolvers.setdefault(key, resolver)
        if key not in self._controls:
            if isinstance(resolver, OfflineResolver):
                # Nothing was asked of the network, so nothing can be claimed
                # about a negative control: recording one would be a false pass.
                self._controls[key] = (None, "not probed (--offline)")
            else:
                data, where = resolver.resolve(
                    repository, reference.get("revision"), CONTROL_NAME
                )
                self._controls[key] = (data is None, where)
        return resolver, self._controls[key]

    def audit(self, references):
        return [self.one(reference) for reference in references]

    def control_report(self):
        """One entry per (backend, repository, revision) pair actually probed."""
        report = []
        for (name, repository, revision), (ok, where) in sorted(self._controls.items()):
            report.append(
                {
                    "backend": name,
                    "repository": repository,
                    "revision": revision,
                    "negative_control_ok": ok,
                    "probe": where,
                }
            )
        return report

    def one(self, reference):
        result = {
            "id": reference["id"],
            "class": reference["class"],
            "label": reference.get("label", RELEASED_LABEL),
            "repository": reference["repository"],
            "revision": reference.get("revision"),
            "revision_kind": reference.get("revision_kind"),
            "path": reference.get("path"),
            "local": reference.get("local"),
            "recorded_sha256": reference.get("sha256"),
            "recorded_bytes": reference.get("bytes"),
            "note": reference.get("note"),
            "verdict": ABSENT,
            "detail": None,
            "backend": None,
            "authority": None,
            "authority_sha256": None,
            "authority_bytes": None,
            "control": None,
            "local_status": None,
            "local_sha256": None,
            "local_bytes": None,
        }
        unusable = self.shape_problem(reference)
        if unusable:
            result["detail"] = unusable
            return result
        local_status, local_digest, local_bytes = self.local_state(reference)
        result["local_status"] = local_status
        result["local_sha256"] = local_digest
        result["local_bytes"] = local_bytes
        resolver, control = self.resolver_for(reference)
        result["backend"] = resolver.name
        control_ok, control_where = control
        if control_ok is None:
            result["control"] = control_where
        elif control_ok:
            result["control"] = "negative control 404 as expected"
        else:
            result["control"] = "FAILED: {}".format(control_where)
            result["detail"] = (
                "backend control probe was not negative ({}); verdicts from this "
                "backend are not trustworthy".format(control_where)
            )
            return result
        data, where = resolver.resolve(
            reference["repository"], reference["revision"], reference["path"]
        )
        result["authority"] = where
        if data is None:
            result["detail"] = "authority unavailable: {}".format(where)
            return result
        digest = hashlib.sha256(data).hexdigest()
        result["authority_sha256"] = digest
        result["authority_bytes"] = len(data)
        if digest != reference["sha256"]:
            result["verdict"] = DRIFT
            result["detail"] = "recorded {} != authority {}".format(
                reference["sha256"], digest
            )
        elif reference.get("bytes") is not None and reference["bytes"] != len(data):
            result["verdict"] = DRIFT
            result["detail"] = "recorded {} bytes != authority {} bytes".format(
                reference["bytes"], len(data)
            )
        else:
            result["verdict"] = FRESH
        lag = self.lag(reference)
        if lag:
            result["lag"] = lag
        return result

    @staticmethod
    def shape_problem(reference):
        """Why a reference cannot be scored at all, or None.

        These are the documented holes: an unrecorded digest or an unrecorded
        revision produces ``ABSENT`` with the reason, never a pass."""
        if reference.get("class") not in CLASSES:
            return "unknown reference class {!r}".format(reference.get("class"))
        if not reference.get("repository"):
            return "no authority repository recorded"
        if not reference.get("sha256"):
            return (
                reference.get("no_pin_detail")
                or "no digest recorded for this reference"
            )
        if (
            reference["class"] in RELEASED_CLASSES
            and reference.get("revision_kind") != "tag"
        ):
            return (
                "released material must be named by a tag, not {!r} "
                "(FAIR-bioHeaders-Specification#241 rule 1)".format(
                    reference.get("revision")
                )
            )
        if not reference.get("path"):
            return reference.get("no_pin_detail") or "no upstream path recorded"
        if not reference.get("revision"):
            return reference.get("no_pin_detail") or "no upstream revision recorded"
        return None

    def local_state(self, reference):
        """How the vendored copy relates to the recorded digest, on its own axis.

        A tree can be *uniformly* stale — local bytes and recorded digest agree,
        both differ from the release — and that is the #241(a) case, so the two
        axes are reported apart."""
        local = reference.get("local")
        if not local:
            return "NOT VENDORED", None, None
        path = self.root / local
        if not path.is_file():
            return "MISSING", None, None
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        status = (
            "MATCHES RECORD"
            if digest == reference.get("sha256")
            else "DIFFERS FROM RECORD"
        )
        return status, digest, len(data)

    def lag(self, reference):
        """Advisory text when a base/carrier pin names an older release than the
        registry's current one — the shape of #241(b).

        Only the base/carrier class gets this: a frozen released-contract snapshot
        *should* name its own older tag, and saying so on every row would bury the
        one case where a lag is a decision someone has to take."""
        if reference["class"] != "base-carrier":
            return None
        newest = getattr(self.options, "current_release", None)
        revision = reference.get("revision") or ""
        if not newest or not revision.startswith("v"):
            return None
        if version_key(revision) < version_key(newest):
            return "pinned {}, current release is {}".format(revision, newest)
        return None


def version_key(tag):
    match = re.match(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)", tag)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def load_table(path=None):
    """Read the reference table: JSON data, never prose (#241 acceptance 1)."""
    if path is None:
        text = files("bioheaders").joinpath("pins.json").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    table = json.loads(text)
    missing = [key for key in ("tableVersion", "references") if key not in table]
    if missing:
        raise ValueError("reference table has no {!r}".format("/".join(missing)))
    unknown = sorted(
        {
            reference.get("class")
            for reference in table["references"]
            if reference.get("class") not in CLASSES
        }
    )
    if unknown:
        raise ValueError("unknown reference classes: {}".format(", ".join(unknown)))
    return table


def conflict_markers(paths, root=None):
    """Look for unresolved merge-conflict markers in each git repository.

    The precedent is concrete: ``FHP-Specification/CHANGELOG.md`` carried an
    unresolved conflict on ``main`` for about three and a half weeks (introduced
    by ``5cf0613``, PR #12, merged 2026-10-22; closed by that repository's #34).
    A scan of all fourteen federation repositories found exactly one file with
    one occurrence, and no gate in any of them looked for a conflict marker at
    all. One ``git grep`` is the cheapest integrity probe available, so the gate
    carries it."""
    findings = []
    for entry in paths:
        target = Path(entry)
        if not target.is_absolute():
            target = (root or Path.cwd()) / entry
        command = ["git", "-C", str(target), "grep", "-I", "-n"]
        for pattern in CONFLICT_PATTERNS:
            command += ["-e", pattern]
        try:
            result = subprocess.run(command, capture_output=True, text=True)
        except OSError as error:  # git is not installed
            findings.append(
                {
                    "path": str(target),
                    "status": "SKIPPED",
                    "detail": str(error),
                    "hits": [],
                }
            )
            continue
        hits = [line for line in result.stdout.splitlines() if line.strip()]
        if result.returncode == 0:
            findings.append(
                {
                    "path": str(target),
                    "status": "MARKERS",
                    "detail": "{} marker line(s)".format(len(hits)),
                    "hits": hits,
                }
            )
        elif result.returncode == 1:  # git grep: no matches
            findings.append(
                {"path": str(target), "status": "NONE", "detail": "clean", "hits": []}
            )
        else:
            detail = (result.stderr.strip().splitlines() or ["git grep failed"])[0]
            findings.append(
                {"path": str(target), "status": "SKIPPED", "detail": detail, "hits": []}
            )
    return findings


def tally(results):
    counts = {FRESH: 0, DRIFT: 0, ABSENT: 0}
    for result in results:
        counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
    return counts


def format_text(table, results, findings, controls):
    """The human-readable report: quiet when green, explicit when not.

    A ``FRESH`` row is one line with its revision and digest. Anything else gets
    its reason printed, because an advisory report nobody can act on is not
    advisory, it is decoration. Draft rows carry their label in every state."""
    lines = [
        "Cross-repo pin audit (FAIR-bioHeaders-Specification#241) — table version "
        "{}, {} references.".format(table.get("tableVersion"), len(results))
    ]
    grouped = {}
    for control in controls:
        grouped.setdefault((control["backend"], control["repository"]), []).append(
            control
        )
    for (backend, repository), entries in grouped.items():
        states = {control["negative_control_ok"] for control in entries}
        if False in states:
            state = "CONTROL FAILED"
        elif states == {True}:
            state = "negative control 404 as expected"
        else:
            state = "control not probed"
        lines.append(
            "  backend {} {}: {} at {} revision(s); e.g. {}".format(
                backend, repository, state, len(entries), entries[0]["probe"]
            )
        )
    for cls in CLASSES:
        rows = [result for result in results if result["class"] == cls]
        if not rows:
            continue
        lines.append("")
        lines.append("{} — {} reference(s)".format(cls, len(rows)))
        for result in rows:
            where = "{}@{}".format(result["path"] or "-", result["revision"] or "-")
            tail = (
                "  [{}]".format(DRAFT_LABEL) if result["label"] == DRAFT_LABEL else ""
            )
            recorded = (result["recorded_sha256"] or "-")[:12]
            authority = (result["authority_sha256"] or "-")[:12]
            if result["verdict"] == FRESH:
                lines.append(
                    "  {:<7} {:<38} {:<40} {} {}{}".format(
                        result["verdict"],
                        result["id"],
                        where,
                        recorded,
                        authority,
                        tail,
                    )
                )
                if result.get("lag"):
                    # A base/carrier pin that agrees with itself and still sits
                    # behind the released carrier: the verdict is right and the
                    # note is the finding, so it prints even on a FRESH row.
                    lines.append("          lag: {}".format(result["lag"]))
                continue
            lines.append(
                "  {:<7} {:<38} {:<40} recorded {} authority {}{}".format(
                    result["verdict"], result["id"], where, recorded, authority, tail
                )
            )
            for key in ("detail", "local_status", "lag"):
                if result.get(key):
                    lines.append(
                        "          {}: {}".format(key.replace("_", " "), result[key])
                    )
    counts = tally(results)
    lines.append("")
    lines.append(
        "summary: {} FRESH, {} DRIFT, {} ABSENT of {}".format(
            counts[FRESH], counts[DRIFT], counts[ABSENT], len(results)
        )
    )
    for finding in findings:
        lines.append(
            "conflict markers: {:<8} {} ({})".format(
                finding["status"], finding["path"], finding["detail"]
            )
        )
        for hit in finding["hits"][:20]:
            lines.append("    {}".format(hit))
    if any(result["label"] == DRAFT_LABEL for result in results):
        lines.append(
            "draft rows are {}, listed as the references they are: development bytes "
            "at a commit, with no release tag, no w3id alias, no row in "
            "schemas/versions.json and no acceptance implied (rule V7 of "
            "docs/SCHEMA-VERSIONS.md).".format(DRAFT_LABEL)
        )
    lines.append(
        "advisory only: FRESH/DRIFT/ABSENT change no file and no pin. Re-pinning is a "
        "deliberate, dated commit in the repository that holds the pin."
    )
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bioheaders-pin-audit",
        description=(
            "Advisory cross-repo pin audit (FAIR-bioHeaders-Specification#241): "
            "compare each recorded released-contract, draft-contract, "
            "conformance-suite and base-carrier reference with the authoritative "
            "bytes at the revision it names. Reads only: it never re-pins, and it "
            "exits 0 whatever it finds unless --exit-on-drift is given."
        ),
    )
    parser.add_argument(
        "--pin-file",
        help="reference table to audit (default: the bundled bioheaders/pins.json)",
    )
    parser.add_argument(
        "--class",
        dest="only_class",
        action="append",
        choices=CLASSES,
        help="audit only this reference class (repeatable)",
    )
    parser.add_argument(
        "--only",
        action="append",
        help="audit only ids containing this text (repeatable)",
    )
    parser.add_argument(
        "--root",
        help="checkout that the table's local paths resolve against "
        "(default: this package's checkout, else the current directory)",
    )
    parser.add_argument(
        "--checkout",
        action="append",
        metavar="REPOSITORY=PATH",
        help="resolve REPOSITORY from a local git checkout at the named revision "
        "(repeatable) instead of over HTTPS",
    )
    parser.add_argument(
        "--fixture-dir",
        help="offline authority directory laid out as <repo>@<revision>/<path>",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="make no network request at all: unmapped references report ABSENT",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("PIN_AUDIT_TIMEOUT", 30)),
        help="HTTPS timeout in seconds (default: 30, or PIN_AUDIT_TIMEOUT)",
    )
    parser.add_argument(
        "--conflicts",
        action="append",
        metavar="PATH",
        help="also probe PATH, a git repository, for unresolved merge-conflict "
        "markers (repeatable; default: the current directory)",
    )
    parser.add_argument(
        "--no-conflicts", action="store_true", help="skip the conflict-marker probe"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--exit-on-drift",
        action="store_true",
        help="exit 1 when any reference reports DRIFT (opt-in: the default is advisory)",
    )
    return parser


def parse_checkouts(values):
    mapping = {}
    for value in values or []:
        if "=" not in value:
            raise SystemExit("--checkout wants REPOSITORY=PATH, got {!r}".format(value))
        repository, path = value.split("=", 1)
        mapping[repository.strip()] = path.strip()
    return mapping


def select_references(table, options):
    return [
        reference
        for reference in table["references"]
        if (not options.only_class or reference["class"] in options.only_class)
        and (
            not options.only
            or any(needle in reference["id"] for needle in options.only)
        )
    ]


def main(argv=None):
    """Entry point of the ``bioheaders-pin-audit`` console script."""
    parser = build_parser()
    options = parser.parse_args(argv)
    options.checkouts = parse_checkouts(options.checkout)
    try:
        table = load_table(options.pin_file)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            "bioheaders-pin-audit: cannot load the reference table: {}".format(error),
            file=sys.stderr,
        )
        return 2
    options.current_release = (table.get("current_release") or "").strip()
    references = select_references(table, options)
    auditor = Auditor(options, root=options.root)
    results = auditor.audit(references)
    controls = auditor.control_report()
    findings = (
        []
        if options.no_conflicts
        else conflict_markers(options.conflicts or ["."], root=Path.cwd())
    )
    if options.json:
        report = {
            "tool": "bioheaders-pin-audit",
            "advisory": True,
            "wrote": [],
            "table_version": table.get("tableVersion"),
            "current_release": options.current_release,
            "tally": tally(results),
            "controls": controls,
            "references": results,
            "conflict_markers": findings,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_text(table, results, findings, controls))
    if options.exit_on_drift and tally(results)[DRIFT]:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
