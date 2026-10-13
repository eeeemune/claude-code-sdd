# Tests

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The suite uses the standard library only and passes on Python 3.9 to 3.14. Commands that take plugin options get them as an options block on stdin (`--options -`), so nothing on your machine changes their results.

## Fixtures

- `../sdd/examples/preview-envs.md` (read as `full.md`): a complete SDD (the running example: per-PR preview environments on EKS). Lint must report nothing on it.
- `fixtures/partial.md`: 1.2 and 1.6 written, 2.1 skipped with a TODO, 5 not applicable, everything else still the template. Its Sections 3 and 4 keep the commented record skeletons, which must never be read as real views or decisions.
- `fixtures/bad.md`: exactly one violation per lint rule.
- `fixtures/mini.md` and `fixtures/mini.notion.md`: a small input and its expected Notion render with heading marks, written by hand before `render` existed.
- `fixtures/options-notion.txt`: an options block with every Notion option set (title prefix, status values, tags, a fixed property, heading marks), with a placeholder data source ID.

## Notion render check

Needs a Notion database of your own and its ID in the `notion_data_source_id` option. Sync `sdd/examples/preview-envs.md` to a test page, fetch it, and run the final-mode checks in `core/sync.md`.

Result on 2026-10-06, with heading marks set: 6 / 14 / 4 marked headings, 5 tables, 4 mermaid diagrams, table of contents and callout present, no literal `\n`, properties right. A second identical sync left the page unchanged. A block comment and a page comment both survived a sync, including one that changed the commented paragraph (the block was edited in place).

## Notion comment check

On 2026-10-07, two comments on the render-check page (one on a V4 paragraph, one asking "why 10 minutes" on R1) went through `/sdd-planner:review notion`: the first changed the file, the second got a reply. Both replies were posted, both comments survived the re-sync, and the V4 block was updated in place. Two things the run showed: a comment inside a section is often anchored to the toggle heading itself, and Notion returns comment text starting `[sdd]` escaped as `\[sdd\]`.

## Review page check

`review-page` output is checked by the unit tests: structure, notes, Claude's findings, embedded data, the notes round trip, `review-changed`, and the Original tab (every part in file order, title block, Revision History, links between cards and parts). The page script is not unit tested: after changing `review-page/template.html`, extract the last `<script>` block of a built page and run `node --check` on it.

The text matching behind suggested edits (`readSelection` and `locateQuote` in the page script) needs a real DOM. On 2026-10-07 those functions, copied out of the built page, ran in headless Chrome against a sample block with a table. All four cases passed: plain words, a selection across two table cells (the selection carries a tab the page text does not), a quote that appears twice (the before and after text picked the second copy), and a selection across bold text.

Live checks on 2026-10-07 and 2026-10-12, on claude.ai with the capabilities in `core/review.md` part 6a: a probe verdict and a probe suggested edit were written, read back with their versions, and deleted with those versions pinned. A full round of part 6b applied a suggested edit and a Needs changes verdict to a scratch SDD, synced Notion, wrote the outcomes back pinned to the versions read, and republished; every verdict survived the republish. A real review of a 25-part SDD on 2026-10-12 went through two rounds: verdicts, two comment threads sent to Claude, the write-back of 12 verdicts in one batch, and a republish.

Layout: at 400px wide (inside an iframe, as the viewer shows it) the page has no sideways scroll. A plain headless Chrome window cannot go below about 500px, so screenshots taken without an iframe look clipped.

## Page conditions (R8)

`python3 tests/page_conditions.py` opens the review page for `sdd/examples/preview-envs.md` in headless Chrome six times: with every capability, with the database refused, with Ask refused, outside claude.ai, in a 500px window, and in dark mode. A stand-in for the claude.ai runtime grants or refuses each capability. For each run it checks what is drawn on screen: every part's text and diagram source, which of Approve, Ask and Comment are enabled or shown, the notice, sideways scroll, and the background color. Pass `--chrome PATH` when Chrome is not in a standard place.

On 2026-10-12 all six passed. The same script run against the template of the first release candidate failed twice (the Ask box showed with Ask refused and outside claude.ai), which is the bug the `[hidden]` rule in the template fixes. claude.ai's own page wrapper hides `[hidden]` elements, so the bug showed only outside claude.ai.

## Baseline runs

`baseline/2026-10-06.md`: what Claude did on the two scenarios without the skill and with it.
