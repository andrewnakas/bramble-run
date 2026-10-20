"""Our own title board (BRAMBLE / RUN): block letters built from 15 quadrant tiles, an own
frame, and an own nametable script for CHR $1EC0 (the game streams that
script through the PPU into its VRAM buffer). Kept facts: the board
footprint (rows 4-14, cols 5-26), the attribute rows and the text lines.
"""
import numpy as np

# 3x7-cell block font (a cell is 4x4 px, a quarter of a tile)
FONT = {
    "S": "### #.. #.. ### ..# ..# ###", "U": "#.# #.# #.# #.# #.# #.# ###",
    "P": "### #.# #.# ### #.. #.. #..", "E": "### #.. #.. ##. #.. #.. ###",
    "R": "### #.# #.# ##. #.# #.# #.#", "M": "#...# ##.## #.#.# #.#.# #...# #...# #...#",
    "A": "### #.# #.# ### #.# #.# #.#", "I": "# # # # # # #",
    "O": "### #.# #.# #.# #.# #.# ###", "B": "##. #.# #.# ##. #.# #.# ##.",
    "L": "#.. #.. #.. #.. #.. #.. ###", "N": "#..# ##.# ##.# #.## #.## #..# #..#",
    ".": ". . . . . . #", " ": ". . . . . . .",
}
BOARD, INK, EDGE = 2, 1, 3            # colour indices (palette 1: sand / brown / black)

# own tile slots (background page numbers), see atlas.LOGO_TILES
SLOTS = [0x42, 0x43, 0x44, 0x46, 0x48, 0x49, 0x4A, 0x5F, 0x78, 0x7A, 0x95, 0x96, 0x97, 0x98] + list(range(0xD0, 0xE9))
QUAD = {m: SLOTS[m] for m in range(16)}                 # bit0 TL, bit1 TR, bit2 BL, bit3 BR
FRAME = {k: SLOTS[16 + i] for i, k in enumerate(["tl", "t", "tr", "l", "r", "bl", "b", "br"])}

