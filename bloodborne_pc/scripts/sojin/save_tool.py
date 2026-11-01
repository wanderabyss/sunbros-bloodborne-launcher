#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage save converter.

Turns every Sojin Chikage weapon in a Bloodborne save into the Chikage it was made from, at the
same level: Sojin Chikage (2040000 + 100*level) into Chikage (2000000 + ...), Uncanny Sojin
Chikage (2050000) into Uncanny Chikage (2010000) and Lost Sojin Chikage (2030000, the ids of the
stand-alone mod) into Lost Chikage (2020000). The save then no longer refers to the weapons and
keeps loading without them. Gems stay valid: each has its Chikage's gem-slot rows.

    python save_tool.py <savedata folder or userdata file>            dry run: report only
    python save_tool.py <savedata folder or userdata file> --apply    back up, write, verify
    python save_tool.py <savedata folder> --before-start              --apply, for run.py: the
        launcher calls it before it starts the game, so the running-game guard is left out

A folder means every userdata00NN / backup00NN in it (character slots 0..9 and the system file
userdata0010, which holds the title-menu summary of each character). A file means that file, its
userdata/backup twin and the system files beside it. Every (weapon handle, Sojin id) pair in a
file is converted, also in the older save copies found in the tail of the files (past the sections
the header lists), and the tool refuses to write if any Sojin id sits somewhere it does not understand.
See save-tool-notes.md for the format facts this relies on.
"""
import argparse, csv, datetime, glob, os, shutil, struct, subprocess, sys
from collections import Counter

# (first Sojin id, its Chikage's first id, that Chikage's sortId of +0, names)
FAMILIES = (
    (2040000, 2000000, 55100, "Sojin Chikage", "Chikage"),
    (2050000, 2010000, 55200, "Uncanny Sojin Chikage", "Uncanny Chikage"),
    (2030000, 2020000, 55300, "Lost Sojin Chikage", "Lost Chikage"),
)
LEVELS = range(11)
SOJIN = {family[0] + 100 * lv: (family, lv) for family in FAMILIES for lv in LEVELS}
# EquipParamWeapon sortId of +0 (+level adds the level); 55400 was the stand-alone mod's.
SOJIN_SORTS = (55400, 55420, 55440)


def sort_part(sort_id):
    """The upper 20 bits of an inventory index."""
    return (sort_id * 100) & 0xFFFFF


SOJIN_SORT_PARTS = {sort_part(s + lv): lv for s in SOJIN_SORTS for lv in LEVELS}

CHAR_SIZE, SYS_SIZE = 0x140000, 0x40000
LIVE_ROOT = r"C:\Games\Bloodborne\user"
GAME_PROCESSES = ("bloodborne", "bb-probe")

# Character save image (offsets from the image start; the main image starts at file offset 0).
TABLE_AT, TABLE_ENTRIES = 0x54, 4096
WEAPON_SIZE, GEM_SIZE = 0x3C, 0x28
NAME_REL = 0x98                 # UTF-16 character name at tableEnd + 0x98
EQUIP_INDEX_REL, EQUIP_HANDLE_REL = 0x129, 0x185   # from the byte before the name
INV_REL = 0x25C                 # inventory count at tableEnd + 0x25C
ENTRY = 16                      # list entry: handle, id, quantity, index
LISTS = (("inventory", 0, 1984), ("key items", 0x7C04, 64), ("list after key items", 0x8008, 64),
         ("storage box", 0x85EC, 1984), ("list after storage box", 0x101F0, 64),
         ("second list after storage box", 0x105F4, 64))     # offsets from the inventory count
EQUIP_SLOTS = ("left hand 1", "right hand 1", "left hand 2", "right hand 2",
               "equip slot 5", "equip slot 6", "equip slot 7", "equip slot 8")

# System file userdata0010: title-menu summary per character slot.
SYS_NAME_AT, SYS_WEAPONS_AT, SYS_STRIDE = 0x1096, 0x11DC, 0x192

# Lost Chikage's open gem slots per level (WeaponGenParam 2020000 + 100*level).
LOST_SLOTS = {lv: () if lv == 0 else (1,) if lv < 3 else (1, 1) if lv < 6 else (1, 1, 8) for lv in LEVELS}
SHAPES = {1: "Radial", 2: "Triangle", 4: "Waning", 8: "Droplet"}


class FormatError(Exception):
    pass


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def target(v):
    """The Chikage a Sojin id becomes."""
    family, lv = SOJIN[v]
    return family[1] + 100 * lv


def target_sort(v):
    family, lv = SOJIN[v]
    return family[2] + lv


def sojin(v):
    family, lv = SOJIN[v]
    return f"{family[3]} +{lv} ({v})"


def chikage(v):
    family, lv = SOJIN[v]
    return f"{family[4]} +{lv} ({target(v)})"


def utf16_name(d, at):
    raw = d[at:at + 34]
    end = next((i for i in range(0, len(raw) - 1, 2) if raw[i:i + 2] == b"\0\0"), None)
    if not end:
        return None
    try:
        s = raw[:end].decode("utf-16-le")
    except UnicodeDecodeError:
        return None
    return s if s.isprintable() else None


class Image:
    """One serialized character: the live one at offset 0, or a stale copy further in the file."""

    def __init__(self, d, base, strict):
        n = len(d)
        self.base = base
        if base + TABLE_AT > n:
            raise FormatError("file too short")
        self.sections = [struct.unpack_from("<II", d, base + 0x0C + 8 * i) for i in range(9)]
        if strict and any(off + size > n for off, size in self.sections):
            raise FormatError("header section runs past the end of the file")
        self.records, self.by_handle, self.kinds = {}, {}, Counter()
        pos = base + TABLE_AT
        for i in range(TABLE_ENTRIES):
            if pos + 8 > n:
                raise FormatError("item table runs past the end of the file")
            h, iid = struct.unpack_from("<II", d, pos)
            if h == 0 and iid == 0xFFFFFFFF:
                pos += 8
                continue
            t = h >> 28
            size = WEAPON_SIZE if t in (0x8, 0x9) else GEM_SIZE if t == 0xC else None
            if size is None:
                raise FormatError(f"item table entry {i} at {pos:#x} has unknown handle {h:#010x}")
            if pos + size > n:
                raise FormatError("item table runs past the end of the file")
            self.records[pos] = (i, h, iid)
            self.by_handle.setdefault(h, []).append(pos)
            self.kinds[t] += 1
            pos += size
        self.table_end = pos
        self.name_at = pos + NAME_REL
        self.name = utf16_name(d, self.name_at)
        if strict and not self.name:
            raise FormatError(f"no character name at tableEnd+{NAME_REL:#x} ({self.name_at:#x})")
        eb = self.name_at - 1
        self.equip_indexes = struct.unpack_from("<8I", d, eb + EQUIP_INDEX_REL) if eb + EQUIP_INDEX_REL + 32 <= n else ()
        self.equip_handles = struct.unpack_from("<8I", d, eb + EQUIP_HANDLE_REL) if eb + EQUIP_HANDLE_REL + 32 <= n else ()
        self.inv_at = pos + INV_REL
        self.lists, self.entries = [], {}
        for lname, rel, cap in LISTS:
            at = self.inv_at + rel
            if at + 4 + cap * ENTRY > n:
                if strict:
                    raise FormatError(f"{lname} runs past the end of the file")
                continue
            count, used = u32(d, at), 0
            for k in range(cap):
                e = at + 4 + k * ENTRY
                h, iid, q, idx = struct.unpack_from("<4I", d, e)
                if h == 0:
                    if strict and (iid, q, idx) != (0xFFFFFFFF, 0, 0):
                        raise FormatError(f"{lname} entry {k} at {e:#x} is neither empty nor an item")
                    continue
                if strict and h >> 28 not in (0x8, 0x9, 0xA, 0xB, 0xC):
                    raise FormatError(f"{lname} entry {k} at {e:#x} has unknown handle {h:#010x}")
                used += 1
                self.entries[e] = (lname, k, h, iid, q, idx)
            if strict and count > cap:
                raise FormatError(f"{lname} count {count} is larger than the list ({cap})")
            self.lists.append((lname, at, cap, count, used))

    def fingerprint(self):
        return {"table end": hex(self.table_end), "item records": len(self.records),
                "records by type": dict(sorted(self.kinds.items())), "name": self.name,
                "lists (count field, used entries)": [(l[0], l[3], l[4]) for l in self.lists],
                "equipment handles": [hex(h) for h in self.equip_handles],
                "equipment indexes": [hex(i) for i in self.equip_indexes]}


def stale_images(d, main):
    """Header-led copies of an older save image after the live image's sections."""
    out, sig = [], d[:8]
    start = max(off + size for off, size in main.sections)
    o = d.find(sig, start)
    while o >= 0:
        if o % 4 == 0 and u32(d, o + 0x0C) == TABLE_AT:
            try:
                out.append(Image(d, o, strict=False))
            except FormatError:
                pass
        o = d.find(sig, o + 1)
    return out


