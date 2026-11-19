# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The JSON Schema validator the metadata readers use, with two corrections.

JSON Schema 2020-12 defines ``pattern`` by ECMA-262 regular expressions and
``format: date`` by RFC 3339 ``full-date``. The stock Python validator differs
from both in ways that change which records are valid:

- Python's ``$`` also matches before a final newline, so ``"not-masked\\n"``
  matched ``^(not-masked|...)$``. In ECMA-262 (no ``m`` flag) ``$`` matches only
  at the end of the string; here it is read as ``\\Z``.
- Python's ``date`` cannot represent year 0, so ``0000-01-01`` was refused,
  although RFC 3339 ``date-fullyear`` is any four digits (0000 is a leap year in
  the proleptic Gregorian calendar, as ISO 8601 counts it).

This is a bounded adapter, not a complete ECMA-262 regular-expression engine.
Empty classes (``[]`` and ``[^]``) are translated with their ECMA meaning;
unsupported contract patterns fail closed with an explicit evaluation error. Remaining
differences include shorthand sets: Python's ``\\d``/``\\w`` are Unicode-aware
where ECMA uses ASCII without flags, and ``\\s`` is Unicode-aware in both but
uses different whitespace sets. Assessment report/rubric validation still uses
stock validators in ``assess/data.py`` and ``assess/render.py``; assessment
identifier/synonym patterns still use plain Python ``re``.
"""

import re
from functools import lru_cache
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker, validators
from jsonschema.exceptions import ValidationError

FULL_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def is_full_date(value):
    """Whether ``value`` is an RFC 3339 ``full-date`` (years 0000-9999)."""
    match = FULL_DATE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return False
    year, month, day = (int(part) for part in match.groups())
    if not 1 <= month <= 12:
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 1 <= day <= _DAYS[month - 1] + (month == 2 and leap)


@lru_cache(maxsize=None)
def ecma_pattern(pattern):
    """``pattern`` with every ``$`` anchor (outside a character class, not
    escaped) written ``\\Z``, so it matches only at the end of the string."""
    # ECMA ClassContents may be empty: [] matches nothing and [^] matches any
    # character. Python instead treats a first ] as a literal class member.
    # https://tc39.es/ecma262/2026/multipage/text-processing.html#sec-patterns
    out = []
    escaped = in_class = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if not escaped and not in_class:
            if pattern.startswith("[]", index):
                out.append("(?!)")
                index += 2
                continue
            if pattern.startswith("[^]", index):
                out.append(r"[\s\S]")
                index += 3
                continue
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "$":
            out.append(r"\Z")
            index += 1
            continue
        out.append(char)
        index += 1
    return re.compile("".join(out))


def _pattern(validator, pattern, instance, schema):
    if not validator.is_type(instance, "string"):
        return
    try:
        matched = ecma_pattern(pattern).search(instance)
    except re.error as error:
        yield ValidationError(
            f"cannot evaluate contract pattern {pattern!r} with the bounded "
            f"Python translation: {error}"
        )
        return
    if not matched:
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


FORMAT_CHECKER = FormatChecker()
FORMAT_CHECKER.checks("date")(
    lambda value: not isinstance(value, str) or is_full_date(value)
)

Validator = validators.extend(Draft202012Validator, {"pattern": _pattern})


def validator(schema):
    """A validator for ``schema`` with the corrected ``pattern`` and ``date``."""
    return Validator(schema, format_checker=FORMAT_CHECKER)


# A draft contract may state ``format: uri`` (the FHGM record contract does, so a
# link field cannot hide a ``javascript:`` or ``data:`` scheme behind the type
# check). The stock checker only enforces ``uri`` when the optional ``rfc3987``
# dependency happens to be installed, and the released header contracts never ask
# for it, so ``FORMAT_CHECKER`` above leaves it alone: released validation is
# untouched. The draft lane needs a verdict that does not depend on what else is
# installed, so it gets ``uri`` from the same source the owning FHGM checker uses
# when the dependency is present, and from this bounded rule when it is not: no
# whitespace or control/format character, no malformed percent escape, no
# excluded character, and a scheme that starts with a letter.
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*")
_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_EXCLUDED = '<>"{}|\\^`'


def _is_uri_local(value):
    """``value`` as a URI, by the bounded rule above (never a replacement guess)."""
    if not isinstance(value, str):
        return True  # the type keyword decides, not the format keyword
    if (
        re.search(r"\s", value)
        or _ESCAPE.search(value)
        or any(
            ord(char) < 0x21 or ord(char) > 0x7E or char in _EXCLUDED for char in value
        )
    ):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return _SCHEME.fullmatch(parts.scheme) is not None


_STOCK_FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER
if "uri" in _STOCK_FORMAT_CHECKER.checkers:

    def _is_uri(value):
        # The installed library's own URI rule, exactly as the owning FHGM
        # checker uses it when the optional dependency is present.
        return _STOCK_FORMAT_CHECKER.conforms(value, "uri")

else:
    _is_uri = _is_uri_local

#: The corrected ``pattern``/``date`` rules plus ``format: uri``, for draft bytes.
#: A separate checker, never a mutation of ``FORMAT_CHECKER``: the released
#: contracts must keep seeing exactly the formats they stated before.
DRAFT_FORMAT_CHECKER = FormatChecker()
DRAFT_FORMAT_CHECKER.checks("date")(
    lambda value: not isinstance(value, str) or is_full_date(value)
)
DRAFT_FORMAT_CHECKER.checks("uri")(_is_uri)


def draft_validator(schema):
    """A validator for *draft* contract bytes: :func:`validator` plus ``uri``.

    Separate from :func:`validator` on purpose. The released header contracts do
    not state ``format: uri``, and giving them it would change which existing
    records are valid; a draft contract that does state it must be enforced
    deterministically whatever optional packages the host happens to have. The
    released path keeps calling :func:`validator`."""
    return Validator(schema, format_checker=DRAFT_FORMAT_CHECKER)
