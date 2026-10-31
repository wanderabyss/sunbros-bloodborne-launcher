# SPDX-License-Identifier: GPL-2.0-or-later
"""FromSoftware containers as Bloodborne 1.09 ships them: DCX (DFLT, zlib), BND4, BXF4 and TPF.

The PC features rewrite a few of the player's own game files at start (the Hunter's Dream
layout, the Altar of Despair's talk script, event scripts, menu assets); these read and write
the containers around them. The HD Texture Pack (hd_texture_pack.py) merges map textures through
BXF4 and checks textures through TPF. Formats as documented by SoulsFormats (BND4, BXF4,
BinderHashTable, TPF) and droogie's bbhost.
"""
import struct
import zlib

# The DCX header Bloodborne's DFLT files use: big-endian offsets, compression level 9.
_DCX_HEADER = struct.Struct('>4sIIIII4sII4s4sIB3xIIII4sI')


class FormatError(ValueError):
    pass


def dcx_decompress(data):
    if data[:4] != b'DCX\0':
        raise FormatError('not a DCX file')
    if data[0x28:0x2c] != b'DFLT':
        raise FormatError(f'unsupported DCX compression {data[0x28:0x2c]!r}')
    size, packed = struct.unpack_from('>II', data, 0x1c)
    try:
        start = data.index(b'DCA\0', 0x2c) + 8
    except ValueError:
        raise FormatError('DCX header has no DCA block') from None
    # A damaged file (a cut-short copy, a repack with a wrong header) is a format error, so the
    # feature reading it turns itself off rather than stopping the game.
    if len(data) - start < packed:
        raise FormatError(f'DCX file is truncated: its header says {packed} bytes of data, '
                          f'the file has {len(data) - start}')
    try:
        out = zlib.decompress(data[start:start + packed])
    except zlib.error as error:
        raise FormatError(f'DCX data is damaged ({error})') from None
    if len(out) != size:
        raise FormatError('DCX size does not match its header')
    return out


def dcx_head(data, size):
    """The first `size` bytes of a DCX file's content (or all of it, if shorter)."""
    if data[:4] != b'DCX\0' or data[0x28:0x2c] != b'DFLT':
        raise FormatError('not a DFLT DCX file')
    try:
        start = data.index(b'DCA\0', 0x2c) + 8
        return zlib.decompressobj().decompress(data[start:], size)
    except (ValueError, zlib.error) as error:
        raise FormatError(f'DCX data is damaged ({error})') from None


def dcx_compress(data, template=None):
    """DFLT DCX of `data`. With `template` (the file being replaced) its header is kept and only
    the sizes change, so the result differs from the original only where the content does."""
    packed = zlib.compress(data, 9)
    if template is not None:
        if template[:4] != b'DCX\0' or template[0x28:0x2c] != b'DFLT':
            raise FormatError('template is not a DFLT DCX file')
        start = template.index(b'DCA\0', 0x2c) + 8
        header = bytearray(template[:start])
        struct.pack_into('>II', header, 0x1c, len(data), len(packed))
        return bytes(header) + packed
    header = _DCX_HEADER.pack(b'DCX\0', 0x10000, 0x18, 0x24, 0x44, 0x4c, b'DCS\0', len(data), len(packed),
                              b'DCP\0', b'DFLT', 0x20, 9, 0, 0, 0, 0x10100, b'DCA\0', 8)
    return header + packed


def _name(data, at, unicode):
    """The zero-terminated name at `at`: UTF-16 or Shift JIS."""
    if unicode:
        end = at
        while data[end:end + 2] != b'\0\0':
            if end + 2 > len(data):
                raise FormatError('name runs past the end of the header')
            end += 2
        return data[at:end].decode('utf-16-le')
    end = data.find(b'\0', at)
    if end < 0:
        raise FormatError('name runs past the end of the header')
    return data[at:end].decode('shift_jis')


