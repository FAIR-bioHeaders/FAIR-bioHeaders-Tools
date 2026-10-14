# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""JSON-LD for FHR metadata: the writer and the canonical reader (provisional API).

The JSON-LD form is the FHR record with its own keys, an embedded ``@context``
and ``@type`` on the record and its nested nodes (FAIR-bioHeaders-Specification
docs/JSONLD.md, feature 011). The bundled ``fhr.context.jsonld`` is a
byte-identical copy of FAIR-bioHeaders-Specification ``jsonld/fhr.context.jsonld``.

Writing and canonical reading (rule J1) need only the standard library. Reading
JSON-LD in other forms (rules J3 to J6) needs the ``jsonld`` extra (PyLD, Python
3.10 or later), which is imported only for those documents. Nothing ever uses
the network: contexts are served only from the bundled copies.
"""

import copy
import json
import re
import sys
from importlib.resources import files

CONTEXT = json.loads(
    files(__package__).joinpath("fhr.context.jsonld").read_text(encoding="utf-8")
)
RAW_MAIN_CONTEXT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHR-Specification/main/"
    "jsonld/fhr.context.jsonld"
)
# (version, context document) for every bundled context. No FAIR-bioHeaders-Specification
# release contains the context yet, so the only one is that of main; release
# versions are added, with their raw tag and w3id URLs, once they exist.
BUNDLED_CONTEXTS = (("main", CONTEXT),)


# The specification repository's names: FAIR-bioHeaders-Specification since
# #108, and FHR-Specification before; URLs under the old name stay supported.
SPECIFICATION_REPOSITORIES = ("FHR-Specification", "FAIR-bioHeaders-Specification")


def _context_urls(version):
    ref = "main" if version == "main" else version
    raw = tuple(
        f"https://raw.githubusercontent.com/FAIR-bioHeaders/{repository}/"
        f"{ref}/jsonld/fhr.context.jsonld"
        for repository in SPECIFICATION_REPOSITORIES
    )
    if version == "main":
        return raw
    return raw + (
        f"https://w3id.org/fair-bioheaders/fhr/{version}/jsonld/fhr.context.jsonld",
    )


# Context URLs that a canonical document may reference; nothing is fetched.
KNOWN_CONTEXT_URLS = tuple(
    url for version, _ in BUNDLED_CONTEXTS for url in _context_urls(version)
)
# The Bioschemas Dataset release whose minimum properties are checked; Dataset
# 1.1 was still a draft on 2026-10-10 (https://bioschemas.org/profiles/).
BIOSCHEMAS_DATASET_PROFILE = "https://bioschemas.org/profiles/Dataset/1.0-RELEASE"
# Its minimum properties beside @context, @type and dct:conformsTo, with the key
# that carries each one in a written document.
BIOSCHEMAS_MINIMUM = (
    ("@id", "@id"),
    ("description", "documentation"),
    ("identifier", "identifier"),
    ("keywords", "keywords"),
    ("license", "reuseConditions"),
    ("name", "genome"),
    ("url", "url"),
)
NODE_TYPES = {
    "taxon": "Taxon",
    "accessionID": "PropertyValue",
    "vitalStats": "VitalStats",
}
AUTHOR_KEYS = ("metadataAuthor", "assemblyAuthor")
# The fhr.json orcidUri pattern (a prefix match) and the ROR identifier form.
ORCID_URI = re.compile(r"https://orcid\.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]")
ROR_URI = re.compile(r"https://ror\.org/0[0-9a-z]{6}[0-9]{2}")
# An absolute URL: a scheme, "://", and no whitespace.
ABSOLUTE_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")
URL_TERM = "subjectOf"
# assemblyProtocolHowTo is used only by the schema.org export profile (rule X8).
EXPORT_KEYS = ("id", "url", "keywords", "assemblyProtocolHowTo")
# Root keys of a written document that carry export metadata, not FHR fields.
EXPORT_OUTPUT = ("@id", "keywords", "url", "conformsTo")
NEEDS_EXTRA = (
    "reading this JSON-LD form needs the jsonld extra: "
    'pip install "fair-bioheaders[jsonld]"'
)


def _print_warning(message):
    print(f"FHR: {message}", file=sys.stderr)


def author_type(item):
    """``Person`` for an ORCID ``uri``, ``Organization`` for ROR, else ``Agent``."""
    uri = item.get("uri")
    if isinstance(uri, str) and ORCID_URI.match(uri):
        return "Person"
    if isinstance(uri, str) and ROR_URI.fullmatch(uri):
        return "Organization"
    return "Agent"


def is_absolute_url(value):
    return isinstance(value, str) and ABSOLUTE_URL.fullmatch(value) is not None


def check_export(export):
    """Validate an export context: optional ``id``, ``url``, ``keywords`` and
    ``assemblyProtocolHowTo``."""
    if not isinstance(export, dict):
        raise ValueError(
            "export context must be a mapping with id, url and/or keywords"
        )
    unknown = sorted(str(key) for key in set(export) - set(EXPORT_KEYS))
    if unknown:
        raise ValueError(
            f"export context: unknown key {', '.join(unknown)}; "
            "allowed: id, url, keywords, assemblyProtocolHowTo"
        )
    if "assemblyProtocolHowTo" in export and not isinstance(
        export["assemblyProtocolHowTo"], bool
    ):
        raise ValueError("export context: assemblyProtocolHowTo must be true or false")
    for key in ("id", "url"):
        if key in export and not is_absolute_url(export[key]):
            raise ValueError(f"export context: {key} must be an absolute URL")
    keywords = export.get("keywords", ["x"])
    if not (
        isinstance(keywords, list)
        and keywords
        and all(isinstance(word, str) and word.strip() for word in keywords)
    ):
        raise ValueError(
            "export context: keywords must be a non-empty list of non-empty strings"
        )
    return export


def _present(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def bioschemas_missing(document):
    """The Bioschemas Dataset minimum properties that a written document lacks."""
    return [name for name, key in BIOSCHEMAS_MINIMUM if not _present(document.get(key))]


def _check_reserved(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}" if path else key
            if key.startswith("@"):
                raise ValueError(
                    f"JSON-LD: {here} starts with @, which JSON-LD reserves; "
                    "it cannot be written"
                )
            _check_reserved(item, here)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_reserved(item, f"{path}[{index}]")


def _typed_items(value, kind):
    return [
        (
            {"@type": kind(item), **copy.deepcopy(item)}
            if isinstance(item, dict)
            else copy.deepcopy(item)
        )
        for item in value
    ]


def _typed(key, value):
    if key in NODE_TYPES and isinstance(value, dict):
        return {"@type": NODE_TYPES[key], **copy.deepcopy(value)}
    if key in AUTHOR_KEYS and isinstance(value, list):
        return _typed_items(value, author_type)
    if key == "assemblySoftware" and isinstance(value, list):
        return _typed_items(value, lambda item: "SoftwareApplication")
    return copy.deepcopy(value)


def to_jsonld(data, export=None):
    """Return the JSON-LD document for FHR metadata ``data`` (rule J7).

    ``export`` is an optional export context (``id``, ``url``, ``keywords``);
    ``conformsTo`` the Bioschemas Dataset profile is added only when every
    minimum property of that profile is present.
    """
    _check_reserved(data, "")
    for key in (URL_TERM, *EXPORT_OUTPUT):
        if key in data:
            raise ValueError(
                f"JSON-LD: the root key {key} is reserved for JSON-LD output"
            )
    if export is not None:
        export = check_export(export)
    document = {"@context": CONTEXT["@context"], "@type": "Dataset"}
    if export and "id" in export:
        document["@id"] = export["id"]
    for key, value in data.items():
        if key == "documentation" and is_absolute_url(value):
            document[URL_TERM] = value
        else:
            document[key] = _typed(key, value)
    if export:
        for key in ("keywords", "url"):
            if key in export:
                document[key] = copy.deepcopy(export[key])
        if not bioschemas_missing(document):
            document["conformsTo"] = BIOSCHEMAS_DATASET_PROFILE
    return document


# The schema.org export profile (FAIR-bioHeaders-Specification docs/SCHEMAORG-EXPORT.md,
# feature 013): a one-way projection, distinct from the canonical form above.

EXPORT_CONTEXT = {
    "@vocab": "http://schema.org/",
    "fhr": "https://w3id.org/fair-bioheaders/terms#",
    "dct": "http://purl.org/dc/terms/",
}
ASSEMBLY_ID = "_:assembly"
METADATA_RECORD_ID = "_:metadata-record"
ACTIVITY_ID = "_:assembly-activity"
_UO = "http://purl.obolibrary.org/obo/"
UNITS = {
    "bp": (_UO + "UO_0000244", "base pair"),
    "count": (_UO + "UO_0000189", "count unit"),
    "percent": (_UO + "UO_0000187", "percent"),
}
# Each numeric statistic and its unit (rule X4); the scaffold ones are v0.4 fields.
STATISTIC_UNITS = {
    "N50": "bp",
    "N90": "bp",
    "L50": "count",
    "L90": "count",
    "totalBasePairs": "bp",
    "numberContigs": "count",
    "numberScaffolds": "count",
    "gcContent": "percent",
    "scaffoldN50": "bp",
    "scaffoldN90": "bp",
    "scaffoldL50": "count",
    "scaffoldL90": "count",
}
SEQCOL_SCHEME = "GA4GH refget sequence collection"
DOI_REGISTRY = "https://registry.identifiers.org/registry/doi"
STRICT_DOI = re.compile(r"10\.[0-9]{4,9}/\S+")
EXPORT_REFUSAL = (
    "this is a one-way schema.org export (FAIR-bioHeaders-Specification "
    "docs/SCHEMAORG-EXPORT.md); it cannot be read back as FHR metadata; use the "
    "canonical JSON-LD form"
)
# Keys of FHR's open nested objects that the export writes (rule X9).
EXPORT_NESTED_KEYS = {
    "taxon": ("name", "uri"),
    "metadataAuthor": ("name", "uri"),
    "assemblyAuthor": ("name", "uri"),
    "accessionID": ("name", "url"),
    "assemblySoftware": ("name", "version", "uri", "commandLineOption"),
    "vitalStats": tuple(STATISTIC_UNITS) + ("readTechnology",),
}


def _export_iri(value):
    return {"@id": value}


def _export_author(item):
    if not isinstance(item, dict):
        return copy.deepcopy(item)
    kind = author_type(item)
    node = {}
    if isinstance(item.get("uri"), str):
        node["@id"] = item["uri"]
    node["@type"] = "fhr:Agent" if kind == "Agent" else kind
    if "name" in item:
        node["name"] = item["name"]
    return node


def _export_software(item):
    if not isinstance(item, dict):
        return {"@type": "SoftwareApplication", "name": item}
    node = {"@type": "SoftwareApplication"}
    for key, target in (("name", "name"), ("version", "softwareVersion")):
        if key in item:
            node[target] = item[key]
    if "uri" in item:
        node["url"] = _export_iri(item["uri"])
    if "commandLineOption" in item:
        node["fhr:commandLineOption"] = {
            "@list": copy.deepcopy(item["commandLineOption"])
        }
    return node


def export_unmapped_keys(data):
    """Paths of nested keys that the export leaves out (rule X9)."""
    found = []
    for key, allowed in EXPORT_NESTED_KEYS.items():
        value = data.get(key)
        if isinstance(value, dict):
            items = [(key, value)]
        elif isinstance(value, list):
            items = [
                (f"{key}[{index}]", item)
                for index, item in enumerate(value)
                if isinstance(item, dict)
            ]
        else:
            items = []
        for path, item in items:
            found += [f"{path}.{name}" for name in item if name not in allowed]
    return found


def _export_assembly(data, export, assembly_id):
    assembly = {"@id": assembly_id, "@type": "Dataset"}
    for key, target in (
        ("genome", "name"),
        ("genomeSynonym", "alternateName"),
        ("version", "version"),
        ("dateCreated", "dateCreated"),
    ):
        if key in data:
            assembly[target] = copy.deepcopy(data[key])
    taxon = data.get("taxon")
    if isinstance(taxon, dict):
        node = {}
        if "uri" in taxon:
            node["@id"] = taxon["uri"]
        node["@type"] = "Taxon"
        if "name" in taxon:
            node["name"] = taxon["name"]
        assembly["about"] = node
    if "assemblyAuthor" in data:
        assembly["creator"] = [_export_author(item) for item in data["assemblyAuthor"]]
    identifiers = list(copy.deepcopy(data.get("identifier", [])))
    accession = data.get("accessionID")
    if isinstance(accession, dict):
        node = {"@type": "PropertyValue"}
        if "name" in accession:
            node["name"] = accession["name"]
        if "url" in accession:
            node["url"] = _export_iri(accession["url"])
        identifiers.append(node)
    if "seqcol_id" in data:
        identifiers.append(
            {
                "@type": "PropertyValue",
                "propertyID": SEQCOL_SCHEME,
                "value": data["seqcol_id"],
            }
        )
    if identifiers:
        assembly["identifier"] = identifiers
    subject_of = []
    documentation = data.get("documentation")
    if documentation is not None:
        if is_absolute_url(documentation):
            subject_of.append(_export_iri(documentation))
        else:
            assembly["description"] = documentation
    article = data.get("scholarlyArticle")
    if isinstance(article, str) and STRICT_DOI.fullmatch(article):
        subject_of.append(
            {
                "@id": f"https://doi.org/{article}",
                "@type": "ScholarlyArticle",
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": DOI_REGISTRY,
                    "value": article,
                },
            }
        )
    elif article is not None:
        assembly["citation"] = article
    if subject_of:
        assembly["subjectOf"] = subject_of
    if "reuseConditions" in data:
        value = data["reuseConditions"]
        assembly["license"] = _export_iri(value) if is_absolute_url(value) else value
    if "funding" in data:
        assembly["funding"] = {"@type": "Grant", "description": data["funding"]}
    if "keywords" in export:
        assembly["keywords"] = copy.deepcopy(export["keywords"])
    if "url" in export:
        assembly["url"] = _export_iri(export["url"])
    for key in ("voucherSpecimen", "instrument", "masking"):
        if key in data:
            assembly[f"fhr:{key}"] = copy.deepcopy(data[key])
    if "relatedLink" in data:
        assembly["fhr:relatedLink"] = [
            _export_iri(link) for link in data["relatedLink"]
        ]
    return assembly


def to_export(data, export=None):
    """Return the one-way schema.org export graph of FHR metadata ``data``.

    ``export`` is an optional export context (``id``, ``url``, ``keywords`` and
    ``assemblyProtocolHowTo``). The output follows FAIR-bioHeaders-Specification
    docs/SCHEMAORG-EXPORT.md (rules X1 to X9) byte for byte when written with
    ``export_text``.
    """
    _check_reserved(data, "")
    export = check_export(export) if export is not None else {}
    assembly_id = export.get("id", ASSEMBLY_ID)
    assembly = _export_assembly(data, export, assembly_id)
    how_to = export.get("assemblyProtocolHowTo") is True and "assemblyProtocol" in data
    if "assemblyProtocol" in data and not how_to:
        assembly["fhr:assemblyProtocol"] = _export_iri(data["assemblyProtocol"])
    stats = data.get("vitalStats")
    stats = stats if isinstance(stats, dict) else {}
    if "readTechnology" in stats:
        assembly["fhr:vitalStats"] = {
            "@type": "fhr:VitalStats",
            "fhr:readTechnology": stats["readTechnology"],
        }
    if "checksum" in data:
        assembly["fhr:checksum"] = data["checksum"]
    complete = ("id" in export) and all(
        key in assembly
        for key in ("description", "identifier", "keywords", "license", "name", "url")
    )
    if complete:
        assembly["dct:conformsTo"] = _export_iri(BIOSCHEMAS_DATASET_PROFILE)

    metadata = {
        "@id": METADATA_RECORD_ID,
        "@type": "CreativeWork",
        "about": _export_iri(assembly_id),
    }
    if "metadataAuthor" in data:
        metadata["creator"] = [_export_author(item) for item in data["metadataAuthor"]]
    if "schema" in data:
        metadata["schemaVersion"] = _export_iri(data["schema"])
    if "schemaVersion" in data:
        metadata["fhr:schemaVersion"] = data["schemaVersion"]
    graph = [assembly, metadata]

    activity = {
        "@id": ACTIVITY_ID,
        "@type": "CreateAction",
        "result": _export_iri(assembly_id),
    }
    software = data.get("assemblySoftware")
    if isinstance(software, str):  # the legacy form: one software name
        activity["instrument"] = [_export_software(software)]
    elif isinstance(software, list):
        activity["instrument"] = [_export_software(item) for item in software]
    if how_to:
        activity["actionProcess"] = {"@id": data["assemblyProtocol"], "@type": "HowTo"}
    if len(activity) > 3:
        graph.append(activity)

    for key, value in stats.items():
        if key not in STATISTIC_UNITS or isinstance(value, bool):
            continue
        unit, label = UNITS[STATISTIC_UNITS[key]]
        graph.append(
            {
                "@id": f"_:observation-{key}",
                "@type": "Observation",
                "name": key,
                "observationAbout": _export_iri(assembly_id),
                "measuredProperty": _export_iri(f"fhr:{key}"),
                "value": value,
                "unitCode": _export_iri(unit),
                "unitText": label,
            }
        )
    return {"@context": copy.deepcopy(EXPORT_CONTEXT), "@graph": graph}


def export_text(data, export=None):
    """The export as JSON text, formatted like FAIR-bioHeaders-Specification's fixtures."""
    return json.dumps(to_export(data, export), ensure_ascii=False, indent=2) + "\n"


