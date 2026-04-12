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

# In-text patterns to remove (substring substitution)
STRIP_PATTERNS = [
    re.compile(r"Copyright\s*\(C\)\s*\d{4}\s*HERO-?S[^\n]*", re.IGNORECASE),
    re.compile(r"Copyright\s*\(C\)\s*\d{4}\s*G\.?T\.?Entertainment[^\n]*", re.IGNORECASE),
    re.compile(r"当サイトで使用している写真およびテキストの無断転載を禁止します。?"),
    re.compile(r"Mail\s*to\s*:?\s*official@hero-s\.com", re.IGNORECASE),
    re.compile(r"[\w.+-]*@hero-s\.com", re.IGNORECASE),
    re.compile(r"https?://(www\.)?dreamofficial\.com[^\s]*", re.IGNORECASE),
    re.compile(r"https?://(www\.)?hero-s\.com[^\s]*", re.IGNORECASE),
    re.compile(r"https?://(eee\.)?eplus\.(co\.)?jp[^\s]*", re.IGNORECASE),
]

# Whole-line drop patterns: if a line matches any of these, drop the whole line
LINE_DROP_PATTERNS = [
    re.compile(r"株式会社\s*キョードー"),
    re.compile(r"キョードー(東京|チケットセンター|大阪|名古屋|横浜)"),
    # TEL/FAX/電話 followed by digits or colon (i.e. a phone number)
    re.compile(r"(?:TEL|Tel|tel|FAX|Fax|fax)[\s::\-－ｰ]*[\d0-9０-９]"),
    re.compile(r"電話[\s::]*\d"),
    re.compile(r"お問[いあ]?\s*合[わ]?\s*せ"),
    re.compile(r"問\s*い?\s*合わせ"),
    re.compile(r"ファンクラブ.*\d{2,}"),
    re.compile(r"特電"),
    # 0570 (Japan navi-dial) with ascii/full-width/katakana hyphens
    re.compile(r"0570[\-－ｰ]?\d{2,3}[\-－ｰ]?\d{3,4}"),
    # Phone-like with any Unicode hyphen variant
    re.compile(r"0\d{1,4}[\-－ｰ]\d{1,4}[\-－ｰ]\d{3,4}"),
    re.compile(r"^\s*\(\s*0\d{1,4}\)\s*\d"),
    # Lines mentioning eplus
    re.compile(r"eplus\.jp", re.IGNORECASE),
    # Booking/code lines that reference 0570 indirectly
    re.compile(r"0570から始まる"),
    re.compile(r"Lコード[:：]"),
    # 実行委員会/開催事務局 contact lines
    re.compile(r"(実行委員会|開催事務局).*?\d{2,4}[\-－]\d"),
]

# Patterns matched against the FULL src path
CHROME_PATH = re.compile(
    r"(img_share|img_head|/share/|/common/|/nav/|/header/|/footer/)",
    re.IGNORECASE,
)
# Patterns matched against the basename only
CHROME_NAME = re.compile(
    r"(^he[\W_]?\d+\.gif$|^bt_|^btn_|^sub_|^nav_|footer|spacer|^menu_"
    r"|^headline_|^line\.gif$|blank|arrow|sideline|sidedot|side_"
    r"|title\.gif$|_title\.gif$|^title|^bg_|background|copyright|^bar)",
    re.IGNORECASE,
)
# Article photos (preferred)
PHOTO_NAME = re.compile(r"(ph\d+\.jpg|photo\d*\.jpg|^p\d+\.jpg|^img\d+\.jpg)$", re.IGNORECASE)


BOILERPLATE_RE = re.compile(
    r"(HERO'?S|HERO-?S|NEWS|OFFICIAL|ニュース|オフィシャル|トップ|HOME|MENU"
    r"|What's|ファイターズ|イベント|スケジュール|メディア|インフォメーション|INFO"
    r"|投票|VOTE|リンク|PROFILE|プロフィール)",
    re.IGNORECASE,
)


