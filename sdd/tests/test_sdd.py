"""Tests for scripts/sdd.py.

Run from the sdd/ folder:
    python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "scripts" / "sdd.py"
FIX = HERE / "fixtures"

WALK_ORDER = ["1.2", "1.6", "1.1", "2.1", "2.2", "3", "4", "5", "1.4", "1.3", "1.5"]
VIEWPOINTS = [
    "Context", "Composition", "Logical", "Physical", "Structure", "Dependency", "Information", "Interface",
    "Interaction", "Algorithm", "State Dynamics", "Concurrency", "Patterns", "Deployment", "Resources",
]
EM_DASH = "\u2014"


def _load():
    if not SCRIPT.exists():
        return None
    spec = importlib.util.spec_from_file_location("sdd", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SDD = _load()


def sdd():
    if SDD is None:
        raise AssertionError(f"{SCRIPT} does not exist yet")
    return SDD


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def run_cli(*args, stdin=None):
    sdd()  # a missing script must fail the test, not satisfy a "non-zero exit" assertion
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True, input=stdin
    )


def notion_settings():
    """Options that reproduce the plugin's behavior before options existed: SDD: titles, hearts, Doing/Done."""
    return sdd().load_options(read("options-notion.txt"))


def code_line_indexes(lines):
    """Indexes of lines inside fenced code blocks, fences included."""
    inside, idx = False, set()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            idx.add(i)
            inside = not inside
        elif inside:
            idx.add(i)
    return idx


def code_blocks(text):
    return re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)


