"""CLEAN ROOM: our own wording for every in-game string (status bar, lives screen, time-out, game over,
shortcut notice, end-of-keep and finale messages, world select).

Kept as structure only: the VRAM-write string format (address hi, lo, length, tile codes; $FF / $00 ends),
the screen row each message sits on, the 5-letter name slot the code swaps for player 2, the labels the
code reads. Wording, names and columns are ours (names in STATUS.md and games/smb/names.json).

    patch(dst)                        rewrite the text blocks of src/prg.asm
    export(rom, labels, outdir)       decode every string of a ROM to <outdir>/text/strings.json
"""
import json
import os
import re

P1, P2 = "FENN ", "MOSS "                  # 5-tile name slot (code copies 5 tiles over the P1 name)


BLANK = False                              # code-only build: every glyph becomes a space (layout bytes stay)


def enc(s):
    out = []
    for ch in s:
        if BLANK:
            out.append(0x24)
            continue
        if ch.isdigit():
            out.append(int(ch))
        elif "A" <= ch <= "Z":
            out.append(0x0A + ord(ch) - ord("A"))
        else:
            out.append({" ": 0x24, "-": 0x28, "x": 0x29, "!": 0x2B, ".": 0xAF}[ch])
    return out


def dec(codes):
    s = ""
    for c in codes:
        if c < 10:
            s += str(c)
        elif c < 0x24:
            s += chr(ord("A") + c - 0x0A)
        else:
            s += {0x24: " ", 0x28: "-", 0x29: "x", 0x2B: "!", 0xAF: ".", 0x2E: "*"}.get(c, " ")
    return s


def at(row_addr, text, center=True, col=None):
    """VRAM string: row_addr = nametable address of the row start"""
    c = (32 - len(text)) // 2 if col is None else col
    a = row_addr + c
    return [a >> 8, a & 0xFF, len(text)] + enc(text)


def db(vals):
    return "\n".join("\t.db " + ", ".join(f"${v:02x}" for v in vals[i:i + 12]) for i in range(0, len(vals), 12))


def game_text():
    """the GameText block (8-bit offsets from GameText: keep it under 256 bytes)"""
    L = []
    L += ["GameText:", "TopStatusBarLine:",
          db([0x20, 0x43, 0x05] + enc(P1) + [0x20, 0x52, 0x0c] + enc("ROUTE  CLOCK")
             + [0x20, 0x68, 0x05, 0x00, 0x24, 0x24, 0x2e, 0x29, 0x23, 0xc0, 0x7f, 0xaa, 0x23, 0xc2, 0x01, 0xea, 0xff])]
    L += ["WorldLivesDisplay:",
          db([0x21, 0xcd, 0x07, 0x24, 0x24, 0x29, 0x24, 0x24, 0x24, 0x24, 0x21, 0x4b, 0x09] + enc("ROUTE  - ")
             + [0x22, 0x0c, 0x48, 0x24, 0x23, 0xdc, 0x01, 0xba, 0xff])]
    L += ["TwoPlayerTimeUp:", db([0x21, 0xcd, 0x05] + enc(P1)),
          "OnePlayerTimeUp:", db([0x22, 0x0c, 0x08] + enc("TOO LATE") + [0xff])]
    L += ["TwoPlayerGameOver:", db([0x21, 0xcd, 0x05] + enc(P1)),
          "OnePlayerGameOver:", db([0x22, 0x0b, 0x09] + enc("RUN ENDED") + [0xff])]
    L += ["WarpZoneWelcome:", db(at(0x2580, "SECRET PATHS AHEAD.") +
                                 [0x26, 0x25, 0x01, 0x24, 0x26, 0x2d, 0x01, 0x24, 0x26, 0x35, 0x01, 0x24,
                                  0x27, 0xd9, 0x46, 0xaa, 0x27, 0xe1, 0x45, 0xaa, 0xff])]
    L += ["LuigiName:", db(enc(P2))]
    return L


def finale_text():
    L = []
    L += ["MarioThanksMessage:", db(at(0x2540, "NICE RUN " + P1.strip() + "!") + [0x00])]
    L += ["LuigiThanksMessage:", db(at(0x2540, "NICE RUN " + P2.strip() + "!") + [0x00])]
    L += ["MushroomRetainerSaved:", db(at(0x25c0, "THE QUEEN IS NOT HERE.") + at(0x2600, "TRY THE NEXT KEEP!") + [0x00])]
    L += ["PrincessSaved1:", db(at(0x25a0, "THE BELL RINGS AGAIN.") + [0x00])]
    L += ["PrincessSaved2:", db(at(0x25e0, "NOW TRY THE HARDER ROAD.") + [0x00])]
    L += ["WorldSelectMessage1:", db(at(0x2640, "PRESS B TO PICK") + [0x00])]
    L += ["WorldSelectMessage2:", db(at(0x2680, "A STARTING ROUTE") + [0x00])]
    return L


def replace_block(lines, first, stop, new):
    i = next(k for k, l in enumerate(lines) if l.startswith(first + ":"))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith(stop))
    return lines[:i] + new + [""] + lines[j:]


def patch(dst):
    p = os.path.join(dst, "src", "prg.asm")
    lines = open(p, encoding="latin-1", newline="").read().split("\n")
    # GameText ... WarpZoneNumbers (numbers kept: they are digits the warp code indexes)
    lines = replace_block(lines, "GameText", "WarpZoneNumbers:", game_text())
    lines = replace_block(lines, "MarioThanksMessage", "; ----", finale_text())
    open(p, "w", encoding="latin-1", newline="").write("\n".join(lines))
    n = len(strings_of(game_text() + finale_text()))
    return f"{n} strings rewritten ({P1.strip()} / {P2.strip()})"


def strings_of(asm_lines):
    data = []
    for l in "\n".join(asm_lines).split("\n"):
        if l.startswith("\t.db"):
            data += [int(v.strip()[1:], 16) for v in l[4:].split(",")]
    return decode_stream(bytes(data))


def decode_stream(b, limit=None):
    out, i = [], 0
    while i + 2 < len(b):
        hi, lo, n = b[i], b[i + 1], b[i + 2]
        if hi in (0x00, 0xFF) or not (0x20 <= hi <= 0x27):
            i += 1
            continue
        ln = n & 0x3F
        if n & 0x40:                       # repeat run: one tile
            i += 4
            continue
        codes = b[i + 3:i + 3 + ln]
        if hi < 0x23 or (hi >= 0x24 and hi < 0x27):
            s = dec(codes).strip()
            if s and any(c.isalpha() for c in s):
                out.append(s)
        i += 3 + ln
    return out


LABELS = ["GameText", "WarpZoneNumbers", "MarioThanksMessage", "WorldSelectMessage2"]


def export(rom, labels, outdir):
    """strings of the GameText and finale blocks of a ROM (labels: asm6f .nl map)"""
    prg = rom[16:16 + 0x8000]

    def span(a, b, extra=0):
        return prg[labels[a] - 0x8000:labels[b] - 0x8000 + extra]
    s = decode_stream(span("GameText", "WarpZoneNumbers")) + decode_stream(span("MarioThanksMessage", "WorldSelectMessage2", 40))
    name = dec(prg[labels["LuigiName"] - 0x8000:labels["LuigiName"] - 0x8000 + 5]).strip()
    s.append(name)
    os.makedirs(os.path.join(outdir, "text"), exist_ok=True)
    json.dump(s, open(os.path.join(outdir, "text", "strings.json"), "w"), indent=1)
    return s
