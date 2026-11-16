# Qualified DCMI exporter provenance and checks

This implements the adopted mapping-v1 assembly scope under shared specification
issue #56. It keeps the existing profile token `0.1.0-draft.1` and context schema
identity, accepts only complete fixed FHR v0.4.0 / schemaVersion `"2.0"` metadata,
and leaves the official label and package publication to their existing gates.
See the [CLI/API and preservation contract](../README.md#qualified-dcmi-assembly-export).

## Reviewed upstream inputs

The reviewed foundation revision is
[`c1512e8c3569920206322bc76d9414f4503bcd55`](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/tree/c1512e8c3569920206322bc76d9414f4503bcd55).
This names immutable reviewed bytes, not a claim that the proposal PR or this
exporter has shipped. The final default-branch reconciliation is recorded in the
implementation PR before consumers cite it as merged.

- `bioheaders/mappings/assembly-export-context.schema.json` copies the adopted
  `mappings/proposals/assembly-export-context.schema.json` without semantic changes.
- `bioheaders/mappings/loss-notes.json` copies each inventory entry's `path` and
  `loss_or_limitation` from `mappings/proposals/assembly-dcmi.yml`; no target fields
  or profile versions are added.
- `tests/fixtures/dcmi/` rich and minimal inputs and Turtle expectations copy
  `tests/fixtures/mapping-proposal/`. Reports and the explicitly changed
  identity-conflict fixture are local tool-output examples, labelled in their README.
- Source validation uses the existing immutable packaged
  `bioheaders/schemas/fhr-2.0.json` (v0.4.0), never network/raw-main selection.
  Local JSON Schema references are resolved inside this fixed schema.

| Packaged input | SHA-256 |
| --- | --- |
| `bioheaders/schemas/fhr-2.0.json` | `168a60467e3651dfdfe9855747f38257d5889bfcce6ec8661d9a378762a362dd` |
| `bioheaders/mappings/assembly-export-context.schema.json` | `47b963a2df24d559de9592f49337589c7b4164e4e09b0982443785998e66f35d` |
| `bioheaders/mappings/loss-notes.json` | `612fd9950a9b735c966d163701031a57a5f73c6d9961bff7731e3e781f0a8364` |

## Evidence and omissions

`tests/dcmi_test.py` compares parsed Turtle with independent rich/minimal curated
RDF graphs, verifies repeated output bytes and complete input preservation, and
uses deliberately wrong subject/creator/date expectations as negative controls.
It checks conflict and invalid-input bundles, source scope, strict JSON, optional
omissions, literal escaping, creator classification and no-overwrite behavior.
The installed CLI test clears `PYTHONPATH`, runs outside the checkout, and verifies
that the imported `dcmi.py` is the matching noneditable site-packages artifact;
packaged context/loss data are compared independently as well.

RDFLib is a **development-only** independent parser, not an exporter dependency.
The locked [RDFLib 7.6.0 metadata](https://pypi.org/project/rdflib/7.6.0/) declares
Python >=3.8.1, compatible with this project's Python 3.9 floor. Python CI checks
3.9 and 3.13; both ordinary and release-test jobs install a noneditable copy
before pytest. Existing shared conformance, canonical JSON-LD, schema.org and MIxS
checks continue unchanged. The generated capability matrix lists the command
separately and does not count Turtle as a whole-header serialization.

No source sequence is present, so checksum verification is unperformed. There
are no network, DOI-agency submission, reverse-conversion or dataset pilot steps.
The generated example reports explicitly retain unprojected fields and context,
including year/DOI assertions for which v1 defines conflict checks but no graph
projection. Keep both original inputs with every graph.

Article DOI names are encoded as resolver URL paths. Reserved characters such as
`?`, `#`, `%` and `>` stay part of that name, rather than becoming query/fragment
syntax or invalid RDF IRIs. The original DOI string remains unchanged in the
preservation copy; no DOI is resolved or registered.
