"""Preview of the two Bowser halves as the game places them (rear 16 px behind, 8 px lower).

    python -m games.smb.bowser_view out.png
"""
import sys

import numpy as np

from cleanroom.gfx import png
from cleanroom.nes import chr as C
from games.smb import atlas, generate, palettes

_, tiles = generate.build_chr()
P = {p["name"]: p for p in atlas.pictures()}
pal = [palettes.SKY] + palettes.TABLES["BowserPaletteData"][1][1:]
out = []
for f in ("enemy_bowser_frame_1", "enemy_bowser_frame_2"):
    idx = C.compose(tiles, P[f]["layout"], P[f]["flips"])
    cv = np.zeros((32, 32), np.uint8)
    cv[8:32, 0:16] = idx[:, 0:16]
    front = idx[:, 16:32]
    cv[0:24, 16:32] = np.where(front > 0, front, cv[0:24, 16:32])
    out.append(C.upscale(C.rgb(cv, pal), 8))
png.write(sys.argv[1], np.concatenate(out, axis=1))
