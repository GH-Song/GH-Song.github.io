#!/usr/bin/env python3
"""
gh-song.github.io — static site generator. Python 3.8+, standard library only.

    python3 build.py              build into _site/
    python3 build.py --serve      build, then serve http://localhost:8000
    python3 build.py --pdf        also print /cv/ to static/files/Gookho_Song_CV.pdf (needs Google Chrome)

All text lives in content/*.json. A field is either a plain string (same in both
languages) or {"en": "...", "ko": "..."}. Inline **bold**, *italic* and
[text](url) are understood everywhere. Never edit _site/ — it is regenerated.
"""
import argparse
import datetime as dt
import functools
import hashlib
import html
import http.server
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
OUT = ROOT / "_site"
LANGS = ("en", "ko")
HOME = {"en": "/", "ko": "/ko/"}
RESEARCH_PAGE = {"en": "/research/", "ko": "/ko/research/"}
CV_PAGE = {"en": "/cv/", "ko": "/ko/cv/"}


# ─────────────────────────────────────────────────────────────── helpers ──

def load(name):
    path = CONTENT / f"{name}.json"
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"✗ {path.relative_to(ROOT)} line {e.lineno} col {e.colno}: {e.msg}")


def T(v, lang):
    """Pick the language variant of a field."""
    if isinstance(v, dict) and ("en" in v or "ko" in v):
        return v.get(lang) or v.get("en") or v.get("ko") or ""
    return "" if v is None else v


esc = functools.partial(html.escape, quote=True)


def md(s):
    """Escape, then allow **bold**, *italic*, [text](url) and line breaks."""
    s = esc(str(s))
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    # closing * may touch a following word: Korean particles attach directly (*무질서*로)
    s = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: link(m.group(2), m.group(1), raw=True), s)
    return s.replace("\n", "<br>")


def link(url, text, cls="", raw=False):
    """<a>; off-site links open in a new tab. `text` is escaped unless raw."""
    url = html.unescape(url)
    attrs = [f'href="{esc(url)}"']
    if cls:
        attrs.append(f'class="{cls}"')
    if url.startswith("http") and not url.startswith(SITE["url"]):
        attrs.append('target="_blank" rel="noopener"')
    return f'<a {" ".join(attrs)}>{text if raw else esc(text)}</a>'


def parse_date(s):
    parts = [int(x) for x in str(s).split("-")]
    while len(parts) < 3:
        parts.append(1)
    return dt.date(*parts)


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def fmt_date(s, lang, day=False):
    """2026-08-06 → 'Aug 2026' / '2026.08' (with day=True: 'Aug 6, 2026' / '2026.08.06')."""
    s = str(s)
    d = parse_date(s)
    has_month, has_day = s.count("-") >= 1, s.count("-") >= 2
    if lang == "ko":
        out = str(d.year)
        if has_month:
            out += f".{d.month:02d}"
        if has_day and day:
            out += f".{d.day:02d}"
        return out
    if not has_month:
        return str(d.year)
    if has_day and day:
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    return f"{MONTHS[d.month - 1]} {d.year}"


@functools.lru_cache(None)
def image_size(src):
    """(w, h) of a local webp/png/jpg without third-party libraries."""
    b = (ROOT / src.lstrip("/")).read_bytes()
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        c = b[12:16]
        if c == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if c == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if c == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b):
            marker, size = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + size
    raise ValueError(f"unknown image format: {src}")


def img(src, alt, cls="", eager=False):
    w, h = image_size(src)
    parts = [f'src="{esc(src)}"', f'alt="{esc(alt)}"', f'width="{w}"', f'height="{h}"',
             'fetchpriority="high"' if eager else 'loading="lazy"', 'decoding="async"']
    if cls:
        parts.append(f'class="{cls}"')
    return f"<img {' '.join(parts)}>"


def asset(path):
    """Static URL with a content hash, so browsers never keep a stale CSS/JS."""
    digest = hashlib.sha1((ROOT / path.lstrip("/")).read_bytes()).hexdigest()[:8]
    return f"{path}?v={digest}"


_S = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "mail": f'<g {_S}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></g>',
    "scholar": '<path fill="currentColor" d="M12 3 1.5 9.2 12 15.4l8.6-5.1V16h1.9V9.2L12 3Zm-6.3 9.6v3.6C7.2 18 9.4 19.3 12 19.3s4.8-1.3 6.3-3.1v-3.6L12 16.3l-6.3-3.7Z"/>',
    "github": '<path fill="currentColor" d="M12 1.8a10.2 10.2 0 0 0-3.2 19.9c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.3-3.4-1.3-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.6 1 1.6 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.6-1.4-2.3-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.5-1.3.1-2.7 0 0 .9-.3 2.8 1a9.6 9.6 0 0 1 5.1 0c1.9-1.3 2.8-1 2.8-1 .6 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.3 4.7-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10.2 10.2 0 0 0 12 1.8Z"/>',
    "orcid": '<path fill="currentColor" d="M12 1.8a10.2 10.2 0 1 0 0 20.4 10.2 10.2 0 0 0 0-20.4ZM8.2 17.1H6.6V9.6h1.6v7.5ZM7.4 8.6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm2.8 8.5V9.6h3.3c2.7 0 4 1.9 4 3.8 0 2.1-1.6 3.7-4 3.7h-3.3Zm1.6-1.4h1.6c2 0 2.5-1.5 2.5-2.3 0-1.4-.9-2.4-2.5-2.4h-1.6v4.7Z"/>',
    "doc": f'<g {_S}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/></g>',
}


def icon(name):
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICONS[name]}</svg>'


# ────────────────────────────────────────────────────────────── UI text ──

