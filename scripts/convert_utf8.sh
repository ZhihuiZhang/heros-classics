#!/bin/bash
# Convert HTML/CSS files to UTF-8 (auto-detect CP932 vs already-UTF-8) and rewrite charset meta
set -u
ROOT="${1:-site}"
converted=0
kept=0
failed=0
while IFS= read -r -d '' f; do
  if iconv -f UTF-8 -t UTF-8 "$f" > /dev/null 2>&1; then
    # Already valid UTF-8, just rewrite meta
    kept=$((kept+1))
  else
    tmp="${f}.utf8"
    if iconv -f CP932 -t UTF-8//TRANSLIT "$f" > "$tmp" 2>/dev/null; then
      mv "$tmp" "$f"
      converted=$((converted+1))
    else
      rm -f "$tmp"
      echo "FAIL convert: $f" >&2
      failed=$((failed+1))
      continue
    fi
  fi
  LC_ALL=C sed -E -i '' \
    -e 's/(charset=)[Ss]hift[_-]?JIS/\1UTF-8/g' \
    -e 's/(charset=)[xX]-sjis/\1UTF-8/g' \
    -e 's/(charset=)[Cc][Pp]932/\1UTF-8/g' \
    -e 's/(charset=)[eE][uU][cC]-[jJ][pP]/\1UTF-8/g' \
    "$f"
done < <(find "$ROOT" -type f \( -iname '*.html' -o -iname '*.htm' -o -iname '*.css' -o -name '*.html@*' \) -print0)
echo "converted=$converted kept_as_utf8=$kept failed=$failed"
