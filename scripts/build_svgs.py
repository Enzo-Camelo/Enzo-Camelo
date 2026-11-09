#!/usr/bin/env python3
"""Generate the animated README SVGs (light + dark) into assets/light and assets/dark.

Edit CONTENT below (search for TODO) and run:  python scripts/build_svgs.py
Needs: pip install fonttools, and the font files Geist-Variable.ttf + PlayfairDisplay-Variable.ttf
in _local/fonts/ (gitignored; both are OFL, available from github.com/vercel/geist-font and github.com/google/fonts).
Fonts: Playfair Display (numbers, titles, subtitles) + Geist (body text), both OFL, embedded
in each SVG as a subsetted base64 WOFF so they render on GitHub (no external font loading).
"""
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import base64, io, re
from html import unescape
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

# --------------------------------------------------------------------------
# CONTENT — everything the SVGs say lives here.
# --------------------------------------------------------------------------
CONTENT = {
    "name": "Enzo Camelo",
    "location": "Joinville, SC, Brazil",
    "whoami": [
        ("AI Engineer based in Joinville, SC, Brazil.", "bone", 17),
        ("building across the stack — Python APIs · React interfaces · PostgreSQL · automation.", "bone", 17),
        ("drawn to products where generative AI meets solid backend engineering and clean UX.", "bone", 16),
    ],
    "focus": "AI-integrated systems · Python backend · React frontend · workflow automation",
    "status": "open to opportunities — remote · hybrid · on-site",
    "github": "Enzo-Camelo",
    "projects": [
        {
            "title": "TRANSLIVE",
            "desc": ["Real-time audio transcription and translation for conferences, talks and",
                     "international presentations. Speech to text, translated, shown as live captions."],
            "stack": "PYTHON · FLASK",
            "link": "PRIVATE",
        },
        {
            "title": "DOCBOARD",
            "desc": ["Clinical and financial monitoring dashboard for Hemodynamics.",
                     "Goal management, physician productivity and patient safety indicators in one panel."],
            "stack": "PYTHON · REACT · SUPABASE · FASTAPI · VITE",
            "link": "github.com/Enzo-Camelo/DocBoard",
        },
    ],
    # estimated focus distribution (label, percent) — adjust to taste
    "focus_bars": [("python", 35), ("react / js", 25), ("ai & automation", 20), ("sql", 12), ("devops", 8)],
    "counters": [("2", "PROJECTS DOCUMENTED"), ("4", "STACK LAYERS"), ("∞", "PROMPTS THIS WEEK")],
    "stack": [
        ("LANGUAGES", "Python · JavaScript · SQL"),
        ("WEB", "React · Next.js · Vite · Tailwind CSS"),
        ("BACKEND", "FastAPI · Django · Flask · REST APIs"),
        ("DATA", "PostgreSQL · MySQL · Supabase"),
        ("AI", "n8n · LLM APIs · generative AI workflows"),
        ("TOOLING", "Docker · CI/CD · Git · GitHub · Figma"),
    ],
    "footer_right": "Joinville, BR  ·  © 2026",
}

# --------------------------------------------------------------------------
# Theme tokens
# --------------------------------------------------------------------------
THEMES = {  # dark mode: light blue + white only. light mode: dark blue + black only.
    "light": dict(bone="#000000", muted="#1e4f9c", dim="#5d83bf", rule="rgba(10,61,145,.30)",
                  accent="#0a3d91", ghost="rgba(10,61,145,.12)", node="#ffffff"),
    "dark": dict(bone="#ffffff", muted="#8fd8ff", dim="#6cc4f5", rule="rgba(143,216,255,.30)",
                 accent="#8fd8ff", ghost="rgba(143,216,255,.16)", node="#000000"),
}

