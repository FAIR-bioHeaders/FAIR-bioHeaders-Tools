# FHGFF3 examples and microdata fixtures

The GFF3 files and YAML/JSON headers are this toolkit's synthetic FHGFF3
examples (plain, embedded-`##FASTA`, invalid-header and stale-parent cases; see
FAIR-bioHeaders-Specification [docs/FHGFF3.md](https://github.com/FAIR-bioHeaders/FAIR-bioHeaders-Specification/blob/main/docs/FHGFF3.md)).
The `*.microdata.fhgff3.*` files are the HTML microdata binding fixtures copied
from [FHGFF3](https://github.com/FAIR-bioHeaders/FHGFF3) at commit
`1bfccedbe444e5a9d9c39ae3e7d1b35e43df77e0` (`main`), where the reviewed binding
`docs/FHGFF3-MICRODATA.md` (rules H1 to H8, named canonical by shared
docs/MICRODATA.md) keeps them as its conformance oracle. Names, checksums,
counts and identifiers are placeholders, not real data.

| File | Purpose |
| --- | --- |
| `annotation.fhgff3.gff3`, `embedded-fasta.fhgff3.gff3` | Verified FHGFF3 GFF3 fixtures |
| `stale-parent.fhgff3.gff3`, `header-invalid.fhgff3.gff3`, `no-header.gff3` | Negative file-backed fixtures |
| `genome.fhr.fasta` | Parent genome for `verify-links` examples |
| `annotation.fhgff3.yaml`, `rich.fhgff3.yaml`, `minimal-reference.fhgff3.json` | Metadata records for the GFF3 examples |
| `minimal-reference.microdata.fhgff3.html` + `.json` + `.yaml` | Valid standalone microdata; asserted `genomeReference` link only (H4) |
| `minimal-parent.microdata.fhgff3.html` + `.json` + `.yaml` | Valid standalone microdata; checksum-linked `annotates` FHR parent only (H4) |
| `rich-microdata.microdata.fhgff3.html` + `.json` + `.yaml` | Valid standalone microdata; both links, ordered arrays, nested objects, `featureCounts` with a zero count, `completeness`, escaped Unicode and markup (H3, H5, H6) |
| `invalid-itemtype.microdata.fhgff3.html` | FHR itemtype carrying an FHGFF3 record: not FHGFF3 (H1) |
| `invalid-unsupported-version.microdata.fhgff3.html` | `schemaVersion` `"2.0"` under the FHGFF3 1.0 contract (H2) |
| `invalid-unknown-release.microdata.fhgff3.html` | A release the reader does not carry (H2, V4) |
| `invalid-malformed-nesting.microdata.fhgff3.html` | An array container child without `itemprop="item"` |
| `invalid-repeated-scalar.microdata.fhgff3.html` | A repeated single-valued property (H7) |
| `invalid-repeated-array.microdata.fhgff3.html` | Two array containers for one array field (H7) |
| `invalid-unsafe-content.microdata.fhgff3.html` | Metadata that exists only inside a `<script>` block (H6) |
| `invalid-no-genome-link.microdata.fhgff3.html` | Neither genome-link alternative (H4) |
| `invalid-two-annotates.microdata.fhgff3.html` | Two `annotates` parents (H4) |
| `invalid-annotates-non-fhr.microdata.fhgff3.html` | An `annotates` parent that is not FHR (H4) |

The `.microdata.fhgff3.html` files are generated, not hand edited. Regenerate
them with the writer in this checkout and keep the FHGFF3-side copies equal:

```bash
python - <<'PY'
import json, pathlib
from bioheaders import fhgff3_microdata

base = pathlib.Path("examples/fhgff3")
for path in sorted(base.glob("*.microdata.fhgff3.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    stem = path.name[: -len(".microdata.fhgff3.json")]
    (base / f"{stem}.microdata.fhgff3.html").write_text(
        fhgff3_microdata.write_page(record), encoding="utf-8"
    )
PY
```

`tests/fhgff3_microdata_test.py` checks the bytes: the committed HTML equals
the writer output, the committed records extract back from it, and every
`invalid-*.microdata.fhgff3.html` fixture is rejected. The shipped package
therefore verifies its own behavior against the binding's fixtures without
reading a sibling checkout.
