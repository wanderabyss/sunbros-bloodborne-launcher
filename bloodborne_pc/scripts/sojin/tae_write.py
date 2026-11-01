# SPDX-License-Identifier: GPL-2.0-or-later
"""Bloodborne TAE (version 0x1000C, 64-bit, little-endian; DS3 "TAE3" layout) reader and writer.

read(data) -> TaeFile; TaeFile.to_bytes() -> data. Every TAE the game ships in chr/c0000.anibnd.dcx
comes back byte for byte (test_roundtrip()). The layout is in moveset-notes.md; in short:

  header (0x00-0xD0), skeleton name, SIB name (UTF-16, each padded to 0x10)
  animation table: (q id, q offset of the animation's 0x30-byte body), sorted by id
  animation groups: q count, q offset, then (i first id, i last id, q table offset) per run of
    consecutive ids
  animation bodies: 0x30 bytes each (q events, q event groups, q times, q mini-header,
    i event count, i group count, i time count, i 0)
  then per animation, in order: mini-header (+ its UTF-16 .hkt name when it has one), times
  (f32, padded to 0x10), event headers (q start-time offset, q end-time offset, q data offset),
  event data (i type, i unk, q params offset, params, padded to 0x10), event group headers
  (q count, q values offset, q type-data offset, q 0), event group data (q type, q 0, then
  the member event-header offsets as i32, padded to 0x10).

Events keep their parameters as raw bytes (padding included), so anything the game reads from
them survives a copy unchanged. Run this file to test every TAE of the game.
"""
import bisect
import struct

HEADER_SIZE = 0xD0
ANIM_BODY_SIZE = 0x30
MINI_SIZE = 0x30
VERSION = 0x1000C


class FormatError(ValueError):
    pass


def _pad(buf, align=0x10):
    while len(buf) % align:
        buf.append(0)


def _utf16(data, at):
    end = at
    while data[end:end + 2] != b"\0\0":
        end += 2
        if end + 2 > len(data):
            raise FormatError("string runs past the end of the file")
    return data[at:end].decode("utf-16-le")


def _f32bits(value):
    return struct.pack("<f", value)


class MiniHeader:
    """The animation's file header ("AnimMiniHeader").

    type 0 (Standard): the animation plays its own HKX. Its name is "aTTT_AAAAAA.hkt" (TAE id
        TTT, animation id AAAAAA); the HKX itself is aTTT_AAAAAA.hkx in a c0000_*.anibnd.dcx.
        fields: flags (4 bytes: loop, imports-hkx, allow-delay-load, 0) and
        import_hkx_id (i32, -1 = none) = the full animation id (TTT*1000000 + AAAAAA) whose
        HKX it plays instead of its own.
    type 1 (ImportOtherAnim): the animation is another one's: import_id = full animation id
        (TTT*1000000 + AAAAAA), unknown (i32, 0 in every game file).
    `name` is the .hkt name stored after the header (None when there is none); `name_ptr` says
    whether the name offset field points at the end of the header even without a name (the
    game's files do that for most type-1 entries) or is 0.
    """

    def __init__(self, type=0, data=None, name=None, name_ptr=True):
        self.type = type
        self.data = bytearray(data if data is not None else
                              (b"\0\0\0\0" + struct.pack("<i", -1) + bytes(16)))
        if len(self.data) != 0x18:
            raise FormatError("mini-header data must be 0x18 bytes")
        self.name = name
        self.name_ptr = name_ptr or name is not None

    # Standard (type 0)
    @property
    def flags(self):
        return bytes(self.data[0:4])

    @flags.setter
    def flags(self, value):
        self.data[0:4] = bytes(value)

    @property
    def import_hkx_id(self):
        return struct.unpack_from("<i", self.data, 4)[0]

    @import_hkx_id.setter
    def import_hkx_id(self, value):
        struct.pack_into("<i", self.data, 4, value)

    # ImportOtherAnim (type 1)
    @property
    def import_id(self):
        return struct.unpack_from("<i", self.data, 0)[0]

    @import_id.setter
    def import_id(self, value):
        struct.pack_into("<i", self.data, 0, value)

    @property
    def unknown(self):
        return struct.unpack_from("<i", self.data, 4)[0]

    def copy(self):
        return MiniHeader(self.type, bytes(self.data), self.name, self.name_ptr)

    def __repr__(self):
        if self.type == 1:
            return f"MiniHeader(import {self.import_id}, name={self.name!r})"
        return f"MiniHeader(own, flags={self.flags.hex()}, import_hkx={self.import_hkx_id}, name={self.name!r})"