UI = {
    "en": {
        "skip": "Skip to content",
        "nav": [("publications", "Publications"), ("awards", "Awards"), ("patents", "Patents"),
                ("presentations", "Presentations"), ("press", "Press")],
        "home": "Home", "research": "Research", "cv": "CV", "cv_pdf": "CV (PDF)",
        "main_nav": "Pages", "section_nav": "Sections on this page", "print": "Print",
        "switch_label": "한국어", "switch_title": "한국어로 보기",
        "interests": "Research interests", "overview": "Overview", "news": "News",
        "publications": "Publications", "awards": "Honors & awards", "patents": "Patents",
        "presentations": "Conference presentations", "press": "Press coverage",
        "projects": "Participation in sponsored research", "grants": "Grants", "education": "Education", "skills": "Skills",
        "projects_note": "Projects of Prof. Mooseok Jang (PI), in which I participated as a researcher.",
        "metrics": [("Journal articles", "articles"), ("Citations", "cites"), ("Patent applications", "patents"),
                    ("Awards", "awards"), ("Conference presentations", "talks")],
        "metrics_note": "Citations from Google Scholar, {d}.",
        "advisor": "Advisor: Prof. Mooseok Jang",
        "groups": {"first": "First-author papers", "other": "Awards and other", "coauthor": "Co-authored papers"},
        "ch_cites": "Citations per year",
        "ch_pubs": "Journal articles per year", "ch_first": "First author", "ch_other": "Co-author",
        "filter_all": "All", "filter_first": "First author",
        "preprints": "Preprints",
        "legend": "<strong>G. Song</strong> · † equal contribution (co-first) · * corresponding author",
        "first_badge": "First author", "doi": "DOI", "pdf": "PDF", "code": "Code", "bibtex": "BibTeX",
        "press_n": "Press ({n})", "summary": "Summary", "copied": "BibTeX copied",
        "granted": "Granted", "pending": "Pending", "inventors": "Inventors",
        "press_total": "{n} articles in {m} outlets, {y0}–{y1}. Headlines are quoted as published.",
        "articles": "{n} articles",
        "invention_title": "Before KAIST",
        "updated": "Last updated {d}",
        "research_title": "Research",
        "research_intro": "Summaries of first-author publications († equal contribution). Figures are reproduced from the papers, with credit.",
        "results": "Key results", "other": "Other contributions",
        "paper": "Paper", "back": "← Back to home",
    },
    "ko": {
        "skip": "본문 바로가기",
        "nav": [("publications", "논문"), ("awards", "수상"), ("patents", "특허"),
                ("presentations", "학회 발표"), ("press", "언론 보도")],
        "home": "홈", "research": "연구 소개", "cv": "CV", "cv_pdf": "CV (PDF)",
        "main_nav": "페이지", "section_nav": "이 페이지의 항목", "print": "인쇄",
        "switch_label": "EN", "switch_title": "View in English",
        "interests": "연구 분야", "overview": "요약", "news": "소식",
        "publications": "논문", "awards": "수상", "patents": "특허",
        "presentations": "학회 발표", "press": "언론 보도",
        "projects": "참여 연구과제", "grants": "연구비 수혜", "education": "학력", "skills": "기술",
        "projects_note": "지도교수 장무석 교수(연구책임자)의 과제에 참여연구원으로 참여했습니다.",
        "metrics": [("국제 학술지 논문", "articles"), ("피인용", "cites"), ("특허 출원", "patents"),
                    ("수상", "awards"), ("학회 발표", "talks")],
        "metrics_note": "피인용: Google Scholar, {d} 기준.",
        "advisor": "지도교수: 장무석",
        "groups": {"first": "제1저자 논문", "other": "수상·기타", "coauthor": "공저 논문"},
        "ch_cites": "연도별 피인용",
        "ch_pubs": "연도별 학술지 논문", "ch_first": "제1저자", "ch_other": "공저자",
        "filter_all": "전체", "filter_first": "제1저자",
        "preprints": "프리프린트",
        "legend": "<strong>G. Song</strong> · † 공동 제1저자 (equal contribution) · * 교신저자",
        "first_badge": "제1저자", "doi": "DOI", "pdf": "PDF", "code": "코드", "bibtex": "BibTeX",
        "press_n": "보도 {n}", "summary": "요약", "copied": "BibTeX를 복사했습니다",
        "granted": "등록", "pending": "출원", "inventors": "발명자",
        "press_total": "{y0}–{y1}년 {m}개 매체, {n}건. 기사 제목은 보도된 그대로 옮겼습니다.",
        "articles": "{n}건",
        "invention_title": "KAIST 이전",
        "updated": "최종 수정 {d}",
        "research_title": "연구 소개",
        "research_intro": "제1저자 논문(† 공동 제1저자) 요약입니다. 그림은 각 논문에서 출처와 함께 인용했습니다.",
        "results": "주요 결과", "other": "공동 연구",
        "paper": "논문", "back": "← 홈으로",
    },
}


# ────────────────────────────────────────────────────────── page chrome ──

def header(lang, active=None, alt_paths=None, sections=False):
    """Site header. Tabs are pages only (Home, Research, CV); on the home page a
    second row links to its sections."""
    u = UI[lang]
    tabs = ""
    for key, href in (("home", HOME[lang]), ("research", RESEARCH_PAGE[lang]), ("cv", CV_PAGE[lang])):
        on = ' class="on" aria-current="page"' if key == active else ""
        tabs += f'<a href="{href}"{on}>{esc(u[key])}</a>'
    switch = ""
    if alt_paths:
        other = "ko" if lang == "en" else "en"
        switch = (f'<a class="lang" href="{alt_paths[other]}" hreflang="{other}" lang="{other}" '
                  f'title="{esc(u["switch_title"])}">{esc(u["switch_label"])}</a>')
    sub = ""
    if sections:
        links = "".join(f'<a href="#{k}" data-spy="{k}">{esc(v)}</a>' for k, v in u["nav"])
        sub = f'\n  <div class="subnav"><nav class="wrap subnav-in" aria-label="{esc(u["section_nav"])}">{links}</nav></div>'
    return f"""<header class="top" data-top>
  <div class="wrap top-in">
    <a class="brand" href="{HOME[lang]}">{esc(T(SITE['name'], lang))}</a>
    <nav class="tabs" aria-label="{esc(u['main_nav'])}">{tabs}</nav>
    {switch}
  </div>{sub}
</header>"""


