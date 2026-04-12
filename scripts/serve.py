#!/usr/bin/env python3
"""Local server for the hero-s archive.

- Serves files under site/www.hero-s.com/
- Maps URL query strings (?a=b) to filesystem @a=b (wget convention).
"""
import http.server
import os
import socketserver
import sys
from urllib.parse import unquote

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "www.hero-s.com")
PORT = int(os.environ.get("PORT", "8000"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        raw = self.path.split("#", 1)[0]
        if "?" in raw:
            path_part, query = raw.split("?", 1)
            candidate = path_part + "@" + query
            fs = os.path.normpath(os.path.join(ROOT, unquote(candidate).lstrip("/")))
            if os.path.isfile(fs):
                return fs
        fs = os.path.normpath(os.path.join(ROOT, unquote(path_part if "?" in raw else raw).lstrip("/")))
        if os.path.isdir(fs):
            idx = os.path.join(fs, "index.html")
            if os.path.isfile(idx):
                return idx
        return fs


if __name__ == "__main__":
    os.chdir(ROOT)
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving {ROOT} at http://127.0.0.1:{PORT}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
