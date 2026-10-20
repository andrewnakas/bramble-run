"""Render every atlas picture of a ROM's CHR to PNG, for the originality gate's
`images` kind (retail and clean ROMs go through the same code, paired by name).

    python -m games.smb.pictures_export <rom.nes> <outdir>     # -> <outdir>/pictures/<name>.png

Index 0 is written transparent; preview palettes are the sheet's (ours), the
same for both ROMs, so only the drawing differs. DIRTY ROOM when given the
retail ROM: the output folder must stay outside the repository.
"""
import os
import sys

import numpy as np

from cleanroom.gfx import png
from cleanroom.nes import chr as C
from games.smb import atlas, palettes


SKIP = {"fills"}        # the four uniform fill tiles (one colour each): structure, not a picture


def _pal(p):
    return (palettes.SPR if p["page"] == 0 else palettes.BG)[p["pal"]]


def export(rom_bytes, outdir, scale=4):
    _, _, chr_ = C.split_ines(rom_bytes)
    tiles = C.decode(chr_)
    d = os.path.join(outdir, "pictures")
    os.makedirs(d, exist_ok=True)
    n = 0
    for p in atlas.pictures():
        if p["name"] in SKIP:
            continue
        idx = C.compose(tiles, p["layout"], p["flips"])
        rgb = C.rgb(idx, _pal(p))
        a = np.where(idx > 0, 255, 0).astype(np.uint8)[..., None]
        img = np.concatenate([rgb, a], axis=2)
        img = img.repeat(scale, 0).repeat(scale, 1)
        png.write(os.path.join(d, p["name"] + ".png"), img)
        n += 1
    return n


if __name__ == "__main__":
    print(export(open(sys.argv[1], "rb").read(), sys.argv[2]), "pictures ->", sys.argv[2])