def is_export(document):
    """True for a document written with the export profile (refused by readers)."""
    return isinstance(document, dict) and document.get("@context") == EXPORT_CONTEXT


def _scope_terms():
    root = CONTEXT["@context"]
    terms = {}
    for key in ("taxon", *AUTHOR_KEYS, "accessionID", "vitalStats"):
        body = root[key]["@context"][1]
        terms[key] = {
            term
            for term, value in body.items()
            if isinstance(value, dict) or value == "@id"
        }
    return terms


SCOPE_TERMS = _scope_terms()


def unmapped_keys(data):
    """Paths of nested keys that the context does not define, such as
    ``taxon.checksum`` or ``assemblyAuthor[0].affiliation``."""
    found = []
    for key, value in data.items():
        if key not in SCOPE_TERMS:
            continue
        if isinstance(value, dict):
            items = [(key, value)]
        elif isinstance(value, list):
            items = [
                (f"{key}[{index}]", item)
                for index, item in enumerate(value)
                if isinstance(item, dict)
            ]
        else:
            items = []
        for path, item in items:
            found += [f"{path}.{name}" for name in item if name not in SCOPE_TERMS[key]]
    return found


def _plain(node, root):
    """True if ``node`` has no JSON-LD keyword except @type (and root @context/@id)."""
    if isinstance(node, list):
        return all(_plain(item, False) for item in node)
    if not isinstance(node, dict):
        return True
    for key, item in node.items():
        if key == "@type":
            if not (
                isinstance(item, str)
                or isinstance(item, list)
                and all(isinstance(kind, str) for kind in item)
            ):
                return False
        elif key.startswith("@"):
            if not (root and key in ("@context", "@id")):
                return False
        elif not _plain(item, False):
            return False
    return True


