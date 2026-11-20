# Native FHGM model 0.1 in toolkit 0.13.0

Specification v0.8.0 publishes the native model contract at
`model-contracts/fhgm/0.1/fhgm-model.schema.json`, with identifier
`https://w3id.org/fair-bioheaders/model-contracts/fhgm/0.1` and SHA-256
`56c0a5a91e9e56c50c0919a375505c01f52bce5f1792841c40b87b1cd18e9336`.
`bioheaders/schemas/bundled.json` records the actual tag commit, GitHub Release
and archive identifier. The package reads its pinned bytes offline; accepting
an identifier does not establish that the external w3id redirect is deployed.

FHGM is a native model carried by the FHGFF3 `x-fhgm-models` array. There is no
FHGM header registry row, no in-record schema field and no schemaVersion. The
four header types remain FHR, FHP, FHGFF3 and FHT. The accepted transport allows
FHGFF3 carriers citing v0.5.0 or v0.6.0; newer carrier citations, raw main and
unknown model versions are refused rather than silently substituted.

Model checking remains a separate experimental implementation gate:

```sh
BIOHEADERS_EXPERIMENTAL_FHGM=1 bioheaders verify annotation.fhgff3.gff3
BIOHEADERS_EXPERIMENTAL_FHGM=1 BIOHEADERS_FHGM_CONTRACT=0.1 bioheaders verify annotation.fhgff3.gff3
```

An enabled implementation selects the published native 0.1 contract by default.
`BIOHEADERS_FHGM_CONTRACT=draft` explicitly replays the preserved owning V7
snapshot and its commit/digest warnings. Unknown selections fail. A closed gate
evaluates no model rules: a successful header/checksum check is not a model pass.
Publication of the contract does not remove the implementation gate.

The `FHGM model 0.1:` report separates the released base header, exact-byte
SHA-512/256 checksum, K1–K6 model checks and GFF3 feature/biology layer. Native
selection and record-schema provenance are also in the structured API report.
The feature layer is always `not-run` here; use gff3-validator independently.
No feature, biological-correctness or curator-acceptance conclusion follows
from a model pass. Published gff3-validator 0.1.0 additionally has a lone-CR row
limitation; its LF/CRLF observations do not establish lone-CR feature validity.

`--fhgm-predecessor FILE`, repeated as needed, supplies the only history a K6
revision pointer may resolve against. A resolvable predecessor identifies a
record, not accepted supersession. Unsupported/unavailable prerequisites remain
explicitly not-run. The existing bounded input observer preserves exact
carrier bytes for K4; stdin is consumed once and gzip/BGZF is decompressed
without normalizing line endings or checksum coverage. Oversized inputs report
an unexecuted model layer rather than truncating evidence into a pass.

JSON/YAML metadata and GFF3 combine/strip preserve the extension records. JSON-LD
and HTML microdata reject/omit extension fields under their existing J9/M5
rules, and are not FHGM serializations. `verify-links` does not resolve model
predecessors, `assess` does not score model rules, and `faidx` is not a GFF3 index.
The generated capability matrix lists supported operations and refusals.

The historical owning 92-vector manifest and its recorded 1.2 twin matrix are
preserved separately from the published native schema. Native acceptance runs
184 case visits using the owning runner's digest-pinned `twin_bytes` derivation,
while the original V7 lane remains independently tested. Reports retain each
layer and prerequisite limitation; an expected NOT_RUN is never counted as a
complete model pass. The historical v0.6.0 291-payload ledger remains unchanged.
