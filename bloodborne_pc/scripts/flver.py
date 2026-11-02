# SPDX-License-Identifier: GPL-2.0-or-later
"""FLVER2 models (Bloodborne 1.09, version 0x20014, little endian, UTF-16 strings): read the
structures, and one edit, glow_material(): a material moved onto one of the game's own emissive
"glow" materials (the shader the Kirkhammer's uses plus emissive and bloom), with an emissive
texture of its own. Formats as documented by SoulsFormats (FLVER2).

Layout: a 0x80 header, then the dummies (0x40 each), materials (0x20), bones (0x80), meshes
(0x30), face sets (0x20), vertex buffers (0x20), buffer layouts (0x10) and textures (0x20), then
everything they point at (GX lists, layout members, index lists, bounding boxes, strings) up to
the header's data offset, then the vertex and index data. Offsets into the vertex and index data
are relative to the data offset; every other offset is from the start of the file.

glow_material() inserts one texture entry into the texture array, so every absolute offset past
it moves by 0x20; the new strings and the new GX list go after the old header data, and the vertex
and index data move along unchanged.
"""
import struct


class FlverError(ValueError):
    pass


HEADER = 0x80
SIZES = {'dummy': 0x40, 'material': 0x20, 'bone': 0x80, 'mesh': 0x30, 'faceset': 0x20,
         'buffer': 0x20, 'layout': 0x10, 'texture': 0x20}
# The absolute offsets in each record: (record kind, field offsets). Bones' name; materials' name,
# MTD and GX list; meshes' bounding box and bone, face set and vertex buffer index lists; layouts'
# members; textures' path and type.
ABSOLUTE = {'material': (0x00, 0x04, 0x14), 'bone': (0x0C,), 'mesh': (0x18, 0x1C, 0x24, 0x2C),
            'layout': (0x0C,), 'texture': (0x00, 0x04)}
GX_END = 0x7FFFFFFF
DATA_ALIGN = 0x10


def _string(data, at):
    end = at
    while data[end:end + 2] != b'\0\0':
        end += 2
    return data[at:end].decode('utf-16-le')


class Flver:
    def __init__(self, data):
        if data[:6] != b'FLVER\0' or data[6:8] != b'L\0':
            raise FlverError('not a little-endian FLVER')
        self.data = data
        self.version, self.data_offset, self.data_length = struct.unpack_from('<3i', data, 0x08)
        counts = dict(zip(('dummy', 'material', 'bone', 'mesh', 'buffer'), struct.unpack_from('<5i', data, 0x14)))
        counts.update(zip(('faceset', 'layout', 'texture'), struct.unpack_from('<3i', data, 0x50)))
        if data[0x49] != 1:
            raise FlverError('not a UTF-16 FLVER')
        self.counts = counts
        self.at = {}
        at = HEADER
        for kind in ('dummy', 'material', 'bone', 'mesh', 'faceset', 'buffer', 'layout', 'texture'):
            self.at[kind] = at
            at += counts[kind] * SIZES[kind]
        self.headers_end = at
        if at > self.data_offset or self.data_offset + self.data_length > len(data):
            raise FlverError('FLVER sections overrun')

    def record(self, kind, i):
        at = self.at[kind] + i * SIZES[kind]
        return at, self.data[at:at + SIZES[kind]]

    def string(self, at):
        return _string(self.data, at)

    def materials(self):
        out = []
        for i in range(self.counts['material']):
            at, _ = self.record('material', i)
            name, mtd, count, first, flags, gx = struct.unpack_from('<6i', self.data, at)
            out.append({'name': self.string(name), 'mtd': self.string(mtd), 'textures': list(range(first, first + count)),
                        'flags': flags, 'gx': self.gx_list(gx) if gx else []})
        return out

    def textures(self):
        out = []
        for i in range(self.counts['texture']):
            at, raw = self.record('texture', i)
            path, kind = struct.unpack_from('<2i', raw)
            out.append({'path': self.string(path), 'type': self.string(kind), 'rest': raw[8:]})
        return out

    def gx_list(self, at):
        """[(id, unk, payload)] up to and including the end marker."""
        items = []
        while True:
            gid, unk, length = struct.unpack_from('<3i', self.data, at)
            items.append((gid, unk, self.data[at + 12:at + length]))
            if gid == GX_END:
                return items
            if length < 12:
                raise FlverError('bad GX list')
            at += length