def is_canonical(document):
    """Rule J1: a bundled context, embedded or by a known URL, and no keyword
    except ``@type`` on objects and an optional root ``@id``."""
    if not isinstance(document, dict) or "@context" not in document:
        return False
    value = document["@context"]
    if isinstance(value, str):
        if value not in KNOWN_CONTEXT_URLS:
            return False
    elif not any(value == bundled["@context"] for _, bundled in BUNDLED_CONTEXTS):
        return False
    if "@id" in document and not isinstance(document["@id"], str):
        return False
    return _plain(document, True)


def _without_types(value):
    if isinstance(value, dict):
        return {k: _without_types(item) for k, item in value.items() if k != "@type"}
    if isinstance(value, list):
        return [_without_types(item) for item in value]
    return value


def from_jsonld(document, *, ignore_unknown_terms=False, warn=None):
    """Return the FHR metadata of a JSON-LD document.

    A canonical document (rule J1) has its ``@context`` and every ``@type`` set
    aside; a root ``subjectOf`` is the ``documentation`` value, and the export
    terms ``@id``, ``keywords``, ``url`` and ``conformsTo`` are set aside with a
    warning passed to ``warn`` (default: print to stderr). Any other document is
    read by JSON-LD expansion (rules J3 to J5, ``read_general``), which needs
    the ``jsonld`` extra; ``ignore_unknown_terms`` turns its unknown terms into
    warnings. Raises ``ValueError`` for anything else.
    """
    warn = _print_warning if warn is None else warn
    if not isinstance(document, (dict, list)):
        raise ValueError("JSON-LD metadata must be a JSON object or array")
    if is_export(document):
        raise ValueError(EXPORT_REFUSAL)
    if not is_canonical(document):
        return read_general(
            document, ignore_unknown_terms=ignore_unknown_terms, warn=warn
        )
    record = {}
    for key, value in document.items():
        if key in ("@context", "@type"):
            continue
        if key in EXPORT_OUTPUT:
            warn(
                f"JSON-LD: {key} is export metadata, not an FHR field; it was not kept"
            )
            continue
        if key == URL_TERM:
            if "documentation" in document:
                raise ValueError("JSON-LD gives both documentation and subjectOf")
            if not isinstance(value, str):
                raise ValueError("JSON-LD subjectOf must be a string")
            key = "documentation"
        record[key] = _without_types(value)
    return record


