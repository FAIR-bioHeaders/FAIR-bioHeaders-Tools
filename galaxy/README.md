# Galaxy tools

`tools/fair_bioheaders/` holds [Galaxy](https://galaxyproject.org/) wrappers for
the `bioheaders` command, laid out as in
[galaxyproject/tools-iuc](https://github.com/galaxyproject/tools-iuc) so that
the directory can be copied there unchanged:

| Tool | Command | What it does |
|---|---|---|
| FAIR-bioHeaders combine | `bioheaders combine` | add a header (from YAML, JSON or JSON-LD metadata) to FASTA, GFA or GFF3 and calculate its checksum |
| FAIR-bioHeaders verify | `bioheaders verify`, `bioheaders validate` | check a header's metadata and checksum, or a metadata file; text report |
| FAIR-bioHeaders strip | `bioheaders strip` | remove the header; optionally save the metadata as YAML, JSON or JSON-LD |
| FAIR-bioHeaders convert | `bioheaders convert` | convert metadata, or a file's header, to YAML, JSON, JSON-LD or HTML |

All four accept plain and gzip-compressed FASTA (nucleotide or protein), GFA
(`gfa1`, `gfa2`) and GFF3 datasets, and datatypes derived from these. They
require the Bioconda package `fair-bioheaders` at the version in `macros.xml`
(`@TOOL_VERSION@`, which CI keeps equal to the version in `pyproject.toml`). From
0.8.2 the Bioconda package also brings `pyld` (the `jsonld` extra, needed for
JSON-LD that is not in the canonical form), so the tools use the single
BioContainers image `quay.io/biocontainers/fair-bioheaders`.

The Galaxy wrapper files in this directory are licensed under the MIT License
(see [`LICENSE`](LICENSE)), like the tools in tools-iuc, while the
fair-bioheaders toolkit itself is licensed under MPL-2.0.

## Testing

```bash
pip install planemo==0.75.47
cd galaxy/tools/fair_bioheaders
planemo lint --fail_level warn .
planemo shed_lint --tools --fail_level warn .
# against the Bioconda package:
planemo test .
# against this checkout (as CI does), with bioheaders on PATH:
pip install "../../..[jsonld]" && planemo test --no_dependency_resolution .
```

The test data are small copies of `examples/`, or derived from them. The
`*.bgzf.gz` files are the toolkit's own (deterministic) BGZF output, compared
byte for byte; regenerate them with `bioheaders combine` or `strip` if the BGZF
writer changes.

## In tools-iuc and the Tool Shed

The tools were merged into galaxyproject/tools-iuc in
[galaxyproject/tools-iuc#8793](https://github.com/galaxyproject/tools-iuc/pull/8793)
(2026-10-28) and are published on the main Galaxy Tool Shed under the `iuc` owner:
[`suite_fair_bioheaders`](https://toolshed.g2.bx.psu.edu/view/iuc/suite_fair_bioheaders)
installs all four, or install
[`fair_bioheaders_combine`](https://toolshed.g2.bx.psu.edu/view/iuc/fair_bioheaders_combine),
[`fair_bioheaders_verify`](https://toolshed.g2.bx.psu.edu/view/iuc/fair_bioheaders_verify),
[`fair_bioheaders_strip`](https://toolshed.g2.bx.psu.edu/view/iuc/fair_bioheaders_strip) and
[`fair_bioheaders_convert`](https://toolshed.g2.bx.psu.edu/view/iuc/fair_bioheaders_convert)
individually.

**The canonical copy is now
[tools-iuc `tools/fair_bioheaders`](https://github.com/galaxyproject/tools-iuc/tree/main/tools/fair_bioheaders).**
This directory is kept in step with it for testing against this checkout.

Galaxy servers install the tools-iuc copy, so make changes there
(and copy them back here): bump `@TOOL_VERSION@`
(and reset `@VERSION_SUFFIX@` to 0) for a new release of fair-bioheaders, or
increase `@VERSION_SUFFIX@` for a change to the wrappers only.
