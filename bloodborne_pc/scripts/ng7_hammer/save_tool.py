#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 hammer's save converter.

Turns every Stormforged Kirkhammer in a Bloodborne save into the Kirkhammer at the same level
(2070000 + 100*level into 8000000 + ...), so the save keeps loading without the weapon. Gems stay
valid: each level has the Kirkhammer's gem-slot row. It is the Sojin Chikage's converter
(sojin/save_tool.py, with its checks, backup, read-back and arguments) on this weapon's ids:

    python save_tool.py <savedata folder or userdata file>            dry run: report only
    python save_tool.py <savedata folder or userdata file> --apply    back up, write, verify
    python save_tool.py <savedata folder> --before-start              --apply, for run.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sojin"))
import save_tool as converter  # noqa: E402

# As weapon.py: (first id, the Kirkhammer's first id, the Kirkhammer's sortId of +0, names).
FAMILIES = ((2070000, 8000000, 45100, "Stormforged Kirkhammer", "Kirkhammer"),)
SORTS = (55480,)


def use():
    """Points the converter at this weapon (its tables are module-level)."""
    converter.FAMILIES = FAMILIES
    converter.SOJIN = {family[0] + 100 * lv: (family, lv) for family in FAMILIES for lv in converter.LEVELS}
    converter.SOJIN_SORTS = SORTS
    converter.SOJIN_SORT_PARTS = {converter.sort_part(s + lv): lv for s in SORTS for lv in converter.LEVELS}
    converter.BACKUP_TAG = "ng7-hammer"
    return converter


if __name__ == "__main__":
    sys.exit(use().main())