def page(lang, body, title, desc, path, alt_paths=None, active=None, sections=False):
    """alt_paths: {'en': '/…', 'ko': '/ko/…'} for hreflang and the language switch."""
    u = UI[lang]
    url = SITE["url"] + path
    alt = ""
    if alt_paths:
        alt = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE["url"]}{p}">' for l, p in alt_paths.items())
        alt += f'<link rel="alternate" hreflang="x-default" href="{SITE["url"]}{alt_paths["en"]}">'
    ld = json.dumps(person_ld(), ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="Gookho Song (송국호)">
<link rel="canonical" href="{url}">
{alt}
<meta name="theme-color" content="#ffffff">
{verification()}
<meta property="og:type" content="profile">
<meta property="og:site_name" content="Gookho Song · 송국호">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE['url']}/static/img/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{'ko_KR' if lang == 'ko' else 'en_US'}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="{asset('/static/css/site.css')}">
<script type="application/ld+json">{ld}</script>
</head>
<body>
<a class="skip" href="#main">{esc(u['skip'])}</a>
{header(lang, active, alt_paths, sections)}
<main id="main" class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap foot-in">
  <p>© {parse_date(SITE['updated']).year} {esc(T(SITE['name'], lang))}</p>
  <p>{esc(u['updated'].format(d=fmt_date(SITE['updated'], lang, day=True)))}</p>
</div></footer>
<div class="toast" role="status" aria-live="polite" data-toast data-copied="{esc(u['copied'])}"></div>
<script src="{asset('/static/js/site.js')}" defer></script>
</body>
</html>
"""


def verification():
    v = SITE.get("verification", {})
    tags = []
    if v.get("google"):
        tags.append(f'<meta name="google-site-verification" content="{esc(v["google"])}">')
    if v.get("naver"):
        tags.append(f'<meta name="naver-site-verification" content="{esc(v["naver"])}">')
    return "\n".join(tags)


def person_ld():
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Gookho Song",
        "alternateName": "송국호",
        "url": SITE["url"] + "/",
        "image": SITE["url"] + "/static/img/portrait.jpg",
        "email": "mailto:" + SITE["email"],
        "jobTitle": T(SITE["role"], "en"),
        "affiliation": {"@type": "CollegeOrUniversity", "name": "KAIST",
                        "alternateName": "Korea Advanced Institute of Science and Technology",
                        "url": "https://www.kaist.ac.kr"},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": "KAIST"},
                     {"@type": "CollegeOrUniversity", "name": "Inha University"}],
        "knowsAbout": [T(x, "en") for x in SITE["interests"]],
        "award": [T(a["title"], "en") + ", " + T(a["org"], "en") for a in HONORS["awards"]],
        "sameAs": [l["url"] for l in SITE["links"]],
    }


def section(key, title, body):
    return (f'<section class="sec" id="{key}"><h2 class="sec-h">{esc(title)}</h2>'
            f'<div class="sec-b">{body}</div></section>')


# ───────────────────────────────────────────────────────────── derived ──

def journal_papers():
    return [p for p in PUBS if p.get("type", "journal") == "journal"]


def filings(status):
    return [f for p in HONORS["patents"] for f in p["filings"] if f["status"] == status]


def press_articles():
    return [a for a in PRESS["articles"] if a.get("show", True)]


def press_counts():
    arts = press_articles()
    return len(arts), len({a["outlet"] for a in arts})


def authors_html(authors):
    out = []
    for a in authors:
        name = a.rstrip("†*")
        marks = a[len(name):]
        sup = f"<sup>{esc(marks)}</sup>" if marks else ""
        out.append(f"<strong>{esc(name)}</strong>{sup}" if name in ("G. Song", "Gookho Song") else f"{esc(name)}{sup}")
    return ", ".join(out)


def venue_line(p):
    s = f"<em>{esc(p['venue'])}</em>"
    if p.get("volume"):
        s += f" {esc(str(p['volume']))}"
        if p.get("issue"):
            s += f"({esc(str(p['issue']))})"
    if p.get("pages"):
        s += f", {esc(str(p['pages']))}"
    return s + f" ({p['year']})"


def bibtex(p):
    full = p.get("authors_full") or [a.rstrip("†*") for a in p["authors"]]

    def last_first(n):
        parts = n.split()
        return f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else n

    first_last = re.sub(r"[^a-z]", "", full[0].split()[-1].lower())
    word = re.sub(r"[^a-z]", "", next((w for w in p["title"].lower().split() if len(w) > 3), "paper"))
    kind = "misc" if p.get("type") == "preprint" else "article"
    fields = [("title", "{" + p["title"] + "}"), ("author", " and ".join(last_first(n) for n in full)),
              ("journal" if kind == "article" else "howpublished", p["venue"]), ("year", str(p["year"]))]
    for k, src in (("volume", "volume"), ("number", "issue"), ("pages", "pages"), ("doi", "doi")):
        if p.get(src):
            fields.append((k, str(p[src])))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
    return f"@{kind}{{{first_last}{p['year']}{word},\n{body}\n}}"


# ───────────────────────────────────────────────────────────── charts ──

def svg_bars(series, classes, labels, note="", height=150, width=360):
    """Vertical, optionally stacked bar chart. series: {x_label: [v1, v2, …]}."""
    W, H, top, bottom = width, height, 20, 22
    vmax = max(sum(v) for v in series.values()) or 1
    slot = W / len(series)
    bw = min(26, slot * 0.52)
    parts = [f'<line x1="0" y1="{H - bottom}" x2="{W}" y2="{H - bottom}" class="axis"/>']
    for i, (x, vals) in enumerate(series.items()):
        cx, y = slot * (i + 0.5), H - bottom
        for k, v in enumerate(vals):
            h = (H - bottom - top) * v / vmax
            if v:
                parts.append(f'<rect x="{cx - bw / 2:.1f}" y="{y - h:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                             f'class="{classes[k]}"><title>{esc(str(x))}: {v}</title></rect>')
            y -= h
        parts.append(f'<text x="{cx:.1f}" y="{y - 6:.1f}" class="val">{sum(vals)}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{H - 6}" class="lab">{esc(str(x))}</text>')
    legend = ""
    if len(labels) > 1:
        legend = '<ul class="legend">' + "".join(f'<li><i class="{c}"></i>{esc(l)}</li>' for c, l in zip(classes, labels)) + "</ul>"
    cap = f'<p class="chart-note">{esc(note)}</p>' if note else ""
    return (f'<svg viewBox="0 0 {W} {H}" class="bars" role="img" aria-label="{esc(" / ".join(labels))}">'
            f'{"".join(parts)}</svg>{legend}{cap}')


# ──────────────────────────────────────────────────────────── sections ──

def sec_profile(lang):
    u = UI[lang]
    s = SITE
    other = "ko" if lang == "en" else "en"
    links = [link("mailto:" + s["email"], icon("mail") + esc(s["email"]), raw=True)]
    links += [link(l["url"], icon(l["id"]) + esc(l["label"]), raw=True) for l in s["links"]]
    links.append(link("/static/files/Gookho_Song_CV.pdf", icon("doc") + esc(u["cv_pdf"]), raw=True))
    return f"""<section class="profile" id="top">
  {img(s['portrait'], T(s['portrait_alt'], lang), cls='photo', eager=True)}
  <div class="profile-b">
    <h1>{esc(T(s['name'], lang))}<span lang="{other}">{esc(T(s['name_alt'], lang))}</span></h1>
    <p class="role">{esc(T(s['role'], lang))}</p>
    <p class="aff">{esc(u['advisor'])} · {link(s['lab']['url'], s['lab']['name'])}</p>
    <ul class="contact">{''.join(f'<li>{x}</li>' for x in links)}</ul>
  </div>
