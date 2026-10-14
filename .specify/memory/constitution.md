# FHR File Converter Constitution

> **Status: draft.** Proposed for Spec Kit planning gates. It restates existing
> AGENTS.md, README, and FAIR-bioHeaders-Specification docs/FORMAT.md practice and adds no
> authority. David and Adam must approve it before it is treated as ratified.

## Core Principles

### I. The specification is the contract

The converter implements FAIR-bioHeaders-Specification; it does not define it. The bundled
`bioheaders/fhr_schema.json` and the `fhr/fhr_schema.json` and root
`fhr_schema.json` copies stay byte-identical with the specification's `fhr.json`. Behaviour the specification does not define is
proposed there first, not invented here.

### II. Exact bytes and one reading

Checksums are SHA-512/256 over exact FASTA/GFA bytes except the single root-level
checksum line, in padded base64. Never normalize line endings, wrapping, comments,
or encoding. Every command must identify metadata from the same byte lines that
are hashed, so validate, convert, strip, and combine agree on what a file says.
`strip(combine(x))` preserves the payload byte for byte.

### III. Fail closed on untrusted input

Inputs may be downloaded from anywhere. Ambiguous input (duplicate keys, YAML
anchors or aliases, line-break characters inside header lines, malformed
microdata) is rejected with a concise error and a nonzero exit, never silently
reinterpreted. Resource use must stay bounded for inputs of any size.

### IV. Preserve metadata and typed values

Round trips across JSON, YAML, HTML microdata, FASTA, and GFA keep values and
types. Absent optional fields are omitted, not emitted as null. HTML output is
escaped. Machine-readable microdata values take precedence over display text.

### V. Compatible, small, tested

Keep runtime dependencies small. Keyword constructor fields, the `bioheaders`
command, the eight `fhr-*` CLI entry points, and the deprecated `fhr` import name
are public API; breaking changes need a migration note and a
version bump. Every behaviour change ships with regression tests.

## Verification gates

Every plan names the checks it must pass, on Python 3.9 and 3.13:

```bash
poetry install
poetry run pytest
poetry run ruff check .
poetry run isort . --check-only
poetry run black . --check
poetry build
python -m build compat/fhr
```

Sequence-tool changes also test metadata and sequence tampering, CRLF, ordinary
comments, combine/strip, and the installed wheel from outside the checkout.

## Decision boundaries

David and Adam hold schema authority. Publishing packages, archiving DOIs, and
deployment are separate maintainer actions; a spec, plan, or task list never
authorizes them. Security-relevant findings follow the specification's
SECURITY.md before any public issue or PR.

## Governance

This constitution guides Spec Kit specify/plan/tasks gates. Amendments follow the
normal review process with a changelog note. On conflict, the specification and
maintainer decisions win.

**Version**: 0.1.0 (draft) | **Ratified**: pending maintainer approval | **Last Amended**: 2026-10-08
