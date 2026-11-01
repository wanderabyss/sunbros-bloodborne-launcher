# SPDX-License-Identifier: GPL-2.0-or-later
"""Havok 2014 packfiles (hk_2014.1.0-r1, file version 11, 64-bit little endian) as Bloodborne's
player behaviour ships them in chr/c0000.anibnd.dcx, and the patch that registers new
animations of a weapon TAE in it.

    new_anibnd = patch_behavior(anibnd_bytes)          # TAE 157, the 6 moves a157 lacks

The player's moves are chosen by CustomManualSelectorGenerator nodes ("selectors", one per
animation id) in Behaviors/c0000.hkx: each lists one hkbClipGenerator per TAE id that has the
move (animation name aTTT_AAAAAA). The patch adds, for every selector of an animation id that
has a clip of the source TAE (a113) but none of the new TAE (a157), a copy of that a113 clip
named a157_AAAAAA. Every clip's animation name is also in Characters/c0000.hkx
(hkbCharacterStringData.animationNames, exactly the set of clip names) and its file name in
Export/c0000.hkx (hkbProjectStringData.animationFilenames); the patch appends the new names
there too.

Packfile edits never move existing bytes: new objects, strings and the grown arrays are
appended to the end of the __data__ section, the array's pointer (a local fixup) is pointed at
the new copy and its size/capacity raised; the old array storage stays in place, unreferenced.
So every existing object keeps its offset and bytes (apart from those size fields) and every
existing fixup stays (apart from the array pointers). Layout notes: moveset-notes.md.

Run this file for the tests: unmodified round trip of every packfile c0000 ships, patch, and a
before/after comparison of the object graphs.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anibnd  # noqa: E402

MAGIC = b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10"
FF_PAD = bytes([0xFF])          # fixup tables are padded with 0xFF
SECTION_HEADER = 0x40
BEHAVIOR_ID, CHARACTER_ID, PROJECT_ID = 7000500, 7000400, 7000300
# Selector (CustomManualSelectorGenerator) fields.
SEL_GENERATORS = 0x88          # hkArray<hkbGenerator*>: ptr (local fixup), i32 size, i32 capacity|flags
SEL_OFFSET_TYPE = 0x98         # 13 right weapon category, 14 left weapon, 11 idle category, 0 none
SEL_ANIM_ID = 0x9C
OFFSET_RIGHT_WEAPON = 13
# hkbNode / hkbClipGenerator fields.
NODE_NAME = 0x38               # hkStringPtr (local fixup)
CLIP_ANIMATION_NAME = 0x90     # hkStringPtr (local fixup)
DONT_DEALLOCATE = 0x80000000   # hkArray capacity flag of packfile arrays
NEW_TAE, SOURCE_TAE = 157, 113
MISSING = (40600, 40700, 41000, 41010, 41100, 47150)
PROJECT_PATH = "..\\..\\..\\Model\\chr\\c0000\\hkx\\a{tae:03d}\\a{tae:03d}_{anim:06d}.hkx"


class FormatError(ValueError):
    pass


def _pad_to(buf, align, fill=b"\0"):
    while len(buf) % align:
        buf += fill


class Section:
    """One packfile section: its data and fixup tables (offsets relative to the section)."""

    def __init__(self, tag, data, local, glob, virtual, pads, exports, imports, tail):
        self.tag = tag
        self.data = bytearray(data)
        self.local = local          # [[src, dst]]
        self.glob = glob            # [[src, section, dst]]
        self.virtual = virtual      # [[object, classnames section, name offset]]
        self.pads = pads            # raw padding after each fixup table (0xFF bytes)
        self.exports = exports
        self.imports = imports
        self.tail = tail            # 16 bytes after the offsets in the section header


class Packfile:
    def __init__(self, raw):
        raw = bytes(raw)
        if raw[:8] != MAGIC:
            raise FormatError("not a Havok packfile")
        self.header = bytearray(raw[:0x40])
        version, = struct.unpack_from("<i", raw, 0x0C)
        if version != 11 or raw[0x10:0x14] != b"\x08\x01\x01\x01":
            raise FormatError(f"unsupported packfile version {version} / layout {raw[0x10:0x14].hex()}")
        count, = struct.unpack_from("<i", raw, 0x14)
        pred, = struct.unpack_from("<h", raw, 0x3E)
        self.predicates = raw[0x40:0x40 + pred]
        at = 0x40 + pred
        self.sections = []
        end_prev = at + count * SECTION_HEADER
        for i in range(count):
            h = at + i * SECTION_HEADER
            tag = raw[h:h + 0x14]
            start, lf, gf, vf, ex, im, end = struct.unpack_from("<7I", raw, h + 0x14)
            tail = raw[h + 0x30:h + 0x40]
            if start != end_prev:
                raise FormatError("sections are not contiguous")
            end_prev = start + end
            if not (lf <= gf <= vf <= ex <= im <= end):
                raise FormatError("section offsets out of order")

            def table(a, b, n):
                ents, k = [], a
                while k + 4 * n <= b and struct.unpack_from("<I", raw, start + k)[0] != 0xFFFFFFFF:
                    ents.append(list(struct.unpack_from(f"<{n}I", raw, start + k)))
                    k += 4 * n
                pad = raw[start + k:start + b]
                if pad.strip(b"\xff"):
                    raise FormatError(f"{tag!r}: data after the end of a fixup table")
                return ents, pad
            local, lp = table(lf, gf, 2)
            glob, gp = table(gf, vf, 3)
            virtual, vp = table(vf, ex, 3)
            self.sections.append(Section(tag, raw[start:start + lf], local, glob, virtual, (lp, gp, vp),
                                         raw[start + ex:start + im], raw[start + im:start + end], tail))
        if end_prev != len(raw):
            raise FormatError("data after the last section")
        self.classnames = next(s for s in self.sections if s.tag.startswith(b"__classnames__"))
        self.dataidx = next(i for i, s in enumerate(self.sections) if s.tag.startswith(b"__data__"))
        self.reindex()

    # -------------------------------------------------------------- indexes
    def reindex(self):
        s = self.sections[self.dataidx]
        self.local = {src: dst for src, dst in s.local}
        self.glob = {src: dst for src, sec, dst in s.glob if sec == self.dataidx}
        cn = self.classnames.data
        self.objects = {}
        for obj, sec, name in s.virtual:
            self.objects[obj] = bytes(cn[name:cn.index(b"\0", name)]).decode()
        self.order = sorted(self.objects)

    @property
    def data(self):
        return self.sections[self.dataidx].data

    def string(self, at):
        d = self.data
        return bytes(d[at:d.index(b"\0", at)]).decode("latin1")

    def ptr(self, src):
        """Target of the pointer at `src` (local or global fixup) or None."""
        if src in self.local:
            return self.local[src]
        return self.glob.get(src)

    def string_at(self, src):
        p = self.local.get(src)
        return self.string(p) if p is not None else None

    def object_end(self, obj):
        import bisect
        i = bisect.bisect_right(self.order, obj)
        return self.order[i] if i < len(self.order) else len(self.data)

    def of_class(self, name):
        return [o for o in self.order if self.objects[o] == name]

    def array(self, at):
        """(data offset or None, size, capacity field) of the hkArray at `at`."""
        size, cap = struct.unpack_from("<iI", self.data, at + 8)
        return self.local.get(at), size, cap

    def pointers(self, arr_at):
        """Targets of an hkArray<T*> at `arr_at`."""
        p, n, _ = self.array(arr_at)
        return [self.ptr(p + 8 * k) for k in range(n)] if p is not None else []

    # -------------------------------------------------------------- editing
    def append(self, blob, align=0x10):
        d = self.data
        _pad_to(d, align)
        at = len(d)
        d += blob
        _pad_to(d, align)
        return at

    def add_local(self, src, dst):
        self.sections[self.dataidx].local.append([src, dst])
        self.local[src] = dst

    def add_global(self, src, dst):
        self.sections[self.dataidx].glob.append([src, self.dataidx, dst])
        self.glob[src] = dst

    def add_object(self, obj, classname_offset):
        s = self.sections[self.dataidx]
        if s.virtual and obj <= s.virtual[-1][0]:
            raise FormatError("new objects must follow the existing ones")
        cn_sec = s.virtual[0][1]
        s.virtual.append([obj, cn_sec, classname_offset])
        cn = self.classnames.data
        self.objects[obj] = bytes(cn[classname_offset:cn.index(b"\0", classname_offset)]).decode()
        self.order.append(obj)

    def set_local(self, src, dst):
        for e in self.sections[self.dataidx].local:
            if e[0] == src:
                e[1] = dst
                self.local[src] = dst
                return
        raise FormatError(f"no local fixup at {src:#x}")

    def grow_array(self, arr_at, new_items, local_items=False):
        """Copy the hkArray at `arr_at` to the end of the data with `new_items` appended and
        point the array at the copy. Items are 8-byte pointers: global fixups (objects) or, with
        local_items, local fixups (strings). Existing items keep their targets."""
        old, n, cap = self.array(arr_at)
        targets = [self.ptr(old + 8 * k) for k in range(n)] if old is not None else []
        if None in targets:
            raise FormatError("array item without a fixup")
        targets += list(new_items)
        at = self.append(bytes(8 * len(targets)))
        for k, t in enumerate(targets):
            (self.add_local if local_items else self.add_global)(at + 8 * k, t)
        if old is None:
            self.add_local(arr_at, at)
        else:
            self.set_local(arr_at, at)
        flags = cap & 0xC0000000
        struct.pack_into("<iI", self.data, arr_at + 8, len(targets), len(targets) | flags)
        return at

    def clone_object(self, obj, rename):
        """Copy the object at `obj` with its own trailing data (strings, inline arrays) to the
        end of the data section; `rename(bytes)` rewrites the copied bytes after the object
        header region (its strings). Local pointers into the region are relocated, global ones
        (other objects) shared. Returns the new object's offset."""
        end = self.object_end(obj)
        blob = bytearray(self.data[obj:end])
        cls_off = next(v[2] for v in self.sections[self.dataidx].virtual if v[0] == obj)
        at = self.append(bytes(blob))
        new = rename(bytes(self.data[at:at + len(blob)]))
        if len(new) != len(blob):
            raise FormatError("renaming must keep the size")
        self.data[at:at + len(blob)] = new
        for src, dst in list(self.sections[self.dataidx].local):
            if obj <= src < end:
                if not obj <= dst < end:
                    raise FormatError(f"clone: local pointer at {src:#x} leaves the object")
                self.add_local(at + src - obj, at + dst - obj)
        for src, sec, dst in list(self.sections[self.dataidx].glob):
            if obj <= src < end:
                self.add_global(at + src - obj, dst)
        self.add_object(at, cls_off)
        return at

    # -------------------------------------------------------------- writing
    def to_bytes(self):
        """Header, section headers, then each section: data, local / global / virtual fixup
        tables (each padded to 0x10 with 0xFF), exports, imports."""
        out = bytearray(self.header)
        out += self.predicates
        heads_at = len(out)
        out += bytes(len(self.sections) * SECTION_HEADER)
        for i, s in enumerate(self.sections):
            start = len(out)
            body = bytearray(s.data)
            lf = len(body)
            for e in s.local:
                body += struct.pack("<2I", *e)
            _pad_to(body, 0x10, FF_PAD)
            gf = len(body)
            for e in s.glob:
                body += struct.pack("<3I", *e)
            _pad_to(body, 0x10, FF_PAD)
            vf = len(body)
            for e in s.virtual:
                body += struct.pack("<3I", *e)
            _pad_to(body, 0x10, FF_PAD)
            ex = len(body)
            body += s.exports
            im = len(body)
            body += s.imports
            h = heads_at + i * SECTION_HEADER
            out[h:h + 0x14] = s.tag
            struct.pack_into("<7I", out, h + 0x14, start, lf, gf, vf, ex, im, len(body))
            out[h + 0x30:h + 0x40] = s.tail
            out += body
        return bytes(out)


