# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only TAE (Bloodborne, version 0x1000C, 64-bit) reader: animations, their mini-header
(own HKX or import of another animation) and events (type, start, end, raw params)."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class Event:
    def __init__(self, d, at):
        self.start_off, self.end_off, data = struct.unpack_from("<qqq", d, at)
        self.start = struct.unpack_from("<f", d, self.start_off)[0]
        self.end = struct.unpack_from("<f", d, self.end_off)[0]
        self.type, self.unk = struct.unpack_from("<ii", d, data)
        pofs, = struct.unpack_from("<q", d, data + 8)
        self.params_at = pofs
        self.raw = d[pofs:pofs + 32] if pofs > 0 else b""

    def ints(self, n=6):
        return struct.unpack_from(f"<{n}i", self.raw.ljust(n * 4, b"\0"))


class Anim:
    def __init__(self, d, aid, at):
        self.id = aid
        self.offset = at
        (self.ev_off, self.grp_off, self.times_off, self.file_off,
         self.ev_count, self.grp_count, self.times_count, _) = struct.unpack_from("<qqqqiiii", d, at)
        self.mini_type, = struct.unpack_from("<q", d, self.file_off)
        self.mini = d[self.file_off:self.file_off + 0x30]
        self.events = [Event(d, self.ev_off + i * 24) for i in range(self.ev_count)]


class Tae:
    def __init__(self, d):
        assert d[:4] == b"TAE " and struct.unpack_from("<i", d, 8)[0] == 0x1000C
        self.data = d
        self.id, count = struct.unpack_from("<ii", d, 0x50)
        anims_off, = struct.unpack_from("<q", d, 0x58)
        self.anims = []
        for i in range(count):
            aid, at = struct.unpack_from("<qq", d, anims_off + i * 16)
            self.anims.append(Anim(d, aid, at))


def load_all():
    from bbparam import GAME, open_bnd
    _, a = open_bnd(GAME + "chr/c0000.anibnd.dcx")
    return {n.split("\\")[-1]: Tae(f) for n, f in zip(a.names, a.files) if n.endswith(".tae")}


if __name__ == "__main__":
    taes = load_all()
    for name, t in taes.items():
        ids = [a.id for a in t.anims]
        print(f"{name:9} id {t.id:5} anims {len(ids):4} range {min(ids)}..{max(ids)}")