class Bnd4:
    """A BND4 archive whose files can be replaced. Everything but the files' data, their sizes
    and their offsets is kept byte for byte (names, ids, flags, hash table, header)."""

    # File header layouts by size: (offset of the compressed size, of the uncompressed size or
    # None, of the data offset).
    _LAYOUTS = {0x24: (0x08, 0x10, 0x18), 0x20: (0x08, 0x10, 0x18), 0x18: (0x08, None, 0x10)}

    def __init__(self, data):
        if data[:4] != b'BND4':
            raise FormatError('not a BND4 archive')
        if data[8]:
            raise FormatError('big-endian BND4 is unsupported')
        count, = struct.unpack_from('<i', data, 0x0c)
        self.header_size, = struct.unpack_from('<q', data, 0x20)
        if self.header_size not in self._LAYOUTS:
            raise FormatError(f'unsupported BND4 file header size {self.header_size:#x}')
        self.unicode = bool(data[0x30])
        self._data = data
        self.names, self.files, self.ids, offsets = [], [], [], []
        size_at, _, offset_at = self._LAYOUTS[self.header_size]
        for i in range(count):
            at = 0x40 + i * self.header_size
            size, = struct.unpack_from('<q', data, at + size_at)
            offset, = struct.unpack_from('<I', data, at + offset_at)
            name_at, = struct.unpack_from('<I', data, at + self.header_size - 4)
            self.names.append(self._name(name_at))
            # The file id follows the data offset in the 0x24-byte headers (None without one).
            self.ids.append(struct.unpack_from('<i', data, at + offset_at + 4)[0]
                            if self.header_size == 0x24 else None)
            self.files.append(bytes(data[offset:offset + size]))
            offsets.append(offset)
        self._offsets = offsets
        self._end = max((o + len(f) for o, f in zip(offsets, self.files)), default=len(data))
        self._start = min(offsets) if offsets else len(data)
        # The archive's data alignment: the largest power of two (up to 0x10) every offset keeps.
        self.align = 0x10
        while self.align > 1 and any(o % self.align for o in offsets):
            self.align //= 2

    def _name(self, at):
        return _name(self._data, at, self.unicode)

    def index(self, name):
        """Index of the file whose path ends with `name` (case-insensitive)."""
        wanted = name.replace('/', '\\').casefold()
        matches = [i for i, n in enumerate(self.names) if n.replace('/', '\\').casefold().endswith(wanted)]
        if len(matches) != 1:
            raise FormatError(f'{name}: {len(matches)} matching files in the archive')
        return matches[0]

    def to_bytes(self):
        prefix = bytearray(self._data[:self._start])
        size_at, raw_at, offset_at = self._LAYOUTS[self.header_size]
        body = bytearray()
        # Files keep their original order in the data area.
        for i in sorted(range(len(self.files)), key=lambda i: self._offsets[i]):
            while (self._start + len(body)) % self.align:
                body.append(0)
            at = 0x40 + i * self.header_size
            struct.pack_into('<q', prefix, at + size_at, len(self.files[i]))
            if raw_at is not None:
                struct.pack_into('<q', prefix, at + raw_at, len(self.files[i]))
            struct.pack_into('<I', prefix, at + offset_at, self._start + len(body))
            body += self.files[i]
        tail = self._data[self._end:]
        return bytes(prefix + body + tail)


