# SPDX-License-Identifier: GPL-2.0-or-later
"""The in-game PC menu's assets, made from the player's own game files.

Two edits, ported from droogie's bbhost (https://github.com/droogie/bbhost, GPL-3.0-or-later,
engine/menu_assets.cpp):

- menu/optionsetting.gfx: each PC section is a clone of the game's ControllSetting sprite under
  a new instance name and character id, retitled to the menu's message id, its static text
  dropped and its widget rows trimmed to the section's; it is placed on the main timeline
  hidden (the game shows the section it opens). The System list gets the movie's own
  ScrollBarV, since it now has more rows than lines.
- msg/<language>/menu.msgbnd.dcx: the menu's message ids added to the menu text (group 200),
  line help (201) and event text (30) FMGs of every language the game has. The game reads the
  folder its region and language pick, so all of them get the (English) strings. Dialog text
  (ids 920000..929999) goes to groups 78 and 204, the yes/no questions'.
- menu/title.gfx and title_dlc.gfx: one more line in the title's command list, for Quit Game.
"""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fromsoft import Bnd4, FormatError, dcx_compress, dcx_decompress

MESSAGES = Path(__file__).resolve().parent / 'pc_menu_messages.tsv'
MOVIE = Path('menu') / 'optionsetting.gfx'
TITLE_MOVIES = [Path('menu') / 'title.gfx', Path('menu') / 'title_dlc.gfx']  # the DLC edition uses the second
MESSAGE_FILE = 'menu.msgbnd.dcx'

# The sections: (instance name, title message id, rows). ControllSetting has rows Item_0_0..
# Item_5_0 and the label slot Item_6_0; a section keeps as many rows as it builds, and the
# game's own "Defaults" row lands in the slot after them. Option sections do not scroll, so six
# rows at most. The names and row counts must match src/pc_menu.c.
SECTION_ROWS = [
    ('PCGraphics', 117020, 5),
    ('PCDisplay', 125020, 5),
    ('PCEffects', 120020, 6),
    ('PCSetting', 116020, 4),
    ('PCGameplay', 126020, 5),
    ('PCCheats', 127020, 5),
    ('PCEnhance', 124020, 3),
    ('PCAchieve', 128020, 6),
]
# (name, title, depth on the main timeline, Defaults slot, rows dropped)
# The in-game movie crashes with seven or eight instantiated PC sections.
# Cheats and Enhancements remain in the overlay and launcher.
NATIVE_SECTIONS = [row for row in SECTION_ROWS if row[0] not in ('PCCheats', 'PCEnhance')]
SECTIONS = [(name, title, 383 + i, rows, [f'Item_{k}_0' for k in range(rows, 6)])
            for i, (name, title, rows) in enumerate(NATIVE_SECTIONS)]
# Where the System list's scroll bar goes, in pixels (bbhost's placement).
SCROLLBAR_AT = (1290, 354.5)


class Fail(FormatError):
    pass


# --- SWF/GFX tags ----------------------------------------------------------------------------

END, SHOW_FRAME, PLACE2, DEFINE_SPRITE, PLACE3, SYMBOL_CLASS = 0, 1, 26, 39, 70, 76
DEFINES = {2, 6, 20, 21, 22, 32, 33, 34, 36, 37, 39, 46, 48, 60, 75, 83, 84,
           1001, 1003, 1005, 1006, 1007, 1008, 1009, 1010}


def u16(b, i):
    if i + 2 > len(b):
        raise Fail('truncated')
    return struct.unpack_from('<H', b, i)[0]


def u32(b, i):
    if i + 4 > len(b):
        raise Fail('truncated')
    return struct.unpack_from('<I', b, i)[0]


def tags(b, i, end):
    """(code, header start, body start, body end) of each tag from i to end (or an End tag)."""
    out = []
    while i < end:
        header = u16(b, i)
        head = i
        i += 2
        code, length = header >> 6, header & 0x3f
        if length == 0x3f:
            length = u32(b, i)
            i += 4
        if i + length > len(b):
            raise Fail('a tag runs past the end')
        out.append((code, head, i, i + length))
        if code == END:
            break
        i += length
    return out


