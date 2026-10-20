"""Which CHR tiles form which picture (sprite frame, block, scenery piece).

Built from the disassembly's own tables (code, kept) plus hand-written
composites. A picture is a grid of tile numbers; page 0 = sprites ($0000),
page 1 = background ($1000, numbers here are 0x100 + tile). The first
picture that lists a tile owns it: the generator draws whole pictures and
cuts owned tiles out of them.
"""
import os
import re

ASM = os.environ.get("SMB_ASM", "D:/n64work/smb/ref/smb1/src/prg.asm")

# preview palettes (master ids): index 0 is transparent / backdrop
SPR = {0: (0x22, 0x16, 0x27, 0x18), 1: (0x22, 0x1A, 0x30, 0x27), 2: (0x22, 0x16, 0x30, 0x27), 3: (0x22, 0x0F, 0x36, 0x17)}
BG = {0: (0x22, 0x29, 0x1A, 0x0F), 1: (0x22, 0x36, 0x17, 0x0F), 2: (0x22, 0x30, 0x21, 0x0F), 3: (0x22, 0x27, 0x17, 0x0F)}


def table(label, asm=None):
    """bytes + per-line comments of a .db table that follows `label:`"""
    lines = open(asm or ASM, encoding="latin-1").read().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith(label + ":")) + 1
    rows = []
    while i < len(lines):
        l = lines[i].strip()
        i += 1
        if not l or l.startswith(";"):
            continue
        m = re.match(r"\.db\s+([^;]*)(?:;\s*(.*))?$", l)
        if not m:
            if rows:
                break
            continue
        vals = [int(v.strip()[1:], 16) for v in m.group(1).split(",") if v.strip().startswith("$")]
        rows.append((vals, (m.group(2) or "").strip()))
    return rows


def _name(base, comment, seen):
    c = re.sub(r"[^a-z0-9]+", "_", comment.lower()).strip("_")
    n = f"{base}_{c}" if c else base
    k, out = 1, n
    while out in seen:
        k += 1
        out = f"{n}_{k}"
    seen.add(out)
    return out


def _grid(vals, cols):
    rows = [[None if v == 0xFC else v for v in vals[i:i + cols]] for i in range(0, len(vals), cols)]
    while rows and all(v is None for v in rows[0]):
        rows.pop(0)
    while rows and all(v is None for v in rows[-1]):
        rows.pop()
    return rows


def _mirror(rows):
    """right tile == left tile -> the game draws it flipped"""
    return [[1 if (c == 1 and r[0] == r[1] and r[0] is not None) else 0 for c in range(len(r))] for r in rows]


def B(*rows):
    return [[None if v is None else 0x100 + v for v in r] for r in rows]


N = None

# hand-written composites: (name, palette, layout, [flips])
SPRITES_EXTRA = [
    ("coin_spin", 2, [[0x60, 0x61, 0x62, 0x63]]),
    ("fireball", 2, [[0x64, 0x65]]),
    ("explosion", 2, [[0x66, 0x67, 0x68]]),
    ("bubble", 2, [[0x74]]),
    ("hammer", 3, [[0x80, 0x81], [0x82, 0x83]]),
    ("brick_chunk", 3, [[0x84], [0x85]]),
    ("block_obj", 3, [[0x85, 0x85], [0x86, 0x86]]),
    ("brick_obj", 3, [[0x87, 0x87]]),
    ("platform", 2, [[0x5B, 0x5B, 0x5B]]),
    ("small_platform", 2, [[0x75]]),
    ("flag", 1, [[0x7E, 0x7F]]),
    ("vine", 1, [[0xE1], [0xE0]]),
    ("swim_kick", 0, [[0x31, 0x46]]),
    ("score_100_8000", 2, [[0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB]]),
    ("score_1up", 2, [[0xFD, 0xFE]]),
    ("misc_ff", 2, [[0xFF]]),
    ("bowser_flame", 1, [[0x51, 0x52, 0x53]]),
    ("score_00", 2, [[0x50]]),
    ("misc_54", 0, [[0x54, 0x55], [0x56, 0x57]]),
]