class Event:
    """One TAE event: start and end time (seconds), type, a second int (unk, 0 in nearly all),
    and the parameter bytes (raw, including the padding to 0x10)."""

    def __init__(self, start, end, type, unk=0, params=b""):
        self.start = start
        self.end = end
        self.type = type
        self.unk = unk
        self.params = bytes(params)
        # Which entries of the animation's time table this event used when read (so a file
        # whose table holds a time twice is written back the same way).
        self._si = self._ei = None

    def ints(self, n=6):
        return struct.unpack_from(f"<{n}i", self.params.ljust(n * 4, b"\0"))

    def set_int(self, index, value):
        p = bytearray(self.params.ljust((index + 1) * 4, b"\0"))
        struct.pack_into("<i", p, index * 4, value)
        self.params = bytes(p)

    def copy(self):
        e = Event(self.start, self.end, self.type, self.unk, self.params)
        e._si, e._ei = self._si, self._ei
        return e

    def __repr__(self):
        return f"Event(type {self.type}, {self.start:.4f}-{self.end:.4f}, {self.params.hex()})"


class EventGroup:
    """A group of events (the editor's rows): type, an extra value (0 in every game file) and
    the member events (as indices into the animation's event list)."""

    def __init__(self, type, indices, extra=0, tail=0):
        self.type = type
        self.indices = list(indices)
        self.extra = extra
        self.tail = tail

    def copy(self):
        return EventGroup(self.type, self.indices, self.extra, self.tail)

    def __repr__(self):
        return f"EventGroup(type {self.type}, events {self.indices})"


class Animation:
    def __init__(self, id, mini=None, events=None, groups=None, times=None):
        self.id = id
        self.mini = mini or MiniHeader()
        self.events = events or []
        self.groups = groups or []
        # The time table as read (floats, in file order); None = build it (sorted, unique).
        self.times = times

    def copy(self, new_id=None):
        return Animation(self.id if new_id is None else new_id, self.mini.copy(),
                         [e.copy() for e in self.events], [g.copy() for g in self.groups],
                         None if self.times is None else list(self.times))

    def __repr__(self):
        return f"Animation({self.id}, {self.mini}, {len(self.events)} events, {len(self.groups)} groups)"