def body_start(b):
    bits = b[8] >> 3
    return 8 + (5 + 4 * bits + 7) // 8 + 4


def tag_bytes(code, body):
    if len(body) < 0x3f:
        return struct.pack('<H', (code << 6) | len(body)) + bytes(body)
    return struct.pack('<HI', (code << 6) | 0x3f, len(body)) + bytes(body)


def cstr(b, i):
    """(string, index after its terminator)."""
    j = b.find(b'\0', i)
    if j < 0:
        raise Fail('an unterminated name')
    return b[i:j].decode('latin-1'), j + 1


class BitReader:
    def __init__(self, b, i):
        self.b, self.i, self.bit = b, i, 0

    def u(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.b[self.i] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit, self.i = 0, self.i + 1
        return v

    def s(self, n):
        v = self.u(n)
        return v - (1 << n) if n and (v >> (n - 1)) & 1 else v

    def align(self):
        if self.bit:
            self.bit, self.i = 0, self.i + 1
        return self.i


class BitWriter:
    def __init__(self):
        self.bits = []

    def u(self, v, n):
        self.bits.extend((v >> k) & 1 for k in range(n - 1, -1, -1))

    def out(self):
        bits = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))


def sbits(v):
    n = 1
    while not -(1 << (n - 1)) <= v < (1 << (n - 1)):
        n += 1
    return n


class Matrix:
    """A matrix as a clone keeps it: scale and rotation fields as read, translation as numbers."""
    def __init__(self):
        self.has_scale = self.has_rot = False
        self.sn = self.rn = self.sa = self.sc = self.ra = self.rc = 0
        self.tx = self.ty = 0

    def copy(self):
        m = Matrix()
        m.__dict__.update(self.__dict__)
        return m


def read_matrix(b, i):
    r = BitReader(b, i)
    m = Matrix()
    if r.u(1):
        m.has_scale, m.sn = True, r.u(5)
        m.sa, m.sc = r.u(m.sn), r.u(m.sn)
    if r.u(1):
        m.has_rot, m.rn = True, r.u(5)
        m.ra, m.rc = r.u(m.rn), r.u(m.rn)
    n = r.u(5)
    m.tx, m.ty = r.s(n), r.s(n)
    return m, r.align()


def write_matrix(m):
    w = BitWriter()
    if m.has_scale:
        w.u(1, 1), w.u(m.sn, 5), w.u(m.sa, m.sn), w.u(m.sc, m.sn)
    else:
        w.u(0, 1)
    if m.has_rot:
        w.u(1, 1), w.u(m.rn, 5), w.u(m.ra, m.rn), w.u(m.rc, m.rn)
    else:
        w.u(0, 1)
    n = max(sbits(m.tx), sbits(m.ty))
    mask = (1 << n) - 1
    w.u(n, 5), w.u(m.tx & mask, n), w.u(m.ty & mask, n)
    return w.out()


def skip_cxform(b, i):
    r = BitReader(b, i)
    has_add, has_mul, n = r.u(1), r.u(1), r.u(4)
    if has_mul:
        r.u(n * 4)
    if has_add:
        r.u(n * 4)
    return r.align()