class Bxf4:
    """The header (BHF4) of a BXF4 archive whose data (BDF4) is a separate file, as Bloodborne's
    map textures are (map/mXX/mXX_000N.tpfbhd + .tpfbdt, and the update archives beside them,
    .tpfbhd.patch + .tpfbdt.patch). Each entry is one texture file (<name>.tpf.dcx).

    Only the header is held: a map's data runs to hundreds of MB, so entries are read from the
    data file by offset (read), and an archive is written by streaming entries into a new data
    file behind data_header() and then writing header() with where each entry went. Everything
    but the entries' sizes and offsets is kept byte for byte: names, ids, flags, the name hash
    table, the version."""

    DATA_HEADER_SIZE = 0x30
    DATA_ALIGN = 0x10
    # Binder file flag: the entry itself is compressed (its stored and real sizes differ).
    _COMPRESSED = 0x01

    def __init__(self, bhd):
        if bhd[:4] != b'BHF4':
            raise FormatError('not a BHF4 archive header')
        if bhd[9]:
            raise FormatError('big-endian BXF4 is unsupported')
        count, = struct.unpack_from('<i', bhd, 0x0c)
        self.header_size, = struct.unpack_from('<q', bhd, 0x20)
        if self.header_size not in Bnd4._LAYOUTS:
            raise FormatError(f'unsupported BXF4 file header size {self.header_size:#x}')
        if count < 0 or 0x40 + count * self.header_size > len(bhd):
            raise FormatError('BXF4 header is truncated')
        self.version = bhd[0x18:0x20]
        self.unicode = bool(bhd[0x30])
        self._data = bytes(bhd)
        self.names, self.ids, self.offsets, self.sizes = [], [], [], []
        size_at, raw_at, offset_at = Bnd4._LAYOUTS[self.header_size]
        for i in range(count):
            at = 0x40 + i * self.header_size
            if bhd[at] & self._COMPRESSED:
                raise FormatError('compressed BXF4 entries are unsupported')
            size, = struct.unpack_from('<q', bhd, at + size_at)
            if raw_at is not None and struct.unpack_from('<q', bhd, at + raw_at)[0] != size:
                raise FormatError('BXF4 entry sizes disagree')
            self.sizes.append(size)
            self.offsets.append(struct.unpack_from('<I', bhd, at + offset_at)[0])
            self.ids.append(struct.unpack_from('<i', bhd, at + offset_at + 4)[0]
                            if self.header_size == 0x24 else None)
            self.names.append(_name(bhd, struct.unpack_from('<I', bhd, at + self.header_size - 4)[0],
                                    self.unicode))

    def __len__(self):
        return len(self.names)

    def index(self):
        """{name casefolded: entry number}."""
        return {name.casefold(): i for i, name in enumerate(self.names)}

    def read(self, bdt, i):
        """Entry `i` from the open data file `bdt`."""
        bdt.seek(self.offsets[i])
        data = bdt.read(self.sizes[i])
        if len(data) != self.sizes[i]:
            raise FormatError(f'{self.names[i]}: the data file is truncated')
        return data

    def in_data_order(self):
        """Entry numbers by offset: reading them in this order only moves forward through the
        data file (a file inside a zip can then be streamed)."""
        return sorted(range(len(self)), key=lambda i: self.offsets[i])

    @staticmethod
    def data_header(bdt_start):
        """The BDF4 header of a new data file: the first bytes of the original's."""
        head = bytes(bdt_start[:Bxf4.DATA_HEADER_SIZE])
        if head[:4] != b'BDF4' or len(head) != Bxf4.DATA_HEADER_SIZE:
            raise FormatError('not a BDF4 archive')
        return head

    def header(self, placed):
        """This header with entry i at placed[i] = (offset, size) in the new data file."""
        if len(placed) != len(self):
            raise FormatError('every entry needs a place')
        out = bytearray(self._data)
        size_at, raw_at, offset_at = Bnd4._LAYOUTS[self.header_size]
        for i, (offset, size) in enumerate(placed):
            if offset > 0xffffffff:
                raise FormatError('BXF4 data file over 4 GB')
            at = 0x40 + i * self.header_size
            struct.pack_into('<q', out, at + size_at, size)
            if raw_at is not None:
                struct.pack_into('<q', out, at + raw_at, size)
            struct.pack_into('<I', out, at + offset_at, offset)
        return bytes(out)


class Tpf:
    """The textures of a TPF (PS4 and PC layouts): name, format, size and mip count of each,
    for checking what a texture mod changes. Read only: mods are merged a whole TPF at a time."""

    PLATFORMS = {0: 'PC', 4: 'PS4', 5: 'XboxOne'}
    # The header, the texture headers and the names come before the texture data.
    HEAD = 1 << 16

    @classmethod
    def head(cls, data):
        """The textures of a TPF (or TPF DCX) from its start only: no texture data is unpacked."""
        if data[:4] == b'DCX\0':
            data = dcx_head(data, cls.HEAD)
        return cls(data, partial=True)

    def __init__(self, data, partial=False):
        if data[:4] == b'DCX\0':
            data = dcx_decompress(data)
        if data[:4] != b'TPF\0' or len(data) < 0x10:
            raise FormatError('not a TPF file')
        count, = struct.unpack_from('<i', data, 0x08)
        platform = data[0x0c]
        if platform not in self.PLATFORMS:
            raise FormatError(f'unsupported TPF platform {platform}')
        self.platform = self.PLATFORMS[platform]
        unicode = data[0x0e] == 1
        entry = 0x14 if platform == 0 else 0x24
        if count < 0 or 0x10 + count * entry > len(data):
            raise FormatError('TPF header is truncated')
        self.textures = []
        for i in range(count):
            at = 0x10 + i * entry
            offset, size, fmt, kind, mipmaps = struct.unpack_from('<IiBBB', data, at)
            if not partial and offset + size > len(data):
                raise FormatError('TPF texture runs past the end of the file')
            width = height = None
            if platform != 0:
                width, height = struct.unpack_from('<hh', data, at + 0x0c)
                name_at, = struct.unpack_from('<I', data, at + 0x18)
            else:
                name_at, = struct.unpack_from('<I', data, at + 0x0c)
            self.textures.append({'name': _name(data, name_at, unicode), 'format': fmt, 'type': kind,
                                  'mipmaps': mipmaps, 'width': width, 'height': height, 'size': size})
