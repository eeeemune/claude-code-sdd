# SDD Planner: Software Design Descriptions in Claude Code

`sdd-planner` helps you write a Software Design Description (IEEE 1016, using the [jam01 SDD template](https://github.com/jam01/SDD-Template)) one section at a time, with Claude as the guide. Each section starts with a short card on what it is and why it matters. Claude then drafts two or three concrete options from your description and your repo, and you pick one. Every requirement gets an acceptance check, every design view names the requirements it implements, and every design choice becomes a decision record, so you end up with a spec you can build against. The SDD is a plain markdown file in your repo. Notion sync is optional.

## Demo

This plugin was designed with itself. Below is the review page for the SDD of its own public release, right after Claude acted on the first round of feedback: green parts are approved, and blue parts were changed by Claude and wait for a re-check, each with a line saying what changed.

![The review page for this plugin's own release SDD after the first round of fixes: 13 parts approved, 12 waiting for a re-check](docs/review-page-recheck.png)

## Install

```bash
claude plugin marketplace add eeeemune/claude-code-sdd
claude plugin install sdd-planner@claude-code-sdd
```

**Requires:** Claude Code, and Python 3.9 or newer as `python3` (macOS includes it). The review page also needs Claude Code's claude.ai Artifact tools. Tested on macOS. The commands are built for Claude Code: they run a local Python helper and write files, which claude.ai chat and Cowork may not allow.

## Commands

| Command | What it does |
|---------|--------------|
| `/sdd-planner:write` | Starts a new SDD or resumes a draft, one section per turn: the card, two or three drafts to pick from, then the pick is written to the file. |
| `/sdd-planner:review` | Reviews the SDD on a private claude.ai review page: plain-language notes, a diagram walk-through, Claude's check of each part, Approve or Needs changes, comments and suggested edits. Run it again and Claude acts on the feedback. `/sdd-planner:review walk` reviews in the terminal; `/sdd-planner:review notion` acts on comments on the Notion page. |
| `/sdd-planner:publish` | Lints the SDD, bumps its version (the first publish is 1.0), adds a Revision History row, and, when Notion is on, syncs the page and reads it back to verify it. |

## What it runs and sends

- **On your machine:** the commands run the plugin's helper, `python3 scripts/sdd.py`, which uses the Python standard library only and makes no network calls. It creates, checks and renders the SDD file. The SDD is written to `docs/sdd/` in the current git repo, or to `~/sdd/`. Claude reads the plugin options Claude Code stores for it, `git config user.name`, and, to draft sections, files in the current repo such as READMEs, manifests, and CI and deploy configuration.
- **Links you give it:** read with the connectors your session already has, such as Notion, Slack or Asana. Nothing is written to them, apart from Notion as described next.
- **Notion, only when your options name a database:** creates and updates the SDD's page in that database, and reads and replies to comments on it, through your own Notion connection.
- **claude.ai review page, with `/sdd-planner:review`:** publishes the SDD's text and Claude's notes as a private page in your claude.ai account, and reads the verdicts, suggested edits and comments saved on it. The page's Ask box sends one part of the SDD and your question to Claude. Only you, and people you share the page with, can open it. The page loads its fonts from Google Fonts.
- **Nothing else:** no cloud CLIs such as `aws` or `kubectl`, no telemetry, and no other network calls.

## Options

Everything works without options, with Notion sync off. To sync to Notion or set an organization, run `/plugin configure sdd-planner@claude-code-sdd`, then start a new session. The [repository README](https://github.com/eeeemune/claude-code-sdd#options) lists every option.

## License

MIT. The SDD template is jam01/SDD-Template, dedicated to the public domain under CC0 1.0.
