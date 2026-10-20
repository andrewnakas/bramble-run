"""CLEAN ROOM: spec + our art -> CHR, palettes -> assembled ROM.

    python -m games.smb.generate [work dir = D:/n64work/smb] [dev=W,L,A]

dev=W,L,A (0-based world, level, area) assembles a second ROM, clean/dev.nes, that starts there: a test aid for
headless screenshots, never copied to the site (1-2 = 0,1,2; 1-4 = 0,3,4; 2-2 = 1,1,2).

Reads only games/smb (spec, art, code) and the pristine disassembly (code,
levels, music: kept). Never reads the retail ROM.
"""
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

from cleanroom.nes import chr as C
from games.smb import art as A
from games.smb import atlas, font, palettes, title

HERE = os.path.dirname(os.path.abspath(__file__))


def build_pictures():
    """-> (pictures, {name: index image})"""
    spec, art = A.load_spec(), A.load_art()
    P = atlas.pictures()
    known = {p["name"] for p in P}
    stray = sorted(set(art) - known)
    if stray:
        print("art blocks without a picture:", " ".join(stray))
    return P, {p["name"]: A.render(p, spec, art) for p in P if p["kind"] not in ("glyph",)}


def build_chr():
    meta = json.load(open(os.path.join(HERE, "spec", "meta.json")))
    P, imgs = build_pictures()
    tiles = np.zeros((512, 8, 8), np.uint8)
    own = atlas.owners(P)
    for t, (i, r, c) in own.items():
        p = P[i]
        if p["kind"] == "glyph":
            continue
        px = imgs[p["name"]][r * 8:r * 8 + 8, c * 8:c * 8 + 8]
        f = p["flips"][r][c]
        if f & 1:
            px = px[:, ::-1]
        tiles[t] = px
    for t, ch in atlas.FONT.items():
        tiles[t] = font.glyph(ch) * meta["font_index"]
    for t, px in title.tiles().items():
        tiles[0x100 + t] = px
    data = bytearray(C.encode(tiles))
    data[0x1EC0:0x2000] = title.script()
    return bytes(data), tiles


def patch_palettes(asm: str) -> str:
    lines = asm.split("\n")
    for label, rows in palettes.TABLES.items():
        i = next(k for k, l in enumerate(lines) if l.startswith(label + ":")) + 1
        for row in rows:
            while not lines[i].strip().startswith(".db"):
                i += 1
            m = re.match(r"(\s*\.db\s+)([^;]*?)(\s*;.*)?$", lines[i])
            n = len([v for v in m.group(2).split(",") if v.strip()])
            assert n == len(row), f"{label}: row has {n} bytes, ours {len(row)}"
            body = ", ".join(f"${v:02x}" for v in row)
            lines[i] = m.group(1) + body + (m.group(3) or "")
            i += 1
    return "\n".join(lines)


HOOKS = [h for h in os.environ.get("SMB_HOOKS", "levelgen,music,text").split(",") if h]


def pad_vectors(asm: str) -> str:
    """new data may be shorter than the disassembly's: fill up to the vectors (overflow = assembler error)"""
    key = "; INTERRUPT VECTORS"
    assert asm.count(key) == 1
    return asm.replace(key, "\t.pad $fffa, $ff\n" + key)


def labels(nes_path):
    """{label: cpu address} from asm6f -n output (<rom>.0.nl / .1.nl)"""
    out = {}
    for k in (0, 1):
        f = f"{nes_path}.{k}.nl"
        if os.path.exists(f):
            for line in open(f, encoding="latin-1"):
                a, n = line.strip().split("#")[:2]
                out[n] = int(a[1:], 16)
    return out


def build_dev(work, dst, p, dev):
    """second ROM that starts at world/level/area `dev` (test aid, never on the site)"""
    w, l, a = (int(v) for v in dev.split(","))
    lines = open(p, encoding="latin-1", newline="").read().split("\n")
    i = next(k for k, x in enumerate(lines) if x.lstrip().startswith("BCC StartWorld1"))
    j = next(k for k, x in enumerate(lines) if x.lstrip().startswith("STA PrimaryHardMode"))
    # same size as the 29 bytes it replaces (PRG is full: nothing may move)
    block = [f"LDA #${w:02x}", "STA WorldNumber", f"LDA #${l:02x}", "STA LevelNumber", f"LDA #${a:02x}", "STA AreaNumber",
             "JSR LoadAreaPointer", "INC Hidden1UpFlag", "INC FetchNewGameTimerFlag", "INC OperMode", "NOP", "NOP"]
    lines[i:j + 1] = ["StartWorld1:"] + ["\t" + x for x in block]
    open(p, "w", encoding="latin-1", newline="").write("\n".join(lines))
    r = subprocess.run([os.path.join(work, "tools", "asm6f.exe"), "smb1.asm", "-q", "bin/dev.nes"], cwd=dst,
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("asm6f (dev) failed:\n" + (r.stdout + r.stderr)[-800:])
    shutil.copyfile(os.path.join(dst, "bin", "dev.nes"), os.environ.get("SMB_DEV_OUT") or os.path.join(work, "clean", "dev.nes"))
    print(f"dev ROM {work}/clean/dev.nes starts at world {w + 1}-{l + 1}")


def main(argv):
    dev = next((a[4:] for a in argv[1:] if a.startswith("dev=")), None)
    argv = [a for a in argv if not a.startswith("dev=")]
    work = argv[1] if len(argv) > 1 else "D:/n64work/smb"
    src, dst = os.path.join(work, "ref", "smb1"), os.path.join(work, "clean", "smb1")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "bin", "*.chr", "*.nes"))
    os.makedirs(os.path.join(dst, "bin"))
    p = os.path.join(dst, "src", "prg.asm")
    asm = open(p, encoding="latin-1", newline="").read()
    open(p, "w", encoding="latin-1", newline="").write(pad_vectors(patch_palettes(asm)))
    for m in HOOKS:                     # new content: levels, music + sfx, text
        try:
            mod = importlib.import_module("games.smb." + m)
        except ModuleNotFoundError as e:
            if e.name != "games.smb." + m:
                raise
            print(f"  ({m}: module missing, kept disassembly data)")
            continue
        print(f"  {m}: {mod.patch(dst)}")
    data, tiles = build_chr()
    open(os.path.join(dst, "smb1.chr"), "wb").write(data)
    r = subprocess.run([os.path.join(work, "tools", "asm6f.exe"), "smb1.asm", "-q", "-n", "bin/smb1.nes"], cwd=dst,
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("asm6f failed:\n" + (r.stdout + r.stderr)[-1500:])
    rom = open(os.path.join(dst, "bin", "smb1.nes"), "rb").read()
    out = os.path.join(work, "clean", "smb.nes")
    open(out, "wb").write(rom)
    for k in (0, 1):
        nl = os.path.join(dst, "bin", f"smb1.nes.{k}.nl")
        if os.path.exists(nl):
            shutil.copyfile(nl, out + f".{k}.nl")
    if dev:
        build_dev(work, dst, p, dev)
    art = A.load_art()
    drawn = sum(1 for n in A.load_spec() if n in art)
    print(f"clean ROM {out}: {len(rom)} bytes sha1 {hashlib.sha1(rom).hexdigest()[:12]}; "
          f"{drawn}/{len(A.load_spec())} pictures hand-drawn, {len(atlas.FONT)} glyphs, {len(title.SLOTS)} title tiles, "
          f"{len(palettes.TABLES)} palette tables")


if __name__ == "__main__":
    main(sys.argv)
