"""DIRTY ROOM: taint scan of the clean ROM (and publish trees) against retail.

    python -m games.smb.taint_report <retail.nes> <clean.nes> [tree to scan ...] [-v]

Prints one screen and "TAINT: n failing". Rules (logged in STATUS.md):
  T1 raw     any 16-byte window of retail CHR pixels (>= 6 distinct byte values) found in the clean ROM
             or in any file of the given trees -> fail
             (forgiven: windows lying in T2 coincidence tiles, bar <= 6 bytes or <= 2 distinct values elsewhere)
  T2 tile    a clean tile equal to any retail tile (any slot, any flip):
             - uniform tile (one value) or <= 10 set pixels                            -> coincidence, counted
             - anything else                                                           -> fail
  T3 picture nothing of the retail art is kept (2026-10 bar): per picture, with >= 12 set pixels on either side,
             silhouette IoU > 0.70 and colour agreement beyond chance (Cohen's kappa over the union) > 0.40 -> fail
  T4 script  title script: any retail entry that draws non-text tiles (>= 8 data bytes) present in ours -> fail
  T5 palette a palette row equal to retail with a non-grey colour                      -> fail (grey rows: counted)
  T6 prg     every 16-byte PRG window (>= 6 distinct values) equal to a retail window must also be in
             clean/code_only.prg (the program assembled with all content blanked, games.smb.orig_export):
             only compiled program code and structure tables may match retail; levels/music/text may not
"""
import os
import sys

import numpy as np

from cleanroom.nes import chr as C
from cleanroom.nes import taint as T
from games.smb import atlas, palettes


def script_entries(d):
    out, i = [], 0
    while i < len(d) and d[i]:
        c = d[i + 2]
        n = 1 if c & 64 else (c & 63)
        out.append(bytes(d[i + 3:i + 3 + n]))
        i += 3 + n
    return out


def table_rows(asm_path, label):
    return [r for r, _ in atlas.table(label, asm_path)]