def read(raw):
    return Packfile(raw)


# ------------------------------------------------------------------ behaviour graph views
def selectors(pf):
    """[(offset, name, offsetType, animId, [generator offsets])] of every selector."""
    out = []
    for o in pf.of_class("CustomManualSelectorGenerator"):
        ot, aid = struct.unpack_from("<ii", pf.data, o + SEL_OFFSET_TYPE)
        out.append((o, pf.string_at(o + NODE_NAME), ot, aid, pf.pointers(o + SEL_GENERATORS)))
    return out


def clip_anim(pf, obj):
    if obj is None or pf.objects.get(obj) != "hkbClipGenerator":
        return None
    return pf.string_at(obj + CLIP_ANIMATION_NAME)


def name_array(pf, classname, pattern):
    """Offset of the hkArray<hkStringPtr> field of the (only) `classname` object whose strings
    match `pattern`; found by scanning the object's array fields."""
    objs = pf.of_class(classname)
    if len(objs) != 1:
        raise FormatError(f"{len(objs)} {classname} objects")
    o = objs[0]
    best = None
    for f in range(o, pf.object_end(o) - 15, 8):
        p, n, cap = pf.array(f)
        if p is None or n <= 0 or cap & 0x3FFFFFFF != n:
            continue
        first = pf.string_at(p)
        if first is not None and re.fullmatch(pattern, first):
            best = f
            break
    if best is None:
        raise FormatError(f"{classname}: no name array matching {pattern}")
    return best


