"""Taint checks for NES stored forms (DIRTY ROOM tool: reads retail + clean).

Forms covered: raw 2bpp planar bytes (any offset, any file), decoded tile
pixels (any tile slot, any flip), palette rows. See docs/PLATFORM_NES.md
for the coincidence rule.
"""
import os

import numpy as np

from . import chr as C

WINDOW = 16          # bytes of raw CHR (= one tile when aligned)
MIN_DISTINCT = 6     # a window with fewer distinct byte values is trivial (fills, stripes)
GREYS = {0x00, 0x10, 0x20, 0x30, 0x0D, 0x0F, 0x1D, 0x2D, 0x3D, 0x0E, 0x1E, 0x2E, 0x3E, 0x1F, 0x2F, 0x3F}


def windows(data: bytes, lo=0, hi=None):
    """set of non-trivial WINDOW-byte strings of data[lo:hi] (every offset)"""
    hi = len(data) if hi is None else hi
    out = set()
    for o in range(lo, hi - WINDOW + 1):
        w = data[o:o + WINDOW]
        if len(set(w)) >= MIN_DISTINCT:
            out.add(w)
    return out


def scan_bytes(retail_windows, blob: bytes):
    """-> offsets in blob where a retail window occurs"""
    hits = []
    for o in range(0, len(blob) - WINDOW + 1):
        if blob[o:o + WINDOW] in retail_windows:
            hits.append(o)
    return hits


def scan_tree(retail_windows, root, skip=(".git",)):
    """-> [(path, hits)] for every file under root"""
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in skip]
        for f in files:
            p = os.path.join(d, f)
            if os.path.getsize(p) > 64 << 20:
                continue
            h = scan_bytes(retail_windows, open(p, "rb").read())
            if h:
                out.append((p, len(h)))
    return out


def variants(t):
    return [t, t[:, ::-1], t[::-1], t[::-1, ::-1]]


def tile_key(t):
    return np.asarray(t, np.uint8).tobytes()


def colours(t):
    return len(set(np.unique(t)) - {0})


def tile_matches(retail_tiles, clean_tiles):
    """-> [(clean slot, retail slot, n nonzero colours, n set pixels)] for clean tiles equal to any retail tile (any flip)"""
    index = {}
    for i, t in enumerate(retail_tiles):
        for v in variants(t):
            index.setdefault(tile_key(v), i)
    out = []
    for i, t in enumerate(clean_tiles):
        j = index.get(tile_key(t))
        if j is not None:
            out.append((i, j, colours(t), int((t > 0).sum())))
    return out


def palette_rows(retail_rows, clean_rows):
    """rows = lists of master ids (same shape). -> (identical colourful rows, identical grey rows, total)"""
    bad, grey = [], []
    for k, (r, c) in enumerate(zip(retail_rows, clean_rows)):
        if list(r) == list(c) and len(r) >= 3:
            (grey if all((v & 0x3F) in GREYS for v in r) else bad).append(k)
    return bad, grey, len(retail_rows)
