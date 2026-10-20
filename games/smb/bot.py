"""Headless reachability bot: beam search over short input segments with save states (cynes).

    python -m games.smb.bot <dev rom> [--beam 10] [--out dir]    one level from the dev ROM's start
    python -m games.smb.bot all [work dir] [--jobs 3]            builds a dev ROM per main-path level, runs them

A level counts as cleared when the player grabs the flagpole, walks into an exit pipe, the area changes,
or the castle axe ends the level. Prints one line per level; writes <out>/<W-L>.png (frames along the path).
"""
import os
import subprocess
import sys
import time

import numpy as np

R, L_, D, U, A, B, ST = 0x80, 0x40, 0x20, 0x10, 0x01, 0x02, 0x08     # set from cynes below
SEG = 8


def _keys():
    import cynes
    global R, L_, D, U, A, B, ST
    R, L_, D, U = cynes.NES_INPUT_RIGHT, cynes.NES_INPUT_LEFT, cynes.NES_INPUT_DOWN, cynes.NES_INPUT_UP
    A, B, ST = cynes.NES_INPUT_A, cynes.NES_INPUT_B, cynes.NES_INPUT_START


def actions():
    return [
        [R | B] * SEG,
        [R | B | A] * SEG,
        [R | B | A] * 3 + [R | B] * (SEG - 3),
        [0] * SEG,
        [L_ | B] * SEG,
        [R] * SEG,
        [A] * SEG,
        [R | A] * 2 + [R] * (SEG - 2),          # swim stroke
        [L_ | A] * 2 + [L_] * (SEG - 2),
        [R | B | A] * SEG + [R | B | A] * SEG,  # long jump (two segments)
    ]


def ram(n):
    return dict(x=n[0x6D] * 256 + n[0x86], y=n[0xCE] + 256 * n[0xB5], ges=n[0x0E], oper=n[0x770],
                area=n[0x750], level=n[0x75C], world=n[0x75F], lives=n[0x75A], size=n[0x754])


def boot(rom):
    from cynes import NES
    n = NES(rom)
    n.step(120)
    n.controller = ST
    n.step(10)
    n.controller = 0
    for _ in range(400):
        n.step(4)
        if n[0x770] == 1 and n[0x0E] == 8:
            break
    return n