def array_strings(pf, arr_at):
    p, n, _ = pf.array(arr_at)
    return [pf.string_at(p + 8 * k) for k in range(n)]


# ------------------------------------------------------------------ the patch
def plan_clips(beh, new_tae=NEW_TAE, source_tae=SOURCE_TAE, anim_ids=MISSING):
    """[(selector, source clip)] to add: each weapon selector of the animation ids that has a
    source-TAE clip and no new-TAE clip."""
    todo = []
    for o, name, ot, aid, gens in selectors(beh):
        if ot != OFFSET_RIGHT_WEAPON or aid not in anim_ids:
            continue
        names = [clip_anim(beh, g) for g in gens]
        want = f"a{new_tae:03d}_{aid:06d}"
        src = [g for g, n in zip(gens, names) if n == f"a{source_tae:03d}_{aid:06d}"]
        if want in names or not src:
            continue
        todo.append((o, src[0]))
    return todo


def patch_packfiles(beh_raw, chr_raw, prj_raw, new_tae=NEW_TAE, source_tae=SOURCE_TAE, anim_ids=MISSING):
    """(behaviour, character, project) packfile bytes with the new TAE's clips registered, and
    a report. Already-registered clips are left alone (the patch can run twice)."""
    beh, chr_, prj = read(beh_raw), read(chr_raw), read(prj_raw)
    todo = plan_clips(beh, new_tae, source_tae, anim_ids)
    old_tag, new_tag = f"a{source_tae:03d}_".encode(), f"a{new_tae:03d}_".encode()
    clones, report = {}, []
    for sel, src in todo:
        if src not in clones:
            clones[src] = beh.clone_object(src, lambda b: b.replace(old_tag, new_tag))
        beh.grow_array(sel + SEL_GENERATORS, [clones[src]])
        report.append((beh.string_at(sel + NODE_NAME), struct.unpack_from("<i", beh.data, sel + SEL_ANIM_ID)[0],
                       beh.string_at(clones[src] + NODE_NAME), clip_anim(beh, clones[src])))
    new_names = sorted({clip_anim(beh, c) for c in clones.values()})
    # Character animation names and project animation file names.
    ca = name_array(chr_, "hkbCharacterStringData", r"a\d{3}_\d{6}")
    have = set(array_strings(chr_, ca))
    add = [n for n in new_names if n not in have]
    if add:
        chr_.grow_array(ca, [chr_.append(n.encode() + b"\0") for n in add], local_items=True)
    pa = name_array(prj, "hkbProjectStringData", r".*\\a\d{3}_\d{6}\.hkx")
    have = set(array_strings(prj, pa))
    paths = [PROJECT_PATH.format(tae=int(n[1:4]), anim=int(n[5:])) for n in new_names]
    addp = [p for p in paths if p not in have]
    if addp:
        prj.grow_array(pa, [prj.append(p.encode() + b"\0") for p in addp], local_items=True)
    return beh.to_bytes(), chr_.to_bytes(), prj.to_bytes(), dict(clips=report, character_names=add, project_files=addp)