def find_values(d):
    """Offsets of every Sojin id (any byte alignment)."""
    hits = set()
    for v in SOJIN:
        b = struct.pack("<I", v)
        o = d.find(b)
        while o >= 0:
            hits.add(o)
            o = d.find(b, o + 1)
    # Only the exact ids: other numbers in the ranges are not weapon ids (a save holds 2050495 in
    # unrelated data), and every weapon id of a range is one of these (first + 100 * level).
    return sorted(hits)


def looks_like_weapon_record(d, o):
    if o + WEAPON_SIZE > len(d) or u32(d, o + 16) > 0xFF:
        return False
    for s in range(5):
        shape, gem = struct.unpack_from("<II", d, o + 20 + 8 * s)
        if not (shape & 0x80000000 or shape in SHAPES) or not (gem == 0 or gem >> 28 == 0xC):
            return False
    return True


def looks_like_entry(d, o):
    return o + ENTRY <= len(d) and 0 < u32(d, o + 8) < 10000 and (u32(d, o + 12) >> 12) in SOJIN_SORT_PARTS


class Change:
    def __init__(self, offset, kind, where, v, handle=None):
        self.offset, self.kind, self.where, self.v, self.handle = offset, kind, where, v, handle
        self.fields, self.notes = [], []        # (offset, old u32, new u32)

    def describe(self):
        h = f"handle {self.handle:#010x}  " if self.handle is not None else ""
        lines = [f"  {self.offset:#08x}  {self.where}\n            {h}{sojin(self.v)} -> {chikage(self.v)}"]
        for off, old, new in self.fields[1:]:
            lines.append(f"            index {old:#010x} -> {new:#010x} (sort part for {chikage(self.v)}, counter kept)")
        lines += [f"            note: {n}" for n in self.notes]
        return "\n".join(lines)


