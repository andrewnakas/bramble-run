"""16:9 poster composed from our own tiles (no screenshot, no retail art).

    python -m games.smb.poster poster.png
"""
import sys

import numpy as np

from cleanroom.gfx import png
from cleanroom.nes import chr as C
from games.smb import atlas, generate, palettes, title

W, H, K = 320, 180, 4


def main(argv):
    _, tiles = generate.build_chr()
    P = {p["name"]: p for p in atlas.pictures()}
    cv = np.zeros((H, W, 3), np.uint8)
    cv[:] = C.MASTER[palettes.SKY]

    def put(name, x, y, pal=None, flip=False):
        p = P[name]
        idx = C.compose(tiles, p["layout"], p["flips"])
        if flip:
            idx = idx[:, ::-1]
        rgb = C.rgb(idx, pal or (palettes.SPR if p["page"] == 0 else palettes.BG)[p["pal"]])
        h, w = idx.shape
        ys, xs = max(0, -y), max(0, -x)
        ye, xe = min(h, H - y), min(w, W - x)
        if ye <= ys or xe <= xs:
            return
        m = idx[ys:ye, xs:xe] > 0
        cv[y + ys:y + ye, x + xs:x + xe][m] = rgb[ys:ye, xs:xe][m]

    def cut(name, r0, r1, c0, c1):
        """sub-picture (tile rows/cols) as a temporary picture"""
        p = P[name]
        q = dict(p, name=name + "_cut", layout=[r[c0:c1] for r in p["layout"][r0:r1]],
                 flips=[r[c0:c1] for r in p["flips"][r0:r1]])
        P[q["name"]] = q
        return q["name"]

    G = 164                                             # ground line
    for x in range(0, W, 16):
        put("ground", x, G)
    put("hill", 4, G - 16)
    put("cloud_bush", 250, 6)
    put("cloud_bush", -6, 26)
    bush = cut("cloud_bush", 0, 2, 0, 4)
    put(bush, 196, G - 16, palettes.BG[0])
    put("pipe_up", 268, G - 32)
    put(cut("pipe_up", 2, 3, 0, 4), 268, G - 8)
    for i, n in enumerate(["brick", "qblock", "brick", "qblock", "brick"]):
        put(n, 20 + 16 * i, 116)
    put("player_big_jumping", 112, 122)
    put("enemy_goomba", 168, G - 16, palettes.SPR[3])
    put("enemy_koopa_troopa_frame_1", 226, G - 24, flip=True)
    put("powerup_regular_mushroom", 52, 100, palettes.SPR[2])
    put("coin_bg", 36, 96)

    # title board: our own tiles and nametable script, as the game draws it
    nt = np.full((30, 32), 0x24, np.uint8)
    d, i = title.script(), 0
    while d[i]:
        a, c = (d[i] << 8 | d[i + 1]) - 0x2000, d[i + 2]
        n, rep, vert = c & 63, c & 64, c & 128
        data = [d[i + 3]] * n if rep else list(d[i + 3:i + 3 + n])
        i += 4 if rep else 3 + n
        for k, t in enumerate(data):
            b = a + (32 * k if vert else k)
            if b < 960:
                nt[b // 32, b % 32] = t
    board = C.compose(tiles, [[0x100 + int(t) for t in r[5:27]] for r in nt[4:15]])
    rgb = C.rgb(board, palettes.BG[1])
    bx, by = (W - board.shape[1]) // 2, 8
    m = board > 0
    cv[by:by + board.shape[0], bx:bx + board.shape[1]][m] = rgb[m]

    def text(s, x, y, col):
        for k, ch in enumerate(s):
            if ch == " ":
                continue
            g = tiles[next(t for t, c in atlas.FONT.items() if c == ch)] > 0
            cv[y:y + 8, x + 8 * k:x + 8 * k + 8][g] = col

    text("CLEAN ROOM BUILD", (W - 128) // 2 + 1, 101, (0, 0, 0))
    text("CLEAN ROOM BUILD", (W - 128) // 2, 100, (255, 255, 255))
    out = C.upscale(cv, K)
    png.write(argv[1], out)
    print(f"poster {argv[1]}: {out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    main(sys.argv)
