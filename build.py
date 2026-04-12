#!/usr/bin/env python3
"""Build the modern static site from extracted content into dist/."""
from __future__ import annotations

import html as html_mod
import json
import shutil
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
ARCHIVE = ROOT / "archive" / "www.hero-s.com"
DIST = ROOT / "dist"
SITE_URL = "https://hero-s.k-1.info"
SITE_NAME = "HERO'S Classics"
SITE_DESC = "総合格闘技イベント『HERO'S』(2005–2008)のアーカイブサイト。試合結果、選手インタビュー、ニュース記事を時系列で閲覧できます。"


def esc(s: str) -> str:
    return html_mod.escape(s, quote=True)


def layout(*, title: str, description: str, canonical: str, body: str, extra_head: str = "", full_width: bool = False) -> str:
    full_title = f"{title} | {SITE_NAME}" if title != SITE_NAME else SITE_NAME
    main_open = '<main>' if full_width else '<main class="container">'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css">
{extra_head}
</head>
<body>
<header class="site-header">
  <div class="container">
    <a href="/" class="brand">HERO'S <span>Classics</span></a>
    <nav class="site-nav">
      <a href="/">ホーム</a>
      <a href="/news/">ニュース</a>
      <a href="/events/">イベント</a>
      <a href="/results/">試合結果</a>
      <a href="/fighters/">選手</a>
      <a href="/about/">HERO'Sとは</a>
    </nav>
  </div>
</header>
{main_open}
{body}
</main>
<footer class="site-footer">
  <div class="container footer-inner">
    <div class="footer-brand">
      <div class="footer-logo">HERO'S <span>Classics</span></div>
      <p class="footer-tag">2005 — 2008 アーカイブ</p>
    </div>
    <nav class="footer-nav">
      <a href="/">ホーム</a>
      <a href="/news/">ニュース</a>
      <a href="/events/">イベント</a>
      <a href="/results/">試合結果</a>
      <a href="/fighters/">選手</a>
      <a href="/about/">HERO'Sとは</a>
    </nav>
    <p class="footer-copy">© HERO'S Classics</p>
  </div>
</footer>
</body>
</html>
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def archive_img_url(archive_rel: str) -> str:
    return "/media/" + archive_rel.replace("\\", "/")


def format_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%Y年%m月%d日")


def format_body_html(body: str) -> str:
    # Paragraph-split on blank lines; linkify URLs
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    url_re = re.compile(r"(https?://[^\s<>]+)")
    paragraphs: list[str] = []
    for ln in lines:
        safe = esc(ln)
        safe = url_re.sub(r'<a href="\1" rel="noopener nofollow">\1</a>', safe)
        paragraphs.append(f"<p>{safe}</p>")
    return "\n".join(paragraphs)


# ---------- Pages ----------------------------------------------------------


def build_news_article(item: dict) -> str:
    imgs_html = ""
    if item["images"]:
        tiles = "".join(
            f'<figure><img src="{esc(archive_img_url(i))}" alt="" loading="lazy"></figure>'
            for i in item["images"]
        )
        imgs_html = f'<div class="gallery">{tiles}</div>'
    body_html = format_body_html(item["body"])
    return f"""
<article class="article">
  <header>
    <p class="date">{esc(format_date(item["date"]))}</p>
    <h1>{esc(item["title"])}</h1>
  </header>
  {imgs_html}
  <div class="prose">
    {body_html}
  </div>
  <p class="back"><a href="/news/">← ニュース一覧へ</a></p>
</article>
"""


def build_news_index(items: list[dict]) -> str:
    by_year: dict[str, list[dict]] = {}
    for it in items:
        by_year.setdefault(it["date"][:4], []).append(it)
    parts: list[str] = ["<h1>ニュース一覧</h1>"]
    for year in sorted(by_year.keys(), reverse=True):
        parts.append(f'<section class="year-block"><h2>{year}年</h2><ul class="news-list">')
        for it in by_year[year]:
            thumb_html = ""
            if it["images"]:
                thumb_html = (
                    f'<img src="{esc(archive_img_url(it["images"][0]))}" alt="" loading="lazy">'
                )
            else:
                thumb_html = '<div class="thumb-placeholder">NEWS</div>'
            parts.append(
                f'<li><a href="/news/{esc(it["slug"])}/">'
                f'{thumb_html}'
                f'<div class="news-meta"><time>{esc(format_date(it["date"]))}</time>'
                f'<span class="title">{esc(it["title"])}</span></div>'
                f'</a></li>'
            )
        parts.append("</ul></section>")
    return "\n".join(parts)


