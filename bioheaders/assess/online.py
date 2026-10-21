# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Opt-in online checks (FR-010, FR-011, research R-10).

Imported only when ``--online`` is given. Only identifiers and URLs taken from
the header are requested: a DOI through https://doi.org/, a CURIE through
https://identifiers.org/, and an http(s) URL as it is. Nothing from the file
is sent apart from that identifier or URL, and the schema URL of a
FAIR-bioHeaders header is never requested.

Each request uses ``urllib`` with only the HTTP(S) handlers installed (no
proxies from the environment, no cookies, no credentials, no FTP, file or data
URLs): HEAD, then GET with ``Range: bytes=0-0`` if HEAD fails, never a request
body, at most 5 redirects, each checked against the same rules, and a
per-request timeout. A host is connected to only through an address checked to
be public: loopback, private, link-local, multicast, reserved and unspecified
addresses are refused, and the connection uses the checked address, so a
second DNS answer cannot redirect it. Requests are de-duplicated per run and
made one at a time.
"""

import http.client
import ipaddress
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .. import __version__
from .model import OnlineCheck

DOI_RESOLVER = "https://doi.org/"
IDENTIFIERS_RESOLVER = "https://identifiers.org/"
USER_AGENT = f"bioheaders-assess/{__version__}"
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT = 10.0
# Test-only override (tests/assess_online_test.py) so that a server on 127.0.0.1
# can be used. There is deliberately no option or environment variable for it.
ALLOW_PRIVATE_ADDRESSES_FOR_TESTS = False
# Header concepts whose values may be resolved. Values of other concepts, and
# the FAIR-bioHeaders schema URL, are never requested.
CONCEPTS = ("data-identifier", "access-url", "taxon", "creator", "licence")
SCHEMES = ("http", "https")
DOI = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.I)
CURIE = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*):([^\s/][^\s]*)$")
UNSAFE = re.compile(r"[\x00-\x20\x7f]")


class Refused(OSError):
    """The scheme, the address or the URL form is not allowed."""


# NAT64 prefixes (RFC 6052, RFC 8215): the last 32 bits are an IPv4 address.
_NAT64 = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48"))


def _embedded_ipv4(ip):
    """IPv4 addresses that an IPv6 address carries (mapped, 6to4, Teredo, NAT64)."""
    if ip.version != 6:
        return []
    if ip.ipv4_mapped is not None:
        return [ip.ipv4_mapped]
    if ip.sixtofour is not None:
        return [ip.sixtofour]
    if ip.teredo is not None:
        return list(ip.teredo)  # The Teredo server and the client.
    if any(ip in network for network in _NAT64):
        return [ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)]
    return []


def _global_unicast(ip):
    return ip.is_global and not (
        ip.is_multicast
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or getattr(ip, "is_site_local", False)
    )


def public_address(address):
    """True if the IP ``address`` is a globally routable unicast address.

    Shared address space (100.64.0.0/10, used for cloud metadata services),
    site-local IPv6 (fec0::/10) and every other special-purpose range are
    refused. An IPv6 address that carries an IPv4 address (IPv4-mapped, 6to4,
    Teredo or NAT64) is judged by the IPv4 addresses it carries.
    """
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    embedded = _embedded_ipv4(ip)
    if embedded:
        return all(_global_unicast(item) for item in embedded)
    return _global_unicast(ip)


# Each request (with its redirects) must finish within REQUEST_DEADLINE_FACTOR
# times the timeout; the timeout alone applies to each socket operation, so a
# server sending one byte at a time could otherwise hold a request open.
REQUEST_DEADLINE_FACTOR = 3
_REQUEST = threading.local()


def _shutdown(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def _arm_deadline(sock):
    deadline = getattr(_REQUEST, "deadline", None)
    if deadline is None:
        return
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise socket.timeout("the request deadline has passed")
    timer = threading.Timer(remaining, _shutdown, (sock,))
    timer.daemon = True
    timer.start()
    _REQUEST.timers.append(timer)


def _vetted(host, port):
    """The first address of ``host`` if every address of it is allowed."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise OSError(f"cannot resolve {host}: {error}") from None
    addresses = [info[4][0] for info in infos]
    if not addresses:
        raise OSError(f"cannot resolve {host}")
    if not ALLOW_PRIVATE_ADDRESSES_FOR_TESTS:
        for address in addresses:
            if not public_address(address):
                raise Refused(f"{host} resolves to a non-public address {address}")
    return infos[0]


def _connect(connection):
    family, kind, proto, _name, address = _vetted(connection.host, connection.port)
    sock = socket.socket(family, kind, proto)
    try:
        sock.settimeout(connection.timeout)
        _arm_deadline(sock)
        sock.connect(address)
    except BaseException:
        sock.close()
        raise
    return sock


class _HTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = _connect(self)