def plan_pair(d, o, v, where, kind, changes, problems):
    family, lv = SOJIN[v]
    c = Change(o, kind, where, v, u32(d, o))
    c.fields.append((o + 4, v, target(v)))
    if kind == "entry":
        idx = u32(d, o + 12)
        part = idx >> 12
        if part not in SOJIN_SORT_PARTS:
            problems.append(f"{o:#x} {where}: index {idx:#010x} has no Sojin Chikage sort part; not converting")
            return None
        if SOJIN_SORT_PARTS[part] != lv:
            c.notes.append(f"index sort part was Sojin Chikage +{SOJIN_SORT_PARTS[part]}'s (the game keeps the "
                           f"sort part of the level an item was obtained at); set to +{lv}'s")
        c.fields.append((o + 12, idx, (sort_part(target_sort(v)) << 12) | (idx & 0xFFF)))
    elif family[1] == 2020000:   # Lost Chikage's slots are known; the others are only converted
        opened = tuple(u32(d, o + 20 + 8 * s) for s in range(5) if not u32(d, o + 20 + 8 * s) & 0x80000000)
        if opened != LOST_SLOTS[lv]:
            want = ", ".join(SHAPES.get(s, hex(s)) for s in LOST_SLOTS[lv]) or "none"
            have = ", ".join(SHAPES.get(s, hex(s)) for s in opened) or "none"
            c.notes.append(f"open gem slots ({have}) differ from Lost Chikage +{lv}'s ({want}); left as they are")
    changes.append(c)
    return c