</section>"""


def sec_interests(lang):
    line = " · ".join(esc(T(x, lang)) for x in SITE["interests"])
    return section("interests", UI[lang]["interests"], f'<p class="interests">{line}</p>')


def sec_overview(lang):
    u = UI[lang]
    journals = journal_papers()
    first = [p for p in journals if "first" in p.get("tags", [])]
    sch = SITE["scholar"]
    values = {"articles": len(journals), "cites": f"{sch['citations']:,}",
              "patents": sum(len(p["filings"]) for p in HONORS["patents"]),      # every national filing, granted or pending
              "awards": len(HONORS["awards"]), "talks": len(TALKS)}
    rows = "".join(f'<tr><th scope="row">{esc(label)}</th><td>{values[k]}</td></tr>' for label, k in u["metrics"])
    ys = [p["year"] for p in journals]
    per_year = {y: [sum(1 for p in first if p["year"] == y), sum(1 for p in journals if p["year"] == y and p not in first)]
                for y in range(min(ys), max(ys) + 1)}
    cites = {int(y): [v] for y, v in sorted(sch["per_year"].items())}
    note = u["metrics_note"].format(d=fmt_date(sch["as_of"], lang))
    body = f"""<div class="ov">
  <table class="metrics"><tbody>{rows}</tbody></table>
  <figure class="mini"><figcaption>{esc(u['ch_cites'])}</figcaption>{svg_bars(cites, ['c1'], [u['ch_cites']], height=190, width=240)}</figure>
  <figure class="mini"><figcaption>{esc(u['ch_pubs'])}</figcaption>{svg_bars(per_year, ['c1', 'c2'], [u['ch_first'], u['ch_other']], height=190, width=240)}</figure>
</div>
<p class="note ov-note">{esc(note)}</p>"""
    return section("overview", u["overview"], body)


def pub_entry(p, lang):
    u = UI[lang]
    thumb_src = f"/static/img/pub/{p['key']}.webp"
    if (ROOT / thumb_src.lstrip("/")).exists():
        thumb = f'<div class="thumb">{img(thumb_src, "")}</div>'
    else:
        thumb = f'<div class="thumb thumb-empty" aria-hidden="true">{esc(p["venue_short"])}</div>'
    badges = []
    if "first" in p.get("tags", []):
        badges.append(f'<span class="badge badge-first">{esc(u["first_badge"])}</span>')
    if p.get("highlight"):
        badges.append(f'<span class="badge">{esc(T(p["highlight"], lang))}</span>')
    acts = []
    if p.get("doi"):
        acts.append(link("https://doi.org/" + p["doi"], u["doi"]))
    if p.get("pdf"):
        acts.append(link(p["pdf"], u["pdf"]))
    if p.get("code"):
        acts.append(link(p["code"], u["code"]))
    stories = [s for s in p.get("stories", []) if s in STORY_ARTICLES]
    if stories:
        n = sum(len(STORY_ARTICLES[s]) for s in stories)
        acts.append(f'<a href="#story-{stories[0]}">{esc(u["press_n"].format(n=n))}</a>')
    if p["key"] in FEATURED:
        acts.append(f'<a href="{RESEARCH_PAGE[lang]}#{p["key"]}">{esc(u["summary"])}</a>')
    acts.append(f'<button type="button" data-bibtex="{esc(bibtex(p))}">{esc(u["bibtex"])}</button>')
    title = link("https://doi.org/" + p["doi"], p["title"]) if p.get("doi") else esc(p["title"])
    return f"""<li class="pub" id="pub-{p['key']}" data-tags="{' '.join(['all'] + p.get('tags', []))}">
  {thumb}
  <div class="pub-b">
    <p class="pub-title">{title}</p>
    <p class="pub-authors">{authors_html(p['authors'])}</p>
    <p class="pub-venue">{venue_line(p)}{(' ' + ''.join(badges)) if badges else ''}</p>
    <p class="acts">{''.join(acts)}</p>
  </div>
