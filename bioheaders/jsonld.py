# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""JSON-LD for FHR and FHP metadata: the writers and canonical readers (provisional API).

The FHR JSON-LD form is the FHR record with its own keys, an embedded ``@context``
and ``@type`` on the record and its nested nodes (FAIR-bioHeaders-Specification
docs/JSONLD.md, feature 011). The bundled ``fhr.context.jsonld`` is a
byte-identical copy of FAIR-bioHeaders-Specification ``jsonld/fhr.context.jsonld``.
FHP canonical JSON-LD uses the bundled reviewed ``fhp.context.jsonld``
(FHP-Specification docs/FHP.md); FHP has no schema.org export profile.

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
FHP_CONTEXT = json.loads(
    files(__package__).joinpath("fhp.context.jsonld").read_text(encoding="utf-8")
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
# The FHP context's canonical raw-main URL is FHP-Specification. The shared
# publication repository becomes a supported URL when the coordinating PR
# publishes the file there. The pre-rename name never hosted it, so it is not a
# known FHP context URL.
FHP_RAW_MAIN_CONTEXT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FHP-Specification/main/"
    "jsonld/fhp.context.jsonld"
)
FHP_SHARED_RAW_MAIN_CONTEXT_URL = (
    "https://raw.githubusercontent.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/main/"
    "jsonld/fhp.context.jsonld"
)
FHP_KNOWN_CONTEXT_URLS = (
    FHP_RAW_MAIN_CONTEXT_URL,
    FHP_SHARED_RAW_MAIN_CONTEXT_URL,
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
# Link schemes (FAIR-bioHeaders-Specification docs/FORMAT.md R14). A URI-shaped
# value: an ASCII scheme at the very start, a colon, then no whitespace (Unicode
# whitespace included), no control character and no bidirectional formatting
# character (RFC 3987 section 4.1). Schemes compare case-insensitively.
URI_FORM = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*):"
    r"([^\s\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]+)"
)
# The schemes a writer emits as an IRI; any other value of an IRI-valued field is
# refused by the JSON-LD writers and reported as a warning by validators (R14).
LINK_SCHEMES = ("http", "https", "ftp", "urn", "doi", "info")
# Of those, the URL schemes, which need "//" and a host. Text is promoted to an
# IRI (documentation as subjectOf, a licence as an IRI) only when it is a URL with
# one of them (rules J7 and X5).
URL_SCHEMES = ("http", "https", "ftp")
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


NAME_TYPES = {"Personal": "Person", "Organizational": "Organization"}


def author_type(item):
    """``Person`` or ``Organization`` from a v0.4 ``nameType``; otherwise
    ``Person`` for an ORCID ``uri``, ``Organization`` for ROR, else ``Agent``."""
    name_type = item.get("nameType")
    kind = NAME_TYPES.get(name_type) if isinstance(name_type, str) else None
    if kind is not None:
        return kind
    uri = item.get("uri")
    if isinstance(uri, str) and ORCID_URI.match(uri):
        return "Person"
    if isinstance(uri, str) and ROR_URI.fullmatch(uri):
        return "Organization"
    return "Agent"


def is_absolute_url(value):
    return isinstance(value, str) and ABSOLUTE_URL.fullmatch(value) is not None


def uri_scheme(value):
    """The lower-case scheme of a URI-shaped string (``URI_FORM``), else ``None``."""
    if not isinstance(value, str):
        return None
    match = URI_FORM.fullmatch(value)
    return match.group(1).lower() if match else None


def is_link(value, schemes=LINK_SCHEMES):
    """Whether ``value`` is a URI with one of ``schemes`` (R14); the URL schemes
    ``http``, ``https`` and ``ftp`` also need ``//`` and a host."""
    scheme = uri_scheme(value)
    if scheme not in schemes:
        return False
    rest = value[len(scheme) + 1 :]
    if scheme in URL_SCHEMES:
        return rest.startswith("//") and len(rest) > 2 and rest[2] != "/"
    return True


