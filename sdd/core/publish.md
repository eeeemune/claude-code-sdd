# /sdd:publish

Finalize one SDD: check it and version it. When Notion is on, also write it to Notion with its published properties and read the page back to verify it. Read `<plugin root>/core/rules.md` and `<plugin root>/core/sync.md` first.

`S` = `python3 <plugin root>/scripts/sdd.py`. Paths like `core/sync.md` are relative to `<plugin root>`.

## Steps

1. **Find the SDD** the same way as `/sdd:review` step 1. None found: say so and suggest `/sdd:write`.
2. **A previous publish that never reached Notion:** if front matter has `status: published` and `notion_pending: true`, the version is already bumped. Skip to step 6.
3. **Lint gate.**
   - Run `S lint <file> --fix`. It only rewrites diagram direction; report what it changed.
   - Errors left: list each in plain words with its line number, and stop. Offer to fix them together: rewrite em-dash sentences, ask for the values behind `{{...}}`, add the missing acceptance checks.
   - Warnings: list them.
   - Run `S status <file>`. Lint does not look for empty sections, so this is the check that stops an unfinished design from going out as Done.
   - Sections still `todo` or `skipped`, `**TODO:**` lines, or ADRs at `Status: proposed`: list them, then ask (header "Open items") Fill them first (Recommended) / Publish as a draft. "Fill them first" points to `/sdd:write`, which resumes at the first open section. "Publish as a draft" runs `core/sync.md` draft mode, reports, and stops: no version bump, and the page keeps its draft properties.
4. **Drift check** from `core/sync.md` (only when Notion is on).
5. **Release.**
   - Suggest the reason: "First published version" on a first publish; otherwise a summary of what changed since the last Revision History row (the file's git diff when it is in a repo, else the sections changed in this session).
   - Ask (header "Reason") with the suggestion as the first option; the user can type their own in Other.
   - Run `S release <file> --reason "<reason>" --author "<git config user.name>"`.
6. **Sync in final mode** (`core/sync.md`), including the read-back checks. Notion off: skip this step.
7. **Report:**
   - the version change (for example 0.4 to 1.0);
   - when Notion is on: the page title (not the URL), its published properties, and each read-back check, pass or fail;
   - next steps: build against this document, using the 1.6 acceptance checks as the verify steps. To change it later, edit the markdown (or run `/sdd:review`) and run `/sdd:publish` again.
