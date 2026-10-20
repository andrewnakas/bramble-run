"""One contact sheet: title screen + one mid-level frame from each bot strip.

    python -m games.smb.contact <rom> <bot dir> <out.png>
"""
import glob
import os
import sys

import numpy as np

from cleanroom.gfx import png


def main(rom, botdir, out):
    from games.smb import bot
    bot._keys()
    from cynes import NES
    n = NES(rom)
    title = n.step(150).copy()
    tiles = [title]
    for f in sorted(glob.glob(os.path.join(botdir, "?-?.png"))):
        im = png.read(f)[:, :, :3]
        k = min(4, im.shape[1] // 256 - 1)
        tiles.append(im[:240, 256 * k:256 * k + 256])
    while len(tiles) % 6:
        tiles.append(np.zeros_like(title))
    rows = [np.concatenate(tiles[i:i + 6], axis=1) for i in range(0, len(tiles), 6)]
    png.write(out, np.concatenate(rows, axis=0))
    print(out, len(tiles), "cells")


if __name__ == "__main__":
    main(*sys.argv[1:4])