class Place2:
    def __init__(self, b, s, e):
        i = s
        self.flags, self.depth = b[i], u16(b, i + 1)
        i += 3
        self.cid = None
        if self.flags & 0x02:
            self.cid = u16(b, i)
            i += 2
        mat_end = i
        self.mat = None
        if self.flags & 0x04:
            self.mat, mat_end = read_matrix(b, i)
            i = mat_end
        if self.flags & 0x08:
            i = skip_cxform(b, i)
        if self.flags & 0x10:
            i += 2
        name_start = i
        self.name = None
        if self.flags & 0x20:
            self.name, i = cstr(b, i)
        self.mid = bytes(b[mat_end:name_start])
        self.tail = bytes(b[i:e])

    def build(self, depth, mat, name):
        flags = (self.flags | 0x20) if name is not None else (self.flags & ~0x20)
        out = bytearray([flags]) + struct.pack('<H', depth)
        if flags & 0x02:
            out += struct.pack('<H', self.cid or 0)
        if flags & 0x04:
            if mat is None:
                raise Fail('a placement with a matrix flag and no matrix')
            out += write_matrix(mat)
        out += self.mid
        if flags & 0x20:
            out += name.encode('latin-1') + b'\0'
        return bytes(out + self.tail)


def place3_hidden(cid, depth, mat, name):
    return bytes([0x02 | 0x04 | 0x20, 0x20]) + struct.pack('<HH', depth, cid) + write_matrix(mat) + \
        name.encode('latin-1') + b'\0\0'  # the last byte: visible = false


def symbol_classes(b):
    out = {}
    for code, _head, s, _e in tags(b, body_start(b), len(b)):
        if code != SYMBOL_CLASS:
            continue
        i = s + 2
        for _ in range(u16(b, s)):
            cid = u16(b, i)
            out[cid], i = cstr(b, i + 2)
    return out


def add_symbol_class(b, cid, name):
    for code, head, s, e in tags(b, body_start(b), len(b)):
        if code != SYMBOL_CLASS:
            continue
        body = bytearray(b[s:e])
        struct.pack_into('<H', body, 0, u16(b, s) + 1)
        body += struct.pack('<H', cid) + name.encode('latin-1') + b'\0'
        return b[:head] + tag_bytes(SYMBOL_CLASS, body) + b[e:]
    return None


def place_char(b, s, code):
    if code not in (PLACE2, PLACE3) or not b[s] & 0x02:
        return None
    return u16(b, s + (4 if code == PLACE3 else 3))


def find_sprite(b, cid):
    for code, head, s, e in tags(b, body_start(b), len(b)):
        if code == DEFINE_SPRITE and u16(b, s) == cid:
            return head, s, e
    return None


def max_character_id(b):
    return max((u16(b, s) for code, _h, s, e in tags(b, body_start(b), len(b)) if code in DEFINES and e - s >= 2),
               default=0)


def set_size(b):
    b = bytearray(b)
    struct.pack_into('<I', b, 4, len(b))
    return bytes(b)


