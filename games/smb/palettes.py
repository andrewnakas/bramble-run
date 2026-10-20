"""Our palette picks (NES master ids), chosen from colour-name briefs.

Index roles (which slot is highlight / body / outline) follow the code's
attribute tables; the hues are our choice. Rows are written over the
disassembly's .db tables by generate.py (same byte counts).
"""
SKY = 0x21          # clear sky blue
K = 0x0F            # black

# label -> replacement rows (hex strings exactly as bytes; header/terminator rows included)
TABLES = {
    "BackgroundColors": [[SKY, SKY, K, K], [K, SKY, K, K]],
    "PlayerColors": [
        [SKY, 0x16, 0x36, 0x07],      # red cap + overalls, peach skin, dark brown hair/boots
        [SKY, 0x2A, 0x36, 0x07],      # brother: green
        [SKY, 0x30, 0x36, 0x26],      # ember: white hood, coral shirt
    ],
    "ColorRotatePalette": [[0x28, 0x28, 0x28, 0x38, 0x30, 0x38]],      # gold that glints to white
    "Palette3Data": [[K, 0x08, 0x11, K], [K, 0x08, 0x17, K], [K, 0x08, 0x17, 0x1C], [K, 0x08, 0x07, 0x10]],
    "WaterPaletteData": [
        [0x3F, 0x00, 0x20],
        [K, 0x14, 0x11, 0x24],        # coral: magenta, water blue (same as the water fill), pink
        [K, 0x2A, 0x1A, K],           # sea rock: greens
        [K, 0x30, 0x11, K],           # foam / water
        [K, 0x28, 0x11, K],           # coins on water blue
        [SKY, 0x16, 0x36, 0x07],
        [K, 0x10, 0x30, 0x37],        # grey swimmers
        [K, 0x16, 0x30, 0x37],        # red swimmers
        [K, K, 0x30, 0x10],           # squid: black, white, grey
        [0x00],
    ],
    "GroundPaletteData": [
        [0x3F, 0x00, 0x20],
        [K, 0x2A, 0x1A, K],           # leaves: light green, green
        [K, 0x37, 0x17, K],           # brick: sand highlight, brown
        [K, 0x30, 0x11, K],           # cloud white, blue shade / water
        [K, 0x28, 0x17, K],           # gold block
        [K, 0x16, 0x36, 0x07],
        [K, 0x1A, 0x30, 0x28],        # green shell, white, yellow skin
        [K, 0x16, 0x30, 0x37],        # red cap, white, cream
        [K, K, 0x37, 0x17],           # walker: black, cream, brown
        [0x00],
    ],
    "UndergroundPaletteData": [
        [0x3F, 0x00, 0x20],
        [K, 0x2A, 0x1A, 0x0A],
        [K, 0x2C, 0x1C, K],           # cave brick: cyan, teal
        [K, 0x30, 0x11, 0x1C],
        [K, 0x28, 0x17, 0x1C],
        [K, 0x16, 0x36, 0x07],
        [K, 0x1C, 0x37, 0x17],
        [K, 0x16, 0x30, 0x37],
        [K, 0x0C, 0x2C, 0x1C],        # cave walker: teal
        [0x00],
    ],
    "CastlePaletteData": [
        [0x3F, 0x00, 0x20],
        [K, 0x30, 0x10, 0x00],        # stone: white, grey, dark grey
        [K, 0x30, 0x10, 0x00],
        [K, 0x30, 0x27, 0x00],        # lava: orange
        [K, 0x28, 0x17, 0x00],
        [K, 0x16, 0x36, 0x07],
        [K, 0x1C, 0x37, 0x17],
        [K, 0x16, 0x30, 0x37],
        [K, 0x00, 0x30, 0x10],
        [0x00],
    ],
    "DaySnowPaletteData": [[0x3F, 0x00, 0x04], [SKY, 0x30, 0x00, 0x10], [0x00]],
    "NightSnowPaletteData": [[0x3F, 0x00, 0x04], [K, 0x30, 0x00, 0x10], [0x00]],
    "MushroomPaletteData": [[0x3F, 0x00, 0x04], [SKY, 0x28, 0x16, K], [0x00]],
    "BowserPaletteData": [[0x3F, 0x14, 0x04], [K, 0x1A, 0x30, 0x28], [0x00]],
}

# preview palettes for sheets / poster (ground area)
BG = [TABLES["GroundPaletteData"][i][:] for i in (1, 2, 3, 4)]
SPR = [TABLES["GroundPaletteData"][i][:] for i in (5, 6, 7, 8)]
for row in BG + SPR:
    row[0] = SKY