def main(argv):
    verbose = "-v" in argv
    args = [a for a in argv[1:] if a != "-v"]
    retail, clean, trees = open(args[0], "rb").read(), open(args[1], "rb").read(), args[2:]
    _, rprg, rchr = C.split_ines(retail)
    _, cprg, cchr = C.split_ines(clean)
    fails, lines = 0, []

    # T2 (first: T1 forgives raw hits that lie inside tiles T2 classes as coincidences)
    rt, ct = C.decode(rchr[:0x1EC0]), C.decode(cchr[:0x1EC0])
    P = atlas.pictures()
    own = atlas.owners(P)
    bad, coinc = [], set()
    for i, j, ncol, npx in T.tile_matches(rt, ct):
        uniform = len(np.unique(ct[i])) == 1
        if uniform or npx <= 10:
            coinc.add(i)
        else:
            bad.append((i, j, P[own[i][0]]["name"] if i in own else "unowned"))
    fails += len(bad)
    t2 = (f"T2 tiles: {len(bad)} failing, {len(coinc)} coincidences (uniform / <= 10 px)"
          + "".join(f"\n     tile {i:03x} == retail {j:03x} ({n})" for i, j, n in bad[:(99 if verbose else 10)]))

    # T1
    win = T.windows(rchr, 0, 0x1EC0)

    def rom_hits(blob):
        if blob[:4] != b"NES":
            return T.scan_bytes(win, blob)
        base = len(blob) - 8192

        def implied(k):          # is this byte fixed by kept facts? (coincidence tile, or a row with <= 1 non-zero colour:
            if k < base:         #  one plane = the silhouette row, the other = 0 or the same)
                return False
            return (k - base) // 16 in coinc

        def outside(o):
            return bytes(blob[k] for k in range(o, o + T.WINDOW) if not implied(k))

        return [o for o in T.scan_bytes(win, blob) if len(outside(o)) > 6 and len(set(outside(o))) > 2]

    h = rom_hits(clean)
    tree_hits = []
    for t in trees:
        for d, dirs, files in os.walk(t):
            dirs[:] = [x for x in dirs if x != ".git"]
            for f in files:
                n = len(rom_hits(open(os.path.join(d, f), "rb").read()))
                if n:
                    tree_hits.append((os.path.join(d, f), n))
    fails += (1 if h else 0) + len(tree_hits)
    lines.append(f"T1 raw windows: {len(win)} retail windows; clean ROM hits {len(h)}"
                 f" (tiles {' '.join(sorted({format((o - len(clean) + 8192) // 16, '03x') for o in h}))}); tree files hit {len(tree_hits)}"
                 + "".join(f"\n     {p} x{n}" for p, n in tree_hits[:8]))
    lines.append(t2)

    # T3
    worst, pfail = [], 0
    for p in P:
        if p["kind"] == "glyph" or p["name"] == "fills":
            continue
        r = C.compose(rt, p["layout"], p["flips"])
        c = C.compose(ct, p["layout"], p["flips"])
        rs, cs = r > 0, c > 0
        union = rs | cs
        if max(rs.sum(), cs.sum()) < 12:
            continue
        iou = float((rs & cs).sum() / union.sum())
        cu, ru = c[union], r[union]
        po = float((cu == ru).mean())
        pe = float(sum((cu == v).mean() * (ru == v).mean() for v in range(4)))
        agree = (po - pe) / (1 - pe) if pe < 1 else 1.0          # Cohen's kappa: agreement beyond chance
        f = iou > 0.70 and agree > 0.40
        pfail += f
        worst.append((iou, agree, p["name"], f))
    worst.sort(reverse=True)
    fails += pfail
    lines.append(f"T3 pictures: {pfail} failing ({' '.join(w[2] for w in worst if w[3])}) of {len(worst)}; mean silhouette IoU "
                 f"{np.mean([w[0] for w in worst]):.2f}; closest: "
                 + ", ".join(f"{n} {i:.2f}/{a:.2f}" for i, a, n, f in worst[:(40 if verbose else 5)]))

    # T4
    re_ = [e for e in script_entries(rchr[0x1EC0:]) if len(e) >= 8 and any(b >= 0x30 and b != 0xCF for b in e)]
    ce = set(script_entries(cchr[0x1EC0:]))
    sb = [e for e in re_ if e in ce or e in cchr[0x1EC0:]]
    fails += len(sb)
    lines.append(f"T4 title script: {len(sb)} retail picture rows present (of {len(re_)})")

    # T5 / T6: compare PRG byte by byte; differing bytes must be palette colours
    diff = [i for i in range(len(rprg)) if rprg[i] != cprg[i]]
    work = os.path.dirname(os.path.dirname(os.path.abspath(args[1])))
    r_asm = os.path.join(work, "ref", "smb1", "src", "prg.asm")
    c_asm = os.path.join(work, "clean", "smb1", "src", "prg.asm")
    rows_r, rows_c = [], []
    for label in palettes.TABLES:
        a, b = table_rows(r_asm, label), table_rows(c_asm, label)
        k = len(palettes.TABLES[label])
        rows_r += [x for x in a[:k] if len(x) >= 3 and x[0] != 0x3F]
        rows_c += [x for x in b[:k] if len(x) >= 3 and x[0] != 0x3F]
    pb, grey, total = T.palette_rows([r[-3:] for r in rows_r], [c[-3:] for c in rows_c])
    fails += len(pb)
    lines.append(f"T5 palettes: {len(pb)} colourful rows equal to retail, {len(grey)} grey rows equal (coincidence), of {total}"
                 + "".join(f"\n     row {k}: {[hex(v) for v in rows_r[k]]}" for k in pb[:10]))
    co_path = os.path.join(work, "clean", "code_only.prg")
    if not os.path.exists(co_path):
        fails += 1
        lines.append("T6 PRG: clean/code_only.prg missing (run python -m games.smb.orig_export) -> FAIL")
    else:
        co = open(co_path, "rb").read()
        rw = {bytes(rprg[i:i + 16]) for i in range(len(rprg) - 15)}
        bad = [i for i in range(len(cprg) - 15)
               if len(set(cprg[i:i + 16])) >= 6 and bytes(cprg[i:i + 16]) in rw and cprg[i:i + 16] != co[i:i + 16]]
        fails += 1 if bad else 0
        lines.append(f"T6 PRG: {len(diff)} bytes differ from retail; {len(bad)} retail-equal 16-byte windows outside "
                     f"the compiled program" + (f" (first at ${0x8000 + bad[0]:04X})" if bad else "") + f" -> {'FAIL' if bad else 'ok'}")

    print("\n".join(lines))
    print(f"TAINT: {fails} failing")
    return fails


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv) else 0)
