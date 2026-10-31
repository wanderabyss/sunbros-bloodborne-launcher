import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_coop as coop


class CoopTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {'LOCALAPPDATA': self.folder.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.folder.cleanup)

    def test_invite_round_trip_and_damage(self):
        code = coop.make_invite('100.64.0.10', 'abc123')
        self.assertTrue(code.startswith(coop.INVITE_PREFIX))
        self.assertEqual(coop.read_invite('  ' + code + '\n'), ('100.64.0.10', 'abc123'))
        # Wrapped by a chat app over two lines.
        self.assertEqual(coop.read_invite(code[:20] + '\r\n ' + code[20:]), ('100.64.0.10', 'abc123'))
        with self.assertRaises(coop.CoopError):
            coop.read_invite('hello')
        with self.assertRaises(coop.CoopError):
            coop.read_invite(coop.INVITE_PREFIX + '!!!')

    def test_registration_key_is_made_once(self):
        cfg = coop.package_dir('server') / 'server' / 'shadnet.cfg'
        cfg.parent.mkdir(parents=True)
        cfg.write_text('[General]\nHost=0.0.0.0\nRegistrationSecretKey=\n', encoding='utf-8')
        with mock.patch.object(coop, 'bundled_server', return_value=None):  # BBSC's own server
            key = coop.registration_key()
            self.assertEqual(len(key), 40)
            self.assertEqual(coop.registration_key(), key)
        self.assertIn(f'RegistrationSecretKey={key}', cfg.read_text(encoding='utf-8'))

    def test_the_bundled_server_runs_from_its_own_folder_with_the_hosts_key(self):
        # This port's shadnet.exe (STUN fix) keeps its config and database beside itself: it is
        # copied under bbport-coop and takes BBSC's configuration, key included, the first time.
        bbsc = coop.package_dir('server') / 'server'
        bbsc.mkdir(parents=True)
        (bbsc / 'shadnet.cfg').write_text('[General]\nRegistrationSecretKey=hostkey\n', encoding='utf-8')
        bundled = Path(self.folder.name) / 'port' / 'bin' / 'coop-server'
        (bundled / 'sqldrivers').mkdir(parents=True)
        (bundled / 'shadnet.exe').write_bytes(b'new server')
        (bundled / 'sqldrivers' / 'qsqlite.dll').write_bytes(b'plugin')
        with mock.patch.object(coop, 'bundled_server', return_value=bundled):
            self.assertEqual(coop.registration_key(), 'hostkey')
            folder = coop.shadnet_dir()
            self.assertEqual(folder, coop.coop_dir() / 'shadnet-bbport')
            self.assertEqual((folder / 'shadnet.exe').read_bytes(), b'new server')
            self.assertTrue((folder / 'sqldrivers' / 'qsqlite.dll').is_file())
            # Its own config from then on; an update of the programs keeps it.
            (folder / 'shadnet.cfg').write_text('[General]\nRegistrationSecretKey=kept\n', encoding='utf-8')
            (bundled / 'shadnet.exe').write_bytes(b'newer server!')
            coop.shadnet_dir(sync=True)
            self.assertEqual((folder / 'shadnet.exe').read_bytes(), b'newer server!')
            self.assertEqual(coop.registration_key(), 'kept')

    def test_environment_points_this_launch_at_the_host(self):
        base = {'BB_ONLINE': '0', 'BB_SHADNET_NPID': 'normal', 'BB_GAME_DIR': 'game'}
        port = Path(self.folder.name) / 'bbport-windows'
        env = coop.co_op_environment(base, '100.64.0.10', 'hunter', 'secret', port / 'bin' / 'bb-probe.exe')
        self.assertEqual(env['BBSC_RELAY'], '100.64.0.10:20444')
        self.assertEqual(env['BB_COOP'], '1')
        # BBSC reads the redirects itself from <port>\user\host_overrides.json (the game starts there).
        self.assertEqual((port / 'user' / 'host_overrides.json').read_text(encoding='utf-8'),
                         Path(env['BB_HOST_OVERRIDES']).read_text(encoding='utf-8'))
        self.assertEqual(base['BB_SHADNET_NPID'], 'normal')  # the normal environment is untouched
        self.assertEqual(env['BB_SHADNET_SERVER'], '100.64.0.10:31313')
        self.assertEqual(env['BB_SHADNET_WEBAPI'], 'http://100.64.0.10:31315')
        self.assertEqual(env['BB_SHADNET_NPID'], 'hunter')
        self.assertTrue(env['BB_PROBE'].endswith('bbsc-launch.exe'))
        self.assertEqual(env['BB_GAME_DIR'], 'game')
        overrides = json.loads(Path(env['BB_HOST_OVERRIDES']).read_text(encoding='utf-8'))
        self.assertEqual(overrides['https://ss4.scej-network.jp:20443'], 'http://100.64.0.10:20443')
        self.assertEqual(overrides['https://thehuntersdream.com:18671/summon_messenger'],
                         'http://100.64.0.10:31315')
        self.assertNotIn('BBSC_SAVE_DIR', env)  # no saves yet: BBSC finds none either way

    def test_bbsc_is_told_where_the_saves_are(self):
        # BBSC gives its co-op kit (Hunt Bell, Kin Bell) only after backing up the save it finds.
        user = Path(self.folder.name) / 'saves'
        older = user / 'savedata' / '2' / 'CUSA00207' / 'SPRJ0005'
        newer = user / 'savedata' / '1' / 'CUSA00207' / 'SPRJ0005'
        for folder, when in ((older, 1000), (newer, 2000)):
            folder.mkdir(parents=True)
            (folder / 'userdata0000').write_bytes(b'save')
            os.utime(folder / 'userdata0000', (when, when))
        port = Path(self.folder.name) / 'bbport-windows'
        env = coop.co_op_environment({'BB_USER_DIR': str(user)}, '100.64.0.10', 'hunter', 'secret',
                                     port / 'bin' / 'bb-probe.exe')
        self.assertEqual(Path(env['BBSC_SAVE_DIR']), newer)
        # With the copy made before the session, BBSC backs that up instead: copying the save the
        # running game has open failed, and the kit was never given.
        copy = coop.backup_saves(user)
        env = coop.co_op_environment({'BB_USER_DIR': str(user)}, '100.64.0.10', 'hunter', 'secret',
                                     port / 'bin' / 'bb-probe.exe', save_copy=copy)
        self.assertEqual(Path(env['BBSC_SAVE_DIR']),
                         copy / 'savedata' / '1' / 'CUSA00207' / 'SPRJ0005')
        self.assertTrue((Path(env['BBSC_SAVE_DIR']) / 'userdata0000').is_file())

    def test_kit_bells_turn_back_into_vanilla_bells_outside_coop(self):
        def slot(n, goods, count=1):
            return (n.to_bytes(4, 'little') + (0xB0000000 | goods).to_bytes(4, 'little')
                    + (0x40000000 | goods).to_bytes(4, 'little') + count.to_bytes(4, 'little'))
        save = b'\0' * 8 + slot(0x40, 4016) + slot(0x41, 4121) + slot(0x42, 4313) + slot(0x43, 900, 20)
        user = Path(self.folder.name) / 'saves'
        folder = user / 'savedata' / '1' / 'CUSA00207' / 'SPRJ0005'
        folder.mkdir(parents=True)
        (folder / 'userdata0000').write_bytes(save)
        (folder / 'userdata0001').write_bytes(b'\0' * 64)
        backup = coop.restore_vanilla_bells(user)
        self.assertIsNotNone(backup)
        self.assertEqual((backup / 'savedata' / '1' / 'CUSA00207' / 'SPRJ0005' / 'userdata0000').read_bytes(), save)
        empty = (0x42).to_bytes(4, 'little') + bytes(4) + b'\xff\xff\xff\xff' + bytes(4)
        self.assertEqual((folder / 'userdata0000').read_bytes(),
                         b'\0' * 8 + slot(0x40, 200) + slot(0x41, 205) + empty + slot(0x43, 900, 20))
        # Nothing left to change: no second backup.
        self.assertIsNone(coop.restore_vanilla_bells(user))

    def test_unsafe_package_paths_are_refused(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('../outside.txt', 'x')
        with zipfile.ZipFile(data) as archive, self.assertRaises(coop.CoopError):
            coop._safe_extract(archive, Path(self.folder.name) / 'unpack')

    def _serve_zip(self, files):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            for name, text in files.items():
                archive.writestr(name, text)
        payload = data.getvalue()
        digest = coop.hashlib.sha256(payload).hexdigest()

        class Reply(io.BytesIO):
            headers = {'Content-Length': str(len(payload))}
            def __enter__(self): return self
            def __exit__(self, *args): return False
        return (mock.patch.object(coop, '_release_asset', return_value=('https://example.invalid', digest)),
                mock.patch.object(coop.urllib.request, 'urlopen', side_effect=lambda *a, **k: Reply(payload)))

    def test_the_client_package_leaves_bbscs_own_game_program_out(self):
        root = coop.PACKAGES['client'][2]
        asset, urlopen = self._serve_zip({
            f'{root}/bbsc/bbsc-launch.exe': 'x', f'{root}/bbsc/bbsc.dll': 'x',
            f'{root}/account/shadnet-sample.exe': 'x', f'{root}/tools/play-bbport.ps1': 'x',
            f'{root}/emulator/bb-probe.exe': 'old game program', f'{root}/source/README.txt': 'x'})
        with asset, urlopen:
            folder = coop.download('client')
        self.assertTrue(coop.installed('client'))
        self.assertTrue((folder / 'tools' / 'play-bbport.ps1').is_file())
        self.assertFalse((folder / 'emulator').exists())
        self.assertFalse((folder / 'source').exists())

    def test_connection_events_keep_only_relay_join_and_session_lines(self):
        logs = Path(self.folder.name) / 'logs'
        logs.mkdir()
        (logs / 'bbsc-timeline-20261030-150000-1.txt').write_text('old session\n', encoding='utf-8')
        newest = logs / 'bbsc-timeline-20261030-160000-2.txt'
        newest.write_text('\n'.join([
            'BBSC timeline - header',
            'time     kind     where | what',
            '16:32:51 RELAY    - | connected to 100.64.0.20:20444',
            '16:33:40 NET      solo | area list: messages',
            '16:33:51 JOIN     solo, Cathedral Ward | HTTP: host rang our sign',
            '16:33:56 SESSION  guest, Cathedral Ward | session state 4 -> 6',
            '16:34:00 BELL     guest | Kin Bell usable']) + '\n', encoding='utf-8')
        os.utime(newest, (2e9, 2e9))
        events = coop.connection_events(folder=logs)
        self.assertEqual([e.split()[1] for e in events], ['RELAY', 'JOIN', 'SESSION'])
        self.assertEqual(len(coop.connection_events(limit=1, folder=logs)), 1)
        self.assertEqual(coop.connection_events(folder=Path(self.folder.name) / 'none'), [])

    def test_connection_checks_for_a_guest_name_each_host_port(self):
        invite = coop.make_invite('100.64.0.20', 'key')
        with mock.patch.object(coop, 'installed', return_value=True),                 mock.patch.object(coop, 'setup_done', return_value=True),                 mock.patch.object(coop, 'host_address', return_value=('100.99.101.1', 'Tailscale')),                 mock.patch.object(coop, 'port_open', side_effect=lambda host, port, timeout=2.0: port != coop.RELAY_PORT):
            rows = coop.connection_checks(Path('bb-probe.exe'), 'join', invite)
        self.assertEqual([r[0] for r in rows][:4], ['BBSC ' + coop.VERSION, 'Firewall rule for this game',
                                                     'Your network', "Host's invite"])
        relay = [r for r in rows if str(coop.RELAY_PORT) in r[0]]
        self.assertEqual(len(relay), 1)
        self.assertFalse(relay[0][1])
        self.assertTrue(all(r[1] for r in rows if r not in relay))
        with mock.patch.object(coop, 'installed', return_value=True),                 mock.patch.object(coop, 'setup_done', return_value=False),                 mock.patch.object(coop, 'host_address', return_value=(None, None)):
            rows = coop.connection_checks(Path('bb-probe.exe'), 'join', 'not an invite')
        self.assertFalse(rows[1][1])
        self.assertFalse(rows[2][1])
        self.assertFalse(rows[3][1])  # the invite is damaged: no port checks after it

    def test_downloading_the_client_again_keeps_bbscs_logs_and_save_backups(self):
        root = coop.PACKAGES['client'][2]
        files = {f'{root}/bbsc/bbsc-launch.exe': 'x', f'{root}/bbsc/bbsc.dll': 'new',
                 f'{root}/account/shadnet-sample.exe': 'x'}
        asset, urlopen = self._serve_zip(files)
        with asset, urlopen:
            folder = coop.download('client')
        backup = folder / 'bbsc' / 'save-backups' / 'before-duel-bell-1' / 'userdata0000'
        backup.parent.mkdir(parents=True)
        backup.write_text('save', encoding='utf-8')
        (folder / 'bbsc' / 'logs').mkdir()
        (folder / 'bbsc' / 'logs' / 'bbsc-mod.log').write_text('log', encoding='utf-8')
        asset, urlopen = self._serve_zip(files)
        with asset, urlopen:
            folder = coop.download('client')
        self.assertEqual(backup.read_text(encoding='utf-8'), 'save')
        self.assertTrue((folder / 'bbsc' / 'logs' / 'bbsc-mod.log').is_file())
        self.assertEqual((folder / 'bbsc' / 'bbsc.dll').read_text(encoding='utf-8'), 'new')

    def test_a_new_server_version_keeps_the_hosts_data_from_the_earlier_one(self):
        earlier = coop.coop_dir() / coop.EARLIER_PACKAGES['server'][0] / 'server'
        (earlier / 'db').mkdir(parents=True)
        (earlier / 'db' / 'accounts.db').write_text('hunters', encoding='utf-8')
        (earlier / 'shadnet.cfg').write_text('RegistrationSecretKey=abc\n', encoding='utf-8')
        root = coop.PACKAGES['server'][2]
        asset, urlopen = self._serve_zip({
            f'{root}/server/shadnet.exe': 'x', f'{root}/server/BBSC-GameServer.exe': 'x',
            f'{root}/server/shadnet.cfg': 'RegistrationSecretKey=\n'})
        with asset, urlopen:
            folder = coop.download('server')
        self.assertEqual((folder / 'server' / 'shadnet.cfg').read_text(encoding='utf-8'),
                         'RegistrationSecretKey=abc\n')
        self.assertEqual((folder / 'server' / 'db' / 'accounts.db').read_text(encoding='utf-8'), 'hunters')
        self.assertTrue((earlier / 'shadnet.cfg').is_file())  # the earlier version stays as it was

    def test_firewall_rules_stay_on_tailscale_and_the_home_network(self):
        script = coop._firewall_script(r'C:\Games\bbport\bin\bb-probe.exe')
        self.assertIn("@('100.64.0.0/10','LocalSubnet')", script)
        self.assertNotIn('Any', script)
        self.assertEqual(script.count('New-NetFirewallRule'), len(coop.FIREWALL_PORTS) + 1)

    def test_firewall_script_quotes_an_apostrophe_in_the_path(self):
        script = coop._firewall_script(r"C:\Users\O'Neil\bbport\bin\bb-probe.exe")
        self.assertIn(r"-Program 'C:\Users\O''Neil\bbport\bin\bb-probe.exe'", script)

    def test_tailscale_addresses(self):
        self.assertTrue(coop.is_tailscale('100.64.0.10'))
        self.assertFalse(coop.is_tailscale('100.128.0.1'))
        self.assertFalse(coop.is_tailscale('192.168.1.5'))

    def test_tailscale_is_found_on_path_outside_program_files(self):
        # Ask which() for the full 'tailscale.exe', not bare 'tailscale': the bare
        # name is only ever resolved by appending a PATHEXT entry, so what comes back
        # is 'tailscale' + whatever extension matched; the full name makes the result
        # unambiguously the file handed to subprocess.run. Also check that exact file
        # is the one run.
        exe = r'D:\Apps\Tailscale\tailscale.exe'
        ran = mock.Mock(stdout='100.64.0.10\n')
        with mock.patch.object(coop.shutil, 'which', return_value=exe) as which, \
                mock.patch.object(coop.subprocess, 'run', return_value=ran) as run:
            self.assertEqual(coop.tailscale_ip(), '100.64.0.10')
        which.assert_called_once_with('tailscale.exe')
        self.assertEqual(run.call_args[0][0][0], str(Path(exe)))

    def test_tailscale_found_in_program_files_when_not_on_path(self):
        # Not on PATH, so which() misses; it must fall back to the install folder,
        # ProgramW6432 before ProgramFiles, and only when the file is there. Both
        # env vars point at our own temp dirs so the real C:\Program Files on the
        # test machine is never consulted. A distinct exe in each proves the order.
        with tempfile.TemporaryDirectory() as w6432, tempfile.TemporaryDirectory() as pf:
            exe_w6432 = Path(w6432) / 'Tailscale' / 'tailscale.exe'
            exe_pf = Path(pf) / 'Tailscale' / 'tailscale.exe'
            exe_w6432.parent.mkdir()
            exe_pf.parent.mkdir()
            exe_w6432.write_bytes(b'')
            exe_pf.write_bytes(b'')
            env = {'ProgramW6432': w6432, 'ProgramFiles': pf}
            with mock.patch.object(coop.shutil, 'which', return_value=None), \
                    mock.patch.dict(coop.os.environ, env, clear=False):
                # ProgramW6432 wins over ProgramFiles when both hold the exe.
                self.assertEqual(coop.tailscale_exe(), exe_w6432)
            # ProgramW6432 empty, ProgramFiles has it: fall through to ProgramFiles.
            exe_w6432.unlink()
            with mock.patch.object(coop.shutil, 'which', return_value=None), \
                    mock.patch.dict(coop.os.environ, env, clear=False):
                self.assertEqual(coop.tailscale_exe(), exe_pf)
            # Neither folder has it: no exe is reported.
            exe_pf.unlink()
            with mock.patch.object(coop.shutil, 'which', return_value=None), \
                    mock.patch.dict(coop.os.environ, env, clear=False):
                self.assertIsNone(coop.tailscale_exe())

    def test_tailscale_address_from_the_route_when_the_cli_is_missing(self):
        probe = mock.MagicMock()
        probe.__enter__.return_value.getsockname.return_value = ('100.64.0.10', 50000)
        with mock.patch.object(coop, 'tailscale_exe', return_value=None), \
                mock.patch.object(coop.socket, 'socket', return_value=probe):
            self.assertEqual(coop.tailscale_ip(), '100.64.0.10')
        probe.__enter__.return_value.getsockname.return_value = ('192.168.1.5', 50000)
        with mock.patch.object(coop, 'tailscale_exe', return_value=None), \
                mock.patch.object(coop.socket, 'socket', return_value=probe):
            self.assertIsNone(coop.tailscale_ip())

    def test_account_names_are_checked_before_asking_the_server(self):
        with self.assertRaises(coop.CoopError):
            coop.create_account('100.64.0.10', '', 'x', 'secret')
        with self.assertRaises(coop.CoopError):
            coop.create_account('100.64.0.10', '', 'hunter', 'abc')

    def account_server(self, *replies):
        """create_account against canned account tool outputs, in order."""
        tool = mock.patch.object(coop, '_account_tool', side_effect=list(replies))
        sleep = mock.patch.object(coop.time, 'sleep')
        self.addCleanup(tool.stop)
        self.addCleanup(sleep.stop)
        sleep.start()
        return tool.start()

    def test_account_created_after_the_server_finished_starting(self):
        refused = '[connect] 100.64.0.10:31313 ...\n[connect] FAILED: connection refused\n'
        tool = self.account_server(refused, '[connect] OK\n[login] FAILED: LoginInvalidPassword\n',
                                   '[connect] OK\n[create] Account created successfully.\n',
                                   '[connect] OK\n[login] OK userId=2\n')
        self.assertEqual(coop.create_account('100.64.0.10', 'key', 'hunter', 'secret'), 'created')
        self.assertEqual(tool.call_count, 4)

    def test_account_failures_say_why(self):
        failed_login = '[connect] OK\n[login] FAILED: LoginInvalidPassword\n'
        for reply, reason in (('[create] FAILED: Unauthorized', 'invite code does not match'),
                              ('[create] FAILED: CreationExistingUsername', 'already taken'),
                              ('[create] FAILED: InvalidInput', 'does not accept the name')):
            self.account_server(failed_login, f'[connect] OK\n{reply}\n')
            with self.assertRaisesRegex(coop.CoopError, reason):
                coop.create_account('100.64.0.10', 'key', 'hunter', 'secret')
        self.account_server('[connect] OK\n[login] FAILED: LoginAlreadyLoggedIn\n')
        with self.assertRaisesRegex(coop.CoopError, 'signed in on the host'):
            coop.create_account('100.64.0.10', 'key', 'hunter', 'secret')

    def test_public_server_account_failures_name_the_public_server(self):
        self.account_server('[connect] OK\n[login] FAILED: LoginInvalidPassword\n',
                            '[connect] OK\n[create] FAILED: CreationExistingUsername\n')
        with self.assertRaisesRegex(coop.CoopError, 'already taken on the BBSC public server'):
            coop.create_account('203.0.113.7', '', 'hunter', 'secret', public=True)
        self.account_server('[connect] FAILED\n', '[connect] FAILED\n')
        with mock.patch.object(coop, 'ACCOUNT_RETRY_WINDOW_S', 0), \
                self.assertRaisesRegex(coop.CoopError, 'No answer from the BBSC public server'):
            coop.create_account('203.0.113.7', '', 'hunter', 'secret', public=True)

    def _card(self, text):
        tools = coop.package_dir('client') / 'tools'
        tools.mkdir(parents=True, exist_ok=True)
        (tools / 'BBSC-card-SeamlessBloodborne.json').write_text(text, encoding='utf-8-sig')

    def test_the_public_server_comes_from_bbscs_card(self):
        self._card('{"name": "SeamlessBloodborne", "shadnet": "play.seamlesshunt.com:31313", '
                   '"registration_key": "", "network": "Typed"}')
        self.assertEqual(coop.public_server(), {'name': 'SeamlessBloodborne',
                                                'host': 'play.seamlesshunt.com', 'key': ''})

    def test_a_public_server_on_another_port_or_no_card_is_refused(self):
        with self.assertRaisesRegex(coop.CoopError, 'no server card'):
            coop.public_server()
        self._card('{"shadnet": "play.example.com:40000"}')
        with self.assertRaisesRegex(coop.CoopError, 'port 40000'):
            coop.public_server()

    def test_co_op_always_runs_at_the_default_frame_rate(self):
        base = {'BB_FPS': 'uncap', 'BB_FPS_LIMIT': '240', 'BB_VBLANK_HZ': '0'}
        probe = Path(self.folder.name) / 'bbport-windows' / 'bin' / 'bb-probe.exe'
        env = coop.co_op_environment(base, '203.0.113.7', 'hunter', 'secret', probe)
        self.assertEqual(env['BB_FPS'], '60')
        self.assertNotIn('BB_FPS_LIMIT', env)
        self.assertNotIn('BB_VBLANK_HZ', env)
        self.assertEqual(base['BB_FPS'], 'uncap')  # solo play keeps its own

    def test_co_op_can_run_at_a_fixed_120_but_never_unlocked(self):
        base = {'BB_FPS': 'uncap', 'BB_FPS_LIMIT': '240', 'BB_VBLANK_HZ': '0'}
        probe = Path(self.folder.name) / 'bbport-windows' / 'bin' / 'bb-probe.exe'
        env = coop.co_op_environment(base, '203.0.113.7', 'hunter', 'secret', probe, fps='120')
        self.assertEqual(env['BB_FPS'], '120')  # run.py sets vblank and the limit to 120 for it
        self.assertNotIn('BB_FPS_LIMIT', env)
        self.assertNotIn('BB_VBLANK_HZ', env)
        for choice in ('uncap', '144', '', None, 'nonsense'):
            self.assertEqual(coop.coop_fps(choice), '60', choice)
        self.assertEqual(coop.coop_fps('90'), '90')
        self.assertEqual(coop.coop_fps('120'), '120')
        env = coop.co_op_environment(base, '203.0.113.7', 'hunter', 'secret', probe, fps='uncap')
        self.assertEqual(env['BB_FPS'], '60')

    def test_the_public_firewall_rule_is_for_the_game_only(self):
        script = coop._public_firewall_script(r'C:\Games\bbport\bin\bb-probe.exe')
        self.assertEqual(script.count('New-NetFirewallRule'), 2)
        self.assertIn(r"-Program 'C:\Games\bbport\bin\bb-probe.exe'", script)
        self.assertNotIn('-LocalPort', script)  # no server ports open to the internet

    @unittest.skipUnless(os.name == 'nt', 'Windows process trees')
    def test_stopping_a_server_ends_its_child_too(self):
        # Like BBSC-GameServer.exe: a parent that starts a second copy of itself and waits.
        import subprocess
        import time
        pid_file = Path(self.folder.name) / 'child.pid'
        child = 'import time; time.sleep(60)'
        parent = (f"import subprocess, sys, pathlib; c = subprocess.Popen([sys.executable, '-c', {child!r}]); "
                  f"pathlib.Path({str(pid_file)!r}).write_text(str(c.pid)); c.wait()")
        process = subprocess.Popen([sys.executable, '-c', parent])
        for _ in range(100):
            if pid_file.exists() and pid_file.read_text():
                break
            time.sleep(0.05)
        child_pid = int(pid_file.read_text())
        coop.end_tree(process)
        self.assertIsNotNone(process.poll())
        alive = subprocess.run(['tasklist', '/FI', f'PID eq {child_pid}', '/NH'], capture_output=True,
                               text=True).stdout
        self.assertNotIn(str(child_pid), alive)


if __name__ == '__main__':
    unittest.main()
