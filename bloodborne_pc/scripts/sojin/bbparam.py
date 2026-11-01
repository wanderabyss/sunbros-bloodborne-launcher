# SPDX-License-Identifier: GPL-2.0-or-later
"""Bloodborne PARAM / PARAMDEF (format 201, unicode) and FMG reader-writer, for the Twin Chikage mod."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fromsoft import dcx_decompress, dcx_compress, Bnd4

GAME = ""  # the dump's dvdroot_ps4 folder, with a trailing slash: weapon.set_game() sets it
SIZES = {"s8": 1, "u8": 1, "s16": 2, "u16": 2, "s32": 4, "u32": 4, "f32": 4, "dummy8": 1, "fixstr": 1, "fixstrW": 2}
FMT = {"s8": "b", "u8": "B", "s16": "h", "u16": "H", "s32": "i", "u32": "I", "f32": "f"}


def load_paramdefs():
    bnd = Bnd4(dcx_decompress(open(GAME + "paramdef/paramdef.paramdefbnd.dcx", "rb").read()))
    defs = {}
    for data in bnd.files:
        ptype = data[0x0C:0x2C].split(b"\0")[0].decode()
        count, fsize = struct.unpack_from("<hh", data, 8)
        start, = struct.unpack_from("<q", data, 0x30)
        fields = []
        for i in range(count):
            at = start + i * fsize
            # The display type is the storage type; the internal type may name an enum.
            itype = data[at + 0x40:at + 0x48].split(b"\0")[0].decode()
            iname = data[at + 0x90:at + 0xB0].split(b"\0")[0].decode()
            fields.append((itype, iname))
        defs[ptype] = layout(fields)
    return defs


def layout(fields):
    """(name, type, byte offset, bit offset or None, bit count or array length)."""
    out, off, bitunit, bitpos = [], 0, None, 0
    for itype, iname in fields:
        m = re.match(r"\s*(\w+)\s*(?::\s*(\d+))?\s*(?:\[\s*(\d+)\s*\])?", iname)
        if not m:
            raise ValueError(f"field name {iname!r}")
        name, bits, arr = m.group(1), m.group(2), m.group(3)
        size = SIZES[itype]
        if bits is not None:
            bits = int(bits)
            if bitunit is not None and bitunit[1] == size and bitpos + bits <= size * 8:
                pass
            else:
                bitunit = (off, size); bitpos = 0; off += size
            out.append((name, itype, bitunit[0], bitpos, bits))
            bitpos += bits
            continue
        bitunit = None
        n = int(arr) if arr else 1
        out.append((name, itype, off, None, n))
        off += size * n
    return out


class Param:
    def __init__(self, data, fields):
        self.raw = data
        self.fields = fields
        self.header = bytearray(data[:0x40])
        count, = struct.unpack_from("<H", data, 0x0A)
        rows = []
        for i in range(count):
            rid, _, doff, noff = struct.unpack_from("<iiqq", data, 0x40 + i * 24)
            rows.append([rid, doff, noff])
        self.rowsize = rows[1][1] - rows[0][1]
        name_start = min(r[2] for r in rows)
        self.rows = {}
        self.names = {}
        self.order = []
        # Format2E bit 1: row names are UTF-16 (repacked params), else Shift JIS.
        self.wide = bool(self.header[0x2E] & 2)
        for rid, doff, noff in rows:
            self.rows[rid] = bytearray(data[doff:doff + self.rowsize])
            end = noff
            if self.wide:
                while data[end:end + 2] != b"\0\0":
                    end += 2
            else:
                while data[end] != 0:
                    end += 1
            self.names[rid] = data[noff:end]
            self.order.append(rid)

    def name(self, rid):
        return self.names[rid].decode("utf-16-le" if self.wide else "shift_jis", "replace")

    def get(self, rid, name):
        row = self.rows[rid]
        for fname, itype, off, bit, n in self.fields:
            if fname == name:
                if bit is not None:
                    v = int.from_bytes(row[off:off + SIZES[itype]], "little")
                    return (v >> bit) & ((1 << n) - 1)
                if itype in ("dummy8", "fixstr", "fixstrW"):
                    return bytes(row[off:off + n * SIZES[itype]])
                return struct.unpack_from("<" + FMT[itype], row, off)[0]
        raise KeyError(name)

    def set(self, rid, name, value):
        row = self.rows[rid]
        for fname, itype, off, bit, n in self.fields:
            if fname == name:
                if bit is not None:
                    size = SIZES[itype]
                    v = int.from_bytes(row[off:off + size], "little")
                    mask = ((1 << n) - 1) << bit
                    v = (v & ~mask) | ((int(value) << bit) & mask)
                    row[off:off + size] = v.to_bytes(size, "little")
                else:
                    struct.pack_into("<" + FMT[itype], row, off, value)
                return
        raise KeyError(name)

    def dump(self, rid):
        return {f[0]: self.get(rid, f[0]) for f in self.fields if f[1] not in ("dummy8", "fixstr", "fixstrW")}

    def add(self, rid, src, name=""):
        assert rid not in self.rows
        self.rows[rid] = bytearray(self.rows[src])
        self.names[rid] = name.encode("utf-16-le" if self.wide else "shift_jis")
        self.order.append(rid)

    def to_bytes(self):
        ids = sorted(self.order)
        n = len(ids)
        data_start = 0x40 + n * 24
        data_start = (data_start + 0xF) & ~0xF
        body = b"".join(bytes(self.rows[i]) for i in ids)
        name_start = data_start + len(body)
        # Identical names share one string, as in the game's own files.
        names, name_offs, seen = bytearray(), [], {}
        for i in ids:
            if self.names[i] not in seen:
                seen[self.names[i]] = name_start + len(names)
                names += self.names[i] + (b"\0\0" if self.wide else b"\0")
            name_offs.append(seen[self.names[i]])
        head = bytearray(self.header)
        struct.pack_into("<I", head, 0, name_start)
        struct.pack_into("<H", head, 0x0A, n)
        struct.pack_into("<I", head, 0x30, data_start)
        rows = bytearray()
        for k, i in enumerate(ids):
            rows += struct.pack("<iiqq", i, 0, data_start + k * self.rowsize, name_offs[k])
        out = head + rows
        out += b"\0" * (data_start - len(out))
        return bytes(out + body + names)


class Fmg:
    """FMG version 2 (Bloodborne): 64-bit offsets, UTF-16."""
    def __init__(self, data):
        self.raw = data
        self.version = data[2]
        count_groups, count_strings = struct.unpack_from("<ii", data, 0x0C)
        str_offsets_at, = struct.unpack_from("<q", data, 0x18)
        self.entries = {}
        for g in range(count_groups):
            idx, first, last, _ = struct.unpack_from("<iiii", data, 0x28 + g * 16)
            for k, sid in enumerate(range(first, last + 1)):
                so, = struct.unpack_from("<q", data, str_offsets_at + (idx + k) * 8)
                if so <= 0:
                    self.entries[sid] = None
                    continue
                end = so
                while data[end:end + 2] != b"\0\0":
                    end += 2
                self.entries[sid] = data[so:end].decode("utf-16-le")

    def to_bytes(self):
        ids = sorted(self.entries)
        groups = []
        for sid in ids:
            if groups and groups[-1][2] == sid - 1:
                groups[-1][2] = sid
            else:
                groups.append([len([0 for g in groups for _ in range(g[1], g[2] + 1)]), sid, sid])
        n = len(ids)
        str_off_at = 0x28 + len(groups) * 16
        str_start = str_off_at + n * 8
        strings, offs = bytearray(), []
        for sid in ids:
            s = self.entries[sid]
            if s is None:
                offs.append(0)
            else:
                offs.append(str_start + len(strings))
                strings += s.encode("utf-16-le") + b"\0\0"
        # The game's FMGs end 4-aligned plus 4 zero bytes.
        while len(strings) % 4:
            strings += b"\0"
        strings += b"\0" * 4
        head = bytearray(self.raw[:0x28])
        total = str_start + len(strings)
        struct.pack_into("<i", head, 4, total)
        struct.pack_into("<ii", head, 0x0C, len(groups), n)
        struct.pack_into("<q", head, 0x18, str_off_at)
        out = head
        for idx, first, last in groups:
            out += struct.pack("<iiii", idx, first, last, 0)
        for o in offs:
            out += struct.pack("<q", o)
        return bytes(out + strings)


def open_bnd(path):
    raw = open(path, "rb").read()
    return raw, Bnd4(dcx_decompress(raw))


def save_bnd(path, bnd, template):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(dcx_compress(bnd.to_bytes(), template))
