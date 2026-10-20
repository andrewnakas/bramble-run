"""SMB area / enemy data: parse, decode, render a solid grid, write .asm.

Format (from the disassembly's parser code, see docs/PLATFORM_NES.md):
  area   = header(2) + objects(2 bytes each) + $FD
  header = TT EEE FFF  (timer, entrance control, fg scenery / bg colour)
           SS BB TTTT  (area style 0 tree 1 mushroom 2 cannon 3 cloud, bg scenery, terrain control)
  object = XXXX YYYY, P nnn LLLL   P = next page; rows 0-11 normal, 12/15 special, 13 page/special, 14 attrs
  enemy  = XXXX YYYY, P H tttttt   row 15 = page select, row 14 = area pointer (3 bytes); end $FF

    python -m games.smb.levels show <asm dir> [label]      one line per area (or the grid of one)
"""
import os
import re
import sys

import numpy as np

AREA_KINDS = ("Water", "Ground", "Underground", "Castle")
COUNTS = {"Water": 3, "Ground": 22, "Underground": 3, "Castle": 6}

# terrain control -> rows (0 = top metatile row, 12 = bottom) filled with terrain (TerrainRenderBits)
TERRAIN = [(0x00, 0x00), (0x00, 0x18), (0x01, 0x18), (0x07, 0x18), (0x0F, 0x18), (0xFF, 0x18), (0x01, 0x1F),
           (0x07, 0x1F), (0x0F, 0x1F), (0x81, 0x1F), (0x01, 0x00), (0x8F, 0x1F), (0xF1, 0x1F), (0xF9, 0x18),
           (0xF1, 0x18), (0xFF, 0x1F)]

# grid cell classes
EMPTY, SOLID, BRICK, QBLOCK, COIN, PIPE, PLATFORM, WATER, HAZARD, DECOR = range(10)
TERR = 11


def terrain_rows(tc):
    a, b = TERRAIN[tc & 15]
    return [r for r in range(13) if ((a | (b << 8)) >> r) & 1]


def parse_asm(path):
    """{label: bytes} for every `Label:` followed by .db lines"""
    out, cur = {}, None
    for line in open(path, encoding="latin-1"):
        s = line.split(";")[0].strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):$", s)
        if m:
            cur = m.group(1)
            out[cur] = bytearray()
        elif s.startswith(".db") and cur:
            out[cur] += bytes(int(v.strip()[1:], 16) for v in s[3:].split(",") if v.strip())
    return {k: bytes(v) for k, v in out.items()}


def load_dir(d):
    """area + enemy data of a disassembly tree (src/levels/*.asm)"""
    a = parse_asm(os.path.join(d, "src", "levels", "objects.asm"))
    e = parse_asm(os.path.join(d, "src", "levels", "enemies.asm"))
    return a, e


def area_labels():
    out = []
    for k in ("Water", "Ground", "Underground", "Castle"):
        out += [f"{k}Area{i + 1}" for i in range(COUNTS[k])]
    return out


def decode_objects(data):
    """-> header dict, [(page, col, row, byte1)]"""
    h0, h1 = data[0], data[1]
    hdr = {"timer": h0 >> 6, "entrance": (h0 >> 3) & 7, "fg": h0 & 7, "style": h1 >> 6, "bg": (h1 >> 4) & 3,
           "terrain": h1 & 15}
    objs, page, i = [], 0, 2
    while i < len(data) and data[i] != 0xFD:
        b0, b1 = data[i], data[i + 1]
        if b1 & 0x80:
            page += 1
        row = b0 & 15
        if row == 13 and not (b1 & 0x40):
            page = b1 & 0x1F
            objs.append((page, b0 >> 4, row, b1))
        else:
            objs.append((page, b0 >> 4, row, b1))
        i += 2
    return hdr, objs


def decode_enemies(data):
    """-> [(page, col, row, id, hard)], [(page, col, area_ptr, world, entry_page)]"""
    ens, links, page, i = [], [], 0, 0
    while i < len(data) and data[i] != 0xFF:
        b0, b1 = data[i], data[i + 1]
        row = b0 & 15
        if b1 & 0x80:
            page += 1
        if row == 15:
            page = b1 & 0x3F
            i += 2
            continue
        if row == 14:
            b2 = data[i + 2]
            links.append((page, b0 >> 4, b1, b2 >> 5, b2 & 31))
            i += 3
            continue
        ens.append((page, b0 >> 4, row, b1 & 0x3F, bool(b1 & 0x40)))
        i += 2
    return ens, links


