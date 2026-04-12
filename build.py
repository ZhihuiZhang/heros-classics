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


def layout(*, title: str, description: str, canonical: str, body: str, extra_head: str = "") -> str:
    full_title = f"{title} | {SITE_NAME}" if title != SITE_NAME else SITE_NAME
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
      <a href="/about/">HERO'Sとは</a>
    </nav>
  </div>
</header>
<main class="container">
{body}
</main>
<footer class="site-footer">
  <div class="container">
    <p>HERO'S Classics — 2005〜2008年のアーカイブ</p>
    <p class="small">本サイトは Wayback Machine 上の公開アーカイブを元に再構成した非公式の歴史資料です。</p>
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
    # Group by year
    by_year: dict[str, list[dict]] = {}
    for it in items:
        y = it["date"][:4]
        by_year.setdefault(y, []).append(it)
    parts: list[str] = ["<h1>ニュース一覧</h1>"]
    for year in sorted(by_year.keys(), reverse=True):
        parts.append(f'<section class="year-block"><h2>{year}年</h2><ul class="news-list">')
        for it in by_year[year]:
            thumb = ""
            if it["images"]:
                thumb = f'<img src="{esc(archive_img_url(it["images"][0]))}" alt="" loading="lazy">'
            parts.append(
                f'<li><a href="/news/{esc(it["slug"])}/">'
                f'{thumb}'
                f'<div><time>{esc(format_date(it["date"]))}</time>'
                f'<span class="title">{esc(it["title"])}</span></div>'
                f'</a></li>'
            )
        parts.append("</ul></section>")
    return "\n".join(parts)


def build_home(items: list[dict]) -> str:
    latest = items[:12]
    cards = "".join(
        f'<a class="card" href="/news/{esc(it["slug"])}/">'
        + (f'<img src="{esc(archive_img_url(it["images"][0]))}" alt="" loading="lazy">' if it["images"] else '')
        + f'<div class="card-body"><time>{esc(format_date(it["date"]))}</time>'
        f'<h3>{esc(it["title"])}</h3></div></a>'
        for it in latest
    )
    return f"""
<section class="hero">
  <h1>HERO'S Classics</h1>
  <p class="lead">総合格闘技イベント『HERO'S』(2005〜2008) のアーカイブ。<br>
  当時のニュース記事や選手コメントをそのまま時系列で閲覧できます。</p>
</section>
<section>
  <div class="section-head"><h2>最新ニュース</h2><a href="/news/">すべて見る →</a></div>
  <div class="card-grid">{cards}</div>
</section>
"""


def build_about(about: dict | None) -> str:
    if not about:
        return "<h1>HERO'Sとは</h1><p>準備中です。</p>"
    body = format_body_html(about["body"])
    return f"<article class=\"article\"><header><h1>HERO'Sとは</h1></header><div class=\"prose\">{body}</div></article>"


# ---------- Media / assets -------------------------------------------------


def copy_media(items: list[dict]) -> None:
    media_root = DIST / "media"
    referenced: set[str] = set()
    for it in items:
        for rel in it["images"]:
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
  --fg: #1a1a1a;
  --muted: #666;
  --bg: #fafafa;
  --card: #fff;
  --border: #e5e5e5;
  --accent: #c8102e;
  --accent-dark: #8a0a1e;
  --max-w: 1100px;
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
  background: #0b0b0b;
  color: #fff;
  border-bottom: 3px solid var(--accent);
}
.site-header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 14px;
  padding-bottom: 14px;
}
.brand {
  color: #fff;
  font-weight: 900;
  font-size: 22px;
  letter-spacing: 0.02em;
}
.brand span { color: var(--accent); font-weight: 700; }
.site-nav { display: flex; gap: 18px; }
.site-nav a { color: #eee; font-size: 15px; }
.site-nav a:hover { color: var(--accent); text-decoration: none; }

/* Hero */
.hero {
  padding: 48px 0 32px;
  text-align: center;
}
.hero h1 {
  font-size: clamp(28px, 5vw, 44px);
  margin: 0 0 12px;
  letter-spacing: 0.02em;
}
.hero .lead { color: var(--muted); margin: 0 auto; max-width: 640px; }

/* Section head */
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 32px 0 16px;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 8px;
}
.section-head h2 { margin: 0; font-size: 22px; }
.section-head a { font-size: 14px; }

/* Card grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
  margin-bottom: 48px;
}
.card {
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  color: var(--fg);
  transition: transform .15s, box-shadow .15s;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,.08);
  text-decoration: none;
}
.card img {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
  background: #eee;
}
.card-body { padding: 12px 14px 16px; }
.card-body time { color: var(--muted); font-size: 12px; }
.card-body h3 {
  margin: 4px 0 0;
  font-size: 15px;
  line-height: 1.5;
  font-weight: 600;
  color: var(--fg);
}

/* News list */
.year-block { margin-bottom: 36px; }
.year-block h2 {
  font-size: 24px;
  margin: 24px 0 12px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--accent);
}
.news-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
.news-list li { background: var(--card); border: 1px solid var(--border); border-radius: 6px; }
.news-list a {
  display: flex;
  gap: 14px;
  padding: 10px 14px;
  align-items: center;
  color: var(--fg);
}
.news-list a:hover { background: #fff8f9; text-decoration: none; }
.news-list img {
  width: 80px;
  height: 60px;
  object-fit: cover;
  flex-shrink: 0;
  border-radius: 4px;
  background: #eee;
}
.news-list time {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.news-list .title {
  display: block;
  font-weight: 600;
  font-size: 15px;
  line-height: 1.5;
}

/* Article */
.article { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 28px; margin: 24px 0 40px; }
.article header { margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
.article .date { color: var(--muted); font-size: 13px; margin: 0 0 6px; }
.article h1 { font-size: clamp(22px, 4vw, 30px); margin: 0; line-height: 1.4; }
.prose p { margin: 0 0 1em; }
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin: 0 0 24px;
}
.gallery figure { margin: 0; }
.gallery img { width: 100%; border-radius: 4px; background: #eee; }
.back { margin-top: 24px; }

/* Footer */
.site-footer {
  background: #0b0b0b;
  color: #aaa;
  padding: 28px 0;
  margin-top: 48px;
  font-size: 13px;
}
.site-footer .small { color: #666; font-size: 12px; margin-top: 4px; }

@media (max-width: 640px) {
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

    news = json.loads((CONTENT / "news.json").read_text(encoding="utf-8"))
    about_path = CONTENT / "about.json"
    about = json.loads(about_path.read_text(encoding="utf-8")) if about_path.exists() else None

    write_css()

    # Home
    home_body = build_home(news)
    write(DIST / "index.html", layout(
        title=SITE_NAME,
        description=SITE_DESC,
        canonical=f"{SITE_URL}/",
        body=home_body,
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

    # About
    write(DIST / "about" / "index.html", layout(
        title="HERO'Sとは",
        description="総合格闘技イベント『HERO'S』の概要。",
        canonical=f"{SITE_URL}/about/",
        body=build_about(about),
    ))

    copy_media(news)
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
