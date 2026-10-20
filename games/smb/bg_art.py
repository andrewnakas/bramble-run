"""Background (and a few sprite) pictures stated as code: our own designs for
Bramble Run, drawn on a pixel canvas. Each function returns art rows in the
art/*.txt alphabet (`.` = 0, `1 2 3` = colour). art.load_art() merges these
under the hand-drawn files.

Tile arrangement facts (which tile sits next to which) come from the code's
metatile tables; see atlas.BACKGROUND. Roles per background palette:
pal0 1 = light green, 2 = green, 3 = black; pal1 1 = sand, 2 = brown,
3 = black; pal2 1 = white, 2 = blue, 3 = black; pal3 1 = gold, 2 = brown, 3 = black.
"""
import numpy as np


def _c(w, h, v=0):
    return np.full((h, w), v, np.uint8)


def _rows(a):
    return ["".join(".123"[v] for v in r) for r in a]


def _rect(a, x0, y0, x1, y1, v):          # inclusive
    a[y0:y1 + 1, x0:x1 + 1] = v


def _disc(a, cx, cy, r, v, sy=1.0):
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    a[((xx + .5 - cx) ** 2 + ((yy + .5 - cy) / sy) ** 2) <= r * r] = v


def _outline(a, v=3):
    s = a > 0
    p = np.pad(s, 1)
    e = s & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    a[e] = v
    return a


def _arr(rows):
    return np.array([[".123".index(c) for c in r] for r in rows], np.uint8)


# ---------------------------------------------------------------- blocks
def brick():
    """cobbles: brown stones with dark lower-right shade set in sand mortar; 45 = top tile, 47 = wall tile"""
    t = _c(8, 8, 1)
    _rect(t, 1, 0, 6, 2, 2)
    _rect(t, 0, 4, 2, 6, 2)
    _rect(t, 4, 4, 7, 6, 2)
    t[2, 2:7] = 3
    t[0:3, 6] = 3
    t[6, 0:3] = 3
    t[6, 4:8] = 3
    t[4:7, 2] = 3
    a = _c(16, 16)
    for ox in (0, 8):
        a[8:16, ox:ox + 8] = t
    top = t.copy()
    top[0, :] = 3
    a[0:8, 0:8] = top
    a[0:8, 8:16] = top
    return _rows(a)


def ground():
    """pavers: two rows of offset slabs with a pebble, light top bevel"""
    a = _c(16, 16, 2)
    a[0, :] = 1
    a[7, :] = 3
    a[8, :] = 1
    a[15, :] = 3
    for x in (5, 13):
        a[0:7, x] = 3
        a[1:7, (x + 1) % 16] = 1
    for x in (1, 9):
        a[8:15, x] = 3
        a[9:15, x + 1] = 1
    for x, y in ((9, 3), (2, 4), (12, 11), (5, 12)):
        a[y, x] = 3
        a[y - 1, x] = 1
    return _rows(a)


def stair_block():
    """carved block: dark frame, raised square plate, diagonal shine"""
    a = _c(16, 16, 2)
    _rect(a, 0, 0, 15, 15, 3)
    _rect(a, 1, 1, 14, 14, 2)
    _rect(a, 4, 4, 11, 11, 1)
    a[4:12, 11] = 3
    a[11, 4:12] = 3
    a[1, 1:15] = 1
    a[1:15, 1] = 1
    for k in range(3):
        a[6 + k, 9 - k] = 2
    return _rows(a)


def castle_block():
    """5d (top row, repeated) / 5e: large ashlar, half offset"""
    a = _c(16, 16, 1)
    a[7, :] = 2
    a[15, :] = 2
    a[0:7, 3] = 2
    a[0:7, 11] = 2
    a[8:15, 7] = 2
    a[8:15, 15] = 2
    for y, x in ((2, 6), (3, 7), (10, 2), (12, 11)):
        a[y, x] = 3
    return _rows(a)


def qblock():
    """gold block, dark rim, brown shade, diamond rune in the middle"""
    a = _c(16, 16, 1)
    a[0, 1:15] = 3
    a[15, 1:15] = 3
    a[1:15, 0] = 3
    a[1:15, 15] = 3
    a[14, 1:15] = 2
    a[1:15, 14] = 2
    for y, x in ((2, 2), (2, 12), (12, 2), (12, 12)):
        a[y, x] = 3
    for k in range(5):
        a[3 + k, 7 - k:9 + k] = 3
        a[12 - k, 7 - k:9 + k] = 3
    for k in range(3):
        a[5 + k, 8 - k:8 + k] = 2
        a[10 - k, 8 - k:8 + k] = 2
    a[7:9, 7:9] = 1
    return _rows(a)


