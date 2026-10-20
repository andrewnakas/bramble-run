"""Assemble the web site: EmulatorJS runtime + FCEUmm core + our page + the clean ROM.

    python ports/ejs/make_site.py <site dir> <emulatorjs package dir> <core package dir> <rom> [<rom> ...]

Refuses any ROM whose SHA1 is a retail one (never publish retail data).
"""
import hashlib
import os
import shutil
import sys

RETAIL_SHA1 = ("ea343f4e445a9050d4b4fbac2c77d0693b1d0922",      # Super Mario Bros. (World), clean header
               "33d23c2f2cfa4c9efec87f7bc1321ce3ce6c89bd")      # same, common dump header
RETAIL_PARTS = ("394badaf0b0bdd0ea279a1bca89a9d9ddc00b1b5",)    # retail CHR
HERE = os.path.dirname(os.path.abspath(__file__))

NOTICE = """# Bramble Run: credits and third-party notices

Bramble Run is an original platformer built on the **smb1 disassembly** (doppelganger's community disassembly, as
maintained at https://github.com/Xkeeper0/smb1). The program in `bramblerun.nes` is assembled from that source;
every stage layout, tile, palette, tune, sound effect and line of text was generated for this project. No original
game file is needed or included. Clean-room pipeline: https://github.com/andrewnakas/smb-cleanroom (MIT).

## Third-party software in this site

| Component | Files | Licence | Source |
|---|---|---|---|
| EmulatorJS 4.2.3 | `data/` (loader, emulator, css, localization, 7z/zip extractors) | GPL-3.0 (`data/LICENSE.EmulatorJS`) | https://github.com/EmulatorJS/EmulatorJS |
| libretro FCEUmm core, built by the EmulatorJS project | `data/cores/fceumm-*.data` | GPL-2.0 | https://github.com/libretro/libretro-fceumm |
| RetroArch (libretro frontend linked into the core by EmulatorJS) | same files | GPL-3.0 | https://github.com/EmulatorJS/RetroArch |
| nipplejs (touch joystick, in EmulatorJS) | `data/src/nipplejs.js` | MIT | https://github.com/yoannmoinet/nipplejs |
| socket.io client (in EmulatorJS) | `data/src/socket.io.min.js` | MIT | https://github.com/socketio/socket.io |
"""
ROM_NAMES = {"smb.nes": "bramblerun.nes"}
DROP = ["compression/libunrar.js", "compression/libunrar.wasm"]


def main(argv):
    site, ejs, core, roms = argv[1], argv[2], argv[3], argv[4:]
    blobs = []
    for r in roms:
        data = open(r, "rb").read()
        if hashlib.sha1(data).hexdigest() in RETAIL_SHA1:
            sys.exit(f"refusing: {r} is a retail ROM")
        if hashlib.sha1(data[-8192:]).hexdigest() in RETAIL_PARTS:
            sys.exit(f"refusing: {r} carries the retail CHR")
        blobs.append((ROM_NAMES.get(os.path.basename(r), os.path.basename(r)), data))
    if os.path.exists(site):
        for n in os.listdir(site):
            if n == ".git":
                continue
            p = os.path.join(site, n)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(site, exist_ok=True)
    shutil.copytree(os.path.join(ejs, "data"), os.path.join(site, "data"), dirs_exist_ok=True)
    shutil.copyfile(os.path.join(ejs, "LICENSE"), os.path.join(site, "data", "LICENSE.EmulatorJS"))
    for rel in DROP:                                   # the ROM is not an archive: no unrar
        p = os.path.join(site, "data", rel)
        if os.path.exists(p):
            os.remove(p)
    cores = os.path.join(site, "data", "cores")
    os.makedirs(os.path.join(cores, "reports"), exist_ok=True)
    for n in os.listdir(core):
        if n.endswith(".data") and "thread" not in n:
            shutil.copyfile(os.path.join(core, n), os.path.join(cores, n))
    for n in os.listdir(os.path.join(core, "reports")):
        shutil.copyfile(os.path.join(core, "reports", n), os.path.join(cores, "reports", n))
    shutil.copyfile(os.path.join(HERE, "index.html"), os.path.join(site, "index.html"))
    for name, data in blobs:
        open(os.path.join(site, name), "wb").write(data)
    open(os.path.join(site, "THIRD_PARTY.md"), "w", encoding="utf-8", newline="\n").write(NOTICE)
    open(os.path.join(site, ".nojekyll"), "w").close()
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(site) for f in fs)
    print(f"site: {site} ({total // 1024} KB), roms " + ", ".join(f"{n} {hashlib.sha1(d).hexdigest()[:10]}" for n, d in blobs))


if __name__ == "__main__":
    main(sys.argv)
