# Sync: regenerate the Notion page from the SDD file

Used by `/sdd:write` after every section, by `/sdd:review` after edits, and by `/sdd:publish`. The markdown file is the source of truth. Every sync rebuilds the whole page from it, so a sync can be repeated safely and a failed one is fixed by the next one. IDs and property formats are in `rules.md`.

`S` = `python3 <plugin root>/scripts/sdd.py`

**Notion off** (`notion_enabled` is false in `S settings`): every mode below does nothing. The markdown file is the whole SDD.

## Draft mode

1. **Render.** Run `S render <file>` (the page body) and `S props <file>` (the properties as JSON). If either fails, show the error, run `S meta <file> --set notion_pending=true`, and stop the sync. The section is already saved in the file.
2. **Find the page.** Read `notion_page_id` from `S meta <file>`.
3. **No page yet: create it.** Call `notion-create-pages` with:
   - `parent`: `{"type": "data_source_id", "data_source_id": "<notion.data_source_id from S settings>"}`
   - one page with `icon` = `notion.page_icon` (leave it out when empty), `properties` = the JSON from `S props`, and `content` = the render output exactly as printed.
   Then store the new page id: `S meta <file> --set notion_page_id=<id>`.
4. **Page exists: replace it.** Call `notion-update-page` with `page_id`, `command: "replace_content"`, `new_str` = the render output exactly as printed, and `allow_async: false`. If a property changed (the status after a release, the tags), make a second call with `command: "update_properties"` and the props JSON.
   - If Notion rejects the size, repeat with `allow_async: true` and poll `notion-get-async-task` until it reports succeeded.
   - If Notion says child pages or databases would be deleted, stop and ask the user. Never pass `allow_deleting_content: true` without a yes.
5. **Record it.** `S meta <file> --set notion_last_sync=<now, ISO 8601 UTC> notion_pending=false`.
6. **Tell the user in one line:** `Notion updated: SDD: <title> (<done> of 11 sections).` Use the page title, not the URL.

Pass the render output with its real newlines and tabs. Never turn them into `\n` or `\t` escape sequences: Notion would show them as the letters "n" and "t".

**Page layout.** Every section, view and ADR is a toggle heading, closed by default, whose first child is a gray "About this section" note built from `core/sections.md` and `core/viewpoints.md`. Chapter headings (1. to 5., Revision History) stay plain. The first sync of a page made before toggles existed moves every block under its toggle once; comments made on that older layout may not survive the move.

**What Notion does with it** (verified on the render-check page, 2026-10-06 and 2026-10-07):

- `replace_content` updates the page in place: unchanged blocks keep their IDs, changed text is edited inside the same block, and comments on blocks stay attached either way. Repeating a sync with the same file leaves the page unchanged.
- Toggle headings take indented callouts, tables, lists, sub-headings and code blocks as children. Notion strips the nesting tab from code block contents. A repeated identical write does not even change the page's `Last edited time`, so the drift check never trips on Claude's own syncs.
- A fetch returns the page slightly normalized. Ignore these when comparing it with `S render`: tab indentation inside tables is dropped, bare URLs in table cells become `[url](url)` links, and `_italic_` comes back as `*italic*`. Property values come back markdown-escaped (`SDD: \[TEST\] ...`); the real title has no backslashes.

## Drift check

Run it when `/sdd:write` resumes a file in a new session, and at the start of `/sdd:publish`.

1. No `notion_page_id`: skip.
2. `notion-fetch` the page and read its `Last edited time` property.
3. If that is more than 2 minutes after `notion_last_sync`, someone edited the page in Notion and the next sync would erase it. One question screen (header "Notion"):
   - "Show me the Notion edits" (Recommended): compare the fetched page with `S render <file>`, list the differences in plain words, and offer to copy them into the markdown (write with `S section ... --write`, show the result) before syncing.
   - "Overwrite with the file": continue.
   - "Cancel": stop without syncing.

## Final mode

Used by `/sdd:publish` after `S release`. Run draft mode (the props now say Status Done), then verify by reading the page back:

1. `notion-fetch` the page.
2. Check each item and report it as pass or fail:
   - **Headings:** the number of level 1, 2 and 3 headings equals the counts in the render output, marks included when the settings set them.
   - **Tables:** the number of tables on the page equals the number of `<table header-row="true">` lines in the render output.
   - **Diagrams:** the number of mermaid code blocks matches.
   - **Blocks:** one table of contents block and the gray header callout are present.
   - **Text:** no literal `\n` or `\t`, and no escaped table tags such as `\<table`.
   - **Properties:** each property in `S props` has that value on the page.
3. On a failure: find the cause (usually the file, sometimes `sdd.py render`), fix it, sync once more and re-check. If it still fails, report it and stop. Do not loop.

## When Notion fails

Writing never waits on Notion. On any Notion error: the section is already in the file, run `S meta <file> --set notion_pending=true`, tell the user in one line, and carry on with the next section. The next sync in any mode rebuilds the whole page, so it catches up by itself.
