# FHP examples and format fixtures

The canonical FHP 1.0 records are synthetic examples copied from
[FHP-Specification](https://github.com/FAIR-bioHeaders/FHP-Specification) at
commit `9931a30cd6cb77619cd8d53b91ab41b5aae95eca` (`main`). Names, checksums,
counts and identifiers are placeholders, not real data.

| File | Purpose |
| --- | --- |
| `*.fhp.json`, `*.fhp.yaml` | Canonical FHP 1.0 records |
| `*.fhp.jsonld` | Canonical JSON-LD written by the toolkit from the matching record |
| `minimal-predicted.microdata.fhp.html` | Standalone HTML microdata for `minimal-predicted.fhp.json` |
| `rich-microdata.microdata.fhp.html` | Standalone HTML microdata for `rich-microdata.fhp.json` |
| `example.fhp.fasta` | Verified FHP protein FASTA fixture |

The `.fhp.jsonld` and `.microdata.fhp.html` files are generated, not hand
edited. Regenerate them with the writer in this checkout:

```bash
python - <<'PY'
import json, pathlib, yaml
from bioheaders import fhr, fhp_microdata

base = pathlib.Path("examples/fhp")
for path in sorted(base.iterdir()):
    if path.name.endswith(".fhp.json"):
        stem = path.name[: -len(".fhp.json")]
        record = json.loads(path.read_text())
    elif path.name.endswith(".fhp.yaml"):
        stem = path.name[: -len(".fhp.yaml")]
        record = yaml.safe_load(path.read_text())
    else:
        continue
    data = fhr(**record)
    (base / f"{stem}.fhp.jsonld").write_text(data.output_jsonld())
    if stem in ("minimal-predicted", "rich-microdata"):
        (base / f"{stem}.microdata.fhp.html").write_text(
            fhp_microdata.write_page(record)
        )
PY
```

## Contract provenance

- FHP schema: FHP 1.0 from FAIR-bioHeaders-Specification v0.4.0, release commit
  `84c2f90ab0e97c81d8afbf33eafe80ebade7a009`; `fhp.json` SHA-256
  `e3f8f45260b833f931644e87ff7530cb9b4151e67094023dd96edde9a1d90366`.
- FHP JSON-LD context: FHP-Specification `main` commit
  `9931a30cd6cb77619cd8d53b91ab41b5aae95eca`; `jsonld/fhp.context.jsonld`
  SHA-256 `cb0b91c6bd55ff6026f0a3e7a30524c3a1d800922dbbf7117f6fe79c7760a984`,
  bundled byte-identically as `bioheaders/fhp.context.jsonld`.
- Shared vocabulary reused by the context: FAIR-bioHeaders-Specification v0.4.0,
  commit `84c2f90ab0e97c81d8afbf33eafe80ebade7a009`; `jsonld/terms.ttl` SHA-256
  `0c641879818a1ce02ed10348b344cb11c37fd86c8a120a9f9bfe8e618d32042c`.
- Context publication is coordinated through
  FAIR-bioHeaders-Specification#107; runtime support is
  FAIR-bioHeaders-Tools#58. Nothing is fetched at run time.
