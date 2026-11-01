# SPDX-License-Identifier: GPL-2.0-or-later
"""Read and write BND4 archives as Bloodborne ships them (chr/c0000.anibnd.dcx and its split
animation archives c0000_*.anibnd.dcx), with files added, replaced or removed.

    raw, bnd = load(GAME + "chr/c0000.anibnd.dcx")
    add_tae(bnd, 157, tae_bytes)            # chr\\c0000\\tae\\a157.tae, file id 5000157
    save(bnd, out_path, raw)                # DCX with the original's header

Unchanged archives come back byte for byte (test_roundtrip()): the BND4 header is kept and
only the counts and offsets that follow from the file list are recomputed; file headers keep
their flags and ids; names, data alignment and order follow the original layout:

  0x00  header (0x40): "BND4", flags, file count (0x0C), 0x40, version "07D7R6", file header
        size (0x20), end of headers+names (0x28), unicode (0x30), format (0x31),
        extended (0x32: 4 = a name hash table follows the names), hash table offset (0x38)
  0x40  file headers, 0x24 bytes each for format 0x74/0x54: u8 flags, 3 x 0, i32 -1,
        i64 stored size, i64 size, u32 data offset, i32 id, u32 name offset
        (0x18 / 0x20 byte layouts are handled too)
  then  names in file order (UTF-16 or Shift JIS, zero-terminated)
  then  [hash table, when extended == 4]
  then  data in file order (the game's archives are sorted by id), every non-empty file
        aligned to 0x10; an empty file's offset is the position where it would go, unaligned

DCX: the game's zlib streams were made by a stronger deflate than Python's zlib, so a rebuilt
archive's compressed bytes differ even when its content does not; save() therefore writes the
original DCX bytes back when the archive is unchanged and otherwise a DFLT DCX with the
original header (only the sizes change). The game reads either.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fromsoft import dcx_decompress, dcx_compress  # noqa: E402

GAME = ""  # the dump's dvdroot_ps4 folder, with a trailing slash: weapon.set_game() sets it
TAE_DIR = "N:\\SPRJ\\data\\INTERROOT_ps4\\chr\\c0000\\tae\\"
TAE_FILE_ID = 5000000          # file id of aNNN.tae = 5000000 + NNN
HKX_DIR = "N:\\SPRJ\\data\\INTERROOT_ps4\\chr\\c0000\\hkx\\"
HKX_FILE_ID = 1000000000       # file id of aTTT_AAAAAA.hkx = 1000000000 + TTT*1000000 + AAAAAA


class FormatError(ValueError):
    pass


# File header layouts by size: (stored size at, size at or None, offset at, id at or None).
_LAYOUTS = {0x24: (0x08, 0x10, 0x18, 0x1C), 0x20: (0x08, 0x10, 0x18, None), 0x18: (0x08, None, 0x10, None)}


def path_hash(name):
    """FromSoftware's file name hash (BND4/BHD5 hash tables): lower case, '/' separators,
    leading '/', h = h*37 + c over the characters, 32 bits."""
    s = name.replace("\\", "/").lower()
    if not s.startswith("/"):
        s = "/" + s
    h = 0
    for ch in s:
        h = (h * 37 + ord(ch)) & 0xFFFFFFFF
    return h


def _next_prime(n):
    def prime(k):
        if k < 2:
            return False
        i = 2
        while i * i <= k:
            if k % i == 0:
                return False
            i += 1
        return True
    while not prime(n):
        n += 1
    return n


def hash_table(names, at):
    """A BND4 name hash table (SoulsFormats BinderHashTable layout) for a table starting at
    `at`. Not exercised by Bloodborne: no BND4 the game ships has one (all have extended 0)."""
    count = len(names)
    groups_n = 0
    if count:
        groups_n = _next_prime(max(count // 7, 1))
    buckets = [[] for _ in range(groups_n)]
    for i, n in enumerate(names):
        h = path_hash(n)
        buckets[h % groups_n].append((h, i))
    out = bytearray()
    out += struct.pack("<q", 0)
    out += struct.pack("<q", 0)            # hashes offset, filled below
    out += struct.pack("<Ii", groups_n, 0x00080810)
    index = 0
    for b in buckets:
        out += struct.pack("<ii", len(b), index)
        index += len(b)
    struct.pack_into("<q", out, 8, at + len(out))
    for b in buckets:
        for h, i in b:
            out += struct.pack("<Ii", h, i)
    return bytes(out)


class Entry:
    def __init__(self, id, name, data, flags=0x40, extra=-1):
        self.id = id
        self.name = name
        self.data = bytes(data)
        self.flags = flags
        self.extra = extra      # the i32 after the flags (-1 in every game file)

    @property
    def basename(self):
        return self.name.replace("/", "\\").split("\\")[-1]

    def __repr__(self):
        return f"Entry({self.id}, {self.basename}, {len(self.data)} bytes)"


class Bnd4Archive:
    def __init__(self, data):
        data = bytes(data)
        if data[:4] != b"BND4":
            raise FormatError("not a BND4 archive")
        if data[8]:
            raise FormatError("big-endian BND4 is unsupported")
        self._original = data
        self.header = bytearray(data[:0x40])
        count, = struct.unpack_from("<i", data, 0x0C)
        self.header_size, = struct.unpack_from("<q", data, 0x20)
        if self.header_size not in _LAYOUTS:
            raise FormatError(f"unsupported file header size {self.header_size:#x}")
        self.unicode = bool(data[0x30])
        self.format = data[0x31]
        self.extended = data[0x32]
        size_at, raw_at, off_at, id_at = _LAYOUTS[self.header_size]
        self.entries = []
        offsets = []
        for i in range(count):
            at = 0x40 + i * self.header_size
            flags = data[at]
            if data[at + 1:at + 4] != b"\0\0\0":
                raise FormatError("file header padding is not zero")
            extra, = struct.unpack_from("<i", data, at + 4)
            size, = struct.unpack_from("<q", data, at + size_at)
            if raw_at is not None and struct.unpack_from("<q", data, at + raw_at)[0] != size:
                raise FormatError("compressed entries are unsupported")
            off, = struct.unpack_from("<I", data, at + off_at)
            fid = struct.unpack_from("<i", data, at + id_at)[0] if id_at is not None else None
            name_at, = struct.unpack_from("<I", data, at + self.header_size - 4)
            self.entries.append(Entry(fid, self._name(data, name_at), data[off:off + size], flags, extra))
            offsets.append(off)
        if offsets != sorted(offsets):
            raise FormatError("file data is not in file order")
        self.hash_raw = None
        if self.extended == 4:
            ht, = struct.unpack_from("<q", data, 0x38)
            self.hash_raw = data[ht:(min(offsets) if offsets else len(data))]

    def _name(self, data, at):
        if self.unicode:
            end = at
            while data[end:end + 2] != b"\0\0":
                end += 2
            return data[at:end].decode("utf-16-le")
        end = data.index(b"\0", at)
        return data[at:end].decode("shift_jis")

    # -------------------------------------------------------------- editing
    def find(self, name=None, id=None):
        for e in self.entries:
            if id is not None and e.id == id:
                return e
            if name is not None and e.basename.casefold() == name.replace("/", "\\").split("\\")[-1].casefold():
                return e
        return None

    def add(self, entry, replace=False):
        """Add an entry, keeping the file list sorted by id (as every game archive is)."""
        old = self.find(id=entry.id) or self.find(name=entry.name)
        if old is not None:
            if not replace:
                raise FormatError(f"{entry.basename} / id {entry.id} already in the archive")
            self.entries.remove(old)
        self.entries.append(entry)
        self.entries.sort(key=lambda e: (e.id if e.id is not None else 0))
        return entry

    def remove(self, name=None, id=None):
        e = self.find(name, id)
        if e is not None:
            self.entries.remove(e)
        return e

    # -------------------------------------------------------------- writing
    def to_bytes(self):
        n = len(self.entries)
        names = bytearray()
        names_at = 0x40 + n * self.header_size
        name_offs = []
        for e in self.entries:
            name_offs.append(names_at + len(names))
            names += e.name.encode("utf-16-le") + b"\0\0" if self.unicode else e.name.encode("shift_jis") + b"\0"
        headers_end = names_at + len(names)
        ht = b""
        if self.extended == 4:
            unchanged = (self.hash_raw is not None and
                         [x.name for x in self.entries] == [x.name for x in Bnd4Archive(self._original).entries])
            # The table follows the names, aligned to 8.
            ht_at = (headers_end + 7) & ~7
            ht = self.hash_raw if unchanged else hash_table([x.name for x in self.entries], ht_at)
            ht = b"\0" * (ht_at - headers_end) + ht
        head = bytearray(self.header)
        struct.pack_into("<i", head, 0x0C, n)
        struct.pack_into("<q", head, 0x28, headers_end)
        if self.extended == 4:
            struct.pack_into("<q", head, 0x38, (headers_end + 7) & ~7)
        out = head + bytearray(n * self.header_size) + names + ht
        size_at, raw_at, off_at, id_at = _LAYOUTS[self.header_size]
        for i, e in enumerate(self.entries):
            # Empty files take the current position; the others start 0x10-aligned.
            while e.data and len(out) % 0x10:
                out.append(0)
            at = 0x40 + i * self.header_size
            out[at] = e.flags
            struct.pack_into("<i", out, at + 4, e.extra)
            struct.pack_into("<q", out, at + size_at, len(e.data))
            if raw_at is not None:
                struct.pack_into("<q", out, at + raw_at, len(e.data))
            struct.pack_into("<I", out, at + off_at, len(out))
            if id_at is not None:
                struct.pack_into("<i", out, at + id_at, e.id)
            struct.pack_into("<I", out, at + self.header_size - 4, name_offs[i])
            out += e.data
        return bytes(out)


def load(path):
    """(raw DCX bytes, Bnd4Archive) of a .dcx (or plain) BND4 file."""
    raw = open(path, "rb").read()
    return raw, Bnd4Archive(dcx_decompress(raw) if raw[:4] == b"DCX\0" else raw)


def save(bnd, path, template):
    """Write `bnd` as a DCX with the header of `template` (the original .dcx). An unchanged
    archive is written as the original bytes."""
    data = bnd.to_bytes()
    if template[:4] == b"DCX\0":
        out = template if dcx_decompress(template) == data else dcx_compress(data, template)
    else:
        out = data
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return out


def tae_entry(tae_number, data):
    """The c0000.anibnd entry of aNNN.tae (TAE id 2000+NNN inside the file)."""
    return Entry(TAE_FILE_ID + tae_number, f"{TAE_DIR}a{tae_number:02d}.tae" if tae_number < 100
                 else f"{TAE_DIR}a{tae_number}.tae", data, 0x40)


def add_tae(bnd, tae_number, data, replace=False):
    """Add aNNN.tae to c0000.anibnd. The TAE's own id field must be 2000 + NNN."""
    tid, = struct.unpack_from("<i", data, 0x50)
    if tid != 2000 + tae_number:
        raise FormatError(f"TAE id {tid} does not match a{tae_number}.tae (expected {2000 + tae_number})")
    return bnd.add(tae_entry(tae_number, data), replace)