BACKGROUND = [
    ("fills", 0, B([0x24, 0x25, 0x26, 0x27])),
    ("cloud_bush", 2, B([N, 0x36, 0x37, N], [0x35, 0x25, 0x25, 0x38], [0x39, 0x3A, 0x3B, 0x3C])),
    ("hill", 0, B([N, 0x31, 0x32, N], [0x30, 0x34, 0x26, 0x33])),
    ("pipe_up", 0, B([0x60, 0x61, 0x62, 0x63], [0x64, 0x65, 0x66, 0x67], [0x68, 0x69, 0x26, 0x6A])),
    ("pipe_side", 0, B([0x86, 0x87, 0x88, 0x89], [0x8A, 0x8B, 0x8C, 0x8D], [0x8E, 0x8F, 0x26, 0x90], [0x91, 0x92, 0x93, 0x94])),
    ("tree", 0, B([0xB8, 0xB9], [0xBA, 0xBB], [0xBC, 0xBD], [0xBE, 0xBF])),
    ("tree_ledge", 0, B([0x4B, 0x4D, 0x4D, 0x50], [0x4C, 0x4F, 0x4E, 0x51], [N, 0x52, 0x52, N])),
    ("mushroom_ledge", 0, B([0x6B, 0x2C, 0x6C, 0x6D, 0x6E, 0x6F], [0x70, 0x2D, 0x71, 0x72, 0x73, 0x74], [N, N, 0x75, 0x76, N, N])),
    ("seaplant", 0, B([0xA4, 0xEA], [0xE9, 0xEB])),
    ("flagpole", 0, B([0x2F, 0x3D], [0xA2, 0xA3])),
    ("guardrail_chain", 0, B([0xC0, 0x7F])),
    ("pulley", 1, B([N, 0x3E, 0x5B, N], [0xA2, 0x3F, 0x5C, 0xA3], [0x99, 0x99, 0x99, 0x99])),
    ("castle_parts", 1, B([0x9D, 0x9E, 0xA9, 0xAA], [0x9B, 0x9C, 0x47, 0x47])),
    ("brick", 1, B([0x45, 0x45], [0x47, 0x47])),
    ("fence", 1, B([0x80, 0x81], [0xA0, 0xA1])),
    ("ground", 1, B([0xB4, 0xB5], [0xB6, 0xB7])),
    ("stair_block", 1, B([0xAB, 0xAD], [0xAC, 0xAE])),
    ("castle_block", 1, B([0x5D, 0x5D], [0x5E, 0x5E])),
    ("bridge", 1, B([0xC1, 0xC1])),
    ("cannon", 1, B([0xCA, 0xCB], [0xCC, 0xCD], [0xC6, 0xC7], [0xC8, 0xC9], [0x2A, 0x40])),
    ("water_rock", 1, B([0x82, 0x84], [0x83, 0x85])),
    ("water_top", 2, B([0x41, 0x41])),
    ("cloud_block", 2, B([0xB0, 0xB2], [0xB1, 0xB3])),
    ("bowser_bridge", 2, B([0x77, 0x77], [0x79, 0x79])),
    ("qblock", 3, B([0x53, 0x54], [0x55, 0x56])),
    ("coin_bg", 3, B([0xA5, 0xA6], [0xA7, 0xA8])),
    ("coin_water", 3, B([0xC2, 0xC3], [0xC4, 0xC5])),
    ("used_block", 3, B([0x57, 0x58], [0x59, 0x5A])),
    ("axe", 3, B([0x7B, 0x7C], [0x7D, 0x7E])),
    ("hud_coin", 3, B([0x2E])),
    ("cursor_mushroom", 3, B([0xCE])),
]

