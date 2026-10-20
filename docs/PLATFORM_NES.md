# NES platform notes (first used for Super Mario Bros.)

## Formats (code in `cleanroom/nes/`)
- **iNES**: 16-byte header, PRG (n x 16 KB), CHR (n x 8 KB). Dumps differ in header junk: compare PRG / CHR
  sha1, not the file (`chr.split_ines`).
- **CHR tile**: 16 bytes, 8 rows of bit-plane 0 then 8 rows of plane 1, MSB = left pixel (`chr.decode/encode`).
  Sprites use pattern table $0000, backgrounds $1000 (game dependent: PPUCTRL).
- **Palettes** live in PRG as tables of 2C02 master ids (0-63); colour 0 of every palette is the backdrop.
  Index *roles* (which slot is outline / highlight) are fixed by the art, the hues are free.
- **Sound**: APU register writes from note / period tables in PRG: sequences, kept. DPCM samples would be
  assets (SMB has none).
- No compression in SMB. Games with CHR-RAM store tiles compressed inside PRG: add the codec there.

## Traps
- **CHR can hold data**: SMB streams its title-screen nametable script out of CHR $1EC0-$1FFF through the
  PPU. Find such reads (`PPU_DATA` loops with a CHR address) before treating the whole 8 KB as pixels.
- **Tiles are shared between pictures** (walk frames share heads, bush = cloud with another palette, the
  same tile mirrored). Draw whole pictures and cut the owned tiles (`atlas.owners`): first listing wins.
- **Graphics tables lie about layout**: enemies are stored facing right; multi-part enemies (Bowser) are two
  objects, some pictures (shells, springboard) are flipped or reordered by code. Check in the running game.
- **Uniform fill tiles** are reused inside large pictures (pipe shaft, cloud centre): designs must agree with
  them.
- **Colour cycling**: one palette slot is rewritten every few frames (coins, ? blocks). Marks drawn in the
  neighbouring colour vanish during part of the cycle: use the outline colour.
- **Convergent drawings**: hand-drawing a 16x16 figure in its exact silhouette lands on the retail pixels
  surprisingly often (boots, a star with two eyes, an outlined hill). The taint scan is what catches it:
  redraw until it passes, do not relax the rule.
- asm6f: `asm6f.exe smb1.asm -q out.nes` in the source dir; build it from `asm6f.c` with zig cc.
- Edit Python with the Edit tool; `\n` and `\x1a` inside bash heredocs get expanded.

## Taint rules (`cleanroom/nes/taint.py`, `games/smb/taint_report.py`)
T1 raw 16-byte windows of retail CHR (>= 6 distinct byte values) anywhere in the ROM, site or repo;
T2 decoded tiles equal to any retail tile in any slot or flip; T3 per-picture agreement beyond the kept facts;
T4 retail title-script picture rows; T5 palette rows; T6 PRG may differ only in palette tables.
Coincidences that are allowed, because the kept facts already imply them: uniform tiles, tiles and pixel rows
with a single non-zero colour (they are the silhouette), own glyph tiles with <= 10 set pixels, grey-only
palette rows.

## Commands
```
python -m games.smb.extract_spec D:/n64work/smb/dirty/baserom.nes     # dirty: spec
sh games/smb/dump.sh '^enemy_koopa' 6                                 # ASCII of pictures to draw over
python -m games.smb.sheet png out.png '^player'                       # contact sheet of our art
python -m games.smb.generate                                          # CHR + palettes + assemble
python -m games.smb.taint_report <retail.nes> <clean.nes> <site> . -v
python ports/ejs/cdp_shot.py out --url "http://localhost:8481/index.html?autostart=1" \
       --script "3:shot,4:Enter:0.2,8:ArrowRight:6,9:x:0.5,11:shot" --webgl
```
Web route: clean ROM + EmulatorJS (`ports/ejs`, npm `@emulatorjs/emulatorjs` + `@emulatorjs/core-fceumm`, 4.2.3).
