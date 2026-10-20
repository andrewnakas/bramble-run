# Bramble Run: credits and third-party notices

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