def build_home(news: list[dict], events: list[dict], results: list[dict], fighters: list[dict]) -> str:
    def card(base: str, it: dict, date: bool = True) -> str:
        has_img = bool(it.get("images"))
        img = (
            f'<img src="{esc(archive_img_url(it["images"][0]))}" alt="" loading="lazy">'
            if has_img else ""
        )
        cls = "card" if has_img else "card no-img"
        time_html = f'<time>{esc(format_date(it["date"]))}</time>' if date and it.get("date") else ""
        return (
            f'<a class="{cls}" href="{base}{esc(it["slug"])}/">{img}'
            f'<div class="card-body">{time_html}'
            f'<h3>{esc(it.get("title") or it.get("name_jp",""))}</h3></div></a>'
        )

    # Prefer items WITH images for the homepage showcases
    news_with_img = [n for n in news if n.get("images")]
    news_cards = "".join(card("/news/", it) for it in (news_with_img[:8] or news[:8]))
    result_cards = "".join(card("/results/", it) for it in results[:4])
    event_cards = "".join(card("/events/", it) for it in events[:4])
    fighter_sample = [f for f in fighters if f.get("images")][:8] or fighters[:8]
    fighter_cards = "".join(
        f'<a class="card fighter-card" href="/fighters/{esc(f["slug"])}/">'
        + (f'<img src="{esc(archive_img_url(f["images"][0]))}" alt="" loading="lazy">' if f.get("images") else '<div class="placeholder">' + esc(f["name_jp"][:1]) + '</div>')
        + f'<div class="card-body"><h3>{esc(f["name_jp"])}</h3></div></a>'
        for f in fighter_sample
    )
    return f"""
<section class="hero hero-full">
  <div class="container">
    <h1>HERO'S <span>Classics</span></h1>
    <p class="lead">総合格闘技イベント『HERO'S』(2005〜2008) のアーカイブ。<br>
    当時のニュース記事、試合結果、選手プロフィールを時系列で閲覧できます。</p>
  </div>
</section>
<div class="container">
<section>
  <div class="section-head"><h2>最新ニュース</h2><a href="/news/">すべて見る →</a></div>
  <div class="card-grid">{news_cards}</div>
</section>
<section>
  <div class="section-head"><h2>試合結果</h2><a href="/results/">すべて見る →</a></div>
  <div class="card-grid">{result_cards}</div>
</section>
<section>
  <div class="section-head"><h2>開催イベント</h2><a href="/events/">すべて見る →</a></div>
  <div class="card-grid">{event_cards}</div>
</section>
<section>
  <div class="section-head"><h2>選手</h2><a href="/fighters/">すべて見る →</a></div>
  <div class="card-grid">{fighter_cards}</div>
</section>
</div>
"""


CATEGORY_LABELS = {
    "01a": "あ行", "02ka": "か行", "03sa": "さ行", "04ta": "た行",
    "05na": "な行", "06ha": "は行", "07ma": "ま行", "08ya": "や行",
    "09ra": "ら行", "10wa": "わ行",
}


def build_event_or_result_page(item: dict, kind: str) -> str:
    body_html = format_body_html(item["body"])
    imgs_html = ""
    if item["images"]:
        tiles = "".join(
            f'<figure><img src="{esc(archive_img_url(i))}" alt="" loading="lazy"></figure>'
            for i in item["images"]
        )
        imgs_html = f'<div class="gallery">{tiles}</div>'
    sub_html = ""
    if item.get("subpages"):
        cards = ""
        for s in item["subpages"]:
            thumb = ""
            if s["images"]:
                thumb = f'<img src="{esc(archive_img_url(s["images"][0]))}" alt="" loading="lazy">'
            preview = re.sub(r"\s+", " ", s["body"])[:120]
            cards += (
                f'<div class="sub-card">{thumb}'
                f'<h3>{esc(s["title"])}</h3>'
                f'<p>{esc(preview)}…</p></div>'
            )
        sub_html = f'<section class="subpages"><h2>関連レポート</h2><div class="sub-grid">{cards}</div></section>'
    back = "/events/" if kind == "event" else "/results/"
    back_label = "イベント一覧へ" if kind == "event" else "試合結果一覧へ"
    return f"""
<article class="article">
  <header>
    <p class="date">{esc(format_date(item["date"]))}</p>
    <h1>{esc(item["title"])}</h1>
  </header>
  {imgs_html}
  <div class="prose">{body_html}</div>
  {sub_html}
  <p class="back"><a href="{back}">← {back_label}</a></p>
</article>
"""


