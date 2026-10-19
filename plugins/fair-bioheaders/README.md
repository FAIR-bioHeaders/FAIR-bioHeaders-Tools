# FAIR-bioHeaders plugin for Claude Code

A Claude Code plugin with one skill, `fair-bioheaders`, that teaches Claude how to
add, verify, convert and strip FAIR-bioHeaders provenance headers (FHR, FHP,
FHGFF3) in FASTA, GFA and GFF3 files with the `bioheaders` command from the
[`fair-bioheaders`](https://pypi.org/project/fair-bioheaders/) package. The skill
tells Claude never to invent metadata values or edit checksums by hand.

## Install

In Claude Code:

```text
/plugin marketplace add FAIR-bioHeaders/FAIR-bioHeaders-Tools
/plugin install fair-bioheaders@fair-bioheaders
```

Or from a shell:

```bash
claude plugin marketplace add FAIR-bioHeaders/FAIR-bioHeaders-Tools
claude plugin install fair-bioheaders@fair-bioheaders
```

The skill runs commands from `fair-bioheaders`, so install that too:
`pip install fair-bioheaders`.

Claude uses the skill when a request matches it, for example "add an FHR header
to genome.fa". You can also run it as `/fair-bioheaders:fair-bioheaders`.

The skill is in [`skills/fair-bioheaders/SKILL.md`](skills/fair-bioheaders/SKILL.md).