BASE_CSS = """
.sans{font-family:"ECSans",Geist,system-ui,"Segoe UI",sans-serif}
.serif{font-family:"ECSerif","Playfair Display",Georgia,serif;font-feature-settings:"lnum" 1;font-variant-numeric:lining-nums}
.rise{opacity:0;animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.fade{opacity:0;animation:fade .7s ease forwards}
@keyframes fade{to{opacity:1}}
.draw{stroke-dasharray:1000;stroke-dashoffset:1000;animation:draw 1.4s cubic-bezier(.6,0,.2,1) forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.bar{transform:scaleX(0);animation:grow 1.1s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes grow{to{transform:scaleX(1)}}
.pop{opacity:0;transform:scale(.6);animation:pop .6s cubic-bezier(.2,.9,.3,1.3) forwards}
@keyframes pop{to{opacity:1;transform:scale(1)}}
.flow{stroke-dasharray:4 7;animation:march 1.2s linear infinite}
@keyframes march{to{stroke-dashoffset:-22}}
.breathe{animation:breathe 2.4s ease-in-out infinite}
@keyframes breathe{0%,100%{opacity:1}50%{opacity:.35}}
.ping{animation:ping 2.4s ease-out infinite}
@keyframes ping{0%{transform:scale(.4);opacity:.9}80%,100%{transform:scale(2.8);opacity:0}}
@media (prefers-reduced-motion:reduce){
 .rise,.fade,.draw,.bar,.pop,.flow,.breathe,.ping{animation:none}
 .rise,.fade,.pop{opacity:1;transform:none}.draw{stroke-dashoffset:0}.bar{transform:none}.ping{opacity:0}
}
"""


FONT_DIR = ROOT / "_local" / "fonts"  # local only (gitignored); see docstring
FONT_SPECS = {"sans": ("Geist-Variable.ttf", 400, "ECSans"),
              "serif": ("PlayfairDisplay-Variable.ttf", 500, "ECSerif")}
_font_bytes = {}


def _static(kind):
    """Variable font pinned to one weight, as bytes (cached)."""
    if kind not in _font_bytes:
        file, wght, _ = FONT_SPECS[kind]
        f = instancer.instantiateVariableFont(TTFont(FONT_DIR / file), {"wght": wght})
        buf = io.BytesIO()
        f.save(buf)
        _font_bytes[kind] = buf.getvalue()
    return _font_bytes[kind]


def text_width(kind, s, size, ls=0):
    f = TTFont(io.BytesIO(_static(kind)))
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return sum(hmtx[cmap[ord(c)]][0] for c in s) / upm * size + ls * len(s)


def font_css(chars):
    out = ""
    for kind, (_, _, fam) in FONT_SPECS.items():
        f = TTFont(io.BytesIO(_static(kind)))
        missing = [c for c in chars if ord(c) not in f.getBestCmap()]
        if missing:
            print(f"warning: {kind} font lacks {missing}")
        opt = subset.Options()
        opt.flavor = "woff"
        opt.layout_features = ["kern", "liga", "lnum"]
        opt.drop_tables += ["meta"]
        sub = subset.Subsetter(opt)
        sub.populate(text=chars)
        sub.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff"
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        out += f'@font-face{{font-family:"{fam}";src:url(data:font/woff;base64,{b64}) format("woff")}}\n'
    return out


def doc(theme, w, h, label, body):
    t = THEMES[theme]
    root = ";".join(f"--{k}:{v}" for k, v in t.items())
    chars = "".join(sorted(set("".join(unescape(m) for m in re.findall(r">([^<>]+)</text>", body)))))
    return (f'<svg viewBox="0 0 {w} {h}" fill="none" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{escape(label)}">\n'
            f'<style>{font_css(chars)}:root{{{root}}}{BASE_CSS}</style>\n{body}\n</svg>\n')


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def T(x, y, s, size=15, fill="bone", ls=None, anchor=None, extra="", f="sans"):
    a = f' letter-spacing="{ls}"' if ls is not None else ""
    an = f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text class="{f}" x="{x}" y="{y}" font-size="{size}" '
            f'fill="var(--{fill})"{a}{an} {extra}>{escape(s)}</text>')


def g(cls, delay, inner, extra=""):
    return f'<g class="{cls}" style="animation-delay:{delay}s;{extra}">{inner}</g>'


def line(x1, y1, x2, y2, stroke="rule", op=None, cls="", delay=0):
    o = f' opacity="{op}"' if op else ""
    st = f' style="animation-delay:{delay}s"' if cls else ""
    c = f' class="{cls}"' if cls else ""
    return (f'<line{c}{st} x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="var(--{stroke})" stroke-width="1"{o}/>')


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------
def section_header(theme, num, name):
    ls = 8  # letter-spacing of the title
    title = name.upper()
    x1 = 128 + text_width("serif", title, 15, ls) + 18
    body = (g("fade", 0.1, T(48, 68, num, 52, "ghost", f="serif") + T(128, 58, title, 15, "accent", ls, f="serif"))
            + line(round(x1), 53, 952, 53, cls="draw", delay=0.2))
    return doc(theme, 1000, 92, f"Section {num} — {name}", body)


