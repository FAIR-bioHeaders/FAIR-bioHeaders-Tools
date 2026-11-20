# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Opt-in online checks (010 FR-010, FR-011, research R-10; T053).

No test reaches the internet. Tests marked ``online_local`` talk only to an
``http.server`` bound to 127.0.0.1, with the private-address refusal turned off
for that test through the test-only module attribute; every other test runs
with sockets disabled (tests/conftest.py).
"""

import http.server
import json
import subprocess
import sys
import threading
import time

import pytest
from assess_helpers import FIXTURES, result, status

from bioheaders.assess import assess_file

ACCESS = ("RDA-A1-03D", "RDA-A1-04D", "RDA-A1-05D", "RDA-A1.1-01D")
URL_ACCESS = ("RDA-A1-04D", "RDA-A1-05D", "RDA-A1.1-01D")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _record(self):
        self.server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
            }
        )

    def _respond(self, code, headers=()):
        self.send_response(code)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _route(self):
        self._record()
        path = self.path
        if path.startswith("/redirect/"):
            remaining = int(path.rsplit("/", 1)[1])
            # /redirect/N answers with N redirects before /ok.
            target = "/ok" if remaining <= 1 else f"/redirect/{remaining - 1}"
            return self._respond(302, [("Location", target)])
        if path == "/to-ftp":
            return self._respond(302, [("Location", "ftp://example.org/file.gff3")])
        if path == "/nohead" and self.command == "HEAD":
            return self._respond(405)
        if path == "/slow":
            time.sleep(1.5)
        if path.startswith("/missing") or path.startswith("/doi/10.1234/missing"):
            return self._respond(404)
        code = 206 if "range" in {k.lower() for k in self.headers} else 200
        return self._respond(code)

    do_HEAD = _route
    do_GET = _route


@pytest.fixture
def server(monkeypatch):
    from bioheaders.assess import online

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    httpd.requests = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    monkeypatch.setattr(online, "ALLOW_PRIVATE_ADDRESSES_FOR_TESTS", True)
    monkeypatch.setattr(online, "DOI_RESOLVER", base + "/doi/")
    monkeypatch.setattr(online, "IDENTIFIERS_RESOLVER", base + "/id/")
    httpd.base = base
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def header(tmp_path, *lines, name="input.gff3", start="##gff-version 3"):
    path = tmp_path / name
    path.write_text("\n".join((start,) + lines) + "\n", encoding="utf-8")
    return path


def paths(server):
    return sorted({r["path"] for r in server.requests})


def checks(report):
    return {c["target"]: c for c in report["online"]["checks"]}


@pytest.mark.online_local
def test_without_online_nothing_is_requested(server, tmp_path):
    path = header(
        tmp_path, f"#!relatedLink {server.base}/ok", "#!identifier doi:10.1/x"
    )
    report = assess_file(path)
    assert server.requests == []
    assert report["online_checks"] == "not_requested"
    assert "online" not in report
    for indicator in ACCESS:
        found = result(report, indicator)
        assert (found["status"], found["reason"]) == (
            "not_assessed",
            "online-check-not-requested",
        )


def test_the_online_module_is_imported_only_with_online():
    code = (
        "import sys; from bioheaders.assess import assess_file; "
        f"assess_file({str(FIXTURES / 'no-header.fa')!r}); "
        "print('bioheaders.assess.online' in sys.modules)"
    )
    output = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert output.stdout.strip() == "False"


@pytest.mark.online_local
def test_only_header_identifiers_and_urls_are_requested(server, tmp_path):
    path = header(
        tmp_path,
        "#!identifier doi:10.1234/abc",
        f"#!relatedLink {server.base}/ok",
        f"#!relatedLink {server.base}/ok",  # requested once (de-duplicated)
        "#!species https://identifiers.org/taxonomy:6239".replace(
            "https://identifiers.org/", server.base + "/id/"
        ),
    )
    report = assess_file(path, online=True)
    assert paths(server) == ["/doi/10.1234/abc", "/id/taxonomy:6239", "/ok"]
    assert [r["path"] for r in server.requests].count("/ok") == 1
    for request in server.requests:
        assert request["method"] == "HEAD"
        assert request["headers"].get("content-length", "0") == "0"
        assert request["headers"]["user-agent"].startswith("bioheaders-assess/")
        assert "cookie" not in request["headers"]
        assert "authorization" not in request["headers"]
    assert report["online_checks"] == "ran"
    for indicator in ACCESS:
        found = result(report, indicator)
        assert found["status"] == "evidenced", indicator
        assert found["method"] == "online"
    for check in report["online"]["checks"]:
        assert check["time_dependent"] is True
        assert check["checked_at"].endswith("Z")
        assert check["outcome"] == "resolved"
    online_checks = checks(report)
    assert (
        online_checks["doi:10.1234/abc"]["request_url"]
        == server.base + "/doi/10.1234/abc"
    )
    assert online_checks["doi:10.1234/abc"]["http_status"] == 200


@pytest.mark.online_local
def test_head_falls_back_to_get_with_a_one_byte_range(server, tmp_path):
    path = header(tmp_path, f"#!relatedLink {server.base}/nohead")
    report = assess_file(path, online=True)
    assert [(r["method"], r["path"]) for r in server.requests] == [
        ("HEAD", "/nohead"),
        ("GET", "/nohead"),
    ]
    assert server.requests[1]["headers"]["range"] == "bytes=0-0"
    assert "content-length" not in server.requests[1]["headers"]
    assert checks(report)[f"{server.base}/nohead"]["http_status"] == 206
    assert status(report, "RDA-A1-04D") == "evidenced"


@pytest.mark.online_local
def test_redirects_are_followed_up_to_five(server, tmp_path):
    path = header(
        tmp_path,
        f"#!relatedLink {server.base}/redirect/5",
        f"#!relatedLink {server.base}/redirect/6",
    )
    report = assess_file(path, online=True)
    found = checks(report)
    five, six = found[f"{server.base}/redirect/5"], found[f"{server.base}/redirect/6"]
    assert five["outcome"] == "resolved"
    assert five["final_url"] == f"{server.base}/ok"
    assert six["outcome"] == "unavailable"
    assert all(r["method"] == "HEAD" for r in server.requests)
    assert status(report, "RDA-A1-04D") == "evidenced"  # one URL resolved


@pytest.mark.online_local
def test_redirect_to_another_scheme_is_refused(server, tmp_path):
    path = header(tmp_path, f"#!relatedLink {server.base}/to-ftp")
    report = assess_file(path, online=True)
    assert checks(report)[f"{server.base}/to-ftp"]["outcome"] == "refused"
    found = result(report, "RDA-A1-04D")
    assert (found["status"], found["reason"]) == (
        "not_assessed",
        "online-check-unavailable",
    )


@pytest.mark.online_local
def test_private_addresses_are_refused_by_default(server, tmp_path, monkeypatch):
    from bioheaders.assess import online

    monkeypatch.setattr(online, "ALLOW_PRIVATE_ADDRESSES_FOR_TESTS", False)
    path = header(
        tmp_path,
        f"#!relatedLink {server.base}/ok",
        f"#!relatedLink http://localhost:{server.server_address[1]}/ok",
    )
    report = assess_file(path, online=True)
    assert server.requests == []
    assert {c["outcome"] for c in report["online"]["checks"]} == {"refused"}
    assert status(report, "RDA-A1-04D") == "not_assessed"


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fd00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "::127.0.0.1",
        "::100.64.0.1",
        "224.0.0.1",
    ],
)
def test_address_vetting_refuses_internal_addresses(address):
    from bioheaders.assess import online

    assert not online.public_address(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
def test_address_vetting_allows_public_addresses(address):
    from bioheaders.assess import online

    assert online.public_address(address)


def test_other_schemes_and_credentials_are_refused_without_a_request(tmp_path):
    path = header(
        tmp_path,
        "#!relatedLink ftp://ftp.example.org/pub/file.gff3",
        "#!relatedLink file:///etc/passwd",
        "#!relatedLink https://user:secret@example.org/file.gff3",
    )
    report = assess_file(path, online=True)  # sockets are disabled here
    assert {c["outcome"] for c in report["online"]["checks"]} == {"refused"}
    assert all(c["http_status"] is None for c in report["online"]["checks"])


@pytest.mark.online_local
def test_a_timeout_gives_not_assessed_unavailable(server, tmp_path):
    path = header(tmp_path, f"#!relatedLink {server.base}/slow")
    report = assess_file(path, online=True, online_timeout=0.3)
    assert checks(report)[f"{server.base}/slow"]["outcome"] == "unavailable"
    for indicator in URL_ACCESS:
        found = result(report, indicator)
        assert (found["status"], found["reason"], found["method"]) == (
            "not_assessed",
            "online-check-unavailable",
            "online",
        )


@pytest.mark.online_local
def test_not_found_gives_not_evidenced_with_a_suggestion(server, tmp_path):
    path = header(tmp_path, f"#!relatedLink {server.base}/missing")
    report = assess_file(path, online=True)
    assert checks(report)[f"{server.base}/missing"]["outcome"] == "not_found"
    found = result(report, "RDA-A1-04D")
    assert found["status"] == "not_evidenced"
    assert found["method"] == "online"
    assert found["suggestion"]["guideline_item"] == "G8"


def test_nothing_to_resolve_gives_not_evidenced(tmp_path):
    report = assess_file(FIXTURES / "no-header.fa", online=True)
    assert report["online_checks"] == "ran"
    assert report["online"]["checks"] == []
    for indicator in ACCESS:
        assert status(report, indicator) == "not_evidenced"


@pytest.mark.online_local
def test_an_online_result_never_lowers_an_offline_status(server, tmp_path):
    path = header(
        tmp_path,
        "#!identifier doi:10.1234/missing",
        f"#!relatedLink {server.base}/missing",
        "#!species " + server.base + "/id/taxonomy:6239",
    )
    offline = assess_file(path)
    online = assess_file(path, online=True)
    for before, after in zip(offline["results"], online["results"]):
        if before["indicator"] in ACCESS:
            continue
        assert (before["status"], before["evidence"]) == (
            after["status"],
            after["evidence"],
        ), before["indicator"]
    assert status(online, "RDA-F1-01D") == status(offline, "RDA-F1-01D") == "evidenced"
    notes = result(online, "RDA-F1-01D").get("notes", [])
    assert any("doi:10.1234/missing" in note and "not found" in note for note in notes)
    assert status(online, "RDA-A1-03D") == "not_evidenced"


@pytest.mark.online_local
def test_the_schema_url_of_an_fhr_header_is_never_requested(server, tmp_path):
    path = tmp_path / "genome.fa"
    path.write_text(
        f";~schema: {server.base}/schema\n"
        ";~schemaVersion: 1.0\n"
        f";~relatedLink: ['{server.base}/ok']\n"
        f";~identifier: ['doi:10.1234/abc']\n"
        ">s1\nACGT\n",
        encoding="utf-8",
    )
    report = assess_file(path, online=True)
    assert "/schema" not in paths(server)
    assert "/ok" in paths(server)
    assert report["online_checks"] == "ran"
    assert f"{server.base}/schema" not in checks(report)


@pytest.mark.online_local
def test_the_text_and_markdown_reports_list_the_requests(server, tmp_path):
    from bioheaders.assess import render

    report = assess_file(
        header(tmp_path, f"#!relatedLink {server.base}/ok"), online=True
    )
    for text in (render.to_text(report), render.to_markdown(report)):
        assert "Online checks: ran" in text
        assert f"{server.base}/ok" in text
        assert "HTTP 200" in text


def bioheaders(*args):
    return subprocess.run(
        [sys.executable, "-m", "bioheaders", *map(str, args)], capture_output=True
    )


def test_online_timeout_without_online_is_a_usage_error():
    result = bioheaders("assess", "--online-timeout", "5", FIXTURES / "no-header.fa")
    assert result.returncode == 2
    assert b"--online" in result.stderr


def test_cli_online_flag(tmp_path):
    result = bioheaders(
        "assess", "--online", "--format", "json", FIXTURES / "no-header.fa"
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["online_checks"] == "ran"
    assert "Online checks" not in result.stderr.decode()