def add_option_section(b, name, title_id, depth, defaults_slot, drop, clone='ControllSetting', top='Top'):
    """One PC section cloned from the donor section into the movie (bbhost add_option_section,
    without the added-rows case the skeleton does not use)."""
    if len(b) < 16 or b[:3] != b'GFX':
        raise Fail('optionsetting.gfx is not an uncompressed GFX')
    names = symbol_classes(b)
    places = {}
    for code, head, s, e in tags(b, body_start(b), len(b)):
        if code == PLACE2:
            p = Place2(b, s, e)
            if p.name:
                places[p.name] = (p, head, s, e)
    for want in (clone, top):
        if want not in places:
            raise Fail(f'no main-timeline instance named {want}')
    if name in places:
        raise Fail(f'already has an instance named {name}')
    clone_p = places[clone][0]
    new_cid = max_character_id(b) + 1
    sprite = find_sprite(b, clone_p.cid or 0)
    if not sprite:
        raise Fail(f'no DefineSprite for {clone}')
    _head, cs, ce = sprite

    # The title: the child sprite holding a StaticText_<id> placement, cloned with the new id.
    title_cid = title_old = title_body = None
    for code, _h, s, _e in tags(b, cs + 4, ce):
        cid = place_char(b, s, code)
        child = find_sprite(b, cid) if cid is not None else None
        if not child:
            continue
        for code2, _h2, s2, e2 in tags(b, child[1] + 4, child[2]):
            if code2 != PLACE2:
                continue
            q = Place2(b, s2, e2)
            if not q.name or not q.name.startswith('StaticText_'):
                continue
            new_name = f'StaticText_{title_id}'
            if len(new_name) != len(q.name):
                raise Fail(f'the title id is not the same length as {q.name}')
            body = bytearray(b[child[1]:child[2]])
            struct.pack_into('<H', body, 0, new_cid + 1)
            at = body.find(q.name.encode('latin-1'))
            if at < 0:
                raise Fail(f'cannot find {q.name} in the title sprite')
            body[at:at + len(new_name)] = new_name.encode('latin-1')
            title_cid, title_old, title_body = new_cid + 1, cid, bytes(body)
            break
        if title_cid:
            break
    if not title_cid:
        raise Fail('no title StaticText found in the clone')

    # The Defaults label slot (Item_6_0) moves up to the first slot after the section's rows.
    drop_names = set(drop)
    rows_y, label_depth = {}, None
    for code, _h, s, e in tags(b, cs + 4, ce):
        if code == PLACE2:
            p = Place2(b, s, e)
            if p.name in ('Item_0_0', 'Item_1_0') and p.mat:
                rows_y[p.name] = p.mat.ty
            if p.name == 'Item_6_0':
                label_depth = p.depth
    if label_depth is None or len(rows_y) != 2:
        raise Fail('the donor has no Item_6_0 label slot, or no two rows')
    label_dy = (rows_y['Item_1_0'] - rows_y['Item_0_0']) * (defaults_slot - 6)
    label_name = f'Item_{defaults_slot}_0'

    new_body = bytearray(struct.pack('<H', new_cid)) + b[cs + 2:cs + 4]
    for code, head, s, e in tags(b, cs + 4, ce):
        if code == PLACE2:
            p = Place2(b, s, e)
            named = bool(p.name)
            if named and p.name.startswith('StaticText'):
                continue
            if named and p.name in drop_names:
                continue
            if p.depth == label_depth and (label_dy or named):
                mat = p.mat.copy() if p.mat else None
                if mat:
                    mat.ty += label_dy
                new_body += tag_bytes(PLACE2, p.build(p.depth, mat, label_name if named else None))
                continue
        if place_char(b, s, code) == title_old:
            body = bytearray(b[s:e])
            struct.pack_into('<H', body, 4 if code == PLACE3 else 3, title_cid)
            new_body += tag_bytes(code, body)
            continue
        new_body += b[head:e]

    if not clone_p.mat:
        raise Fail(f'{clone} is placed without a matrix')
    section = tag_bytes(PLACE3, place3_hidden(new_cid, depth, clone_p.mat, name))
    top_s = places[top][2]
    out = bytearray(b[:body_start(b)])
    for code, head, s, e in tags(b, body_start(b), len(b)):
        out += b[head:e]
        if code == DEFINE_SPRITE and s == cs:
            out += tag_bytes(DEFINE_SPRITE, title_body)
            out += tag_bytes(DEFINE_SPRITE, new_body)
        elif code == PLACE2 and s == top_s:
            out += section
    out = bytes(out)
    if (clone_p.cid or 0) in names:
        out = add_symbol_class(out, new_cid, names[clone_p.cid]) or out
    return set_size(out)


def placement(b, code, s):
    """(depth, character, matrix (sx, sy, r0, r1, tx, ty) or None, name) of a placement."""
    flags = b[s]
    i = s + 1
    flags3 = 0
    if code == PLACE3:
        flags3 = b[i]
        i += 1
    depth = u16(b, i)
    i += 2
    if code == PLACE3 and ((flags3 & 0x08) or ((flags3 & 0x10) and (flags & 0x02))):
        _, i = cstr(b, i)
    cid = None
    if flags & 0x02:
        cid = u16(b, i)
        i += 2
    mat = None
    if flags & 0x04:
        r = BitReader(b, i)
        sx = sy = 1.0
        r0 = r1 = 0.0
        if r.u(1):
            n = r.u(5)
            sx, sy = r.s(n) / 65536.0, r.s(n) / 65536.0
        if r.u(1):
            n = r.u(5)
            r0, r1 = r.s(n) / 65536.0, r.s(n) / 65536.0
        n = r.u(5)
        mat = (sx, sy, r0, r1, r.s(n), r.s(n))
        i = r.align()
    if flags & 0x08:
        i = skip_cxform(b, i)
    if flags & 0x10:
        i += 2
    name = cstr(b, i)[0] if flags & 0x20 else None
    return depth, cid, mat, name


