# Data Model: metadata options document

The document is command input, not FHR metadata: it has no `schema`,
`schemaVersion` or `checksum`, and the record it produces is the one
specs/004-bioheaders-metadata defines.

## Options document

One JSON object. Every key is optional in the document; the required metadata
options are enforced afterwards exactly as for the flags (all missing ones
listed together).

| Kind | Keys | JSON value | Becomes (the flag's text) |
| --- | --- | --- | --- |
| text | `type`, `genome`, `taxon-name`, `version`, `date-created`, `masking`, `voucher-specimen`, `accession`, `accession-url`, `scholarly-article`, `documentation`, `funding`, `reuse-conditions`, `assembly-protocol`, `seqcol-id`, `stats-from` | string | the string |
| taxon id | `taxon-id` | string, or integer (not boolean) | the string / the integer's decimal text |
| text list | `genome-synonym`, `instrument`, `identifier`, `related-link` | list of strings | one value per item, in order |
| author list | `metadata-author`, `assembly-author` | list of Author | `Name` or `Name <orcid>` per item |
| software list | `assembly-software` | list of Software | `NAME`, `NAME=VERSION`, `NAME==URI` or `NAME=VERSION=URI` |
| stat list | `stat` | list of Pair; `value` string or number | `KEY=VALUE` |
| extension list | `extra` | list of Pair; `value` string | `KEY=VALUE` |

Any key may be `null`; a list key may be `[]`. Both mean "not given".

## Author

| Member | Required | JSON value | Rule |
| --- | --- | --- | --- |
| `name` | yes | string | no `<` or `>`; then the flag's text checks |
| `orcid` | no | string or null | full `https://orcid.org/XXXX-XXXX-XXXX-XXXX` URI with a valid check digit |

## Software

| Member | Required | JSON value | Rule |
| --- | --- | --- | --- |
| `name` | yes | string | no `=` |
| `version` | no | string or null | no `=`; not empty |
| `uri` | no | string or null | R14 scheme (checked with the record) |

## Pair

| Member | Required | JSON value | Rule |
| --- | --- | --- | --- |
| `key` | yes | string | `stat`: a `vitalStats` field; `extra`: an R15 `x-` key |
| `value` | yes | string (or number for `stat`) | `stat`: typed by the schema; `extra`: text |

## Validation order

1. Command line: any metadata flag given with `--json` → refused.
2. Bytes: more than 1 MiB, byte order mark, invalid UTF-8 → refused.
3. JSON: syntax, duplicate keys, `NaN`/`Infinity`, nesting depth → refused.
4. Shape: top-level object, known keys, JSON types, list members → refused,
   naming the key path (`metadata-author[0].orcid`).
5. `--json -` with `stats-from` `-` → refused.
6. The flags' checks (`require`, `build_record`, schema), before any FASTA is
   read; then statistics, then output. Nothing is written on failure.