# The general path (rules J3 to J5): JSON-LD 1.1 expansion with bundled contexts
# only, then the reverse of the bundled context, scope by scope.

XSD_DATE = "http://www.w3.org/2001/XMLSchema#date"
# Root terms of the context that are not FHR fields: export metadata, read as
# unknown terms. subjectOf is read as documentation.
EXPORT_TERMS = ("keywords", "url", "conformsTo")
RECORD = "the record"


def _iri(curie, body):
    prefix, colon, rest = curie.partition(":")
    namespace = body.get(prefix) or CONTEXT["@context"].get(prefix)
    if colon and isinstance(namespace, str):
        return namespace + rest
    return curie


def _reverse_scope(body, root=False):
    """``(IRI -> (key, coercion, container, child scope), key that @id fills)``."""
    reverse, id_key = {}, None
    for key, term in body.items():
        if term == "@id":
            id_key = key
            continue
        if not isinstance(term, dict) or root and key in EXPORT_TERMS:
            continue
        child = None
        if "@context" in term:
            child = _reverse_scope(term["@context"][1])
            coercion = "node"
        elif term.get("@type") == "@id":
            coercion = "iri"
        elif term.get("@type") == "xsd:date":
            coercion = "date"
        else:
            coercion = "literal"
        target = "documentation" if key == URL_TERM else key
        reverse[_iri(term["@id"], body)] = (
            target,
            coercion,
            term.get("@container"),
            child,
        )
    return reverse, id_key