def translate_matrix(tx, ty):
    w = BitWriter()
    n = max(sbits(tx), sbits(ty))
    mask = (1 << n) - 1
    w.u(0, 2), w.u(n, 5), w.u(tx & mask, n), w.u(ty & mask, n)
    return w.out()


def add_scrollbar(b, list_name, ax, ay, name='ScrollBarV'):
    sprites, order = {}, []
    for code, head, s, e in tags(b, body_start(b), len(b)):
        if code == DEFINE_SPRITE:
            cid = u16(b, s)
            if cid not in sprites:
                order.append(cid)
            sprites[cid] = (head, s, e)
    target = None
    for code, _h, s, _e in tags(b, body_start(b), len(b)):
        if code in (PLACE2, PLACE3):
            p = placement(b, code, s)
            if p[3] == list_name:
                target = p
                break
    if not target or target[1] is None or target[1] not in sprites:
        raise Fail(f'no main-timeline sprite named {list_name}')
    sx, sy, r0, r1, ltx, lty = target[2] or (1.0, 1.0, 0.0, 0.0, 0, 0)
    if r0 or r1:
        raise Fail(f'{list_name} is rotated')
    donor = None
    for cid in order:
        _h, s, e = sprites[cid]
        for code, _h2, s2, _e2 in tags(b, s + 4, e):
            if code in (PLACE2, PLACE3):
                p = placement(b, code, s2)
                if p[3] == name and p[1] is not None:
                    donor = p[1]
                    break
        if donor is not None:
            break
    if donor is None:
        raise Fail(f'no {name} anywhere to reuse')
    head, ls, le = sprites[target[1]]
    depths, first_show = [], None
    for code, h, s, _e in tags(b, ls + 4, le):
        if code in (PLACE2, PLACE3):
            p = placement(b, code, s)
            depths.append(p[0])
            if p[3] == name:
                raise Fail(f'{list_name} already has a {name}')
        if code == SHOW_FRAME and first_show is None:
            first_show = h
    if first_show is None:
        raise Fail(f'{list_name} has no frames')
    depth = max(depths, default=0) + 1
    tx = round((ax * 20 - ltx) / sx)  # Python rounds half to even, as bbhost's nearbyint does
    ty = round((ay * 20 - lty) / sy)
    place = bytes([0x02 | 0x04 | 0x20]) + struct.pack('<HH', depth, donor) + translate_matrix(tx, ty) + \
        name.encode('latin-1') + b'\0'
    sprite = b[ls:first_show] + tag_bytes(PLACE2, place) + b[first_show:le]
    return set_size(b[:head] + tag_bytes(DEFINE_SPRITE, sprite) + b[le:])


