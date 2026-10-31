from paths import ROOT
import importlib.util
import sys
import unittest

from texture_fixtures import bxf4, tpf
from test_fromsoft import bnd4

sys.path.insert(0, str(ROOT / 'scripts'))
import fromsoft  # noqa: E402

spec = importlib.util.spec_from_file_location('picture_gate', ROOT / 'scripts/picture_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def parts(texture, model=b'model', cloth=b'cloth'):
    root = 'N:\\SPRJ\\data\\INTERROOT_ps4\\parts\\FullBody\\BD_M_1100\\'
    return fromsoft.dcx_compress(bnd4([(root + 'BD_M_1100.tpf', texture), (root + 'BD_M_1100.flver', model),
                                       (root + 'BD_M_1100_c.hkx', cloth)]))


class RuleTests(unittest.TestCase):
    def test_picture_paths_pass(self):
        for path in ('map/m21/m21_0000.tpfbhd', 'map/m24/m24_01_0003.tpfbdt', 'dvdroot_ps4/map/m29/m29_0002.tpfbhd',
                     'parts/bd_m_1100.partsbnd.dcx', 'sfx/frpg_sfxbnd_commoneffects.ffxbnd.dcx',
                     'menu/common.tpf.dcx', 'Map\\M21\\M21_0000.TPFBHD'):
            self.assertIsNotNone(gate.rule(path)[0], path)

    def test_gameplay_and_programs_are_refused(self):
        for path in ('map/MapStudio/m21_00_00_00.msb.dcx', 'event/m21_00_00_00.emevd.dcx',
                     'script/aicommon.luabnd.dcx', 'script/talk/m24_02_00_00.talkesdbnd.dcx',
                     'param/gameparam/gameparam.parambnd.dcx', 'msg/engus/item.msgbnd.dcx',
                     'chr/c0000.anibnd.dcx', 'map/m24_00_00_00/h24_00_00_00.hkxbhd',
                     'map/m24_00_00_00/m24_00_00_00_0000.btl.dcx', 'param/drawparam/m24_drawparam.parambnd.dcx',
                     'map/m24/gi_env_m24.tpfbhd', 'map/m24/m24_0000.tpfbhd.patch', 'chr/c2500.chrbnd.dcx',
                     'obj/o000100.objbnd.dcx', 'mtd/allmaterialbnd.mtdbnd.dcx', 'eboot.bin', 'sce_sys/param.sfo',
                     'map/m24/m24_00_00_00/m24_00_00_00_000000.flver.dcx', 'shader/x.dll', 'map/run.ps1',
                     'map/m24/m24_cgrading.tpf.patch'):
            kind, reason = gate.rule(path)
            self.assertIsNone(kind, path)
            self.assertTrue(reason)
        self.assertFalse(gate.quick('param/gameparam/gameparam.parambnd.dcx'))
        self.assertTrue(gate.quick('map/m21/m21_0000.tpfbdt'))


class MapTests(unittest.TestCase):
    def test_same_names_pass_new_names_and_lightmaps_do_not(self):
        game, _ = bxf4([('a.tpf.dcx', b'1'), ('b.tpf.dcx', b'2')])
        same, _ = bxf4([('A.tpf.dcx', b'11'), ('b.tpf.dcx', b'22')])
        self.assertEqual(gate.check_map_header(game, same), [])
        new, _ = bxf4([('a.tpf.dcx', b'1'), ('c.tpf.dcx', b'3')])
        self.assertIn('c.tpf.dcx', gate.check_map_header(game, new)[0])
        lightmap_game, _ = bxf4([('24000000_m0_gi_0000_00_dol_00.tpf.dcx', b'1')])
        self.assertTrue(gate.check_map_header(lightmap_game, lightmap_game))
        self.assertTrue(gate.check_map_header(game, b'BND4' + b'\0' * 60))

    def test_entry_must_hold_the_game_textures(self):
        game = fromsoft.dcx_compress(tpf(['wall_a']))
        self.assertIsNone(gate.check_map_entry(game, fromsoft.dcx_compress(tpf(['wall_a'], b'bigger pixels'))))
        self.assertIn('does not have', gate.check_map_entry(game, fromsoft.dcx_compress(tpf(['wall_a', 'x']))))
        self.assertIn('not a texture', gate.check_map_entry(game, b'not a tpf'))


class ContainerTests(unittest.TestCase):
    def test_texture_only_change_takes_the_mod_file(self):
        game = parts(tpf(['bd_m_1100_a']))
        mod = parts(tpf(['bd_m_1100_a'], b'4x pixels'))
        verdict = gate.check_container(game, mod)
        self.assertEqual(verdict.verdict, gate.ACCEPT)
        self.assertEqual(verdict.data, mod)

    def test_other_changes_keep_the_game_entries(self):
        game = parts(tpf(['bd_m_1100_a']))
        mod = parts(tpf(['bd_m_1100_a'], b'4x pixels'), model=b'edited model', cloth=b'edited cloth')
        verdict = gate.check_container(game, mod)
        self.assertEqual(verdict.verdict, gate.TEXTURES_ONLY)
        self.assertIn('kept', verdict.reason)
        rebuilt = fromsoft.Bnd4(fromsoft.dcx_decompress(verdict.data))
        self.assertEqual(rebuilt.files[1:], [b'model', b'cloth'])
        self.assertEqual(rebuilt.files[0], tpf(['bd_m_1100_a'], b'4x pixels'))

    def test_no_texture_change_or_unreadable_is_refused(self):
        game = parts(tpf(['bd_m_1100_a']))
        self.assertEqual(gate.check_container(game, parts(tpf(['bd_m_1100_a']), model=b'x')).verdict, gate.REFUSE)
        self.assertEqual(gate.check_container(game, b'junk').verdict, gate.REFUSE)
        renamed = parts(tpf(['bd_m_1100_a', 'extra'], b'4x'))
        self.assertEqual(gate.check_container(game, renamed).verdict, gate.REFUSE)

    def test_loose_texture(self):
        game = fromsoft.dcx_compress(tpf(['menu_a']))
        self.assertEqual(gate.check_texture(game, fromsoft.dcx_compress(tpf(['menu_a'], b'hd'))).verdict, gate.ACCEPT)
        self.assertEqual(gate.check_texture(game, fromsoft.dcx_compress(tpf(['other']))).verdict, gate.REFUSE)


if __name__ == '__main__':
    unittest.main()