def plan_character(d):
    """(image, changes, problems, notes) for a character file."""
    img = Image(d, 0, strict=True)
    stale = stale_images(d, img)
    changes, problems, notes = [], [], []
    for p in find_values(d):
        v = u32(d, p)
        if v not in SOJIN:
            problems.append(f"{p:#x}: value {v} lies in the Sojin id range but is not a Sojin Chikage id")
            continue
        o = p - 4
        if o < 0 or u32(d, o) >> 28 != 0x8:
            problems.append(f"{p:#x}: {sojin(v)} without a weapon handle before it (unknown structure)")
            continue
        h = u32(d, o)
        where = kind = None
        for im in [img] + stale:
            prefix = "" if im is img else f"older save image at {im.base:#x} (file tail, past the header's sections): "
            if o in im.records:
                where, kind = f"{prefix}item table entry #{im.records[o][0]}", "record"
            elif o in im.entries:
                lname, k = im.entries[o][:2]
                where, kind = f"{prefix}{lname} slot {k}", "entry"
                recs = [im.records[r][2] for r in im.by_handle.get(h, [])]
                if recs and v not in recs:
                    problems.append(f"{o:#x} {where}: entry says {v} but the item record of handle {h:#x} says {recs}")
                    where = None
                elif not recs:
                    notes.append(f"{o:#x} {where}: no item record with handle {h:#x}")
            if where or kind:
                break
        if not kind:
            if looks_like_entry(d, o):
                where, kind = "list entry outside the known lists", "entry"
            elif looks_like_weapon_record(d, o):
                where, kind = "weapon record outside the item table", "record"
            else:
                problems.append(f"{o:#x}: {sojin(v)} after handle {h:#x} in an unknown structure")
                continue
        if not where:
            continue
        c = plan_pair(d, o, v, where, kind, changes, problems)
        if c and o in img.records:
            slots = [EQUIP_SLOTS[i] for i, eh in enumerate(img.equip_handles) if eh == h]
            listed = [f"{e[0]} slot {e[1]}" for e in img.entries.values() if e[2] == h]
            if slots:
                c.notes.append(f"equipped in {', '.join(slots)} (equipment points at the handle, which stays)")
            if not listed:
                c.notes.append("in no inventory or storage list (orphan record)")
    return img, changes, problems, notes


def plan_system(d, names):
    """Changes for userdata0010: the title-menu summaries and the stale buffer data after them."""
    changes, problems, notes = [], [], []
    summary = {}
    for slot in range(10):
        nm = utf16_name(d, SYS_NAME_AT + slot * SYS_STRIDE)
        if nm and (slot not in names or names[slot] == nm):
            summary[slot] = SYS_WEAPONS_AT + slot * SYS_STRIDE
    for p in find_values(d):
        v = u32(d, p)
        if v not in SOJIN:
            problems.append(f"{p:#x}: value {v} lies in the Sojin id range but is not a Sojin Chikage id")
            continue
        hit = next(((s, at) for s, at in summary.items() if at <= p < at + 32 and (p - at) % 4 == 0), None)
        if hit:
            s, at = hit
            c = Change(p, "summary", f"title-menu summary of character slot {s} ({names.get(s) or utf16_name(d, SYS_NAME_AT + s * SYS_STRIDE)}), "
                                      f"{EQUIP_SLOTS[(p - at) // 4]}", v)
            c.fields.append((p, v, target(v)))
            changes.append(c)
            continue
        o = p - 4
        if o >= 0 and u32(d, o) >> 28 == 0x8 and looks_like_entry(d, o):
            plan_pair(d, o, v, "stale buffer data after the menu summaries (an inventory-style entry)", "entry", changes, problems)
        elif o >= 0 and u32(d, o) >> 28 == 0x8 and looks_like_weapon_record(d, o):
            plan_pair(d, o, v, "stale buffer data after the menu summaries (a weapon record)", "record", changes, problems)
        else:
            problems.append(f"{p:#x}: {sojin(v)} in an unknown structure of the system file")
    return changes, problems, notes