def add_list_slot(b, list_name):
    """One more line in a command list: the sprite placed as `list_name` gets an Item_<n>_0
    placed like its last one, one pitch further down, at a free depth. The menu counts a list's
    lines from its Item_*_0 children. (The title's CommandList: Item_0_0..Item_4_0.)"""
    sprites = {u16(b, s): (head, s, e) for code, head, s, e in tags(b, body_start(b), len(b))
               if code == DEFINE_SPRITE}
    list_cid = None
    for cid in sorted(sprites):
        _h, s, e = sprites[cid]
        for code, _h2, s2, _e2 in tags(b, s + 4, e):
            if code in (PLACE2, PLACE3):
                p = placement(b, code, s2)
                if p[3] == list_name and p[1] is not None:
                    list_cid = p[1]
        if list_cid is not None:
            break
    if list_cid is None or list_cid not in sprites:
        raise Fail(f'no sprite placed as {list_name}')
    head, ls, le = sprites[list_cid]
    rows, depths, first_show = {}, set(), None
    for code, h, s, e in tags(b, ls + 4, le):
        if code == PLACE2:
            p = Place2(b, s, e)
            depths.add(p.depth)
            if p.name and p.name.startswith('Item_') and p.name.endswith('_0') and p.mat:
                rows[int(p.name[5:-2])] = p
        elif code == PLACE3:
            depths.add(u16(b, s + 2))
        if code == SHOW_FRAME and first_show is None:
            first_show = h
    if len(rows) < 2 or first_show is None:
        raise Fail(f'{list_name} has fewer than two Item_*_0 rows')
    order = sorted(rows)
    last, prev = rows[order[-1]], rows[order[-2]]
    mat = last.mat.copy()
    mat.ty += last.mat.ty - prev.mat.ty
    place = last.build(max(depths) + 1, mat, f'Item_{order[-1] + 1}_0')
    sprite = b[ls:first_show] + tag_bytes(PLACE2, place) + b[first_show:le]
    return set_size(b[:head] + tag_bytes(DEFINE_SPRITE, sprite) + b[le:])


def build_option_movie(source):
    movie = bytes(source)
    for name, title, depth, defaults_slot, drop in SECTIONS:
        movie = add_option_section(movie, name, title, depth, defaults_slot, drop)
    return add_scrollbar(movie, 'Top', *SCROLLBAR_AT)


# --- Messages --------------------------------------------------------------------------------

MENU_TEXT, LINE_HELP, EVENT_TEXT, DIALOG_TEXT, SCREEN_DIALOG_TEXT = 200, 0xc9, 30, 78, 0xcc
FIRST_EVENT_ID, LAST_EVENT_ID = 14000332, 14000399
FIRST_DIALOG_ID, LAST_DIALOG_ID = 920000, 929999
# Which ids each group carries: menu rows, event text, or dialog questions.
GROUP_KIND = {MENU_TEXT: 'menu', LINE_HELP: 'menu', EVENT_TEXT: 'event', DIALOG_TEXT: 'dialog',
              SCREEN_DIALOG_TEXT: 'dialog'}


def message_kind(mid):
    if FIRST_EVENT_ID <= mid <= LAST_EVENT_ID:
        return 'event'
    return 'dialog' if FIRST_DIALOG_ID <= mid <= LAST_DIALOG_ID else 'menu'


def fmg_read(b):
    """{id: UTF-16LE bytes or None} of a version-2 FMG."""
    if len(b) < 0x28 or b[2] != 2:
        raise Fail('an FMG that is not version 2')
    groups, strings = u32(b, 0x0c), u32(b, 0x10)
    offsets = struct.unpack_from('<Q', b, 0x18)[0]
    ids = {}
    for g in range(groups):
        index, first, last = struct.unpack_from('<iii', b, 0x28 + g * 16)
        for k, mid in enumerate(range(first, last + 1)):
            if index + k >= strings:
                raise Fail('an FMG group past its strings')
            at = struct.unpack_from('<Q', b, offsets + (index + k) * 8)[0]
            if not at:
                ids[mid] = None
                continue
            end = at
            while end + 1 < len(b) and b[end:end + 2] != b'\0\0':
                end += 2
            if end + 1 >= len(b):
                raise Fail('an unterminated FMG string')
            ids[mid] = bytes(b[at:end])
    return ids