# title logo: re-typeset by us (own letter tiles + own nametable script), no retail facts kept
LOGO_TILES = [0x100 + t for t in (0x42, 0x43, 0x44, 0x46, 0x48, 0x49, 0x4A, 0x5F, 0x78, 0x7A, 0x95, 0x96, 0x97, 0x98)] +     list(range(0x1D0, 0x1E9))
SPARE = [0x19A, 0x19F, 0x1AF]          # not referenced by the title script; kept blank unless a use turns up

# glyph tiles: drawn from our own font, no retail facts kept
FONT = {0x100 + i: ch for i, ch in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
FONT.update({0x128: "-", 0x129: "x", 0x12B: "!", 0x1CF: "(c)"})
# CHR $1EC0-$1FFF is not pixels: the title screen's nametable/text script, read through the PPU (kept as layout + text)
DATA = range(0x1EC, 0x200)


def pictures():
    """-> list of dict(name, page, pal, layout, flips, kind)"""
    seen, out = set(), []

    def add(name, page, pal, layout, flips=None, kind="sprite"):
        out.append(dict(name=name, page=page, pal=pal, layout=layout, kind=kind,
                        flips=flips or [[0] * len(r) for r in layout]))

    base = ""
    for k, (vals, c) in enumerate(table("PlayerGraphicsTable")):
        size = "big" if k < 12 else "small" if k < 23 else ""
        if c.startswith("frame"):
            c = base + " " + c
        else:
            base = c.split("frame")[0].strip()
        g = _grid(vals, 2)
        add(_name("player", (size + " " + c).strip(), seen), 0, 0, g, _mirror(g))
    en = table("EnemyGraphicsTable")
    base = ""
    for k, (vals, c) in enumerate(en):
        if c.startswith(("frame", "front", "rear")):
            c = base + " " + c
        else:
            base = c.split("frame")[0].replace("front", "").replace("rear", "").strip()
        g = _grid(vals, 2)
        if "rear" in c:
            continue
        if "front" in c:                                                  # bowser: front + rear halves side by side
            rear = [[None if v == 0xFC else v for v in en[k + 1][0][i:i + 2]] for i in (0, 2, 4)]
            g = [[None if v == 0xFC else v for v in vals[i:i + 2]] for i in (0, 2, 4)]
            g = [y + x for x, y in zip(g, rear)]                          # stored facing right: rear is the left half
            add(_name("enemy", c.replace("front ", ""), seen), 0, 1, g)
            continue
        add(_name("enemy", c, seen), 0, 1, g, _mirror(g))
    for (vals, c) in table("PowerUpGfxTable")[:3]:
        g = _grid(vals, 2)
        add(_name("powerup", c, seen), 0, 2, g, _mirror(g))
    for name, pal, layout in SPRITES_EXTRA:
        add(name, 0, pal, layout, _mirror(layout) if all(len(r) == 2 for r in layout) else None,
            kind="own" if name.startswith("score_") else "sprite")      # numerals: re-typeset, nothing kept
    for name, pal, layout in BACKGROUND:
        add(name, 1, pal, layout, kind="bg")
    for t in LOGO_TILES + SPARE:
        add(f"logo_{t - 256:02x}", 1, 1, [[t]], kind="own")
    for t, ch in FONT.items():
        add("glyph_" + {"-": "dash", "x": "times", "!": "bang", "(c)": "copyright"}.get(ch, ch), 1, 2, [[t]], kind="glyph")
    return out


def owners(pics, ntiles=512):
    """tile -> (picture index, row, col); first listing wins"""
    own = {}
    for i, p in enumerate(pics):
        for r, row in enumerate(p["layout"]):
            for c, t in enumerate(row):
                if t is not None and t not in own:
                    own[t] = (i, r, c)
    return own


if __name__ == "__main__":
    P = pictures()
    own = owners(P)
    free = [t for t in range(512) if t not in own and t not in DATA]
    print(len(P), "pictures;", len(own), "tiles owned;", len(free), "free")
    print("free spr:", " ".join(f"{t:02x}" for t in free if t < 256))
    print("free bg :", " ".join(f"{t - 256:02x}" for t in free if t >= 256))
    print(" ".join(p["name"] for p in P if p["page"] == 0))