def whoami(theme):
    c = CONTENT
    b = ""
    y = 32
    for i, (s, fill, size) in enumerate(c["whoami"]):
        b += g("rise", 0.1 + i * 0.12, T(48, y, s, size, fill))
        y += 28
    b += line(48, 116, 952, 116, op=".5", cls="fade", delay=0.5)
    rows = [("FOCUS", c["focus"], "bone", 148), ("STATUS", c["status"], "bone", 182),
            ("BASED", c["location"], "bone", 216)]
    for i, (k, v, fill, yy) in enumerate(rows):
        b += g("rise", 0.5 + i * 0.15, T(48, yy, k, 12, "muted", 2.5, f="serif") + T(154, yy, v, 16, fill))
    return doc(theme, 1000, 236, "whoami — bio, focus, status", b)


def projects(theme):
    ps = CONTENT["projects"]
    card = 150
    h = 30 + card * len(ps)
    b = ""
    for i, p in enumerate(ps):
        y0 = 30 + i * card
        inner = (T(48, y0 + 20, f"{i+1:02d} /", 13, "accent", 2, f="serif") + T(100, y0 + 20, p["title"], 17, "accent", 2, f="serif")
                 + T(952, y0 + 20, p["link"], 12, "muted", 1, "end")
                 + T(48, y0 + 52, p["desc"][0], 15, "bone") + T(48, y0 + 74, p["desc"][1], 15, "bone")
                 + T(48, y0 + 108, p["stack"], 12, "accent", 2)
                 + line(48, y0 + 132, 952, y0 + 132, op=".5"))
        b += g("rise", 0.15 + i * 0.25, inner)
    return doc(theme, 1000, h, "Featured projects", b)


def telemetry(theme):
    c = CONTENT
    b = (T(48, 28, "TELEMETRY — WHAT THE HANDS ARE DOING", 12, "muted", 3.5, f="serif")
         + T(952, 28, "FIG. 01", 12, "muted", 3.5, anchor="end", f="serif") + line(48, 40, 952, 40)
         + line(560, 64, 560, 280, op=".4"))
    b += T(48, 78, "FOCUS DISTRIBUTION · EST.", 12, "dim", 2, f="serif")
    y = 108
    for i, (lab, pct) in enumerate(c["focus_bars"]):
        wd = round(pct / 35 * 380)
        fill = "accent" if i == 0 else "bone"
        b += (T(48, y, lab, 12, "bone")
              + f'<rect class="bar" style="transform-origin:48px {y+8}px;animation-delay:{.3+i*.15}s" x="48" '
                f'y="{y+8}" width="{wd}" height="6" fill="var(--{fill})"/>'
              + T(48 + wd + 10, y + 15, f"{pct}%", 11, "muted"))
        y += 38
    y = 118
    for i, (n, lab) in enumerate(c["counters"]):
        b += g("rise", 0.5 + i * 0.2,
               T(600, y, n, 48, "accent", f="serif") + T(680, y - 8, lab, 11, "bone", 2))
        y += 66
    return doc(theme, 1000, 280, "Telemetry: focus distribution and counters", b)


# ---- live data (GitHub public API). Snapshots: re-run this script to refresh. ----
import json, urllib.request

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "enzo-readme-builder"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def get_languages():
    try:
        repos = fetch_json(f"https://api.github.com/users/{CONTENT['github']}/repos?per_page=100")
        tot = {}
        for r in repos:
            if r.get("fork"):
                continue
            for lang, n in fetch_json(r["languages_url"]).items():
                tot[lang] = tot.get(lang, 0) + n
        s = sum(tot.values())
        if not s:
            return None
        return [(k, v / s * 100) for k, v in sorted(tot.items(), key=lambda kv: -kv[1])[:6]]
    except Exception as e:  # offline / rate-limited: keep the existing file
        print("languages skipped:", e)
        return None


def get_contributions():
    try:
        d = fetch_json(f"https://github-contributions-api.jogruber.de/v4/{CONTENT['github']}?y=last")
        return d["contributions"], d["total"]["lastYear"]
    except Exception as e:
        print("contributions skipped:", e)
        return None


