# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Render suggestions in the file's own convention (research R-11, FR-003).

Templates come from rubric.json. For an indicator over several elements
(discovery, reuse, provenance), the template of the first missing element is
used. A file without a native header convention gets a FAIR-bioHeaders line;
where a native convention has no template, the FAIR-bioHeaders key is written in
that convention. Values come only from the file, the related file, or the file
name (labelled "confirm before use"); everything else is a <placeholder>.
"""

import re

from .. import SCHEMA
from .model import Suggestion
from .synonyms import load as load_synonyms

NATIVE = {
    "gff3": ("gff3-pragma", "gff3-directive"),
    "vcf": ("vcf-meta",),
    "gaf": ("gaf",),
}
# Element (condition concept) -> indicator whose templates suggest adding it.
ELEMENT_TEMPLATES = {
    "data-identifier": "RDA-F1-01D",
    "version": "RDA-F2-01M",
    "taxon": "RDA-I2-01M",
    "creator": "RDA-I3-03M",
    "date-created": "RDA-R1.2-01M",
    "licence": "RDA-R1.1-01M",
    "source-data": "RDA-I3-04M",
}
MULTI_ELEMENT = ("RDA-F2-01M", "RDA-R1-01M", "RDA-R1.2-01M")
VALUE_FALLBACK = "<NCBI taxon id, e.g. 6239>"
RELATED_FALLBACK = {
    "name": "<sequence name, e.g. I>",
    "length": "<sequence length, e.g. 15072434>",
    "md5": "<MD5 of the sequence, e.g. 6aef897c3d6ff0c78aff06ac189178dd>",
    "checksum": "<FHR checksum of the parent file, e.g. 3an6Cqo2eomqlt75XIpyWXDtls3GhA8EOpjK97S+ykc=>",
    "seqcol_id": "<SeqCol digest of the parent file, e.g. 3aH2VIDvPa1rVLSwmJp4pE6lF2Hkt2Az>",
    "accession": "<versioned assembly accession, e.g. GCF_000002985.6>",
}
PLACEHOLDER = re.compile(r"<[^<>\s]*\s[^<>]*>")
ACCESSION = re.compile(r"GC[AF]_\d{9}\.\d+")
DRAFT_NOTE = (
    " FAIR-bioHeaders headers for transcript (FHT) and protein (FHP) FASTA are draft"
    " specifications, not released;"
    " for a genome, bioheaders combine writes a complete FHR header."
)


def _native(line, convention):
    """Write a ``#~key: value`` template line in a native convention."""
    match = re.match(r"^#~([^:\s]+):\s*(.*)$", line)
    if not match:
        return line
    key, value = match.groups()
    if convention == "gaf":
        return f"!{key}: {value}"
    if convention == "vcf-meta":
        return f"##{key}={value}"
    return f"#!{key} {value}"


def _template(indicator, outcome, indicators):
    if indicator["id"] in MULTI_ELEMENT:
        satisfied = outcome.get("satisfied", set())
        for condition in indicator["conditions"]:
            source = ELEMENT_TEMPLATES.get(condition["concept"])
            if condition["id"] not in satisfied and source:
                return indicators[source]
    return indicator


def _taxon_id(context):
    for evidence in context.evidence:
        if evidence.scope != "file":
            continue
        for item in evidence.items:
            if item.concept == "taxon" and isinstance(item.value, str):
                found = re.search(r"(?:taxonomy:|[?&]id=)(\d+)", item.value)
                if found:
                    return found.group(1)
    return None


def suggest(indicator, outcome, context, indicators):
    """Return the Suggestion for a partially or not evidenced indicator."""
    source = _template(indicator, outcome, indicators)
    templates = source["suggestions"]
    format_name = context.format
    convention = next(
        (c for c in NATIVE.get(format_name, ()) if c in templates), "fair-bioheaders"
    )
    text, line = templates[convention]["text"], templates[convention]["line"]
    if convention == "fair-bioheaders" and format_name in ("vcf", "gaf"):
        convention = NATIVE[format_name][0]
        line = _native(line, convention)
    elif convention == "fair-bioheaders" and format_name == "gff3":
        # Use a #! pragma only where the key means something in GFF3 pragmas.
        key = re.match(r"^#~([^:\s]+):\s*([^\[{]|$)", line)
        if key and load_synonyms().candidates("gff3-pragma", key.group(1)):
            convention, line = "gff3-pragma", _native(line, "gff3-pragma")
    elif convention == "fair-bioheaders" and format_name == "fasta":
        line = ";~" + line[2:]
        text += DRAFT_NOTE
    value_source = "placeholder"
    if "{value}" in line:
        taxon = _taxon_id(context)
        if taxon:
            line, value_source = line.replace("{value}", taxon), "file"
        else:
            line = line.replace("{value}", VALUE_FALLBACK)
    related = context.related_values or {}
    for field, fallback in RELATED_FALLBACK.items():
        token = "{related." + field + "}"
        if token in line:
            if related.get(field) is not None:
                line = line.replace(token, str(related[field]))
                if value_source == "placeholder":
                    value_source = "related-file"
            else:
                line = line.replace(token, fallback)
    if (
        indicator.get("check") == "derived-link"
        and convention == "gff3-pragma"
        and "genome-build-accession" in line
        and not any(link.kind == "accession" for link in context.links)
    ):
        found = ACCESSION.search(context.file_name or "")
        if found:
            line = PLACEHOLDER.sub(found.group(0), line)
            value_source = "file-name"
            text += (
                f" The accession {found.group(0)} is from the file name; confirm"
                " before use."
            )
    root = re.match(r"^[;#]~['\"]?([^:\s'\"]+)['\"]?:", line)
    if root and convention == "fair-bioheaders":
        present = {
            e.key
            for e in context.evidence
            if e.convention == "fair-bioheaders" and e.key
        }
        if root.group(1) in present:
            text = f"Replace the existing {root.group(1)} entry. " + text
    if (
        context.conformance is not None
        and context.conformance.result == "valid"
        and convention == "fair-bioheaders"
    ):
        if root and root.group(1) not in SCHEMA["properties"]:
            text += (
                f" FHR schemaVersion 1 has no {root.group(1)} field, so this line makes"
                " the header invalid until the schema supports it."
            )
    return Suggestion(text, line, convention, value_source, source["guideline_item"])