class TaeFile:
    def __init__(self, id, animations=None, skeleton="skeleton.hkt", sib="c9990.SIB",
                 event_bank=4, flags=bytes([1, 0, 1, 2, 2, 1, 1, 1]), unk48=1):
        self.id = id
        self.animations = animations or []
        self.skeleton = skeleton
        self.sib = sib
        self.event_bank = event_bank
        self.flags = bytes(flags)
        self.unk48 = unk48

    def anim(self, aid):
        for a in self.animations:
            if a.id == aid:
                return a
        raise KeyError(aid)

    def ids(self):
        return [a.id for a in self.animations]

    # ------------------------------------------------------------------ reading
    @classmethod
    def read(cls, d):
        d = bytes(d)
        if d[:4] != b"TAE " or d[4:8] != b"\0\0\0\xff":
            raise FormatError("not a little-endian 64-bit TAE")
        version, size = struct.unpack_from("<ii", d, 8)
        if version != VERSION:
            raise FormatError(f"TAE version {version:#x}")
        if size != len(d):
            raise FormatError("TAE size field does not match")
        expect = {0x10: 0x40, 0x18: 1, 0x20: 0x50, 0x28: 0x80, 0x38: 0, 0x68: 0xA0, 0x80: 1,
                  0x88: 0x90, 0x98: 0x50, 0xA0: 0, 0xA8: 0xB0, 0xC0: 0, 0xC8: 0}
        for at, value in expect.items():
            if struct.unpack_from("<q", d, at)[0] != value:
                raise FormatError(f"unexpected header value at {at:#x}")
        event_bank, = struct.unpack_from("<q", d, 0x30)
        flags = d[0x40:0x48]
        unk48, = struct.unpack_from("<q", d, 0x48)
        tid, count = struct.unpack_from("<ii", d, 0x50)
        anims_at, groups_at, _, count2, first_body = struct.unpack_from("<qqqqq", d, 0x58)
        id2, id3 = struct.unpack_from("<ii", d, 0x90)
        if count2 != count or id2 != tid or id3 != tid:
            raise FormatError("header copies disagree")
        sk_at, sib_at = struct.unpack_from("<qq", d, 0xB0)
        t = cls(tid, [], _utf16(d, sk_at), _utf16(d, sib_at), event_bank, flags, unk48)

        table = [struct.unpack_from("<qq", d, anims_at + i * 16) for i in range(count)]
        # Every structure start, to tell where a mini-header's name ends (or that it has none).
        starts = {len(d)}
        bodies = []
        for aid, at in table:
            body = struct.unpack_from("<qqqqiiii", d, at)
            if body[7] != 0:
                raise FormatError(f"anim {aid}: body tail {body[7]}")
            bodies.append(body)
            ev_at, grp_at, times_at, file_at = body[:4]
            starts.update(x for x in (ev_at, grp_at, times_at, file_at) if x)
            for i in range(body[4]):
                starts.add(struct.unpack_from("<q", d, ev_at + i * 24 + 16)[0])
            for g in range(body[5]):
                n, vals, typ, _ = struct.unpack_from("<qqqq", d, grp_at + g * 32)
                starts.update(x for x in (vals, typ) if x)
        order = sorted(starts)

        def next_start(at):
            return order[bisect.bisect_right(order, at)]

        for (aid, at), body in zip(table, bodies):
            ev_at, grp_at, times_at, file_at, ev_n, grp_n, times_n, _ = body
            # Mini-header.
            mtype, nxt, name_at = struct.unpack_from("<qqq", d, file_at)
            if nxt != file_at + 0x10:
                raise FormatError(f"anim {aid}: mini-header pointer")
            name, name_ptr = None, False
            if name_at:
                if name_at != file_at + MINI_SIZE:
                    raise FormatError(f"anim {aid}: mini-header name offset {name_at:#x}")
                name_ptr = True
                if name_at not in starts:
                    name = _utf16(d, name_at)
            mini = MiniHeader(mtype, d[file_at + 0x18:file_at + 0x30], name, name_ptr)
            # Times.
            times = list(struct.unpack_from(f"<{times_n}f", d, times_at)) if times_n else []
            # Events.
            events, header_offsets = [], {}
            for i in range(ev_n):
                hat = ev_at + i * 24
                s_at, e_at, data_at = struct.unpack_from("<qqq", d, hat)
                header_offsets[hat] = i
                etype, unk, p_at = struct.unpack_from("<iiq", d, data_at)
                if p_at != data_at + 0x10:
                    raise FormatError(f"anim {aid} event {i}: params offset")
                end = next_start(data_at)
                ev = Event(struct.unpack_from("<f", d, s_at)[0], struct.unpack_from("<f", d, e_at)[0],
                           etype, unk, d[p_at:end])
                ev._si = (s_at - times_at) // 4
                ev._ei = (e_at - times_at) // 4
                if not (0 <= ev._si < times_n and 0 <= ev._ei < times_n) or (s_at - times_at) % 4 or (e_at - times_at) % 4:
                    raise FormatError(f"anim {aid} event {i}: time outside the table")
                events.append(ev)
            # Event groups.
            groups = []
            for g in range(grp_n):
                n, vals, typ, tail = struct.unpack_from("<qqqq", d, grp_at + g * 32)
                gtype, extra = struct.unpack_from("<qq", d, typ)
                idx = []
                for k in range(n):
                    off, = struct.unpack_from("<i", d, vals + k * 4)
                    if off not in header_offsets:
                        raise FormatError(f"anim {aid} group {g}: member is not an event header")
                    idx.append(header_offsets[off])
                groups.append(EventGroup(gtype, idx, extra, tail))
            t.animations.append(Animation(aid, mini, events, groups, times))
        return t

    # ------------------------------------------------------------------ writing
    def to_bytes(self):
        anims = sorted(self.animations, key=lambda a: a.id)
        if len({a.id for a in anims}) != len(anims):
            raise FormatError("duplicate animation ids")
        out = bytearray(HEADER_SIZE)
        out[0:8] = b"TAE \0\0\0\xff"
        struct.pack_into("<i", out, 8, VERSION)
        for at, value in {0x10: 0x40, 0x18: 1, 0x20: 0x50, 0x28: 0x80, 0x30: self.event_bank,
                          0x68: 0xA0, 0x80: 1, 0x88: 0x90, 0x98: 0x50, 0xA8: 0xB0}.items():
            struct.pack_into("<q", out, at, value)
        out[0x40:0x48] = self.flags
        struct.pack_into("<q", out, 0x48, self.unk48)
        struct.pack_into("<ii", out, 0x50, self.id, len(anims))
        struct.pack_into("<q", out, 0x70, len(anims))
        struct.pack_into("<ii", out, 0x90, self.id, self.id)
        struct.pack_into("<q", out, 0xB0, len(out))
        out += self.skeleton.encode("utf-16-le") + b"\0\0"
        _pad(out)
        struct.pack_into("<q", out, 0xB8, len(out))
        out += self.sib.encode("utf-16-le") + b"\0\0"
        _pad(out)

        # Animation table (bodies filled in below).
        table_at = len(out) if anims else 0
        struct.pack_into("<q", out, 0x58, table_at)
        entry_at = []
        for a in anims:
            entry_at.append(len(out))
            out += struct.pack("<qq", a.id, 0)
        # Groups of consecutive ids.
        struct.pack_into("<q", out, 0x60, len(out))
        groups_head = len(out)
        out += bytes(16)
        runs, i = [], 0
        while i < len(anims):
            first = i
            while i + 1 < len(anims) and anims[i + 1].id == anims[i].id + 1:
                i += 1
            runs.append((anims[first].id, anims[i].id, entry_at[first]))
            i += 1
        runs_at = len(out)
        for first, last, at in runs:
            out += struct.pack("<iiq", first, last, at)
        struct.pack_into("<qq", out, groups_head, len(runs), runs_at if runs else 0)
        # Bodies.
        struct.pack_into("<q", out, 0x78, len(out) if anims else 0)
        body_at = []
        for k, a in enumerate(anims):
            body_at.append(len(out))
            struct.pack_into("<q", out, entry_at[k] + 8, len(out))
            out += bytes(ANIM_BODY_SIZE)

        for k, a in enumerate(anims):
            b = body_at[k]
            # Mini-header and its name.
            m = a.mini
            file_at = len(out)
            out += struct.pack("<qqq", m.type, file_at + 0x10, file_at + MINI_SIZE if m.name_ptr else 0)
            out += m.data
            if m.name is not None:
                out += m.name.encode("utf-16-le") + b"\0\0"
                _pad(out)
            # Time table: the one read, extended with any new times; else sorted unique.
            times = list(a.times) if a.times is not None else sorted({x for e in a.events for x in (e.start, e.end)})
            bits = [_f32bits(x) for x in times]
            refs = []
            for e in a.events:
                pair = []
                for value, hint in ((e.start, e._si), (e.end, e._ei)):
                    vb = _f32bits(value)
                    if hint is not None and hint < len(bits) and bits[hint] == vb:
                        pair.append(hint)
                    elif vb in bits:
                        pair.append(bits.index(vb))
                    else:
                        times.append(value)
                        bits.append(vb)
                        pair.append(len(bits) - 1)
                refs.append(pair)
            times_at = len(out) if times else 0
            for vb in bits:
                out += vb
            _pad(out)
            # Event headers, then their data.
            ev_at = len(out) if a.events else 0
            headers = []
            for (si, ei) in refs:
                headers.append(len(out))
                out += struct.pack("<qqq", times_at + si * 4, times_at + ei * 4, 0)
            # (no padding here: the first event's data follows the headers directly)
            for e, h in zip(a.events, headers):
                struct.pack_into("<q", out, h + 16, len(out))
                out += struct.pack("<iiq", e.type, e.unk, len(out) + 0x10)
                out += e.params
                _pad(out)
            # Event groups: headers, then type data and member lists.
            grp_at = len(out) if a.groups else 0
            gheads = []
            for g in a.groups:
                gheads.append(len(out))
                out += struct.pack("<qqqq", len(g.indices), 0, 0, g.tail)
            for g, gh in zip(a.groups, gheads):
                struct.pack_into("<q", out, gh + 16, len(out))
                out += struct.pack("<qq", g.type, g.extra)
                struct.pack_into("<q", out, gh + 8, len(out))
                for idx in g.indices:
                    out += struct.pack("<i", headers[idx])
                _pad(out)
            struct.pack_into("<qqqqiiii", out, b, ev_at, grp_at, times_at, file_at,
                             len(a.events), len(a.groups), len(times), 0)
        struct.pack_into("<i", out, 0x0C, len(out))
        return bytes(out)


