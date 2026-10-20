"""CLEAN ROOM: seeded level generator -> src/levels/objects.asm + enemies.asm.

Inputs are structure facts only (spec/areas.json: kind, timer, entrance, cloud flag, length in pages, portals =
warp destinations the code follows) plus the engine's rules (object format, 3 object slots per column, 5 enemy
slots, jump reach). Every placement, shape and enemy choice is drawn here from a seed.

    python -m games.smb.levelgen [seed]            summary + bytes per area (writes nothing)
    patch(dst)                                     called by generate.py
"""
import json
import os
import sys

import numpy as np

from cleanroom.decomp.gen import h32

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = "bramble-run-1"
# retail object + enemy data sizes (the PRG is full: new data must fit the same space)
BUDGET = 3372 + 1087

# enemy ids (engine constants)
GKOOPA, BUZZY, RKOOPA, HAMMER, GOOMBA, BLOOBER = 0x00, 0x02, 0x03, 0x05, 0x06, 0x07
GCHEEP, RCHEEP, PODOBOO, PIRANHA, GPARA_J, RPARA, LAKITU, SPINY = 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x11, 0x12
FIREBARS = (0x1B, 0x1C, 0x1D, 0x1E)
BOWSER, RETAINER, FRENZY_FLAME = 0x2D, 0x35, 0x15

# which areas the main path plays in which world (from the kept pointer tables)
WORLD_AREAS = [[0x25, 0x29, 0x40, 0x26, 0x60], [0x28, 0x29, 0x01, 0x27, 0x62], [0x24, 0x35, 0x20, 0x63],
               [0x22, 0x29, 0x41, 0x2C, 0x61], [0x2A, 0x31, 0x26, 0x62], [0x2E, 0x23, 0x2D, 0x60],
               [0x33, 0x29, 0x01, 0x27, 0x64], [0x30, 0x32, 0x21, 0x65]]
KINDS = ("Water", "Ground", "Underground", "Castle")
DROP_DEST = {"GroundArea16"}          # warp-zone room: no warp zones in this game
DROP_SRC = {"CastleArea6", "WaterArea3"}   # final keep is one straight run


def ptr_label(p):
    return f"{KINDS[(p >> 5) & 3]}Area{(p & 31) + 1}"


def first_world(lab):
    ws = [w for w, al in enumerate(WORLD_AREAS) for p in al if ptr_label(p) == lab]
    return min(ws) if ws else 3