def patch_archive(bnd, new_tae=NEW_TAE, source_tae=SOURCE_TAE, anim_ids=MISSING):
    """Patch a c0000.anibnd Bnd4Archive in place; returns the report."""
    b, c, p = bnd.find(id=BEHAVIOR_ID), bnd.find(id=CHARACTER_ID), bnd.find(id=PROJECT_ID)
    b.data, c.data, p.data, report = patch_packfiles(b.data, c.data, p.data, new_tae, source_tae, anim_ids)
    return report


def patch_behavior(anibnd_bytes, new_tae=NEW_TAE, source_tae=SOURCE_TAE, anim_ids=MISSING):
    """c0000.anibnd bytes (DCX or plain BND4) -> the same kind of bytes with the clips of
    `anim_ids` registered for TAE `new_tae` (copied from `source_tae`'s clips). For build.py."""
    from fromsoft import dcx_decompress, dcx_compress
    is_dcx = anibnd_bytes[:4] == b"DCX\0"
    bnd = anibnd.Bnd4Archive(dcx_decompress(anibnd_bytes) if is_dcx else anibnd_bytes)
    patch_archive(bnd, new_tae, source_tae, anim_ids)
    data = bnd.to_bytes()
    return dcx_compress(data, anibnd_bytes) if is_dcx else data