def is_web_url(value):
    """Whether ``value`` is an absolute ``http``, ``https`` or ``ftp`` URL, the
    only text that the writers promote to an IRI (rules J7 and X5)."""
    return is_link(value, URL_SCHEMES)


def _scope_body(term):
    """The term definitions of a property-scoped context (``[null, {...}]``)."""
    scoped = term.get("@context") if isinstance(term, dict) else None
    if isinstance(scoped, list):
        scoped = next(
            (item for item in reversed(scoped) if isinstance(item, dict)), None
        )
    return scoped if isinstance(scoped, dict) else None


def _is_iri_term(term):
    return term == "@id" or isinstance(term, dict) and term.get("@type") == "@id"


def iri_values(record, body):
    """``(path, value)`` for every value that ``body`` (a context's term
    definitions) makes an IRI: ``@type: @id`` terms and ``@id`` aliases, in the
    record and its nested objects."""
    found = []
    for key, value in record.items():
        term = body.get(key)
        items = value if isinstance(value, list) else [value]
        paths = (
            [f"{key}[{index}]" for index in range(len(items))]
            if isinstance(value, list)
            else [key]
        )
        if _is_iri_term(term):
            found += [(path, item) for path, item in zip(paths, items)]
            continue
        child = _scope_body(term)
        if child is None:
            continue
        for path, item in zip(paths, items):
            if isinstance(item, dict):
                found += [
                    (f"{path}.{sub}", subvalue)
                    for sub, subvalue in iri_values(item, child)
                ]
    return found


def link_problem(value):
    """Why ``value`` may not be written as an IRI (R14), or ``None``."""
    if is_link(value):
        return None
    scheme = uri_scheme(value)
    if scheme is None:
        return "is not an absolute URI"
    if scheme in URL_SCHEMES:
        return f"is not an absolute {scheme} URL"
    return f"uses the URI scheme {scheme!r}"


def check_links(record, body, what="JSON-LD"):
    """Refuse a record whose IRI-valued fields use a scheme other than
    ``LINK_SCHEMES`` (FAIR-bioHeaders-Specification docs/FORMAT.md R14)."""
    for path, value in iri_values(record, body):
        if not isinstance(value, str):
            continue
        problem = link_problem(value)
        if problem is not None:
            raise ValueError(
                f"{what}: {path} {problem}; it is not written as a link "
                f"(allowed schemes: {', '.join(LINK_SCHEMES)}; "
                "FAIR-bioHeaders-Specification docs/FORMAT.md R14)"
            )


# Characters escaped in JSON-LD text inside an HTML script element (rule J8).
# In JSON they occur only inside strings, where the escapes mean the same.
SCRIPT_ESCAPES = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    " ": "\\u2028",
    " ": "\\u2029",
}
_SCRIPT_UNSAFE = re.compile("[<>&  ]")


def script_text(text):
    """JSON text made safe for ``<script type="application/ld+json">`` (rule J8).

    ``<``, ``>`` and ``&`` (and U+2028/U+2029) are written as ``\\u`` escapes, so
    no value can end the element, open a comment or reach the HTML parser's
    script-data-escaped states. The result parses to the same JSON value.
    """
    return _SCRIPT_UNSAFE.sub(lambda match: SCRIPT_ESCAPES[match.group()], text)


