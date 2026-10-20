"""Inputs for the originality gate: the same decoders run on the retail ROM (dirty room) and on the clean ROM.

    python -m games.smb.orig_export [work dir = D:/n64work/smb]
      -> <work>/dirty/orig/{music,text,levels,pictures}   (never committed)
      -> <work>/clean/orig/{music,text,levels,pictures}
      -> <work>/clean/code_only.prg   (program assembled with every content block blanked: the 'compiled' file)
    then: python -m cleanroom.originality <work>/dirty/orig <work>/clean/orig games/smb --report ORIGINALITY.md
"""
import os
import shutil
import subprocess
import sys

from games.smb import generate, levelgen, levels, music, pictures_export, text

SCRATCH = os.environ.get("SMB_SCRATCH", os.path.join(os.environ.get("TEMP", "/tmp"), "smb_orig"))


def code_only(work):
    """assemble the clean tree once more with all content blanked (levels, music, text, palettes, CHR):
    what remains is the program the disassembly compiles to, plus the structure tables it needs"""
    src = os.path.join(work, "clean", "smb1")
    d = os.path.join(SCRATCH, "codeonly")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(src, d, ignore=shutil.ignore_patterns("bin"))
    os.makedirs(os.path.join(d, "bin"))
    import re
    for rel in ("src/levels/objects.asm", "src/levels/enemies.asm", "src/music-data.asm"):
        p = os.path.join(d, rel)
        out, keep = [], False
        for line in open(p, encoding="latin-1").read().split("\n"):
            if re.match(r"^[A-Za-z_]\w*:", line):
                keep = line.startswith("FreqRegLookupTbl:")     # tuning table: structure, kept
            out.append(line if keep else re.sub(r"\$[0-9a-fA-F]{2}", "$00", line))
        open(p, "w", encoding="latin-1", newline="").write("\n".join(out))
    p = os.path.join(d, "src", "prg.asm")
    lines = open(p, encoding="latin-1", newline="").read().split("\n")
    text.BLANK = True                           # strings -> spaces, VRAM layout bytes stay
    try:
        lines = text.replace_block(lines, "GameText", "WarpZoneNumbers:", text.game_text())
        lines = text.replace_block(lines, "MarioThanksMessage", "; ----", text.finale_text())
    finally:
        text.BLANK = False
    blank = set()
    for label in ("DemoActionData", "DemoTimingData"):     # attract inputs: content
        i = next(k for k, l in enumerate(lines) if l.startswith(label + ":"))
        k = i + 1
        while k < len(lines) and lines[k].strip():
            blank.add(k)
            k += 1
    from games.smb import palettes
    pal = set()
    for label in palettes.TABLES:
        i = next(k for k, l in enumerate(lines) if l.startswith(label + ":"))
        k = i + 1
        while k < len(lines) and not re.match(r"^[A-Za-z_]\w*:", lines[k]):
            pal.add(k)
            k += 1
    hdr = re.compile(r"^\s*\.db\s+(\$3f,\s*\$[0-9a-f]{2},\s*\$[0-9a-f]{2}|\$00)\s*(;.*)?$", re.I)
    for k in blank:
        if hdr.match(lines[k]):                 # VRAM address/length header, terminator: structure
            continue
        if lines[k].lstrip().startswith(".db"):
            lines[k] = re.sub(r"\$[0-9a-fA-F]{2}", "$00", lines[k])
    for k in pal:                               # colours -> $0f (black, the shared backdrop / outline colour)
        if not hdr.match(lines[k]) and lines[k].lstrip().startswith(".db"):
            lines[k] = re.sub(r"\$[0-9a-fA-F]{2}", "$0f", lines[k])
    open(p, "w", encoding="latin-1", newline="").write("\n".join(lines))
    open(os.path.join(d, "smb1.chr"), "wb").write(bytes(0x2000))
    subprocess.run([os.path.join(work, "tools", "asm6f.exe"), "smb1.asm", "-q", "bin/c.nes"], cwd=d, check=True)
    prg = open(os.path.join(d, "bin", "c.nes"), "rb").read()[16:16 + 0x8000]
    open(os.path.join(work, "clean", "code_only.prg"), "wb").write(prg)
    return len(prg)


def main(work):
    clean = os.path.join(work, "clean", "smb.nes")
    retail = os.path.join(work, "dirty", "baserom.nes")
    rlab = music.retail_labels(os.path.join(SCRATCH, "retail"))
    clab = generate.labels(clean)
    anchors = {lab: a.anchors for lab, a in levelgen.build_all().items()}
    for rom, lab, out, anc in ((retail, rlab, os.path.join(work, "dirty", "orig"), None),
                               (clean, clab, os.path.join(work, "clean", "orig"), anchors)):
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        data = open(rom, "rb").read()
        music.export(data, lab, out)
        text.export(data, lab, out)
        levels.export(data, lab, out, anc)
        pictures_export.export(data, out)
        print(f"{out}: " + ", ".join(f"{k} {len(os.listdir(os.path.join(out, k)))}" for k in sorted(os.listdir(out))))
    print("code_only.prg", code_only(work), "bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "D:/n64work/smb")