def build_event_index(items: list[dict], kind: str) -> str:
    title = "イベント一覧" if kind == "event" else "試合結果一覧"
    base = "/events/" if kind == "event" else "/results/"
    parts = [f"<h1>{title}</h1>"]
    by_year: dict[str, list[dict]] = {}
    for it in items:
        by_year.setdefault(it["date"][:4], []).append(it)
    for year in sorted(by_year.keys(), reverse=True):
        parts.append(f'<section class="year-block"><h2>{year}年</h2><div class="card-grid">')
        for it in by_year[year]:
            thumb = ""
            if it["images"]:
                thumb = f'<img src="{esc(archive_img_url(it["images"][0]))}" alt="" loading="lazy">'
            parts.append(
                f'<a class="card" href="{base}{esc(it["slug"])}/">'
                f'{thumb}<div class="card-body">'
                f'<time>{esc(format_date(it["date"]))}</time>'
                f'<h3>{esc(it["title"])}</h3></div></a>'
            )
        parts.append("</div></section>")
    return "\n".join(parts)


def build_fighter_page(f: dict) -> str:
    info = f.get("info", {})
    info_rows = ""
    label_map = [
        ("team", "所属"), ("birth", "生年月日"), ("origin", "出身地"),
        ("height", "身長"), ("weight", "体重"), ("background", "バックボーン"),
        ("titles", "主な獲得タイトル"), ("record_summary", "対戦成績"),
    ]
    for key, jp in label_map:
        if info.get(key):
            info_rows += f'<dt>{esc(jp)}</dt><dd>{esc(info[key])}</dd>'
    img_html = ""
    if f["images"]:
        img_html = f'<img class="fighter-photo" src="{esc(archive_img_url(f["images"][0]))}" alt="{esc(f["name_jp"])}" loading="lazy">'
    return f"""
<article class="article fighter-detail">
  <header>
    <h1>{esc(f["name_jp"])}</h1>
    {('<p class="name-en">' + esc(f["name_en"]) + '</p>') if f.get("name_en") else ''}
  </header>
  {img_html}
  <dl class="fighter-info">{info_rows}</dl>
  <p class="back"><a href="/fighters/">← 選手一覧へ</a></p>
</article>
"""


