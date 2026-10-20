#!/bin/sh
# Headless screenshots of a level: sh games/smb/shots.sh <name> <W,L,A> "<cdp script after start>"
#   builds clean/dev.nes, serves the site on 8481 with it, writes D:/n64work/smb/shots/<name>/sheet.png
W=${SMB_WORK:-/d/n64work/smb}
cd "$(dirname "$0")/../.."
python -m games.smb.generate "$W" dev=$2 | tail -1
cp "$W/clean/dev.nes" "$W/site/dev.nes"
(python ports/wasm/serve.py "$W/site" 8481 >/dev/null 2>&1 &)
CDP_MUTE=1 python ports/ejs/cdp_shot.py "$W/shots/$1" --url "http://localhost:8481/index.html?autostart=1&rom=dev.nes" --script "$3" --webgl --wait 70
rm -f "$W/site/dev.nes"
python - "$W/shots/$1" <<'P'
import sys, glob, os
sys.path.insert(0, '.')
import numpy as np
from cleanroom.gfx import png
d = sys.argv[1]
fs = sorted(glob.glob(d + '/shot_*.png'), key=lambda f: float(os.path.basename(f)[5:-4]))
ims = [png.read(f)[:, :, :3] for f in fs]
ims = [im[0:600, 130:800][::2, ::2] for im in ims]
while len(ims) % 3:
    ims.append(np.zeros_like(ims[0]))
rows = [np.concatenate(ims[i:i + 3], axis=1) for i in range(0, len(ims), 3)]
png.write(d + '/sheet.png', np.concatenate(rows, axis=0))
print(d + '/sheet.png', len(fs), 'shots')
P