def langs(theme, data):
    h = 70 + 36 * len(data)
    b = (T(48, 28, "TOP LANGUAGES — BY CODE SIZE", 12, "muted", 3.5, f="serif")
         + T(952, 28, "FIG. 02", 12, "muted", 3.5, anchor="end", f="serif") + line(48, 40, 952, 40))
    top = data[0][1]
    for i, (name, pct) in enumerate(data):
        y = 82 + i * 36
        wd = max(4, round(pct / top * 560))
        fill = "accent" if i == 0 else "bone"
        b += (T(48, y + 9, name.lower(), 13, "bone")
              + f'<rect x="200" y="{y}" width="560" height="10" stroke="var(--rule)" fill="none"/>'
              + f'<rect class="bar" style="transform-origin:200px {y}px;animation-delay:{.2+i*.12}s" '
                f'x="200" y="{y}" width="{wd}" height="10" fill="var(--{fill})"/>'
              + T(780, y + 9, f"{pct:.1f}%", 13, "muted"))
    return doc(theme, 1000, h, "Most used languages", b)


def activity(theme, data):
    days, total = data
    days = days[-371:]
    pad = days[0]["date"]
    import datetime as dt
    first = dt.date.fromisoformat(pad)
    offset = (first.weekday() + 1) % 7  # Sunday-first rows
    cells = [None] * offset + days
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]
    size, gap = 12, 3
    x0 = round((1000 - len(weeks) * (size + gap)) / 2)
    b = (T(48, 28, "CONTRIBUTION TELEMETRY — LAST 12 MONTHS", 12, "muted", 3.5, f="serif")
         + T(952, 28, f"{total} CONTRIBUTIONS", 12, "accent", 3.5, anchor="end", f="serif") + line(48, 40, 952, 40))
    op = {0: None, 1: .3, 2: .5, 3: .75, 4: 1}
    for wi, wk in enumerate(weeks):
        col = ""
        for di, cell in enumerate(wk):
            if cell is None:
                continue
            lv = cell["level"]
            x, y = x0 + wi * (size + gap), 62 + di * (size + gap)
            if lv == 0:
                col += f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="var(--rule)" opacity=".55"/>'
            else:
                col += (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="2" '
                        f'fill="var(--accent)" opacity="{op[lv]}"/>')
        b += g("fade", round(0.1 + wi * 0.025, 3), col)
    return doc(theme, 1000, 62 + 7 * (size + gap) + 18, "GitHub contribution activity", b)


def stack(theme):
    rows = CONTENT["stack"]
    h = 20 + 32 * len(rows)
    b = line(162, 8, 162, h - 8, op=".4")
    for i, (k, v) in enumerate(rows):
        y = 32 + i * 32
        b += g("rise", 0.1 + i * 0.1, T(48, y, k, 13, "muted", 1.5, f="serif") + T(180, y, v, 16, "bone"))
    return doc(theme, 1000, h, "Technical stack", b)


def footer(theme):
    b = (line(48, 24, 952, 24, cls="draw", delay=0.1)
         + '<circle class="ping" cx="60" cy="64" r="5" stroke="var(--accent)" fill="none" style="transform-origin:60px 64px"/>'
         + '<circle class="breathe" cx="60" cy="64" r="4" fill="var(--accent)"/>'
         + T(82, 62, "STATUS — BUILDING", 13, "accent", 3, f="serif")
         + T(82, 82, "probably in an editor, probably running a model", 12, "bone", 1)
         + T(952, 66, CONTENT["footer_right"].replace("  ", "  "), 16, "muted", anchor="end"))
    return doc(theme, 1000, 110, "Status: building. Joinville, Brazil.", b)


SECTIONS = [("01", "who am i"), ("02", "projects"), ("03", "telemetry"), ("04", "stack")]
VISUALS = {"whoami": whoami, "projects": projects, "telemetry": telemetry, "stack": stack, "footer": footer}


def main():
    live = {"langs": (get_languages(), langs), "activity": (get_contributions(), activity)}
    files = []
    for theme in THEMES:
        d = OUT / theme
        d.mkdir(parents=True, exist_ok=True)
        keep = {f"s{n}.svg" for n, _ in SECTIONS} | {f"{k}.svg" for k in VISUALS}
        for name, (data, fn) in live.items():
            if data:
                files.append((d / f"{name}.svg", fn(theme, data)))
            elif (d / f"{name}.svg").exists():
                keep.add(f"{name}.svg")
            keep.add(f"{name}.svg")
        for old in d.glob("*.svg"):  # drop stale files from removed sections
            if old.name not in keep:
                old.unlink()
        for num, name in SECTIONS:
            files.append((d / f"s{num}.svg", section_header(theme, num, name)))
        for name, fn in VISUALS.items():
            files.append((d / f"{name}.svg", fn(theme)))
    for path, text in files:
        ET.fromstring(text)  # raises if the SVG is not well-formed XML
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} svgs to {OUT}")


if __name__ == "__main__":
    main()
