"""Draw the README graphics as light and dark SVGs.

Usage: python3 .github/readme/draw.py   (writes the SVGs next to this script)
"""
import html
import pathlib
import sys

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
MW = 0.602  # advance of one monospace character, in em

THEMES = {
    "light": dict(bg="#FFFFFF", panel="#F6F8FA", border="#D0D7DE", grid="#E6EAEF", fg="#1F2328", muted="#59636E",
                  accent="#BC5A35", accentbg="#FBEFEA", red="#CF222E", redbg="#FFEBE9", green="#1A7F37",
                  greenbg="#DAFBE1", term="#0D1117", termfg="#E6EDF3", termmuted="#8B949E", termsel="#30363D",
                  termborder="#0D1117", key="#FFFFFF", keyedge="#AFB8C1", keyborder="#D0D7DE", card="#FFFFFF"),
    "dark": dict(bg="#0D1117", panel="#161B22", border="#30363D", grid="#1A2029", fg="#E6EDF3", muted="#9198A1",
                 accent="#E5896A", accentbg="#2B1A14", red="#F85149", redbg="#3A1719", green="#3FB950",
                 greenbg="#12291B", term="#010409", termfg="#E6EDF3", termmuted="#8B949E", termsel="#30363D",
                 termborder="#30363D", key="#2D333B", keyedge="#010409", keyborder="#444C56", card="#0D1117"),
}


def esc(s):
    return html.escape(s, quote=True)


def text(x, y, s, size, fill, weight=400, font=SANS, anchor="start", ls=None, opacity=None):
    extra = f' letter-spacing="{ls}"' if ls else ""
    extra += f' opacity="{opacity}"' if opacity else ""
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def rect(x, y, w, h, fill, stroke=None, rx=8, sw=1, dash=None, opacity=None):
    extra = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    extra += f' stroke-dasharray="{dash}"' if dash else ""
    extra += f' opacity="{opacity}"' if opacity else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{extra}/>'


def mono_width(s, size, ls=0):
    return len(s) * (MW * size + ls)


def pill(x, y, s, size, fg, bg, h=28, padx=12):
    w = mono_width(s, size) + 2 * padx
    return rect(x, y, w, h, bg, rx=h / 2) + text(x + padx, y + h / 2 + size * 0.36, s, size, fg, 500, MONO)


def keycap(x, y, w, h, label, size, t):
    return (rect(x, y + 6, w, h, t["keyedge"], rx=12)
            + rect(x, y, w, h, t["key"], stroke=t["keyborder"], rx=12, sw=1.5)
            + text(x + w / 2, y + h / 2 + size * 0.36, label, size, t["fg"], 600, MONO, "middle"))


def arrow(x1, y, x2, color):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 2}" y2="{y}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            f'<path d="M{x2 - 9} {y - 6} L{x2} {y} L{x2 - 9} {y + 6}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def svg(w, h, alt, body, t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{esc(alt)}"><title>{esc(alt)}</title>'
            + rect(0.5, 0.5, w - 1, h - 1, t["bg"], stroke=t["border"], rx=16) + body + "</svg>\n")


def panel_head(x, label, title, color, t):
    return text(x, 68, label, 13, color, 700, MONO, ls=2) + text(x, 100, title, 24, t["fg"], 650)


ITERATE_ALT = ("Before: 4 corrections, 4 human checks. You ask for preview environments, then ask again to delete "
               "them when the PR closes, to keep them off the prod database, and to cap how many run, with a human "
               "check after each round. After: 4 requirements, written once. R1 reachable within 10 minutes, "
               "verified by curl /healthz giving 200. R2 deleted within 1 hour of the PR closing, verified by the "
               "namespace being gone. R3 cannot reach production databases, verified by a failed connection to the "
               "database port. R4 at most 15 run at once, verified by PR 16 getting capacity full.")

BEFORE = ["> add preview environments for PRs", "> delete them when the PR closes",
          "> keep them off the prod database", "> how many can run at once?"]
AFTER = [("R1", "Reachable within 10 minutes", "verification: curl /healthz gives 200"),
         ("R2", "Deleted within 1 hour of PR close", "verification: namespace pr-123 is gone"),
         ("R3", "Cannot reach production databases", "verification: connect to DB port fails"),
         ("R4", "At most 15 run at once", 'verification: PR 16 gets "capacity full"')]