def used_block():
    """spent block: sand-framed crate, vertical brown boards with dark seams and nail heads"""
    a = _c(16, 16, 2)
    a[0, :] = a[15, :] = 1
    a[:, 0] = a[:, 15] = 1
    for x in (5, 10):
        a[1:15, x] = 3
    for x in (2, 7, 12):
        a[3, x] = a[12, x] = 3
    a[1:15, 1] = 1
    return _rows(a)


def _gem(bg):
    """wide hexagonal gem with a bright upper facet"""
    a = _c(16, 16, bg)
    for y in range(3, 13):
        d = max(0, 5 - y) if y < 5 else max(0, y - 10)
        a[y, 1 + d * 2:15 - d * 2] = 1
    a[8:13, :][a[8:13, :] == 1] = 2 if bg != 2 else 3
    a[3:13, 7:9][a[3:13, 7:9] > 0] = 1
    _outline_bg(a, bg)
    return a


def _outline_bg(a, bg):
    s = a != bg
    p = np.pad(s, 1)
    e = s & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    a[e] = 3 if bg != 3 else 1


def coin_bg():
    return _rows(_gem(0))


def coin_water():
    return _rows(_gem(2))


def axe():
    """pull lever: plate on the floor, slanted rod, round grip"""
    a = _c(16, 16)
    _rect(a, 2, 13, 13, 15, 3)
    _rect(a, 3, 13, 12, 14, 2)
    a[13, 3:13] = 1
    for k in range(10):
        a[12 - k, 5 + k // 2:7 + k // 2] = 3
        a[12 - k, 5 + k // 2] = 2
    _disc(a, 11.5, 2.5, 2.6, 3)
    _disc(a, 11.5, 2.5, 1.6, 1)
    return _rows(a)


def hud_coin():
    return ["...33...", "..3113..", ".311213.", "31111213", "32111123", ".322223.", "..3223..", "...33..."]


def cursor_mushroom():
    return [".3......", ".33.....", ".313....", ".3113...", ".31113..", ".3113...", ".313....", ".33....."]


def bridge():
    """rope bridge: planks hung from a rope line"""
    a = _c(16, 8)
    a[0, :] = 3
    a[1, :] = 2
    for x0 in (0, 8):
        _rect(a, x0, 2, x0 + 6, 6, 1)
        a[6, x0:x0 + 7] = 2
        a[2:7, x0 + 6] = 2
        a[4, x0 + 2] = 3
    return _rows(a)


def guardrail_chain():
    """c0 = rope rail with a post (repeats), 7f = chain link on the diagonal"""
    a = _c(16, 8)
    a[2, 0:8] = 3
    a[3, 0:8] = 1
    a[1:8, 3] = 3
    a[1:8, 4] = 2
    t = _c(8, 8)
    for k in range(8):
        if k % 3 != 2:
            t[k, k] = 3
            t[k, max(0, k - 1)] = 3
    t[2, 4] = t[5, 1] = 3
    a[:, 8:] = t
    return _rows(a)


def fence():
    a = _c(16, 16)
    for x0 in (1, 9):
        _rect(a, x0, 2, x0 + 4, 15, 1)
        a[2:16, x0 + 4] = 2
        a[1, x0 + 1:x0 + 4] = 1
        a[0, x0 + 2] = 1
    a[5, :] = 3
    a[11, :] = 3
    return _rows(a)


def water_rock():
    """sea block: crusted stone with holes"""
    a = _c(16, 16, 1)
    a[0, :] = 3
    a[:, 0] = 3
    a[15, :] = 3
    a[:, 15] = 3
    for cx, cy, r in ((5, 5, 2.2), (11, 10, 1.8), (4, 12, 1.2)):
        _disc(a, cx, cy, r, 2)
    for y, x in ((3, 11), (8, 3), (12, 9)):
        a[y, x] = 3
    a[1, 1:15] = 2
    return _rows(a)


def water_top():
    a = _c(16, 8, 2)
    a[0:4, :] = 0
    for x in range(16):
        y = [3, 2, 1, 1, 1, 2, 3, 3][x % 8]
        a[y:4, x] = 1
        a[4, x] = 1 if x % 4 < 2 else 2
    return _rows(a)


def cloud_block():
    """cloud floor: three puffs per block"""
    a = _c(16, 16)
    for cx, cy, r in ((4, 5, 4.2), (11.5, 5.5, 4.0), (8, 11, 4.8)):
        _disc(a, cx, cy, r, 1)
    s = a > 0
    a[12:16, :][s[12:16, :]] = 2
    _outline(a, 3)
    return _rows(a)


def bowser_bridge():
    """77 top / 79 bottom: chained girder"""
    a = _c(16, 16)
    _rect(a, 0, 0, 15, 5, 2)
    a[0, :] = 1
    a[5, :] = 3
    for x in (2, 7, 12):
        a[2:4, x:x + 2] = 1
    for k in range(8):
        a[6 + k, k] = 3
        a[6 + k, 15 - k] = 3
    return _rows(a)


def cannon():
    """launcher tower: domed muzzle with side ports, banded barrel, pedestal (2a | 40 repeat)"""
    a = _c(16, 40)
    top = _c(16, 32)
    _disc(top, 8, 9, 7.5, 2, sy=1.15)
    top[9:32, 1:15] = 2
    _disc(top, 6, 6, 3, 1)
    _outline(top, 3)
    _rect(top, 0, 8, 2, 11, 3)
    _rect(top, 13, 8, 15, 11, 3)
    top[14:16, :] = 3
    for y in (19, 25, 31):
        top[y, 1:15] = 3
        top[y - 1, 2:14] = 1
    _disc(top, 8, 22.5, 2.5, 3)
    _disc(top, 8, 22.5, 1.2, 1)
    a[:32] = top
    _rect(a, 2, 32, 13, 39, 2)
    a[32:40, 2] = 1
    a[32:40, 13] = 3
    a[32:40, 7] = 3
    a[32:40, 8] = 1
    a[36, 2:14] = 3
    return _rows(a)


def castle_parts():
    """9d 9e = merlons on brick, a9 aa = merlons with a slit, 9b 9c = gate arch over the dark doorway"""
    a = _c(32, 16)
    for x0 in (0, 16):
        _rect(a, x0 + 1, 2, x0 + 6, 7, 1)
        _rect(a, x0 + 10, 2, x0 + 15, 7, 1)
        a[2, x0 + 1:x0 + 7] = 2
        a[2, x0 + 10:x0 + 16] = 2
        a[7, x0:x0 + 16] = 3
        a[2:7, x0 + 6] = 3
        a[2:7, x0 + 15] = 3
    a[3:6, 21:24] = 3
    a[8:16, 0:16] = 3
    for x in range(16):
        d = abs(x - 7.5)
        h = max(1, int(round(8 - np.sqrt(max(0.0, 64 - (d * 1.05) ** 2)))))
        a[8:8 + h, x] = 1
        a[8 + h - 1, x] = 2
    a[8:16, 16:32] = _arr(brick())[8:16, :]
    return _rows(a)


def pulley():
    """3e 3f / 5b 5c wheels, 99 horizontal rope, a2 a3 = vertical rope (shared with the goal pole)"""
    a = _c(32, 24)
    for cx in (12, 20):
        _disc(a, cx, 12, 4.5, 3)
        _disc(a, cx, 12, 3, 2)
        _disc(a, cx, 12, 1, 1)
    a[0:8, :] = 0
    a[8:16, 7] = 2
    a[8:16, 8] = 3
    a[8:16, 23] = 2
    a[8:16, 24] = 3
    a[16, :] = 3
    a[17, :] = 1
    return _rows(a)


def flagpole():
    """2f 3d = finial (a lantern), a2 a3 = the pole (centred on the tile seam)"""
    a = _c(16, 16)
    _rect(a, 5, 1, 10, 6, 3)
    _rect(a, 6, 2, 9, 5, 1)
    a[3:5, 7:9] = 2
    a[0, 7:9] = 3
    a[7, 6:10] = 3
    a[8:16, 7] = 2
    a[8:16, 8] = 3
    return _rows(a)


def seaplant():
    """kelp: two waving fronds"""
    a = _c(16, 16)
    for k in range(16):
        x = 3 + int(round(1.5 * np.sin(k / 2.5)))
        a[k, x:x + 3] = 1
        if k >= 4:
            x2 = 10 + int(round(1.5 * np.cos(k / 2.2)))
            a[k, x2:x2 + 3] = 1
    for y in (3, 7, 11):
        a[y, 4] = 3
        a[y + 2, 11] = 3
    return _rows(_outline(a, 2))


def tree():
    """cypress: pointed crown (b8 b9), column (ba bb, also the toadstool stem), base (bc bd), trunk (be bf)"""
    a = _c(16, 32)
    for y in range(24):
        half = min(7, 1 + y // 2) if y < 16 else 7 - max(0, y - 19)
        a[y, 8 - half:8 + half] = 1
    for y in range(2, 24, 3):
        for x in range(16):
            if a[y, x] and (x + y) % 4 == 0:
                a[y, x] = 2
    sub = a[:24, 9:]
    sub[sub == 1] = 2
    _outline(a[:24], 3)
    a[8:16, 1:15] = np.where(a[8:16, 1:15] == 0, 1, a[8:16, 1:15])
    a[8:16, 0] = 3
    a[8:16, 15] = 3
    a[24:32, 6:10] = 2
    a[24:32, 6] = 3
    a[24:32, 9] = 3
    a[24:32, 7] = 1
    return _rows(a)


def tree_ledge():
    """leaf-shelf platform with a scalloped leaf rim: 4b cap, 4d top, 50 cap; 4c 4f 4e 51 under-row; 52 trunk"""
    a = _c(32, 24)
    _rect(a, 0, 3, 31, 12, 2)
    for cx in range(2, 32, 4):
        _disc(a, cx, 4, 2.2, 1)
    for y in (7, 10):
        for x in range(32):
            if (x + y) % 5 == 0:
                a[y, x] = 1
    for cx in range(0, 34, 4):
        _disc(a, cx, 12.5, 2.0, 2)
    a[:16][a[:16] == 0] = 0
    sub = a[:16].copy()
    _outline(sub, 3)
    sub[:, 0] = np.where(a[:16, 0] > 0, 3, 0)
    a[:16] = sub
    a[16:24, 12:20] = 2
    a[16:24, 12] = 3
    a[16:24, 19] = 3
    a[16:24, 14] = 1
    return _rows(a)


def mushroom_ledge():
    """flat cap shelf with spots; stump top 75 76"""
    a = _c(48, 24)
    _rect(a, 0, 0, 47, 12, 1)
    a[0, :] = 3
    a[0:13, 0] = 3
    a[0:13, 47] = 3
    a[0, 0] = a[0, 47] = 0
    a[11:13, 1:47] = 2
    a[13, 1:47] = 3
    for cx in range(5, 48, 9):
        _disc(a, cx, 5.5, 2.2, 2)
    a[14:24, 18:30] = 1
    a[14:24, 18] = 3
    a[14:24, 29] = 3
    a[14, 18:30] = 3
    a[16:24, 22] = 2
    return _rows(a)


def hill():
    """terraced mound: stepped slopes (30 / 33), flat summit (31 32), a stone (34); 26 = fill"""
    a = _c(32, 16)
    for y in range(16):
        l = max(0, 15 - y - (y % 2))                 # left slope, 2 px steps
        r = min(31, 16 + y + (y % 2))
        if y >= 2:
            a[y, max(l, 0):r + 1] = 2
            a[y, max(l, 0)] = 3
            a[y, r] = 3
            if l + 1 <= r:
                a[y, l + 1] = 1
    a[2, 14:18] = 2
    a[2, 13] = a[2, 18] = 3
    a[2, 14:18] = 1
    a[0:2, :] = 0
    _rect(a, 10, 11, 13, 13, 3)                       # stone (tile 34 = x 8-15, y 8-15)
    _rect(a, 10, 11, 12, 12, 1)
    a[8:16, 16:24] = 2                                # 26 uniform
    return _rows(a)


def cloud_bush():
    """lens cloud / round bush: bumps 36 37 (repeat), caps 35 38, base 39 3a 3b 3c; 25 = fill (colour 1)"""
    s = _c(32, 24)
    s[8:16, 8:24] = 1
    for cx in (12, 20):
        _disc(s, cx, 9.5, 5.0, 1)
    _disc(s, 8.5, 15, 7.0, 1, sy=0.85)
    _disc(s, 23.5, 15, 7.0, 1, sy=0.85)
    s[16:19, 3:29] = 1
    s[19:21, 7:25] = 1
    a = s.copy()
    _outline(a, 3)
    a[8:16, 8:24] = np.where(a[8:16, 8:24] == 3, np.where(np.arange(8)[:, None] < 4, 3, 1), a[8:16, 8:24])
    a[8:16, 8:24][s[8:16, 8:24] > 0] = np.maximum(a[8:16, 8:24][s[8:16, 8:24] > 0], 1)
    a[12:16, 8:24] = 1
    for x in range(5, 28, 6):
        a[18, x:x + 2] = 2
    return _rows(a)


def pipe_up():
    """tube with a bolted collar (rows 0-15) and a ribbed shaft (rows 16-23); x 16-23 of the shaft = 26 fill"""
    a = _c(32, 24)
    _rect(a, 0, 0, 31, 15, 2)
    a[0, :] = 3
    a[15, :] = 3
    a[:16, 0] = 3
    a[:16, 31] = 3
    a[3, 1:31] = 3
    a[12, 1:31] = 3
    a[1:3, 1:31] = 1
    a[13:15, 1:31] = 1
    for x in range(4, 30, 6):
        a[7:9, x:x + 2] = 3
        a[7, x] = 1
    a[4:12, 26:29] = 1
    _rect(a, 2, 16, 29, 23, 2)
    a[16:24, 2] = 3
    a[16:24, 29] = 3
    a[16:24, 3:5] = 1
    a[16:24, 25:27] = 1
    a[20, 3:16] = 3
    a[20, 24:29] = 3
    a[16:24, 16:24] = 2
    return _rows(a)


def pipe_side():
    """sideways tube: collar on the left (cols 0-15), shaft to the right; rows 16-23 x 16-23 = 26"""
    a = _c(32, 32)
    _rect(a, 0, 0, 15, 31, 2)
    a[:, 0] = 3
    a[:, 15] = 3
    a[0, 0:16] = 3
    a[31, 0:16] = 3
    a[1:31, 3] = 3
    a[1:31, 12] = 3
    a[1:31, 1:3] = 1
    a[1:31, 13:15] = 1
    for y in range(4, 30, 6):
        a[y:y + 2, 7:9] = 3
        a[y, 7] = 1
    _rect(a, 16, 2, 31, 29, 2)
    a[2, 16:32] = 3
    a[29, 16:32] = 3
    a[3:5, 16:32] = 1
    a[25:27, 16:32] = 1
    a[5:16, 20] = 3
    a[24:29, 20] = 3
    a[16:24, 16:24] = 2
    return _rows(a)


def _egg(q):
    """atlas lists [Q, vQ ; vQ, Q]; the game shows the right column flipped both ways: a round seed"""
    v = q[::-1]
    return [x + y for x, y in zip(q, v)] + [x + y for x, y in zip(v, q)]


def spiny_egg_1():
    return _egg(["...2..2.", "..2111.1", ".2111111", "21111111", ".1113111", "21113311", ".1111111", ".2111111"])


def spiny_egg_2():
    return _egg(["........", "..21212.", ".2111111", ".1111111", "21113111", ".1113311", "21111111", ".1111111"])


CODE = {f.__name__: f for f in (brick, ground, stair_block, castle_block, qblock, used_block, coin_bg, coin_water, axe,
                                hud_coin, cursor_mushroom, bridge, guardrail_chain, fence, water_rock, water_top,
                                cloud_block, bowser_bridge, cannon, castle_parts, pulley, flagpole, seaplant, tree,
                                tree_ledge, mushroom_ledge, hill, cloud_bush, pipe_up, pipe_side)}
def logo_9a():
    return ["........", "...22...", "..2112..", ".211112.", "..2112..", "...22...", "........", "........"]


def logo_af():
    return ["........", ".3....3.", "..3..3..", "...33...", "...33...", "..3..3..", ".3....3.", "........"]


_SPR = {0: 0, 1: 2, 2: 3, 3: 1}           # bg roles (sand, brown, black) -> sprite palette 3 (black, cream, brown)


def _to_spr(rows):
    return ["".join(".123"[_SPR[".123".index(c)]] if c in ".123" else "." for c in r) for r in rows]


def brick_obj():
    """bumped brick sprite = top half of our brick"""
    return _to_spr(brick()[:8])


def brick_chunk():
    """084 = one flying cobble; 085 = top-left of the spent block (shared with block_obj)"""
    cob = ["........", "..1111..", ".122231.", ".122231.", ".133331.", "..1111..", "........", "........"]
    return cob + _to_spr([r[:8] for r in used_block()[:8]])


def block_obj():
    return ["." * 16] * 8 + _to_spr([r[:8] + "........" for r in used_block()[8:]])


CODE["brick_obj"] = brick_obj
CODE["brick_chunk"] = brick_chunk
CODE["block_obj"] = block_obj
CODE["logo_9a"] = logo_9a
CODE["logo_af"] = logo_af
CODE["enemy_spiny_s_egg_frame_1"] = spiny_egg_1
CODE["enemy_spiny_s_egg_frame_2"] = spiny_egg_2