def build_fighters_index(fighters: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = {}
    for f in fighters:
        by_cat.setdefault(f["category"], []).append(f)
    parts = ['<h1>選手一覧</h1><p class="lead">HERO\'S に出場した選手のプロフィール。</p>']
    for cat in sorted(by_cat.keys()):
        label = CATEGORY_LABELS.get(cat, cat)
        parts.append(f'<section class="year-block"><h2>{esc(label)}</h2><div class="card-grid">')
        for f in by_cat[cat]:
            thumb = ""
            if f["images"]:
                thumb = f'<img src="{esc(archive_img_url(f["images"][0]))}" alt="" loading="lazy">'
            sub = f.get("info", {}).get("team", "")
            sub_html = f'<p class="sub">{esc(sub)}</p>' if sub else ""
            parts.append(
                f'<a class="card fighter-card" href="/fighters/{esc(f["slug"])}/">'
                f'{thumb}<div class="card-body">'
                f'<h3>{esc(f["name_jp"])}</h3>'
                f'{sub_html}'
                f'</div></a>'
            )
        parts.append("</div></section>")
    return "\n".join(parts)


def build_about(about: dict | None) -> str:
    if not about:
        return "<h1>HERO'Sとは</h1><p>準備中です。</p>"
    body = format_body_html(about["body"])
    return f"<article class=\"article\"><header><h1>HERO'Sとは</h1></header><div class=\"prose\">{body}</div></article>"


# ---------- Media / assets -------------------------------------------------


def copy_media(all_items: list[dict]) -> None:
    media_root = DIST / "media"
    referenced: set[str] = set()
    for it in all_items:
        for rel in it.get("images", []) or []:
            referenced.add(rel)
        for sp in it.get("subpages", []) or []:
            for rel in sp.get("images", []) or []:
                referenced.add(rel)
    for rel in referenced:
        src = ARCHIVE / rel
        dst = media_root / rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copyfile(src, dst)


def write_css() -> None:
    css = """
:root {
  --fg: #111;
  --muted: #6b7280;
  --bg: #f5f5f4;
  --card: #fff;
  --border: #e5e5e4;
  --border-strong: #d4d4d3;
  --accent: #d11a2a;
  --accent-dark: #8c0e1a;
  --ink: #0a0a0a;
  --max-w: 1180px;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN",
    "ヒラギノ角ゴ ProN W3", "Yu Gothic", "Meiryo", sans-serif;
  color: var(--fg);
  background: var(--bg);
  line-height: 1.7;
}
img { max-width: 100%; height: auto; display: block; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: var(--max-w); margin: 0 auto; padding: 0 20px; }

/* Header */
.site-header {
  background: var(--ink);
  color: #fff;
  border-bottom: 4px solid var(--accent);
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: saturate(140%);
}
.site-header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 16px;
  padding-bottom: 16px;
}
.brand {
  color: #fff;
  font-weight: 900;
  font-size: 22px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.brand span {
  color: var(--accent);
  font-weight: 700;
  margin-left: 4px;
  font-size: 14px;
  letter-spacing: 0.1em;
}
.site-nav { display: flex; gap: 22px; }
.site-nav a {
  color: #d4d4d3;
  font-size: 14px;
  font-weight: 500;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: color .15s, border-color .15s;
}
.site-nav a:hover {
  color: #fff;
  border-bottom-color: var(--accent);
  text-decoration: none;
}

/* Hero */
.hero {
  position: relative;
  padding: 80px 0 60px;
  text-align: center;
  background:
    radial-gradient(ellipse at center top, rgba(209,26,42,0.18), transparent 60%),
    linear-gradient(180deg, #111 0%, #0a0a0a 100%);
  color: #fff;
  margin-bottom: 16px;
}
.hero::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
}
.hero h1 {
  font-size: clamp(32px, 6vw, 56px);
  margin: 0 0 16px;
  letter-spacing: 0.04em;
  font-weight: 900;
  text-transform: uppercase;
}
.hero h1 span { color: var(--accent); }
.hero .lead {
  color: #d4d4d3;
  margin: 0 auto;
  max-width: 680px;
  font-size: 16px;
  line-height: 1.8;
}

/* Section head */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 48px 0 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-strong);
  position: relative;
}
.section-head::before {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 48px;
  height: 3px;
  background: var(--accent);
}
.section-head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.02em;
}
.section-head a {
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
}
.section-head a:hover { color: var(--accent); }

/* Card grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}
.card {
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  color: var(--fg);
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}
.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(0,0,0,.1);
  border-color: var(--border-strong);
  text-decoration: none;
}
.card img {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  background: #f0f0ef;
  display: block;
}
.card.no-img {
  background: linear-gradient(135deg, #1a1a1a 0%, #0a0a0a 100%);
  color: #fff;
  border-color: #222;
}
.card.no-img:hover {
  border-color: var(--accent);
}
.card.no-img .card-body {
  padding: 20px 18px;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.card.no-img .card-body::before {
  content: "";
  display: block;
  width: 32px;
  height: 3px;
  background: var(--accent);
  margin-bottom: 10px;
}
.card.no-img h3 { color: #fff; }
.card.no-img time { color: #a1a1a0; }
.card-body { padding: 14px 16px 18px; }
.card-body time {
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.card-body h3 {
  margin: 6px 0 0;
  font-size: 15px;
  line-height: 1.55;
  font-weight: 600;
  color: inherit;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.fighter-card .placeholder {
  width: 100%;
  aspect-ratio: 1/1;
  background: linear-gradient(135deg, #222, #0a0a0a);
  color: var(--accent);
  font-size: 64px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* News list (year listings) */
.year-block { margin-bottom: 48px; }
.year-block > h2 {
  font-size: 28px;
  margin: 32px 0 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-strong);
  font-weight: 900;
  position: relative;
  letter-spacing: 0.02em;
}
.year-block > h2::before {
  content: "";
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 64px;
  height: 3px;
  background: var(--accent);
}
.news-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.news-list li {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color .15s, transform .15s;
}
.news-list li:hover { border-color: var(--accent); }
.news-list a {
  display: flex;
  gap: 16px;
  padding: 14px 18px;
  align-items: center;
  color: var(--fg);
}
.news-list a:hover { text-decoration: none; }
.news-list img {
  width: 96px;
  height: 72px;
  object-fit: cover;
  flex-shrink: 0;
  border-radius: 6px;
  background: #f0f0ef;
}
.thumb-placeholder {
  width: 96px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, #1a1a1a, #0a0a0a);
  color: var(--accent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.15em;
  display: flex;
  align-items: center;
  justify-content: center;
}
.news-meta { min-width: 0; flex: 1; }
.news-list time {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
}
.news-list .title {
  display: block;
  font-weight: 600;
  font-size: 15px;
  line-height: 1.55;
  margin-top: 4px;
}

/* Article */
.article {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 36px 40px;
  margin: 32px 0 48px;
  max-width: 820px;
}
.article header {
  margin-bottom: 28px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 20px;
}
.article .date {
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 10px;
  letter-spacing: 0.05em;
}
.article h1 {
  font-size: clamp(24px, 4vw, 32px);
  margin: 0;
  line-height: 1.5;
  font-weight: 800;
}
.prose { font-size: 16px; line-height: 1.9; }
.prose p { margin: 0 0 1.2em; }
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  margin: 0 0 28px;
}
.gallery figure { margin: 0; }
.gallery img { width: 100%; border-radius: 6px; background: #f0f0ef; }
.back {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
.back a { font-size: 14px; font-weight: 500; }

/* Footer */
.site-footer {
  background: var(--ink);
  color: #9a9a99;
  padding: 48px 0 32px;
  margin-top: 72px;
  font-size: 13px;
  border-top: 4px solid var(--accent);
  background-image:
    radial-gradient(ellipse at 20% 0%, rgba(209,26,42,0.14), transparent 55%);
}
.footer-inner {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px 48px;
  align-items: start;
}
.footer-brand { grid-column: 1; }
.footer-logo {
  color: #fff;
  font-size: 20px;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.footer-logo span {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  margin-left: 6px;
}
.footer-tag {
  margin: 6px 0 0;
  color: #6a6a69;
  font-size: 12px;
  letter-spacing: 0.08em;
}
.footer-nav {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-self: center;
}
.footer-nav a {
  color: #c4c4c3;
  font-size: 13px;
  font-weight: 500;
}
.footer-nav a:hover { color: var(--accent); text-decoration: none; }
.footer-copy {
  grid-column: 1 / -1;
  margin: 24px 0 0;
  padding-top: 20px;
  border-top: 1px solid #1f1f1f;
  color: #555;
  font-size: 12px;
  letter-spacing: 0.05em;
}

/* Fighter */
.fighter-card img { aspect-ratio: 1/1; object-fit: cover; }
.fighter-detail .name-en { color: var(--muted); font-size: 14px; margin: 4px 0 0; letter-spacing: 0.05em; }
.fighter-photo { max-width: 320px; margin: 0 0 20px; border-radius: 6px; background: #eee; }
.fighter-info { display: grid; grid-template-columns: 130px 1fr; gap: 6px 14px; margin: 0; }
.fighter-info dt { color: var(--muted); font-size: 13px; padding-top: 2px; }
.fighter-info dd { margin: 0; font-size: 15px; }

/* Sub cards (event result sub-pages) */
.subpages { margin-top: 28px; }
.sub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.sub-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}
.sub-card img {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  border-radius: 4px;
  background: #eee;
  margin-bottom: 8px;
}
.sub-card h3 { font-size: 14px; margin: 0 0 6px; line-height: 1.5; }
.sub-card p { font-size: 12px; color: var(--muted); margin: 0; }
.card-body .sub { color: var(--muted); font-size: 12px; margin: 4px 0 0; }

@media (max-width: 640px) {
  .footer-inner { grid-template-columns: 1fr; }
  .footer-nav { grid-column: 1; grid-row: auto; }
  .fighter-info { grid-template-columns: 100px 1fr; }
  .site-header .container { flex-direction: column; align-items: flex-start; }
  .site-nav { gap: 14px; }
  .article { padding: 18px; }
  .news-list img { width: 64px; height: 48px; }
}
"""
    write(DIST / "assets" / "site.css", css.strip() + "\n")


def write_sitemap(urls: list[str]) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    today = datetime.now().strftime("%Y-%m-%d")
    for u in urls:
        lines.append(f"  <url><loc>{esc(u)}</loc><lastmod>{today}</lastmod></url>")
    lines.append("</urlset>")
    write(DIST / "sitemap.xml", "\n".join(lines) + "\n")


def write_robots() -> None:
    robots = f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
"""
    write(DIST / "robots.txt", robots)


# ---------- Main -----------------------------------------------------------


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    def load(name: str, default):
        p = CONTENT / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    news = load("news.json", [])
    events = load("events.json", [])
    results = load("results.json", [])
    fighters = load("fighters.json", [])
    about = load("about.json", None)

    write_css()

    # Home
    home_body = build_home(news, events, results, fighters)
    write(DIST / "index.html", layout(
        title=SITE_NAME,
        description=SITE_DESC,
        canonical=f"{SITE_URL}/",
        body=home_body,
        full_width=True,
    ))

    # News index
    write(DIST / "news" / "index.html", layout(
        title="ニュース一覧",
        description="HERO'S 全ニュース記事の一覧(2005〜2008年)。",
        canonical=f"{SITE_URL}/news/",
        body=build_news_index(news),
    ))

    # Article pages
    urls = [f"{SITE_URL}/", f"{SITE_URL}/news/", f"{SITE_URL}/about/"]
    for it in news:
        url = f"{SITE_URL}/news/{it['slug']}/"
        urls.append(url)
        desc = re.sub(r"\s+", " ", it["body"])[:140]
        write(DIST / "news" / it["slug"] / "index.html", layout(
            title=it["title"],
            description=desc or it["title"],
            canonical=url,
            body=build_news_article(it),
        ))

    # Events
    write(DIST / "events" / "index.html", layout(
        title="イベント一覧",
        description="HERO'S 開催イベントの一覧(2005〜2008年)。",
        canonical=f"{SITE_URL}/events/",
        body=build_event_index(events, "event"),
    ))
    for it in events:
        url = f"{SITE_URL}/events/{it['slug']}/"
        urls.append(url)
        desc = re.sub(r"\s+", " ", it["body"])[:140]
        write(DIST / "events" / it["slug"] / "index.html", layout(
            title=it["title"],
            description=desc or it["title"],
            canonical=url,
            body=build_event_or_result_page(it, "event"),
        ))

    # Results
    write(DIST / "results" / "index.html", layout(
        title="試合結果一覧",
        description="HERO'S 試合結果の一覧(2005〜2008年)。",
        canonical=f"{SITE_URL}/results/",
        body=build_event_index(results, "result"),
    ))
    for it in results:
        url = f"{SITE_URL}/results/{it['slug']}/"
        urls.append(url)
        desc = re.sub(r"\s+", " ", it["body"])[:140]
        write(DIST / "results" / it["slug"] / "index.html", layout(
            title=it["title"],
            description=desc or it["title"],
            canonical=url,
            body=build_event_or_result_page(it, "result"),
        ))

    # Fighters
    write(DIST / "fighters" / "index.html", layout(
        title="選手一覧",
        description="HERO'S 出場選手のプロフィール一覧。",
        canonical=f"{SITE_URL}/fighters/",
        body=build_fighters_index(fighters),
    ))
    for f in fighters:
        url = f"{SITE_URL}/fighters/{f['slug']}/"
        urls.append(url)
        write(DIST / "fighters" / f["slug"] / "index.html", layout(
            title=f["name_jp"],
            description=f"{f['name_jp']} のプロフィール。" + (f" {f['info'].get('team','')}" if f.get('info') else ""),
            canonical=url,
            body=build_fighter_page(f),
        ))

    # About
    write(DIST / "about" / "index.html", layout(
        title="HERO'Sとは",
        description="総合格闘技イベント『HERO'S』の概要。",
        canonical=f"{SITE_URL}/about/",
        body=build_about(about),
    ))

    copy_media(news + events + results + fighters)
    write_sitemap(urls)
    write_robots()

    # Emit 404 page (Amplify will serve this on missing paths if configured)
    write(DIST / "404.html", layout(
        title="ページが見つかりません",
        description="指定されたページは存在しません。",
        canonical=f"{SITE_URL}/404.html",
        body="<h1>404 - ページが見つかりません</h1><p><a href=\"/\">トップに戻る</a></p>",
    ))

    print(f"built: {len(news)} articles, {len(urls)} urls")


if __name__ == "__main__":
    main()
