#!/usr/bin/env python3
"""Extract structured content from the archived hero-s.com HTML files.

Outputs:
  content/news.json     - list of news articles (date, slug, title, body, images)
  content/events.json   - list of events
  content/fighters.json - fighter profiles
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

ARCHIVE = Path("archive/www.hero-s.com")
OUT = Path("content")
OUT.mkdir(exist_ok=True)

# Strings to strip from any extracted text
STRIP_PATTERNS = [
    re.compile(r"Copyright\s*\(C\)\s*\d{4}\s*HERO-?S[^\n]*", re.IGNORECASE),
    re.compile(r"Copyright\s*\(C\)\s*\d{4}\s*G\.?T\.?Entertainment[^\n]*", re.IGNORECASE),
    re.compile(r"当サイトで使用している写真およびテキストの無断転載を禁止します。?"),
    re.compile(r"Mail\s*to\s*:?\s*official@hero-s\.com", re.IGNORECASE),
    re.compile(r"official@hero-s\.com", re.IGNORECASE),
]

# Generic chrome image patterns to filter out
CHROME_IMG = re.compile(
    r"(img_share|img_head|sideline|^he\d+\.gif$|bt_|btn_|sub_|nav_|footer|spacer|menu_|headline_|line\.gif|blank|arrow)",
    re.IGNORECASE,
)


BOILERPLATE_RE = re.compile(
    r"(HERO'?S|HERO-?S|NEWS|OFFICIAL|ニュース|オフィシャル|トップ|HOME|MENU"
    r"|What's|ファイターズ|イベント|スケジュール|メディア|インフォメーション|INFO"
    r"|投票|VOTE|リンク|PROFILE|プロフィール)",
    re.IGNORECASE,
)


def derive_title(body: str, date_str: str) -> str:
    for line in body.split("\n"):
        line = line.strip()
        line = re.sub(r"^[■●◆▼▲※»\s]+", "", line).strip()
        if len(line) < 6:
            continue
        # Skip lines that look like nav labels
        if len(line) < 20 and BOILERPLATE_RE.search(line):
            continue
        if line.startswith(("http://", "https://")):
            continue
        if len(line) > 70:
            line = line[:70].rstrip() + "…"
        return line
    return f"HERO'S NEWS {date_str}"


def clean_text(text: str) -> str:
    for pat in STRIP_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


NAV_LINES = {
    "HERO'S", "HERO-S", "HOME", "TOP", "MENU", "NEWS", "INFO",
    "ニュース", "ファイターズ", "イベント", "スケジュール", "メディア",
    "インフォメーション", "投票", "VOTE", "リンク", "プロフィール",
    "What's HERO'S", "HERO'S NEWS", "EVENT SCHEDULE", "EVENT RESULT",
    "MEDIA INFO", "HERO'S VOTE", "FIGHTERS INFO",
}


def visible_text_blocks(soup: BeautifulSoup) -> str:
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    raw = soup.get_text("\n", strip=True)
    cleaned = clean_text(raw)
    seen: set[str] = set()
    out: list[str] = []
    for line in cleaned.split("\n"):
        line = line.strip(" 　\t")
        if not line or len(line) < 2:
            continue
        # Skip nav/chrome labels (short lines that match known nav)
        normalized = re.sub(r"[\s［］\[\]【】]+", "", line)
        if normalized in NAV_LINES or any(nav == normalized for nav in NAV_LINES):
            continue
        if len(line) <= 12 and BOILERPLATE_RE.search(line):
            continue
        # Strip standalone markers
        if re.fullmatch(r"[■●◆▼▲※»・\-–—\s]+", line):
            continue
        # Skip the repeated <title> line
        if "HERO'S" in line and "NEWS" in line and len(line) < 25:
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return "\n".join(out)


def collect_local_images(html_path: Path, soup: BeautifulSoup) -> list[str]:
    """Return list of image paths (relative to ARCHIVE) that look like article photos."""
    out: list[str] = []
    seen: set[str] = set()
    base = html_path.parent
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        name = src.rsplit("/", 1)[-1]
        if CHROME_IMG.search(name):
            continue
        # Resolve relative to the HTML file
        try:
            resolved = (base / src).resolve()
        except Exception:
            continue
        try:
            rel = resolved.relative_to(ARCHIVE.resolve())
        except ValueError:
            continue
        rel_str = str(rel)
        if rel_str in seen:
            continue
        if not (ARCHIVE / rel).exists():
            continue
        seen.add(rel_str)
        out.append(rel_str)
    return out


# ---------- News -----------------------------------------------------------

DATE_RE = re.compile(r"^(\d{8})(?:_\d+)?$")


def extract_news() -> list[dict]:
    items: list[dict] = []
    base = ARCHIVE / "01herosnews"
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        m = DATE_RE.match(entry.name)
        if not m:
            continue
        date_str = m.group(1)
        # Find primary HTML file in this dir
        htmls = sorted(entry.glob("*.html"))
        htmls = [h for h in htmls if "@" not in h.name]
        if not htmls:
            continue
        primary = htmls[0]
        html = primary.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        body = visible_text_blocks(soup)
        if not body or len(body) < 5:
            continue
        title = derive_title(body, date_str)
        images = collect_local_images(primary, soup)
        items.append({
            "id": entry.name,
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "slug": entry.name,
            "title": title,
            "body": body,
            "images": images,
            "source": str(primary.relative_to(ARCHIVE)),
        })
    items.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)
    return items


# ---------- About / What's HERO'S -----------------------------------------


def extract_about() -> dict | None:
    p = ARCHIVE / "07whatsheros" / "index.html"
    if not p.exists():
        return None
    soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "lxml")
    body = visible_text_blocks(soup)
    return {"title": "HERO'S とは", "body": body, "source": str(p.relative_to(ARCHIVE))}


def main() -> None:
    news = extract_news()
    (OUT / "news.json").write_text(
        json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"news: {len(news)} items")

    about = extract_about()
    if about:
        (OUT / "about.json").write_text(
            json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"about: {len(about['body'])} chars")


if __name__ == "__main__":
    main()