</li>"""


def sec_publications(lang):
    u = UI[lang]
    journals = sorted(journal_papers(), key=lambda p: p["date"], reverse=True)
    preprints = sorted((p for p in PUBS if p.get("type") == "preprint"), key=lambda p: p["date"], reverse=True)
    n_first = sum(1 for p in journals if "first" in p.get("tags", []))
    chips = (f'<div class="filters" role="group">'
             f'<button type="button" data-filter="all" aria-pressed="true">{esc(u["filter_all"])} <span>{len(journals)}</span></button>'
             f'<button type="button" data-filter="first" aria-pressed="false">{esc(u["filter_first"])} <span>{n_first}</span></button></div>')
    groups = "".join(
        f'<div class="year-group"><h3 class="year">{y}</h3><ol class="pubs">'
        + "".join(pub_entry(p, lang) for p in journals if p["year"] == y) + "</ol></div>"
        for y in sorted({p["year"] for p in journals}, reverse=True))
    if preprints:
        groups += (f'<div class="year-group"><h3 class="year">{esc(u["preprints"])}</h3>'
                   f'<ol class="pubs">{"".join(pub_entry(p, lang) for p in preprints)}</ol></div>')
    legend = f'<p class="note">{u["legend"]}</p>'
    return section("publications", u["publications"], f'<div class="pub-top">{chips}{legend}</div>{groups}')


def sec_awards(lang):
    rows = "".join(f"""<li><time datetime="{a['date']}">{esc(fmt_date(a['date'], lang))}</time>