def render(data, kind):
    """approximate solid grid (13 rows x 16*pages columns) of one area"""
    hdr, objs = decode_objects(data)
    pages = max([o[0] for o in objs] + [0]) + 2
    W = pages * 16
    g = np.zeros((13, W), np.uint8)
    tc = np.full(W, hdr["terrain"], np.int16)
    for p, c, r, b1 in objs:
        if r == 14 and not (b1 & 0x40):
            tc[p * 16 + c:] = b1 & 15
    for x in range(W):
        for r in terrain_rows(tc[x]):
            g[r, x] = TERR
    for p, c, r, b1 in objs:
        x = p * 16 + c
        n, L = (b1 >> 4) & 7, b1 & 15
        if r < 12:
            if n == 0:
                cls = {0: QBLOCK, 1: QBLOCK, 2: DECOR, 3: DECOR, 9: PIPE, 10: SOLID, 11: PLATFORM}.get(L, BRICK)
                if L not in (2, 3):
                    g[r, x] = cls
            elif n == 1:            # ledge / cannon
                if hdr["style"] == 2:
                    g[r:r + L + 1, x] = SOLID
                else:
                    g[r, x:x + L + 1] = PLATFORM
            elif n in (2, 3, 4):
                g[r, x:x + L + 1] = {2: BRICK, 3: SOLID, 4: COIN}[n]
            elif n in (5, 6):
                g[r:r + L + 1, x] = BRICK if n == 5 else SOLID
            elif n == 7:
                g[r:min(13, r + (L & 7) + 1), x:x + 2] = PIPE
        elif r == 12:
            if n == 0 or n == 5:
                g[8:, x:x + L + 1] = WATER if n == 5 else EMPTY
            elif n in (2, 3, 4):
                g[{2: 7, 3: 8, 4: 10}[n], x:x + L + 1] = PLATFORM
            elif n in (6, 7):
                g[3 if n == 6 else 7, x:x + L + 1] = QBLOCK
        elif r == 15:
            if n == 3:              # staircase rising to the right
                for k in range(L + 1):
                    hgt = min(k + 1, 8)
                    g[11 - hgt:11, x + k] = SOLID
            elif n == 4:
                g[max(0, L - 1):L + 1, x:x + 4] = PIPE
            elif n == 2:
                g[L:11, x:x + 5] = DECOR
        elif r == 13 and b1 & 0x40:
            o = b1 & 0x3F
            if o == 0:
                g[7:11, x:x + 4] = PIPE
            elif o == 1:
                g[1:10, x] = DECOR
                g[10, x] = SOLID
            elif o == 4:
                g[8, x:x + 13] = PLATFORM
    return g[:, :W]


def show(d, label=None):
    a, e = load_dir(d)
    for lab in area_labels():
        if label and lab != label:
            continue
        hdr, objs = decode_objects(a["L_" + lab])
        ens, links = decode_enemies(e["E_" + lab])
        pages = max([o[0] for o in objs] + [0]) + 1
        print(f"{lab:20s} {len(a['L_' + lab]):4d}B {len(e['E_' + lab]):4d}B pages {pages:2d} hdr {hdr} "
              f"links {[(p, c, hex(ap), w, ep) for p, c, ap, w, ep in links]}")
        if label:
            kind = re.match(r"[A-Z][a-z]+", lab).group(0)
            g = render(a["L_" + lab], kind)
            for r in range(13):
                print("".join(" #B?oP=~^d"[v] for v in g[r]))


if __name__ == "__main__":
    if sys.argv[1] == "show":
        show(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)


ENEMY = 10


def area_bytes(prg, addr, end_byte):
    i = addr - 0x8000
    j = prg.index(bytes([end_byte]), i + (2 if end_byte == 0xFD else 0))
    return prg[i:j + 1]


def export(rom, labels, outdir, anchors=None):
    """every area's solid grid + enemy cells from a ROM -> <outdir>/levels/<Area>.json (for the tilemap gate)"""
    import json
    prg = rom[16:16 + 0x8000]
    os.makedirs(os.path.join(outdir, "levels"), exist_ok=True)
    n = 0
    for lab in area_labels():
        if "L_" + lab not in labels:
            continue
        a = area_bytes(prg, labels["L_" + lab], 0xFD)
        # objects are 2 bytes: find the real terminator on an object boundary
        k = 2
        while a[k] != 0xFD if k < len(a) else False:
            k += 2
        data = prg[labels["L_" + lab] - 0x8000:labels["L_" + lab] - 0x8000 + k + 1]
        while data[-1] != 0xFD:
            k += 2
            data = prg[labels["L_" + lab] - 0x8000:labels["L_" + lab] - 0x8000 + k + 1]
        g = render(data, lab.split("Area")[0])
        e0 = labels["E_" + lab] - 0x8000
        edata = bytearray()
        i = e0
        while prg[i] != 0xFF:
            ln = 3 if (prg[i] & 15) == 14 else 2
            edata += prg[i:i + ln]
            i += ln
        ens, _ = decode_enemies(bytes(edata) + b"\xff")
        for p, c, r, eid, hard in ens:
            x = p * 16 + c
            if x < g.shape[1] and r < 13:
                g[r, x] = ENEMY
        d = {"grid": g.tolist()}
        if anchors and lab in anchors:
            d["anchor_cols"] = sorted(int(x) for x in anchors[lab])
        json.dump(d, open(os.path.join(outdir, "levels", lab + ".json"), "w"))
        n += 1
    return n
