# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Map header keys to concepts and match value forms (synonyms.json).

Key normalisation applies only to *matching*; evidence keeps the raw line. A
key may map to several concepts: the concepts whose value forms the value
matches win; otherwise the concepts without forms; otherwise the first
candidate, whose value is then reported malformed (identifier forms) or
irregular (other forms).
"""

import re
from collections import namedtuple

from . import data

# Item: one (concept, value) statement found on a header line.
#   status: "ok", "malformed" (fails a required identifier form) or "irregular"
#   (a non-standard form, credited, reported as format-irregularity).
#   extra: details such as the derivedFrom entry or the contig name.
Item = namedtuple("Item", "concept value forms status key extra")

# Forms whose failure makes a value malformed (B §3 rule 4).
STRICT_FORMS = {"insdc-assembly-accession", "fhr-checksum", "seqcol-digest", "md5"}
# Identifier forms looked for in free text (research R-05 edge case).
SEARCHED = {
    "insdc-assembly-accession": r"(?:NCBI_Assembly:)?GC[AF]_\d{9}\.\d+",
    "doi": r"(?:doi:|https://doi\.org/)10\.\d{4,9}/[^\s,;)]+",
    "orcid": r"https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]",
    "taxonomy-iri": r"https://identifiers\.org/taxonomy:\d+",
}
# Concepts whose value may contain an identifier that is credited (research R-06:
# "accession inside #!annotation-source/annotationSource").
EMBEDDED = {"source-data": ("insdc-assembly-accession", "assembly-accession")}
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def normalise(key):
    """Case-fold; fold -, _, space and camelCase; strip a trailing colon."""
    if key is None:
        return None
    key = key.strip()
    if key.endswith(":"):
        key = key[:-1].rstrip()
    parts = []
    for part in key.split("."):
        part = _CAMEL.sub("-", part).casefold()
        parts.append(re.sub(r"[-_ ]+", "-", part).strip("-"))
    return ".".join(parts)


def search(pattern):
    return re.compile(r"(?<![A-Za-z0-9_])(" + pattern + r")(?![A-Za-z0-9_])")


class Synonyms:
    def __init__(self, loaded=None):
        loaded = loaded or data.load()
        table = loaded.synonyms
        self.forms = table["forms"]
        self.concepts = table["concepts"]
        self.patterns = {
            name: re.compile(form["pattern"]) for name, form in self.forms.items()
        }
        self.index = {}
        for concept, definition in self.concepts.items():
            for convention, keys in definition["keys"].items():
                for key in keys:
                    bucket = self.index.setdefault(convention, {})
                    bucket.setdefault(normalise(key), []).append(concept)
        spdx = loaded.reference["spdx-licenses"]["entries"]
        self.spdx = {entry["id"] for entry in spdx}
        self.schemes = {
            entry["prefix"].casefold(): entry
            for entry in loaded.reference["id-schemes"]["entries"]
        }
        self.searched = {name: search(pattern) for name, pattern in SEARCHED.items()}

    # Value forms -----------------------------------------------------------

    def _scheme_match(self, value):
        """True if ``value`` is in a persistent scheme of the id-schemes table."""
        value = value.strip()
        doi = re.match(r"(?:https://doi\.org/|doi:)(10\..+)$", value, re.IGNORECASE)
        if doi:
            return self._in_scheme("doi", doi.group(1))
        value = re.sub(r"^https?://identifiers\.org/", "", value)
        value = re.sub(r"^NCBI_Assembly:", "", value)
        accession = re.match(r"GC([AF])_", value)
        if accession:
            prefix = "insdc.gca" if accession.group(1) == "A" else "refseq.gcf"
            return self._in_scheme(prefix, value)
        if ":" not in value:
            return False
        prefix, local = value.split(":", 1)
        entry = self.schemes.get(prefix.casefold())
        if entry is None:
            return False
        embedded = entry["pattern"].lstrip("^").upper().startswith(prefix.upper() + ":")
        return self._in_scheme(prefix.casefold(), value if embedded else local)

    def _in_scheme(self, prefix, local):
        entry = self.schemes.get(prefix)
        return bool(
            entry and entry["persistent"] and re.match(entry["pattern"], local.strip())
        )

    def form_matches(self, form, value):
        """True if ``value`` has value form ``form`` (reference tables included)."""
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not self.patterns[form].fullmatch(text):
            return False
        table = self.forms[form].get("reference_table")
        if table == "spdx-licenses":
            return text in self.spdx
        if table == "id-schemes":
            return self._scheme_match(text)
        return True

    def matching_forms(self, concept, value):
        """The forms of ``concept`` that ``value`` matches."""
        return [
            form
            for form in self.concepts[concept].get("forms", [])
            if self.form_matches(form, value)
        ]

    # Key resolution ----------------------------------------------------------

    def candidates(self, convention, key):
        return list(self.index.get(convention, {}).get(normalise(key), []))

    def resolve(self, convention, key, value, extra=None):
        """Return the Items for ``key: value`` written in ``convention``."""
        candidates = self.candidates(convention, key)
        if not candidates or value is None or value == "":
            return []
        if not isinstance(value, str):
            return [Item(c, value, [], "ok", key, extra or {}) for c in candidates]
        matched = [(c, self.matching_forms(c, value)) for c in candidates]
        matched = [(c, forms) for c, forms in matched if forms]
        if matched:
            items = [Item(c, value, f, "ok", key, extra or {}) for c, f in matched]
        else:
            formless = [c for c in candidates if not self.concepts[c].get("forms")]
            if formless:
                items = [Item(c, value, [], "ok", key, extra or {}) for c in formless]
            else:
                concept = candidates[0]
                forms = self.concepts[concept]["forms"]
                strict = all(form in STRICT_FORMS for form in forms)
                status = "malformed" if strict else "ok"
                if not strict and any(f in ("iso-date", "vcf-date") for f in forms):
                    status = "irregular"
                items = [Item(concept, value, [], status, key, extra or {})]
        for item in list(items):
            embedded = EMBEDDED.get(item.concept)
            if embedded:
                form, concept = embedded
                for found in search(SEARCHED[form]).finditer(value):
                    items.append(
                        Item(concept, found.group(1), [form], "ok", key, extra or {})
                    )
        return items

    def identifiers_in(self, text):
        """Identifier-shaped substrings of free ``text``: [(form, value)]."""
        found = []
        for name, pattern in self.searched.items():
            found += [(name, match.group(1)) for match in pattern.finditer(text)]
        return found

    def link_kind(self, concept):
        return self.concepts[concept].get("link_kind")

    def relationship(self, concept):
        return self.concepts[concept].get("relationship")


_CACHE: list[Synonyms] = []


def load():
    if not _CACHE:
        _CACHE.append(Synonyms())
    return _CACHE[0]
