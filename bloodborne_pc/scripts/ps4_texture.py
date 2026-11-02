# SPDX-License-Identifier: GPL-2.0-or-later
"""PS4 TPF textures to images and back, for retexturing a model from the player's own files.

Bloodborne's PS4 TPFs (fromsoft.Tpf reads only their headers) hold BCn textures as the GPU reads
them: each mip level 1D-tiled (ARRAY_1D_TILED_THIN1), that is cut into 8x8-block micro tiles laid
out row by row, the blocks inside a tile in Morton order (x0 y0 x1 y1 x2 y2: the GCN thin micro
tiling, gpu/shadps4/video_core/host_shaders/tiling.comp), and every level padded to whole tiles.
A texture header's last word is its DXGI format. Supported: BC1 (punch-through alpha kept), BC3,
BC4 and BC5, the formats the weapon parts use.

Round trip: detiling and tiling again gives back the same bytes, and so does set_image() with the
image image() returned: a block whose pixels did not change keeps its original bytes, and a mip
level is made again only where the full-size image changed. Only the changed blocks are encoded
again (BCn encoding is lossy and encoder-specific, so new blocks are Pillow's, not the game's).
Pillow encodes BC1/BC3/BC5; BC4 is taken from a BC3 block's alpha half (the same 8-byte format).
"""
import io
import struct

from fromsoft import FormatError, _name

ENTRY = 0x24
# DXGI format -> (bytes per block, DDS FourCC, Pillow mode, Pillow pixel_format to encode).
FORMATS = {
    71: (8, b'DXT1', 'RGBA', 'DXT1'), 72: (8, b'DXT1', 'RGBA', 'DXT1'),      # BC1 (and sRGB)
    77: (16, b'DXT5', 'RGBA', 'DXT5'), 78: (16, b'DXT5', 'RGBA', 'DXT5'),    # BC3
    80: (8, b'ATI1', 'L', None),                                             # BC4
    83: (16, b'ATI2', 'RGB', 'BC5'),                                         # BC5
}


def _morton(x, y):
    return (x & 1) | (y & 1) << 1 | (x & 2) << 1 | (y & 2) << 2 | (x & 4) << 2 | (y & 4) << 3


_MORTON = [[_morton(x, y) for x in range(8)] for y in range(8)]


