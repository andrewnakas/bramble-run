"""CLEAN ROOM: new music and sound-effect data for the SMB sound engine.

    patch(dst)                      rewrite dst/src/music-data.asm (+ SFX tables in music-engine.asm)
    export(rom, labels, outdir)     decode every song of a ROM to outdir/music/<slot>.mid (both rooms)
    python -m games.smb.music wav <slot> out.wav    preview one of our songs

Every song comes from cleanroom.audio.compose: input is structure only (tempo row,
bars, loop, channel roles, moods, seed); no retail note is read. Kept from the
engine (structure): header layout (length row, data pointer, 8-bit triangle /
square 1 / noise offsets), byte encodings per channel, the 33-entry ground layout
that loops to its 2nd entry, the +8 length-row hurry-up, the frequency table
(tuning: index -> APU period; code and SFX index it with immediates).
New: all note data, the length rows (our tempos), every envelope curve, and the
SFX data tables (1-up, power-up, sprout/vine, swim/stomp, brick, flame).
"""
import os
import re
import sys

import numpy as np

from cleanroom.audio.compose import compose
from cleanroom.audio.notes import Note
from cleanroom.decomp.gen import h32

CPU = 1789773.0
LEN_MULT = (1, 2, 3, 4, 6, 8, 12, 16)        # sixteenths per length index (same shape every row)
ROW_F = (8, 7, 5, 7, 5, 4)                   # frames per sixteenth: rows $00..$28
SEED = 1985_2026


# ------------------------------------------------------------------ asm helpers

def _db_table(text, label):
    lines = text.split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith(label + ":")) + 1
    vals = []
    while i < len(lines):
        l = lines[i].split(";")[0].strip()
        i += 1
        if not l:
            if vals:
                break
            continue
        if not l.startswith(".db"):
            break
        vals += [int(v.strip()[1:], 16) for v in l[3:].split(",") if v.strip().startswith("$")]
    return vals


def _replace_table(text, label, vals):
    """replace the .db rows after `label:` (same count) keeping comments"""
    lines = text.split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith(label + ":")) + 1
    k = 0
    while k < len(vals):
        m = re.match(r"(\s*\.db\s+)([^;]*?)(\s*;.*)?$", lines[i])
        if not m:
            i += 1
            continue
        n = len([v for v in m.group(2).split(",") if v.strip()])
        row = vals[k:k + n]
        assert len(row) == n, f"{label}: table shorter than retail"
        lines[i] = m.group(1) + ", ".join(f"${v:02x}" for v in row) + (m.group(3) or "")
        k += n
        i += 1
    return "\n".join(lines)


def _db(vals, per=16):
    return ["\t.db " + ", ".join(f"${v:02x}" for v in vals[i:i + per]) for i in range(0, len(vals), per)]


# ------------------------------------------------------------------ pitch maps

def pitch_tables(freq):
    """index -> MIDI key (square), from the frequency table bytes (hi, lo pairs)"""
    out = {}
    for idx in range(0, len(freq) - 1, 2):
        p = (freq[idx] << 8) | freq[idx + 1]
        if freq[idx + 1] == 0 or p < 8:
            continue
        f = CPU / (16 * (p + 1))
        out[idx] = 69 + 12 * np.log2(f / 440.0)
    return out


def nearest(ptab, key, maxidx=200):
    """index whose pitch is nearest to key; folds by octaves into the table range"""
    cand = {i: k for i, k in ptab.items() if 2 <= i <= maxidx}
    lo, hi = min(cand.values()), max(cand.values())
    while key < lo - 0.5:
        key += 12
    while key > hi + 0.5:
        key -= 12
    return min(cand, key=lambda i: (abs(cand[i] - key), i))


# ------------------------------------------------------------------ song plan (structure only)