def script_element(document):
    """A ``<script type="application/ld+json">`` element holding ``document``."""
    text = json.dumps(document, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{script_text(text)}\n</script>\n'


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
        if key in export and not (
            is_absolute_url(export[key]) and is_link(export[key], URL_SCHEMES)
        ):
            raise ValueError(
                f"export context: {key} must be an absolute http, https or ftp URL"
            )
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
    check_links(data, CONTEXT["@context"])
    if export is not None:
        export = check_export(export)
    document = {"@context": CONTEXT["@context"], "@type": "Dataset"}
    if export and "id" in export:
        document["@id"] = export["id"]
    for key, value in data.items():
        if key == "documentation" and is_web_url(value):
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
    # nameType (FHR-Specification v0.4) is written as the author node's @type.
    "metadataAuthor": ("name", "uri", "nameType"),
    "assemblyAuthor": ("name", "uri", "nameType"),
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
        if is_web_url(documentation):
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
        assembly["license"] = _export_iri(value) if is_web_url(value) else value
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
    check_links(data, CONTEXT["@context"], "JSON-LD export")
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


def same_json(left, right):
    """Equality of parsed JSON values that keeps booleans, numbers and strings
    apart (``true`` is not ``1``), as "equal as parsed JSON" means in J1 and J3."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            same_json(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(same_json, left, right))
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def is_fhr_context(value):
    """A known FHR context URL, or an embedded copy of a bundled FHR context."""
    if isinstance(value, str):
        return value in KNOWN_CONTEXT_URLS
    return isinstance(value, dict) and any(
        same_json(value, bundled["@context"]) for _, bundled in BUNDLED_CONTEXTS
    )


def is_canonical(document):
    """Rule J1: a bundled context, embedded or by a known URL, and no keyword
    except ``@type`` on objects and an optional root ``@id``."""
    if not isinstance(document, dict) or "@context" not in document:
        return False
    if not is_fhr_context(document["@context"]):
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
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        # PyLD raises these on some malformed contexts, e.g. a null @language.
        raise ValueError(f"invalid JSON-LD: {type(error).__name__}: {error}") from None
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


CONTEXT_REFUSAL = (
    "JSON-LD: {detail}; only the FHR context may be used, by a known URL or as an "
    "embedded copy, alone and only at the top level (FAIR-bioHeaders-Specification "
    "docs/JSONLD.md J3). A different context could give an FHR key another "
    "meaning; write the record in the canonical form (J1)"
)


def _nested_context(value, path):
    """The path of the first ``@context`` key below the top level, or of any
    ``@nest`` key (which moves properties into their parent), else ``None``."""
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}" if path else key
            if key in ("@context", "@nest"):
                return here
            found = _nested_context(item, here)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _nested_context(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def check_contexts(document):
    """Rule J3: a document read by expansion may use only the FHR context.

    Each top-level object (the document, or each item of a top-level array) may
    have a ``@context`` that is a known FHR context URL, an embedded copy of the
    FHR context, or an array of exactly one of those. No other ``@context`` may
    appear anywhere, and neither may ``@nest``. A document without a context
    (expanded form) is allowed.
    Raises ``ValueError``.
    """
    tops = document if isinstance(document, list) else [document]
    for index, top in enumerate(tops):
        if not isinstance(top, dict):
            continue
        where = f"[{index}]" if isinstance(document, list) else ""
        if "@context" in top:
            value = top["@context"]
            single = value[0] if isinstance(value, list) and len(value) == 1 else value
            if isinstance(single, str) and not is_fhr_context(single):
                raise ValueError(f"JSON-LD context is not available offline: {single}")
            if not is_fhr_context(single):
                kind = (
                    "an array of contexts"
                    if isinstance(value, list)
                    else "an embedded context that is not the FHR context"
                )
                raise ValueError(
                    CONTEXT_REFUSAL.format(
                        detail=f"{where or 'the'} @context is {kind}"
                    )
                )
        rest = {key: item for key, item in top.items() if key != "@context"}
        nested = _nested_context(rest, where)
        if nested is not None and nested.endswith("@nest"):
            raise ValueError(
                f"JSON-LD: {nested} is not allowed: @nest gives its properties to the "
                "enclosing object, out of sight of a JSON reader "
                "(FAIR-bioHeaders-Specification docs/JSONLD.md J3)"
            )
        if nested is not None:
            raise ValueError(
                CONTEXT_REFUSAL.format(
                    detail=f"{nested} gives a context below the top level"
                )
            )


def read_general(document, *, ignore_unknown_terms=False, warn=None):
    """Read JSON-LD in any form by expansion (rules J3 to J5); see ``from_jsonld``."""
    warn = _print_warning if warn is None else warn
    check_contexts(document)
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


# FHP canonical JSON-LD (FHP-Specification docs/FHP.md, issue #4). The writer
# and reader are the reference implementation from the specification's
# scripts/make_jsonld.py. FHP has canonical JSON-LD only: the one-way schema.org
# export profile is an FHR feature and has no FHP terms.

# Writer @type for each inlined FHP object (the scoped contexts define the same).
FHP_NODE_TYPES = {
    "taxon": "Taxon",
    "accessionID": "PropertyValue",
    "sequenceStats": "SequenceStats",
    "completeness": "Completeness",
}
# Writer @type for each item of an FHP array of objects.
FHP_LIST_TYPES = {
    "source": "Source",
    "derivedFrom": "DerivedFrom",
    "predictionSoftware": "SoftwareApplication",
}
# Root keys that are not FHP fields (the writer never emits a root @id; a reader
# sets one aside rather than silently keeping it).
FHP_RESERVED_ROOT = ("@id",)
FHP_NOT_CANONICAL = (
    "this JSON-LD is not in the canonical FHP form (FHP-Specification docs/FHP.md); "
    "the root @context must be the embedded FHP context or a known FHP context URL"
)
FHP_BAD_VERSION = (
    "this JSON-LD declares a JSON-LD @version other than 1.1; the FHP context is 1.1"
)
# Terms of the FHP context whose objects are inlined; used for unknown-term warnings.
FHP_SCOPE_KEYS = (
    "taxon",
    "metadataAuthor",
    "accessionID",
    "derivedFrom",
    "source",
    "predictionSoftware",
    "sequenceStats",
    "completeness",
)


def load_fhp_context():
    """The bundled FHP context document."""
    return copy.deepcopy(FHP_CONTEXT)


def fhp_is_document(document):
    """Whether ``document`` carries the embedded or a known FHP context."""
    if not isinstance(document, dict) or "@context" not in document:
        return False
    value = document["@context"]
    if isinstance(value, str):
        return value in FHP_KNOWN_CONTEXT_URLS
    return same_json(value, FHP_CONTEXT["@context"])


def fhp_looks_like_record(document):
    """Whether a document carries an FHP-only root field (for reader dispatch)."""
    return isinstance(document, dict) and (
        "proteome" in document or "sourceType" in document
    )


def fhp_is_canonical(document, context=None):
    """Rule J1 for FHP: the bundled FHP context, and no keyword but @type."""
    if not isinstance(document, dict) or "@context" not in document:
        return False
    bundled = (load_fhp_context() if context is None else context)["@context"]
    value = document["@context"]
    if not (
        same_json(value, bundled)
        or isinstance(value, str)
        and value in FHP_KNOWN_CONTEXT_URLS
    ):
        return False
    if "@id" in document and not isinstance(document["@id"], str):
        return False
    return _plain(document, True)


def _fhp_typed_node(kind, value):
    """A typed FHP object, recursively typing its children in the original order."""
    node = {"@type": kind}
    for key, item in value.items():
        node[key] = _fhp_typed(key, item)
    return node


def _fhp_typed(key, value):
    """Type an FHP field and, recursively, every inlined object below it."""
    if key in FHP_NODE_TYPES and isinstance(value, dict):
        return _fhp_typed_node(FHP_NODE_TYPES[key], value)
    if key in AUTHOR_KEYS and isinstance(value, list):
        return [
            (
                _fhp_typed_node(author_type(item), item)
                if isinstance(item, dict)
                else copy.deepcopy(item)
            )
            for item in value
        ]
    if key in FHP_LIST_TYPES and isinstance(value, list):
        return [
            (
                _fhp_typed_node(FHP_LIST_TYPES[key], item)
                if isinstance(item, dict)
                else copy.deepcopy(item)
            )
            for item in value
        ]
    return copy.deepcopy(value)


def fhp_to_jsonld(record, context=None):
    """The canonical JSON-LD document for an FHP record (loss-preserving)."""
    _check_reserved(record, "")
    for key in (URL_TERM, *FHP_RESERVED_ROOT):
        if key in record:
            raise ValueError(
                f"JSON-LD: the root key {key} is reserved for JSON-LD output"
            )
    context = load_fhp_context() if context is None else context
    check_links(record, context["@context"])
    document = {"@context": context["@context"], "@type": "Dataset"}
    for key, value in record.items():
        if key == "documentation" and is_web_url(value):
            document[URL_TERM] = value
        else:
            document[key] = _fhp_typed(key, value)
    return document


def fhp_jsonld_text(record, context=None):
    """The canonical FHP JSON-LD as formatted text."""
    return (
        json.dumps(fhp_to_jsonld(record, context), ensure_ascii=False, indent=2) + "\n"
    )


# The classes the canonical FHP form expects on the record and its objects. A
# reader checks them instead of silently stripping any @type.
FHP_EXPECTED_TYPES = {
    "record": {"Dataset"},
    "taxon": {"Taxon"},
    "accessionID": {"PropertyValue"},
    "sequenceStats": {"SequenceStats"},
    "completeness": {"Completeness"},
}
FHP_EXPECTED_ITEM_TYPES = {
    "metadataAuthor": {"Person", "Organization", "Agent"},
    "source": {"Source"},
    "derivedFrom": {"DerivedFrom"},
    "predictionSoftware": {"SoftwareApplication"},
}


def _fhp_type_names(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("JSON-LD @type must be a string or an array of strings")


def _fhp_context_maps():
    """Prefixes and term IRIs defined by the bundled FHP context.

    A class must be named by its own term, its compact IRI or its expanded IRI.
    Matching only a local name would let ``fhr:Dataset`` stand in for
    ``sdo:Dataset`` or ``sdo:Source`` for ``fhr:Source``, and would accept an
    undefined prefix such as ``schema:``.
    """
    context = FHP_CONTEXT["@context"]
    prefixes = {
        key: value
        for key, value in context.items()
        if not key.startswith("@")
        and isinstance(value, str)
        and value.startswith(("http://", "https://"))
    }
    terms = {}
    for key, value in context.items():
        if key.startswith("@") or not isinstance(value, str):
            continue
        if value.startswith(("http://", "https://")) or ":" not in value:
            continue
        prefix, rest = value.split(":", 1)
        if prefix in prefixes:
            terms[key] = prefixes[prefix] + rest
    return prefixes, terms


_FHP_PREFIXES, _FHP_TERM_IRIS = _fhp_context_maps()


def _fhp_type_iri(value):
    """Resolve a ``@type`` value to its IRI, or ``None`` if it is not defined."""
    if not isinstance(value, str):
        return None
    if value in _FHP_TERM_IRIS:
        return _FHP_TERM_IRIS[value]
    if value.startswith(("http://", "https://")):
        return value
    if ":" in value:
        prefix, rest = value.split(":", 1)
        namespace = _FHP_PREFIXES.get(prefix)
        if namespace is not None:
            return namespace + rest
    return None


def _fhp_type_iris(values):
    return {_fhp_type_iri(value) for value in values}


def _check_expected_type(node, allowed, path):
    if not isinstance(node, dict):
        raise ValueError(f"JSON-LD: {path} must be an object")
    if "@type" not in node:
        raise ValueError(f"JSON-LD: {path} has no @type; expected {sorted(allowed)}")
    values = _fhp_type_names(node["@type"])
    expected = {_FHP_TERM_IRIS[term] for term in allowed}
    if not _fhp_type_iris(values) & expected:
        raise ValueError(
            f"JSON-LD: {path} has @type {sorted(values)}; "
            f"expected one of {sorted(allowed)}"
        )


def _check_author_type(item, path):
    """An author @type must equal the type the writer derives from nameType/uri."""
    values = _fhp_type_names(item["@type"])
    expected = _FHP_TERM_IRIS[author_type(item)]
    if _fhp_type_iris(values) != {expected}:
        detail = item.get("nameType")
        detail = f'nameType "{detail}"' if detail is not None else "its nameType/uri"
        raise ValueError(
            f"JSON-LD: {path} has @type {sorted(values)}; {detail} derives "
            f"{author_type(item)}"
        )


def fhp_validate_types(document):
    """Reject a canonical document with a wrong or missing nested @type."""
    _check_expected_type(document, FHP_EXPECTED_TYPES["record"], "the record")
    for key, allowed in FHP_EXPECTED_TYPES.items():
        if key == "record" or key not in document:
            continue
        _check_expected_type(document[key], allowed, key)
    for key, allowed in FHP_EXPECTED_ITEM_TYPES.items():
        items = document.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"JSON-LD: {key} must be an array")
        for index, item in enumerate(items):
            _check_expected_type(item, allowed, f"{key}[{index}]")
            if key in AUTHOR_KEYS:
                _check_author_type(item, f"{key}[{index}]")
            if key == "derivedFrom" and "accessionID" in item:
                _check_expected_type(
                    item["accessionID"],
                    {"PropertyValue"},
                    f"{key}[{index}].accessionID",
                )


def fhp_canonical_record(document, warn=None, context=None):
    """Read a canonical FHP JSON-LD document back to FHP metadata.

    Rejects an unknown context, an unsupported JSON-LD @version, a document that
    is not canonical, and a wrong or missing nested @type. Nothing is fetched: a
    known context URL is served from the bundled file. The FHP objects are
    closed, so an unknown key is left for validation against fhp.json rather
    than dropped.
    """
    if not isinstance(document, dict) or "@context" not in document:
        raise ValueError(FHP_NOT_CANONICAL)
    value = document["@context"]
    if isinstance(value, dict) and "@version" in value and value["@version"] != 1.1:
        raise ValueError(FHP_BAD_VERSION)
    if isinstance(value, str) and value not in FHP_KNOWN_CONTEXT_URLS:
        raise ValueError(f"unknown FHP JSON-LD context (nothing is fetched): {value}")
    if not fhp_is_canonical(document, context):
        raise ValueError(FHP_NOT_CANONICAL)
    fhp_validate_types(document)
    record = {}
    for key, item in document.items():
        if key in ("@context", "@type"):
            continue
        if key in FHP_RESERVED_ROOT:
            if warn is not None:
                warn(f"JSON-LD: {key} is not an FHP field; it was not kept")
            continue
        if key == URL_TERM:
            if "documentation" in document:
                raise ValueError("JSON-LD gives both documentation and subjectOf")
            if not isinstance(item, str):
                raise ValueError("JSON-LD subjectOf must be a string")
            key = "documentation"
        record[key] = _without_types(item)
    return record


def _fhp_scope_terms():
    root = FHP_CONTEXT["@context"]
    terms = {}
    for key in FHP_SCOPE_KEYS:
        body = root[key]["@context"][1]
        terms[key] = {
            term
            for term, value in body.items()
            if isinstance(value, dict) or value == "@id"
        }
    return terms


def fhp_unmapped_keys(record):
    """Paths of nested FHP keys that the context does not define."""
    terms = _fhp_scope_terms()
    found = []
    for key, value in record.items():
        if key not in terms:
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
            found += [f"{path}.{name}" for name in item if name not in terms[key]]
    return found
