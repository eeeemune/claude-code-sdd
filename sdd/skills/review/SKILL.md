---
name: review
description: Use when the user types /sdd:review, or asks to review, walk through, explain, or check a Software Design Description (SDD).
argument-hint: "[path to SDD .md] [walk | notion]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py:*), Bash(python3 --version), Artifact, ArtifactData, ArtifactComments
---

# /sdd:review

The plugin root is `${CLAUDE_PLUGIN_ROOT}`. If that path still starts with a dollar sign (the variable was not replaced), the plugin root is the folder two levels above this skill's base directory. Below, `<plugin root>` means that path.

1. Run `python3 --version`. If `python3` is missing or older than 3.9, stop and say: "sdd needs Python 3.9 or newer as `python3`. macOS includes it; on Linux, install it with your package manager."
2. Read `<plugin root>/core/review.md` and follow it. Arguments: `$ARGUMENTS` (if that is empty or still starts with a dollar sign, use what the user asked for).

The procedure lives in that file, not in this one. If it is missing, say so and stop. Do not run the procedure from memory.
