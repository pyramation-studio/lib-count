#!/bin/bash
# For each GitHub repo (owner/name), find the earliest commits whose package.json diff
# introduced one of our package names (git log -S pickaxe on a blobless clone).
# Usage: CG_DATA_DIR=./data ./who_added.sh owner/repo [owner/repo ...]
# Output: $CG_DATA_DIR/who_added.tsv  (repo, pattern, sha, date, author name, subject)
DATA="${CG_DATA_DIR:-$PWD/data}"
CLONES="${CG_CLONE_DIR:-$DATA/clones}"
mkdir -p "$DATA" "$CLONES"
out="$DATA/who_added.tsv"
PATTERNS=${CG_PATTERNS:-'"libpg-query" "pgsql-parser" "@pgsql/types" "@libpg-query/parser" "pgsql-deparser" "@pgsql/traverse" "kubernetesjs" "@pgpmjs/core"'}
for r in "$@"; do
  d="$CLONES/$(echo "$r" | tr / _)"
  [ -d "$d" ] || git clone -q --filter=blob:none --no-checkout "https://github.com/$r" "$d" 2>/dev/null
  (
    cd "$d" || exit 0
    eval "set -- $PATTERNS"
    for pat in "$@"; do
      timeout 240 git log --reverse --format="$r	$pat	%h	%ad	%an	%s" --date=short -S"$pat" -- '*package.json' 2>/dev/null | head -2 >> "$out"
    done
  )
done