class NewTests(unittest.TestCase):
    def new(self, out, *extra, org=("--org", "Acme"), stdin=None):
        return run_cli(
            "new", "--title", "Per-PR preview environments", "--slug", "preview-envs", "--kind", "new",
            "--author", "eeeemune", *org, "--tags", "Infra,Kubernetes",
            "--date", "2026-10-06", "--out", out, *extra, stdin=stdin,
        )

    def test_new_takes_the_author_from_the_options(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a.md"
            r = run_cli("new", "--title", "T", "--slug", "t", "--kind", "new", "--options", "-",
                        "--date", "2026-10-13", "--out", out, stdin="author=Ada Lovelace\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertEqual(sdd().parse_front_matter(text)["author"], "Ada Lovelace")
            self.assertEqual(sdd().revision_rows(text)[0][0], "Ada Lovelace")

    def test_new_without_an_author_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a.md"
            r = run_cli("new", "--title", "T", "--slug", "t", "--kind", "new", "--out", out)
            self.assertEqual(r.returncode, 2)
            self.assertIn("author", r.stderr)
            self.assertFalse(out.exists())

    def test_new_creates_all_sections(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "docs" / "sdd" / "preview-envs.md"
            r = self.new(out)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = out.read_text(encoding="utf-8")
            for heading in [
                "### 1.1 Document Purpose", "### 1.2 Subject Scope",
                "### 1.3 Definitions, Acronyms, and Abbreviations", "### 1.4 References",
                "### 1.5 Document Overview", "### 1.6 Requirements", "### 2.1 Stakeholder Concerns",
                "### 2.2 Selected Viewpoints", "## 3. Design Views", "## 4. Decisions",
                "## 5. Appendixes", "## Revision History",
            ]:
                self.assertIn("\n" + heading + "\n", text)
            self.assertNotIn("{{", text)
            fm = sdd().parse_front_matter(text)
            self.assertEqual(fm["title"], "Per-PR preview environments")
            self.assertEqual(fm["tags"], ["Infra", "Kubernetes"])
            self.assertEqual(fm["created"], "2026-10-06")
            self.assertEqual(fm["status"], "draft")
            self.assertEqual(sdd().revision_rows(text), [["eeeemune", "2026-10-06", "Initial draft", "0.1"]])
            st = json.loads(run_cli("status", out).stdout)
            self.assertEqual(st["done"], 0)
            self.assertEqual(st["next"], "1.2")

    def test_new_takes_the_organization_from_the_options(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a.md"
            r = self.new(out, "--options", "-", org=(), stdin="organization=Acme\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertEqual(sdd().parse_front_matter(text)["organization"], "Acme")
            self.assertIn("Prepared by eeeemune  \nAcme  \n2026-10-06\n", text)

    def test_new_without_organization_drops_its_line(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "a.md"
            r = self.new(out, org=())
            self.assertEqual(r.returncode, 0, r.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Prepared by eeeemune  \n2026-10-06\n", text)
            self.assertEqual(sdd().parse_front_matter(text)["organization"], "")
            self.assertNotIn("{{", text)

    def test_new_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "x.md"
            out.write_text("keep me\n", encoding="utf-8")
            r = self.new(out)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "keep me\n")

    def test_new_rejects_bad_slug_and_kind(self):
        with tempfile.TemporaryDirectory() as d:
            bad_slug = run_cli(
                "new", "--title", "T", "--slug", "Bad Slug", "--kind", "new", "--author", "A",
                "--org", "O", "--out", Path(d) / "a.md",
            )
            self.assertNotEqual(bad_slug.returncode, 0)
            bad_kind = run_cli(
                "new", "--title", "T", "--slug", "ok", "--kind", "other", "--author", "A",
                "--org", "O", "--out", Path(d) / "b.md",
            )
            self.assertNotEqual(bad_kind.returncode, 0)


class StatusTests(unittest.TestCase):
    def test_status_partial(self):
        st = sdd().status(read("partial.md"))
        self.assertEqual([s["id"] for s in st["sections"]], WALK_ORDER)
        states = {s["id"]: s["state"] for s in st["sections"]}
        self.assertEqual(states, {
            "1.2": "done", "1.6": "done", "1.1": "todo", "2.1": "skipped", "2.2": "todo", "3": "todo",
            "4": "todo", "5": "na", "1.4": "todo", "1.3": "todo", "1.5": "todo",
        })
        self.assertEqual(st["next"], "1.1")
        self.assertEqual(st["skipped"], ["2.1"])
        self.assertEqual(st["done"], 3)
        self.assertEqual(st["total"], 11)

    def test_status_full(self):
        st = sdd().status(read("full.md"))
        self.assertEqual(st["done"], 11)
        self.assertIsNone(st["next"])

    def test_status_section3_waits_for_every_picked_viewpoint(self):
        full = read("full.md")
        views = sdd().section_body(full, "3")
        without_v4 = views.split("### V4 Deployment")[0]
        st = sdd().status(sdd().replace_section_body(full, "3", without_v4))
        self.assertEqual({s["id"]: s["state"] for s in st["sections"]}["3"], "todo")
        self.assertEqual(st["next"], "3")
        self.assertEqual(st["pending_views"], ["deployment"])
        skipped = without_v4 + "\n**TODO:** Deployment view, waiting for the node pool size.\n"
        st = sdd().status(sdd().replace_section_body(full, "3", skipped))
        self.assertEqual({s["id"]: s["state"] for s in st["sections"]}["3"], "skipped")
        self.assertEqual(st["pending_views"], [])

    def test_status_section4_with_only_proposed_adrs_is_todo(self):
        full = read("full.md")
        proposed = sdd().section_body(full, "4").replace("**Status:** accepted", "**Status:** proposed")
        st = sdd().status(sdd().replace_section_body(full, "4", proposed))
        self.assertEqual({s["id"]: s["state"] for s in st["sections"]}["4"], "todo")
        one_accepted = proposed.replace("**Status:** proposed", "**Status:** accepted", 1)
        st = sdd().status(sdd().replace_section_body(full, "4", one_accepted))
        self.assertEqual({s["id"]: s["state"] for s in st["sections"]}["4"], "done")

    def test_status_returns_skipped_after_todos(self):
        text = read("partial.md")
        for sid in ["1.1", "2.2", "3", "4", "1.4", "1.3", "1.5"]:
            text = sdd().replace_section_body(text, sid, "Filled.")
        st = sdd().status(text)
        self.assertEqual(st["next"], "2.1")


EXPECTED_BAD = {
    "em-dash": EM_DASH,
    "mermaid-direction": "flowchart LR",
    "mermaid-label-parens": "a[Dev (laptop)]",
    "placeholder": "{{owner team}}",
    "req-unknown": "**Implements:** R1, R2, R9",
    "req-no-check": "| R2 |",
    "req-orphan": "| R3 |",
    "view-no-implements": "### V2 Context",
    "viewpoint-unused": "#### 2.2.14 Deployment",
    "decision-incomplete": "### ADR-002",
    "adr-proposed": "**Status:** proposed",
    "todo": "**TODO:**",
    "emoji": "\U0001F680",
    "vague-word": "scalable",
}
ERROR_RULES = {"em-dash", "mermaid-direction", "placeholder", "req-unknown", "req-no-check"}
INFO_RULES = {"vague-word"}


class LintTests(unittest.TestCase):
    def test_lint_bad_fires_each_rule_once_on_the_right_line(self):
        text = read("bad.md")
        lines = text.splitlines()
        findings = sdd().lint(text)
        self.assertEqual(Counter(f["rule"] for f in findings), Counter({rule: 1 for rule in EXPECTED_BAD}))
        for f in findings:
            self.assertIn(EXPECTED_BAD[f["rule"]], lines[f["line"] - 1], f)

    def test_lint_levels(self):
        for f in sdd().lint(read("bad.md")):
            expected = "error" if f["rule"] in ERROR_RULES else "info" if f["rule"] in INFO_RULES else "warning"
            self.assertEqual(f["level"], expected, f["rule"])

    def test_lint_full_is_clean(self):
        self.assertEqual(sdd().lint(read("full.md")), [])

    def test_lint_catches_placeholders_in_inline_code_but_not_go_templates(self):
        full = read("full.md")
        text = full.replace(
            "Nothing outside this diagram calls the pipeline.",
            "Nothing outside this diagram calls the pipeline. URLs look like `https://pr-1.{{preview domain}}`; "
            "the chart uses `{{ .Values.image }}`, `{{range .Items}}` and `{{- end }}`.",
        )
        found = [f for f in sdd().lint(text) if f["rule"] == "placeholder"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("{{preview domain}}", found[0]["message"])

    def test_lint_reports_every_placeholder_on_a_line(self):
        text = read("full.md").replace(
            "Nothing outside this diagram calls the pipeline.",
            "Still to name: {{Git host and CI system}} and {{container registry}}.",
        )
        found = [f["message"] for f in sdd().lint(text) if f["rule"] == "placeholder"]
        self.assertEqual(len(found), 2, found)

    def test_lint_catches_placeholders_in_diagram_labels_but_not_hexagons(self):
        text = read("full.md").replace(
            '\tci -->|"push image"| ecr["ECR"]',
            '\tci -->|"push image"| reg["{{container registry}}"]\n\treg --> hex{{Image cache}}',
        )
        found = [f["message"] for f in sdd().lint(text) if f["rule"] == "placeholder"]
        self.assertEqual(found, ["unfilled placeholder {{container registry}}"])

    def test_lint_partial_ignores_commented_skeletons(self):
        rules = Counter(f["rule"] for f in sdd().lint(read("partial.md")))
        self.assertEqual(rules, Counter({"req-orphan": 4, "todo": 1}))

    def test_fix_rewrites_lr_and_nothing_else(self):
        before = read("bad.md")
        after = sdd().fix(before)
        self.assertEqual(len(before.splitlines()), len(after.splitlines()))
        changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual(changed, [("flowchart LR", "flowchart TB")])

    def test_lint_cli_exit_codes(self):
        self.assertEqual(run_cli("lint", FIX / "bad.md").returncode, 1)
        self.assertEqual(run_cli("lint", FIX / "full.md").returncode, 0)


TEST_GUIDE = {
    "sections": {"1.1": {"what": "why this SDD exists and who reads it.",
                         "look_for": "the readers, and where changes are made."}},
    "viewpoints": {},
}


def untab(block):
    """Drop the one tab of toggle indentation from every line of a code block."""
    return "\n".join(line[1:] if line.startswith("\t") else line for line in block.split("\n")).rstrip()


class RenderTests(unittest.TestCase):
    def test_render_matches_hand_written_golden(self):
        out = sdd().render(read("mini.md"), source_label="fixtures/mini.md", guide=TEST_GUIDE, settings=notion_settings())
        self.assertEqual(out, read("mini.notion.md"))

    def test_default_guide_covers_every_section_and_viewpoint(self):
        guide = sdd().load_guide()
        for sid in WALK_ORDER:
            self.assertTrue(guide["sections"][sid]["what"], sid)
            self.assertTrue(guide["sections"][sid]["look_for"], sid)
        for name in VIEWPOINTS:
            self.assertTrue(guide["viewpoints"][name.lower()]["answers"], name)

    def test_render_about_notes_for_sections_views_and_records(self):
        lines = sdd().render(read("full.md"), source_label="x.md", settings=notion_settings()).splitlines()

        def about_after(heading_start):
            i = next(n for n, line in enumerate(lines) if line.startswith(heading_start))
            self.assertTrue(lines[i].endswith(' {toggle="true"}'), lines[i])
            self.assertEqual(lines[i + 1], '\t<callout color="gray_bg">')
            return lines[i + 2]

        self.assertTrue(about_after("## \U0001F49B 1.6 Requirements").startswith("\t\t**About this section:** the things"))
        view = about_after("## \U0001F49B V1 Context")
        self.assertTrue(view.startswith("\t\t**About this view:** Context views answer: what is inside the system"), view)
        self.assertIn("**Look for:**", view)
        self.assertTrue(about_after("## \U0001F49B ADR-001").startswith("\t\t**About this record:** one record"))

    def test_escape_inline(self):
        self.assertEqual(
            sdd().escape_inline("a <b> {c} d|e $1 2^3 ~4 [x] [l](https://u.v/w_x) `k<m>` ~~s~~ back\\slash"),
            "a \\<b\\> \\{c\\} d\\|e \\$1 2\\^3 \\~4 \\[x\\] [l](https://u.v/w_x) `k<m>` ~~s~~ back\\\\slash",
        )

    def test_render_invariants_on_full(self):
        src = read("full.md")
        out = sdd().render(src, source_label="fixtures/full.md", settings=notion_settings())
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("<callout"))
        self.assertNotIn("<!--", out)
        self.assertNotIn(EM_DASH, out)
        self.assertNotIn("\\n", out)
        self.assertEqual(out.count("<table_of_contents/>"), 1)
        self.assertEqual(sum(1 for line in lines if line.lstrip().startswith("<table ")), 5)
        self.assertEqual([untab(b) for b in code_blocks(out)], [b.rstrip() for b in code_blocks(src)])
        hearts = {1: "\U0001F49A", 2: "\U0001F49B", 3: "\U0001F90D"}
        skip = code_line_indexes(lines)
        in_toggle = False
        for i, line in enumerate(lines):
            if i in skip:
                if in_toggle:
                    self.assertTrue(line.startswith("\t"), f"code line {i} not indented under its toggle")
                continue
            self.assertIsNone(re.match(r"^\s*\|.*\|\s*$", line), line)
            m = re.match(r"^(\t*)(#+) (\S+)", line)
            if m:
                level = len(m.group(2))
                self.assertIn(level, hearts, line)
                self.assertEqual(m.group(3), hearts[level], line)
                if level == 1:
                    in_toggle = False
                    self.assertEqual(m.group(1), "", line)
                elif level == 2:
                    in_toggle = True
                    self.assertEqual(m.group(1), "", line)
                    self.assertTrue(line.endswith(' {toggle="true"}'), line)
                else:
                    self.assertEqual(m.group(1), "\t" if in_toggle else "", line)
            elif in_toggle:
                self.assertTrue(line.startswith("\t"), f"line {i} not indented under its toggle: {line}")
            stripped = line.strip()
            if re.search(r"</?table[\s>]|</?tr>", stripped):
                self.assertIn(stripped, {'<table header-row="true">', "</table>", "<tr>", "</tr>"}, line)
            if "<td>" in stripped:
                self.assertRegex(stripped, r"^<td>.*</td>$")

    def test_render_uses_plain_headings_by_default(self):
        out = sdd().render(read("full.md"), source_label="x.md")
        for heart in ("\U0001F49A", "\U0001F49B", "\U0001F90D"):
            self.assertNotIn(heart, out)
        self.assertIn('## 1.6 Requirements {toggle="true"}', out)
        self.assertIn("# 1. Introduction", out)

    def test_render_template_only_doc(self):
        out = sdd().render(read("partial.md"), source_label="x.md")
        self.assertNotIn("<!--", out)
        self.assertNotIn("V<n>", out)
        self.assertIn("**Status** Draft", out)

    def test_render_published_label(self):
        text = sdd().set_front_matter(read("full.md"), {"status": "published", "version": "1.0"})
        self.assertIn("**Version** 1.0 · **Status** Published", sdd().render(text, source_label="x.md"))


class PropsTests(unittest.TestCase):
    def test_props_with_notion_settings_keep_the_old_shape(self):
        # Same keys, values and order as before settings existed, so an existing page is updated the same way (R6).
        out = sdd().props(read("full.md"), notion_settings())
        self.assertEqual(json.dumps(out), json.dumps({
            "Name": "SDD: Per-PR preview environments",
            "Category": "Document",
            "Status": "Doing",
            "Tags": '["Infra", "Kubernetes", "CI/CD"]',
        }))

    def test_props_published(self):
        text = sdd().set_front_matter(read("full.md"), {"status": "published"})
        self.assertEqual(sdd().props(text, notion_settings())["Status"], "Done")

    def test_props_by_default_set_only_the_title(self):
        self.assertEqual(sdd().props(read("full.md")), {"Name": "Per-PR preview environments"})


class OptionsTests(unittest.TestCase):
    def test_no_options_means_notion_off(self):
        s = sdd().load_options("")
        self.assertFalse(s["notion_enabled"])
        self.assertEqual(s["organization"], "")
        self.assertEqual(s["notion"]["heading_marks"], [])
        self.assertEqual((s["warnings"], s["error"]), ([], None))

    def test_options_block_maps_to_settings(self):
        s = notion_settings()
        self.assertTrue(s["notion_enabled"])
        self.assertEqual(s["organization"], "Acme")
        n = s["notion"]
        self.assertEqual(n["tags"], ["Infra", "Kubernetes", "CI/CD"])
        self.assertEqual(n["fixed_properties"], {"Category": "Document"})
        self.assertEqual(n["status_values"], {"draft": "Doing", "published": "Done"})
        self.assertEqual(n["heading_marks"], ["\U0001F49A", "\U0001F49B", "\U0001F90D"])
        self.assertEqual(n["title_prefix"], "SDD:")

    def test_unset_placeholders_count_as_empty(self):
        s = sdd().load_options("organization=${user_config.organization}\n"
                               "notion_data_source_id=${user_config.notion_data_source_id}\n")
        self.assertEqual(s["organization"], "")
        self.assertFalse(s["notion_enabled"])
        self.assertEqual(s["warnings"], [])

    def test_unknown_key_warns(self):
        s = sdd().load_options("organisation=Acme\nnotion_data_source_id=x\n")
        self.assertEqual(s["warnings"], ["unknown option 'organisation' is ignored"])
        self.assertTrue(s["notion_enabled"])

    def test_heading_marks_need_three(self):
        s = sdd().load_options("notion_data_source_id=x\nnotion_heading_marks=A B\n")
        self.assertIn("notion_heading_marks", s["error"])
        self.assertFalse(s["notion_enabled"])
        self.assertEqual(s["notion"]["heading_marks"], [])

    def test_fixed_properties_need_name_value_pairs(self):
        s = sdd().load_options("notion_data_source_id=x\nnotion_fixed_properties=Category\n")
        self.assertIn("notion_fixed_properties", s["error"])
        self.assertFalse(s["notion_enabled"])

    def test_title_prefix_is_followed_by_a_space(self):
        s = sdd().load_options("notion_title_prefix=SDD:\n")
        self.assertEqual(sdd().props(read("full.md"), s)["Name"], "SDD: Per-PR preview environments")

    def test_options_cli_reads_stdin(self):
        r = run_cli("options", "--options", "-", stdin="organization=Acme\nbogus=1\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["organization"], "Acme")
        self.assertEqual(out["warnings"], ["unknown option 'bogus' is ignored"])
        r = run_cli("options", "--options", "-", stdin="notion_heading_marks=A\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("notion_heading_marks", json.loads(r.stdout)["error"])

    def test_render_and_props_cli_take_the_options(self):
        block = read("options-notion.txt")
        r = run_cli("props", FIX / "full.md", "--options", "-", stdin=block)
        self.assertEqual(json.loads(r.stdout)["Name"], "SDD: Per-PR preview environments")
        r = run_cli("render", FIX / "full.md", "--options", "-", stdin=block)
        self.assertIn("## \U0001F49B 1.6 Requirements", r.stdout)
        r = run_cli("render", FIX / "full.md")
        self.assertIn("## 1.6 Requirements", r.stdout)

    def test_author_option(self):
        self.assertEqual(sdd().load_options("")["author"], "")
        s = sdd().load_options("author=Ada Lovelace\nauthor_x=1\n")
        self.assertEqual(s["author"], "Ada Lovelace")
        self.assertEqual(s["warnings"], ["unknown option 'author_x' is ignored"])

    def test_every_option_is_declared_and_passed_by_every_skill(self):
        keys = set(sdd().OPTION_KEYS)
        declared = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["userConfig"]
        self.assertEqual(set(declared), keys)
        for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
            block = re.findall(r"^(\w+)=\$\{user_config\.(\w+)\}$", skill.read_text(encoding="utf-8"), flags=re.M)
            self.assertEqual({k for k, _ in block}, keys, skill.parent.name)
            self.assertTrue(all(k == v for k, v in block), skill.parent.name)

    def test_no_procedure_reads_the_git_identity(self):
        for path in [ROOT / "README.md", *sorted((ROOT / "core").glob("*.md")), *sorted((ROOT / "skills").glob("*/SKILL.md"))]:
            self.assertFalse("git config" in path.read_text(encoding="utf-8"), path.name)

    def test_no_procedure_reads_cloud_state(self):
        for path in [ROOT / "README.md", *sorted((ROOT / "core").glob("*.md")), *sorted((ROOT / "skills").glob("*/SKILL.md"))]:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?i)\b(cluster|aws|cloud)\b[\w ]{0,12}\bstate\b", text), path.name)

    def test_helper_reads_no_settings_file(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE_CONFIG_DIR", source)
        self.assertNotIn("settings.json", source)


class MetaTests(unittest.TestCase):
    def test_set_front_matter_changes_only_named_keys(self):
        src = read("full.md")
        out = sdd().set_front_matter(src, {"notion_page_id": "abc123", "notion_pending": "true", "extra": "x"})
        before, after = sdd().parse_front_matter(src), sdd().parse_front_matter(out)
        self.assertEqual(after["notion_page_id"], "abc123")
        self.assertEqual(after["notion_pending"], "true")
        self.assertEqual(after["extra"], "x")
        for key in before:
            if key not in {"notion_page_id", "notion_pending"}:
                self.assertEqual(after[key], before[key], key)
        self.assertEqual(sdd().split_front_matter(src)[1], sdd().split_front_matter(out)[1])

    def test_meta_cli_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.md"
            path.write_text(read("full.md"), encoding="utf-8")
            r = run_cli("meta", path, "--set", "notion_page_id=p1", "notion_last_sync=2026-10-06T10:00:00Z")
            self.assertEqual(r.returncode, 0, r.stderr)
            fm = json.loads(r.stdout)
            self.assertEqual(fm["notion_page_id"], "p1")
            self.assertEqual(sdd().parse_front_matter(path.read_text(encoding="utf-8"))["notion_last_sync"],
                             "2026-10-06T10:00:00Z")


class SectionTests(unittest.TestCase):
    def test_replace_section_body_keeps_everything_else(self):
        src = read("partial.md")
        out = sdd().replace_section_body(src, "2.2", "Picked: Context.\n\n#### 2.2.1 Context\nAddresses: boundary.")
        self.assertIn("### 2.2 Selected Viewpoints\nPicked: Context.\n\n#### 2.2.1 Context\nAddresses: boundary.\n\n## 3. Design Views", out)
        self.assertNotIn("#### 2.2.15 Resources", out)
        self.assertEqual(out.split("### 2.2 Selected Viewpoints")[0], src.split("### 2.2 Selected Viewpoints")[0])
        self.assertEqual(out.split("## 3. Design Views")[1], src.split("## 3. Design Views")[1])

    def test_section_cli_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.md"
            path.write_text(read("partial.md"), encoding="utf-8")
            sdd()
            r = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "section", str(path), "1.1", "--write"],
                input="This SDD describes the preview pipeline.\n", capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(run_cli("section", path, "1.1").stdout, "This SDD describes the preview pipeline.\n")
            self.assertEqual(sdd().status(path.read_text(encoding="utf-8"))["next"], "2.2")

    def test_section_unknown_id_fails(self):
        self.assertNotEqual(run_cli("section", FIX / "partial.md", "9.9").returncode, 0)


class LocateTests(unittest.TestCase):
    def hit(self, snippet):
        return sdd().locate(read("full.md"), snippet)

    def test_requirement_row(self):
        h = self.hit("R2 An environment is deleted within 1 hour of its PR closing")
        self.assertEqual((h["section"], h["record"]), ("1.6", None))

    def test_paragraph_in_a_view(self):
        h = self.hit("Two paths remove an environment: the PR-closed workflow (normal path) and the reaper "
                     "(catches failed or cancelled workflow runs).")
        self.assertEqual((h["section"], h["record"]), ("3", "V4"))

    def test_line_in_a_decision(self):
        h = self.hit('Chosen option: "both", because the workflow removes the environment within minutes')
        self.assertEqual((h["section"], h["record"]), ("4", "ADR-002"))

    def test_notion_normalizations(self):
        self.assertEqual(self.hit("[https://docs.github.com/actions](https://docs.github.com/actions)")["section"], "1.4")
        self.assertEqual(self.hit("*Not applicable: no supporting material for v1.*")["section"], "5")
        self.assertEqual(self.hit("\U0001F49B 1.6 Requirements")["section"], "1.6")

    def test_no_match(self):
        self.assertIsNone(self.hit("completely unrelated text about bananas and submarines"))
        r = run_cli("locate", FIX / "full.md", "--text", "completely unrelated text about bananas and submarines")
        self.assertEqual(r.returncode, 3)

    def test_cli(self):
        r = run_cli("locate", FIX / "full.md", "--text", "R2 An environment is deleted within 1 hour")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["section"], "1.6")


class ReviewDataTests(unittest.TestCase):
    def test_entries_in_reading_order(self):
        data = sdd().review_data(read("full.md"))
        self.assertEqual([e["id"] for e in data["entries"]], [
            "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "2.1", "2.2",
            "V1", "V2", "V3", "V4", "ADR-001", "ADR-002", "5",
        ])
        self.assertEqual((data["title"], data["version"], data["status"]), ("Per-PR preview environments", "0.1", "draft"))

    def test_view_and_decision_entries(self):
        entries = {e["id"]: e for e in sdd().review_data(read("full.md"))["entries"]}
        v4 = entries["V4"]
        self.assertEqual((v4["kind"], v4["parent"], v4["viewpoint"]), ("view", "3", "Deployment"))
        self.assertEqual(v4["title"], "Deployment: where it runs and how it is removed")
        self.assertEqual((v4["implements"], v4["decisions"]), (["R2", "R4"], ["ADR-001", "ADR-002"]))
        self.assertIn("```mermaid", v4["markdown"])
        self.assertTrue(v4["about"]["what"].startswith("Deployment views answer"))
        adr = entries["ADR-002"]
        self.assertEqual((adr["kind"], adr["parent"], adr["decision_status"]), ("decision", "4", "accepted"))
        self.assertEqual(entries["1.6"]["kind"], "section")
        self.assertNotIn("<!--", entries["1.1"]["markdown"])

    def test_requirements_trace(self):
        reqs = {r["id"]: r for r in sdd().review_data(read("full.md"))["requirements"]}
        self.assertEqual(reqs["R1"]["implemented_by"], ["V1", "V3"])
        self.assertTrue(reqs["R2"]["check"].startswith("Given a closed PR"))

    def test_findings_land_on_their_entry(self):
        entries = {e["id"]: e for e in sdd().review_data(read("partial.md"))["entries"]}
        self.assertIn("3", entries)  # no views yet: the section itself is the entry
        self.assertEqual([f["rule"] for f in entries["2.1"]["findings"]], ["todo"])
        self.assertEqual([f["rule"] for f in entries["1.6"]["findings"]], ["req-orphan"] * 4)
        self.assertEqual((entries["1.1"]["state"], entries["2.1"]["state"]), ("todo", "skipped"))
        self.assertTrue(all(not e["findings"] for e in sdd().review_data(read("full.md"))["entries"]))

    def test_cli_prints_json(self):
        r = run_cli("review-data", FIX / "full.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)["entries"]), 15)


SAMPLE_NOTES = {
    "1.6": {"in_short": "Four things the pipeline must do, each with a test.",
            "why_care": "This is what the build is checked against.",
            "connects": "1.2 scope -> R1 to R4 -> views V1 to V4"},
    "V4": {"in_short": "Previews live in their own namespaces; two things delete them.",
           "tour": ["The outer box is the EKS cluster.", "Two arrows delete namespaces: the workflow and the reaper."],
           "check": {"q": "If the PR-closed workflow fails, what still deletes the namespace?",
                     "a": "The reaper, within 15 minutes."}},
}


class ReviewPageTests(unittest.TestCase):
    def test_markdown_to_html(self):
        html = sdd().md_to_html(
            "Text with **bold**, `a<b>`, <tag> and [docs](https://example.com/x).\n\n"
            "- one\n  - nested\n- two\n\n"
            "| A | B |\n|---|---|\n| 1 | `x\\|y` |\n\n"
            "```mermaid\nflowchart TB\n\ta --> b\n```\n\n"
            "```bash\necho <hi>\n```\n\n"
            "**TODO:** fill this in.\n"
        )
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>a&lt;b&gt;</code>", html)
        self.assertIn("&lt;tag&gt;", html)
        self.assertIn('<a href="https://example.com/x" target="_blank" rel="noopener">docs</a>', html)
        self.assertRegex(html, r"<ul>\s*<li>one\s*<ul>\s*<li>nested</li>\s*</ul>\s*</li>\s*<li>two</li>\s*</ul>")
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td><code>x|y</code></td>", html)
        self.assertIn('<pre class="mermaid">flowchart TB\n\ta --&gt; b</pre>', html)
        self.assertIn("<pre><code>echo &lt;hi&gt;</code></pre>", html)
        self.assertIn('<p class="todo"><strong>TODO:</strong> fill this in.</p>', html)

    def test_review_page_structure(self):
        page = sdd().review_page(read("full.md"), SAMPLE_NOTES, source_label="fixtures/full.md")
        self.assertTrue(page.startswith("<title>Per-PR preview environments review</title>"))
        self.assertEqual(page.count('<section class="entry"'), 15)
        self.assertEqual(page.count('<pre class="mermaid">'), 8)  # each diagram in its card and in the Original tab
        self.assertEqual(page.count('class="toc-link"'), 15)
        self.assertIn("Previews live in their own namespaces; two things delete them.", page)
        self.assertIn("If the PR-closed workflow fails, what still deletes the namespace?", page)
        self.assertNotIn("<!--SDD:", page)
        self.assertNotIn("__SDD_", page)
        data_json = re.search(r'<script type="application/json" id="sdd-data">(.*?)</script>', page, re.S).group(1)
        data = json.loads(data_json)
        self.assertEqual([e["id"] for e in data["entries"]][:2], ["1.1", "1.2"])
        self.assertIn("```mermaid", next(e["markdown"] for e in data["entries"] if e["id"] == "V4"))

    def test_review_page_without_notes_still_complete(self):
        page = sdd().review_page(read("partial.md"), {}, source_label="x.md")
        self.assertEqual(page.count('<section class="entry"'), 11)
        self.assertNotIn("In short", page)

    def test_review_page_cli(self):
        with tempfile.TemporaryDirectory() as d:
            notes, out = Path(d) / "notes.json", Path(d) / "page.html"
            notes.write_text(json.dumps(SAMPLE_NOTES), encoding="utf-8")
            r = run_cli("review-page", FIX / "full.md", "--notes", notes, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('<section class="entry"', out.read_text(encoding="utf-8"))

    def test_review_page_shows_claudes_findings(self):
        notes = dict(SAMPLE_NOTES, **{"1.6": {"in_short": "Five requirements.",
                                              "findings": ["R1 has no number for `fast`. Fix: say 10 minutes.", "A <b> tag."]}})
        page = sdd().review_page(read("full.md"), notes, source_label="x.md")
        card = re.search(r'<section class="entry" id="s-1-6".*?</section>', page, re.S).group(0)
        block = re.search(r'<div class="findings claude">.*?</div>', card, re.S).group(0)
        self.assertIn("What Claude found", block)
        self.assertIn("<li>R1 has no number for <code>fast</code>. Fix: say 10 minutes.</li>", block)
        self.assertIn("<li>A &lt;b&gt; tag.</li>", block)
        self.assertNotIn('class="findings claude"', sdd().review_page(read("full.md"), SAMPLE_NOTES, source_label="x.md"))

    def test_hidden_attribute_beats_display_rules(self):
        # .note-row and .suggestions set display: grid, which overrides the browser's own [hidden] rule.
        page = sdd().review_page(read("full.md"), SAMPLE_NOTES, source_label="x.md")
        self.assertIn("[hidden] { display: none !important; }", page)

    def test_last_card_points_to_the_default_review_command(self):
        page = sdd().review_page(read("full.md"), SAMPLE_NOTES, source_label="x.md")
        self.assertIn("Run /sdd-planner:review in Claude Code", page)
        self.assertNotIn("/sdd-planner:review page", page)

    def test_page_changes_lists_entries_edited_since_the_page_was_built(self):
        text = read("full.md")
        page = sdd().review_page(text, SAMPLE_NOTES, source_label="x.md")
        self.assertEqual(sdd().page_changes(page, text), {"changed": [], "added": [], "removed": []})
        edited = text.replace("It is prescriptive: the system is built from it.", "It is prescriptive.")
        self.assertEqual(sdd().page_changes(page, edited), {"changed": ["1.1"], "added": [], "removed": []})

    def test_review_changed_cli(self):
        with tempfile.TemporaryDirectory() as d:
            notes, out, doc = Path(d) / "notes.json", Path(d) / "page.html", Path(d) / "doc.md"
            notes.write_text(json.dumps(SAMPLE_NOTES), encoding="utf-8")
            run_cli("review-page", FIX / "full.md", "--notes", notes, "--out", out)
            doc.write_text(read("full.md").replace("It is prescriptive: the system is built from it.", "Changed."),
                           encoding="utf-8")
            r = run_cli("review-changed", out, doc)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["changed"], ["1.1"])

    def test_page_carries_its_notes(self):
        notes = dict(SAMPLE_NOTES, **{"1.1": {"in_short": "Ends a script early: </script> & \"quotes\"."}})
        page = sdd().review_page(read("full.md"), notes, source_label="x.md")
        self.assertNotIn("</script> &", page)
        self.assertEqual(sdd().page_notes(page), notes)

    def test_review_notes_cli(self):
        with tempfile.TemporaryDirectory() as d:
            notes, out = Path(d) / "notes.json", Path(d) / "page.html"
            notes.write_text(json.dumps(SAMPLE_NOTES), encoding="utf-8")
            run_cli("review-page", FIX / "full.md", "--notes", notes, "--out", out)
            r = run_cli("review-notes", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), SAMPLE_NOTES)
            r = run_cli("review-notes", FIX / "full.md")
            self.assertEqual(r.returncode, 2)
            self.assertIn("not a review page", r.stderr)


def doc_part(html, slug):
    m = re.search(rf'<section class="doc-part" id="d-{slug}" data-id="[^"]+">(.*?)</section>', html, re.S)
    if not m:
        raise AssertionError(f"no doc part d-{slug}")
    return m.group(1)


class OriginalDocumentTests(unittest.TestCase):
    def test_parts_in_file_order(self):
        html = sdd().original_html(read("full.md"))
        ids = re.findall(r'<section class="doc-part" id="d-[^"]+" data-id="([^"]+)"', html)
        self.assertEqual(ids, ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "2.1", "2.2",
                               "V1", "V2", "V3", "V4", "ADR-001", "ADR-002", "5"])

    def test_title_block_revision_history_and_chapters(self):
        html = sdd().original_html(read("full.md"))
        self.assertIn('<h2 class="doc-title">Software Design Description</h2>', html)
        self.assertIn('<p class="doc-subtitle">For Per-PR preview environments</p>', html)
        self.assertIn("Version 0.1<br>Prepared by eeeemune<br>Acme<br>2026-10-06", html)
        self.assertIn('<h3 class="doc-chapter">Revision History</h3>', html)
        self.assertIn("<td>Initial draft</td>", html)
        for chapter in ("1. Introduction", "2. Design Overview", "3. Design Views", "4. Decisions"):
            self.assertIn(f'<h3 class="doc-chapter">{chapter}</h3>', html)
        self.assertLess(html.index("Revision History"), html.index("1. Introduction"))
        self.assertNotIn("Table of Contents", html)
        self.assertNotIn("#11-document-purpose", html)
        self.assertNotIn("<!--", html)

    def test_part_markup_and_heading_levels(self):
        html = sdd().original_html(read("full.md"))
        part = doc_part(html, "1-6")
        self.assertIn('<h4 class="doc-h">1.6 Requirements</h4>', part)
        self.assertIn('data-chip="1.6"', part)
        self.assertIn('href="#s-1-6"', part)
        self.assertIn('<div class="doc-body" data-sel="1.6">', part)
        self.assertIn("<table>", part)
        self.assertIn("<h5>2.2.1 Context</h5>", doc_part(html, "2-2"))
        self.assertIn('<h4 class="doc-h">V4 Deployment: where it runs and how it is removed</h4>', doc_part(html, "v4"))
        self.assertIn('<pre class="mermaid">', doc_part(html, "v4"))
        self.assertIn('<h3 class="doc-h">5. Appendixes</h3>', doc_part(html, "5"))

    def test_partial_has_a_part_per_review_entry(self):
        text = read("partial.md")
        ids = re.findall(r'<section class="doc-part" id="d-[^"]+" data-id="([^"]+)"', sdd().original_html(text))
        self.assertEqual(ids, [e["id"] for e in sdd().review_data(text)["entries"]])

    def test_markdown_heading_level_option(self):
        self.assertIn("<h5>Sub</h5>", sdd().md_to_html("#### Sub\n\ntext", heading_tag="h5"))
        self.assertIn("<h3>Sub</h3>", sdd().md_to_html("#### Sub\n\ntext"))

    def test_review_page_links_cards_and_parts(self):
        text = read("full.md")
        page = sdd().review_page(text, SAMPLE_NOTES, source_label="x.md")
        self.assertIn('<article id="original"', page)
        self.assertEqual(page.count('<section class="doc-part"'), 15)
        for e in sdd().review_data(text)["entries"]:
            slug = re.sub(r"[^A-Za-z0-9]+", "-", e["id"]).strip("-").lower()
            self.assertIn(f'<div class="content" data-sel="{e["id"]}">', page)
            self.assertIn(f'href="#d-{slug}"', page)
            self.assertIn(f'href="#s-{slug}"', doc_part(page, slug))


class ReleaseTests(unittest.TestCase):
    def test_release_cli_author_order(self):
        with tempfile.TemporaryDirectory() as d:
            for extra, stdin, want in [
                ((), None, "eeeemune"),
                (("--options", "-"), "author=Ada Lovelace\n", "Ada Lovelace"),
                (("--author", "Grace Hopper", "--options", "-"), "author=Ada Lovelace\n", "Grace Hopper"),
            ]:
                path = Path(d) / "sdd.md"
                path.write_text(read("full.md"), encoding="utf-8")
                r = run_cli("release", path, "--reason", "R", "--date", "2026-10-13", *extra, stdin=stdin)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(sdd().revision_rows(path.read_text(encoding="utf-8"))[-1][0], want)

    def test_release_versions(self):
        src = sdd().set_front_matter(read("full.md"), {"version": "0.4"})
        out, info = sdd().release(src, reason="First published version", author="eeeemune", date="2026-10-07")
        fm = sdd().parse_front_matter(out)
        self.assertEqual((fm["version"], fm["status"], fm["updated"]), ("1.0", "published", "2026-10-07"))
        self.assertEqual(info["from"], "0.4")
        self.assertEqual(info["to"], "1.0")
        rows = sdd().revision_rows(out)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1], ["eeeemune", "2026-10-07", "First published version", "1.0"])
        self.assertIn("\nVersion 1.0  \n", out)
        out2, info2 = sdd().release(out, reason="Added V5", author="eeeemune", date="2026-10-08")
        self.assertEqual(info2["to"], "1.1")
        self.assertEqual(len(sdd().revision_rows(out2)), 3)


class GuideTests(unittest.TestCase):
    def test_guide_covers_template(self):
        path = ROOT / "core" / "sections.md"
        self.assertTrue(path.exists(), f"{path} does not exist yet")
        guide = path.read_text(encoding="utf-8")
        for sid in WALK_ORDER:
            self.assertRegex(guide, rf"(?m)^## {re.escape(sid)} \S")

    def test_viewpoint_examples_are_tb(self):
        path = ROOT / "core" / "viewpoints.md"
        self.assertTrue(path.exists(), f"{path} does not exist yet")
        text = path.read_text(encoding="utf-8")
        for name in VIEWPOINTS:
            self.assertRegex(text, rf"(?m)^## 2\.2\.\d+ {re.escape(name)}$")
        self.assertNotRegex(text, r"(?m)^\s*(flowchart|graph)\s+(LR|RL)\b")
        self.assertNotRegex(text, r"direction\s+(LR|RL)")


if __name__ == "__main__":
    unittest.main()
