"""Our pixel art: one index image (0..3) per atlas picture.

Sources, in order:
  1. `own` pictures (score popups, etc.): drawn by code here.
  2. art/*.txt: hand-drawn ASCII. A block is `@ name` followed by rows of
     `.` (transparent), `1 2 3` (colour index); `?` marks pixels of tiles the
     picture does not own (context only, ignored).
  3. bg_art.py: pictures easier to state as rules.
Nothing retail is used (2026-10 originality bar): no silhouettes, no colour
grids; the spec only gives sizes and the uniform fill values.
"""
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def load_spec():
    return json.load(open(os.path.join(HERE, "spec", "pictures.json")))


def load_art():
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, "art", "*.txt"))):
        name = None
        for line in open(f, encoding="utf-8").read().split("\n"):
            if line.startswith("@"):
                name = line[1:].strip()
                out[name] = []
            elif (line.startswith("#") and not line.startswith("##")) or name is None:
                continue
            elif line.strip() or out[name]:
                out[name].append(line.rstrip("\r"))
    for k in out:
        while out[k] and not out[k][-1].strip():
            out[k].pop()
    from games.smb import bg_art
    for k, f in bg_art.CODE.items():
        out.setdefault(k, f())
    return out


def parse(rows, w, h) -> np.ndarray:
    """-> (h, w) of 0..3 (`.`, `?`, space and missing pixels are 0)"""
    out = np.zeros((h, w), np.uint8)
    for y, r in enumerate(rows[:h]):
        for x, c in enumerate(r[:w]):
            if c in "123":
                out[y, x] = int(c)
    return out


def _directives(img, lines):
    """`!outline <c>`: paint the edge pixels of our own drawn shape (never a retail silhouette)"""
    sil = img > 0
    for d in lines:
        k = d[1:].split()
        if k[0] == "outline":
            pad = np.pad(sil, 1, constant_values=False)
            edge = sil & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
            img = np.where(edge, int(k[1]), img)
    return img.astype(np.uint8)


def render(p, spec, art) -> np.ndarray:
    """atlas picture -> index image, drawn freely by us (spec gives only the size / fill values)"""
    name = p["name"]
    h, w = len(p["layout"]) * 8, len(p["layout"][0]) * 8
    if name in OWN:
        return OWN[name]()
    s = spec.get(name) or {}
    if "uniform" in s:
        return np.concatenate([np.full((8, 8), v, np.uint8) for v in s["uniform"]], axis=1)
    rows = art.get(name)
    if rows is None:
        return np.zeros((h, w), np.uint8)
    img = parse([r for r in rows if not r.startswith("!")], w, h)
    return _directives(img, [r for r in rows if r.startswith("!")])


# 3x6 numerals for the score popups (own design; a tile holds two of them)
_NUM = {"0": "111 101 101 101 101 111", "1": "010 110 010 010 010 111", "2": "111 001 111 100 100 111",
        "4": "101 101 101 111 001 001", "5": "111 100 111 001 001 111", "8": "111 101 111 101 101 111",
        "U": "101 101 101 101 101 111", "P": "111 101 111 100 100 100", " ": "000 000 000 000 000 000"}


def _numerals(text, colour=2):
    out = np.zeros((8, 4 * len(text)), np.uint8)
    for i, ch in enumerate(text):
        for y, r in enumerate(_NUM[ch].split()):
            for x, c in enumerate(r):
                if c == "1":
                    out[1 + y, 4 * i + x] = colour
    return out


OWN = {
    "score_100_8000": lambda: _numerals("10204050800 "),      # 100 = "10" + "0 ", 1000 = "10" + "00"
    "score_00": lambda: _numerals("00"),
    "score_1up": lambda: _numerals("1UP "),
}


def ascii_of(img, owned=None) -> str:
    """index image -> text; pixels of tiles this picture does not own are shown as `:` (empty) / `+` (set)"""
    rows = []
    for y in range(img.shape[0]):
        r = ""
        for x in range(img.shape[1]):
            v = img[y, x]
            if owned is not None and not owned[y // 8][x // 8]:
                r += "+" if v else ":"
            else:
                r += ".123"[v]
        rows.append(r)
    return "\n".join(rows)