# slot: (length row, bars, roles, moods, seed salt)
AREA = {
    "water":       (1, 8, ["lead", "counter", "bass", "drums"], ["calm", "major"], 1),
    "underground": (3, 4, ["lead"], ["eerie", "minor"], 2),
    "castle":      (0, 6, ["lead", "counter", "bass"], ["tense", "dark"], 3),
    "star":        (4, 2, ["lead", "arp", "bass", "drums"], ["bright", "fast"], 4),
}
EVENT = {
    "death":       (2, 2, ["lead", "counter", "bass"], ["sad", "minor"], 5),
    "gameover":    (1, 3, ["lead", "counter", "bass"], ["sad", "slow"], 16),
    "victory":     (3, 4, ["lead", "counter", "bass"], ["triumphant", "happy"], 7),
    "wincastle":   (1, 3, ["lead", "counter", "bass"], ["heroic", "bright"], 8),
    "endoflevel":  (2, 3, ["lead", "counter", "bass"], ["heroic", "major"], 9),
    "hurry":       (1, 2, ["lead", "bass"], ["tense", "fast"], 10),
}
GROUND_ROW = 3
GROUND_PARTS = {"leadin": 1, "a": 4, "b": 4, "c": 4, "d": 4}
# 33 entries; the engine loops back to entry 2 after the last
GROUND_LAYOUT = (["leadin"] + ["a", "a", "b", "c"] * 2 + ["d", "d", "c", "a"] + ["leadin"] +
                 ["a", "b", "a", "c"] * 2 + ["d", "b", "d", "c"] * 2 + ["a", "d", "c", "leadin"])[:33]


def bpm_of(row):
    return 3600.0 / (4 * ROW_F[row])