def apply_changes(d, changes):
    out = bytearray(d)
    for c in changes:
        for off, old, new in c.fields:
            assert u32(out, off) == old, f"{off:#x} changed under the plan"
            struct.pack_into("<I", out, off, new)
    return bytes(out)


def verify(kind, old, new, changes):
    """List of (ok, text)."""
    res = [(len(new) == len(old), f"size unchanged ({len(new)} bytes)")]
    left = find_values(new)
    res.append((not left, "no Sojin Chikage id remains anywhere in the file" if not left else
                f"Sojin Chikage ids remain at {[hex(o) for o in left]}"))
    allowed = {off + i for c in changes for off, _, _ in c.fields for i in range(4)}
    diff = [i for i in range(min(len(old), len(new))) if old[i] != new[i]]
    stray = [i for i in diff if i not in allowed]
    res.append((not stray, f"{len(diff)} changed bytes, all inside the planned fields" if not stray else
                f"bytes changed outside the planned fields: {[hex(i) for i in stray[:20]]}"))
    wrong = [(off, want) for c in changes for off, _, want in c.fields if u32(new, off) != want]
    nfields = sum(len(c.fields) for c in changes)
    res.append((not wrong, f"all {nfields} planned fields hold their new values" if not wrong else
                "fields without their new value: " + ", ".join(f"{o:#x} (want {w:#x})" for o, w in wrong)))
    if kind == "character":
        a, b = Image(old, 0, strict=True), Image(new, 0, strict=True)
        fa, fb = a.fingerprint(), b.fingerprint()
        for key in fa:
            res.append((fa[key] == fb[key], f"{key} unchanged: {fb[key]}" if fa[key] == fb[key] else
                        f"{key} changed: {fa[key]} -> {fb[key]}"))
        for c in changes:
            if c.offset in b.records:
                _, h, iid = b.records[c.offset]
                res.append((iid == target(c.v) and h == c.handle,
                            f"{c.where}: handle {h:#x} id {iid}"))
            elif c.offset in b.entries:
                lname, k, h, iid, q, idx = b.entries[c.offset]
                ok = (iid == target(c.v) and h == c.handle and idx >> 12 == sort_part(target_sort(c.v))
                      and idx & 0xFFF == c.fields[1][1] & 0xFFF and q == u32(old, c.offset + 8))
                res.append((ok, f"{c.where}: handle {h:#x} id {iid} qty {q} index {idx:#010x} "
                                f"(sort part {idx >> 12:#x} = {chikage(c.v)} sortId {target_sort(c.v)} * 100 & 0xFFFFF)"))
    return res


# ---------------------------------------------------------------------------------------------

def gather(target):
    """(folder, [file paths]) to process."""
    target = os.path.abspath(target)
    if os.path.isdir(target):
        folder = target
        files = sorted(f for f in glob.glob(os.path.join(folder, "*")) if os.path.isfile(f)
                       and os.path.basename(f).lower().startswith(("userdata", "backup"))
                       and os.path.basename(f)[-4:].isdigit())
        if not files:
            found = []
            for root, dirs, fs in os.walk(folder):
                if "userdata0000" in fs:
                    found.append(root)
                if len(found) >= 10:
                    break
            hint = "".join(f"\n  {f}" for f in found)
            raise SystemExit(f"No userdata/backup files in {folder}. Pass the folder that holds userdata0000"
                             + (f"; found:{hint}" if found else "."))
        return folder, files
    if not os.path.isfile(target):
        raise SystemExit(f"{target} does not exist")
    folder, base = os.path.split(target)
    num = base[-4:]
    files = [target]
    for twin in (f"userdata{num}", f"backup{num}", "userdata0010", "backup0010"):
        p = os.path.join(folder, twin)
        if os.path.isfile(p) and os.path.normcase(p) not in map(os.path.normcase, files):
            files.append(p)
    return folder, files


def under(path, root):
    p, r = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(root))
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def is_live(path):
    if under(path, LIVE_ROOT):
        return True
    try:
        st = os.stat(path)
    except OSError:
        return False
    if st.st_nlink > 1:     # a hard link into the live save folder counts as the live save
        for f in glob.glob(os.path.join(LIVE_ROOT, "savedata", "*", "*", "*", "*")):
            try:
                s2 = os.stat(f)
            except OSError:
                continue
            if (s2.st_dev, s2.st_ino) == (st.st_dev, st.st_ino):
                return True
    return False