def _gx_bytes(items):
    return b''.join(struct.pack('<3i', gid, unk, 12 + len(payload)) + payload for gid, unk, payload in items)


def gx_id(name):
    """'GX03' -> its id (the four letters as a little-endian int)."""
    return struct.unpack('<i', name.encode('ascii'))[0]


def glow_material(data, material, mtd, emissive_path, emissive_slot, glow_scale):
    """`data` with material `material` on MTD `mtd` (full path, as the game's flvers give it), an
    emissive texture (`emissive_path`, type g_EmissiveTexture) inserted at position `emissive_slot`
    of its textures, and its GX list given the glow material's two items: GX03 (glow scale, after
    GX00) and GX32 (zeros, before GX30), as the game's own C[ARSN]_em_Glow materials have them."""
    f = Flver(data)
    if f.counts['material'] <= material:
        raise FlverError(f'no material {material}')
    mat_at, _ = f.record('material', material)
    name, old_mtd, count, first, flags, gx = struct.unpack_from('<6i', data, mat_at)
    if not 0 <= emissive_slot <= count:
        raise FlverError('emissive slot outside the material')
    items = f.gx_list(gx)
    ids = [g for g, _u, _p in items]
    if gx_id('GX03') in ids or gx_id('GX32') in ids or gx_id('GX00') not in ids or gx_id('GX30') not in ids:
        raise FlverError(f'GX list {ids} is not a plain material\'s')
    unk = items[0][1]
    glow = []
    for item in items:
        if item[0] == gx_id('GX30'):
            glow.append((gx_id('GX32'), unk, b'\0' * 12))
        glow.append(item)
        if item[0] == gx_id('GX00'):
            glow.append((gx_id('GX03'), unk, struct.pack('<f', glow_scale) + b'\0' * 12))

    insert_index = first + emissive_slot
    insert_at = f.at['texture'] + insert_index * SIZES['texture']
    shift = SIZES['texture']
    head = bytearray(data[:f.data_offset])

    def moved(offset):
        return offset + shift if offset >= insert_at else offset

    # Every absolute offset past the insertion point moves.
    for kind, fields in ABSOLUTE.items():
        for i in range(f.counts[kind]):
            at, _ = f.record(kind, i)
            for field in fields:
                value = struct.unpack_from('<i', head, at + field)[0]
                if value:
                    struct.pack_into('<i', head, at + field, moved(value))
    # Materials whose textures come after the new one start one later.
    for i in range(f.counts['material']):
        at, _ = f.record('material', i)
        c, start = struct.unpack_from('<2i', head, at + 8)
        if i == material:
            struct.pack_into('<i', head, at + 8, c + 1)
        elif start >= insert_index:
            struct.pack_into('<i', head, at + 12, start + 1)
    # The new texture entry: the old slot's layout (scale 1, the flags of a real texture).
    like = f.record('texture', first)[1]
    entry = bytearray(like)
    head[insert_at:insert_at] = entry
    struct.pack_into('<i', head, 0x58, f.counts['texture'] + 1)

    # New strings and the GX list after the old header data.
    tail = bytearray()
    base = len(head)

    def add(blob, align=2):
        while (base + len(tail)) % align:
            tail.append(0)
        at = base + len(tail)
        tail.extend(blob)
        return at

    mtd_at = add(mtd.encode('utf-16-le') + b'\0\0')
    path_at = add(emissive_path.encode('utf-16-le') + b'\0\0')
    type_at = add('g_EmissiveTexture'.encode('utf-16-le') + b'\0\0')
    gx_at = add(_gx_bytes(glow), 4)
    struct.pack_into('<2i', head, insert_at, path_at, type_at)
    struct.pack_into('<i', head, mat_at + 4, mtd_at)
    struct.pack_into('<i', head, mat_at + 0x14, gx_at)
    head.extend(tail)
    while len(head) % DATA_ALIGN:
        head.append(0)
    struct.pack_into('<i', head, 0x0C, len(head))
    return bytes(head) + data[f.data_offset:]