def iterate(t):
    w, h = 1200, 500
    lx, rx_, pw = 28, 620, 552
    body = rect(lx, 24, pw, 452, t["panel"], rx=14) + rect(rx_, 24, pw, 452, t["panel"], rx=14)
    body += panel_head(lx + 28, "BEFORE", "4 corrections, 4 human checks", t["red"], t)
    body += panel_head(rx_ + 28, "AFTER", "4 requirements, written once", t["green"], t)
    for i, prompt in enumerate(BEFORE):
        ry = 136 + i * 84
        cx, cy = lx + 44, ry + 30
        if i < 3:
            body += (f'<line x1="{cx}" y1="{cy + 18}" x2="{cx}" y2="{cy + 84 - 18}" stroke="{t["red"]}" '
                     f'stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round" opacity="0.6"/>')
        body += (f'<circle cx="{cx}" cy="{cy}" r="16" fill="{t["redbg"]}" stroke="{t["red"]}" stroke-width="1.5"/>'
                 + text(cx, cy + 5, str(i + 1), 14, t["red"], 700, MONO, "middle"))
        body += text(lx + 76, ry + 24, prompt, 16, t["fg"], 500, MONO)
        body += pill(lx + 76, ry + 36, f"round {i + 1}: human check", 14, t["red"], t["redbg"])
        body += arrow(lx + pw + 10, cy, rx_ - 10, t["muted"])
    for i, (rid, req, ver) in enumerate(AFTER):
        ry = 136 + i * 84
        body += (rect(rx_ + 28, ry + 7, 44, 28, t["green"], rx=7)
                 + text(rx_ + 50, ry + 26, rid, 15, t["bg"], 700, MONO, "middle"))
        body += text(rx_ + 86, ry + 27, req, 18, t["fg"], 600)
        body += pill(rx_ + 86, ry + 38, ver, 14, t["green"], t["greenbg"])
    return svg(w, h, ITERATE_ALT, body, t)


ENTER_ALT = ("Before: one plan, one key. Claude asks 'Here is the design. Proceed?' and you press Enter, approving "
             "it without reading. When it breaks, you do not know which choice broke it. After: you make each call. "
             "Each section opens with a card, Claude drafts 2 or 3 versions and you pick one, each choice becomes a "
             "decision record with the options you turned down, and each part on the review page has a Check "
             "yourself question.")


def enter(t):
    w, h = 1200, 500
    lx, rx_, pw = 28, 620, 552
    body = rect(lx, 24, pw, 452, t["panel"], rx=14) + rect(rx_, 24, pw, 452, t["panel"], rx=14)
    body += panel_head(lx + 28, "BEFORE", "One plan, one key", t["red"], t)
    body += panel_head(rx_ + 28, "AFTER", "You make each call", t["green"], t)
    # terminal
    tx, ty, tw, th = lx + 28, 128, pw - 56, 176
    body += rect(tx, ty, tw, th, t["term"], stroke=t["termborder"], rx=10)
    for k in range(3):
        body += f'<circle cx="{tx + 22 + k * 20}" cy="{ty + 20}" r="6" fill="{t["termmuted"]}" opacity="0.45"/>'
    body += text(tx + 22, ty + 70, "Here is the design. Proceed?", 18, t["termfg"], 500, MONO)
    body += rect(tx + 14, ty + 86, 150, 32, t["termsel"], rx=6)
    body += text(tx + 22, ty + 108, "> 1. Yes", 18, t["termfg"], 700, MONO)
    body += text(tx + 22, ty + 146, "  2. No", 18, t["termmuted"], 500, MONO)
    # the key
    body += keycap(lx + 28, 340, 176, 70, "Enter", 28, t)
    body += text(lx + 232, 368, "Approved without reading", 20, t["red"], 650)
    body += text(lx + 232, 398, "When it breaks, which choice broke it?", 16, t["muted"], 400)
    # the four calls
    x, cw = rx_ + 28, pw - 56
    body += text(x, 140, "Each section opens with a card", 14, t["muted"], 500)
    body += rect(x, 150, cw, 60, t["card"], stroke=t["border"], rx=10)
    body += text(x + 16, 176, "Section 2 of 11 · 1.6 Requirements", 16, t["fg"], 650)
    body += text(x + 16, 198, "What it is · Why it matters · You decide", 13, t["muted"], 500, MONO)
    body += text(x, 240, "Claude drafts, you pick one", 14, t["muted"], 500)
    for k, name in enumerate(["Draft A", "Draft B", "Draft C"]):
        cx = x + k * 132
        on = k == 1
        body += rect(cx, 250, 120, 36, t["accentbg"] if on else t["card"], stroke=t["accent"] if on else t["border"],
                     rx=18, sw=1.5 if on else 1)
        body += f'<circle cx="{cx + 20}" cy="268" r="6" fill="none" stroke="{t["accent"] if on else t["muted"]}" stroke-width="1.5"/>'
        if on:
            body += f'<circle cx="{cx + 20}" cy="268" r="3" fill="{t["accent"]}"/>'
        body += text(cx + 34, 273, name, 14, t["accent"] if on else t["fg"], 600, MONO)
    body += text(x, 318, "Each choice becomes a decision record", 14, t["muted"], 500)
    body += rect(x, 328, cw, 60, t["card"], stroke=t["border"], rx=10)
    body += text(x + 16, 354, "ADR-001  One namespace per PR", 16, t["fg"], 650)
    body += pill(x + cw - 16 - mono_width("accepted", 12) - 20, 338, "accepted", 12, t["green"], t["greenbg"], h=24, padx=10)
    body += text(x + 16, 376, "Turned down: vcluster per PR, about 2 min slower to start", 13, t["muted"], 500, MONO)
    body += text(x, 416, "Each part has a Check yourself question", 14, t["muted"], 500)
    body += rect(x, 426, cw, 40, t["card"], stroke=t["accent"], rx=10, dash="5 4")
    body += f'<path d="M{x + 16} 440 L{x + 24} 446 L{x + 16} 452 Z" fill="{t["accent"]}"/>'
    body += text(x + 34, 451, "Check yourself: what cleans up after a failed run?", 15, t["fg"], 500)
    return svg(w, h, ENTER_ALT, body, t)


