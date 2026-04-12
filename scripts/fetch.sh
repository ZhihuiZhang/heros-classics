#!/bin/bash
# Usage: fetch.sh <ts> <url>
set -u
ts="$1"
url="$2"

path="${url#http://}"
path="${path#https://}"
path="${path/:80/}"
if [[ "$path" == hero-s.com* ]]; then
  path="www.${path}"
fi

host="${path%%/*}"
rest="${path#"$host"}"
rest="${rest#/}"

if [ -z "$rest" ] || [[ "$rest" == */ ]]; then
  rest="${rest}index.html"
fi
rest="${rest//\?/@}"

local_path="site/${host}/${rest}"
mkdir -p "$(dirname "$local_path")"

if [ -s "$local_path" ]; then
  exit 0
fi

fetch_url="https://web.archive.org/web/${ts}id_/${url}"

# Retry with backoff: handle rate limit (429/503) and connection failures
for attempt in 1 2 3 4 5; do
  http=$(curl -sS -L --max-time 90 -A "Mozilla/5.0" \
      -w "%{http_code}" -o "$local_path.tmp" "$fetch_url" 2>/dev/null)
  rc=$?
  if [ $rc -eq 0 ] && [ -s "$local_path.tmp" ] && [ "$http" = "200" ]; then
    mv "$local_path.tmp" "$local_path"
    exit 0
  fi
  rm -f "$local_path.tmp"
  # Exponential backoff: 2, 5, 10, 20, 40 seconds
  case $attempt in
    1) sleep 2 ;;
    2) sleep 5 ;;
    3) sleep 10 ;;
    4) sleep 20 ;;
    5) sleep 40 ;;
  esac
done
echo "FAIL $ts $url rc=$rc http=$http" >&2
exit 1
