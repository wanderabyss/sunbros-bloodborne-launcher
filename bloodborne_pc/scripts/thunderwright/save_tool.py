#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Thunderwright's Kirkhammer save converter.

Turns every Thunderwright's Kirkhammer in a Bloodborne save, Uncanny and Lost too, into the Kirkhammer
it was made from, at the same level (2060000 + 100*level into 8000000 + ...), so the save keeps
loading without the weapon. Gems stay valid: each level has the Kirkhammer's gem-slot rows. It is the Sojin Chikage's
converter (sojin/save_tool.py, with its checks, backup, read-back and arguments) on this weapon's
ids:

    python save_tool.py <savedata folder or userdata file>            dry run: report only
    python save_tool.py <savedata folder or userdata file> --apply    back up, write, verify
    python save_tool.py <savedata folder> --before-start              --apply, for run.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sojin"))
import save_tool as converter  # noqa: E402

# (first id, the Kirkhammer's first id, the Kirkhammer's sortId of +0, names), as the converter's
# FAMILIES; the weapons' own sortIds of +0 (weapon.VARIANTS).
FAMILIES = (
    (2060000, 8000000, 45100, "Thunderwright's Kirkhammer", "Kirkhammer"),
    (2120000, 8010000, 45200, "Uncanny Thunderwright Hammer", "Uncanny Kirkhammer"),
    (2130000, 8020000, 45300, "Lost Thunderwright Hammer", "Lost Kirkhammer"),
)
SORTS = (55460, 55580, 55620)


def use():
    """Points the converter at this weapon (its tables are module-level)."""
    converter.FAMILIES = FAMILIES
    converter.SOJIN = {family[0] + 100 * lv: (family, lv) for family in FAMILIES for lv in converter.LEVELS}
    converter.SOJIN_SORTS = SORTS
    converter.SOJIN_SORT_PARTS = {converter.sort_part(s + lv): lv for s in SORTS for lv in converter.LEVELS}
    converter.BACKUP_TAG = "thunderwright"
    return converter


if __name__ == "__main__":
    sys.exit(use().main())