def game_processes():
    """(list of running game processes, error text)."""
    try:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if r.returncode:
        return None, r.stderr.strip() or f"tasklist exit code {r.returncode}"
    running = []
    for row in csv.reader(r.stdout.splitlines()):
        if len(row) >= 2 and os.path.splitext(row[0])[0].lower() in GAME_PROCESSES:
            running.append(f"{row[0]} (pid {row[1]})")
    return running, None


LIVE_BACKUPS = r"C:\Games\Bloodborne\save-backups-bankai-hunter"


def backup(folder, paths, data, beside=False):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if under(folder, LIVE_ROOT) and not beside and os.path.isdir(LIVE_BACKUPS):
        # The live save's backup goes beside the earlier save backups, outside the save folder
        # (nothing the game or an emulator lists, and a redeploy can't touch it).
        base, name = LIVE_BACKUPS, f"{stamp} before sojin-chikage removal"
    else:
        # A long name (>= 32 characters) keeps the save-directory search of the PC port from listing it.
        base, name = os.path.dirname(folder), f"{os.path.basename(folder)} sojin-chikage backup {stamp}"
    dest = os.path.join(base, name)
    k = 1
    while os.path.exists(dest):
        k += 1
        dest = os.path.join(base, f"{name}-{k}")
    try:
        os.makedirs(dest)
        for p in paths:
            q = os.path.join(dest, os.path.basename(p))
            shutil.copy2(p, q)
            with open(q, "rb") as f:
                if f.read() != data[p]:
                    raise OSError(f"backup copy {q} differs from {p}")
    except OSError as e:
        raise SystemExit(f"REFUSED: the backup could not be written ({e}); nothing was changed.")
    return dest


