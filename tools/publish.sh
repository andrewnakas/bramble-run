#!/bin/sh
# Rebuild the clean ROM and the site; with "push" as $1 also push gh-pages. Originality and taint must be 0 failing.
# Repo is in takedown (2026-10-19): only the owner republishes; run without "push".
#   sh tools/publish.sh [push] ["message"]
set -e
W=${SMB_WORK:-/d/n64work/smb}
R="$(cd "$(dirname "$0")/.." && pwd)"
cd "$R"
python -m games.smb.generate "$W"
python -m games.smb.orig_export "$W"
python -m cleanroom.originality "$W/dirty/orig" "$W/clean/orig" games/smb --report ORIGINALITY.md || { echo "originality not clean: not publishing"; exit 1; }
python -m games.smb.poster poster.png
python ports/ejs/make_site.py "$W/site" "$W/ejs/ejs" "$W/ejs/core-fceumm" "$W/clean/smb.nes"
# dirty-room check of the ROM, the site and this repository
python -m games.smb.taint_report "$W/dirty/baserom.nes" "$W/clean/smb.nes" "$W/site" "$R" | tee "$W/taint.txt" | cut -c1-200
grep -q "^TAINT: 0 failing" "$W/taint.txt" || { echo "taint not clean: not publishing"; exit 1; }
{ echo "# Taint report"; echo; echo '```'; cat "$W/taint.txt"; echo '```'; } > TAINT.md
[ "$1" = push ] || exit 0
cd "$W/site"
[ -d .git ] || { git init -q && git remote add origin https://github.com/andrewnakas/smb-cleanroom.git; }
git config user.name andre; git config user.email treesixtyweather@gmail.com
# one orphan commit per deploy keeps the Pages branch small
git checkout -q --orphan tmp && git add -A && git commit -qm "Site: ${2:-rebuild}" && { git branch -D gh-pages -q 2>/dev/null || true; } && git branch -m gh-pages && git push -q -f origin gh-pages && echo "pushed gh-pages"
