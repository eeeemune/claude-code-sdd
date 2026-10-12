#!/usr/bin/env python3
"""Deterministic helper for the /sdd skill.

Commands (JSON output unless noted):
  new      create an SDD file from core/template.md
  status   state of every section and the next one in writing order
  lint     findings, exit 1 on errors; --fix rewrites LR/RL diagrams to TB
  settings the user's settings merged with the defaults; exit 1 when the file is broken
  render   Notion-flavored markdown (stdout, not JSON)
  props    Notion page properties
  meta     read front matter, or update keys with --set k=v
  section  print one section's body, or replace it from stdin with --write
  release  bump the version, mark published, add a Revision History row
  locate   which section a piece of Notion block text belongs to (exit 3 when nothing matches)
  review-data  the facts the guided review page shows (JSON)
  review-page  build the guided review page as HTML, for publishing as an artifact
  review-notes    the notes embedded in a published review page (JSON)
  review-changed  entries whose text changed since a review page was built (JSON)

Standard library only, Python 3.9+. Run any command with --help for its options.
"""
from __future__ import annotations

import argparse
import html as html_lib
import datetime as dt
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "core" / "template.md"

# The order sections are written in. Reading order is the document order.
WALK_ORDER = ["1.2", "1.6", "1.1", "2.1", "2.2", "3", "4", "5", "1.4", "1.3", "1.5"]
KINDS = ("new", "existing", "change")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EM_DASH = "\u2014"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
REV_HEADER_RE = re.compile(r"^\|\s*Name\s*\|\s*Date\s*\|\s*Reason For Changes\s*\|\s*Version\s*\|$")
LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]+\}\}")
# Inside inline code, only flag what looks like our placeholders ("{{preview domain}}"): starts with a letter,
# has a space, no "." or "$". That skips Helm/Go templates ({{ .Values.x }}, {{range .Items}}, {{- end }}).
CODE_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z][^{}.$\n]*\s[^{}.$\n]*)\}\}")
# Same inside fenced code, except right after a node id: mermaid's hexagon shape is id{{label}}.
FENCED_PLACEHOLDER_RE = re.compile(r"(?<![\w\])])\{\{([A-Za-z][^{}.$\n]*\s[^{}.$\n]*)\}\}")
GO_KEYWORD_RE = re.compile(r"^(end|else|if|range|with|define|template|block|break|continue|include)\b")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")
VAGUE_RE = re.compile(r"\b(scalable|robust|seamless(?:ly)?|efficient(?:ly)?|fast|flexible)\b", re.IGNORECASE)
ID_RE = re.compile(r"^[A-Za-z]+-?\d+$")


class SddError(Exception):
    pass


# ---------------------------------------------------------------- front matter

def split_front_matter(text: str) -> tuple[list[str], str]:
    """(front matter lines without the --- fences, body). No front matter: ([], text)."""
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 3)
    if end == -1:
        return [], text
    return text[4:end].split("\n"), text[end + 5:]


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [item.strip() for item in inner.split(",") if item.strip()] if inner else []
    return raw


def parse_front_matter(text: str) -> dict:
    lines, _ = split_front_matter(text)
    data = {}
    for line in lines:
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            data[key.strip()] = _parse_value(value)
    return data


