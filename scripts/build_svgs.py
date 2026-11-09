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


# --------------------------------------------------------------------------
# link badges (local SVGs: no shields.io / camo dependency, so they always render on GitHub)
# Icons: Simple Icons v13 (CC0) filled paths, Lucide "file-user" (ISC) stroked paths.
# --------------------------------------------------------------------------
ICONS = {
    "linkedin": ("fill", ["M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"]),
    "instagram": ("fill", ["M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077"]),
    "gmail": ("fill", ["M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"]),
    "chrome": ("fill", ["M12 0C8.21 0 4.831 1.757 2.632 4.501l3.953 6.848A5.454 5.454 0 0 1 12 6.545h10.691A12 12 0 0 0 12 0zM1.931 5.47A11.943 11.943 0 0 0 0 12c0 6.012 4.42 10.991 10.189 11.864l3.953-6.847a5.45 5.45 0 0 1-6.865-2.29zm13.342 2.166a5.446 5.446 0 0 1 1.45 7.09l.002.001h-.002l-5.344 9.257c.206.01.413.016.621.016 6.627 0 12-5.373 12-12 0-1.54-.29-3.011-.818-4.364zM12 16.364a4.364 4.364 0 1 1 0-8.728 4.364 4.364 0 0 1 0 8.728Z"]),
    "cv": ("stroke", ["M14 2v4a2 2 0 0 0 2 2h4", "M15 18a3 3 0 1 0-6 0",
                      "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z",
                      "M14 13a2 2 0 1 1-4 0 2 2 0 0 1 4 0z"]),
}
BADGES = [("portfolio", "PORTFOLIO", "chrome"), ("cv", "CV", "cv"), ("linkedin", "LINKEDIN", "linkedin"),
          ("instagram", "INSTAGRAM", "instagram"), ("email", "EMAIL", "gmail")]
BADGE_COLORS = {"dark": ("#0a162f", "#ffffff", "none"), "light": ("#ffffff", "#000000", "#000000")}


def badge(theme, label, icon):
    bg, fg, border = BADGE_COLORS[theme]
    h, pad, isz, gap, ls = 28, 12, 14, 8, 1.6
    tw = text_width("sans", label, 11, ls) - ls
    w = round(pad + isz + gap + tw + pad)
    kind, ds = ICONS[icon]
    sc = isz / 24
    if kind == "fill":
        paths = "".join(f'<path d="{d}"/>' for d in ds)
        ic = f'<g transform="translate({pad} {(h-isz)/2}) scale({sc})" fill="{fg}">{paths}</g>'
    else:
        paths = "".join(f'<path d="{d}"/>' for d in ds)
        ic = (f'<g transform="translate({pad} {(h-isz)/2}) scale({sc})" fill="none" stroke="{fg}" '
              f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths}</g>')
    stroke = f' stroke="{border}" stroke-width="1"' if border != "none" else ""
    body = (f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="3" fill="{bg}"{stroke}/>' + ic
            + f'<text class="sans" x="{pad+isz+gap}" y="{h/2+4}" font-size="11" letter-spacing="{ls}" '
              f'fill="{fg}">{escape(label)}</text>')
    chars = "".join(sorted(set(label)))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{escape(label)}">\n<style>{font_css(chars)}.sans{{font-family:"ECSans",Geist,system-ui,sans-serif}}'
            f'</style>\n{body}\n</svg>\n')


SECTIONS = [("01", "who am i"), ("02", "projects"), ("03", "telemetry"), ("04", "stack")]
VISUALS = {"whoami": whoami, "projects": projects, "telemetry": telemetry, "stack": stack, "footer": footer}


def main():
    live = {"langs": (get_languages(), langs), "activity": (get_contributions(), activity)}
    files = []
    for theme in THEMES:
        d = OUT / theme
        d.mkdir(parents=True, exist_ok=True)
        keep = {f"s{n}.svg" for n, _ in SECTIONS} | {f"{k}.svg" for k in VISUALS} | {f"badge-{k}.svg" for k, _, _ in BADGES}
        for name, (data, fn) in live.items():
            if data:
                files.append((d / f"{name}.svg", fn(theme, data)))
            elif (d / f"{name}.svg").exists():
                keep.add(f"{name}.svg")
            keep.add(f"{name}.svg")
        for old in d.glob("*.svg"):  # drop stale files from removed sections
            if old.name not in keep:
                old.unlink()
        for key, label, icon in BADGES:
            files.append((d / f"badge-{key}.svg", badge(theme, label, icon)))
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
