"""Contact sheet of our pictures (clean), or ASCII dumps to draw over.

    python -m games.smb.sheet png <out.png> [name filter regex]
    python -m games.smb.sheet txt [name filter regex]        # current art as ASCII
"""
import re
import sys

import numpy as np

from cleanroom.gfx import png
from cleanroom.nes import chr as C
from games.smb import art as A
from games.smb import atlas, generate, palettes


def pal_of(p):
    return (palettes.SPR if p["page"] == 0 else palettes.BG)[p["pal"]]


def full(p, tiles):
    """picture composed from the final tiles (shows shared tiles from their owners)"""
    return C.compose(tiles, p["layout"], p["flips"])


def main(argv):
    mode = argv[1]
    flt = re.compile(argv[3] if mode == "png" and len(argv) > 3 else argv[2] if mode == "txt" and len(argv) > 2 else ".")
    _, tiles = generate.build_chr()
    P = [p for p in atlas.pictures() if p["kind"] != "glyph" and flt.search(p["name"])]
    if mode == "txt":
        own = atlas.owners(atlas.pictures())
        allp = atlas.pictures()
        for p in P:
            idx = next(i for i, q in enumerate(allp) if q["name"] == p["name"])
            owned = [[t is not None and own[t][0] == idx for t in r] for r in p["layout"]]
            print("@ " + p["name"])
            print(A.ascii_of(full(p, tiles), owned))
        return
    k, cols, x, y, rowh = 4, 1040, 4, 4, 0
    cv = np.full((2400, cols, 3), 30, np.uint8)
    for p in P:
        img = C.upscale(C.rgb(full(p, tiles), pal_of(p)), k)
        h, w = img.shape[:2]
        if x + w + 4 > cols:
            x, y, rowh = 4, y + rowh + 6, 0
        cv[y:y + h, x:x + w] = img
        x += w + 6
        rowh = max(rowh, h)
    png.write(argv[2], cv[:y + rowh + 4])
    print(f"sheet {argv[2]}: {len(P)} pictures")


if __name__ == "__main__":
    main(sys.argv)