TITLE_SKIP_RE = re.compile(
    r"(HERO'?S.*?[★☆][^\s]*|EVENT\s*(SCHEDULE|RESULT)|"
    r"FIGHTERS?\s*(INFO|PROFILE)|MEDIA\s*INFO|NEWS|VOTE|TOP|HOME)",
    re.IGNORECASE,
)


def derive_title(body: str, date_str: str) -> str:
    for line in body.split("\n"):
        line = line.strip()
        line = re.sub(r"^[■●◆▼▲※»\s]+", "", line).strip()
        if len(line) < 6:
            continue
        # Skip lines that look like nav/title-tag boilerplate
        if TITLE_SKIP_RE.search(line) and len(line) < 40:
            continue
        if len(line) < 20 and BOILERPLATE_RE.search(line):
            continue
        if line.startswith(("http://", "https://")):
            continue
        if len(line) > 70:
            line = line[:70].rstrip() + "…"
        return line
    return f"HERO'S {date_str}"


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
        # Drop entire line if it matches contact/company patterns
        if any(p.search(line) for p in LINE_DROP_PATTERNS):
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
    """Return list of article-photo paths (relative to ARCHIVE).

    Filters out site chrome (nav, headers, banners, title gifs, etc).
    Photos (ph*.jpg style) come first, then other plausible images.
    """
    photos: list[str] = []
    others: list[str] = []
    seen: set[str] = set()
    base = html_path.parent
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        name = src.rsplit("/", 1)[-1]
        if CHROME_PATH.search(src) or CHROME_NAME.search(name):
            continue
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
        if PHOTO_NAME.search(name):
            photos.append(rel_str)
        else:
            others.append(rel_str)
    return photos + others


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


# ---------- Events ---------------------------------------------------------


