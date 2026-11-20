# Contract: `bioheaders metadata --json` options document

Status: proposed with FAIR-bioHeaders-Tools#197; public API from the first
release that includes it. Within a major version keys may be added, never
renamed, removed or given another meaning.

## Command line

```text
bioheaders metadata --json FILE [--format yaml|json] [-o OUTPUT]
bioheaders metadata --json -    [--format yaml|json] [-o OUTPUT]   # document on stdin
```

- Any other `metadata` option given with `--json` is an error (exit 1) naming it.
- `-o`/`--format` behave as without `--json`. `-o` may not name the document.
- Exit status and output are those of the equivalent flags: 0 and the same
  bytes on success; 1 and nothing written on any refusal.

## Document

UTF-8 JSON (RFC 8259), no byte order mark, at most 1 MiB, one top-level object.
Keys are the `metadata` options without their leading `--`:

| Key | Flag | JSON value |
| --- | --- | --- |
| `type` | `--type` | `"fhr"` (`"fhp"`, `"fhgff3"` refused: not supported yet) |
| `genome` | `--genome` | string |
| `genome-synonym` | `--genome-synonym` | list of strings |
| `taxon-name` | `--taxon-name` | string |
| `taxon-id` | `--taxon-id` | string of digits or positive integer |
| `version` | `--version` | string |
| `metadata-author` | `--metadata-author` | list of `{"name", "orcid"?}` |
| `assembly-author` | `--assembly-author` | list of `{"name", "orcid"?}` |
| `date-created` | `--date-created` | string `YYYY-MM-DD` |
| `masking` | `--masking` | string, one of the schema's values |
| `voucher-specimen` | `--voucher-specimen` | string |
| `accession` | `--accession` | string |
| `accession-url` | `--accession-url` | string (needs `accession`) |
| `instrument` | `--instrument` | list of strings |
| `scholarly-article` | `--scholarly-article` | string |
| `documentation` | `--documentation` | string |
| `identifier` | `--identifier` | list of strings |
| `related-link` | `--related-link` | list of strings |
| `funding` | `--funding` | string |
| `reuse-conditions` | `--reuse-conditions` | string |
| `assembly-software` | `--assembly-software` | list of `{"name", "version"?, "uri"?}` |
| `assembly-protocol` | `--assembly-protocol` | string |
| `seqcol-id` | `--seqcol-id` | string |
| `stats-from` | `--stats-from` | string: FASTA path, or `"-"` (not with `--json -`) |
| `stat` | `--stat` | list of `{"key", "value"}`; value string or number |
| `extra` | `--extra` | list of `{"key", "value"}`; value string |

- `null` (any key or optional member) and `[]` mean "not given". An empty
  string is not "not given": it is refused as `--option ""` is.
- Lists keep their order in the output, as repeated flags do.
- Author `name` may not hold `<` or `>`; software `name` and `version` may not
  hold `=` (the flags use them as separators).
- Every value then passes the flag's checks; messages name the flag
  (`--date-created: '2026-02-30' is not a date`).

## Refused (exit 1, nothing written)

Unknown keys at any level (with a suggestion), a key twice in one object,
values of another JSON type (including booleans for numbers), `NaN`,
`Infinity`, invalid JSON, invalid UTF-8, a byte order mark, more than 1 MiB,
excessive nesting, a top level other than an object, missing required members
of list objects, and everything the equivalent flags refuse.

## Example

```json
{
  "genome": "Taeniopygia guttata",
  "taxon-name": "Taeniopygia guttata",
  "taxon-id": 59729,
  "version": "1",
  "date-created": "2024-01-02",
  "masking": "not-masked",
  "metadata-author": [{"name": "Adam Wright", "orcid": "https://orcid.org/0000-0002-5719-4024"}],
  "assembly-author": [{"name": "Vertebrate Genomes Project", "orcid": null}],
  "assembly-software": [{"name": "hifiasm", "version": "0.19.8"}],
  "stats-from": "genome.fa.gz",
  "stat": [{"key": "readTechnology", "value": "hifi"}],
  "funding": null
}
```

is equivalent to

```bash
bioheaders metadata --genome "Taeniopygia guttata" \
  --taxon-name "Taeniopygia guttata" --taxon-id 59729 --version 1 \
  --date-created 2024-01-02 --masking not-masked \
  --metadata-author "Adam Wright <https://orcid.org/0000-0002-5719-4024>" \
  --assembly-author "Vertebrate Genomes Project" \
  --assembly-software hifiasm=0.19.8 --stats-from genome.fa.gz \
  --stat readTechnology=hifi
```