class Area:
    def __init__(self, lab, fact, rng):
        self.lab, self.f, self.rng = lab, fact, rng
        self.kind = fact["kind"]
        self.W = fact["pages"] * 16
        self.objs = []        # (x, order, row, b1, width)
        self.ens = []         # (x, order, row, id, hard)
        self.links = []       # (x, ptr, world, page)
        self.order = 0
        self.hdr = (0, 0)
        self.busy = np.zeros(self.W + 64, np.int16)     # object slots in use per column
        self.free = np.ones(self.W + 64, bool)           # column free for new features
        self.anchors = set()                             # columns the code hard-wires (warps, boss bridge)

    def anchor(self, x0, x1):
        self.anchors |= set(range(max(0, x0), x1))

    # ---- objects -------------------------------------------------------------------------------------------
    def obj(self, x, row, b1, width=1):
        assert 0 <= row <= 15 and 0 <= b1 < 0x80, (x, row, b1)
        self.order += 1
        self.objs.append((x, self.order, row, b1, width))
        self.busy[x:x + width] += 1

    def row_of(self, x, row, n, length):        # n: 2 bricks 3 solid 4 coins, length >= 1
        while length > 0:
            k = min(length, 16)
            self.obj(x, row, (n << 4) | (k - 1), k)
            x, length = x + k, length - k

    def column(self, x, row, n, height):        # n: 5 bricks 6 solid
        self.obj(x, row, (n << 4) | (height - 1))

    def small(self, x, row, kind):              # 0 ?pow 1 ?coin 2 hidden coin 3 hidden 1up 4 brick pow 5 vine
        self.obj(x, row, kind)                  # 6 star 7 coins 8 1up 9 water pipe 10 used block 11 spring

    def pipe(self, x, height, enter=False):     # standing on floor row 11
        top = 11 - height
        self.obj(x, top, 0x70 | (8 if enter else 0) | (height - 1), 2)

    def hole(self, x, length, water=False):
        self.obj(x, 12, ((5 if water else 0) << 4) | (length - 1), length)

    def terrain(self, x, tc, bg=None):
        self.obj(x, 14, ((self.bg if bg is None else bg) << 4) | tc)

    def special13(self, x, k):                 # 0 intro pipe 1 flagpole 2 axe 3 chain 4 bridge 6/7 scroll lock
        self.obj(x, 13, 0x40 | k, {0: 4, 4: 13}.get(k, 1))  # 8 cheep frenzy 9 bill frenzy 10 stop frenzy

    def special15(self, x, n, low, width):     # 2 castle 3 staircase 4 exit pipe
        self.obj(x, 15, (n << 4) | low, width)

    # ---- enemies -------------------------------------------------------------------------------------------
    def enemy(self, x, row, eid, hard=False):
        self.order += 1
        self.ens.append((x, self.order, row, eid, hard))

    def link(self, x, ptr, world, page):
        self.order += 1
        self.links.append((x, self.order, ptr, world, page))

    # ---- encode --------------------------------------------------------------------------------------------
    def encode_objects(self):
        out = bytearray(self.hdr)
        cur = 0
        for x, _, row, b1, _w in sorted(self.objs):
            p = x // 16
            flag = 0
            if p == cur + 1:
                flag, cur = 0x80, p
            elif p != cur:
                assert p > cur
                out += bytes([0x0D, p & 0x1F])
                cur = p
            out += bytes([((x % 16) << 4) | row, b1 | flag])
        out.append(0xFD)
        return bytes(out)

    def encode_enemies(self):
        items = [(x, o, "e", r, i, h) for x, o, r, i, h in self.ens] + \
                [(x, o, "l", p, w, pg) for x, o, p, w, pg in self.links]
        out = bytearray()
        cur = 0
        for it in sorted(items):
            x = it[0]
            p = x // 16
            flag = 0
            if p == cur + 1:
                flag, cur = 0x80, p
            elif p != cur:
                assert p > cur
                out += bytes([0x0F, p & 0x3F])
                cur = p
            if it[2] == "e":
                _, _, _, r, i, h = it
                out += bytes([((x % 16) << 4) | r, i | (0x40 if h else 0) | flag])
            else:
                _, _, _, ptr, w, pg = it
                out += bytes([((x % 16) << 4) | 0x0E, ptr | flag, (w << 5) | pg])
        out.append(0xFF)
        return bytes(out)

    def check(self):
        assert self.busy.max() <= 3, f"{self.lab}: {self.busy.max()} objects in one column at {int(self.busy.argmax())}"
        cnt = np.zeros(self.W // 16 + 4, int)
        for x, *_ in self.ens:
            cnt[x // 16] += 1


# =============================================================================================================
# area designs
# =============================================================================================================

def reserve(a, x0, x1):
    a.free[max(0, x0):x1] = False


def portals_of(lab, facts):
    """outgoing portals kept for this area"""
    if lab in DROP_SRC:
        return []
    out = []
    for po in facts[lab]["portals"]:
        ent = [e for e in po["entries"] if e["dest"] not in DROP_DEST]
        if ent:
            out.append(dict(po, entries=ent))
    return out


def arrivals_of(lab, facts):
    """{page: mode} of entries into this area: 'pipe' (rise out of a pipe), 'fall' (cloud exit), 'top' (header)"""
    out = {}
    for src, s in facts.items():
        for po in portals_of(src, facts):
            for e in po["entries"]:
                if e["dest"] != lab:
                    continue
                mode = {"side_pipe": "pipe", "cloud_exit": "fall"}.get(po["use"], "top")
                out.setdefault(e["page"], mode)
    return out


def enemy_pool(world, kind):
    if kind == "Water":
        return [BLOOBER, GCHEEP, RCHEEP] if world > 1 else [BLOOBER, GCHEEP]
    pool = [GOOMBA, GOOMBA, GKOOPA]
    if world >= 1:
        pool += [RKOOPA, GPARA_J]
    if world >= 2:
        pool += [BUZZY, RPARA]
    if world >= 4:
        pool += [GOOMBA, GKOOPA, BUZZY]
    return pool


def ground_area(a, facts, world):
    rng, lab = a.rng, a.lab
    kind = a.kind
    under = kind == "Underground"
    style = 2 if (not under and rng.random() < (0.35 if world >= 4 else 0.0)) else int(rng.integers(0, 2))
    if under:
        style = 0
    a.bg = 0 if under else int(rng.integers(1, 4))
    a.style = style
    fg = 0 if under else int(rng.choice([0, 0, 0, 4]))
    a.hdr = ((a.f["timer"] << 6) | (a.f["entrance"] << 3) | fg, (style << 6) | (a.bg << 4) | (15 if under else 1))
    if under:                                   # open sky where the player drops in, then a roof
        a.terrain(0, 1, 0)
        a.terrain(int(rng.integers(5, 8)), 2, 0)
    W = a.W
    arr = arrivals_of(lab, facts)
    pors = portals_of(lab, facts)
    # ---- the finish
    if lab == "GroundArea10":                   # pipe intro: small keep, then the pipe the player walks into
        a.anchor(0, 32)
        a.special15(int(rng.integers(0, 2)), 2, 6, 5)
        a.special13(int(rng.integers(9, 11)), 0)
        a.special13(19, 7)
        return
    if under:
        end = W - 24
        side = [po for po in pors if po["use"] == "side_pipe" and facts[po["entries"][0]["dest"]]["kind"] == "Ground"
                and po["entries"][0]["dest"] == "GroundArea6"]
        reserve(a, end - 4, W + 64)
        a.terrain(end - 2, 1, 0)                 # no roof over the exit
        for po in side:
            for e in po["entries"]:
                a.link(end - 3, e["ptr"], e["world"], e["page"])
        a.anchor(end - 2, end + 7)
        a.special15(end, 4, 10, 4)               # walk-in exit pipe
        a.terrain(end + 4, 15, 0)
        a.special13(end + 12, 7)            # lock lands once the pipe is on screen (renderer runs ahead)
        pors = [po for po in pors if po not in side]
    else:
        end = W - 16 - int(rng.integers(2, 6))  # flagpole column
        reserve(a, end - 6, W + 64)
        if rng.random() < 0.6:                   # run-up steps, our own shape
            h = int(rng.integers(3, 7))
            a.special15(end - h - 2, 3, h - 1, h)
            reserve(a, end - h - 3, end)
        a.special13(end, 1)
        big = rng.random() < 0.4
        a.special15(end + (5 if big else 4), 2, 0 if big else 6, 5)
    # ---- arrivals (anchors: a pipe at column 3 of the entry page, or flat ground to land on)
    for page, mode in sorted(arr.items()):
        x = page * 16
        if mode == "pipe":
            a.anchor(x + 3, x + 5)
            a.pipe(x + 3, 2)
            reserve(a, x, x + 8)
        elif mode == "fall":
            reserve(a, x, x + 7)
        else:
            reserve(a, x, x + 6)
    reserve(a, 0, 12 if not under else 10)
    # ---- portals (warp pipes / vines) at our own spots, roughly in the retail order
    for po in pors:
        want = po["page"] * 16 + int(rng.integers(2, 12))
        x = find_free(a, want, 7)
        if x is None:
            continue
        for e in po["entries"]:
            a.link(x, e["ptr"], e["world"], e["page"])
        if po["use"] == "vine":
            a.row_of(x + 2, 7, 2, 1)
            a.small(x + 3, 7, 5)
            a.row_of(x + 4, 7, 2, 1)
        elif po["use"] == "down_pipe":
            a.pipe(x + 3, int(rng.integers(2, 4)), enter=True)
        reserve(a, x, x + 7)
    # ---- fill the rest with chunks
    fill(a, world, under)


def find_free(a, want, width):
    for d in range(0, a.W):
        for x in (want + d, want - d):
            if 0 <= x and x + width <= a.W - 8 and a.free[x:x + width].all():
                return x
    return None


def fill(a, world, under=False, castle=False):
    rng = a.rng
    x = 0
    pool = enemy_pool(world, a.kind)
    while x < a.W:
        if not a.free[x]:
            x += 1
            continue
        run = 0
        while x + run < a.W and a.free[x + run]:
            run += 1
        if run < 4:
            if run >= 2 and rng.random() < 0.5:
                a.row_of(x, int(rng.choice([7, 8])), 4, run)
            x += run
            continue
        chunk = CASTLE_CHUNKS if castle else GROUND_CHUNKS
        names = [n for n, (wmin, _f, wt) in chunk.items() if wmin <= run]
        weights = np.array([chunk[n][2] for n in names], float)
        if under:
            weights = np.array([w * (1.6 if n in ("ceiling", "bricks", "columns") else 1.0) for n, w in zip(names, weights)])
        name = names[int(rng.choice(len(names), p=weights / weights.sum()))]
        used = chunk[name][1](a, x, run, world, pool)
        a.free[x:x + used] = False
        x += used


# ---- chunk library: each returns the number of columns used (<= room) ---------------------------------------

def ch_flat(a, x, room, world, pool):
    w = min(room, int(a.rng.integers(3, 6)))
    if a.rng.random() < 0.5:
        a.enemy(x + w - 1, 11, int(a.rng.choice(pool)))
    return w


def ch_bricks(a, x, room, world, pool):
    rng = a.rng
    w = min(room, int(rng.integers(5, 10)))
    n = int(rng.integers(2, min(6, w - 1) + 1))
    s = x + int(rng.integers(1, w - n + 1))
    row = int(rng.choice([7, 7, 8]))
    k = s
    while k < s + n:                            # runs of bricks with blocks in between
        if rng.random() < 0.35:
            a.small(k, row, int(rng.choice([0, 1, 1, 1, 7, 4, 6] if rng.random() < 0.3 else [1])))
            k += 1
        else:
            m = min(s + n - k, int(rng.integers(1, 4)))
            a.row_of(k, row, 2, m)
            k += m
    if rng.random() < 0.4 and n >= 3:
        hi = row - 4
        m = int(rng.integers(2, n + 1))
        a.row_of(s + int(rng.integers(0, n - m + 1)), hi, 2 if rng.random() < 0.6 else 4, m)
    if rng.random() < 0.7:
        a.enemy(s + n - 1, 11, int(rng.choice(pool)))
    return w


def ch_hole(a, x, room, world, pool):
    rng = a.rng
    L = int(rng.integers(2, 4 if world < 2 else 5))
    L = min(L, 3)
    w = L + 4
    if w > room:
        return ch_flat(a, x, room, world, pool)
    a.hole(x + 2, L)
    if rng.random() < 0.5:
        a.row_of(x + 2, int(rng.choice([6, 7])), 4, L)
    return w


def ch_pipes(a, x, room, world, pool):
    rng = a.rng
    count = int(rng.integers(1, 4))
    k = x + 1
    for i in range(count):
        if k + 3 > x + room:
            break
        a.pipe(k, int(rng.integers(2, 5)))
        gap = int(rng.integers(3, 6))
        if rng.random() < 0.6 and k + 2 + gap <= x + room:
            a.enemy(k + 2 + gap // 2, 11, GOOMBA if rng.random() < 0.6 else int(rng.choice(pool)))
        k += 2 + gap
    return max(4, min(room, k - x))


def ch_stairs(a, x, room, world, pool):
    rng = a.rng
    h = int(rng.integers(2, 5))
    down = rng.random() < 0.6
    gap = int(rng.integers(0, 3)) if down else 0
    w = h + (gap + h if down else 0) + 2
    if w > room:
        return ch_flat(a, x, room, world, pool)
    a.special15(x + 1, 3, h - 1, h)
    if down:
        if gap:
            a.hole(x + 1 + h, gap)
        for i in range(h):                      # mirrored steps down, our own columns
            hh = h - i
            a.column(x + 1 + h + gap + i, 11 - hh, 6, hh)
    return w


def ch_ledges(a, x, room, world, pool):
    rng = a.rng
    if a.style not in (0, 1) or room < 9:
        return ch_bricks(a, x, room, world, pool) if room >= 5 else ch_flat(a, x, room, world, pool)
    w = min(room, int(rng.integers(9, 15)))
    a.hole(x + 1, w - 2) if w - 2 <= 16 else None
    k, top = x + 1, 10
    while k < x + w - 2:
        ln = int(rng.integers(3, 6))
        ln = min(ln, x + w - 1 - k)
        if ln < 2:
            break
        top = int(np.clip(top + rng.integers(-2, 3), 6, 9))
        a.obj(k, top, 0x10 | (ln - 1), ln)
        if rng.random() < 0.4:
            a.row_of(k, top - 3, 4, ln)
        if rng.random() < 0.3 and ln >= 3:
            a.enemy(k + ln - 1, top - 1, int(rng.choice([GKOOPA, RKOOPA, GOOMBA])))
        k += ln + int(rng.integers(1, 3))
    return w


def ch_cannons(a, x, room, world, pool):
    rng = a.rng
    if a.style != 2:
        return ch_pipes(a, x, room, world, pool)
    k, count = x + 1, int(rng.integers(1, 3))
    for i in range(count):
        if k + 2 > x + room:
            break
        h = int(rng.integers(1, 4))
        a.obj(k, 11 - h, 0x10 | (h - 1))
        k += int(rng.integers(3, 6))
    return max(3, min(room, k - x))


def ch_coins(a, x, room, world, pool):
    rng = a.rng
    w = min(room, int(rng.integers(4, 8)))
    m = int(rng.integers(2, w))
    a.row_of(x + 1, 8, 3, m)
    a.row_of(x + 1, 6, 4, m)
    if rng.random() < 0.5:
        a.enemy(x + w - 1, 11, int(rng.choice(pool)))
    return w


def ch_columns(a, x, room, world, pool):
    rng = a.rng
    w = min(room, int(rng.integers(5, 9)))
    h = int(rng.integers(2, 4))
    a.column(x + 1, 11 - h, 6 if rng.random() < 0.7 else 5, h)
    if w >= 6:
        h2 = int(rng.integers(1, 4))
        a.column(x + w - 2, 11 - h2, 6, h2)
        if rng.random() < 0.6:
            a.enemy(x + w // 2, 11, int(rng.choice(pool)))
    return w


def ch_ceiling(a, x, room, world, pool):
    """underground: brick ceiling dips / brick walls with a passage"""
    rng = a.rng
    w = min(room, int(rng.integers(4, 8)))
    if a.kind != "Underground":
        return ch_bricks(a, x, room, world, pool)
    a.row_of(x, 1, 2, w)
    a.row_of(x + 1, int(rng.choice([4, 5])), 2, w - 2)
    if rng.random() < 0.5:
        a.small(x + w // 2, 8, 1)
    if rng.random() < 0.6:
        a.enemy(x + w - 1, 11, int(rng.choice(pool)))
    return w


GROUND_CHUNKS = {          # name: (min room, fn, weight)
    "flat": (3, ch_flat, 1.0), "bricks": (5, ch_bricks, 3.0), "hole": (4, ch_hole, 2.0), "pipes": (4, ch_pipes, 1.6),
    "stairs": (4, ch_stairs, 1.2), "ledges": (9, ch_ledges, 1.4), "cannons": (3, ch_cannons, 1.0),
    "coins": (4, ch_coins, 0.8), "columns": (5, ch_columns, 1.2), "ceiling": (4, ch_ceiling, 0.6),
}


# ---- castles ------------------------------------------------------------------------------------------------

def castle_area(a, facts, world):
    rng = a.rng
    a.bg = 0
    a.style = 0
    a.hdr = ((a.f["timer"] << 6) | (a.f["entrance"] << 3) | 3, 7)
    # our start perch
    a.row_of(0, 7, 3, int(rng.integers(3, 6)))
    a.column(int(rng.integers(0, 2)), int(rng.integers(4, 6)), 6, 2)
    W = a.W
    P = W // 16 - 2                              # bridge page (anchor: bridge, chain, axe, keeper relative to it)
    bx = P * 16
    a.anchor(bx - 1, bx + 16 + 10)
    a.terrain(bx - 1, 10, 0)                     # no floor under the bridge
    a.special13(bx, 4)
    a.special13(bx + 12, 3)
    a.terrain(bx + 12, 9, 0)
    a.special13(bx + 13, 2)
    a.terrain(bx + 13, 11, 0)
    a.terrain(bx + 15, 2, 0)
    a.special13(bx + 16 + 5, 7)
    a.enemy(bx + 7, 8, BOWSER)
    a.enemy(bx + 16 + 9, 0, RETAINER)
    a.enemy(bx - 18, 8, FRENZY_FLAME)
    reserve(a, bx - 6, W + 64)
    reserve(a, 0, 8)
    fill(a, world, castle=True)


def cs_corridor(a, x, room, world, pool):
    rng = a.rng
    w = min(room, int(rng.integers(4, 9)))
    tc = int(rng.choice([7, 8, 8, 4]))
    a.terrain(x, tc, 0)
    if tc != 7:
        a.terrain(x + w - 1, 7, 0)
    if rng.random() < 0.5:
        a.row_of(x + 1, 4, 3, max(1, w - 3))
    return w


def cs_lava(a, x, room, world, pool):
    rng = a.rng
    L = int(rng.integers(2, 4))
    w = L + 4
    if w > room:
        return cs_corridor(a, x, room, world, pool)
    a.terrain(x + 1, 3, 0)
    a.hole(x + 2, L, water=True)
    a.terrain(x + 2 + L, 7, 0)
    if rng.random() < 0.6:
        a.enemy(x + 2 + L // 2, 12, PODOBOO)
    return w


def cs_firebar(a, x, room, world, pool):
    rng = a.rng
    if x - getattr(a, "last_bar", -99) < 12 or room < 6:     # bars need room to time a pass
        return cs_corridor(a, x, room, world, pool)
    w = min(room, int(rng.integers(6, 9)))
    row = int(rng.choice([3, 3, 7] if world >= 2 else [3]))
    if row == 3:
        a.column(x + w // 2, 3, 6, 1)           # hangs from the ceiling: walk under it
    else:
        a.small(x + w // 2, 7, 10)
    a.enemy(x + w // 2, row, int(rng.choice(FIREBARS[:3])))
    a.last_bar = x
    return w


def cs_blocks(a, x, room, world, pool):
    rng = a.rng
    w = min(room, int(rng.integers(5, 9)))
    h = int(rng.integers(1, 3))
    a.column(x + 1, 7 - h + 1, 6, h)
    a.row_of(x + 2, int(rng.choice([4, 5])), 3, max(1, w - 3))
    if rng.random() < 0.3:
        a.small(x + w - 1, 4, 0)
    return w


CASTLE_CHUNKS = {"corridor": (4, cs_corridor, 1.0), "lava": (4, cs_lava, 2.0), "firebar": (5, cs_firebar, 1.5),
                 "blocks": (5, cs_blocks, 1.2)}


# ---- water --------------------------------------------------------------------------------------------------

def water_area(a, facts, world):
    rng = a.rng
    a.bg = 0
    a.style = 0
    a.hdr = ((a.f["timer"] << 6) | (a.f["entrance"] << 3) | 1, 1)
    W = a.W
    pors = portals_of(a.lab, facts)
    end = W - 22
    for po in pors:
        for e in po["entries"]:
            a.link(end - 2, e["ptr"], e["world"], e["page"])
    a.anchor(end, end + 14)
    a.terrain(end, 11, 0)                        # corridor rows 4-6 to the exit pipe
    a.small(end + 3, 5, 9)
    a.terrain(end + 3, 15, 0)
    a.special13(end + 6, 10)
    a.special13(end + 13, 7)
    reserve(a, end - 3, W + 64)
    reserve(a, 0, 6)
    x = 6
    pool = enemy_pool(world, "Water")
    while x < end - 3:
        w = int(rng.integers(4, 9))
        w = min(w, end - 3 - x)
        if w < 2:
            break
        t = rng.random()
        if t < 0.35:
            h = int(rng.integers(2, 6))
            a.column(x + 1, 11 - h, 6, h)
        elif t < 0.6:
            a.row_of(x, int(rng.integers(3, 7)), 3, max(1, w - 2))
        elif t < 0.8:
            a.row_of(x + 1, int(rng.integers(3, 9)), 4, max(1, w - 3))
        if rng.random() < 0.55:
            a.enemy(x + w - 1, int(rng.integers(4, 11)), int(rng.choice(pool)), hard=bool(rng.random() < 0.3))
        x += w


# ---- cloud bonus areas --------------------------------------------------------------------------------------

def cloud_area(a, facts, world):
    rng = a.rng
    a.bg = 0
    a.style = 3
    a.hdr = ((a.f["timer"] << 6) | (a.f["entrance"] << 3) | int(rng.choice([0, 6])), (3 << 6) | 1)
    for po in portals_of(a.lab, facts):
        for e in po["entries"]:
            a.link(16, e["ptr"], e["world"], e["page"])
    W = a.W
    end = W - 20
    x = 6
    while x < end:
        m = int(rng.integers(3, 7))
        a.row_of(x, int(rng.choice([5, 6, 7])), 4, min(m, end - x))
        x += m + int(rng.integers(2, 5))
    a.hole(end, 15)
    a.special13(end + 14, 7)


def bonus_rooms(a, facts, world):
    """the shared underground bonus area: one room per entry page"""
    rng = a.rng
    a.bg = 0
    a.style = 0
    a.hdr = ((a.f["timer"] << 6) | (a.f["entrance"] << 3), 2)
    pages = sorted(arrivals_of(a.lab, facts))
    pors = portals_of(a.lab, facts)
    for p in pages:
        x = p * 16
        a.column(x, 1, 5, 10)                    # brick wall on the left of each room
        k = x + 2
        while k < x + 11:
            m = int(rng.integers(2, 5))
            m = min(m, x + 11 - k)
            row = int(rng.choice([4, 5, 6, 7, 8]))
            a.row_of(k, row, 4, m)
            if rng.random() < 0.6:
                a.row_of(k, row + 1, 3 if rng.random() < 0.5 else 2, m)
            k += m + 1
        a.anchor(x + 12, x + 16)
        a.special15(x + 12, 4, 10, 4)
        a.special13(x + 16 + 4, 7)
        for po in pors:
            if po["page"] // 2 == p // 2:
                for e in po["entries"]:
                    a.link(x + 16 + 1, e["ptr"], e["world"], e["page"])


def build(lab, facts, seed=SEED):
    rng = np.random.default_rng(h32(seed, lab))
    f = facts[lab]
    a = Area(lab, f, rng)
    world = first_world(lab)
    if lab == "UndergroundArea3":
        bonus_rooms(a, facts, world)
    elif f["cloud"]:
        cloud_area(a, facts, world)
    elif f["kind"] == "Castle":
        castle_area(a, facts, world)
    elif f["kind"] == "Water":
        water_area(a, facts, world)
    else:
        ground_area(a, facts, world)
    a.check()
    return a


def build_all(seed=SEED):
    facts = json.load(open(os.path.join(HERE, "spec", "areas.json")))
    from games.smb.levels import area_labels
    return {lab: build(lab, facts, seed) for lab in area_labels()}


def asm(areas):
    def rows(data):
        return "\n".join("\t.db " + ", ".join(f"${b:02x}" for b in data[i:i + 12]) for i in range(0, len(data), 12))
    obj = ["; AREA OBJECT DATA (generated by games/smb/levelgen.py)", ""]
    en = ["; ENEMY OBJECT DATA (generated by games/smb/levelgen.py)", ""]
    for lab, a in areas.items():
        obj += [f"L_{lab}:", rows(a.encode_objects()), ""]
        en += [f"E_{lab}:", rows(a.encode_enemies()), ""]
    return "\n".join(obj) + "\n", "\n".join(en) + "\n"


def patch_demo(dst):
    """attract demo inputs: runs recorded by our bot on our 1-1 (spec/demo.json), not the retail inputs"""
    import re
    runs = json.load(open(os.path.join(HERE, "spec", "demo.json")))
    p = os.path.join(dst, "src", "prg.asm")
    t = open(p, encoding="latin-1", newline="").read()
    acts = ", ".join(f"${b:02x}" for b, _ in runs) + ", $00"
    tims = ", ".join(f"${n:02x}" for _, n in runs) + ", $00"
    t, k = re.subn(r"DemoActionData:\n(?:\t\.db[^\n]*\n)+\nDemoTimingData:\n(?:\t\.db[^\n]*\n)+",
                   f"DemoActionData:\n\t.db {acts}\n\nDemoTimingData:\n\t.db {tims}\n", t)
    assert k == 1, "demo tables not found"
    open(p, "w", encoding="latin-1", newline="").write(t)
    return len(runs)


def patch(dst, seed=None):
    areas = build_all(seed or os.environ.get("SMB_LEVEL_SEED", SEED))
    o, e = asm(areas)
    total = sum(len(a.encode_objects()) + len(a.encode_enemies()) for a in areas.values())
    assert total <= BUDGET, f"level data {total} B > budget {BUDGET} B"
    open(os.path.join(dst, "src", "levels", "objects.asm"), "w", newline="\n").write(o)
    open(os.path.join(dst, "src", "levels", "enemies.asm"), "w", newline="\n").write(e)
    d = patch_demo(dst) if os.path.exists(os.path.join(HERE, "spec", "demo.json")) else 0
    return f"{len(areas)} areas generated, {total}/{BUDGET} bytes; demo {d} runs"


if __name__ == "__main__":
    areas = build_all(sys.argv[1] if len(sys.argv) > 1 else SEED)
    tot = 0
    for lab, a in areas.items():
        o, e = a.encode_objects(), a.encode_enemies()
        tot += len(o) + len(e)
        print(f"{lab:18s} obj {len(o):4d} en {len(e):3d} objs {len(a.objs):3d} enemies {len(a.ens):3d} links {len(a.links)}")
    print(f"total {tot} / {BUDGET}")
