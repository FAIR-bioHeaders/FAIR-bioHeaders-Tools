# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Extension fields: top-level keys that start with ``x-``.

FAIR-bioHeaders-Specification docs/FORMAT.md R15 (FHR 2.1, FHP and FHGFF3 1.1):
a top-level key matching :data:`PATTERN` may hold any value the standard does not
define. The bundled schemas decide which keys are valid; this module only finds
them. JSON-LD, the schema.org export and HTML microdata carry no extension fields
(rules J9 and M5): writers leave them out and readers reject them.
"""

import re

PREFIX = "x-"
# The schema's pattern, used with ``fullmatch`` (no line feed can slip past "$").
# Validation uses the schemas themselves; this copy only chooses messages.
PATTERN = re.compile(r"x-[A-Za-z0-9][A-Za-z0-9_.-]*")


def is_extension_key(key):
    """Whether ``key`` is a well-formed extension key (R15)."""
    return isinstance(key, str) and PATTERN.fullmatch(key) is not None


def quoted(keys):
    """Keys for a message, as Python literals so control characters are escaped."""
    return ", ".join(repr(key) for key in keys)


FORMATS = {
    "jsonld": "JSON-LD",
    "export": "the schema.org export",
    "microdata": "HTML microdata",
}


def extension_keys(metadata):
    """The top-level keys of ``metadata`` that start with ``x-``, in order.

    Every such key, valid or not, is an extension key here: a writer leaves it out
    and a JSON-LD or microdata reader rejects it."""
    if not isinstance(metadata, dict):
        return []
    return [key for key in metadata if isinstance(key, str) and key.startswith(PREFIX)]


def without_extensions(metadata):
    """A shallow copy of ``metadata`` without its extension fields."""
    left_out = set(extension_keys(metadata))
    return {key: value for key, value in metadata.items() if key not in left_out}


def left_out_message(metadata, form):
    """The writer warning for the extension fields ``form`` leaves out, or None."""
    keys = extension_keys(metadata)
    if not keys:
        return None
    # Writers run after validation, so every key here matches the pattern.
    return f"extension fields are not written to {FORMATS[form]}: {', '.join(keys)}"


def reject(metadata, form, rule):
    """Raise ``ValueError`` if ``metadata`` read from ``form`` has extension keys."""
    keys = extension_keys(metadata)
    if keys:
        raise ValueError(
            f"{FORMATS[form]} carries no extension fields "
            f"(FAIR-bioHeaders-Specification {rule}): {quoted(keys)}"
        )