# The reverse map derived once from the bundled context (data-model section 4).
REVERSE_MAP = _reverse_scope(CONTEXT["@context"], root=True)
# Output key order: the context lists keys in fhr.json property order.
KEY_ORDER = {
    key: index for index, key in enumerate(CONTEXT["@context"]) if key != URL_TERM
}


def _document_loader(refused):
    from pyld import jsonld as pyld

    def load(url, options=None):
        for version, context in BUNDLED_CONTEXTS:
            if url in _context_urls(version):
                return {
                    "contextUrl": None,
                    "documentUrl": url,
                    "document": copy.deepcopy(context),
                }
        refused.append(url)
        raise pyld.JsonLdError(
            f"JSON-LD context is not available offline: {url}",
            "jsonld.LoadDocumentError",
            {"url": url},
            code="loading document failed",
        )

    return load


def expand(document):
    """Expand ``document`` with the bundled contexts only (rule J3).

    Returns ``(expanded, dropped)``; ``dropped`` lists the terms that expansion
    dropped because they have no IRI. Raises ``ValueError``.
    """
    try:
        from pyld import jsonld as pyld
    except ImportError:
        raise ValueError(NEEDS_EXTRA) from None
    refused, dropped = [], []

    def on_dropped(term):
        if term is not None and term not in dropped:
            dropped.append(term)

    try:
        expanded = pyld.expand(
            copy.deepcopy(document),
            {"documentLoader": _document_loader(refused)},
            on_property_dropped=on_dropped,
        )
    except pyld.JsonLdError as error:
        if refused:
            raise ValueError(
                f"JSON-LD context is not available offline: {refused[0]}"
            ) from None
        raise ValueError(
            f"invalid JSON-LD: {error.code or error.type}: {error.args[0]}"
        ) from None
    return expanded, dropped


