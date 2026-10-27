# Tasks: `bioheaders faidx`

- [x] T001 Read htslib 1.24 `faidx.c` and `bgzf.c`; record the rules in plan.md (Research).
- [x] T002 `bioheaders/faidx.py`: `FaiBuilder` state machine following `fai_build_core`, fed from `sequence_parts` with absolute offsets; `;` comments allowed in the leading block.
- [x] T003 `bioheaders/faidx.py`: BGZF block reader with header/CRC/length checks, plain-gzip error, `.gzi` entries as `bgzf_index_dump` writes them.
- [x] T004 `bioheaders/cli.py`: `faidx` subcommand (`-o`, `--gzi`), regular-file input, output-is-input checks, atomic writes, warnings.
- [x] T005 Tests: expected records, CRLF, unterminated last line, chunk sizes 1-64, header offsets, records without sequence, errors (gzip, inconsistent lines, duplicates, empty, header-only, FASTQ, lone CR, long names, late header lines, header limits), BGZF `.gzi`, command behaviour.
- [x] T006 Tests with samtools/bgzip: byte-identical `.fai`/`.gzi` and the same accept/reject decision over fixed and 200 generated header-less files (plain, bgzip, toolkit BGZF); region lookups on FHR and FHP files, plain and BGZF, equal the stripped file's; `samtools faidx FILE` without a region still fails and keeps the index.
- [x] T007 Tests with pysam: `FastaFile.fetch` on headed files equals the stripped file's.
- [x] T008 CI: install samtools, tabix (bgzip) and pysam; require the comparison tests.
- [x] T009 README section with the unblocked tools and the "index first" caveat; CHANGELOG; AGENTS.md map; plugin skill.
- [ ] T010 FAIR-bioHeaders-Specification `docs/TOOL_COMPATIBILITY.md` "Recommended workarounds": point to `bioheaders faidx` once released (separate PR).
