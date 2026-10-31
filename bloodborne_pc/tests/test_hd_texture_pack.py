from paths import ROOT
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from texture_fixtures import bxf4, tpf
from test_fromsoft import bnd4

sys.path.insert(0, str(ROOT / 'scripts'))
import fromsoft  # noqa: E402

spec = importlib.util.spec_from_file_location('hd_texture_pack', ROOT / 'scripts/hd_texture_pack.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)
pack.game_running = lambda: False


def texture(name, pixels):
    return fromsoft.dcx_compress(tpf([name], pixels))


def parts(pixels, model=b'model'):
    root = 'N:\\SPRJ\\data\\INTERROOT_ps4\\parts\\FullBody\\BD_M_1100\\'
    return fromsoft.dcx_compress(bnd4([(root + 'BD_M_1100.tpf', tpf(['bd_m_1100_a'], pixels)),
                                       (root + 'BD_M_1100.flver', model)]))


GAME_MAP = [(f'{n}.tpf.dcx', texture(n, b'game ' + n.encode())) for n in ('a', 'b', 'c', 'd')]


class BuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / 'game'
        maps = self.game / 'dvdroot_ps4' / 'map' / 'm21'
        maps.mkdir(parents=True)
        bhd, bdt = bxf4(GAME_MAP)
        (maps / 'm21_0000.tpfbhd').write_bytes(bhd)
        (maps / 'm21_0000.tpfbdt').write_bytes(bdt)
        (self.game / 'dvdroot_ps4' / 'parts').mkdir()
        (self.game / 'dvdroot_ps4' / 'parts' / 'bd_m_1100.partsbnd.dcx').write_bytes(parts(b'game'))
        (self.game / 'dvdroot_ps4' / 'param' / 'gameparam').mkdir(parents=True)
        (self.game / 'dvdroot_ps4' / 'param' / 'gameparam' / 'gameparam.parambnd.dcx').write_bytes(b'params')
        self.downloads = self.root / 'downloads'
        self.downloads.mkdir()
        self.out = self.root / 'mods'
        self.listing = self.root / 'sources.json'
        self.listing.write_text(json.dumps({'sources': [
            {'id': 'R0', 'title': 'World', 'author': 'A', 'mod': 1, 'download': 'World 0'},
            {'id': 'SKY', 'title': 'Sky', 'author': 'B', 'mod': 2, 'download': 'Sky'},
            {'id': 'ARM', 'title': 'Armour', 'author': 'C', 'mod': 3, 'download': 'Armour'}]}))

    def zip(self, name, files):
        with zipfile.ZipFile(self.downloads / name, 'w', zipfile.ZIP_DEFLATED) as z:
            for path, data in files.items():
                z.writestr(path, data)

    def map_files(self, wrapper, entries):
        bhd, bdt = bxf4(entries)
        return {f'{wrapper}/map/m21/m21_0000.tpfbhd': bhd, f'{wrapper}/map/m21/m21_0000.tpfbdt': bdt}

    def downloads_all(self):
        world = [(n, texture(n[0], b'world ' + n[0].encode())) for n, _ in GAME_MAP[:3]] + [GAME_MAP[3]]
        # The sky ships the whole archive: a and b are the game's own, c and d are its changes.
        sky = [GAME_MAP[0], GAME_MAP[1], ('c.tpf.dcx', texture('c', b'sky c')), ('d.tpf.dcx', texture('d', b'sky d'))]
        self.zip('World 0-1-1-100.zip', self.map_files('World_textures_0', world))
        self.zip('Sky-2-2-0-200_2.zip', {**self.map_files('sky/dvdroot_ps4', sky),
                                         'sky/dvdroot_ps4/param/gameparam/gameparam.parambnd.dcx': b'cheat',
                                         'sky/readme.txt': b'hello'})
        self.zip('Armour-3-1-300.zip', {'parts/bd_m_1100.partsbnd.dcx': parts(b'4x', model=b'edited'),
                                        'parts/bd_m_9999.partsbnd.dcx': parts(b'new'),
                                        'tools/install.exe': b'MZ'})

    def build(self, **kwargs):
        lines = io.StringIO()
        with contextlib.redirect_stdout(lines), contextlib.redirect_stderr(io.StringIO()):
            report = pack.build(self.game, self.downloads, self.out, listing=self.listing, **kwargs)
        return report, lines.getvalue()

    def merged(self):
        folder = self.out / 'HD Texture Pack' / 'dvdroot_ps4' / 'map' / 'm21'
        archive = fromsoft.Bxf4((folder / 'm21_0000.tpfbhd').read_bytes())
        with open(folder / 'm21_0000.tpfbdt', 'rb') as bdt:
            return {name: fromsoft.dcx_decompress(archive.read(bdt, i))[-7:]
                    for i, name in enumerate(archive.names)}, archive

    def test_maps_merge_texture_by_texture(self):
        self.downloads_all()
        report, _ = self.build()
        textures, archive = self.merged()
        # a and b: the world mod's (the sky's copies are the game's own); c: both changed it, the
        # sky wins; d: only the sky changed it.
        self.assertEqual((textures['a.tpf.dcx'], textures['b.tpf.dcx']), (b'world a', b'world b'))
        self.assertTrue(textures['c.tpf.dcx'].endswith(b'sky c'))
        self.assertTrue(textures['d.tpf.dcx'].endswith(b'sky d'))
        self.assertEqual(archive.names, [n for n, _ in GAME_MAP])
        self.assertEqual(report['merged_maps'], [{'path': 'map/m21/m21_0000.tpfbhd', 'SKY': 2, 'R0': 2, 'game': 0}])

    def test_gameplay_files_and_new_files_are_refused(self):
        self.downloads_all()
        report, _ = self.build()
        refused = {(r['source'], r['path']): r['reason'] for r in report['refused']}
        self.assertEqual(refused[('SKY', 'param/gameparam/gameparam.parambnd.dcx')], 'game parameters')
        self.assertIn('no new files', refused[('ARM', 'parts/bd_m_9999.partsbnd.dcx')])
        self.assertIn(('ARM', 'tools/install.exe'), refused)
        built = self.out / 'HD Texture Pack' / 'dvdroot_ps4'
        self.assertFalse((built / 'param').exists())
        files = sorted(p.relative_to(built).as_posix() for p in built.rglob('*') if p.is_file())
        self.assertEqual(files, ['map/m21/m21_0000.tpfbdt', 'map/m21/m21_0000.tpfbhd', 'parts/bd_m_1100.partsbnd.dcx'])

    def test_container_keeps_the_game_model(self):
        self.downloads_all()
        report, _ = self.build()
        data = (self.out / 'HD Texture Pack' / 'dvdroot_ps4' / 'parts' / 'bd_m_1100.partsbnd.dcx').read_bytes()
        archive = fromsoft.Bnd4(fromsoft.dcx_decompress(data))
        self.assertEqual(archive.files[1], b'model')
        self.assertEqual(archive.files[0], tpf(['bd_m_1100_a'], b'4x'))
        self.assertEqual(report['rebuilt'][0]['path'], 'parts/bd_m_1100.partsbnd.dcx')

    def test_pack_json_progress_and_replacing_an_old_pack(self):
        self.downloads_all()
        old = self.out / 'HD Texture Pack' / 'dvdroot_ps4'
        old.mkdir(parents=True)
        (old / 'stale.txt').write_text('old')
        report, stdout = self.build(show_progress=True)
        folder = self.out / 'HD Texture Pack'
        self.assertFalse((folder / 'dvdroot_ps4' / 'stale.txt').exists())
        self.assertFalse((self.out / 'HD Texture Pack.new').exists())
        saved = json.loads((folder / 'pack.json').read_text())
        self.assertTrue(saved['picture_only'])
        self.assertEqual([s['id'] for s in saved['sources']], ['R0', 'SKY', 'ARM'])
        self.assertEqual(len(saved['sources'][0]['sha256']), 64)
        self.assertIn('Sky by B', (folder / 'README.txt').read_text())
        lines = [json.loads(line) for line in stdout.splitlines()]
        self.assertEqual(lines[-1]['stage'], 'done')
        self.assertEqual(lines[-1]['done'], lines[-1]['total'])
        self.assertTrue(all(a['done'] <= b['done'] for a, b in zip(lines, lines[1:])))

    def test_dry_run_and_missing_downloads(self):
        self.zip('Armour-3-1-300.zip', {'parts/bd_m_1100.partsbnd.dcx': parts(b'4x')})
        report, _ = self.build(dry_run=True)
        self.assertEqual(report['missing_sources'], ['R0', 'SKY'])
        self.assertEqual(report['planned'], {'parts/bd_m_1100.partsbnd.dcx': ['ARM']})
        self.assertFalse(self.out.exists())

    def test_unchanged_archive_is_left_out(self):
        bhd, bdt = bxf4(GAME_MAP)
        self.zip('Sky-2-1.zip', {'dvdroot_ps4/map/m21/m21_0000.tpfbhd': bhd, 'dvdroot_ps4/map/m21/m21_0000.tpfbdt': bdt})
        report, _ = self.build()
        self.assertEqual(report['files'], 0)
        self.assertFalse((self.out / 'HD Texture Pack' / 'dvdroot_ps4' / 'map' / 'm21' / 'm21_0000.tpfbhd').exists())

    def test_source_left_out_by_default(self):
        listing = json.loads(self.listing.read_text())
        listing['sources'][2]['default'] = False  # ARM
        self.listing.write_text(json.dumps(listing))
        self.downloads_all()
        report, _ = self.build()
        self.assertEqual(report['left_out'], ['ARM'])
        self.assertNotIn('ARM', [s['id'] for s in report['sources']])
        self.assertFalse((self.out / 'HD Texture Pack' / 'dvdroot_ps4' / 'parts').exists())
        report, _ = self.build(include=('ARM',))
        self.assertEqual(report['left_out'], [])
        self.assertTrue((self.out / 'HD Texture Pack' / 'dvdroot_ps4' / 'parts').exists())

    def test_no_downloads(self):
        with self.assertRaises(ValueError):
            self.build()

    def test_game_path(self):
        self.assertEqual(pack.game_path('BBReborne_textures_0\\map\\m21\\m21_0000.tpfbdt'), 'map/m21/m21_0000.tpfbdt')
        self.assertEqual(pack.game_path('x/CUSA03173/dvdroot_ps4/sfx/a.ffxbnd.dcx'), 'sfx/a.ffxbnd.dcx')
        self.assertIsNone(pack.game_path('readme.txt'))


if __name__ == '__main__':
    unittest.main()