class _Reader:
    def __init__(self):
        self.unknown = []

    def node(self, node, scope, where):
        reverse, id_key = scope
        found = {}
        for name, values in node.items():
            if name == "@type":
                continue
            if name == "@id" and id_key is not None:
                found[id_key] = node["@id"]
                continue
            if name not in reverse:
                reason = "root-id" if name == "@id" and where == RECORD else "unmapped"
                self.unknown.append((name, where, reason))
                continue
            key, coercion, container, child = reverse[name]
            if key in found:
                raise ValueError("JSON-LD gives both documentation and subjectOf")
            field = key if where == RECORD else f"{where}.{key}"
            items = []
            for value in values:
                if isinstance(value, dict) and "@list" in value:
                    items.extend(value["@list"])
                else:
                    items.append(value)
            converted = [
                self.value(item, key, field, coercion, child, where, index)
                for index, item in enumerate(items)
            ]
            if key == "assemblySoftware" and [type(v) for v in converted] == [str]:
                found[key] = converted[0]
            elif container is not None:
                found[key] = converted
            elif len(converted) != 1:
                raise ValueError(
                    f"JSON-LD gives {len(converted)} values for single-valued "
                    f"field {field}"
                )
            else:
                found[key] = converted[0]
        if where == RECORD:
            order = KEY_ORDER
        else:
            order = {key: index for index, key in enumerate(_scope_keys(scope))}
        return dict(sorted(found.items(), key=lambda item: order.get(item[0], 1 << 30)))

    def value(self, item, key, field, coercion, child, where, index):
        if not isinstance(item, dict):
            raise ValueError(f"JSON-LD gives an unsupported value for field {field}")
        if "@value" in item:
            if "@language" in item:
                raise ValueError(
                    f"JSON-LD gives a language-tagged value for field {field}, "
                    "which FHR cannot keep"
                )
            kind = item.get("@type")
            if kind is not None and not (coercion == "date" and kind == XSD_DATE):
                allowed = (
                    "only xsd:date or no datatype" if coercion == "date" else "none"
                )
                raise ValueError(
                    f"JSON-LD gives field {field} the datatype {kind}; "
                    f"allowed: {allowed}"
                )
            value = item["@value"]
            if coercion == "node" and not (
                key == "assemblySoftware" and isinstance(value, str)
            ):
                raise ValueError(
                    f"JSON-LD gives a value for field {field}, which takes an object"
                )
            if coercion in ("iri", "date") and not isinstance(value, str):
                raise ValueError(f"JSON-LD gives a non-string value for field {field}")
            return value
        if coercion == "iri" and set(item) == {"@id"}:
            return item["@id"]
        if coercion != "node":
            raise ValueError(
                f"JSON-LD gives a node for field {field}, which takes a value"
            )
        if set(item) == {"@id"}:
            raise ValueError(
                f"JSON-LD gives field {field} only as a reference to {item['@id']} "
                "(flattened form), which is not supported"
            )
        path = key if where == RECORD else f"{where}.{key}"
        if key in AUTHOR_KEYS or key == "assemblySoftware":
            path = f"{path}[{index}]"
        return self.node(item, child, path)


