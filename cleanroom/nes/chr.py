"""NES 2bpp planar tiles (CHR), iNES container, master palette and sheets.

A tile is 16 bytes: 8 rows of bit-plane 0, then 8 rows of bit-plane 1
(MSB = leftmost pixel). Pixel value = plane0 | plane1 << 1 (0..3).
"""
import numpy as np

# 2C02 master palette (a common RGB approximation; previews only, the emulator has its own)
_PAL = """
626262 001FB2 2404C8 5200B2 730076 800024 730B00 522800 244400 005700 005C00 005324 003C76 000000 000000 000000
ABABAB 0D57FF 4B30FF 8A13FF BC08D6 D21269 C72E00 9D5400 607B00 209800 00A300 009942 007DB4 000000 000000 000000
FFFFFF 53AEFF 9085FF D365FF FF57FF FF5DCF FF7757 FA9E00 BDC700 7AE700 43F611 26EF7E 2CD5F6 4E4E4E 000000 000000
FFFFFF B6E1FF CED1FF E9C3FF FFBCFF FFBDF4 FFC6C3 FFD59A E9E681 CEF481 B6FB9A A9FAC3 A9F0F4 B8B8B8 000000 000000
"""
MASTER = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in _PAL.split()], np.uint8)


def decode_tile(b) -> np.ndarray:
    p0 = np.unpackbits(np.frombuffer(bytes(b[:8]), np.uint8)).reshape(8, 8)
    p1 = np.unpackbits(np.frombuffer(bytes(b[8:16]), np.uint8)).reshape(8, 8)
    return (p0 | (p1 << 1)).astype(np.uint8)


def encode_tile(t) -> bytes:
    t = np.asarray(t, np.uint8)
    return np.packbits(t & 1, axis=1).tobytes() + np.packbits((t >> 1) & 1, axis=1).tobytes()


def decode(chr_bytes) -> np.ndarray:
    """-> (ntiles, 8, 8) of 0..3"""
    n = len(chr_bytes) // 16
    return np.stack([decode_tile(chr_bytes[i * 16:i * 16 + 16]) for i in range(n)])


def encode(tiles) -> bytes:
    return b"".join(encode_tile(t) for t in tiles)


def split_ines(rom: bytes):
    """-> (header, prg, chr)"""
    assert rom[:4] == b"NES\x1a"
    prg = rom[4] * 16384
    off = 16 + (512 if rom[6] & 4 else 0)
    return rom[:16], rom[off:off + prg], rom[off + prg:off + prg + rom[5] * 8192]


def rgb(idx, pal):
    """index image (0..3) + 4 master palette ids -> RGB"""
    return MASTER[np.asarray(pal, np.uint8) & 63][idx]


def compose(tiles, layout, flips=None) -> np.ndarray:
    """layout: rows of tile numbers (None = empty) -> index image."""
    h, w = len(layout), len(layout[0])
    out = np.zeros((h * 8, w * 8), np.uint8)
    for r in range(h):
        for c in range(w):
            t = layout[r][c]
            if t is None:
                continue
            px = tiles[t]
            f = flips[r][c] if flips else 0
            if f & 1:
                px = px[:, ::-1]
            if f & 2:
                px = px[::-1]
            out[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = px
    return out


def upscale(img, k):
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def sheet(tiles, pal=(0x0F, 0x16, 0x27, 0x30), cols=16, scale=4, gap=1) -> np.ndarray:
    """All tiles in a grid, RGB."""
    n = len(tiles)
    rows = (n + cols - 1) // cols
    cell = 8 * scale + gap
    out = np.full((rows * cell + gap, cols * cell + gap, 3), 40, np.uint8)
    for i in range(n):
        y, x = gap + (i // cols) * cell, gap + (i % cols) * cell
        out[y:y + 8 * scale, x:x + 8 * scale] = upscale(rgb(tiles[i], pal), scale)
    return out