<div><p class="r-title">{md(T(a['title'], lang))}</p><p class="r-meta">{md(T(a['org'], lang))}</p>
{f'<p class="r-note">{md(T(a["note"], lang))}</p>' if a.get('note') else ''}</div></li>""" for a in HONORS["awards"])
    return section("awards", UI[lang]["awards"], f'<ul class="rows">{rows}</ul>')


def sec_patents(lang):
    u = UI[lang]
    rows = ""
    for p in HONORS["patents"]:
        fl = "".join(
            f'<li><span class="pat-no">{link(f["url"], f["number"]) if f.get("url") else esc(f["number"])}</span>'
            f'<span class="pat-st pat-{f["status"]}">{esc(u[f["status"]])} · {esc(fmt_date(f["date"], lang, day=True))}</span></li>'
            for f in p["filings"])
        thumb = (f'<div class="thumb thumb-pat">{img(p["image"], "")}</div>' if p.get("image")
                 else f'<div class="thumb thumb-pat thumb-empty" aria-hidden="true">{esc(p["filings"][0]["office"])}</div>')
        rows += (f'<li class="patent">{thumb}<div><p class="r-title">{md(T(p["title"], lang))}</p><ul class="filings">{fl}</ul>'
                 f'<p class="r-note">{esc(u["inventors"])}: {authors_html(p["inventors"])} · {esc(p.get("assignee", ""))}</p></div></li>')
    inv = HONORS["inventions"]
    items = "".join(f"<li>{md(T(x, lang))}</li>" for x in inv["items"])
    extra = (f'<li><p class="r-title">{esc(u["invention_title"])}</p><p class="r-meta">{md(T(inv["body"], lang))}</p>'
             f'<ul class="plain">{items}</ul></li>')
    return section("patents", u["patents"], f'<ul class="rows rows-flat">{rows}{extra}</ul>')


def sec_presentations(lang):
    rows = ""
    for t in TALKS:
        kind = f' <span class="badge">{esc(T(t["kind"], lang))}</span>' if t.get("kind") else ""
        award = f'<p class="r-note r-award">{esc(T(t["award"], lang))}</p>' if t.get("award") else ""
        rows += (f'<li><time datetime="{t["date"]}">{esc(fmt_date(t["date"], lang))}</time><div>'
                 f'<p class="r-title">{esc(t["title"])}{kind}</p>'
                 f'<p class="r-meta">{authors_html(t["authors"])} · <em>{esc(T(t["venue"], lang))}</em>'
                 f'{", " + esc(t["place"]) if t.get("place") else ""}</p>{award}</div></li>')
    return section("presentations", UI[lang]["presentations"], f'<ul class="rows">{rows}</ul>')


def sec_press(lang):
    u = UI[lang]
    arts = press_articles()
    if not arts:
        return ""
    n, m = press_counts()
    years = sorted(parse_date(a["date"]).year for a in arts)
    head = f'<p class="note">{esc(u["press_total"].format(n=n, m=m, y0=years[0], y1=years[-1]))}</p>'
    vmax = max(len(v) for v in STORY_ARTICLES.values())
    order = ["first", "other", "coauthor"]
    keys = sorted((k for k in STORY_ORDER if STORY_ARTICLES.get(k)),
                  key=lambda k: (order.index(PRESS["stories"][k].get("group", "other")), STORY_ORDER.index(k)))
    bars = ""
    for k in keys:
        s_ = PRESS["stories"][k]
        g = s_.get("group", "other")
        bars += (f'<li><a href="#story-{k}">{esc(T(s_["label"], lang))}</a>'
                 f'<span class="hbar"><i class="g-{g}" style="width:{len(STORY_ARTICLES[k]) / vmax * 100:.1f}%"></i></span>'
                 f'<b>{len(STORY_ARTICLES[k])}</b></li>')
    legend = '<ul class="legend">' + "".join(
        f'<li><i class="g-{g}"></i>{esc(u["groups"][g])}</li>' for g in order
        if any(PRESS["stories"][k].get("group", "other") == g for k in keys)) + "</ul>"
    blocks = ""
    for g in order:
        ks = [k for k in keys if PRESS["stories"][k].get("group", "other") == g]
        if not ks:
            continue
        blocks += f'<p class="group-h">{esc(u["groups"][g])}</p>'
        for k in ks:
            s_ = PRESS["stories"][k]
            rows = ""
            for a in STORY_ARTICLES[k]:
                a_lang = a.get("lang", "ko")
                la = f' lang="{a_lang}"' if a_lang != lang else ""
                outlet = a.get("outlet_en") if (lang == "en" and a.get("outlet_en")) else a["outlet"]
                rows += (f'<tr><td class="p-out">{esc(outlet)}</td><td class="p-head"{la}>{link(a["url"], a["headline"])}</td>'
                         f'<td class="p-date"><time datetime="{a["date"]}">{esc(fmt_date(a["date"], lang, day=True))}</time></td></tr>')
            n_k = len(STORY_ARTICLES[k])
            blocks += (f'<details class="story" id="story-{k}"><summary><span class="s-date">{esc(fmt_date(s_["date"], lang))}</span>'
                       f'<span class="s-title">{md(T(s_["title"], lang))}</span>'
                       f'<span class="s-n">{esc(u["articles"].format(n=n_k))}</span></summary>'
                       f'<table class="ptable"><tbody>{rows}</tbody></table></details>')
    return section("press", u["press"], f'{head}<ul class="hbars">{bars}</ul>{legend}<div class="stories">{blocks}</div>')


def sec_projects(lang):
    u = UI[lang]
    rows = ""
    for e in sorted(CV["experience"], key=lambda e: (e["start"], e["end"]), reverse=True):
        pts = "".join(f"<li>{md(T(x, lang))}</li>" for x in e["points"])
        rows += (f'<li><time>{e["start"]}–{e["end"]}</time><div><p class="r-title">{md(T(e["title"], lang))}</p>'
                 f'<p class="r-meta">{esc(T(e["org"], lang))}</p><ul class="plain">{pts}</ul></div></li>')
    grants = "".join(f'<li><time>{g["year"]}</time><div><p class="r-title">{md(T(g["title"], lang))}</p>'
                     f'<p class="r-meta">{esc(T(g["org"], lang))}</p><p class="r-note">{md(T(g["body"], lang))}</p></div></li>'
                     for g in CV["grants"])
    return (section("projects", u["projects"], f'<p class="note sec-note">{esc(u["projects_note"])}</p><ul class="rows">{rows}</ul>')
            + section("grants", u["grants"], f'<ul class="rows">{grants}</ul>'))


def sec_education(lang):
    rows = "".join(
        f'<li><time>{esc(T(e["years"], lang))}</time><div><p class="r-title">{md(T(e["degree"], lang))}</p>'
        f'<p class="r-meta">{esc(T(e["school"], lang))}</p>'
        + (f'<p class="r-note">{md(T(e["note"], lang))}</p>' if e.get("note") else "") + "</div></li>"
        for e in CV["education"])
    return section("education", UI[lang]["education"], f'<ul class="rows">{rows}</ul>')


def sec_skills(lang):
    rows = ""
    for s in CV["skills"]:
        groups = "".join(f"<dt>{esc(T(g['k'], lang))}</dt><dd>{esc(', '.join(T(t, lang) for t in g['v']))}</dd>" for g in s["groups"])
        rows += f'<div class="skill"><p class="r-title">{esc(T(s["title"], lang))}</p><dl>{groups}</dl></div>'
    return section("skills", UI[lang]["skills"], f'<div class="skills">{rows}</div>')


# ─────────────────────────────────────────────────────────────── pages ──

def build_home(lang):
    body = "\n".join([
        sec_profile(lang), sec_interests(lang), sec_overview(lang),
        sec_publications(lang), sec_awards(lang), sec_patents(lang), sec_presentations(lang),
        sec_press(lang), sec_projects(lang), sec_education(lang), sec_skills(lang),
    ])
    return page(lang, body, T(SITE["title"], lang), T(SITE["description"], lang), HOME[lang], alt_paths=HOME,
                active="home", sections=True)


def build_research(lang):
    u = UI[lang]
    parts = [f'<div class="page-head"><h1>{esc(u["research_title"])}</h1><p class="note">{esc(u["research_intro"])}</p></div>']
    for f in RESEARCH["featured"]:
        p = PUB_BY_KEY[f["paper"]]
        links = [link("https://doi.org/" + p["doi"], u["paper"])]
        if p.get("code"):
            links.append(link(p["code"], u["code"]))
        stories = [s for s in p.get("stories", []) if s in STORY_ARTICLES]
        if stories:
            links.append(f'<a href="{HOME[lang]}#story-{stories[0]}">{esc(u["press_n"].format(n=sum(len(STORY_ARTICLES[s]) for s in stories)))}</a>')
        results = "".join(f"<li>{md(T(r, lang))}</li>" for r in f["results"])
        figs = "".join(f'<figure>{img(x["src"], T(x["alt"], lang))}<figcaption>{md(T(x["caption"], lang))}</figcaption></figure>'
                       for x in f["figures"])
        parts.append(f"""<section class="sec" id="{p['key']}">
  <h2 class="sec-h">{esc(p['venue_short'])} {p['year']}</h2>
  <div class="sec-b research">
    <h3 class="r-h">{esc(p['title'])}</h3>
    <p class="r-meta">{authors_html(p['authors'])}<br>{venue_line(p)}</p>
    <p class="acts">{''.join(links)}</p>
    <p class="r-text">{md(T(f['summary'], lang))}</p>
    <p class="r-sub">{esc(u['results'])}</p>
    <ul class="plain">{results}</ul>
    <div class="figs">{figs}</div>
  </div>
