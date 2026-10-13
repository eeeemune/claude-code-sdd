# Rules shared by /sdd-planner:write, /sdd-planner:review and /sdd-planner:publish

## Reference (do not guess these)

- **Plugin root:** the folder the skill named when it started (`<plugin root>` in these procedures). Every file path and every `S` command below starts there.
- **Helper:** `python3 <plugin root>/scripts/sdd.py`, called `S` in the procedures. `S <command> --help` shows options.
- **Options:** the user sets the plugin options with `/plugin configure sdd-planner@claude-code-sdd`, and Claude Code shows them in the skill as the **options block**, one `key=value` line each. The helper never reads them from a file: pass the block on stdin with a quoted heredoc, `S <command> --options - <<'OPTS'`, then the block exactly as the skill shows it, then `OPTS`. "With the options" below means that. `S options --options -` prints them merged with the defaults; run it once per session. Every option is optional, and one that still reads `${user_config...}` was never set:
  - `organization`: the organization `S new` puts in the title block.
  - `author`: the name `S new` puts on a new SDD and `S release` puts on its Revision History row. `--author` overrides it; when it is empty, `S new` needs `--author` and `S release` uses the file's author.
  - `notion_*`: where pages go and how they look. `notion_enabled` is true only when `notion_data_source_id` is set; otherwise Notion sync is off and every Notion step is skipped. Lists (`notion_tags`, `notion_fixed_properties` as `Name=Value` pairs) are comma-separated, and `notion_heading_marks` holds 3 marks separated by spaces.
  - `warnings` lists options the helper ignores, and exit code 1 with an `error` means an option is malformed. Say either once, in one line, and carry on (a malformed option means Notion is off). To change an option, the user runs `/plugin configure sdd-planner@claude-code-sdd` and starts a new session.
- **Template:** `core/template.md`, the jam01 SDD template (commit 5dca2e5, CC0) plus front matter, section 1.6 Requirements and the record formats for Sections 3 and 4.
- **Worked example:** `tests/fixtures/full.md`.
- **Notion:** through whatever Notion connection the user has, the claude.ai Notion connector or a Notion MCP server. Call its tools by what they do, whatever prefix the connection gives them: `notion-search`, `notion-fetch`, `notion-create-pages`, `notion-update-page`, `notion-get-async-task`, and for review comments `notion-get-comments` and `notion-create-comment`. The user may be asked to allow each one the first time it runs. Nothing here needs `notion-query-data-sources`, which some plans do not have.
  - New pages go under the data source `notion.data_source_id`.
  - Properties: `S props` with the options builds them: the title (with `notion.title_prefix`), `notion.fixed_properties`, the status from `notion.status_values`, and the tags as a JSON-array string such as `"[\"Infra\", \"Kubernetes\"]"`.
  - Page icon: `notion.page_icon`, or none when it is empty.
  - Notion on in the options but no Notion tools in this session: say once that this session cannot sync, set `notion_pending=true` after each write, and carry on. The next session with Notion catches up.
- **Notion comments:** every reply Claude posts starts with `[sdd]`, so a later review can tell answered threads apart. Never resolve or delete a comment; the person who wrote it resolves it.
- **Tags:** when Notion is on and `notion.tags` lists the database's options, pick only from that list. Otherwise suggest 2 to 4 short tags that fit the design.
- **What runs today:** for an existing system, take it from the repo (Helm charts, Terraform, Kubernetes manifests, CI and deploy configuration) or ask the user. The plugin never runs cloud CLIs such as `aws` or `kubectl`.

## Files

- **Location:** inside a git repo, `<repo root>/docs/sdd/<slug>.md`. Otherwise `~/sdd/<slug>.md`.
- **Slug:** kebab-case from the title, a to z, 0 to 9 and hyphens, at most 40 characters.
- **Source of truth:** the markdown file. The Notion page is a copy regenerated on every sync, so edits made in Notion are overwritten (the drift check in `sync.md` catches them first).
- **Git:** never commit or push. The user commits.
- **Front matter keys:** title, slug, kind (new, existing, change), version, status (draft, published), author, organization, created, updated, tags, links, notion_page_id, notion_last_sync, notion_pending, review_url (the review page, see `core/review.md` part 6). Change them with `S meta <file> --set key=value`, never by hand.
- **Section bodies:** write them with `S section <file> <id> --write` and a heredoc. It replaces everything between the section heading and the next heading of the same or higher level, template comments included, and keeps the heading line.

## IDs

- Requirements: `R1`, `R2` and so on, in the 1.6 table. When the repo already defines IDs (for example `SEL-001` in `specs/`), use those.
- Views: `V1`, `V2` and so on, as `### V<n> <Viewpoint>: <title>` in Section 3.
- Decisions: `ADR-001`, `ADR-002` and so on, as `### ADR-<nnn> <title>` in Section 4.

## Section states (computed by `S status`)

- **todo:** the body is empty or still exactly the template's.
- **done:** the body has content.
- **skipped:** the body has a `**TODO:** <what is missing>` line.
- **na:** the body is `_Not applicable: <reason>_`.

## Writing rules for anything that goes into the SDD

`S lint` enforces the mechanical rules (em-dash, diagram direction, placeholders, emoji, traceability). These are the judgment rules:

1. **Concrete.** Real names, numbers, paths, commands and versions. "p95 under 300 ms at 50 requests per second", not "fast".
2. **Never invent facts.** A number, owner, name or link you do not know is written as `{{what is needed}}`, for example `{{p95 latency target}}`. Lint blocks publishing until it is filled. Put placeholders in plain text where you can. Lint also catches multi-word ones inside inline code and diagram labels, but it skips anything that looks like a Helm or Go template (`{{ .Values.x }}`), so `{{x}}` written that way is not caught.
3. **Plain sentences.** One idea per bullet. No metaphors, no filler, no em-dash: use a period, comma, colon or parentheses.
4. **Template length hints:** 1.1 is 2 to 4 sentences, 1.2 is one purpose sentence plus in and out lists, 1.5 is 3 to 5 sentences.
5. **No emoji in the file.** Heading marks, when the options set any, are added by `S render` on the way to Notion.
6. **Diagrams:** mermaid, `flowchart TB` for flowcharts, quoted labels when they hold punctuation, `<br>` for a line break inside a label. See `viewpoints.md`.
7. **Tables:** normal pipe tables in the file. `S render` turns them into Notion tables.
8. **Lists:** nested bullets are indented with 2 spaces. Soft-wrapped lines are fine; render joins them.

## Question screens (AskUserQuestion)

- 1 to 4 questions per screen, 2 to 4 options per question. The tool always adds "Other" for free text, so never add your own "Other".
- `header`: at most 12 characters.
- `preview`: only on single-select questions. Use it to show the exact markdown a draft will write.
- `multiSelect` for picking several items: viewpoints, glossary terms, ADRs to keep, tags, normative references.
- The user can attach notes to a pick. Treat notes as edit instructions for that pick.
- An answer typed into Other is one of three things: a question (answer it, then show the same screen again), their own text (clean it up to the writing rules, show it, ask before writing), or "pause".