def _blocks(size):
    return max(1, (size + 3) // 4)


def levels(width, height, mipmaps):
    """(width, height, blocks across, blocks down) of each mip level."""
    out = []
    for level in range(mipmaps):
        w, h = max(1, width >> level), max(1, height >> level)
        out.append((w, h, _blocks(w), _blocks(h)))
    return out


def tiled_size(bw, bh, block):
    return ((bw + 7) // 8) * ((bh + 7) // 8) * 64 * block


def detile(data, bw, bh, block):
    """Linear blocks (row by row) of one tiled mip level."""
    tiles = (bw + 7) // 8
    out = bytearray(bw * bh * block)
    for by in range(bh):
        ty, y = divmod(by, 8)
        order = _MORTON[y]
        row = by * bw
        for bx in range(bw):
            tx, x = divmod(bx, 8)
            src = ((ty * tiles + tx) * 64 + order[x]) * block
            dst = (row + bx) * block
            out[dst:dst + block] = data[src:src + block]
    return bytes(out)


def tile(linear, bw, bh, block):
    """One mip level tiled, the padding of each tile zero (as the game's own textures)."""
    tiles = (bw + 7) // 8
    out = bytearray(tiled_size(bw, bh, block))
    for by in range(bh):
        ty, y = divmod(by, 8)
        order = _MORTON[y]
        row = by * bw
        for bx in range(bw):
            tx, x = divmod(bx, 8)
            dst = ((ty * tiles + tx) * 64 + order[x]) * block
            src = (row + bx) * block
            out[dst:dst + block] = linear[src:src + block]
    return bytes(out)


def _dds(width, height, fourcc, data):
    """A one-level DDS around linear blocks, for Pillow to decode."""
    return struct.pack('<4sIIIIIII44xII4sIIIII5I', b'DDS ', 124, 0x81007, height, width, len(data), 0, 1,
                       32, 4, fourcc, 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0) + data


def _decode(blocks, w, h, bw, bh, fmt):
    from PIL import Image
    _size, fourcc, mode, _pf = FORMATS[fmt]
    im = Image.open(io.BytesIO(_dds(bw * 4, bh * 4, fourcc, blocks)))
    im.load()
    if im.mode != mode:
        im = im.convert(mode)
    return im.crop((0, 0, w, h)) if (w, h) != im.size else im


def _encode(im, bw, bh, fmt):
    """Linear blocks of `im`, padded to whole blocks by repeating its edge."""
    from PIL import Image
    block, _fourcc, mode, pixel_format = FORMATS[fmt]
    im = im.convert(mode)
    if im.size != (bw * 4, bh * 4):
        padded = Image.new(mode, (bw * 4, bh * 4))
        padded.paste(im.resize((bw * 4, bh * 4), Image.NEAREST))
        padded.paste(im, (0, 0))
        im = padded
    out = io.BytesIO()
    if pixel_format is None:   # BC4: a BC3's alpha blocks
        rgba = Image.merge('RGBA', (im, im, im, im))
        rgba.save(out, 'DDS', pixel_format='DXT5')
        data = out.getvalue()[128:]
        return b''.join(data[i:i + 8] for i in range(0, len(data), 16))
    im.save(out, 'DDS', pixel_format=pixel_format)
    data = out.getvalue()
    start = 148 if data[84:88] == b'DX10' else 128
    return data[start:start + bw * bh * block]


class Texture:
    def __init__(self, tpf, index):
        at = 0x10 + index * ENTRY
        self.tpf, self.at = tpf, at
        data = tpf.data
        self.offset, self.size, self.format_byte, self.type, self.mipmaps = struct.unpack_from('<IiBBB', data, at)
        self.width, self.height = struct.unpack_from('<hh', data, at + 0x0c)
        name_at, = struct.unpack_from('<I', data, at + 0x18)
        self.dxgi, = struct.unpack_from('<I', data, at + 0x20)
        self.name = _name(data, name_at, data[0x0e] == 1)
        if self.dxgi not in FORMATS:
            raise FormatError(f'{self.name}: unsupported texture format (DXGI {self.dxgi})')
        if self.type != 0:
            raise FormatError(f'{self.name}: not a 2D texture (type {self.type})')
        self.block = FORMATS[self.dxgi][0]
        self.levels = levels(self.width, self.height, self.mipmaps)
        if sum(tiled_size(bw, bh, self.block) for *_wh, bw, bh in self.levels) != self.size:
            raise FormatError(f'{self.name}: its size is not a 1D-tiled mip chain')
        self.mips = []   # linear blocks of each level
        pos = self.offset
        for *_wh, bw, bh in self.levels:
            n = tiled_size(bw, bh, self.block)
            self.mips.append(detile(data[pos:pos + n], bw, bh, self.block))
            pos += n

    def tiled(self):
        return b''.join(tile(m, bw, bh, self.block) for m, (*_wh, bw, bh) in zip(self.mips, self.levels))

    def image(self, level=0):
        """The level as a Pillow image (RGBA for BC1/BC3, L for BC4, RGB for BC5)."""
        w, h, bw, bh = self.levels[level]
        return _decode(self.mips[level], w, h, bw, bh, self.dxgi)

    def set_image(self, im):
        """Replaces the texture with `im` (its full size): every mip level is made from it where
        it differs from the current image, and only changed blocks are encoded again."""
        from PIL import Image, ImageChops
        mode = FORMATS[self.dxgi][2]
        im = im.convert(mode)
        if im.size != (self.width, self.height):
            raise FormatError(f'{self.name}: the image is {im.size}, the texture {self.width}x{self.height}')
        channels = ImageChops.difference(im, self.image(0)).split()
        mask0 = channels[0]
        for c in channels[1:]:
            mask0 = ImageChops.lighter(mask0, c)
        mask0 = mask0.point(lambda v: 255 if v else 0)
        if not mask0.getbbox():
            return
        for level, (w, h, bw, bh) in enumerate(self.levels):
            old = self.image(level)
            if level:
                new = im.resize((w, h), Image.BOX)
                mask = mask0.resize((w, h), Image.BOX).point(lambda v: 255 if v else 0)
                new = Image.composite(new, old, mask)
            else:
                new, mask = im, mask0
            if not mask.getbbox():
                continue
            # Which blocks change: any changed pixel in their 4x4.
            grid = Image.new('L', (bw * 4, bh * 4))
            grid.paste(mask, (0, 0))
            grid = grid.resize((bw, bh), Image.BOX).point(lambda v: 255 if v else 0).tobytes()
            fresh = _encode(new, bw, bh, self.dxgi)
            out = bytearray(self.mips[level])
            b = self.block
            for i, flag in enumerate(grid):
                if flag:
                    out[i * b:(i + 1) * b] = fresh[i * b:(i + 1) * b]
            self.mips[level] = bytes(out)


class Ps4Tpf:
    """A PS4 TPF whose textures can be read as images and replaced; to_bytes() writes it back
    with the same headers, sizes and layout."""

    def __init__(self, data):
        if data[:4] != b'TPF\0' or len(data) < 0x10:
            raise FormatError('not a TPF file')
        if data[0x0c] != 4:
            raise FormatError(f'not a PS4 TPF (platform {data[0x0c]})')
        self.data = data
        count, = struct.unpack_from('<i', data, 0x08)
        self.textures = [Texture(self, i) for i in range(count)]

    def __getitem__(self, name):
        for t in self.textures:
            if t.name.casefold() == name.casefold():
                return t
        raise KeyError(name)

    def rename(self, old, new):
        """Every texture name with `old` in it gets `new` in its place (the same length, so the
        layout stays)."""
        if len(old) != len(new):
            raise ValueError('a rename keeps the length')
        data = bytearray(self.data)
        unicode = data[0x0e] == 1
        for t in self.textures:
            if old not in t.name:
                continue
            name_at, = struct.unpack_from('<I', data, t.at + 0x18)
            encoded = t.name.replace(old, new).encode('utf-16le' if unicode else 'shift_jis')
            data[name_at:name_at + len(encoded)] = encoded
            t.name = t.name.replace(old, new)
        self.data = bytes(data)

    def add_texture(self, name, like, image, format_byte=None):
        """A new texture `name`, of `like`'s size, format and mip count, made from `image`; the TPF
        is laid out again (entries, names, then the data from a 0x100 boundary, back to back).
        format_byte: the entry's own format byte (default `like`'s)."""
        if any(t.name.casefold() == name.casefold() for t in self.textures):
            raise FormatError(f'{name} is already in the TPF')
        unicode = self.data[0x0e] == 1
        old = self.textures
        count = len(old) + 1
        names_at = 0x10 + count * ENTRY
        names = bytearray()
        name_offsets = []
        for n in [t.name for t in old] + [name]:
            name_offsets.append(names_at + len(names))
            names += n.encode('utf-16le') + b'\0\0' if unicode else n.encode('shift_jis') + b'\0'
        data_at = (names_at + len(names) + 0xFF) & ~0xFF
        body, entries = bytearray(), bytearray()
        sources = [(self.data[t.at:t.at + ENTRY], t.tiled()) for t in old]   # with any set_image() edits
        sources.append((self.data[like.at:like.at + ENTRY], bytes(like.size)))
        for (entry, blob), name_at in zip(sources, name_offsets):
            entry = bytearray(entry)
            struct.pack_into('<I', entry, 0, data_at + len(body))
            struct.pack_into('<I', entry, 0x18, name_at)
            entries += entry
            body += blob
        if format_byte is not None:
            entries[-ENTRY + 8] = format_byte
        head = bytearray(self.data[:0x10])
        struct.pack_into('<I', head, 0x04, len(body))
        struct.pack_into('<i', head, 0x08, count)
        rebuilt = Ps4Tpf(bytes(head + entries + names + bytes(data_at - names_at - len(names)) + body))
        rebuilt.textures[-1].set_image(image)
        self.data = rebuilt.to_bytes()
        self.textures = Ps4Tpf(self.data).textures
        return self.textures[-1]

    def to_bytes(self):
        out = bytearray(self.data)
        for t in self.textures:
            out[t.offset:t.offset + t.size] = t.tiled()
        return bytes(out)