</section>""")
    other = ""
    for o in RESEARCH["other"]:
        refs = ", ".join(f'<a href="{HOME[lang]}#pub-{k}">{esc(PUB_BY_KEY[k]["venue_short"])} {PUB_BY_KEY[k]["year"]}</a>' for k in o["papers"])
        other += (f'<li><p class="r-title">{md(T(o["title"], lang))}</p><p class="r-meta">{md(T(o["text"], lang))}</p>'
                  f'<p class="r-note">{refs}</p></li>')
    parts.append(section("other", u["other"], f'<ul class="rows rows-flat">{other}</ul>'))
    parts.append(f'<p class="back"><a href="{HOME[lang]}">{esc(u["back"])}</a></p>')
    return page(lang, "\n".join(parts), f'{u["research_title"]} · {T(SITE["name"], lang)}', T(SITE["description"], lang),
                RESEARCH_PAGE[lang], alt_paths=RESEARCH_PAGE, active="research")


def build_cv(lang="en"):
    """Print-first CV (English content; site header in `lang`). Self-contained CSS so Chrome can print it from file://."""
    L = "en"
    u = UI[lang]
    s = SITE
    css = (STATIC / "css" / "cv.css").read_text("utf-8")

    def row(left, right):
        return f'<div class="jb"><span>{left}</span><span class="r">{right}</span></div>'

    def cite(p):
        return (f"<li>{authors_html(p['authors'])}, “{esc(p['title'])},” <em>{esc(p['venue'])}</em>"
                f"{', vol. ' + esc(str(p['volume'])) if p.get('volume') else ''}"
                f"{', no. ' + esc(str(p['issue'])) if p.get('issue') else ''}"
                f"{', ' + esc(str(p['pages'])) if p.get('pages') else ''}, <strong>{p['year']}</strong>."
                f"{' <em>(' + esc(T(p['highlight'], L)) + ')</em>' if p.get('highlight') else ''}"
                f"{' doi:' + esc(p['doi']) if p.get('doi') else ''}</li>")

    edu = "".join(row(f"<strong>{esc(T(e['school'], L))}</strong>", esc(T(e["years"], L)))
                  + row(f"<em>{md(T(e['degree'], L))}</em>", esc(e.get("place", "")))
                  + (f"<ul>{''.join(f'<li>{md(x)}</li>' for x in e['cv_points'])}</ul>" if e.get("cv_points") else "")
                  for e in CV["education"])
    awards = "".join(row(f"<strong>{md(T(a['title'], L))}</strong> — {md(T(a['org'], L))}", esc(fmt_date(a["date"], L)))
                     + (f"<ul><li>{md(T(a['note'], L))}</li></ul>" if a.get("note") else "")
                     for a in HONORS["awards"])
    ordered = sorted(PUBS, key=lambda p: p["date"], reverse=True)
    pubs = "".join(cite(p) for p in ordered if p.get("type", "journal") == "journal")
    preprints = "".join(cite(p) for p in ordered if p.get("type") == "preprint")
    talks = "".join(
        f"<li>{('<b>[' + esc(T(t['kind'], L)) + ']</b> ') if t.get('kind') else ''}{authors_html(t['authors'])}, “{esc(t['title'])},” "
        f"<em>{esc(T(t['venue'], L))}</em>{', ' + esc(t['place']) if t.get('place') else ''}, <strong>{esc(fmt_date(t['date'], L))}</strong>."
        f"{' — <em>' + esc(T(t['award'], L)) + '</em>' if t.get('award') else ''}</li>"
        for t in TALKS)
    pats = "".join(
        f"<li>{authors_html(p['inventors'])}, “{md(T(p['title'], L))},” "
        + "; ".join(f"{esc(f['number'])} ({UI[L][f['status']].lower()} {esc(fmt_date(f['date'], L, day=True))})" for f in p["filings"])
        + ".</li>" for p in HONORS["patents"])
    inv = HONORS["inventions"]
    grants = "".join(row(f"<strong>{md(T(g['title'], L))}</strong> — {esc(T(g['org'], L))}", esc(str(g["year"])))
                     + f"<ul><li>{md(T(g['body'], L))}</li></ul>" for g in CV["grants"])
    exp = "".join(row(f"<strong>{md(T(e['title'], L))}</strong> · <em>{esc(T(e['org'], L))}</em>", f"{e['start']} – {e['end']}")
                  + f"<ul>{''.join(f'<li>{md(T(x, L))}</li>' for x in e['points'])}</ul>"
                  for e in sorted(CV["experience"], key=lambda e: e["start"], reverse=True))
    skills = "".join(f"<p><strong>{esc(T(s_['title'], L))}</strong></p><ul>"
                     + "".join(f"<li><em>{esc(T(g['k'], L))}:</em> {esc(', '.join(T(t, L) for t in g['v']))}</li>" for g in s_["groups"])
                     + "</ul>" for s_ in CV["skills"])
    sch = s["scholar"]
    short = {"scholar": ("Scholar", "YJQV1tgAAAAJ"), "github": ("GitHub", "github.com/GH-Song"),
             "orcid": ("ORCID", "0000-0002-4906-9506")}
    links = "".join(f"<tr><td class=k>{esc(short[l['id']][0])}</td><td>{link(l['url'], short[l['id']][1])}</td></tr>"
                    for l in s["links"] if l["id"] in short)
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gookho Song — Curriculum Vitae</title>
<meta name="description" content="Curriculum vitae of Gookho Song (송국호), Ph.D. candidate at KAIST.">
<link rel="canonical" href="{s['url']}/cv/">
<link rel="alternate" hreflang="en" href="{s['url']}/cv/"><link rel="alternate" hreflang="ko" href="{s['url']}/ko/cv/">
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Charis+SIL:ital,wght@0,400;0,700;1,400;1,700&display=swap">
<style>{css}</style></head>
<body>
{header(lang, "cv", CV_PAGE)}
<div class="cv-actions"><a href="/static/files/Gookho_Song_CV.pdf" download>{esc(u['cv_pdf'])}</a><button type="button" onclick="print()">{esc(u['print'])}</button></div>
<article class="cv" lang="en">
<div class="cv-header"><div class="cv-id"><h1>Gookho Song</h1>
<div class="cv-title">{esc(T(s.get('role_short') or s['role'], L))}</div><div class="cv-aff">Korea Advanced Institute of Science and Technology (KAIST)</div></div>
<div class="cv-contact"><table><tr><td class=k>Email</td><td>{link('mailto:' + s['email'], s['email'])}</td></tr>
<tr><td class=k>Web</td><td>{link(s['url'] + '/', s['url'].split('//')[1])}</td></tr>{links}</table></div></div>
<hr class="cv-rule">
<h2>Research Interests</h2>
<p>{md(T(CV['interests'], L))}</p>
<h2>Education</h2>{edu}
<h2>Honors &amp; Awards</h2>{awards}
<h2>Journal Articles</h2>
<div class="legend"><strong>G. Song</strong> = applicant · <sup>†</sup> equal contribution · <sup>*</sup> corresponding author</div>
<div class="metrics"><strong>Google Scholar ({esc(fmt_date(sch['as_of'], L))}):</strong> {sch['citations']} citations · h-index {sch['h_index']} · i10-index {sch['i10_index']}</div>
<ol class="pubs">{pubs}</ol>
{f'<h2>Preprints</h2><ol>{preprints}</ol>' if preprints else ''}
<h2>Conference Presentations</h2><ol>{talks}</ol>
<h2>Patents &amp; Inventions</h2><ul>{pats}</ul>
<p><em>{md(T(inv['title'], L))}</em> — {md(T(inv['body'], L))} {'; '.join(md(T(x, L)) for x in inv['items'])}.</p>
<h2>Grants &amp; Funded Projects</h2>{grants}
<h2>Research Experience</h2><div class="legend">Sponsored projects of Prof. Mooseok Jang (PI); participating researcher.</div>{exp}
<h2>Technical Skills</h2><div class="skills">{skills}</div>
<p class="updated">Last updated {esc(fmt_date(s['updated'], L, day=True))}</p>
</article></body></html>"""


def build_404():
    body = '<div class="page-head"><h1>Page not found</h1><p class="note"><a href="/">Home</a> · <a href="/ko/">홈</a></p></div>'
    return page("en", body, "Not found · Gookho Song", "Page not found", "/404.html")


# ───────────────────────────────────────────────────────────── loading ──

def load_all():
    global SITE, RESEARCH, PUBS, PUB_BY_KEY, TALKS, HONORS, CV, PRESS, STORY_ARTICLES, STORY_ORDER, FEATURED
    SITE = load("site")
    RESEARCH = load("research")
    PUBS = load("publications")["papers"]
    TALKS = load("talks")
    HONORS = load("honors")
    CV = load("cv")
    PRESS = load("press")
    PUB_BY_KEY = {p["key"]: p for p in PUBS}
    FEATURED = {f["paper"] for f in RESEARCH["featured"]}
    STORY_ARTICLES = {}
    for a in press_articles():
        STORY_ARTICLES.setdefault(a["story"], []).append(a)
    for arts in STORY_ARTICLES.values():   # the university's own release first, then by date
        arts.sort(key=lambda a: (0 if a.get("type") in ("university", "institution") else 1, a["date"], a["outlet"]))
    STORY_ORDER = sorted(PRESS["stories"], key=lambda k: PRESS["stories"][k]["date"], reverse=True)


def validate():
    errors = []
    keys = set()
    for p in PUBS:
        if p["key"] in keys:
            errors.append(f"publications: duplicate key {p['key']}")
        keys.add(p["key"])
        parse_date(p["date"])
        for s in p.get("stories", []):
            if s not in PRESS["stories"]:
                print(f"! publications/{p['key']}: no press story '{s}' yet (link hidden)")
    seen = set()
    for a in PRESS["articles"]:
        for f in ("story", "outlet", "headline", "url", "date"):
            if not a.get(f):
                errors.append(f"press: article missing '{f}': {a}")
        if a.get("story") not in PRESS["stories"]:
            errors.append(f"press: '{a.get('headline', '')[:40]}' has unknown story '{a.get('story')}'")
        if a.get("url") in seen:
            errors.append(f"press: duplicate url {a['url']}")
        seen.add(a.get("url"))
        parse_date(a["date"])
    for k, s in PRESS["stories"].items():
        if s.get("paper") and s["paper"] not in PUB_BY_KEY:
            errors.append(f"press/stories/{k}: unknown paper '{s['paper']}'")
        if "label" not in s:
            errors.append(f"press/stories/{k}: missing 'label'")
    for f in RESEARCH["featured"]:
        if f["paper"] not in PUB_BY_KEY:
            errors.append(f"research: unknown paper '{f['paper']}'")
    for o in RESEARCH["other"]:
        for k in o["papers"]:
            if k not in PUB_BY_KEY:
                errors.append(f"research/other: unknown paper '{k}'")
    if errors:
        sys.exit("✗ content errors:\n  " + "\n  ".join(errors))


# ─────────────────────────────────────────────────────────────── build ──

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def build():
    load_all()
    validate()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(STATIC, OUT / "static")
    for lang in LANGS:
        write(OUT / HOME[lang].strip("/") / "index.html", build_home(lang))
        write(OUT / RESEARCH_PAGE[lang].strip("/") / "index.html", build_research(lang))
    for lang in LANGS:
        write(OUT / CV_PAGE[lang].strip("/") / "index.html", build_cv(lang))
    write(OUT / "404.html", build_404())
    write(OUT / ".nojekyll", "")
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")
    pages = ["/", "/ko/", "/research/", "/ko/research/", "/cv/"]
    urls = "".join(f"<url><loc>{SITE['url']}{p}</loc><lastmod>{SITE['updated']}</lastmod></url>" for p in pages)
    write(OUT / "sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n'
                               f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    n, m = press_counts()
    print(f"✓ built {OUT.relative_to(ROOT)}/ — {len(PUBS)} papers · {n} press articles / {m} outlets")


def print_pdf():
    chrome = next((c for c in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
    ) if c and pathlib.Path(c).exists()), None)
    if not chrome:
        sys.exit("✗ --pdf needs Google Chrome")
    target = STATIC / "files" / "Gookho_Song_CV.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
                    f"--print-to-pdf={target}", (OUT / "cv" / "index.html").as_uri()], check=True, capture_output=True)
    (OUT / "static" / "files").mkdir(parents=True, exist_ok=True)
    shutil.copy(target, OUT / "static" / "files" / target.name)
    print(f"✓ {target.relative_to(ROOT)} ({target.stat().st_size // 1024} KB)")


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"→ http://localhost:{port}/   (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="serve _site/ after building")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--pdf", action="store_true", help="print the CV page to static/files/ (needs Chrome)")
    args = ap.parse_args()
    build()
    if args.pdf:
        print_pdf()
    if args.serve:
        serve(args.port)
