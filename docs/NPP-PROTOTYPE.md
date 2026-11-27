# NPP verification-report prototype (Tools #169, increment PR-A)

**Status: prototype.** The command `bioheaders npp` builds a layered verification
report for one file, bound to the maintainer-accepted NPP/Janeway mapping slice
(`npp-fhr-publication`, profile_version `0.1.0-draft.2`, landed commit
`efa67d71fecb90a7b47e47f6c036324d2f71d19b`, decision record on specification
#249). It is not a JATS exporter, not a registration or deposit tool, and it
implies no scientific certification.

```console
$ bioheaders npp genome.fhr.fasta                      # JSON report to stdout
$ bioheaders npp genome.fhr.fasta --text               # human summary
$ bioheaders npp protein.fhp.fasta --parent genome.fhr.fasta
```

Layers are decided independently and reported separately:

| layer | source of truth | outcomes |
| --- | --- | --- |
| `schema` | version-aware bundled selection; contracts outside the bundle raise `UnsupportedSchemaVersion` | `valid` / `invalid` / `refused-unsupported-schema` |
| `integrity` | header SHA-512/256 vs recomputed over the exact bytes | `pass` / `fail` / `absent` |
| `parent_links` | the documented `verify-links` exit-code contract (0/1/2/3); message text is captured as data, never parsed for logic | `pass` / `mismatch-or-unchecked` / `input-error` / `usage-error` / `not-run` |
| `not_run` | biology, live services, JATS projection | always explicit; absence never reads as success |

The report binds the input (`bytes`, `sha256`, header checksum), toolkit version,
selected contract and bundled-schema digest, and the accepted profile pair.
Builds are deterministic: same bytes, same report (no clocks, no network).

**Exit codes:** `0` executed layers pass (recorded parents unchecked without
candidates count as `pass-unchecked-parents`), `1` a layer failed or the input
could not be read, `2` usage.

Not yet built (open acceptance criteria of #169): the JATS table fragment
emitter bound to the accepted crosswalk (PR-B), the HTML microdata preview and
full public-API documentation pass (PR-C). Production Janeway compatibility is
gated by Q3b (specification #292, round NPP-3) and is **not** claimed here.