TEXT = [(15, 10, "FENN AND MOSS"), (18, 11, "1 RUNNER"), (20, 11, "2 RUNNERS"), (23, 11, "BEST-"), (23, 22, "0")]
CHARS = {c: i for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
CHARS.update({" ": 0x24, "-": 0x28, "x": 0x29, "!": 0x2B, "@": 0xCF})


def tiles():
    """-> {bg tile number: 8x8 index image} for every own slot"""
    out = {s: np.zeros((8, 8), np.uint8) for s in SLOTS}
    for m in range(16):
        t = np.full((8, 8), BOARD, np.uint8)
        for b, (y, x) in enumerate([(0, 0), (0, 4), (4, 0), (4, 4)]):
            if m >> b & 1:
                t[y:y + 4, x:x + 4] = INK
                t[y + 3, x:x + 4] = EDGE            # each cell is a small stud: dark lower and right edge
                t[y:y + 4, x + 3] = EDGE
        out[QUAD[m]] = t
    # frame: 2 px black line with a sand highlight inside it, rounded corners
    def edge(side):
        t = np.full((8, 8), BOARD, np.uint8)
        v = np.array([0, 0, EDGE, EDGE, INK, BOARD, BOARD, BOARD], np.uint8)
        if side == "t":
            t[:] = v[:, None]
        elif side == "b":
            t[:] = v[::-1, None]
        elif side == "l":
            t[:] = v[None, :]
        elif side == "r":
            t[:] = v[None, ::-1]
        return t
    for s in "tblr":
        out[FRAME[s]] = edge(s)
    c = np.full((8, 8), BOARD, np.uint8)
    for y in range(8):
        for x in range(8):
            d = max(0, 4 - y) + max(0, 4 - x) if (y < 4 and x < 4) else 9
            ring = min(y, x)
            if y < 4 and x < 4 and (y + x) < 5:
                c[y, x] = 0
            elif ring <= 3 or (y < 5 and x < 5 and y + x < 7):
                c[y, x] = EDGE
            elif ring == 4:
                c[y, x] = INK
    c[:2, :] = 0
    c[:, :2] = 0
    c[2:4, 4:] = EDGE
    c[4:, 2:4] = EDGE
    c[4, 5:] = INK
    c[5:, 4] = INK
    c[2, 2] = c[2, 3] = c[3, 2] = 0
    c[3, 3] = c[4, 4] = EDGE
    c[5, 5] = INK
    out[FRAME["tl"]] = c
    out[FRAME["tr"]] = c[:, ::-1]
    out[FRAME["bl"]] = c[::-1]
    out[FRAME["br"]] = c[::-1, ::-1]
    return out


def _cells(text):
    rows = [""] * 7
    for i, ch in enumerate(text):
        g = FONT[ch].split()
        for y in range(7):
            rows[y] += g[y] + ("." if i < len(text) - 1 and ch != " " else "")
    return rows


def board_cells(w=40, h=18):
    """cell bitmap of the board interior (20x9 tiles)"""
    b = np.zeros((h, w), np.uint8)
    for text, y0 in (("BRAMBLE", 1), ("RUN", 10)):
        rows = _cells(text)
        x0 = (w - len(rows[0])) // 2 // 2 * 2
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                b[y0 + y, x0 + x] = c == "#"
    return b


def script(limit=0x13A) -> bytes:
    out = bytearray()

    def put(row, col, data, rep=0, vert=False):
        a = 0x2000 + row * 32 + col
        if rep:
            out.extend([a >> 8, a & 255, 0x40 | (0x80 if vert else 0) | rep, data[0]])
        else:
            out.extend([a >> 8, a & 255, (0x80 if vert else 0) | len(data)] + list(data))

    b = board_cells()
    for r in range(9):
        row = [QUAD[int(b[2 * r, 2 * c]) | int(b[2 * r, 2 * c + 1]) << 1 | int(b[2 * r + 1, 2 * c]) << 2 | int(b[2 * r + 1, 2 * c + 1]) << 3]
               for c in range(20)]
        used = [i for i, t in enumerate(row) if t != QUAD[0]]
        if not used:
            put(5 + r, 6, [QUAD[0]], rep=20)
            continue
        a, z = used[0], used[-1] + 1
        if a:
            put(5 + r, 6, [QUAD[0]], rep=a) if a > 1 else put(5 + r, 6, [QUAD[0]])
        put(5 + r, 6 + a, row[a:z])
        if z < 20:
            put(5 + r, 6 + z, [QUAD[0]], rep=20 - z) if 20 - z > 1 else put(5 + r, 6 + z, [QUAD[0]])
    put(4, 5, [FRAME["tl"]])
    put(4, 6, [FRAME["t"]], rep=20)
    put(4, 26, [FRAME["tr"]])
    put(5, 5, [FRAME["l"]], rep=9, vert=True)
    put(5, 26, [FRAME["r"]], rep=9, vert=True)
    put(14, 5, [FRAME["bl"]])
    put(14, 6, [FRAME["b"]], rep=20)
    put(14, 26, [FRAME["br"]])
    for row, col, s in TEXT:
        put(row, col, [CHARS[c] for c in s])
    out.extend([0x23, 0xC9, 0x40 | 22, 0x55])                 # board rows: palette 1
    out.extend([0x23, 0xE2, 4, 0x99, 0xAA, 0xAA, 0xAA])       # menu text: palette 2
    out.extend([0x23, 0xEA, 4, 0x99, 0xAA, 0xAA, 0xAA])
    out.append(0)
    assert len(out) <= limit, f"title script {len(out)} > {limit}"
    return bytes(out) + b"\xff" * (0x140 - len(out))


if __name__ == "__main__":
    for r in board_cells():
        print("".join("#" if v else "." for v in r))
    print(len(script().rstrip(b"\xff")), "bytes")