def check_glow(old, new, material, mtd, emissive_path, emissive_slot, glow_scale):
    """FlverError unless `new` is `old` with exactly glow_material()'s change."""
    a, b = Flver(old), Flver(new)
    if a.data_length != b.data_length or \
            old[a.data_offset:a.data_offset + a.data_length] != new[b.data_offset:b.data_offset + b.data_length]:
        raise FlverError('the vertex and index data changed')
    for kind in ('dummy', 'material', 'bone', 'mesh', 'faceset', 'buffer', 'layout'):
        if a.counts[kind] != b.counts[kind]:
            raise FlverError(f'{kind} count changed')
    if b.counts['texture'] != a.counts['texture'] + 1:
        raise FlverError('not one texture more')
    for kind in ('dummy', 'faceset', 'buffer'):
        if old[a.at[kind]:a.at[kind] + a.counts[kind] * SIZES[kind]] != new[b.at[kind]:b.at[kind] + b.counts[kind] * SIZES[kind]]:
            raise FlverError(f'{kind} records changed')
    for i in range(a.counts['bone']):
        ra, rb = a.record('bone', i)[1], b.record('bone', i)[1]
        if ra[:0x0C] + ra[0x10:] != rb[:0x0C] + rb[0x10:] or \
                a.string(struct.unpack_from('<i', ra, 0x0C)[0]) != b.string(struct.unpack_from('<i', rb, 0x0C)[0]):
            raise FlverError(f'bone {i} changed')
    for i in range(a.counts['mesh']):
        ra, rb = a.record('mesh', i)[1], b.record('mesh', i)[1]
        for field, length in ((0x18, 24), (0x1C, 4 * struct.unpack_from('<i', ra, 0x14)[0]),
                              (0x24, 4 * struct.unpack_from('<i', ra, 0x20)[0]), (0x2C, 4 * struct.unpack_from('<i', ra, 0x28)[0])):
            pa, pb = struct.unpack_from('<i', ra, field)[0], struct.unpack_from('<i', rb, field)[0]
            if bool(pa) != bool(pb) or (pa and old[pa:pa + length] != new[pb:pb + length]):
                raise FlverError(f'mesh {i} list at {field:#x} changed')
        if ra[:0x18] != rb[:0x18] or ra[0x20:0x24] != rb[0x20:0x24] or ra[0x28:0x2C] != rb[0x28:0x2C]:
            raise FlverError(f'mesh {i} changed')
    for i in range(a.counts['layout']):
        ra, rb = a.record('layout', i)[1], b.record('layout', i)[1]
        n = struct.unpack_from('<i', ra)[0]
        pa, pb = struct.unpack_from('<i', ra, 0x0C)[0], struct.unpack_from('<i', rb, 0x0C)[0]
        if ra[:0x0C] != rb[:0x0C] or old[pa:pa + n * 0x14] != new[pb:pb + n * 0x14]:
            raise FlverError(f'layout {i} changed')
    ma, mb = a.materials(), b.materials()
    ta, tb = a.textures(), b.textures()
    for i, (x, y) in enumerate(zip(ma, mb)):
        if i != material:
            if (x['name'], x['mtd'], x['flags'], x['gx']) != (y['name'], y['mtd'], y['flags'], y['gx']) or \
                    [ta[t] for t in x['textures']] != [tb[t] for t in y['textures']]:
                raise FlverError(f'material {i} changed')
            continue
        if (y['name'], y['flags'], y['mtd']) != (x['name'], x['flags'], mtd):
            raise FlverError('the material is not the old one on the new MTD')
        old_tex = [ta[t] for t in x['textures']]
        new_tex = [tb[t] for t in y['textures']]
        added = new_tex.pop(emissive_slot)
        if new_tex != old_tex or (added['path'], added['type']) != (emissive_path, 'g_EmissiveTexture'):
            raise FlverError('the material\'s textures are not the old ones plus the emissive one')
        gx = [item for item in y['gx'] if item[0] not in (gx_id('GX03'), gx_id('GX32'))]
        extra = {item[0]: item[2] for item in y['gx'] if item[0] in (gx_id('GX03'), gx_id('GX32'))}
        if gx != x['gx'] or extra.get(gx_id('GX03'), b'')[:4] != struct.pack('<f', glow_scale) or gx_id('GX32') not in extra:
            raise FlverError('the GX list is not the old one plus the glow items')