def lines_of(song, t0=0, t1=None):
    """{role: [(t16, dur16, key)]} monophonic (highest key per onset), 16th grid"""
    t1 = song.length if t1 is None else t1
    q = song.division // 4
    by = {}
    for n in song.notes:
        if t0 <= n.time < t1:
            role = song.roles[n.ch]
            s = (n.time - t0) // q
            cur = by.setdefault(role, {}).get(s)
            pr = DRUM_PRI.get(n.key, 0) if role == "drums" else n.key
            if cur is None or pr > (DRUM_PRI.get(cur[1], 0) if role == "drums" else cur[1]):
                by[role][s] = (max(1, -(-n.dur // q)), n.key)
    return {r: sorted((s, d, k) for s, (d, k) in m.items()) for r, m in by.items()}


DRUM_PRI = {38: 3, 36: 2, 42: 1, 46: 1}


def split_len(n):
    """sixteenths -> list of length indices summing to n (greedy)"""
    out = []
    while n > 0:
        i = max(j for j, m in enumerate(LEN_MULT) if m <= n)
        out.append(i)
        n -= LEN_MULT[i]
    return out


def events(line, total16, drum=False):
    """[(t, d, key)] -> [(len_idx, key or None)] covering exactly total16 sixteenths"""
    ev, t = [], 0
    line = [x for x in line if x[0] < total16]
    for j, (s, d, k) in enumerate(line):
        if s > t:
            ev += [(i, None) for i in split_len(s - t)]
        nxt = line[j + 1][0] if j + 1 < len(line) else total16
        gap = nxt - s
        snd = gap if drum else min(gap, d)
        parts = split_len(snd)
        ev.append((parts[0], k))
        ev += [(i, None) for i in parts[1:]]
        if gap > snd:
            ev += [(i, None) for i in split_len(gap - snd)]
        t = nxt
    if t < total16:
        ev += [(i, None) for i in split_len(total16 - t)]
    return ev


# ------------------------------------------------------------------ channel encoders

REST = 0x04


def enc_sq2(ev, ptab, tri=False):
    """square 2 / triangle: $80|len when the length changes, then the note (rest = $04;
    never $00 on the triangle: that skips the length reload and stalls the channel)"""
    out, cur = [], None
    for li, key in ev:
        note = REST if key is None else nearest(ptab, key + (12 if tri else 0))
        if li != cur:
            out.append(0x80 | li)
            cur = li
        out.append(note)
    return out


def _lenbits(li):
    return ((li >> 2) & 1) | (((li >> 1) & 1) << 7) | ((li & 1) << 6)


def enc_sq1(ev, ptab):
    out = []
    for li, key in ev:
        note = REST if key is None else nearest(ptab, key, maxidx=62)
        out.append(_lenbits(li) | note)
    return out


def enc_noise(ev):
    beat = {36: 0x20, 38: 0x30, 42: 0x10, 46: 0x10}
    out = []
    for li, key in ev:
        out.append(_lenbits(li) | (beat.get(key, 0x10) if key is not None else 0x02))
    return out


def song_block(song, row, t0, t1, ptab, roles, label, tri_doubles=False):
    """-> (bytes, tri_ofs, sq1_ofs, noise_ofs) for one header"""
    total = (t1 - t0) // (song.division // 4)
    L = lines_of(song, t0, t1)
    sq2 = enc_sq2(events(L.get("lead", []), total), ptab) + [0]
    data, tri_o, sq1_o, noi_o = list(sq2), 0, 0, 0
    sq1_role = next((r for r in ("counter", "arp") if r in roles), None)
    if sq1_role:
        sq1_o = len(data)
        data += enc_sq1(events(L.get(sq1_role, []), total), ptab)
    if "bass" in roles and not tri_doubles:
        tri_o = len(data)
        data += enc_sq2(events(L.get("bass", []), total), ptab, tri=True)
    if "drums" in roles:
        noi_o = len(data)
        bar16 = 16
        data += enc_noise(events(lines_of(song, t0, t0 + song.division * 4).get("drums", []), bar16, drum=True)) + [0]
    assert len(data) <= 256, f"{label}: {len(data)} bytes > 256 (8-bit channel offsets)"
    assert noi_o < 256 and tri_o < 256 and sq1_o < 256
    return data, tri_o, sq1_o, noi_o


def make_song(slot, row, bars, roles, moods, salt):
    bar = 48 * 4
    return compose(bpm=bpm_of(row), length=bars * bar, loop=0 if slot in AREA else None,
                   roles=roles, moods=moods, seed=h32("smb-music", SEED, salt) & 0xFFFF)


# ------------------------------------------------------------------ data generators

def sfx_tables(ptab, rng):
    """new values, retail sizes"""
    def notes_to_idx(keys, maxidx=200):
        return [nearest(ptab, k, maxidx) for k in keys]
    t = {}
    # swim / stomp: square-1 envelope, read last-to-first (14)
    env = np.clip(np.round(np.linspace(13, 1, 14) ** 1.0 + rng.normal(0, 0.6, 14)), 1, 15).astype(int)
    t["SwimStompEnvelopeData"] = [0x90 | int(v) for v in env[::-1]]
    # 1-up: six tones of an upward run (pentatonic, our key), played last entry first
    base = 64 + int(rng.integers(0, 5))
    run = [base + o for o in (0, 3, 5, 7, 10, 12)]
    t["ExtraLifeFreqData"] = notes_to_idx(run)[::-1]
    # power-up grab: 27 + 3 residual, played from the end: a rising zig-zag
    seq, k = [], 60 + int(rng.integers(0, 6))
    for i in range(30):
        k += [4, -2, 5, -3, 3][i % 5]
        seq.append(k)
    t["PowerUpGrabFreqData"] = notes_to_idx(seq)[::-1]
    # sprout / vine (32): rising pairs with a rest after every third tone
    out, k = [], 52 + int(rng.integers(0, 4))
    for i in range(32):
        if i % 4 == 3:
            out.append(REST)
        else:
            out.append(nearest(ptab, k))
            k += 1 + (i % 2)
    t["PUp_VGrow_FreqData"] = out
    # brick shatter: noise periods (16)
    t["BrickShatterFreqData"] = [int(v) for v in rng.permutation(16)]
    return t


def env_tables(rng):
    def curve(n, top, shape, base=0x90, lo=0):
        x = np.linspace(0, 1, n)
        v = lo + (top - lo) * x ** shape
        return [base | int(np.clip(round(a), 0, 15)) for a in v]
    return {
        "EndOfCastleMusicEnvData": curve(4, 11, 0.7),
        "AreaMusicEnvData": curve(8, 9, 0.55),
        "WaterEventMusEnvData": [0x90] + curve(36, 7, 0.4, lo=2) + curve(3, 5, 1.0, lo=3)[::-1],
        "BowserFlameEnvData": [0x10 | int(np.clip(round(14 + 8 * np.sin(i / 5.0) * np.exp(-i / 30)), 2, 15))
                               for i in range(32)],
        "BrickShatterEnvData": [0x10 | int(np.clip(round(15 - i * 0.6 + rng.normal(0, 0.8)), 3, 15))
                                for i in range(16)],
    }


def build(freq):
    """-> (asm text for music-data.asm, sfx tables, stats)"""
    ptab = pitch_tables(freq)
    rng = np.random.default_rng(SEED)
    blocks, headers = [], {}          # name -> (row, label, tri, sq1, noise)

    def add(name, data, row, tri, sq1, noi):
        lab = f"Mus_{name}_Data"
        blocks.append((lab, data))
        headers[name] = (row, lab, tri, sq1, noi)

    # ground: one composition, cut into parts
    bars = sum(GROUND_PARTS.values())
    gsong = compose(bpm=bpm_of(GROUND_ROW), length=bars * 192, loop=192, roles=["lead", "counter", "bass", "drums"],
                    moods=["heroic", "happy"], seed=h32("smb-music", SEED, 0) & 0xFFFF)
    t = 0
    for part, nb in GROUND_PARTS.items():
        d, tri, sq1, noi = song_block(gsong, GROUND_ROW, t, t + nb * 192, ptab, ["lead", "counter", "bass", "drums"],
                                      "ground_" + part)
        add("ground_" + part, d, GROUND_ROW, tri, sq1, noi)
        t += nb * 192
    songs = {"ground": gsong}
    for slot, (row, nb, roles, moods, salt) in list(AREA.items()) + list(EVENT.items()):
        s = make_song(slot, row, nb, roles, moods, salt)
        songs[slot] = s
        d, tri, sq1, noi = song_block(s, row, 0, s.length, ptab, roles, slot, tri_doubles=(slot == "underground"))
        add(slot, d, row, tri, sq1, noi)
    blocks.append(("SilenceData", [0]))
    headers["silence"] = (1, "SilenceData", 0, 0, 0)

    order = ["death", "gameover", "victory", "wincastle", "gameover", "endoflevel", "hurry", "silence",
             "ground_a", "water", "underground", "castle", "star", "ground_leadin", "star", "silence"]
    order += ["ground_" + p for p in GROUND_LAYOUT]
    hnames = list(dict.fromkeys(order))
    asm = ["; music header offsets (new data, see games/smb/music.py)", "", "MusicHeaderData:"]
    asm += ["\t.db " + ", ".join(f"Hdr_{n}-MHD" for n in order[i:i + 8]) for i in range(0, len(order), 8)]
    asm += ["", "; header: length row, data address, triangle / square 1 / noise offsets"]
    for n in hnames:
        row, lab, tri, sq1, noi = headers[n]
        asm.append(f"Hdr_{n}:")
        asm.append(f"\t.db ${row * 8:02x}, <{lab}, >{lab}, ${tri:02x}, ${sq1:02x}, ${noi:02x}")
    asm += ["", "; song data: square 2 (ends $00), square 1, triangle, noise (loops at $00)"]
    nbytes = 0
    for lab, data in blocks:
        asm.append(f"{lab}:")
        asm += _db(data)
        nbytes += len(data)
    asm += ["", "FreqRegLookupTbl:"] + _db(freq, 8)
    lens = [min(255, f * m) for f in ROW_F for m in LEN_MULT]
    asm += ["", "MusicLengthLookupTbl:"] + _db(lens, 8)
    envs = env_tables(rng)
    for lab, vals in envs.items():
        asm += ["", lab + ":"] + _db(vals, 8)
    hdr_bytes = len(order) + 6 * len(hnames)
    stats = {"note_bytes": nbytes, "header_bytes": hdr_bytes,
             "table_bytes": len(freq) + len(lens) + sum(len(v) for v in envs.values()),
             "headers": len(hnames)}
    return "\n".join(asm) + "\n", sfx_tables(ptab, rng), stats, songs


def data_size(text):
    n = 0
    for l in text.split("\n"):
        l = l.split(";")[0].strip()
        if l.startswith(".db"):
            n += len([v for v in l[3:].split(",") if v.strip()])
    return n


def patch(dst):
    md = os.path.join(dst, "src", "music-data.asm")
    me = os.path.join(dst, "src", "music-engine.asm")
    old = open(md, encoding="latin-1").read()
    freq = _db_table(old, "FreqRegLookupTbl")
    budget = data_size(old)
    text, sfx, st, _ = build(freq)
    used = data_size(text)
    assert used <= budget, f"music data {used} B > retail budget {budget} B"
    open(md, "w", encoding="latin-1", newline="\n").write(text)
    eng = open(me, encoding="latin-1").read()
    res = _db_table(eng, "PowerUpGrabFreqData")
    for lab, vals in sfx.items():
        n = len(_db_table(eng, lab))
        if lab == "PowerUpGrabFreqData":
            n = len(res)           # 27 + the 3 'residual' bytes that follow in the same run
        eng = _replace_table(eng, lab, vals[:n] if len(vals) >= n else vals + vals[:n - len(vals)])
    open(me, "w", encoding="latin-1", newline="\n").write(eng)
    return (f"{st['headers']} headers, {st['note_bytes']} B notes + {st['header_bytes']} B headers + "
            f"{st['table_bytes']} B tables = {used}/{budget} B; {len(sfx)} sfx tables")


# ------------------------------------------------------------------ decoder (both rooms)

def _prg(rom, addr):
    return 16 + (addr - 0x8000)


def decode_header(rom, lab, hofs, slot_bits, adder=0, max_frames=30000):
    """simulate the engine for one header -> [Note] (time in frames)"""
    def rd(a):
        return rom[_prg(rom, a)]
    mhd = lab["MusicHeaderData"]
    h = mhd + hofs
    row, ptr = rd(h), rd(h + 1) | (rd(h + 2) << 8)
    o_tri, o_sq1, o_noi = rd(h + 3), rd(h + 4), rd(h + 5)
    lent = lab["MusicLengthLookupTbl"]
    freq = [rd(lab["FreqRegLookupTbl"] + i) for i in range(102)]
    ptab = pitch_tables(freq)

    def length(i):
        return rd(lent + (i & 7) + row + adder) or 256

    def alt(b):
        return length(((b & 1) << 2) | ((b >> 6) & 3))

    def byte(o):
        return rd(ptr + (o & 0xFF))
    notes = []
    s2, s1, tr, nz = 0, o_sq1, o_tri, o_noi
    c2 = c1 = ct = cn = 1
    l2 = lt = 1
    noise_on = bool(slot_bits & 0xF3)
    for f in range(max_frames):
        c2 -= 1
        if c2 == 0:
            b = byte(s2)
            s2 += 1
            if b == 0:
                return notes
            if b & 0x80:
                l2 = length(b)
                b = byte(s2)
                s2 += 1
            if b in ptab:
                notes.append(Note(f, 0, int(round(ptab[b])), 100, l2))
            c2 = l2
        if o_sq1:
            c1 -= 1
            if c1 == 0:
                b = byte(s1)
                s1 += 1
                while b == 0:
                    b = byte(s1)
                    s1 += 1
                c1 = alt(b)
                n = b & 0x3E
                if n in ptab:
                    notes.append(Note(f, 1, int(round(ptab[n])), 80, c1))
        ct = (ct - 1) & 0xFF
        if ct == 0:
            b = byte(tr)
            tr += 1
            if b & 0x80:
                lt = length(b)
                b = byte(tr)
                tr += 1
            if b:
                ct = lt
                if b in ptab:
                    notes.append(Note(f, 2, int(round(ptab[b])) - 12, 90, lt))
        if noise_on:
            cn -= 1
            if cn == 0:
                for _ in range(2):
                    b = byte(nz)
                    nz += 1
                    if b:
                        break
                    nz = o_noi
                cn = alt(b)
                v = b & 0x3E
                k = 38 if v == 0x30 else 36 if v == 0x20 else 42 if v & 0x10 else None
                if k:
                    notes.append(Note(f, 9, k, 70, 4))
    return notes


SLOTS_EVENT = ["death", "gameover", "victory", "wincastle", None, "endoflevel", "hurry", None]
SLOTS_AREA = [None, "water", "underground", "castle", "cloud_star", "pipe_intro", None, None]
AREA_BITS = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]


def export(rom, labels, outdir):
    """one MIDI per slot (ground = its 33-entry layout played through)"""
    from cleanroom.audio import midi
    os.makedirs(os.path.join(outdir, "music"), exist_ok=True)
    mhd = labels["MusicHeaderData"]
    ofs = [rom[_prg(rom, mhd + i)] for i in range(16 + 33)]
    done = {}

    def write(name, notes):
        if not notes:
            return
        data = midi.write(notes, division=60, tempo=1_000_000)
        open(os.path.join(outdir, "music", name + ".mid"), "wb").write(data)
        done[name] = len(notes)
    for i, s in enumerate(SLOTS_EVENT):
        if s:
            write(s, decode_header(rom, labels, ofs[i], 0))
    for i, s in enumerate(SLOTS_AREA):
        if s:
            write(s, decode_header(rom, labels, ofs[8 + i], AREA_BITS[i]))
    allg, t = [], 0
    for e in range(16, 16 + 33):
        ns = decode_header(rom, labels, ofs[e], 0x01)
        allg += [n._replace(time=n.time + t) for n in ns]
        t += (max((n.time + n.dur for n in ns if n.ch == 0), default=0))
    write("ground", allg)
    return done


def retail_labels(scratch):
    """dirty room: assemble the dirty tree with asm6f -n for label addresses"""
    import shutil
    import subprocess
    from games.smb.generate import labels
    src = "D:/n64work/smb/dirty/smb1"
    d = os.path.join(scratch, "smb1_retail")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(src, d, ignore=shutil.ignore_patterns(".git", "bin"))
    os.makedirs(os.path.join(d, "bin"))
    subprocess.run(["D:/n64work/smb/tools/asm6f.exe", "smb1.asm", "-q", "-n", "bin/r.nes"], cwd=d, check=True)
    return labels(os.path.join(d, "bin", "r.nes"))


def main(argv):
    if argv[1:2] == ["wav"]:
        import wave
        from cleanroom.audio.compose import to_pcm
        old = open("D:/n64work/smb/ref/smb1/src/music-data.asm", encoding="latin-1").read()
        _, _, _, songs = build(_db_table(old, "FreqRegLookupTbl"))
        pcm = (to_pcm(songs[argv[2]]) * 32767).astype("<i2").tobytes()
        with wave.open(argv[3], "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(32000), w.writeframes(pcm)
        print(argv[3])
    elif argv[1:2] == ["export"]:          # export <rom> <nl base> <outdir> | export retail <scratch> <outdir>
        if argv[2] == "retail":
            lab = retail_labels(argv[3])
            rom = open("D:/n64work/smb/dirty/baserom.nes", "rb").read()
            out = argv[4]
        else:
            from games.smb.generate import labels
            rom, lab, out = open(argv[2], "rb").read(), labels(argv[3]), argv[4]
        print(export(rom, lab, out))


if __name__ == "__main__":
    main(sys.argv)