# ------------------------------------------------------------------ checks
def compare(before, after):
    """Problems (list of str) in `after` against `before`, and the grown arrays. Every original
    object must keep its offset, class and bytes, except the size/capacity field of an array
    that grew; every original fixup must stay, except that a grown array's pointer may point
    at its new copy, whose leading items must target what the old items did; every new fixup
    and object must lie after the original data; other sections must be unchanged."""
    problems = []
    a, b = before, after
    sa, sb = a.sections[a.dataidx], b.sections[b.dataidx]
    end = len(a.data)
    grown = []
    for (s1, d1), (s2, d2) in zip(sa.local, sb.local):
        if s1 != s2:
            problems.append(f"local fixup order changed at {s1:#x}")
            break
        if d1 != d2:
            grown.append(s1)
            n1 = a.array(s1)[1]
            n2 = b.array(s1)[1]
            if d2 < end:
                problems.append(f"array at {s1:#x} repointed inside the original data")
            if n2 < n1 or [a.ptr(d1 + 8 * k) for k in range(n1)] != [b.ptr(d2 + 8 * k) for k in range(n1)]:
                problems.append(f"array at {s1:#x}: leading items differ")
    if len(sb.local) < len(sa.local):
        problems.append("local fixups lost")
    allowed = set()
    for g in grown:
        allowed.update(range(g + 8, g + 16))
    if bytes(b.data[:end]) != bytes(a.data):
        bad = [i for i in range(end) if a.data[i] != b.data[i] and i not in allowed]
        if bad:
            problems.append(f"{len(bad)} original data bytes changed, first at {bad[0]:#x}")
    for t in ("glob", "virtual"):
        x, y = getattr(sa, t), getattr(sb, t)
        if y[:len(x)] != x:
            problems.append(f"original {t} fixups changed")
        if any(e[0] < end for e in y[len(x):]):
            problems.append(f"new {t} fixup inside the original data")
    if any(e[0] < end for e in sb.local[len(sa.local):]):
        problems.append("new local fixup inside the original data")
    for o, c in a.objects.items():
        if b.objects.get(o) != c:
            problems.append(f"object {o:#x} {c} lost or changed class")
    for i, (s1, s2) in enumerate(zip(a.sections, b.sections)):
        if i != a.dataidx and (s1.data, s1.local, s1.glob, s1.virtual) != (s2.data, s2.local, s2.glob, s2.virtual):
            problems.append(f"section {i} changed")
    return problems, grown