def extract_events() -> list[dict]:
    """Event schedules (02eventschedule/YYYYMMDD/)."""
    items: list[dict] = []
    base = ARCHIVE / "02eventschedule"
    if not base.exists():
        return items
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        m = DATE_RE.match(entry.name)
        if not m:
            continue
        date_str = m.group(1)
        htmls = [h for h in sorted(entry.glob("*.html")) if "@" not in h.name]
        if not htmls:
            continue
        primary = htmls[0]
        soup = BeautifulSoup(primary.read_text(encoding="utf-8", errors="replace"), "lxml")
        body = visible_text_blocks(soup)
        if not body:
            continue
        images = collect_local_images(primary, soup)
        nice_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}"
        items.append({
            "id": entry.name,
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "slug": entry.name,
            "title": f"HERO'S {nice_date} 大会概要",
            "body": body,
            "images": images,
            "source": str(primary.relative_to(ARCHIVE)),
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def extract_event_results() -> list[dict]:
    """Event result top pages (03eventresult/YYYYMMDD/*.html at top level)."""
    items: list[dict] = []
    base = ARCHIVE / "03eventresult"
    if not base.exists():
        return items
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        m = DATE_RE.match(entry.name)
        if not m:
            continue
        date_str = m.group(1)
        # Top-level HTMLs (index / overview), ignore per-fight subdirs here
        top_htmls = [
            h for h in sorted(entry.glob("*.html"))
            if "@" not in h.name
        ]
        if not top_htmls:
            continue
        primary = top_htmls[0]
        soup = BeautifulSoup(primary.read_text(encoding="utf-8", errors="replace"), "lxml")
        body = visible_text_blocks(soup)
        if not body:
            continue
        images = collect_local_images(primary, soup)
        nice_date = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:8]}"
        # Collect additional sub-pages (per fight)
        subpages: list[dict] = []
        for sub in sorted(entry.iterdir()):
            if not sub.is_dir():
                continue
            for sub_html in sorted(sub.glob("*.html")):
                if "@" in sub_html.name:
                    continue
                sub_soup = BeautifulSoup(
                    sub_html.read_text(encoding="utf-8", errors="replace"), "lxml")
                sub_body = visible_text_blocks(sub_soup)
                if not sub_body or len(sub_body) < 20:
                    continue
                sub_title = derive_title(sub_body, date_str)
                sub_images = collect_local_images(sub_html, sub_soup)
                subpages.append({
                    "slug": sub.name,
                    "title": sub_title,
                    "body": sub_body,
                    "images": sub_images,
                })
                break
        items.append({
            "id": entry.name,
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "slug": entry.name,
            "title": f"HERO'S {nice_date} 試合結果",
            "body": body,
            "images": images,
            "subpages": subpages,
            "source": str(primary.relative_to(ARCHIVE)),
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


# ---------- Fighters -------------------------------------------------------


FIGHTER_LABELS = {
    "所属": "team",
    "生年月日": "birth",
    "出身地": "origin",
    "身長": "height",
    "体重": "weight",
    "バックボーン": "background",
    "主な獲得タイトル": "titles",
    "対戦成績": "record_summary",
}


def parse_fighter(html_path: Path) -> dict | None:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    raw_lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    # Drop leading boilerplate
    lines: list[str] = []
    for l in raw_lines:
        if not lines and ("HERO" in l or "PROFILE" in l or "FIGHTERS" in l):
            continue
        # Drop copyright/mail lines
        if any(p.search(l) for p in STRIP_PATTERNS):
            continue
        lines.append(l)
    if not lines:
        return None
    name_jp = lines[0] if lines else ""
    name_en = lines[1] if len(lines) > 1 and re.search(r"[A-Za-z]", lines[1]) else ""
    info: dict[str, str] = {}
    i = 2 if name_en else 1
    while i < len(lines):
        label = lines[i]
        if label in FIGHTER_LABELS and i + 1 < len(lines):
            info[FIGHTER_LABELS[label]] = lines[i + 1]
            i += 2
        else:
            i += 1
    images = collect_local_images(html_path, soup)
    slug_dir = html_path.parent.name
    category = html_path.parent.parent.name
    return {
        "id": f"{category}/{slug_dir}",
        "slug": slug_dir,
        "category": category,
        "name_jp": name_jp,
        "name_en": name_en,
        "info": info,
        "images": images,
        "source": str(html_path.relative_to(ARCHIVE)),
    }


def extract_fighters() -> list[dict]:
    items: list[dict] = []
    base = ARCHIVE / "06fightersinfo"
    if not base.exists():
        return items
    for category in sorted(base.iterdir()):
        if not category.is_dir() or category.name == "img_share":
            continue
        for fighter_dir in sorted(category.iterdir()):
            if not fighter_dir.is_dir():
                continue
            htmls = [h for h in sorted(fighter_dir.glob("*.html")) if "@" not in h.name]
            if not htmls:
                continue
            result = parse_fighter(htmls[0])
            if result:
                items.append(result)
    items.sort(key=lambda x: (x["category"], x["slug"]))
    return items


# ---------- About / What's HERO'S -----------------------------------------


def extract_about() -> dict | None:
    p = ARCHIVE / "07whatsheros" / "index.html"
    if not p.exists():
        return None
    soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "lxml")
    body = visible_text_blocks(soup)
    return {"title": "HERO'S とは", "body": body, "source": str(p.relative_to(ARCHIVE))}


def _save(name: str, data) -> None:
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    news = extract_news()
    _save("news.json", news)
    print(f"news: {len(news)} items")

    events = extract_events()
    _save("events.json", events)
    print(f"events: {len(events)} items")

    results = extract_event_results()
    _save("results.json", results)
    print(f"results: {len(results)} items")

    fighters = extract_fighters()
    _save("fighters.json", fighters)
    print(f"fighters: {len(fighters)} items")

    about = extract_about()
    if about:
        _save("about.json", about)
        print(f"about: {len(about['body'])} chars")


if __name__ == "__main__":
    main()