def _scope_keys(scope):
    reverse, id_key = scope
    keys = [entry[0] for entry in reverse.values()]
    return keys + [id_key] if id_key else keys


def _unknown_text(term, where, reason):
    if reason == "dropped":
        return f"{term} (dropped by JSON-LD expansion: it has no IRI)"
    return f"{term} (at {where})"


def read_general(document, *, ignore_unknown_terms=False, warn=None):
    """Read JSON-LD in any form by expansion (rules J3 to J5); see ``from_jsonld``."""
    warn = _print_warning if warn is None else warn
    expanded, dropped = expand(document)
    nodes = expanded
    if len(nodes) == 1 and set(nodes[0]) == {"@graph"}:
        nodes = nodes[0]["@graph"]
    if len(nodes) != 1:
        raise ValueError(
            f"JSON-LD must describe exactly one FHR record (found {len(nodes)} nodes)"
        )
    reader = _Reader()
    record = reader.node(nodes[0], REVERSE_MAP, RECORD)
    unknown = [(term, None, "dropped") for term in dropped] + reader.unknown
    if unknown:
        texts = [_unknown_text(*entry) for entry in unknown]
        if not ignore_unknown_terms:
            raise ValueError("JSON-LD term not in the FHR mapping: " + ", ".join(texts))
        for text in texts:
            warn(f"warning: JSON-LD term not in the FHR mapping: {text}")
    return record