def fmg_write(ids):
    order = sorted(ids)
    groups, start = [], 0
    for i in range(1, len(order) + 1):
        if i == len(order) or order[i] != order[i - 1] + 1:
            groups.append((start, order[start], order[i - 1]))
            start = i
    strings, pool = {}, bytearray()
    for mid in order:
        text = ids[mid]
        if text is None or text in strings:
            continue
        strings[text] = len(pool)
        pool += text + b'\0\0'
    offsets = 0x28 + len(groups) * 16
    body = offsets + len(order) * 8
    out = bytearray(body + len(pool))
    out[2] = 2
    struct.pack_into('<IIII', out, 0x08, 1, len(groups), len(order), 0xff)
    struct.pack_into('<Q', out, 0x18, offsets)
    for g, (index, first, last) in enumerate(groups):
        struct.pack_into('<iii', out, 0x28 + g * 16, index, first, last)
    for i, mid in enumerate(order):
        text = ids[mid]
        struct.pack_into('<Q', out, offsets + i * 8, 0 if text is None else body + strings[text])
    out[body:] = pool
    struct.pack_into('<I', out, 0x04, len(out))
    return bytes(out)


def read_messages(path=MESSAGES):
    """{id: (text, help)} from the TSV."""
    rows = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 2:
            raise Fail(f'pc_menu_messages: a row without text: {line}')
        text = parts[1].replace('\\n', '\n')
        help_text = parts[2].replace('\\n', '\n') if len(parts) > 2 else ''
        rows[int(parts[0])] = (text, help_text)
    return rows


def build_menu_messages(packed, rows):
    """The message bundle with the menu's ids: menu text and line help, event text and the
    dialog questions."""
    archive = Bnd4(dcx_decompress(packed))
    groups = {}
    for i, file_id in enumerate(archive.ids):
        if file_id in GROUP_KIND:
            groups[file_id] = i
    if set(groups) != set(GROUP_KIND):
        raise Fail('the message bundle lacks the menu, line help, event or dialog text group')
    for file_id, index in groups.items():
        wanted = {mid: row for mid, row in rows.items() if message_kind(mid) == GROUP_KIND[file_id]}
        ids = fmg_read(archive.files[index])
        clash = sorted(set(wanted) & set(ids))
        if clash:
            raise Fail(f'message id {clash[0]} is already in group {file_id}')
        for mid, (text, help_text) in wanted.items():
            value = help_text if file_id == LINE_HELP else text
            ids[mid] = value.encode('utf-16-le') if value else None
        archive.files[index] = fmg_write(ids)
    return dcx_compress(archive.to_bytes(), template=packed)


def make(dvdroot, log=print):
    """{relative path: bytes} of the menu's assets, or {} when the game's files are not the
    expected ones (the menu then stays off)."""
    dvdroot = Path(dvdroot)
    rows = read_messages()
    try:
        files = {MOVIE: build_option_movie((dvdroot / MOVIE).read_bytes())}
    except (OSError, FormatError, IndexError, struct.error) as error:
        log(f'PC menu: off - {MOVIE.as_posix()}: {error}')
        return {}
    languages = sorted(p.name for p in (dvdroot / 'msg').iterdir() if (p / MESSAGE_FILE).is_file()) \
        if (dvdroot / 'msg').is_dir() else []
    for language in languages:
        relative = Path('msg') / language / MESSAGE_FILE
        try:
            files[relative] = build_menu_messages((dvdroot / relative).read_bytes(), rows)
        except (OSError, FormatError, IndexError, struct.error) as error:
            log(f'PC menu: off - {relative.as_posix()}: {error}')
            return {}
    if not languages:
        log('PC menu: off - the game has no msg/*/menu.msgbnd.dcx')
        return {}
    # Quit Game on the title: both title movies, or neither (the row needs its line).
    try:
        titles = {relative: add_list_slot((dvdroot / relative).read_bytes(), 'CommandList')
                  for relative in TITLE_MOVIES}
        files.update(titles)
    except (OSError, FormatError, IndexError, struct.error) as error:
        log(f'PC menu: no Quit Game on the title - {error}')
    return files