def _format_value(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    return str(value)


def set_front_matter(text: str, updates: dict) -> str:
    """Change only the named keys; append keys that do not exist yet. The body is untouched."""
    lines, body = split_front_matter(text)
    if not text.startswith("---\n"):
        raise SddError("file has no front matter")
    lines = list(lines)
    for key, value in updates.items():
        rendered = f"{key}: {_format_value(value)}".rstrip()
        for i, line in enumerate(lines):
            if line.partition(":")[0].strip() == key:
                lines[i] = rendered
                break
        else:
            lines.append(rendered)
    return "---\n" + "\n".join(lines) + "\n---\n" + body


# ---------------------------------------------------------------- line model

def _strip_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    out, i = [], 0
    while i < len(line):
        if in_comment:
            end = line.find("-->", i)
            if end == -1:
                return "".join(out), True
            i, in_comment = end + 3, False
        else:
            start = line.find("<!--", i)
            if start == -1:
                out.append(line[i:])
                break
            out.append(line[i:start])
            i, in_comment = start + 4, True
    return "".join(out), in_comment


def classify(lines: list[str]) -> list[tuple[str, str]]:
    """Per line: (text with HTML comments removed, kind) where kind is fm, code or text."""
    result: list[tuple[str, str]] = []
    i = 0
    if lines and lines[0] == "---":
        for j in range(1, len(lines)):
            if lines[j] == "---":
                result = [(line, "fm") for line in lines[: j + 1]]
                i = j + 1
                break
    in_code, fence, in_comment = False, "", False
    for line in lines[i:]:
        stripped = line.lstrip()
        if in_code:
            result.append((line, "code"))
            if stripped.startswith(fence) and stripped.strip().strip(fence[0]) == "":
                in_code = False
            continue
        if not in_comment and stripped.startswith(("```", "~~~")):
            in_code, fence = True, stripped[:3]
            result.append((line, "code"))
            continue
        cleaned, in_comment = _strip_comments(line, in_comment)
        result.append((cleaned, "text"))
    return result


def _headings(cls) -> list[tuple[int, int, str]]:
    """(index, level, title) for real headings: not in code, not inside comments."""
    out = []
    for i, (text, kind) in enumerate(cls):
        if kind == "text":
            m = HEADING_RE.match(text)
            if m:
                out.append((i, len(m.group(1)), m.group(2)))
    return out


def section_span(cls, sid: str):
    """(heading index, body start, body end) of section `sid` (levels 2 and 3), or None."""
    heads = _headings(cls)
    for n, (i, level, title) in enumerate(heads):
        m = SECTION_RE.match(title)
        if m and m.group(1) == sid and level in (2, 3):
            end = len(cls)
            for j, level2, _ in heads[n + 1:]:
                if level2 <= level:
                    end = j
                    break
            return i, i + 1, end
    return None


def _normalized(cls_slice) -> str:
    return "\n".join(text.strip() for text, _ in cls_slice if text.strip())


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, i = [], [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if s[i] == "|":
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(s[i])
        i += 1
    cells.append("".join(buf).strip())
    return cells


def _is_table_start(cls, i: int) -> bool:
    return (
        cls[i][1] == "text" and cls[i][0].lstrip().startswith("|")
        and i + 1 < len(cls) and cls[i + 1][1] == "text" and TABLE_SEP_RE.match(cls[i + 1][0]) is not None
    )


def _table_at(cls, i: int) -> tuple[list[tuple[int, list[str]]], int]:
    """Rows (index, cells) of the table starting at i, header first, separator skipped; and the end index."""
    rows = [(i, _split_row(cls[i][0]))]
    j = i + 2
    while j < len(cls) and cls[j][1] == "text" and cls[j][0].lstrip().startswith("|"):
        rows.append((j, _split_row(cls[j][0])))
        j += 1
    return rows, j


# ---------------------------------------------------------------- status

def section_state(body: str, template_body: str) -> str:
    if not body or body == template_body:
        return "todo"
    if re.search(r"(?m)^\*\*TODO:\*\*", body):
        return "skipped"
    if body.startswith("_Not applicable"):
        return "na"
    return "done"


def _pending_views(cls) -> list[str]:
    """Viewpoints picked in 2.2 that have neither a view in Section 3 nor a TODO line naming them."""
    span = section_span(cls, "3")
    body = _normalized(cls[span[1]:span[2]]) if span else ""
    todo = " ".join(line.lower() for line in body.split("\n") if line.startswith("**TODO:**"))
    covered = {view["viewpoint"] for view in _views(cls) if view["viewpoint"]}
    return [name for _, name in _kept_viewpoints(cls) if name not in covered and name not in todo]


def status(text: str, template_text: str | None = None) -> dict:
    if template_text is None:
        template_text = TEMPLATE.read_text(encoding="utf-8")
    t_cls = classify(template_text.split("\n"))
    cls = classify(text.split("\n"))
    fm = parse_front_matter(text)
    pending_views = _pending_views(cls)
    sections = []
    for sid in WALK_ORDER:
        span = section_span(cls, sid)
        if span is None:
            sections.append({"id": sid, "title": "", "state": "missing", "line": None})
            continue
        title = SECTION_RE.match(HEADING_RE.match(cls[span[0]][0]).group(2)).group(2)
        t_span = section_span(t_cls, sid)
        t_body = _normalized(t_cls[t_span[1]:t_span[2]]) if t_span else ""
        body = _normalized(cls[span[1]:span[2]])
        state = section_state(body, t_body)
        if sid == "3" and pending_views:
            state = "todo"  # written one view per turn: not done until every picked viewpoint is covered
        if sid == "4" and state == "done":
            statuses = re.findall(r"(?m)^-\s*\*\*Status:\*\*\s*(\w+)", body)
            if statuses and all(s.lower() == "proposed" for s in statuses):
                state = "todo"  # proposed ADRs collected earlier still wait for the step 7 review
        sections.append({"id": sid, "title": title, "state": state, "line": span[0] + 1})
    todo = [s["id"] for s in sections if s["state"] == "todo"]
    skipped = [s["id"] for s in sections if s["state"] == "skipped"]
    return {
        "title": fm.get("title", ""),
        "status": fm.get("status", ""),
        "version": fm.get("version", ""),
        "sections": sections,
        "done": sum(1 for s in sections if s["state"] in ("done", "na")),
        "total": len(WALK_ORDER),
        "next": todo[0] if todo else (skipped[0] if skipped else None),
        "skipped": skipped,
        "missing": [s["id"] for s in sections if s["state"] == "missing"],
        "pending_views": pending_views,
    }


# ---------------------------------------------------------------- sections

def replace_section_body(text: str, sid: str, body: str) -> str:
    lines = text.split("\n")
    span = section_span(classify(lines), sid)
    if span is None:
        raise SddError(f"no section {sid} in this file")
    _, start, end = span
    new_body = body.strip("\n").split("\n") if body.strip() else []
    if end >= len(lines):
        return "\n".join(lines[:start] + new_body + [""])
    return "\n".join(lines[:start] + new_body + [""] + lines[end:])


def section_body(text: str, sid: str) -> str:
    lines = text.split("\n")
    span = section_span(classify(lines), sid)
    if span is None:
        raise SddError(f"no section {sid} in this file")
    body = lines[span[1]:span[2]]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n" if body else ""


# ---------------------------------------------------------------- locate

def _tokens(s: str) -> str:
    """Plain lowercase words: links reduced to their text; markdown, escapes and emoji dropped."""
    s = LINK_RE.sub(lambda m: m.group(1), s)
    return " ".join(re.findall(r"[a-z0-9]+", s.lower()))


def _line_sections(cls) -> list:
    """For every line: (walk section id, V/ADR record id), or (None, None) outside the sections."""
    where = [(None, None)] * len(cls)
    for sid in WALK_ORDER:
        span = section_span(cls, sid)
        if not span:
            continue
        for k in range(span[0], span[2]):
            where[k] = (sid, None)
        if sid in ("3", "4"):
            for i, end, title in _records(cls, span):
                for k in range(i, end):
                    where[k] = (sid, title.split()[0])
    return where


def locate(text: str, snippet: str, threshold: float = 0.6) -> dict | None:
    """Which section (and view or ADR) a piece of Notion block text comes from. None when nothing matches well."""
    want = _tokens(snippet)
    if not want:
        return None
    cls = classify(text.split("\n"))
    where = _line_sections(cls)
    units: list[tuple[int, str]] = []
    paragraph: list[int] = []
    code: list[int] = []

    def close(run: list[int]) -> None:
        if len(run) > 1:
            units.append((run[0], _tokens(" ".join(cls[k][0] for k in run))))
        run.clear()

    for k, (line, kind) in enumerate(cls):
        if kind == "fm":
            continue
        if kind == "code":
            close(paragraph)
            code.append(k)
        else:
            close(code)
            if not line.strip() or HEADING_RE.match(line):
                close(paragraph)
            else:
                paragraph.append(k)
        tokens = _tokens(line)
        if tokens:
            units.append((k, tokens))
    close(paragraph)
    close(code)

    best = None
    padded = f" {want} "
    for index, tokens in units:
        if padded in f" {tokens} ":
            score = 1.0
        else:
            matcher = SequenceMatcher(None, want, tokens)
            floor = best[0][0] if best else 0.0
            if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
                continue
            score = matcher.ratio()
        # Equal scores: prefer text inside a section (the title block and TOC never reach Notion), then the shortest.
        key = (score, where[index][0] is not None, -len(tokens))
        if best is None or key > best[0]:
            best = (key, index)
    if best is None or best[0][0] < threshold:
        return None
    section, record = where[best[1]]
    return {"section": section, "record": record, "line": best[1] + 1, "score": round(best[0][0], 2)}


# ---------------------------------------------------------------- lint

def _prose(text: str) -> str:
    return INLINE_CODE_RE.sub(" ", text)


def _unquoted_parens(line: str) -> bool:
    pattern = r'\w\[(?!["\[(])([^\]]*)\]|\w\{(?![{"])([^}]*)\}|\|(?!")([^|]*)\|'
    for m in re.finditer(pattern, line):
        label = next(g for g in m.groups() if g is not None)
        if "(" in label or ")" in label:
            return True
    return False


def _records(cls, span, level: int = 3) -> list[tuple[int, int, str]]:
    """(heading index, end index, title) for headings of `level` inside a section span."""
    heads = [(i, title) for i, lvl, title in _headings(cls) if span[1] <= i < span[2] and lvl == level]
    out = []
    for n, (i, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else span[2]
        out.append((i, end, title))
    return out


def _views(cls) -> list[dict]:
    """The V-records in Section 3 with their Viewpoint and Implements lines."""
    span = section_span(cls, "3")
    views = []
    if not span:
        return views
    for i, end, title in _records(cls, span):
        view = {"index": i, "end": end, "title": title, "viewpoint": None, "viewpoint_name": "",
                "implements": None, "implements_index": None, "decisions": []}
        for j in range(i + 1, end):
            line, kind = cls[j]
            if kind != "text":
                continue
            m = re.match(r"^\s*-\s*\*\*Viewpoint:\*\*\s*(.+)$", line)
            if m:
                view["viewpoint_name"] = m.group(1).split("(")[0].strip()
                view["viewpoint"] = view["viewpoint_name"].lower()
            m = re.match(r"^\s*-\s*\*\*Decisions:\*\*\s*(.*)$", line)
            if m:
                view["decisions"] = re.findall(r"ADR-\d+", m.group(1))
            m = re.match(r"^\s*-\s*\*\*Implements:\*\*\s*(.*)$", line)
            if m:
                view["implements"] = [t for t in re.split(r"[,\s]+", m.group(1)) if ID_RE.match(t)]
                view["implements_index"] = j
        views.append(view)
    return views


def _kept_viewpoints(cls) -> list[tuple[int, str]]:
    """(heading index, lowercase name) of the 2.2.x subsections that have content."""
    span = section_span(cls, "2.2")
    kept = []
    if not span:
        return kept
    for i, end, title in _records(cls, span, level=4):
        if any(cls[j][0].strip() for j in range(i + 1, end)):
            m = SECTION_RE.match(title)
            kept.append((i, (m.group(2) if m else title).strip().lower()))
    return kept


def lint(text: str) -> list[dict]:
    lines = text.split("\n")
    cls = classify(lines)
    findings: list[dict] = []

    def add(rule: str, level: str, index: int, message: str) -> None:
        findings.append({"rule": rule, "level": level, "line": index + 1, "message": message})

    # Line rules.
    mermaid, mermaid_kind = False, None
    for i, (line, kind) in enumerate(cls):
        if kind == "fm":
            continue
        if kind == "code":
            s = lines[i].strip()
            if s.startswith(("```", "~~~")):
                if not mermaid and s[3:].strip().lower() == "mermaid":
                    mermaid, mermaid_kind = True, None
                elif mermaid and s.strip("`~") == "":
                    mermaid = False
                continue
            if mermaid:
                if mermaid_kind is None and s:
                    mermaid_kind = s.split()[0]
                if re.match(r"^(flowchart|graph)\s+(LR|RL)\b", s) or re.match(r"^direction\s+(LR|RL)\b", s):
                    add("mermaid-direction", "error", i, "diagram must run top to bottom (TB)")
                if mermaid_kind in ("flowchart", "graph") and _unquoted_parens(s):
                    add("mermaid-label-parens", "warning", i, 'quote labels that contain parentheses: a["label (x)"]')
            for m in FENCED_PLACEHOLDER_RE.finditer(lines[i]):
                if not GO_KEYWORD_RE.match(m.group(1)):
                    add("placeholder", "error", i, f"unfilled placeholder {m.group(0)}")
            continue
        prose = _prose(line)
        if EM_DASH in prose:
            add("em-dash", "error", i, "replace the em-dash with a period, comma, colon or parentheses")
        found = [m.group(0) for m in PLACEHOLDER_RE.finditer(prose)]
        for span in INLINE_CODE_RE.finditer(line):
            found += [m.group(0) for m in CODE_PLACEHOLDER_RE.finditer(span.group(2))
                      if not GO_KEYWORD_RE.match(m.group(1))]
        for placeholder in found:
            add("placeholder", "error", i, f"unfilled placeholder {placeholder}")
        if EMOJI_RE.search(prose):
            add("emoji", "warning", i, "no emoji in the SDD file (Notion hearts are added by render)")
        if re.match(r"^\s*\*\*TODO:\*\*", line):
            add("todo", "warning", i, "open TODO")
        for sentence in re.split(r"(?<=[.!?])\s+", prose):
            vague = VAGUE_RE.search(sentence)
            if vague and not re.search(r"\d", sentence):
                add("vague-word", "info", i, f'"{vague.group(1)}" with no number in the same sentence')
                break

    # Requirements (1.6).
    req_ids: dict[str, int] = {}
    span = section_span(cls, "1.6")
    if span:
        for i in range(span[1], span[2]):
            if _is_table_start(cls, i):
                rows, _ = _table_at(cls, i)
                for index, cells in rows[1:]:
                    rid = cells[0].strip("*` ") if cells else ""
                    if not rid:
                        continue
                    req_ids[rid] = index
                    if len(cells) < 3 or not cells[-1].strip():
                        add("req-no-check", "error", index, f"{rid} has no acceptance check")
                break

    # Views (Section 3).
    views = _views(cls)
    for view in views:
        if view["implements"] is None:
            add("view-no-implements", "warning", view["index"], f"{view['title']} has no Implements line")
            continue
        for rid in view["implements"]:
            if rid not in req_ids:
                add("req-unknown", "error", view["implements_index"], f"{rid} is not in the 1.6 table")
    cited = {rid for view in views for rid in (view["implements"] or [])}
    for rid, index in req_ids.items():
        if rid not in cited:
            add("req-orphan", "warning", index, f"no view implements {rid}")

    # Viewpoints picked in 2.2 but never used by a view.
    if views:
        used = {view["viewpoint"] for view in views if view["viewpoint"]}
        for i, name in _kept_viewpoints(cls):
            if name not in used:
                add("viewpoint-unused", "warning", i, f"viewpoint {name} has no view in Section 3")

    # Decisions (Section 4).
    span = section_span(cls, "4")
    if span:
        for i, end, title in _records(cls, span):
            status_value, status_index, has_outcome, options = None, None, False, None
            for j in range(i + 1, end):
                line, kind = cls[j]
                if kind != "text":
                    continue
                m = re.match(r"^\s*-\s*\*\*Status:\*\*\s*(.*)$", line)
                if m:
                    status_value, status_index = m.group(1).strip().lower(), j
                if re.match(r"^\s*-\s*\*\*Outcome:\*\*\s*\S", line):
                    has_outcome = True
                m = re.match(r"^(\s*)-\s*\*\*Options:\*\*\s*(.*)$", line)
                if m:
                    indent = len(m.group(1))
                    count = len([p for p in m.group(2).split(";") if p.strip()])
                    for k in range(j + 1, end):
                        mk = re.match(r"^(\s*)[-*+]\s+\S", cls[k][0])
                        if not mk or len(mk.group(1)) <= indent:
                            break
                        count += 1
                    options = count
            if status_value and "proposed" in status_value:
                add("adr-proposed", "warning", status_index, f"{title} is still proposed")
            if options is None or options < 2 or not has_outcome:
                add("decision-incomplete", "warning", i, f"{title} needs at least two options and an outcome")

    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return findings


def fix(text: str) -> str:
    """Rewrite mermaid LR/RL directions to TB. Nothing else changes."""
    lines = text.split("\n")
    mermaid = False
    for i, (_, kind) in enumerate(classify(lines)):
        if kind != "code":
            continue
        s = lines[i].strip()
        if s.startswith(("```", "~~~")):
            if not mermaid and s[3:].strip().lower() == "mermaid":
                mermaid = True
            elif mermaid and s.strip("`~") == "":
                mermaid = False
            continue
        if mermaid:
            lines[i] = re.sub(r"^(\s*)(flowchart|graph)(\s+)(LR|RL)\b", r"\1\2\3TB", lines[i])
            lines[i] = re.sub(r"^(\s*)direction(\s+)(LR|RL)\b", r"\1direction\2TB", lines[i])
    return "\n".join(lines)


# ---------------------------------------------------------------- render

def escape_inline(s: str) -> str:
    """Escape Notion's special characters in prose. Inline code and link targets stay as they are."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "`":
            j = i
            while j < n and s[j] == "`":
                j += 1
            ticks = s[i:j]
            end = s.find(ticks, j)
            if end != -1:
                out.append(s[i:end + len(ticks)])
                i = end + len(ticks)
            else:
                out.append(ticks)
                i = j
            continue
        if c == "[":
            m = LINK_RE.match(s, i)
            if m:
                out.append("[" + escape_inline(m.group(1)) + "](" + m.group(2) + ")")
                i = m.end()
            else:
                out.append("\\[")
                i += 1
            continue
        if c == "~":
            if s.startswith("~~", i):
                out.append("~~")
                i += 2
            else:
                out.append("\\~")
                i += 1
            continue
        if c in "\\<>{}|$^]":
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _indent_unit(cls) -> int:
    widths = []
    for text, kind in cls:
        if kind == "text":
            m = LIST_RE.match(text)
            if m and m.group(1):
                widths.append(len(m.group(1).expandtabs(4)))
    return min(widths) if widths else 2


def _starts_block(text: str) -> bool:
    s = text.lstrip()
    return bool(HEADING_RE.match(text) or LIST_RE.match(text) or s.startswith(("|", ">", "**TODO:**")))


def _join(parts: list[str], br: str = "<br>") -> str:
    joined = ""
    for n, part in enumerate(parts):
        if n == 0:
            joined = part.strip()
        else:
            sep = br if parts[n - 1].endswith("  ") else " "
            joined += sep + part.strip()
    return joined


def default_source_label(path: Path) -> str:
    path = path.resolve()
    for parent in [path.parent, *path.parent.parents]:
        if (parent / ".git").exists():
            return f"{parent.name}/{path.relative_to(parent).as_posix()}"
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return path.as_posix()


GUIDE_SECTIONS = ROOT / "core" / "sections.md"
GUIDE_VIEWPOINTS = ROOT / "core" / "viewpoints.md"


def load_guide() -> dict:
    """The About-note text for each section and viewpoint, read from core/sections.md and core/viewpoints.md."""
    guide: dict = {"sections": {}, "viewpoints": {}}
    fields = {"sections": {"What it is": "what", "Look for": "look_for"}, "viewpoints": {"Answers": "answers"}}
    sources = (("sections", GUIDE_SECTIONS, r"^## (\d+(?:\.\d+)*) \S"),
               ("viewpoints", GUIDE_VIEWPOINTS, r"^## 2\.2\.\d+ (.+)$"))
    for kind, path, heading in sources:
        current = None
        for line in path.read_text(encoding="utf-8").split("\n"):
            m = re.match(heading, line)
            if m:
                key = m.group(1).strip()
                key = key.lower() if kind == "viewpoints" else key
                current = guide[kind].setdefault(key, {name: "" for name in fields[kind].values()})
                continue
            if line.startswith("## "):
                current = None
            elif current is not None:
                m = re.match(r"^- \*\*([^*]+):\*\* (.+)$", line)
                if m and m.group(1) in fields[kind]:
                    current[fields[kind][m.group(1)]] = m.group(2).strip()
    return guide


def _about(title: str, guide: dict) -> str | None:
    """The About note for a section, view or decision heading; None when the guide has nothing for it."""
    sections = guide.get("sections", {})
    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s", title)
    if m:
        s = sections.get(m.group(1), {})
        if s.get("what") and s.get("look_for"):
            return f"**About this section:** {escape_inline(s['what'])} **Look for:** {escape_inline(s['look_for'])}"
        return None
    m = re.match(r"^V\d+\s+(.+?):", title)
    if m:
        name = m.group(1).strip()
        answers = guide.get("viewpoints", {}).get(name.lower(), {}).get("answers")
        look_for = sections.get("3", {}).get("look_for")
        if answers and look_for:
            return (f"**About this view:** {escape_inline(name)} views answer: {escape_inline(answers)} "
                    f"**Look for:** {escape_inline(look_for)}")
        return None
    if re.match(r"^ADR-\d+", title):
        s = sections.get("4", {})
        if s.get("what") and s.get("look_for"):
            return f"**About this record:** {escape_inline(s['what'])} **Look for:** {escape_inline(s['look_for'])}"
    return None


def render(text: str, source_label: str, guide: dict | None = None, settings: dict | None = None) -> str:
    if guide is None:
        guide = load_guide()
    marks = (settings or settings_from({}))["notion"]["heading_marks"]  # plain headings by default
    fm = parse_front_matter(text)
    lines = text.split("\n")
    cls = classify(lines)
    unit = _indent_unit(cls)
    label = "Published" if fm.get("status") == "published" else "Draft"
    out = [
        '<callout color="gray_bg">',
        f"\t**Version** {fm.get('version', '')} · **Status** {label} · "
        f"**Author** {escape_inline(str(fm.get('author', '')))} · **Updated** {fm.get('updated', '')}",
        f"\tGenerated from `{source_label}`. Edit that file, not this page: every sync rewrites the text here. Comments stay.",
        "\tTo review, open one section at a time and comment on any line.",
        "</callout>",
    ]
    toggle = False  # inside a section's toggle heading: every block is indented one tab

    def emit(line: str) -> None:
        out.append("\t" + line if toggle else line)

    i, n, skip = 0, len(lines), None
    while i < n:
        text_i, kind = cls[i]
        if kind == "fm":
            i += 1
            continue
        heading = HEADING_RE.match(text_i) if kind == "text" else None
        if skip is not None:
            if heading and not (skip == "title" and len(heading.group(1)) == 2 and heading.group(2).startswith("For ")):
                skip = None
            else:
                i += 1
                continue
        if kind == "code":
            lead = len(lines[i]) - len(lines[i].lstrip())
            prefix = "\t" * (lead // unit)
            while i < n and cls[i][1] == "code":
                raw = lines[i]
                emit(prefix + (raw[lead:] if raw[:lead].strip() == "" else raw.lstrip()))
                i += 1
            continue
        stripped = text_i.strip()
        if not stripped:
            i += 1
            continue
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            if level == 1 and title == "Software Design Description":
                skip = "title"
                i += 1
                continue
            if level == 2 and title == "Table of Contents":
                emit("<table_of_contents/>")
                skip = "toc"
                i += 1
                continue
            new_level = min(max(level - 1, 1), 3)
            mark = f"{marks[new_level - 1]} " if marks else ""
            heading_line = f"{'#' * new_level} {mark}{escape_inline(title)}"
            if new_level == 3:
                emit(heading_line)
            else:
                toggle = False
                if new_level == 1:
                    out.append(heading_line)
                else:
                    out.append(heading_line + ' {toggle="true"}')
                    toggle = True
                    about = _about(title, guide)
                    if about:
                        for part in ('<callout color="gray_bg">', "\t" + about, "</callout>"):
                            emit(part)
            i += 1
            continue
        if _is_table_start(cls, i):
            rows, i = _table_at(cls, i)
            emit('<table header-row="true">')
            for _, cells in rows:
                if not any(cells):
                    continue
                emit("\t<tr>")
                for cell in cells:
                    emit(f"\t\t<td>{escape_inline(cell)}</td>")
                emit("\t</tr>")
            emit("</table>")
            continue
        if stripped.startswith(">"):
            parts = []
            while i < n and cls[i][1] == "text" and cls[i][0].lstrip().startswith(">"):
                parts.append(escape_inline(re.sub(r"^\s*>\s?", "", cls[i][0]).strip()))
                i += 1
            emit("> " + "<br>".join(parts))
            continue
        # Paragraph, list item or TODO line: gather soft-wrapped continuation lines.
        parts = [text_i]
        j = i + 1
        while j < n and cls[j][1] == "text" and cls[j][0].strip() and not _starts_block(cls[j][0]):
            parts.append(cls[j][0])
            j += 1
        item = LIST_RE.match(text_i)
        if item:
            indent, marker, _ = item.groups()
            marker = "-" if marker in "*+" else marker.replace(")", ".")
            content = _join([item.group(3)] + parts[1:])
            task = re.match(r"^(\[[ xX]\]\s+)(.*)$", content)
            body = task.group(1) + escape_inline(task.group(2)) if task else escape_inline(content)
            emit("\t" * (len(indent.expandtabs(4)) // unit) + f"{marker} {body}")
        elif stripped.startswith("**TODO:**"):
            for part in ('<callout color="yellow_bg">', "\t" + escape_inline(_join(parts)), "</callout>"):
                emit(part)
        else:
            emit(escape_inline(_join(parts)))
        i = j
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- review data

READING_ORDER = ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "2.1", "2.2", "3", "4", "5"]


def _markdown(cls, start: int, end: int) -> str:
    """The lines between start and end with HTML comments removed, blank-line runs collapsed."""
    body = "\n".join(text for text, kind in cls[start:end] if kind != "fm").strip("\n")
    return re.sub(r"\n{3,}", "\n\n", body)


def review_data(text: str, guide: dict | None = None) -> dict:
    """The facts the review page shows: one entry per section, view and decision, in reading order."""
    if guide is None:
        guide = load_guide()
    fm = parse_front_matter(text)
    cls = classify(text.split("\n"))
    states = {s["id"]: s["state"] for s in status(text)["sections"]}
    findings = lint(text)
    views = {v["index"]: v for v in _views(cls)}
    sections = guide.get("sections", {})

    def found(start: int, end: int) -> list:
        return [f for f in findings if start <= f["line"] - 1 < end]

    entries = []
    for sid in READING_ORDER:
        span = section_span(cls, sid)
        if span is None:
            continue
        title = SECTION_RE.match(HEADING_RE.match(cls[span[0]][0]).group(2)).group(2)
        records = _records(cls, span) if sid in ("3", "4") else []
        if not records:
            s = sections.get(sid, {})
            entries.append({
                "id": sid, "title": title, "kind": "section", "parent": None, "state": states.get(sid),
                "markdown": _markdown(cls, span[1], span[2]), "findings": found(span[0], span[2]),
                "about": {"what": s.get("what", ""), "look_for": s.get("look_for", "")},
            })
            continue
        for i, end, record_title in records:
            rid, _, rest = record_title.partition(" ")
            entry = {
                "id": rid, "title": rest.strip(), "parent": sid, "state": states.get(sid),
                "markdown": _markdown(cls, i + 1, end), "findings": found(i, end),
            }
            if sid == "3":
                view = views.get(i, {})
                name = view.get("viewpoint_name", "")
                answers = guide.get("viewpoints", {}).get(name.lower(), {}).get("answers", "")
                entry.update({
                    "kind": "view", "viewpoint": name,
                    "implements": view.get("implements") or [], "decisions": view.get("decisions", []),
                    "about": {"what": f"{name} views answer: {answers}" if answers else "",
                              "look_for": sections.get("3", {}).get("look_for", "")},
                })
            else:
                status_line = next((m.group(1).lower() for k in range(i + 1, end)
                                    for m in [re.match(r"^\s*-\s*\*\*Status:\*\*\s*(\w+)", cls[k][0])] if m), "")
                entry.update({
                    "kind": "decision", "decision_status": status_line,
                    "about": {"what": sections.get("4", {}).get("what", ""),
                              "look_for": sections.get("4", {}).get("look_for", "")},
                })
            entries.append(entry)

    requirements = []
    span = section_span(cls, "1.6")
    if span:
        for k in range(span[1], span[2]):
            if _is_table_start(cls, k):
                rows, _ = _table_at(cls, k)
                for _, cells in rows[1:]:
                    rid = cells[0].strip("*` ") if cells else ""
                    if rid:
                        requirements.append({
                            "id": rid,
                            "text": cells[1] if len(cells) > 1 else "",
                            "check": cells[-1] if len(cells) > 2 else "",
                            "implemented_by": [v["title"].split()[0] for v in views.values()
                                               if rid in (v["implements"] or [])],
                        })
                break
    return {"title": fm.get("title", ""), "version": fm.get("version", ""), "status": fm.get("status", ""),
            "updated": fm.get("updated", ""), "entries": entries, "requirements": requirements}


# ---------------------------------------------------------------- review page

REVIEW_TEMPLATE = ROOT / "review-page" / "template.html"
URL_RE = re.compile(r"https?://[^\s<>()\x00]*[^\s<>()\x00.,;:]")


def _inline_html(s: str) -> str:
    """Inline markdown to HTML: code spans, links, bare URLs, bold, italic. Everything else is escaped."""
    kept: list[str] = []

    def keep(fragment: str) -> str:
        kept.append(fragment)
        return f"\x00{len(kept) - 1}\x00"

    def link(href: str, label: str) -> str:
        return f'<a href="{html_lib.escape(href)}" target="_blank" rel="noopener">{label}</a>'

    s = INLINE_CODE_RE.sub(lambda m: keep("<code>" + html_lib.escape(m.group(2), quote=False) + "</code>"), s)
    s = LINK_RE.sub(lambda m: keep(link(m.group(2), html_lib.escape(m.group(1), quote=False))), s)
    s = URL_RE.sub(lambda m: keep(link(m.group(0), html_lib.escape(m.group(0), quote=False))), s)
    s = html_lib.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], s)


def _list_html(items: list) -> str:
    """Nested <ul>/<ol> from (indent width, marker, text) items."""
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    for indent, marker, text in items:
        tag = "ol" if marker[0].isdigit() else "ul"
        if not stack or indent > stack[-1][0]:
            out.append(f"<{tag}>")
            stack.append((indent, tag))
        else:
            while len(stack) > 1 and indent < stack[-1][0]:
                out.append(f"</li></{stack.pop()[1]}>")
            out.append("</li>")
        out.append(f"<li>{_inline_html(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def md_to_html(markdown: str, heading_tag: str = "h3") -> str:
    """The markdown subset an SDD uses, as HTML. Mermaid fences become <pre class="mermaid">."""
    lines = markdown.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith(("```", "~~~")):
            fence, lang = stripped[:3], stripped[3:].strip().lower()
            lead = len(line) - len(line.lstrip())
            body, j = [], i + 1
            while j < n and not (lines[j].strip().startswith(fence) and lines[j].strip().strip(fence[0]) == ""):
                body.append(lines[j][lead:] if lines[j][:lead].strip() == "" else lines[j].lstrip())
                j += 1
            code = html_lib.escape("\n".join(body), quote=False)
            out.append(f'<pre class="mermaid">{code}</pre>' if lang == "mermaid" else f"<pre><code>{code}</code></pre>")
            i = j + 1
            continue
        heading = HEADING_RE.match(line)
        if heading:
            out.append(f"<{heading_tag}>{_inline_html(heading.group(2))}</{heading_tag}>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1]):
            header, j, rows = _split_row(line), i + 2, []
            while j < n and lines[j].lstrip().startswith("|"):
                cells = _split_row(lines[j])
                if any(cells):
                    rows.append(cells)
                j += 1
            head = "".join(f"<th>{_inline_html(c)}</th>" for c in header)
            body = "".join("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in row) + "</tr>" for row in rows)
            out.append(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
            i = j
            continue
        if LIST_RE.match(line):
            items, j = [], i
            while j < n:
                item = LIST_RE.match(lines[j])
                if item:
                    items.append([len(item.group(1).expandtabs(4)), item.group(2), item.group(3).strip()])
                elif lines[j].strip() and not _starts_block(lines[j]):
                    items[-1][2] += " " + lines[j].strip()
                else:
                    break
                j += 1
            out.append(_list_html(items))
            i = j
            continue
        if stripped.startswith(">"):
            parts, j = [], i
            while j < n and lines[j].lstrip().startswith(">"):
                parts.append(re.sub(r"^\s*>\s?", "", lines[j]).strip())
                j += 1
            out.append(f"<blockquote><p>{_inline_html(' '.join(parts))}</p></blockquote>")
            i = j
            continue
        parts, j = [line], i + 1
        while j < n and lines[j].strip() and not _starts_block(lines[j]) and not lines[j].strip().startswith(("```", "~~~")):
            parts.append(lines[j])
            j += 1
        text = _inline_html(_join(parts, "\x01")).replace("\x01", "<br>")
        out.append(f'<p class="todo">{text}</p>' if stripped.startswith("**TODO:**") else f"<p>{text}</p>")
        i = j
    return "\n".join(out)


def _slug(entry_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", entry_id).strip("-").lower()


def _anchor_id(entry_id: str) -> str:
    """The review card's anchor; the same part in the Original tab is d-<slug>."""
    return "s-" + _slug(entry_id)


def original_html(text: str) -> str:
    """The whole SDD as written, below the front matter, for the page's Original tab.

    Every section, view and decision becomes a part with the anchor d-<slug>, its status chip, a link to
    its review card, and a body marked data-sel for selecting text. The file's Table of Contents is left
    out: its links point at markdown anchors, and the page's index does the same job.
    """
    cls = classify(text.split("\n"))
    heads = _headings(cls)
    parts = {}
    for sid in READING_ORDER:
        span = section_span(cls, sid)
        if span is None:
            continue
        records = _records(cls, span) if sid in ("3", "4") else []
        if records:
            for i, end, record_title in records:
                parts[i] = (record_title.partition(" ")[0], end)
        else:
            parts[span[0]] = (sid, span[2])

    def esc(value) -> str:
        return html_lib.escape(str(value), quote=True)

    def text_block(start: int, end: int, heading_tag: str) -> str:
        body = _markdown(cls, start, end)
        return f'<div class="doc-text">{md_to_html(body, heading_tag)}</div>' if body.strip() else ""

    body_start = next((i for i, (_, kind) in enumerate(cls) if kind != "fm"), len(cls))
    out = [text_block(body_start, heads[0][0] if heads else len(cls), "h4")]
    n, after_title = 0, False
    while n < len(heads):
        i, level, title = heads[n]
        nxt = heads[n + 1][0] if n + 1 < len(heads) else len(cls)
        if i in parts:
            pid, end = parts[i]
            tag = 3 if level <= 2 else 4
            slug = _slug(pid)
            body = md_to_html(_markdown(cls, i + 1, end), f"h{min(6, tag + 1)}") or '<p class="empty">Nothing written here yet.</p>'
            out.append(
                f'<section class="doc-part" id="d-{slug}" data-id="{esc(pid)}">\n'
                f'<div class="doc-head"><h{tag} class="doc-h">{_inline_html(title)}</h{tag}>'
                f'<span class="chip" data-chip="{esc(pid)}">Open</span>'
                f'<a class="sg-count" data-sgcount="{esc(pid)}" href="#s-{slug}" hidden></a>'
                f'<a class="doc-review" href="#s-{slug}">Review</a></div>\n'
                f'<div class="doc-body" data-sel="{esc(pid)}">{body}</div>\n</section>'
            )
            while n < len(heads) and heads[n][0] < end:
                n += 1
            after_title = False
            continue
        if title.strip().lower() == "table of contents":
            n, after_title = n + 1, False
            continue
        if level == 1:
            out.append(f'<h2 class="doc-title">{_inline_html(title)}</h2>')
            after_title = True
        elif after_title and level == 2:
            out.append(f'<p class="doc-subtitle">{_inline_html(title)}</p>')
            after_title = False
        else:
            out.append(f'<h3 class="doc-chapter">{_inline_html(title)}</h3>')
            after_title = False
        out.append(text_block(i + 1, nxt, "h4"))
        n += 1
    return "\n".join(block for block in out if block)


def review_page(text: str, notes: dict, source_label: str, guide: dict | None = None) -> str:
    """The guided review page: every entry rendered as static HTML, ready to publish as an artifact."""
    data = review_data(text, guide)
    entries = data["entries"]

    def esc(value) -> str:
        return html_lib.escape(str(value), quote=True)

    kinds = {"section": "Section", "view": "View", "decision": "Decision"}
    nav, sections = [], []
    for k, e in enumerate(entries):
        anchor = _anchor_id(e["id"])
        nav.append(
            f'<li><a class="toc-link" href="#{anchor}"><span class="chip" data-chip="{esc(e["id"])}">Open</span>'
            f'<span class="toc-id">{esc(e["id"])}</span><span class="toc-title">{esc(e["title"])}</span></a></li>'
        )
        eyebrow = [f'<span class="id">{esc(e["id"])}</span>', kinds[e["kind"]]]
        if e["kind"] == "view":
            eyebrow.append(f'{esc(e["viewpoint"])} viewpoint')
            if e["implements"]:
                eyebrow.append("implements " + ", ".join(esc(r) for r in e["implements"]))
        if e["kind"] == "decision" and e.get("decision_status"):
            eyebrow.append(esc(e["decision_status"]))
        about = e.get("about", {})
        about_html = ""
        if about.get("what"):
            look = f' <strong>Look for:</strong> {_inline_html(about["look_for"])}' if about.get("look_for") else ""
            about_html = (f'<aside class="about"><p><strong>About this {kinds[e["kind"]].lower()}:</strong> '
                          f'{_inline_html(about["what"])}{look}</p></aside>')
        note = notes.get(e["id"], {}) if isinstance(notes, dict) else {}
        parts = []
        for key, label in (("in_short", "In short"), ("why_care", "Why you care"), ("connects", "How it connects")):
            if note.get(key):
                parts.append(f'<p><span class="label">{label}</span> {_inline_html(note[key])}</p>')
        if note.get("tour"):
            steps = "".join(f"<li>{_inline_html(step)}</li>" for step in note["tour"])
            parts.append(f'<div class="tour"><span class="label">Read the diagram, top to bottom</span><ol>{steps}</ol></div>')
        notes_html = f'<div class="notes">{"".join(parts)}</div>' if parts else ""
        check = note.get("check") or {}
        check_html = (f'<details class="check"><summary>Check yourself: {_inline_html(check["q"])}</summary>'
                      f'<p>{_inline_html(check.get("a", ""))}</p></details>') if check.get("q") else ""
        findings_html = ""
        if e["findings"]:
            rows = "".join(
                f'<li><span class="sev" data-level="{esc(f["level"])}">{esc(f["level"])}</span> {esc(f["message"])} '
                f'<span class="rule">{esc(f["rule"])}, line {f["line"]}</span></li>' for f in e["findings"]
            )
            findings_html = f'<div class="findings"><p class="label">What the checker found</p><ul>{rows}</ul></div>'
        if note.get("findings"):
            rows = "".join(f"<li>{_inline_html(item)}</li>" for item in note["findings"])
            findings_html += f'<div class="findings claude"><p class="label">What Claude found</p><ul>{rows}</ul></div>'
        nxt = entries[k + 1] if k + 1 < len(entries) else None
        next_html = (f'<a class="next" href="#{_anchor_id(nxt["id"])}">Next: {esc(nxt["id"])} {esc(nxt["title"])}</a>'
                     if nxt else '<p class="next done">That was the last part. Run /sdd:review in Claude Code to act on your verdicts.</p>')
        sections.append(f"""<section class="entry" id="{anchor}" data-id="{esc(e["id"])}">
<p class="eyebrow">{' <span class="dot">&middot;</span> '.join(eyebrow)}</p>
<h2>{esc(e["title"])}</h2>
{about_html}
{notes_html}
<p class="sdd-label"><span class="label">The SDD text</span><span class="sel-hint" hidden>Select words to comment or suggest an edit.</span><a class="to-original" href="#d-{_slug(e["id"])}">Read in the original document</a></p>
<div class="content" data-sel="{esc(e["id"])}">{md_to_html(e["markdown"]) or '<p class="empty">Nothing written here yet.</p>'}</div>
<div class="suggestions" id="sgl-{anchor}" hidden><p class="label">Suggested edits</p><ul></ul></div>
{findings_html}
{check_html}
<div class="ask" hidden>
<label for="ask-{anchor}">Ask about this part</label>
<div class="ask-row"><textarea id="ask-{anchor}" rows="2" placeholder="What does this mean? Why does it matter?"></textarea>
<div class="ask-buttons"><button type="button" class="btn" data-action="ask" data-id="{esc(e["id"])}">Ask</button>
<button type="button" class="btn quiet" data-action="stop" data-id="{esc(e["id"])}" hidden>Stop</button></div></div>
<div class="answer" aria-live="polite"></div>
</div>
<div class="verdict">
<div class="verdict-row">
<button type="button" class="btn approve" data-action="approve" data-id="{esc(e["id"])}">Approve</button>
<button type="button" class="btn changes" data-action="changes" data-id="{esc(e["id"])}">Needs changes</button>
<button type="button" class="btn quiet" data-action="comment" data-id="{esc(e["id"])}" hidden>Comment</button>
</div>
<div class="note-row" hidden>
<label for="note-{anchor}">What should change?</label>
<textarea id="note-{anchor}" rows="3"></textarea>
<div class="note-actions"><button type="button" class="btn changes" data-action="save-note" data-id="{esc(e["id"])}">Save</button>
<button type="button" class="btn quiet" data-action="cancel-note" data-id="{esc(e["id"])}">Cancel</button></div>
</div>
<p class="verdict-status" id="vs-{anchor}" aria-live="polite"></p>
</div>
{next_html}
</section>""")
    trace_rows = []
    views = {e["id"]: e for e in entries if e["kind"] == "view"}
    for r in data["requirements"]:
        decisions = sorted({d for v in r["implemented_by"] for d in views.get(v, {}).get("decisions", [])})
        trace_rows.append(
            f'<tr><td class="mono">{esc(r["id"])}</td><td>{_inline_html(r["text"])}</td>'
            f'<td class="mono">{esc(", ".join(r["implemented_by"]) or "none yet")}</td>'
            f'<td class="mono">{esc(", ".join(decisions) or "none")}</td></tr>'
        )
    trace = ('<div class="table-wrap"><table><thead><tr><th>Requirement</th><th>What it says</th>'
             '<th>Built by</th><th>Shaped by</th></tr></thead><tbody>' + "".join(trace_rows) + "</tbody></table></div>"
             ) if trace_rows else '<p class="empty">No requirements in 1.6 yet.</p>'
    payload = {"title": data["title"], "entries": [
        {"id": e["id"], "title": e["title"], "kind": e["kind"], "markdown": e["markdown"]} for e in entries],
        "notes": notes if isinstance(notes, dict) else {}}
    status_label = "Published" if data["status"] == "published" else "Draft"
    replacements = {
        "__SDD_TITLE__": esc(data["title"]),
        "__SDD_META__": f'SDD &middot; version {esc(data["version"])} &middot; {status_label} &middot; from <code>{esc(source_label)}</code>',
        "__SDD_TOTAL__": str(len(entries)),
        "<!--SDD:NAV-->": "\n".join(nav),
        "<!--SDD:SECTIONS-->": "\n".join(sections),
        "<!--SDD:TRACE-->": trace,
        "<!--SDD:ORIGINAL-->": original_html(text),
        "__SDD_DATA__": json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
    }
    page = REVIEW_TEMPLATE.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


PAGE_DATA_RE = re.compile(r'<script type="application/json" id="sdd-data">(.*?)</script>', re.S)


def page_notes(page: str) -> dict:
    """The notes a published review page was built with, so a later run can rebuild it without rewriting them."""
    m = PAGE_DATA_RE.search(page)
    if not m:
        raise SddError("not a review page: no sdd-data block")
    return json.loads(m.group(1)).get("notes", {})


def page_changes(page: str, text: str) -> dict:
    """Entries whose text differs between a published review page and the SDD file, so a refresh knows what to redo."""
    m = PAGE_DATA_RE.search(page)
    if not m:
        raise SddError("not a review page: no sdd-data block")
    before = {e["id"]: e["markdown"] for e in json.loads(m.group(1)).get("entries", [])}
    after = {e["id"]: e["markdown"] for e in review_data(text)["entries"]}
    return {
        "changed": [i for i in after if i in before and before[i] != after[i]],
        "added": [i for i in after if i not in before],
        "removed": [i for i in before if i not in after],
    }


# ---------------------------------------------------------------- settings

# Every key is optional. Without a "notion" block (or its data_source_id) Notion sync is off.
SETTINGS_DEFAULTS = {
    "organization": "",
    "notion": {
        "data_source_id": "",
        "title_property": "Name",
        "title_prefix": "",
        "status_property": "",
        "status_values": {},
        "tags_property": "",
        "tags": [],
        "fixed_properties": {},
        "heading_marks": [],
        "page_icon": "",
    },
}
_TYPE_NAMES = {str: "a string", list: "a list of strings", dict: "an object of strings"}


def config_dir() -> Path:
    """The Claude config folder: $CLAUDE_CONFIG_DIR, or ~/.claude when it is not set."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def _well_typed(value, default) -> bool:
    if not isinstance(value, type(default)):
        return False
    if isinstance(value, list):
        return all(isinstance(item, str) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    return True


def settings_from(raw) -> dict:
    """Merge a user's settings with the defaults. Unknown keys warn; a wrong type is an error, and errors turn Notion off."""
    out = json.loads(json.dumps(SETTINGS_DEFAULTS))
    warnings, errors = [], []
    if not isinstance(raw, dict):
        errors.append("the file must hold one JSON object")
        raw = {}
    for key, value in raw.items():
        default = SETTINGS_DEFAULTS.get(key)
        if default is None:
            warnings.append(f"unknown key '{key}' is ignored")
        elif isinstance(default, dict):
            if not isinstance(value, dict):
                errors.append(f"{key} must be an object")
                continue
            for name, item in value.items():
                if name not in default:
                    warnings.append(f"unknown key '{key}.{name}' is ignored")
                elif not _well_typed(item, default[name]):
                    errors.append(f"{key}.{name} must be {_TYPE_NAMES[type(default[name])]}")
                else:
                    out[key][name] = item
        elif not _well_typed(value, default):
            errors.append(f"{key} must be {_TYPE_NAMES[type(default)]}")
        else:
            out[key] = value
    if len(out["notion"]["heading_marks"]) not in (0, 3):
        errors.append("notion.heading_marks must list 3 marks, one per heading level, or none")
        out["notion"]["heading_marks"] = []
    out["notion_enabled"] = bool(out["notion"]["data_source_id"]) and not errors
    out["warnings"] = warnings
    out["error"] = "; ".join(errors) or None
    return out


def load_settings(folder: Path | None = None) -> dict:
    """Read <config>/sdd/settings.json. A missing file means the defaults; a broken one is reported and Notion is off."""
    path = (folder or config_dir()) / "sdd" / "settings.json"
    found = path.exists()
    if not found:
        merged = settings_from({})
    else:
        try:
            merged = settings_from(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as error:
            merged = settings_from({})
            merged["error"] = f"not valid JSON: {error.msg} at line {error.lineno}, column {error.colno}"
            merged["notion_enabled"] = False
    if merged["error"]:
        merged["error"] = f"{path}: {merged['error']}"
    return {"path": str(path), "found": found, **merged}


# ---------------------------------------------------------------- props, revisions, release, new

def props(text: str, settings: dict | None = None) -> dict:
    """Notion page properties, named and filled as the settings say. By default only the title is set."""
    notion = (settings or settings_from({}))["notion"]
    fm = parse_front_matter(text)
    out = {notion["title_property"]: f"{notion['title_prefix']}{fm.get('title', '')}"}
    out.update(notion["fixed_properties"])
    state = "published" if fm.get("status") == "published" else "draft"
    if notion["status_property"] and state in notion["status_values"]:
        out[notion["status_property"]] = notion["status_values"][state]
    if notion["tags_property"]:
        tags = fm.get("tags") or []
        out[notion["tags_property"]] = json.dumps([tags] if isinstance(tags, str) else tags)
    return out


def _revision_span(lines: list[str]):
    for i, line in enumerate(lines):
        if REV_HEADER_RE.match(line.strip()):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return i, j
    return None


def revision_rows(text: str) -> list[list[str]]:
    lines = text.split("\n")
    span = _revision_span(lines)
    if span is None:
        return []
    rows = [_split_row(line) for line in lines[span[0] + 2:span[1]]]
    return [row for row in rows if any(row)]


def append_revision_row(text: str, cells: list[str]) -> str:
    lines = text.split("\n")
    span = _revision_span(lines)
    if span is None:
        raise SddError("no Revision History table in this file")
    kept = [line for line in lines[span[0] + 2:span[1]] if any(_split_row(line))]
    row = "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"
    lines[span[0] + 2:span[1]] = kept + [row]
    return "\n".join(lines)


def release(text: str, reason: str, author: str, date: str) -> tuple[str, dict]:
    old = str(parse_front_matter(text).get("version", "0.1"))
    major, _, minor = old.partition(".")
    try:
        major_n, minor_n = int(major), int(minor or 0)
    except ValueError:
        raise SddError(f"cannot read version {old!r}") from None
    new = "1.0" if major_n == 0 else f"{major_n}.{minor_n + 1}"
    text = set_front_matter(text, {"version": new, "status": "published", "updated": date})
    text = re.sub(r"(?m)^Version \S+(?=\s*$)", f"Version {new}", text, count=1)
    text = append_revision_row(text, [author, date, reason, new])
    return text, {"from": old, "to": new, "status": "published"}


def new_document(title: str, slug: str, kind: str, author: str, org: str,
                 tags: list[str], links: list[str], date: str) -> str:
    if not SLUG_RE.match(slug) or len(slug) > 40:
        raise SddError(f"slug {slug!r} must be kebab-case (a-z, 0-9, hyphens), at most 40 characters")
    if kind not in KINDS:
        raise SddError(f"kind must be one of {', '.join(KINDS)}")
    text = TEMPLATE.read_text(encoding="utf-8")
    if not org:
        text = text.replace("{{organization}}  \n", "", 1)  # no empty line in the title block
    substitutions = {
        "{{project name}}": title, "{{slug}}": slug, "{{kind}}": kind, "{{author}}": author,
        "{{organization}}": org, "{{date_modified}}": date,
        "{{tags}}": _format_value(tags), "{{links}}": _format_value(links),
    }
    for key, value in substitutions.items():
        text = text.replace(key, value)
    leftover = PLACEHOLDER_RE.findall(text)
    if leftover:
        raise SddError(f"template placeholders left unfilled: {leftover}")
    return append_revision_row(text, [author, date, "Initial draft", "0.1"])


# ---------------------------------------------------------------- CLI

def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SddError(f"{path} does not exist") from None


def _write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdd.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create an SDD file from the template")
    p.add_argument("--title", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--kind", required=True, help="new | existing | change")
    p.add_argument("--author", required=True)
    p.add_argument("--org", help="default: organization from the settings file")
    p.add_argument("--tags", help="comma-separated Notion tags")
    p.add_argument("--links", help="comma-separated URLs")
    p.add_argument("--date", help="YYYY-MM-DD, default today")
    p.add_argument("--out", required=True)

    p = sub.add_parser("status", help="state of every section and the next one to write")
    p.add_argument("file")

    p = sub.add_parser("lint", help="check the file; exit 1 on errors")
    p.add_argument("file")
    p.add_argument("--fix", action="store_true", help="rewrite mermaid LR/RL to TB in place first")

    p = sub.add_parser("render", help="print the Notion-flavored markdown")
    p.add_argument("file")
    p.add_argument("--source", help="path shown in the page's header callout")

    sub.add_parser("settings", help="print the settings merged with the defaults; exit 1 when the file is broken")

    p = sub.add_parser("props", help="print the Notion page properties")
    p.add_argument("file")

    p = sub.add_parser("meta", help="print front matter, or update keys")
    p.add_argument("file")
    p.add_argument("--set", nargs="+", metavar="KEY=VALUE", default=[])

    p = sub.add_parser("section", help="print a section body, or replace it from stdin")
    p.add_argument("file")
    p.add_argument("id", help="section id, e.g. 1.6 or 3")
    p.add_argument("--write", action="store_true", help="replace the body with stdin")

    p = sub.add_parser("locate", help="which section a piece of Notion block text comes from (exit 3: no match)")
    p.add_argument("file")
    p.add_argument("--text", required=True)

    p = sub.add_parser("review-data", help="the facts the guided review page shows, as JSON")
    p.add_argument("file")

    p = sub.add_parser("review-page", help="build the guided review page (HTML) for publishing as an artifact")
    p.add_argument("file")
    p.add_argument("--notes", help="JSON file with the plain-language notes per entry id")
    p.add_argument("--out", required=True)
    p.add_argument("--source", help="path shown in the page header")

    p = sub.add_parser("review-notes", help="print the notes embedded in a review page, as JSON")
    p.add_argument("page", help="the page HTML, e.g. saved by an Artifact read")

    p = sub.add_parser("review-changed", help="entries whose text changed since a review page was built, as JSON")
    p.add_argument("page", help="the page HTML, e.g. saved by an Artifact read")
    p.add_argument("file")

    p = sub.add_parser("release", help="bump the version, mark published, add a revision row")
    p.add_argument("file")
    p.add_argument("--reason", required=True)
    p.add_argument("--author", help="default: the author in front matter")
    p.add_argument("--date", help="YYYY-MM-DD, default today")

    args = parser.parse_args(argv)
    today = dt.date.today().isoformat()
    try:
        if args.command == "new":
            out = Path(args.out)
            if out.exists():
                raise SddError(f"{out} already exists; refusing to overwrite")
            org = args.org if args.org is not None else load_settings()["organization"]
            text = new_document(args.title, args.slug, args.kind, args.author, org,
                                _csv(args.tags), _csv(args.links), args.date or today)
            out.parent.mkdir(parents=True, exist_ok=True)
            _write(str(out), text)
            _print_json({"path": str(out), "next": status(text)["next"]})
        elif args.command == "status":
            _print_json(status(_read(args.file)))
        elif args.command == "lint":
            text = _read(args.file)
            fixed = 0
            if args.fix:
                new_text = fix(text)
                fixed = sum(1 for a, b in zip(text.split("\n"), new_text.split("\n")) if a != b)
                if fixed:
                    _write(args.file, new_text)
                    text = new_text
            findings = lint(text)
            counts = {level: sum(1 for f in findings if f["level"] == level) for level in ("error", "warning", "info")}
            _print_json({"fixed": fixed, **counts, "findings": findings})
            return 1 if counts["error"] else 0
        elif args.command == "render":
            sys.stdout.write(render(_read(args.file), args.source or default_source_label(Path(args.file)),
                                    settings=load_settings()))
        elif args.command == "props":
            _print_json(props(_read(args.file), load_settings()))
        elif args.command == "settings":
            current = load_settings()
            _print_json(current)
            return 1 if current["error"] else 0
        elif args.command == "meta":
            text = _read(args.file)
            if args.set:
                updates = {}
                for pair in args.set:
                    key, sep, value = pair.partition("=")
                    if not sep or not key:
                        raise SddError(f"--set expects KEY=VALUE, got {pair!r}")
                    updates[key] = value
                text = set_front_matter(text, updates)
                _write(args.file, text)
            _print_json(parse_front_matter(text))
        elif args.command == "section":
            text = _read(args.file)
            if args.write:
                text = replace_section_body(text, args.id, sys.stdin.read())
                _write(args.file, text)
                state = next(s for s in status(text)["sections"] if s["id"] == args.id) \
                    if args.id in WALK_ORDER else {"id": args.id}
                _print_json(state)
            else:
                sys.stdout.write(section_body(text, args.id))
        elif args.command == "locate":
            hit = locate(_read(args.file), args.text)
            if hit is None:
                _print_json({"section": None, "record": None})
                return 3
            _print_json(hit)
        elif args.command == "review-data":
            _print_json(review_data(_read(args.file)))
        elif args.command == "review-page":
            notes = json.loads(_read(args.notes)) if args.notes else {}
            page = review_page(_read(args.file), notes, args.source or default_source_label(Path(args.file)))
            _write(args.out, page)
            _print_json({"path": args.out, "entries": page.count('<section class="entry"')})
        elif args.command == "review-notes":
            _print_json(page_notes(_read(args.page)))
        elif args.command == "review-changed":
            _print_json(page_changes(_read(args.page), _read(args.file)))
        elif args.command == "release":
            text = _read(args.file)
            author = args.author or str(parse_front_matter(text).get("author", ""))
            text, info = release(text, args.reason, author, args.date or today)
            _write(args.file, text)
            _print_json(info)
    except SddError as error:
        print(f"sdd.py: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
