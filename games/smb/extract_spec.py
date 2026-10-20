"""DIRTY ROOM: read the retail ROM, write the kept facts to games/smb/spec/.

Per picture (see atlas.py): size, a 1-bit silhouette (pixel is backdrop /
transparent or not) and a colour grid of at most 4x4 cells over the WHOLE
picture (cells never smaller than 4x4 px; a lone 8x8 tile gets one cell).
Glyphs and the title logo keep nothing. Also: sha1s for the taint scan.

    python -m games.smb.extract_spec <baserom.nes>
"""
import hashlib
import json
import os
import sys

import numpy as np

from cleanroom.nes import chr as C
from games.smb import atlas

HERE = os.path.dirname(os.path.abspath(__file__))


def grid_dims(w, h):
    if w <= 8 and h <= 8:
        return 1, 1
    return min(4, w // 4), min(4, h // 4)


def main(argv):
    rom = open(argv[1], "rb").read()
    _, prg, chr_ = C.split_ines(rom)
    tiles = C.decode(chr_)
    out = {}
    for p in atlas.pictures():
        if p["kind"] in ("glyph", "own"):
            continue
        img = C.compose(tiles, p["layout"], p["flips"])
        h, w = img.shape
        if p["name"] == "fills":
            out[p["name"]] = dict(w=w, h=h, uniform=[int(tiles[t][0, 0]) for t in p["layout"][0]])
            continue
        gw, gh = grid_dims(w, h)
        grid = []
        for gy in range(gh):
            row = []
            for gx in range(gw):
                cell = img[gy * h // gh:(gy + 1) * h // gh, gx * w // gw:(gx + 1) * w // gw].ravel()
                nz = cell[cell > 0]
                row.append(int(np.bincount(nz, minlength=4).argmax()) if len(nz) else 0)
            grid.append(row)
        out[p["name"]] = dict(w=w, h=h, sil=["".join("#" if v else "." for v in r) for r in img], grid=grid)
    os.makedirs(os.path.join(HERE, "spec"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "spec", "pictures.json"), "w"), indent=0)
    meta = dict(prg_sha1=hashlib.sha1(prg).hexdigest(), chr_sha1=hashlib.sha1(chr_).hexdigest(),
                rom_sha1=hashlib.sha1(rom).hexdigest(),
                font_index=int(np.bincount(np.concatenate([tiles[t][tiles[t] > 0] for t in atlas.FONT]), minlength=4).argmax()))
    json.dump(meta, open(os.path.join(HERE, "spec", "meta.json"), "w"), indent=1)
    print(f"spec: {len(out)} pictures with silhouette + grid; prg {meta['prg_sha1'][:10]} chr {meta['chr_sha1'][:10]}")


if __name__ == "__main__":
    main(sys.argv)
