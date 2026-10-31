from paths import ROOT
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import tempfile
import exit_text
from menu_assets import fmg_read, fmg_write


def test_replaces_only_exit_label_help_and_confirmation():
    groups = [200, 201, 204, 78]
    files = [fmg_write({110004: b'O\0', 110000: b'Q\0', 1: b'X\0'}) for _ in groups]
    original = files.copy()
    archive = SimpleNamespace(ids=groups, files=files, to_bytes=lambda: b'repacked')
    with mock.patch.object(exit_text, 'Bnd4', return_value=archive), \
         mock.patch.object(exit_text, 'dcx_decompress', side_effect=lambda b: b), \
         mock.patch.object(exit_text, 'dcx_compress', return_value=b'output'):
        assert exit_text.rewrite(b'input') == b'output'
    for i, group in enumerate(groups):
        before, after = fmg_read(original[i]), fmg_read(files[i])
        for key, value in before.items():
            replacement = exit_text.REPLACEMENTS.get(group, {}).get(key)
            assert after[key] == (replacement.encode('utf-16-le') if replacement else value)


def test_opt_out_removes_stale_generated_wording():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        old = root / 'out/dvdroot_ps4/msg/engus/menu.msgbnd.dcx'
        old.parent.mkdir(parents=True)
        old.write_bytes(b'old')
        with mock.patch('sys.argv', ['exit_text', '--game', str(root/'game'), '--out', str(root/'out')]), \
             mock.patch.dict('os.environ', {'BB_EXIT_TO_DESKTOP': '0'}):
            exit_text.main()
        assert not old.exists()