class _HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        sock = _connect(self)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, request):
        return self.do_open(_HTTPConnection, request)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_HTTPSConnection, request)


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS
    max_repeats = MAX_REDIRECTS

    def redirect_request(self, request, fp, code, message, headers, url):
        _check_url(url)
        # request.headers holds only the headers set by Resolver (not Host).
        return urllib.request.Request(
            url,
            headers=dict(request.headers),
            origin_req_host=request.origin_req_host,
            unverifiable=True,
            method=request.get_method(),
        )


def _opener():
    opener = urllib.request.OpenerDirector()
    for handler in (
        _HTTPHandler(),
        _HTTPSHandler(),
        _Redirects(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def _check_url(url):
    if UNSAFE.search(url):
        raise Refused("the URL contains spaces or control characters")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in SCHEMES:
        raise Refused(f"scheme {parts.scheme or 'none'} is not http or https")
    if parts.username is not None or parts.password is not None:
        raise Refused("the URL contains credentials")
    if not parts.hostname:
        raise Refused("the URL has no host")
    try:
        literal = ipaddress.ip_address(parts.hostname)
    except ValueError:
        literal = None
    if (
        literal is not None
        and not ALLOW_PRIVATE_ADDRESSES_FOR_TESTS
        and not public_address(str(literal))
    ):
        raise Refused(f"{parts.hostname} is not a public address")


def request_url(target):
    """The URL to request for a header value, or None if it is not resolvable.

    Returns the value itself for a URL of any scheme (the scheme is checked
    when the request is made, so that a refusal is reported).
    """
    value = target.strip()
    found = DOI.match(value)
    if found:
        return DOI_RESOLVER + urllib.parse.quote(found.group(1), safe="/:;()._-~")
    parts = urllib.parse.urlsplit(value)
    if parts.scheme and parts.netloc:
        return value
    if parts.scheme and value.lower().startswith(("file:", "ftp:", "data:")):
        return value
    found = CURIE.match(value)
    if found and found.group(1).lower() not in ("http", "https", "urn", "mailto"):
        local = urllib.parse.quote(found.group(2), safe="/:;()._-~")
        return f"{IDENTIFIERS_RESOLVER}{found.group(1)}:{local}"
    return None


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Resolver:
    """Resolve header values one at a time, each at most once per run."""

    def __init__(self, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.opener = _opener()
        self.results = {}

    def check(self, target):
        """Return the OnlineCheck for ``target``, or None if it is not resolvable."""
        if target in self.results:
            return self.results[target]
        url = request_url(target)
        result = None if url is None else self._check(target, url)
        self.results[target] = result
        return result

    def _check(self, target, url):
        try:
            _check_url(url)
        except Refused:
            return OnlineCheck(target, url, "refused", _now())
        status, final, outcome = self._request(url, "HEAD")
        if status is not None and status >= 400:
            # Some servers refuse HEAD; ask for one byte instead.
            status, final, outcome = self._request(url, "GET")
        return OnlineCheck(target, url, outcome, _now(), final, status)

    def _request(self, url, method):
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        request = urllib.request.Request(url, headers=headers, method=method)
        deadline = time.monotonic() + REQUEST_DEADLINE_FACTOR * self.timeout
        _REQUEST.deadline = deadline
        _REQUEST.timers = []
        try:
            result = self._open(request)
            # Closing the socket at the deadline can end a response early, which
            # would otherwise read as a complete one.
            return (
                (None, None, "unavailable") if time.monotonic() >= deadline else result
            )
        finally:
            for timer in _REQUEST.timers:
                timer.cancel()
            _REQUEST.deadline = None

    def _open(self, request):
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.status, response.geturl(), "resolved"
        except urllib.error.HTTPError as error:
            error.close()
            outcome = "not_found" if error.code in (404, 410) else "unavailable"
            return error.code, error.geturl(), outcome
        except Refused:
            return None, None, "refused"
        except urllib.error.URLError as error:
            if isinstance(error.reason, Refused):
                return None, None, "refused"
            return None, None, "unavailable"
        except (OSError, http.client.HTTPException, ValueError):
            return None, None, "unavailable"


def targets(evidence):
    """{value: [evidence ids]} of the header values that may be resolved."""
    schema_values = {
        str(item.value).strip()
        for line in evidence
        for item in line.items
        if item.concept == "header-schema" and isinstance(item.value, str)
    }
    found = {}
    for line in evidence:
        if line.scope != "file":
            continue
        for item in line.items:
            if item.concept not in CONCEPTS or item.status == "malformed":
                continue
            if not isinstance(item.value, str) or not item.value.strip():
                continue
            value = item.value.strip()
            if value in schema_values:
                continue
            found.setdefault(value, [])
            if line.id not in found[value]:
                found[value].append(line.id)
    return found


def run(evidence, timeout=DEFAULT_TIMEOUT, resolver=None):
    """Resolve the header's targets; return ({value: outcome}, [OnlineCheck])."""
    resolver = resolver or Resolver(timeout)
    outcomes, checks = {}, []
    for value in sorted(targets(evidence)):
        check = resolver.check(value)
        if check is None:
            continue
        outcomes[value] = check.outcome
        checks.append(check)
    checks.sort(key=lambda c: (c.target, c.request_url))
    return outcomes, checks
