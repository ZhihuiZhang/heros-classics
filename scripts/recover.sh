#!/bin/bash
# For each localhost URL on stdin, check CDX for a status=200 snapshot.
# If found, fetch via id_ mode and save locally.
set -u
ok=0
nosnap=0
dead=0
fail=0
while IFS= read -r local_url; do
  [ -z "$local_url" ] && continue
  rel="${local_url#http://127.0.0.1:8000/}"
  rest="${rel//\?/@}"
  local_path="site/www.hero-s.com/${rest}"
  [ -z "${rest##*/}" ] && local_path="${local_path}index.html"
  if [ -s "$local_path" ]; then
    ok=$((ok+1))
    continue
  fi

  orig="http://www.hero-s.com/${rel}"
  cdx=$(curl -sS --max-time 30 \
    "https://web.archive.org/cdx/search/cdx?url=www.hero-s.com/${rel}&filter=statuscode:200&limit=1&fl=timestamp,original")
  if [ -z "$cdx" ]; then
    # Try without www
    cdx=$(curl -sS --max-time 30 \
      "https://web.archive.org/cdx/search/cdx?url=hero-s.com/${rel}&filter=statuscode:200&limit=1&fl=timestamp,original")
  fi
  if [ -z "$cdx" ]; then
    dead=$((dead+1))
    continue
  fi
  ts=$(printf '%s' "$cdx" | awk '{print $1}')
  src=$(printf '%s' "$cdx" | awk '{print $2}')
  fetch_url="https://web.archive.org/web/${ts}id_/${src}"
  mkdir -p "$(dirname "$local_path")"
  for attempt in 1 2 3; do
    http=$(curl -sS -L --max-time 60 -A "Mozilla/5.0" \
      -w "%{http_code}" -o "${local_path}.tmp" "$fetch_url" 2>/dev/null)
    if [ -s "${local_path}.tmp" ] && [ "$http" = "200" ]; then
      mv "${local_path}.tmp" "$local_path"
      ok=$((ok+1))
      echo "OK $local_path"
      break
    fi
    rm -f "${local_path}.tmp"
    sleep $((attempt*3))
  done
  if [ ! -s "$local_path" ]; then
    fail=$((fail+1))
    echo "FAIL $orig" >&2
  fi
done
echo "--- recovered=$ok dead_origin=$dead fail=$fail"
