#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 Sojin Chikage's save converter.

Turns every Bloodsworn weapon in a Bloodborne save into its Chikage at the same level, so the save
keeps loading without them. Gems stay valid: each level has that Chikage's gem-slot row. It is the
Sojin Chikage's converter (sojin/save_tool.py, with its checks, backup, read-back and arguments) on
these weapons' ids:

    python save_tool.py <savedata folder or userdata file>            dry run: report only
    python save_tool.py <savedata folder or userdata file> --apply    back up, write, verify
    python save_tool.py <savedata folder> --before-start              --apply, for run.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sojin"))
import save_tool as converter  # noqa: E402

# As weapon.py: (first id, its Chikage's first id, that Chikage's sortId of +0, names).
FAMILIES = (
    (2080000, 2000000, 55100, "Bloodsworn Sojin Chikage", "Chikage"),
    (2100000, 2010000, 55200, "Uncanny Bloodsworn Sojin", "Uncanny Chikage"),
    (2110000, 2020000, 55300, "Lost Bloodsworn Sojin", "Lost Chikage"),
)
SORTS = (55520, 55540, 55560)


def use():
    """Points the converter at these weapons (its tables are module-level)."""
    converter.FAMILIES = FAMILIES
    converter.SOJIN = {family[0] + 100 * lv: (family, lv) for family in FAMILIES for lv in converter.LEVELS}
    converter.SOJIN_SORTS = SORTS
    converter.SOJIN_SORT_PARTS = {converter.sort_part(s + lv): lv for s in SORTS for lv in converter.LEVELS}
    converter.BACKUP_TAG = "ng7-chikage"
    return converter


if __name__ == "__main__":
    sys.exit(use().main())
