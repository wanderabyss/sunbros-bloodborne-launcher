from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core

CASES = Path(__file__).resolve().parent / 'data' / 'rt_settings.txt'


def cases(kind):
    """The rows of one kind in tests/data/rt_settings.txt (read by tests/test_rt_settings.cpp too):
    (input, expected words)."""
    rows = []
    for line in CASES.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        row_kind, given, expected = (part.strip() for part in line.split('|'))
        if row_kind == kind:
            rows.append((given, expected.split()))
    return rows


class RayTracingMigrationTests(unittest.TestCase):
    """bbport.ini files from before the quality tiers show the nearest tier in the launcher, as
    bbport_settings.cpp Load reads them; Custom starts as the in-game menu's does."""

    def migrated(self, ini):
        values = {**core.INI_DEFAULTS, **ini}
        core.migrate_ray_tracing(values, set(ini))
        return values

    def test_shared_migration_cases(self):
        rows = cases('migrate')
        self.assertGreaterEqual(len(rows), 20)
        for given, expected in rows:
            ini = dict(pair.split('=', 1) for pair in given.split(';') if pair)
            values = self.migrated(ini)
            with self.subTest(ini=given):
                self.assertEqual([values['ray_tracing'], values['rt_ao_quality'],
                                  values['rt_shadow_quality']], expected)
                # The keys before the tiers are not written again.
                self.assertFalse(set(core.RETIRED_RT_KEYS) & set(values))

    def test_level_tiers_match_the_game(self):
        rows = cases('level')
        self.assertEqual({level for level, _ in rows}, set(core.LEVEL_TIERS))
        for level, expected in rows:
            self.assertEqual(list(core.LEVEL_TIERS[level]), expected)

    def test_custom_starts_from_the_level(self):
        for given, expected in cases('custom'):
            level, ao, shadows, strength = given.split()
            values = {'rt_ao_quality': ao, 'rt_shadow_quality': shadows, 'rt_ao_strength': strength}
            changed = core.custom_start(level, values)
            with self.subTest(case=given):
                self.assertEqual([values['rt_ao_quality'], values['rt_shadow_quality']], expected[:2])
                self.assertAlmostEqual(float(values['rt_ao_strength']), float(expected[2]))
                self.assertEqual(changed, [ao, shadows] != expected[:2])

    def test_save_drops_the_old_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            ini.write_text('# kept\npreset=1\nambient_occlusion=raytraced\nshadows=raytraced\n'
                           'rt_shadow_reach=20\nrt_ao_rays=1\nother_key=5\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                values, lines = core.load_ini()
                core.save_ini({k: values[k] for k in core.INI_DEFAULTS}, lines)
                text = ini.read_text(encoding='utf-8')
                again, _ = core.load_ini()
        keys = {line.split('=', 1)[0] for line in text.splitlines() if '=' in line}
        self.assertFalse(set(core.RETIRED_RT_KEYS) & keys)
        for line in ('# kept', 'preset=1', 'other_key=5', 'ray_tracing=custom',
                     'rt_ao_quality=medium', 'rt_shadow_quality=high'):
            self.assertIn(line, text.splitlines())
        self.assertEqual((again['ray_tracing'], again['rt_ao_quality'], again['rt_shadow_quality']),
                         ('custom', 'medium', 'high'))

    def test_every_choice_has_a_label(self):
        tiers = ['off', 'low', 'medium', 'high', 'ultra']
        self.assertEqual([value for value, _ in core.RT_AO_QUALITIES], tiers)
        self.assertEqual([value for value, _ in core.RT_SHADOW_QUALITIES], tiers)
        self.assertEqual([value for value, _ in core.RAY_TRACING], tiers + ['custom'])


if __name__ == '__main__':
    unittest.main()
