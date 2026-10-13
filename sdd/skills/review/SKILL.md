---
name: review
description: Use when the user types /sdd-planner:review, or asks to review, walk through, explain, or check a Software Design Description (SDD).
argument-hint: "[path to SDD .md] [walk | notion]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sdd.py:*), Bash(python3 --version), Artifact, ArtifactData, ArtifactComments
---

# /sdd-planner:review

The plugin root is `${CLAUDE_PLUGIN_ROOT}`. If that path still starts with a dollar sign (the variable was not replaced), the plugin root is the folder two levels above this skill's base directory. Below, `<plugin root>` means that path.

1. Run `python3 --version`. If `python3` is missing or older than 3.9, stop and say: "sdd-planner needs Python 3.9 or newer as `python3`. macOS includes it; on Linux, install it with your package manager."
2. Read `<plugin root>/core/review.md` and follow it. Arguments: `$ARGUMENTS` (if that is empty or still starts with a dollar sign, use what the user asked for).

The procedure lives in that file, not in this one. If it is missing, say so and stop. Do not run the procedure from memory.

## Plugin options

The options set with `/plugin configure sdd-planner@claude-code-sdd`, one per line. A line whose value still starts with a dollar sign was never set. Wherever the procedure says "with the options", pass this block to the helper on stdin exactly as shown:

```text
organization=${user_config.organization}
author=${user_config.author}
notion_data_source_id=${user_config.notion_data_source_id}
notion_title_property=${user_config.notion_title_property}
notion_title_prefix=${user_config.notion_title_prefix}
notion_status_property=${user_config.notion_status_property}
notion_status_draft=${user_config.notion_status_draft}
notion_status_published=${user_config.notion_status_published}
notion_tags_property=${user_config.notion_tags_property}
notion_tags=${user_config.notion_tags}
notion_fixed_properties=${user_config.notion_fixed_properties}
notion_heading_marks=${user_config.notion_heading_marks}
notion_page_icon=${user_config.notion_page_icon}
```