def hkx_entry(tae_number, anim_id, data):
    """An entry of a split animation archive (c0000_*.anibnd.dcx): aTTT_AAAAAA.hkx."""
    name = f"a{tae_number:03d}_{anim_id:06d}.hkx"
    return Entry(HKX_FILE_ID + tae_number * 1000000 + anim_id, f"{HKX_DIR}a{tae_number:03d}\\{name}", data, 0x40)


def test_roundtrip(verbose=True):
    """Every c0000 animation archive (c0000.anibnd and the 14 split archives) and c0000.chrbnd
    rebuilt unchanged must equal the original BND4 bytes; c0000.anibnd with an added TAE must
    read back with that TAE and every other file unchanged; save() of an unchanged archive
    must give the original DCX bytes. Returns (passed, failed)."""
    import tempfile
    files = ["chr/c0000.anibnd.dcx", "chr/c0000.chrbnd.dcx"] + sorted(
        "chr/" + f for f in os.listdir(GAME + "chr") if f.startswith("c0000_") and f.endswith(".anibnd.dcx"))
    passed, failed = 0, []
    for rel in files:
        raw, bnd = load(GAME + rel)
        ok = bnd.to_bytes() == bnd._original
        if verbose:
            print(f"{rel:32} {len(bnd.entries):5} files  BND4 rebuild {'byte-identical' if ok else 'DIFFERS'}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + [rel])
    # Unchanged save = original DCX bytes; added TAE reads back.
    raw, bnd = load(GAME + "chr/c0000.anibnd.dcx")
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "c0000.anibnd.dcx")
        ok = save(bnd, p, raw) == raw and open(p, "rb").read() == raw
        if verbose:
            print(f"save() unchanged c0000.anibnd.dcx -> original DCX bytes: {ok}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + ["save-unchanged"])
        before = [(e.id, e.name, e.data) for e in bnd.entries]
        tae = bnd.find("a113.tae").data
        new = bytearray(tae)
        struct.pack_into("<i", new, 0x50, 2157)
        struct.pack_into("<ii", new, 0x90, 2157, 2157)
        add_tae(bnd, 157, bytes(new))
        save(bnd, p, raw)
        _, back = load(p)
        e = back.find("a157.tae")
        ok = (e is not None and e.id == 5000157 and e.data == bytes(new) and
              [(x.id, x.name, x.data) for x in back.entries if x.id != 5000157] == before and
              [x.id for x in back.entries] == sorted(x.id for x in back.entries) and
              back.to_bytes() == bnd.to_bytes())
        if verbose:
            print(f"add a157.tae, save, reload: {ok} ({len(back.entries)} files, new entry at index "
                  f"{[x.id for x in back.entries].index(5000157) if e else None})")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + ["add-tae"])
    # Hash-table writer self-check (no game BND4 has one, so only a synthetic test).
    syn = Bnd4Archive(bnd.to_bytes())
    syn.extended = 4
    syn.header[0x32] = 4
    syn.hash_raw = None
    data = syn.to_bytes()
    back = Bnd4Archive(data)
    ok = back.extended == 4 and [x.data for x in back.entries] == [x.data for x in syn.entries] and back.to_bytes() == data
    if verbose:
        print(f"synthetic hash-table archive writes and reads back: {ok}")
    passed, failed = (passed + 1, failed) if ok else (passed, failed + ["hash-table"])
    if verbose:
        print(f"anibnd round trip: {passed}/{passed + len(failed)} pass, failed {failed}")
    return passed, failed


if __name__ == "__main__":
    p, f = test_roundtrip()
    sys.exit(1 if f else 0)
