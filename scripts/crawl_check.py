#!/usr/bin/env python3
"""Crawl local server and report broken links (internal only)."""
import re
import sys
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
import urllib.request

BASE = "http://127.0.0.1:8000/"
HREF_RE = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

visited = set()
broken = []
queue = deque([BASE])
limit = 2000

while queue and len(visited) < limit:
    url = queue.popleft()
    url, _ = urldefrag(url)
    if url in visited:
        continue
    visited.add(url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "check/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            ct = resp.headers.get("Content-Type", "")
            body = resp.read() if "html" in ct else b""
    except urllib.error.HTTPError as e:
        broken.append((url, f"HTTP {e.code}"))
        continue
    except Exception as e:
        broken.append((url, f"ERR {type(e).__name__}"))
        continue
    if status != 200:
        broken.append((url, f"HTTP {status}"))
        continue
    if not body:
        continue
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        continue
    for m in HREF_RE.finditer(text):
        link = m.group(1).strip()
        if link.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        absu = urljoin(url, link)
        p = urlparse(absu)
        if p.netloc and p.netloc != "127.0.0.1:8000":
            continue
        if absu not in visited:
            queue.append(absu)

print(f"visited={len(visited)} broken={len(broken)}")
for u, why in broken:
    print(f"  {why}  {u}")
