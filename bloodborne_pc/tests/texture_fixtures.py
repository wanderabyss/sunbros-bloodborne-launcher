"""Small synthetic FromSoftware texture containers for the tests (no game data in the repo)."""
import struct


def tpf(names, data=b'pixels'):
    """A PS4 TPF holding one texture per name (UTF-16 names)."""
    count = len(names)
    names_at = 0x10 + 0x24 * count
    blob = b''
    offsets = []
    for name in names:
        offsets.append(names_at + len(blob))
        blob += name.encode('utf-16-le') + b'\0\0'
    data_at = names_at + len(blob)
    entries = b''
    for i, name_at in enumerate(offsets):
        entries += struct.pack('<IiBBBBhhiiIii', data_at + i * len(data), len(data), 0, 0, 1, 0, 64, 64, 1, 0xD,
                               name_at, 0, 71)
    body = data * count
    return b'TPF\0' + struct.pack('<ii', len(body), count) + bytes([4, 0, 1, 0]) + entries + blob + body


def bxf4(files):
    """(bhd, bdt) of a unicode BXF4 with 0x24-byte file headers, as the game's map textures."""
    count = len(files)
    names_at = 0x40 + 0x24 * count
    blob = b''
    name_offsets = []
    for name, _ in files:
        name_offsets.append(names_at + len(blob))
        blob += name.encode('utf-16-le') + b'\0\0'
    header = (b'BHF4' + bytes([0, 0, 0, 0, 0, 0, 1, 0]) + struct.pack('<i', count) + struct.pack('<q', 0x40) +
              b'07D7R6\0\0' + struct.pack('<qq', 0x24, 0) + bytes([1, 0x74, 0, 0]) + b'\0' * 12)
    bdt = bytearray(b'BDF4' + bytes([0, 0, 0, 0, 0, 0, 1, 0]) + b'\0' * 8 + struct.pack('<q', 0x30) +
                    b'07D7R6\0\0' + b'\0' * 8)
    headers = b''
    for i, ((name, data), name_at) in enumerate(zip(files, name_offsets)):
        bdt += b'\0' * (-len(bdt) % 0x10)
        headers += struct.pack('<B3xiqqIiI', 0x40, -1, len(data), len(data), len(bdt), i, name_at)
        bdt += data
    return header + headers + blob, bytes(bdt)