def read(data):
    return TaeFile.read(data)


def game_taes():
    """{name: bytes} of every TAE in the game's chr/c0000.anibnd.dcx."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bbparam import GAME, open_bnd
    _, a = open_bnd(GAME + "chr/c0000.anibnd.dcx")
    return {n.split("\\")[-1]: f for n, f in zip(a.names, a.files) if n.endswith(".tae")}


def test_roundtrip(verbose=True):
    """Read and write back every TAE of the game; also check a copy of every animation (all
    events/groups copied, time table rebuilt from scratch) keeps every event's values.
    Returns (passed, failed names)."""
    taes = game_taes()
    passed, failed = 0, []
    for name, data in taes.items():
        try:
            t = read(data)
            ok = t.to_bytes() == data
            # Rebuilding the time tables (as a merged moveset does) must keep every event.
            t2 = read(data)
            for a in t2.animations:
                a.times = None
                for e in a.events:
                    e._si = e._ei = None
            r = read(t2.to_bytes())
            for a, b in zip(t.animations, r.animations):
                if (a.id != b.id or len(a.events) != len(b.events) or
                        any((x.start, x.end, x.type, x.unk, x.params) != (y.start, y.end, y.type, y.unk, y.params)
                            for x, y in zip(a.events, b.events)) or
                        [(g.type, g.indices) for g in a.groups] != [(g.type, g.indices) for g in b.groups]):
                    ok = False
        except FormatError as error:
            ok = False
            if verbose:
                print(f"{name}: {error}")
        if ok:
            passed += 1
        else:
            failed.append(name)
        if verbose:
            print(f"{name:10} {len(data):8} bytes  {'pass' if ok else 'FAIL'}")
    if verbose:
        print(f"TAE round trip: {passed}/{len(taes)} pass, {len(failed)} fail {failed}")
    return passed, failed


if __name__ == "__main__":
    import sys
    passed, failed = test_roundtrip()
    sys.exit(1 if failed else 0)