FLOW_ALT = ("How it works: 1. Write with /sdd-planner:write, picking one of 2 or 3 drafts, one section per turn. "
            "2. Review with /sdd-planner:review, approving each part or marking it Needs changes; Claude fixes "
            "flagged parts and marks them Re-check. 3. Publish with /sdd-planner:publish: lint, bump the version, "
            "and sync to Notion if it is on.")

STEPS = [("Write", "/sdd-planner:write", ["Pick one of 2 or 3 drafts,", "one section per turn"]),
         ("Review", "/sdd-planner:review", ["Approve each part or", "mark it Needs changes"]),
         ("Publish", "/sdd-planner:publish", ["Lint, bump the version,", "sync to Notion if it is on"])]


def flow(t):
    w, h = 1200, 300
    body = ""
    xs = [28, 424, 820]
    cw, ch, y = 352, 168, 28
    for k, (title, cmd, lines) in enumerate(STEPS):
        x = xs[k]
        body += rect(x, y, cw, ch, t["panel"], rx=14)
        body += (f'<circle cx="{x + 42}" cy="{y + 44}" r="18" fill="{t["accent"]}"/>'
                 + text(x + 42, y + 50, str(k + 1), 17, t["bg"], 800, MONO, "middle"))
        body += text(x + 72, y + 54, title, 26, t["fg"], 700)
        body += text(x + 24, y + 98, cmd, 16, t["accent"], 600, MONO)
        body += text(x + 24, y + 130, lines[0], 16, t["muted"], 400)
        body += text(x + 24, y + 152, lines[1], 16, t["muted"], 400)
        if k < 2:
            body += arrow(x + cw + 8, y + ch / 2, xs[k + 1] - 8, t["muted"])
    # the review loop
    x1, x2, yb = xs[1] + 290, xs[1] + 62, y + ch
    body += (f'<path d="M{x1} {yb + 4} C {x1} {yb + 54}, {x2} {yb + 54}, {x2} {yb + 10}" fill="none" '
             f'stroke="{t["accent"]}" stroke-width="2" stroke-dasharray="5 5" stroke-linecap="round"/>'
             f'<path d="M{x2 - 7} {yb + 18} L{x2} {yb + 6} L{x2 + 7} {yb + 18}" fill="none" stroke="{t["accent"]}" '
             f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    body += text(600, yb + 76, "Needs changes: Claude fixes the part and marks it Re-check", 15, t["muted"], 500,
                 anchor="middle")
    return svg(w, h, FLOW_ALT, body, t)


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in [("iterate", iterate), ("enter", enter), ("flow", flow)]:
        for theme, t in THEMES.items():
            (out / f"{name}-{theme}.svg").write_text(fn(t))
    print("wrote", len(list(out.glob("*.svg"))), "files to", out)


if __name__ == "__main__":
    main()
