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