def test(verbose=True):
    """Round trip of every packfile in c0000.anibnd/c0000.chrbnd (and the split archives'
    first 200 HKX), then the patch with full checks. Returns (passed, failed)."""
    import collections
    passed, failed = 0, []

    def check(ok, what):
        nonlocal passed
        if ok:
            passed += 1
        else:
            failed.append(what)
        if verbose:
            print(f"{'PASS' if ok else 'FAIL'}  {what}")

    raw, bnd = anibnd.load(anibnd.GAME + "chr/c0000.anibnd.dcx")
    for e in bnd.entries:
        if e.data[:8] == MAGIC:
            check(read(e.data).to_bytes() == e.data, f"round trip {e.basename} ({e.id}, {len(e.data)} bytes)")
    _, cb = anibnd.load(anibnd.GAME + "chr/c0000.chrbnd.dcx")
    for e in cb.entries:
        if e.data[:8] == MAGIC:
            check(read(e.data).to_bytes() == e.data, f"round trip chrbnd {e.basename}")
    n_ok = n = 0
    for f in ("c0000_a9x", "c0000_dlc"):
        _, sb = anibnd.load(anibnd.GAME + f"chr/{f}.anibnd.dcx")
        for e in [x for x in sb.entries if x.data[:8] == MAGIC][:100]:
            n += 1
            try:
                n_ok += read(e.data).to_bytes() == e.data
            except FormatError:
                pass
    check(n_ok == n, f"round trip of {n} animation HKX from c0000_a9x/c0000_dlc ({n_ok} identical)")

    beh_e, chr_e, prj_e = bnd.find(id=BEHAVIOR_ID), bnd.find(id=CHARACTER_ID), bnd.find(id=PROJECT_ID)
    before = read(beh_e.data)
    nb, nc, np_, rep = patch_packfiles(beh_e.data, chr_e.data, prj_e.data)
    after = read(nb)
    check(len(rep["clips"]) == 10 and len({r[3] for r in rep["clips"]}) == 6,
          f"added {len(rep['clips'])} clips to selectors: " + "; ".join(f"{r[0].split(' ')[0]}({r[1]})" for r in rep["clips"]))
    problems, grown = compare(before, after)
    check(not problems, f"behaviour graph before/after: {len(grown)} grown arrays, problems {problems[:5]}")
    # New clips equal their source clips but for the names.
    ok = True
    for o in after.order:
        if o < len(before.data):
            continue
        if after.objects[o] != "hkbClipGenerator":
            ok = False
            continue
        node = after.string_at(o + NODE_NAME).replace("a157_", "a113_")
        src = [s for s in before.of_class("hkbClipGenerator") if before.string_at(s + NODE_NAME) == node]
        if len(src) != 1:
            ok = False
            continue
        src = src[0]
        e1 = before.object_end(src)
        b1 = bytes(before.data[src:e1]).replace(b"a113_", b"a157_")
        if bytes(after.data[o:o + len(b1)]) != b1:
            ok = False
        loc1 = sorted((s - src, d - src) for s, d in before.local.items() if src <= s < e1)
        loc2 = sorted((s - o, d - o) for s, d in after.local.items() if o <= s < o + len(b1))
        glo1 = sorted((s - src, d) for s, d in before.glob.items() if src <= s < e1)
        glo2 = sorted((s - o, d) for s, d in after.glob.items() if o <= s < o + len(b1))
        ok &= loc1 == loc2 and glo1 == glo2 and after.string_at(o + NODE_NAME) == before.string_at(src + NODE_NAME).replace("a113_", "a157_")
    check(ok, "every new clip = its a113 clip (bytes, pointers, class) with a157 names")
    # Every one of the 61 combined animations has an a157 clip in each selector that holds
    # its source TAE's clip.
    import combine_moveset as cm
    import tae_write as tw
    taes = {113: tw.read(tw.game_taes()["a113.tae"]), 114: tw.read(tw.game_taes()["a114.tae"])}
    plan = cm.plan(taes[114], taes[113])
    src_of = {aid: (114 if t is taes[114] else 113) for aid, t in plan}
    sels = collections.defaultdict(list)
    for o, name, ot, aid, gens in selectors(after):
        if ot == OFFSET_RIGHT_WEAPON:
            sels[aid].append((name, [clip_anim(after, g) for g in gens]))
    missing = []
    for aid, src in sorted(src_of.items()):
        nodes = [(n, g) for n, g in sels[aid] if f"a{src}_{aid:06d}" in g]
        if not nodes or any(f"a157_{aid:06d}" not in g for n, g in nodes):
            missing.append(aid)
    check(not missing, f"all {len(src_of)} combined animations have an a157 clip in every selector "
                       f"that has their source clip (missing: {missing})")
    before_missing = [aid for aid in src_of if not any(f"a157_{aid:06d}" in g for n, g in
                      [(n, [clip_anim(before, x) for x in gens]) for o, n, ot, a, gens in selectors(before)
                       if ot == OFFSET_RIGHT_WEAPON and a == aid])]
    check(sorted(before_missing) == list(MISSING), f"before the patch exactly {sorted(before_missing)} lacked an a157 clip")
    # Character / project name lists.
    c0, c1 = read(chr_e.data), read(nc)
    p0, p1 = read(prj_e.data), read(np_)
    ca0, ca1 = name_array(c0, "hkbCharacterStringData", r"a\d{3}_\d{6}"), name_array(c1, "hkbCharacterStringData", r"a\d{3}_\d{6}")
    n0, n1 = array_strings(c0, ca0), array_strings(c1, ca1)
    clip_names = {clip_anim(after, c) for c in after.of_class("hkbClipGenerator")}
    check(n1[:len(n0)] == n0 and set(n1) == clip_names and len(n1) == len(n0) + 6,
          f"character animationNames {len(n0)} -> {len(n1)}, = the set of clip names: {set(n1) == clip_names}")
    pa0, pa1 = name_array(p0, "hkbProjectStringData", r".*\\a\d{3}_\d{6}\.hkx"), name_array(p1, "hkbProjectStringData", r".*\\a\d{3}_\d{6}\.hkx")
    q0, q1 = array_strings(p0, pa0), array_strings(p1, pa1)
    check(q1[:len(q0)] == q0 and len(q1) == len(q0) + 6, f"project animationFilenames {len(q0)} -> {len(q1)}: {q1[len(q0):][:2]}...")
    for x0, x1, what in ((c0, c1, "character"), (p0, p1, "project")):
        pr, _ = compare(x0, x1)
        check(not pr, f"{what} file before/after: problems {pr[:3]}")
    # Idempotent; and patch_behavior on the archive bytes.
    nb2, nc2, np2, rep2 = patch_packfiles(nb, nc, np_)
    check(not rep2["clips"] and not rep2["character_names"] and nb2 == nb and nc2 == nc and np2 == np_,
          "patching twice changes nothing")
    out = patch_behavior(raw)
    from fromsoft import dcx_decompress
    back = anibnd.Bnd4Archive(dcx_decompress(out))
    check(back.find(id=BEHAVIOR_ID).data == nb and back.find(id=CHARACTER_ID).data == nc and
          back.find(id=PROJECT_ID).data == np_ and
          all(x.data == y.data for x, y in zip(back.entries, bnd.entries) if x.id not in (BEHAVIOR_ID, CHARACTER_ID, PROJECT_ID)),
          f"patch_behavior(c0000.anibnd.dcx): {len(raw)} -> {len(out)} bytes, other files unchanged")
    if verbose:
        for r in rep["clips"]:
            print(f"      {r[0]:52} anim {r[1]}  + {r[2]} ({r[3]})")
        print(f"behaviour graph tests: {passed}/{passed + len(failed)} pass, failed {failed}")
    return passed, failed


if __name__ == "__main__":
    p, f = test()
    sys.exit(1 if f else 0)
