#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Experimental, independent native lamp menu rewrite for the player's 1.09 files.

Made by scripts/enhancements.py when pc_enhanced_lamps is on (off by default). It covers
ordinary, DLC, and shared chalice lamp scripts at verified insertion points; Hunter's Dream's
own lamp keeps the Doll and the box beside it.
"""
from collections import defaultdict
import hashlib
from pathlib import Path
import struct

import esd
from fromsoft import Bnd4, dcx_compress, dcx_decompress


# Exact unmodified CUSA03173 1.09 ESDs from the player's dump. The contents of the game files
# are neither bundled nor copied here. Unknown versions fail closed.
INPUTS = {
    ('m21_01_00_00', 't211000.esd'): '9d9fbd9f9fdc60da1b874b400dbd791b29bd1146f02c80dc04425f6357ae8426',
    ('m22_00_00_00', 't220000.esd'): '18f1bc4e10525837b8b14d4249d1add40be577b8ad8d20463cc80ae5174cee6c',
    ('m22_00_00_00', 't220001.esd'): 'c785e03276b024bc080ca55c3a973ff6e4e8d22b05490eff216b0160ba6c12d7',
    ('m23_00_00_00', 't230000.esd'): 'cbda89378ee742313f5dd412cb301b628df8ca466f293faad095990284a1b5af',
    ('m23_00_00_00', 't230001.esd'): '1a4d33af170cc10d743b4203572eb0a596e5c77b8bb98c769ba95e611a4281fc',
    ('m23_00_00_00', 't230002.esd'): '00d5a1f91322ab4a8c0ae9d64dc104281f575c489fe333baa9a7f4534473f6c6',
    ('m24_00_00_00', 't240000.esd'): 'b03dcd5cb97c7c8cdc6049e3a6c957ce022cde550ab0046a7aed5853deac7aae',
    ('m24_00_00_00', 't240001.esd'): 'ea3a7aebce5a0ebbd7577e75cd0ac86486417200c18bbad4ad47932c93df1d62',
    ('m24_00_00_00', 't240002.esd'): '0a31145d733eb01fb594143eb4dacedc7c15101169bb35aabf238d65e70a67e2',
    ('m24_00_00_00', 't240003.esd'): 'e8071c36e9d8db26baed27ff42832c15366e2511182c78d698bd6381d689cb49',
    ('m24_01_00_00', 't241000.esd'): 'c660fafb5fdc6c1976458e4d3eb015125e185fb2904e671d1d4ae82b953472d5',
    ('m24_01_00_00', 't241001.esd'): 'b1be889ab48113c6125c86d4921179b8fe7ca2664634d98ca333ded93a55a35f',
    ('m24_01_00_00', 't241002.esd'): '38a71a798d6e6d3b40fd94f212f17fbeef2ab721888752ef6f2196e506c4aae4',
    ('m24_01_00_00', 't241003.esd'): 'd5d5148548d0be74e39ad66a694fff12e3fd61320a3dc9a1754b72d5288f5a4d',
    ('m24_02_00_00', 't242000.esd'): 'aedcb172ce5cdd784bac97c1032b14d878e91924dd3cd5e84b63603bc8f873f1',
    ('m24_02_00_00', 't242001.esd'): '4031e5974780e26ed8a28afce41196299f65a9256a6044c39736f7bb7ba0f0d8',
    ('m24_02_00_00', 't242002.esd'): '39534704648b9d4951bbb02b3b057d6bb779bd35bd90fac07faedb6aa9f5dcd3',
    ('m25_00_00_00', 't250000.esd'): 'fffe9ca99c16feb3a77e643b15c11d282952d8547eb0cf13eb0f28d8d185371e',
    ('m25_00_00_00', 't250001.esd'): 'b0dbca4b9990ef1ee5e5d1fee709e6ad4e6d875e3a4128fd7f7ce4ebe523f894',
    ('m25_00_00_00', 't250002.esd'): 'e2bf90524898354c1ba8cb9da3be498a71d0ed65add0bdbe65329033a7fa630a',
    ('m26_00_00_00', 't260000.esd'): 'd764ebb320abd0e8f9561f0f1225ddcafdf266d4154b58f83aab7c43e8d574b7',
    ('m26_00_00_00', 't260001.esd'): '1735ddd39b2726da5c055e0aa8588bf806b92aca4a3739d191bc84ff55c85da6',
    ('m26_00_00_00', 't260002.esd'): 'fc945b27fb04d9df369519fca3c8a758a969154ab76495ee53a87c42689a305f',
    ('m26_00_00_00', 't260003.esd'): 'aff2ec0747ab576e715323bc1212e7195fc54bb729fc68fccb8a081ad9ebcf47',
    ('m27_00_00_00', 't270000.esd'): '7860c0628fed349513d8d63bb255372dc2a1c5b33a45b4d8efdadf17938a0db3',
    ('m27_00_00_00', 't270001.esd'): 'b091291ae39405fa6ef4fbe83c2367e0c1304cef5e0fd35aecb9bbadeb04cd94',
    ('m28_00_00_00', 't280000.esd'): 'c69300e6fe8b848aef61db9aaf6509f5fe211982785bcadb54b12414de1aef6a',
    ('m28_00_00_00', 't280001.esd'): '4dd27d8453006d8a47a2ba48fda160807f849f2483f6924c5f56cf1151f077dc',
    ('m28_00_00_00', 't280002.esd'): '58eaaedd0182f3d43d7888ef44cdc0335688ab145f3e8527b0b439d1e075f4e6',
    ('m28_00_00_00', 't280003.esd'): '787c88582b4dc3f6acca74f70b755b3fecf068b32884e690375c0d55a28c3cfd',
    ('m32_00_00_00', 't320000.esd'): 'd9285af75debc08a172ef45bedbd6d0717dbceb04793f069b3fb494b154c51e4',
    ('m32_00_00_00', 't320001.esd'): '602dd58f8bc179430028fd7190be2f55f207a2f942c89ec56a3056fb1dd7c2d1',
    ('m32_00_00_00', 't320002.esd'): '18b5e980075afde7c34079e3158ff2b55c3264f4ff9f4b9489b909c8215e935c',
    ('m32_00_00_00', 't320003.esd'): 'a624dd8e3998c8df8a1525f2b5b623db3d6c3fc08128b1d6b306c483413239b3',
    ('m33_00_00_00', 't330000.esd'): '00315b65f8a725b3a80089b5718ed8647c466cf14d039dd00ba4256ab7afea30',
    ('m33_00_00_00', 't330001.esd'): 'fe6ba6ec14f6e4c0d80c43fe8125d7827be0cf67171e0dea85ab8cd13306cd00',
    ('m34_00_00_00', 't340000.esd'): '0e003276305bb33e1a7e67857bd19182e2cb4156f7875c95378a7731edae7c37',
    ('m34_00_00_00', 't340001.esd'): '20f3543c710761cf7173bd2c5d173b33463c3895959184a136dc3d9c2a78d710',
    ('m34_00_00_00', 't340002.esd'): '884347c5ec5d3b87a3db1ff90acb91435b035f2e265a0b29df12043a97578eb2',
    ('m34_00_00_00', 't340003.esd'): '9a73f6abff1b3a9bba02772edf651ba1acc0ff796ee9a5ab50c514a84c3f96bc',
    ('m35_00_00_00', 't350000.esd'): 'f824e532158770362570574b9947c6f7860967d2d5782e561141c3cf1e3f9e16',
    ('m35_00_00_00', 't350001.esd'): '96d37abfd73c8259b13d9f9dd317da971c2096c56d787816861b539830711ed2',
    ('m35_00_00_00', 't350002.esd'): '1796aa86671c0a9c780d5b8464f37f1e782c1b57de0d44961aa5252bc4281221',
    ('m36_00_00_00', 't360000.esd'): '7654a29833d6b04f8d9ef681297387ed186b53343223d8f27e2c7e64e5a4c0e3',
    ('m36_00_00_00', 't360001.esd'): '82b2bc38668e2da17d703d34f79fbece1812cae5eac434fe745ff20594bc7d1b',
    ('m36_00_00_00', 't360002.esd'): 'eb6aec0799137c291a92ea376149dd76e1b8268e5a19dffb7b92c570a44266cb',
}

# The shared chalice lamps use a different state layout and two warp arguments.
CHALICE_INPUTS = {
    ('m29_00_00_00', 't290110.esd'): '4081ac830f6794b9f364540f9a7d4eb79b7230fe2cf7dc6fe2018465bd679322',
    ('m29_00_00_00', 't290111.esd'): 'cccf90bdefa003ca7df7e34a9dd12c80f69e6585abac270ab53ec250c3c59912',
    ('m29_00_00_00', 't290112.esd'): 'f2f031e4528948cbe5be964535cac2e8771b90377f279f666f6924107184a99f',
    ('m29_00_00_00', 't290113.esd'): 'cd7007add4732e4673c6e9af60e594098500784af9520835f8650cd2a6eb9659',
    ('m29_00_00_00', 't290114.esd'): '4857667037b8da0d660b6afed45a75ad0ab10f37fcc82c59d8ae4b89c16ca23c',
    ('m29_00_00_00', 't290115.esd'): 'd4b0006970aafabd8553df5c8b00147711ec476fa6199fba571a5a43c0640273',
    ('m29_00_00_00', 't290116.esd'): 'f9c3f53013eb728e44970a92aaeb077a9bbfea08d2f75dac2947e24c8fb12870',
    ('m29_00_00_00', 't290117.esd'): '283ceef063ad621fcfde572e3b44fc6224370da64127a1ab19187130bf651b30',
    ('m29_00_00_00', 't290118.esd'): 'd7b39ba4bbc12f0d924e8b0686ac06f4add584e9b9791d12549930ac6994c625',
    ('m29_00_00_00', 't290119.esd'): '81505aed80293f192f44b7cd1019dfef5a3ffae66941e6131d14a34adcffbd0a',
}

ACTIVE_GROUP = 2147483644
ACTIVE_STATE = 6
VANILLA_WARP_GROUP = 2147483643
LAMP_MENU_GROUP = 2147483600
LEVEL_INTRO_DONE = 6700
STORAGE_INTRO_DONE = 6701
EQ = b'\x95'


class UnsupportedLamp(ValueError):
    pass


def _eq(lhs, rhs):
    return esd.done(lhs + esd.lit(rhs) + EQ)


def add_lamp_menu(data: bytes, expected_sha: str, *, active_state: int = 6,
                  follow_state: int = 5, warp_args: int = 3,
                  rematch: tuple[int, int, int] | None = None) -> bytes:
    """Add Level Up and Storage to one activated lamp while retaining its original warp path."""
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise UnsupportedLamp('unexpected lamp ESD hash')
    script = esd.parse(data)
    if script.group(LAMP_MENU_GROUP):
        raise UnsupportedLamp('lamp menu group is already present')
    active = script.group(ACTIVE_GROUP)
    if active is None:
        raise UnsupportedLamp('activated-lamp state group is missing')
    site = script.state_in(active, active_state)
    if site < 0:
        raise UnsupportedLamp('activated-lamp state is missing')
    entry = script.runs[script.states[site].entry].items
    if len(entry) != 1:
        raise UnsupportedLamp('activated-lamp action is not a single call')
    old = script.cmds[entry[0]]
    if old.bank != 6 or old.id != VANILLA_WARP_GROUP:
        raise UnsupportedLamp('activated-lamp action is not the vanilla warp call')
    args = [script.exprs[i].code for i in script.runs[old.args].items]
    if len(args) != warp_args:
        raise UnsupportedLamp('vanilla warp call has an unexpected parameter count')
    follow = script.state_in(active, follow_state)
    if follow < 0:
        raise UnsupportedLamp('vanilla post-warp state is missing')
    warp_conditions = script.runs[script.states[site].conds].items
    follow_conditions = script.runs[script.states[follow].conds].items
    if (len(warp_conditions) != 2
            or [script.conds[c].target for c in warp_conditions] != [-1, follow]
            or len(follow_conditions) != 1
            or script.conds[follow_conditions[0]].target != -1):
        raise UnsupportedLamp('vanilla warp continuation has an unknown shape')

    # Preserve the existing action's three arguments for the Warp choice. A separate group opens
    # the game's own talk list; it calls the game's own level, storage and warp operations.
    script.states[site].entry = script.run([script.cmd(6, LAMP_MENU_GROUP, args)])
    states = [script.state(i) for i in range(14 if rematch else 11)]
    script.groups.append(esd.Group(LAMP_MENU_GROUP, states))
    start, menu, level, storage, warp, restart, end, add_level, add_storage, choose, storage_gate = states[:11]
    if rematch:
        rematch_gate, add_rematch, rematch_action = states[11:]
    true = esd.done(esd.lit(1))

    script.states[start].conds = script.run([script.cond(menu, true)])

    def command(id, *args):
        return script.cmd(1, id, [esd.done(esd.lit(arg)) for arg in args])

    script.states[menu].entry = script.run([
        command(20),  # ClearTalkListData
        command(19, 1, 70002100, -1),  # Hunter's Dream
    ])
    # The Doll sets this vanilla flag on the first level-up introduction. Requiring it keeps a
    # new character's first level-up with the Doll and avoids skipping her initial progression.
    script.states[menu].conds = script.run([
        script.cond(add_level, _eq(esd.call(15, [LEVEL_INTRO_DONE]), 1)),
        script.cond(storage_gate, true),
    ])
    script.states[add_level].entry = script.run([command(19, 2, 15000100, -1)])
    script.states[add_level].conds = script.run([script.cond(storage_gate, true)])
    # The vanilla storage interaction likewise shows a first-use explanation, then sets 6701.
    after_storage = rematch_gate if rematch else choose
    script.states[storage_gate].conds = script.run([
        script.cond(add_storage, _eq(esd.call(15, [STORAGE_INTRO_DONE]), 1)),
        script.cond(after_storage, true),
    ])
    script.states[add_storage].entry = script.run([command(19, 3, 70000000, -1)])
    script.states[add_storage].conds = script.run([script.cond(after_storage, true)])
    if rematch:
        defeated_flag, request_flag, text_id = rematch
        script.states[rematch_gate].conds = script.run([
            script.cond(add_rematch, _eq(esd.call(15, [defeated_flag]), 1)),
            script.cond(choose, true),
        ])
        script.states[add_rematch].entry = script.run([command(19, 4, text_id, -1)])
        script.states[add_rematch].conds = script.run([script.cond(choose, true)])
        script.states[rematch_action].entry = script.run([command(11, request_flag, 1)])
        script.states[rematch_action].conds = script.run([script.cond(end, true)])
    script.states[choose].entry = script.run([command(10, 0, 0, 0)])  # vanilla Doll/box choice list
    # The first condition consumes the selected entry and stores it in register 0.
    # Subsequent conditions read that same value, as the game's own talk scripts do.
    choice = esd.lit(23) + b'\x84\xa7'
    choices = [
        script.cond(warp, _eq(choice, 1)),
        script.cond(level, _eq(b'\xaf', 2)),
        script.cond(storage, _eq(b'\xaf', 3)),
    ]
    if rematch:
        choices.append(script.cond(rematch_action, _eq(b'\xaf', 4)))
    choices.append(script.cond(end, _eq(esd.call(53, []), 0)))  # menu closed
    script.states[choose].conds = script.run(choices)

    script.states[level].entry = script.run([command(31)])  # OpenSoul
    script.states[level].conds = script.run([
        script.cond(menu, _eq(esd.call(59, [23, 0]), 0))
    ])
    script.states[storage].entry = script.run([command(30)])  # OpenRepository
    script.states[storage].conds = script.run([
        script.cond(menu, _eq(esd.call(59, [200, 0]), 0))
    ])

    # Pass the original warp parameters through the new group in the same order.
    passthrough = [esd.done(bytes((0x40 + i, 0xb8))) for i in range(warp_args)]
    script.states[warp].entry = script.run([script.cmd(6, VANILLA_WARP_GROUP, passthrough)])
    # Preserve both vanilla warp outcomes, including its post-warp root call.
    script.states[warp].conds = script.run([
        script.cond(end, script.exprs[script.conds[warp_conditions[0]].eval].code),
        script.cond(restart, script.exprs[script.conds[warp_conditions[1]].eval].code),
    ])
    script.states[restart].entry = script.run(list(script.runs[script.states[follow].entry].items))
    script.states[restart].conds = script.run([
        script.cond(end, script.exprs[script.conds[follow_conditions[0]].eval].code)
    ])
    script.states[end].conds = script.run([script.cond(-1, true)])  # return to the vanilla caller

    wait = script.cmd(1, 68, [b'\x81' + struct.pack('<d', 0.33) + b'\xa1'])
    for state in (choose, level, storage):
        script.states[state].whiles = script.run([wait])

    result = esd.serialize(script)
    if esd.serialize(esd.parse(result)) != result:
        raise UnsupportedLamp('patched script does not round-trip')
    return result


def make(dvdroot: Path, rematches=None) -> dict[Path, bytes]:
    """Build supported lamp archives from an exact 1.09 dump; return no partial output.
    rematches: {(map, script): (defeat flag, request flag, text id)} adds a boss rematch entry to
    those lamps' menus (boss_rematches.lamp_rows)."""
    rematches = dict(rematches or {})
    unknown = set(rematches) - set(INPUTS)
    if unknown:
        raise UnsupportedLamp(f'no lamp script {sorted(unknown)[0]} to add a rematch to')
    targets = defaultdict(list)
    for (map_name, script_name), digest in INPUTS.items():
        targets[map_name].append((script_name, digest, 6, 5, 3))
    for (map_name, script_name), digest in CHALICE_INPUTS.items():
        targets[map_name].append((script_name, digest, 5, 4, 2))
    files = {}
    for map_name, scripts in sorted(targets.items()):
        relative = Path('script') / 'talk' / f'{map_name}.talkesdbnd.dcx'
        packed = (dvdroot / relative).read_bytes()
        archive = Bnd4(dcx_decompress(packed))
        for script_name, digest, active_state, follow_state, warp_args in scripts:
            i = archive.index(script_name)
            archive.files[i] = add_lamp_menu(archive.files[i], digest,
                                            active_state=active_state,
                                            follow_state=follow_state, warp_args=warp_args,
                                            rematch=rematches.get((map_name, script_name)))
        files[relative] = dcx_compress(archive.to_bytes(), template=packed)
    return files
