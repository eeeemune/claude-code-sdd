"""R8: open the review page in every condition it can be opened in, in headless Chrome, and check what it shows.

Usage, from the sdd/ folder:
    python3 tests/page_conditions.py [--sdd tests/fixtures/full.md] [--chrome PATH]

Each condition replaces the claude.ai runtime with a stand-in that grants or refuses one capability, opens the page,
and reads back what is visible: every part's text and diagram source, which controls are enabled or hidden, the notice,
sideways overflow, and the background color. Not part of the unittest suite, because it needs Chrome.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDD = HERE.parent / "scripts" / "sdd.py"
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

# A stand-in for window.claude: each capability is granted (an object) or refused (null), as on claude.ai.
STUB = """<script>
(function () {
  var grant = %(grant)s;
  if (!grant.runtime) return;
  if (grant.theme) document.documentElement.setAttribute("data-theme", grant.theme);
  var caps = {
    db: { collection: function () { return { onSnapshot: function (cb) { cb({ docs: [] }); return function () {}; },
                                             doc: function () { return {}; } }; },
          doc: function () { return { set: async function () {} }; } },
    user: { id: async function () { return "u1"; }, can: async function () { return true; },
            profiles: async function () { return {}; } },
    sample: async function () { return { text: "" }; },
    comments: { openComposer: async function () {} }
  };
  window.claude = { use: async function (name) { return grant[name] ? caps[name] : null; } };
})();
</script>
"""

PROBE = """<script>
setTimeout(function () {
  function all(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
  function shown(el) { return el.getClientRects().length > 0; }  // drawn on screen, whatever the attributes say
  var notice = document.getElementById("notice");
  document.body.setAttribute("data-probe", JSON.stringify({
    entries: all("section.entry").length,
    with_text: all("section.entry .content").filter(function (e) { return e.textContent.trim().length > 0; }).length,
    parts: all(".doc-part").length,
    diagrams: all("pre.mermaid").length,
    approve_enabled: all('[data-action="approve"]').filter(function (b) { return !b.disabled; }).length,
    ask_shown: all(".ask").filter(shown).length,
    comment_shown: all('[data-action="comment"]').filter(shown).length,
    notice: shown(notice) ? notice.textContent : "",
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    background: getComputedStyle(document.body).backgroundColor
  }));
}, 1500);
</script>
"""

FULL = {"runtime": True, "db": True, "user": True, "sample": True, "comments": True}
CONDITIONS = [
    ("all capabilities", FULL, 1280),
    ("database refused", dict(FULL, db=False), 1280),
    ("Ask refused", dict(FULL, sample=False), 1280),
    ("outside claude.ai", {"runtime": False}, 1280),
    ("narrow window", FULL, 500),  # headless Chrome lays out no narrower than about 500px
    ("dark mode", dict(FULL, theme="dark"), 1280),
]
SAVE_ONLY_ON_CLAUDE = "saved only on claude.ai"


def find_chrome(given: str | None) -> str:
    for candidate in ([given] if given else CHROME_CANDIDATES):
        path = candidate if Path(candidate).exists() else shutil.which(candidate)
        if path:
            return path
    sys.exit("page_conditions: Chrome not found; pass --chrome PATH")


def probe(chrome: str, page: str, grant: dict, width: int, folder: Path) -> dict:
    target = folder / f"page-{len(list(folder.iterdir()))}.html"
    target.write_text(STUB % {"grant": json.dumps(grant)} + page + PROBE, encoding="utf-8")
    dom = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", f"--window-size={width},900", "--virtual-time-budget=4000",
         "--dump-dom", target.as_uri()],
        capture_output=True, text=True, timeout=90,
    ).stdout
    m = re.search(r'data-probe="([^"]*)"', dom)
    if not m:
        raise RuntimeError("the page did not report back; is Chrome working?")
    return json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&"))


def expected(name: str, grant: dict, n: int) -> dict:
    runtime = grant.get("runtime", False)
    return {
        "approve_enabled": n if runtime and grant.get("db") else 0,
        "ask_shown": n if runtime and grant.get("sample") else 0,
        "comment_shown": n if runtime and grant.get("comments") else 0,
        "notice": SAVE_ONLY_ON_CLAUDE if not (runtime and grant.get("db")) else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sdd", default=str(HERE / "fixtures" / "full.md"))
    parser.add_argument("--chrome")
    args = parser.parse_args()
    chrome = find_chrome(args.chrome)
    text = Path(args.sdd).read_text(encoding="utf-8")
    entries = len(json.loads(subprocess.run([sys.executable, str(SDD), "review-data", args.sdd],
                                            capture_output=True, text=True, check=True).stdout)["entries"])
    diagrams = 2 * text.count("```mermaid")  # each diagram appears in its card and in the Original tab
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        built = folder / "built.html"
        subprocess.run([sys.executable, str(SDD), "review-page", args.sdd, "--out", str(built)],
                       capture_output=True, check=True)
        page = built.read_text(encoding="utf-8")
        for name, grant, width in CONDITIONS:
            got = probe(chrome, page, grant, width, folder)
            want = expected(name, grant, entries)
            problems = []
            if (got["entries"], got["with_text"], got["parts"]) != (entries, entries, entries):
                problems.append(f"parts shown {got['entries']}/{got['with_text']}/{got['parts']}, expected {entries}")
            if got["diagrams"] != diagrams:
                problems.append(f"diagrams {got['diagrams']}, expected {diagrams}")
            for key in ("approve_enabled", "ask_shown", "comment_shown"):
                if got[key] != want[key]:
                    problems.append(f"{key} {got[key]}, expected {want[key]}")
            if bool(got["notice"]) != bool(want["notice"]) or want["notice"] not in got["notice"]:
                problems.append(f"notice {got['notice']!r}")
            if got["overflow"] > 0:
                problems.append(f"{got['overflow']}px of sideways scroll at {width}px")
            if grant.get("theme") == "dark":
                rgb = [int(v) for v in re.findall(r"\d+", got["background"])[:3]]
                if sum(rgb) > 150:
                    problems.append(f"background {got['background']} is not dark")
            failures += bool(problems)
            print(f"{'FAIL' if problems else 'ok  '} {name}: " + ("; ".join(problems) or
                  f"{entries} parts, {got['diagrams']} diagrams, approve {got['approve_enabled']}, "
                  f"ask {got['ask_shown']}, comment {got['comment_shown']}, notice {'yes' if got['notice'] else 'no'}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
