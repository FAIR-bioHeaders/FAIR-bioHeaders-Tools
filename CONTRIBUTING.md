# Contributing

Start with an issue describing the use case or failure and a small reproducible
example. Submit a focused branch/PR with behavior, compatibility implications,
and relevant validation. Link related work in [FAIR-bioHeaders-Specification](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification)
and the release tracker when a change spans repositories. Do not include private
genome data, credentials, or unrelated formatting in fixtures.

## Setup and checks

See README for Python requirements and environment setup. From this checkout:

```bash
poetry install
poetry run pytest
poetry run ruff check .
poetry run isort . --check-only
poetry run black . --check
```

For changes to FASTA/GFA processing, also run the opt-in large-file memory test,
which writes about 1 GB of temporary files: `FHR_MEMORY_TEST=1 poetry run pytest
-s -k memory` (set `FHR_MEMORY_TEST_MB` to change the 300 MB input size).

Changes to metadata must coordinate `fhr.json`, the LinkML model, the converter
schema copies (`bioheaders/fhr_schema.json`, `fhr/fhr_schema.json`, and root
`fhr_schema.json`), serializers, examples, and documentation. Add regression tests
for changed behavior, including minimal metadata and relevant invalid cases.
Document checksum semantics and migration rather than silently changing identity.
Keep required metadata and runtime dependencies small.

David and Adam are the maintainers and jointly hold schema and release authority
([GOVERNANCE](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/GOVERNANCE.md)). The steering-group option described there is not active.
Follow CODE_OF_CONDUCT and use the SECURITY policy for sensitive findings. Private reporting addresses and independent conflict/appeal routing are documented there.

Release preparation does not authorize publishing packages, merging PRs, or
transferring repository ownership. Keep companion PRs linked for coordinated review.

## Coordinated documentation and citations

Guidance and README changes are tracked in [specification issue #23](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/23). Both private conduct/security contacts and the conflict/appeal routing are documented in the policies.

Use Chicago bibliography entries with DOI resolver links in human-readable citations. Keep the published paper, preprint, specification and converter distinct; preserve concept DOI meaning and existing BibTeX keys. CFF/BibTeX remain machine-readable metadata. The file audit and companion PRs are recorded in [FHR-Citation/AUDIT.md](https://github.com/FAIR-bioHeaders/FHR-Citation/blob/main/AUDIT.md), tracked by [issue #25](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/issues/25).

## Releasing

Each release publishes two PyPI distributions with the same version:
`fair-bioheaders` (this project, built by Poetry) and `fhr`, the former name,
which is built from `compat/fhr` with `python -m build compat/fhr` and only
requires `fair-bioheaders==X.Y.Z` and declares the `fhr-*` commands.

1. In one PR, set the version in `pyproject.toml`, `bioheaders/__init__.py`,
   `tests/fhr_test.py`, `tests/bioheaders_test.py`, `compat/fhr/pyproject.toml`
   (both `version` and the `fair-bioheaders==X.Y.Z` requirement), README and
   `CITATION.cff` (with `date-released`), and turn the CHANGELOG `Unreleased`
   heading into `## X.Y.Z — YYYY-MM-DD`.
2. After it merges, tag main:
   `git tag -a vX.Y.Z -m "FAIR-bioHeaders Tools vX.Y.Z"` and push the tag.
3. The [release workflow](.github/workflows/release.yml) checks the tag against
   both distribution versions and the `fhr` requirement, runs the tests, builds
   both wheels and sdists, installs the wheels outside the checkout as a smoke
   test, creates the GitHub release from the CHANGELOG entry with all four files
   (Zenodo archives it), and publishes both distributions to PyPI through
   trusted publishing in the `pypi` environment. Both PyPI projects must list
   this repository, `release.yml`, and the `pypi` environment as a trusted
   publisher.
4. Add the new Zenodo version DOI to `CITATION.cff`.

## License of contributions

New project contributions from March 2025 onward use [MPL-2.0](LICENSE). David Molik left USDA in February 2025. Historical USDA public-domain material remains public domain within the United States; its original notice is preserved in LICENSE. Previously granted permissions and third-party terms remain intact. The project includes both historical material and subsequent MPL-2.0 contributions; file notices and history identify provenance. New contributions must have the rights needed for their declared license; retain source notices.
