"""DIRTY ROOM: structure facts of the retail areas -> games/smb/spec/areas.json.

    python -m games.smb.extract_levels [disassembly dir = D:/n64work/smb/ref/smb1]

Kept per area (structure + gameplay anchors only, owner bar 2026-10-19):
  kind, header timer / entrance control / cloud flag, length in pages,
  portals = groups of area-pointer entries (destination area, world filter, entry page) and how they are used
  (vertical pipe, side exit pipe, vine, cloud exit) -- the warps the code follows.
Not kept: any object or enemy placement, shapes, scenery, enemy choice.
"""
import json
import os
import sys

from games.smb import levels as L

HERE = os.path.dirname(os.path.abspath(__file__))


def ptr_label(p):
    kind = L.AREA_KINDS[(p >> 5) & 3]
    return f"{kind}Area{(p & 31) + 1}"


def main(src):
    a, e = L.load_dir(src)
    out = {}
    for lab in L.area_labels():
        hdr, objs = L.decode_objects(a["L_" + lab])
        ens, links = L.decode_enemies(e["E_" + lab])
        kind = lab.split("Area")[0]
        groups = {}
        for p, c, ptr, w, ep in links:
            groups.setdefault((p, c), []).append({"dest": ptr_label(ptr), "ptr": ptr & 0x7F, "world": w, "page": ep})
        portals = []
        for (p, c), ent in sorted(groups.items()):
            portals.append({"page": p, "entries": ent})
        out[lab] = {"kind": kind, "timer": hdr["timer"], "entrance": hdr["entrance"],
                    "cloud": hdr["style"] == 3, "pages": max([o[0] for o in objs] + [0]) + 1,
                    "portals": portals}
    # how each portal is used: decided by source / destination type (code behaviour, not placement)
    for lab, s in out.items():
        for po in s["portals"]:
            d = out[po["entries"][0]["dest"]]
            if s["cloud"]:
                po["use"] = "cloud_exit"
            elif d["cloud"]:
                po["use"] = "vine"
            elif lab in ("UndergroundArea3",) or s["kind"] == "Water" or (
                    s["kind"] == "Underground" and d["kind"] == "Ground"):
                po["use"] = "side_pipe"
            else:
                po["use"] = "down_pipe"
    json.dump(out, open(os.path.join(HERE, "spec", "areas.json"), "w"), indent=1)
    n = sum(len(s["portals"]) for s in out.values())
    print(f"areas.json: {len(out)} areas, {n} portals")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "D:/n64work/smb/ref/smb1")