def play(rom, beam=int(os.environ.get("SMB_BOT_BEAM", 10)), max_iter=900, stall=60, log=None):
    _keys()
    n = boot(rom)
    s0 = ram(n)
    start = (s0["area"], s0["level"], s0["world"])
    lives0 = s0["lives"]
    acts = actions()
    pool = [(s0["x"], n.save(), [], s0)]
    best_x, best_it, frames = s0["x"], 0, 0
    for it in range(max_iter):
        cand = {}
        for x0, st, path, _ in pool:
            for ai, act in enumerate(acts):
                n.load(st)
                done = False
                for k in act:
                    n.controller = k
                    n.step()
                frames += len(act)
                m = ram(n)
                won = (m["ges"] in (2, 3, 4, 5) or m["oper"] == 2 or (m["level"], m["world"]) != start[1:])
                if m["ges"] in (6, 11) or m["lives"] != lives0 or (m["y"] >= 0x1D0 and not won):
                    continue
                if won:
                    return dict(ok=True, x=m["x"], it=it, frames=frames, path=path + [ai], how=m)
                key = (m["x"] // 6, m["y"] // 12, m["size"])
                score = m["x"] + 2 * m["size"]
                if key not in cand or cand[key][0] < score:
                    cand[key] = (score, n.save(), path + [ai], m)
        if not cand:
            return dict(ok=False, x=best_x, it=it, frames=frames, why="all dead", path=pool[0][2], state=pool[0][1])
        pool = sorted(cand.values(), key=lambda c: -c[0])[:beam]
        if pool[0][0] > best_x + 4:
            best_x, best_it = pool[0][0], it
        elif it - best_it > stall:
            return dict(ok=False, x=best_x, it=it, frames=frames, why="stuck", path=pool[0][2], state=pool[0][1])
        if log and it % 50 == 0:
            print(f"    it {it} best x {best_x}", file=log, flush=True)
    return dict(ok=False, x=best_x, it=max_iter, frames=frames, why="out of time")


def replay(rom, path, every=90):
    """frames along a path (for a contact sheet)"""
    _keys()
    n = boot(rom)
    acts, shots, f = actions(), [], 0
    frame = None
    for ai in path:
        for k in acts[ai]:
            n.controller = k
            frame = n.step()
            f += 1
            if f % every == 0:
                shots.append(frame.copy())
    for _ in range(60):
        n.controller = 0
        frame = n.step()
    shots.append(frame.copy())
    return shots


def sheet(shots, cols=6, scale=1):
    h, w = shots[0].shape[:2]
    while len(shots) % cols:
        shots.append(np.zeros_like(shots[0]))
    rows = [np.concatenate(shots[i:i + cols], axis=1) for i in range(0, len(shots), cols)]
    return np.concatenate(rows, axis=0)


def main_path():
    """(world, level, area index) for every main-path area start (intro areas are skipped: they play themselves)"""
    from games.smb.levelgen import WORLD_AREAS
    out = []
    for w, al in enumerate(WORLD_AREAS):
        lvl = 0
        for ai, p in enumerate(al):
            if p == 0x29:                         # pipe intro: same level number as the next area
                continue
            out.append((w, lvl, ai))
            lvl += 1
    return out


def build_one(work, w, l, a, outdir):
    rom = os.path.join(outdir, f"dev_{w + 1}-{l + 1}.nes")
    r = subprocess.run([sys.executable, "-m", "games.smb.generate", work, f"dev={w},{l},{a}"], capture_output=True,
                       text=True, env=dict(os.environ, SMB_DEV_OUT=rom))
    if r.returncode:
        print("build failed", r.stdout[-300:], r.stderr[-500:])
    return rom


def run_one(args):
    work, w, l, a, outdir = args
    rom = os.path.join(outdir, f"dev_{w + 1}-{l + 1}.nes")
    if not os.path.exists(rom):
        return (w, l, a, dict(ok=False, why="no rom"))
    t = time.time()
    res = play(rom)
    res["secs"] = round(time.time() - t)
    if res.get("state") is not None:
        from cleanroom.gfx import png
        n = boot(rom)
        n.load(res.pop("state"))
        png.write(os.path.join(outdir, f"{w + 1}-{l + 1}_stuck.png"), n.step(1))
    if res.get("path"):
        import json
        json.dump({"ok": res["ok"], "path": res["path"]}, open(os.path.join(outdir, f"{w + 1}-{l + 1}.json"), "w"))
        from cleanroom.gfx import png
        png.write(os.path.join(outdir, f"{w + 1}-{l + 1}.png"), sheet(replay(rom, res["path"], every=150)))
    return (w, l, a, res)


def demo_runs(path, limit=21, frames=900):
    """bot path -> <= limit (buttons, frames<=255) runs for the attract demo (DemoActionData/DemoTimingData)"""
    _keys()
    acts = actions()
    seq = [k for ai in path for k in acts[ai]][:frames]
    runs = []
    for k in seq:
        if runs and runs[-1][0] == k:
            runs[-1][1] += 1
        else:
            runs.append([k, 1])
    while len(runs) > limit:                      # fold the shortest run into its longer neighbour
        i = min(range(len(runs)), key=lambda j: runs[j][1])
        j = i - 1 if i > 0 and (i == len(runs) - 1 or runs[i - 1][1] >= runs[i + 1][1]) else i + 1
        runs[j][1] += runs[i][1]
        del runs[i]
        k = 0
        while k + 1 < len(runs):
            if runs[k][0] == runs[k + 1][0]:
                runs[k][1] += runs.pop(k + 1)[1]
            else:
                k += 1
    out = []
    for b, n in runs:
        while n > 0:
            out.append([b, min(n, 255)])
            n -= 255
    return out[:limit]


def main(argv):
    if argv[1] == "demo":                         # python -m games.smb.bot demo <1-1 path json> -> spec/demo.json
        import json
        runs = demo_runs(json.load(open(argv[2]))["path"])
        json.dump(runs, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec", "demo.json"), "w"))
        print(len(runs), "demo runs", sum(n for _, n in runs), "frames")
        return 0
    if argv[1] == "all":
        work = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "D:/n64work/smb"
        jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 3
        outdir = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(work, "bot")
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
        os.makedirs(outdir, exist_ok=True)
        todo = [(work, w, l, a, outdir) for w, l, a in main_path() if not only or f"{w + 1}-{l + 1}" in only]
        for t in todo:
            if os.path.exists(os.path.join(outdir, f"dev_{t[1] + 1}-{t[2] + 1}.nes")):
                os.remove(os.path.join(outdir, f"dev_{t[1] + 1}-{t[2] + 1}.nes"))
            build_one(*t)
        from multiprocessing import Pool
        ok = 0
        with Pool(jobs) as p:
            for w, l, a, r in p.imap_unordered(run_one, todo):
                ok += bool(r.get("ok"))
                print(f"{w + 1}-{l + 1} (area {a}): {'CLEAR' if r.get('ok') else 'FAIL ' + r.get('why', '')} "
                      f"x {r.get('x')} it {r.get('it')} {r.get('secs', '?')}s", flush=True)
        print(f"bot: {ok}/{len(todo)} levels cleared")
        return 0 if ok == len(todo) else 1
    rom = argv[1]
    r = play(rom, beam=int(argv[argv.index("--beam") + 1]) if "--beam" in argv else 10, log=sys.stdout)
    print({k: v for k, v in r.items() if k != "path"})
    if "--out" in argv and r.get("path"):
        from cleanroom.gfx import png
        png.write(argv[argv.index("--out") + 1], sheet(replay(rom, r["path"], every=120)))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