def write_file(path, data):
    tmp = path + ".sojin-tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert every Sojin Chikage in a Bloodborne save into its Chikage of the same level.")
    ap.add_argument("target", help="savedata folder (the one holding userdata0000) or a userdata file")
    ap.add_argument("--apply", action="store_true", help="back up, write and verify (default: dry run)")
    ap.add_argument("--before-start", action="store_true",
                    help="--apply without the running-game guard: the launcher, before it starts the game")
    args = ap.parse_args(argv)
    args.apply = args.apply or args.before_start
    try:
        sys.stdout.reconfigure(errors="replace")    # a non-ASCII character name must not crash the report
    except (AttributeError, ValueError):
        pass

    folder, files = gather(args.target)
    live = [p for p in files if is_live(p)] if not args.before_start else []
    if live:
        running, err = game_processes()
        if running is None:
            print(f"REFUSED: {folder} is the live save folder ({LIVE_ROOT}) and the running processes could "
                  f"not be listed ({err}), so it is unknown whether the game is using the save.")
            return 2
        if running:
            print(f"REFUSED: {', '.join(running)} is running and {folder} is the live save folder "
                  f"({LIVE_ROOT}). The game keeps the save in memory and writes it back, which would undo "
                  f"the conversion or mix old and new data. Close the game (and bb-probe) and run again.")
            return 2

    mode = "APPLY" if args.apply else "DRY RUN (nothing is written; add --apply to convert)"
    print(f"Sojin Chikage -> Chikage save converter  [{mode}]")
    print(f"Folder: {folder}")
    data = {}
    for p in files:
        with open(p, "rb") as f:
            data[p] = f.read()

    plans, problems, names = {}, [], {}
    chars = [p for p in files if len(data[p]) == CHAR_SIZE]
    systems = [p for p in files if len(data[p]) == SYS_SIZE]
    print("Files:")
    for p in files:
        b, d = os.path.basename(p), data[p]
        if p in chars:
            if d.count(0) == len(d):
                print(f"  {b:13} empty character slot")
                continue
            try:
                img, ch, pr, nt = plan_character(d)
            except FormatError as e:
                left = find_values(d)
                print(f"  {b:13} not readable as a character save: {e}")
                if left:
                    problems.append(f"{b}: unreadable, and Sojin-range ids sit at {[hex(o) for o in left]}")
                continue
            names.setdefault(int(b[-4:]), img.name)
            fp = img.fingerprint()
            print(f"  {b:13} character slot {int(b[-4:])} \"{img.name}\": {fp['item records']} item records "
                  f"(table ends {fp['table end']}), inventory count {img.lists[0][3]}, storage box count {img.lists[3][3]}"
                  + (f"; older save images in the file tail at {', '.join(hex(s.base) for s in stale_images(d, img))}" if ch else ""))
            plans[p] = ("character", ch)
            problems += [f"{b}: {x}" for x in pr]
            for x in nt:
                print(f"  {b:13} note: {x}")
        elif p not in systems:
            left = find_values(data[p])
            print(f"  {b:13} unknown file size {len(data[p])}; not touched")
            if left:
                problems.append(f"{b}: unknown file with Sojin-range ids at {[hex(o) for o in left]}")
    for p in systems:
        b = os.path.basename(p)
        ch, pr, nt = plan_system(data[p], names)
        print(f"  {b:13} system data (title-menu character summaries)")
        plans[p] = ("system", ch)
        problems += [f"{b}: {x}" for x in pr]

    total = sum(len(ch) for _, ch in plans.values())
    print()
    print("Sojin Chikage found:" if total else "No Sojin Chikage found.")
    for p, (kind, ch) in plans.items():
        if ch:
            print(f" {os.path.basename(p)}")
            for c in sorted(ch, key=lambda c: c.offset):
                print(c.describe())
    if problems:
        print("\nPROBLEMS (the tool will not write while any of these stand):")
        for x in problems:
            print("  " + x)
    if problems:
        return 1
    if not total:
        return 0

    new = {p: apply_changes(data[p], ch) for p, (kind, ch) in plans.items() if ch}
    checks = {p: verify(plans[p][0], data[p], new[p], plans[p][1]) for p in new}
    bad = [(p, t) for p, cs in checks.items() for ok, t in cs if not ok]
    if bad:
        print("\nREFUSED: the converted data failed its own checks:")
        for p, t in bad:
            print(f"  {os.path.basename(p)}: {t}")
        return 1
    print(f"\n{total} change(s) in {len(new)} file(s); the converted data passed every check in memory:")
    for p, cs in checks.items():
        print(f" {os.path.basename(p)}")
        for ok, t in cs:
            print(f"  [ok] {t}")
    if not args.apply:
        print(f"\nDry run: nothing was written. With --apply the tool first copies "
              f"{', '.join(os.path.basename(p) for p in new)} to a new folder\n  "
              f"{os.path.join(os.path.dirname(folder), os.path.basename(folder) + ' sojin-chikage backup <date-time>')}")
        return 0

    for p in new:   # nothing may have changed since it was read
        with open(p, "rb") as f:
            if f.read() != data[p]:
                print(f"REFUSED: {p} changed while the tool was running; nothing was written.")
                return 1
    dest = backup(folder, list(new), data, beside=args.before_start)
    print(f"Backup: {dest}")

    def restore(why):
        print(f"{why}; restoring the originals from the backup.")
        for p in new:
            shutil.copy2(os.path.join(dest, os.path.basename(p)), p)
            with open(p, "rb") as f:
                same = f.read() == data[p]
            print(f"  {os.path.basename(p)}: {'restored' if same else 'RESTORE FAILED, copy it back from ' + dest}")
        return 1

    try:
        for p in new:
            write_file(p, new[p])
        print("\nVerification (re-read from disk):")
        failed = False
        for p in new:
            with open(p, "rb") as f:
                disk = f.read()
            print(f" {os.path.basename(p)}")
            for ok, t in verify(plans[p][0], data[p], disk, plans[p][1]):
                print(f"  [{'ok' if ok else 'FAIL'}] {t}")
                failed |= not ok
    except BaseException as e:      # a failed write or check (or Ctrl+C) must not leave half a conversion
        return restore(f"WRITE OR CHECK FAILED ({type(e).__name__}: {e})")
    if failed:
        return restore("VERIFICATION FAILED")
    print(f"\nDone: {total} change(s) written to {len(new)} file(s). Originals are in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
