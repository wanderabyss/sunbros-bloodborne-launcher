"""Seamless co-op (experimental): BBSC 0.0.2 by CLS_AMG, set up and run from the launcher.

BBSC (Bloodborne Seamless Co-op, https://github.com/CLSAMG22/BBSC, GPL-2.0-or-later) keeps a
co-op session alive through deaths, lamps, areas and bosses for up to five hunters. It needs a
server: the host's PC runs BBSC's two server programs (shadnet.exe, from Wozzardman's
shadnet-p2p, and BBSC-GameServer.exe) and the guests reach it over Tailscale (or the same home
network). The game runs with BBSC's DLL through bbsc-launch.exe, which BBSC's own BBport package
puts in BB_PROBE's place.

Nothing of BBSC is shipped with the port: its official release packages are downloaded on demand,
checked against the release's published SHA-256, and unpacked under %LOCALAPPDATA%\\bbport-coop.
Normal play and normal online are unchanged: co-op settings only reach the game started by
co_op_environment(), and run.py writes the server redirects for that one launch.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

REPO = 'CLSAMG22/BBSC'
RELEASES = f'https://github.com/{REPO}/releases'
DISCORD = 'https://discord.gg/Df7BCmfWdt'
# (release tag, asset, folder inside the zip): the BBport package of the newest release and the
# server package (0.0.2).
VERSION = '0.0.2'
# (release tag, asset, folder inside the zip): BBSC 0.0.2's BBport and server packages. Everyone
# in a session needs the same BBSC version.
PACKAGES = {
    'client': ('v0.0.2', 'BBSC-0.0.2-BBport.zip', 'BBSC-0.0.2-BBport'),
    'server': ('v0.0.2', 'BBSC-0.0.2-Server.zip', 'BBSC-0.0.2-Server'),
}
# Folders of earlier versions: an update takes the host's server data from the newest of them.
EARLIER_PACKAGES = {
    'client': ('BBSC-0.0.1-BBport',),
    'server': ('BBSC-0.0.1-Server',),
}
# Not unpacked from the client package: BBSC's own game program (emulator\, which bbsc-launch.exe
# would start instead of this port's) and the source of it (source\).
SKIPPED_PARTS = {'client': ('emulator', 'source')}
# What BBSC writes into its own folder and a new download of the client keeps (download).
CLIENT_KEEP = ('bbsc/logs', 'bbsc/save-backups', 'bbsc/captures')
SHADNET_PORT, MATCHING_PORT, WEBAPI_PORT, GAME_PORT, RELAY_PORT = 31313, 31314, 31315, 20443, 20444
INVITE_PREFIX = 'BBCOOP-'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
# Tailscale's own address on every tailnet: a route to it goes out through the Tailscale adapter.
TAILSCALE_DNS = '100.100.100.100'
# Inbound rules: the server ports, and the game itself (the host's game takes the guests'
# connections). Tailscale's range and this PC's own networks only - nothing opens to the internet.
FIREWALL_RANGES = ('100.64.0.0/10', 'LocalSubnet')
FIREWALL_PORTS = (('shadnet', 'TCP', SHADNET_PORT), ('matching', 'UDP', MATCHING_PORT),
                  ('webapi', 'TCP', WEBAPI_PORT), ('game server', 'TCP', GAME_PORT),
                  ('relay', 'TCP', RELAY_PORT), ('sessions', 'TCP', 18671), ('STUN', 'UDP', 3478))
RULE_PREFIX = 'Bloodborne co-op'


class CoopError(Exception):
    pass


def coop_dir():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'bbport-coop'


def package_dir(kind):
    return coop_dir() / PACKAGES[kind][2]


def installed(kind):
    folder = package_dir(kind)
    if kind == 'client':
        return all((folder / p).is_file() for p in ('bbsc/bbsc-launch.exe', 'bbsc/bbsc.dll',
                                                     'account/shadnet-sample.exe'))
    return all((folder / 'server' / p).is_file() for p in ('shadnet.exe', 'BBSC-GameServer.exe',
                                                            'shadnet.cfg'))


# --- Download -------------------------------------------------------------------------------------

def _release_asset(tag, name):
    request = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}',
                                     headers={'User-Agent': 'bbport-launcher',
                                              'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as reply:
        release = json.load(reply)
    for asset in release.get('assets', []):
        if asset.get('name') == name:
            digest = str(asset.get('digest') or '')
            if not digest.startswith('sha256:'):
                raise CoopError(f'{name}: the release publishes no SHA-256 to check it against.')
            return asset['browser_download_url'], digest.split(':', 1)[1].lower()
    raise CoopError(f'{name} is not in BBSC release {tag} any more ({RELEASES}).')


def _safe_extract(archive, destination, skip=()):
    """Unpacks the archive; `skip` names top-level folders inside the package folder to leave out."""
    root = destination.resolve()
    members = []
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if root != target and root not in target.parents:
            raise CoopError(f'Unsafe path in the package: {member.filename}')
        parts = member.filename.replace('\\', '/').split('/')
        if len(parts) > 1 and parts[1] in skip:
            continue
        members.append(member)
    archive.extractall(destination, members)


def download(kind, progress=None):
    """Downloads and unpacks one BBSC package; the server package keeps an existing database,
    registration key and logs, the client package BBSC's own logs, save backups and captures
    (CLIENT_KEEP)."""
    tag, name, folder = PACKAGES[kind]
    url, expected = _release_asset(tag, name)
    coop_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bbsc-', dir=coop_dir()) as temporary:
        zip_path = Path(temporary) / name
        digest = hashlib.sha256()
        request = urllib.request.Request(url, headers={'User-Agent': 'bbport-launcher'})
        with urllib.request.urlopen(request, timeout=60) as reply, open(zip_path, 'wb') as out:
            total = int(reply.headers.get('Content-Length') or 0)
            done = 0
            while chunk := reply.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(f'Downloading {name}: {done * 100 // total}%')
        if digest.hexdigest() != expected:
            raise CoopError(f'{name} does not match the checksum BBSC published; not installed.')
        staging = Path(temporary) / 'unpacked'
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract(archive, staging, SKIPPED_PARTS.get(kind, ()))
        new = staging / folder
        old = package_dir(kind)
        if kind == 'server':
            # The host's own data survives an update of the programs, also from an earlier
            # version's folder (which is left as it is).
            earlier = [old] + [coop_dir() / name for name in EARLIER_PACKAGES.get(kind, ())]
            source = next((f for f in earlier if _readable_dir(f / 'server')), None)
            for keep in ('server/shadnet.cfg', 'server/db', 'server/logs'):
                if source is None or not (source / keep).exists():
                    continue
                if source != old and keep == 'server/logs':
                    continue  # an earlier version's logs stay with it
                target = new / keep
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                if source == old:
                    shutil.move(str(old / keep), str(target))
                elif (source / keep).is_dir():
                    shutil.copytree(source / keep, target)
                else:
                    shutil.copy2(source / keep, target)
        if kind == 'client' and old.is_dir():
            # Downloading again (the Co-op page's button) replaced the folder whole and took
            # BBSC's save backups (before-duel-bell-...) and its logs with it (testing, 2026-10-30).
            for keep in CLIENT_KEEP:
                if (old / keep).is_dir():
                    target = new / keep
                    if target.exists():
                        shutil.rmtree(target)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old / keep), str(target))
        if old.exists():
            shutil.rmtree(old)
        shutil.move(str(new), str(old))
    return package_dir(kind)


def _readable_dir(folder):
    """True for a folder this user can list (an elevated program may have made one that is not)."""
    try:
        next(folder.iterdir(), None)
        return True
    except OSError:
        return False


# --- Network ---------------------------------------------------------------------------------------

def tailscale_exe():
    """tailscale.exe: on PATH (the installer adds it, wherever it was installed), else the default folder."""
    # Full name, not bare 'tailscale': what which() returns is then unambiguously the
    # file we hand to subprocess.run, not 'tailscale' + whichever PATHEXT entry matched.
    found = shutil.which('tailscale.exe')
    if found:
        return Path(found)
    for variable in ('ProgramW6432', 'ProgramFiles'):
        folder = os.environ.get(variable)
        if folder and (Path(folder) / 'Tailscale' / 'tailscale.exe').is_file():
            return Path(folder) / 'Tailscale' / 'tailscale.exe'
    return None


def tailscale_ip():
    return _tailscale_ip_from_cli() or _tailscale_ip_from_route()


def _tailscale_ip_from_cli():
    exe = tailscale_exe()
    if not exe:
        return None
    try:
        out = subprocess.run([str(exe), 'ip', '-4'], capture_output=True, text=True,
                             timeout=10, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.split():
        if is_tailscale(line):
            return line
    return None


def _tailscale_ip_from_route():
    """This PC's address on the Tailscale adapter, when the CLI can't be run (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect((TAILSCALE_DNS, 9))
            ip = probe.getsockname()[0]
        except OSError:
            return None
    return ip if is_tailscale(ip) else None


def is_tailscale(address):
    parts = address.split('.')
    return len(parts) == 4 and parts[0] == '100' and parts[1].isdigit() and 64 <= int(parts[1]) <= 127


def local_ip():
    """This PC's address on its home network (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(('192.0.2.1', 9))
            return probe.getsockname()[0]
        except OSError:
            return None


def host_address():
    """(address, network name): Tailscale when it is connected, else the home network."""
    ip = tailscale_ip()
    if ip:
        return ip, 'Tailscale'
    ip = local_ip()
    if ip:
        return ip, 'your home network only (Tailscale is not connected)'
    return None, None


# --- One-time setup (one administrator prompt) ---------------------------------------------------

def _quoted(text):
    """A PowerShell single-quoted string: a path with an apostrophe (C:\\Users\\O'Neil) broke the
    script, and the setup then never finished."""
    return "'" + str(text).replace("'", "''") + "'"


def _firewall_script(game_exe):
    ranges = ','.join(f"'{r}'" for r in FIREWALL_RANGES)
    lines = ['$ErrorActionPreference = "Continue"', f'$ranges = @({ranges})']
    for label, protocol, port in FIREWALL_PORTS:
        rule = f'{RULE_PREFIX} {label} {port}'
        lines.append(f"Remove-NetFirewallRule -DisplayName '{rule}' -ErrorAction SilentlyContinue")
        lines.append(f"New-NetFirewallRule -DisplayName '{rule}' -Direction Inbound -Protocol {protocol} "
                     f"-LocalPort {port} -RemoteAddress $ranges -Action Allow | Out-Null")
    rule = f'{RULE_PREFIX} game'
    lines.append(f"Remove-NetFirewallRule -DisplayName '{rule}' -ErrorAction SilentlyContinue")
    lines.append(f"New-NetFirewallRule -DisplayName '{rule}' -Direction Inbound -Program {_quoted(game_exe)} "
                 "-RemoteAddress $ranges -Action Allow | Out-Null")
    redist = package_dir('server') / 'server' / 'vc_redist.x64.exe'
    lines.append("$key = 'HKLM:\\SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64'")
    lines.append(f"if (-not ((Test-Path $key) -and (Get-ItemProperty $key).Installed -eq 1) -and "
                 f"(Test-Path {_quoted(redist)})) {{ Start-Process {_quoted(redist)} -ArgumentList '/install /quiet /norestart' -Wait }}")
    return '\r\n'.join(lines) + '\r\n'


def setup_done(game_exe):
    command = (f"$r = Get-NetFirewallRule -DisplayName '{RULE_PREFIX} game' -ErrorAction SilentlyContinue; "
               f"if ($r -and (($r | Get-NetFirewallApplicationFilter).Program -eq {_quoted(game_exe)})) {{ exit 0 }} else {{ exit 1 }}")
    try:
        return subprocess.run(['powershell', '-NoProfile', '-Command', command], timeout=30,
                              creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_setup(game_exe):
    """Firewall rules (Tailscale and home network only) and the C++ runtime the servers need.
    Windows asks the player once for administrator rights."""
    script = coop_dir() / 'setup-firewall.ps1'
    coop_dir().mkdir(parents=True, exist_ok=True)
    script.write_text(_firewall_script(game_exe), encoding='utf-8-sig')
    if not run_as_administrator('powershell.exe', f'-NoProfile -ExecutionPolicy Bypass -File "{script}"'):
        raise CoopError('Co-op needs a Yes on the Windows administrator prompt (firewall rules); '
                        'the answer was No. Try Start hosting again.')
    if not setup_done(game_exe):
        raise CoopError('The firewall rules were not made although Windows allowed the setup. '
                        'A firewall program other than Windows Defender Firewall may manage them; '
                        f'the setup script is {script}.')


def run_as_administrator(program, parameters, verb='runas'):
    """Runs program with administrator rights, hidden, and waits for it. False when the player
    said No. The launcher asks Windows itself: a prompt requested by a process in the background
    (it was a hidden PowerShell's Start-Process -Verb RunAs) opens only as a flashing taskbar
    button, and players saw no prompt at all (#49). Asked by the launcher, whose window is in
    front after the click, it opens over it."""
    import ctypes
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wintypes.HWND),
                    ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR),
                    ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                    ('dwHotKey', wintypes.DWORD), ('hIconOrMonitor', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]

    shell32 = ctypes.WinDLL('shell32', use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    window = user32.GetForegroundWindow()
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
    ctypes.windll.ole32.CoInitializeEx(None, 0x2 | 0x4)  # the shell wants COM on this thread
    info = ShellExecuteInfo(cbSize=ctypes.sizeof(ShellExecuteInfo),
                            fMask=0x40 | 0x100 | 0x400,  # NOCLOSEPROCESS, NOASYNC, FLAG_NO_UI (errors come back)
                            hwnd=window if owner.value == os.getpid() else None,
                            lpVerb=verb, lpFile=program, lpParameters=parameters, nShow=0)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:  # ERROR_CANCELLED: the player said No
            return False
        raise CoopError(f'Windows could not run the co-op setup: {ctypes.FormatError(error)}')
    if info.hProcess:
        kernel32.WaitForSingleObject(wintypes.HANDLE(info.hProcess), 0xFFFFFFFF)
        kernel32.CloseHandle(wintypes.HANDLE(info.hProcess))
    return True


# --- Hosting -----------------------------------------------------------------------------------------

# This port's build of the co-op shadNet server (packaging/windows/build_coop_server.sh):
# Wozzardman's shadnet-p2p with one patch, so clients on shadPS4 0.20's network code (this port
# since 1.9.5) get STUN replies; BBSC's own shadnet.exe drops their signaling packets. BBSC's game
# server is used as it is.
PORT_DIR = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parent.parent)


def bundled_server():
    for folder in (PORT_DIR / 'bin' / 'coop-server', PORT_DIR / 'out' / 'coop-server'):
        if (folder / 'shadnet.exe').is_file():
            return folder
    return None


def shadnet_dir(sync=False):
    """The folder shadnet.exe runs from. It keeps shadnet.cfg and its database beside itself, so
    this port's server runs from its own folder under bbport-coop, which updates leave alone.
    sync (only while the server is stopped): copy the bundled programs there, and BBSC's
    configuration (ports, seamless co-op, the host's registration key) the first time."""
    bundled = bundled_server()
    if bundled is None:
        return package_dir('server') / 'server'
    target = coop_dir() / 'shadnet-bbport'
    if sync:
        for source in bundled.rglob('*'):
            if not source.is_file():
                continue
            copy = target / source.relative_to(bundled)
            if (not copy.is_file() or copy.stat().st_size != source.stat().st_size
                    or copy.stat().st_mtime < source.stat().st_mtime):
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, copy)
        bbsc = package_dir('server') / 'server'
        for name in ('shadnet.cfg', 'worlds.cfg', 'scoreboards.cfg'):
            if not (target / name).exists() and (bbsc / name).is_file():
                shutil.copy2(bbsc / name, target / name)
    return target


def registration_key():
    """The host's own key (created on first use): only players who have it can make accounts."""
    cfg = shadnet_dir() / 'shadnet.cfg'
    if not cfg.is_file():
        cfg = shadnet_dir(sync=True) / 'shadnet.cfg'
    text = cfg.read_text(encoding='utf-8')
    for line in text.splitlines():
        if line.startswith('RegistrationSecretKey='):
            value = line.split('=', 1)[1].strip()
            if value:
                return value
            key = secrets.token_hex(20)
            cfg.write_text(text.replace(line, f'RegistrationSecretKey={key}'), encoding='utf-8')
            return key
    key = secrets.token_hex(20)
    cfg.write_text(text.rstrip('\n') + f'\nRegistrationSecretKey={key}\n', encoding='utf-8')
    return key


class Host:
    """The two server programs while this launcher hosts."""

    def __init__(self):
        self.processes = []
        self.address = None

    @property
    def running(self):
        return any(p.poll() is None for p in self.processes)

    def start(self, address):
        self.stop()
        server = package_dir('server') / 'server'
        shadnet = shadnet_dir()
        # Servers left over from a launcher that closed without stopping them hold the ports.
        end_leftovers(server)
        if shadnet != server:
            end_leftovers(shadnet)
        shadnet = shadnet_dir(sync=True)
        logs = server / 'logs'
        logs.mkdir(exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        env = dict(os.environ, SHADNET_BLOODBORNE_SEAMLESS_COOP='1')
        shadnet_log = open(logs / f'shadnet-{stamp}.log', 'w', encoding='utf-8', errors='replace')
        self.processes.append(subprocess.Popen([str(shadnet / 'shadnet.exe')], cwd=shadnet, env=env,
                                               stdout=shadnet_log, stderr=subprocess.STDOUT,
                                               stdin=subprocess.DEVNULL, creationflags=NO_WINDOW))
        time.sleep(2)
        game_log = open(logs / f'gameserver-{stamp}.log', 'w', encoding='utf-8', errors='replace')
        self.processes.append(subprocess.Popen(
            [str(server / 'BBSC-GameServer.exe'), '--shadnet', address, '--host', '0.0.0.0',
             '--advertise', address, '--summon-interval', '5', '--no-playlog', '--log-dir', str(logs)],
            cwd=server, stdout=game_log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW))
        time.sleep(1)
        if not self.running or any(p.poll() is not None for p in self.processes):
            self.stop()
            raise CoopError(f'A co-op server stopped at start; see {logs}.')
        self.address = address

    def stop(self):
        for process in self.processes:
            if process.poll() is None:
                end_tree(process)
        self.processes = []
        self.address = None


def end_tree(process):
    """BBSC-GameServer.exe runs a second copy of itself as a child: end the whole tree, or the
    child keeps the ports after Stop hosting."""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                       creationflags=NO_WINDOW)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def end_leftovers(server):
    """Ends shadnet.exe and BBSC-GameServer.exe processes started from this server folder."""
    if os.name != 'nt':
        return
    folder = str(Path(server).resolve()).replace("'", "''")
    script = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -and "
              f"$_.ExecutablePath.StartsWith('{folder}\\', 'OrdinalIgnoreCase') }} | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                   capture_output=True, creationflags=NO_WINDOW)


# --- Invites and accounts ------------------------------------------------------------------------

def make_invite(address, key):
    data = json.dumps({'a': address, 'k': key}, separators=(',', ':')).encode()
    return INVITE_PREFIX + base64.urlsafe_b64encode(data).decode().rstrip('=')


def read_invite(code):
    # Chat apps wrap long codes over lines and add spaces: none belong to the code.
    code = ''.join(code.split())
    if not code.startswith(INVITE_PREFIX):
        raise CoopError(f'An invite code starts with {INVITE_PREFIX}')
    body = code[len(INVITE_PREFIX):]
    try:
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        address, key = str(data['a']), str(data.get('k', ''))
    except (ValueError, KeyError, TypeError):
        raise CoopError('That invite code is damaged; ask the host to copy it again.') from None
    return address, key


def _account_tool(address, *arguments, public=False):
    tool = package_dir('client') / 'account' / 'shadnet-sample.exe'
    if not tool.is_file():
        raise CoopError('Set up co-op first (the BBSC package is missing).')
    try:
        result = subprocess.run([str(tool), address, str(SHADNET_PORT), *arguments], capture_output=True,
                                text=True, timeout=30, cwd=tool.parent, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        if public:
            raise CoopError(f'No answer from the BBSC public server ({address}). Check your internet '
                            'connection, or try again later.') from None
        raise CoopError(f'No answer from the co-op server at {address}. Is the host hosting, '
                        'and are you both on Tailscale?') from None
    return (result.stdout or '') + (result.stderr or '')


def create_account(address, key, name, password, public=False):
    """Creates the account on the host's server (public: the BBSC public server), then checks it
    signs in. An existing account (the same name and password) only gets the check."""
    if not (3 <= len(name) <= 16 and all(c.isalnum() or c in '-_' for c in name)):
        raise CoopError('A co-op name is 3-16 letters, numbers, - or _.')
    if len(password) < 4:
        raise CoopError('Choose a password of at least 4 characters (one you use nowhere else).')
    out = _account_reply(address, 'login', name, password, public=public)
    if '[login] OK' in out:
        return 'signed in'
    # The server answers LoginInvalidPassword for an unknown name too: only creating it tells.
    if _account_error(out) == 'LoginAlreadyLoggedIn':
        raise _account_failure(address, name, out, public)
    arguments = ['register', name, password, f'{name}@bbport-coop.invalid']
    if key:
        arguments.append(key)
    out = _account_reply(address, *arguments, public=public)
    if 'Account created successfully' not in out:
        raise _account_failure(address, name, out, public)
    out = _account_reply(address, 'login', name, password, public=public)
    if '[login] OK' not in out:
        raise _account_failure(address, name, out, public)
    return 'created'


# Connection attempts to the account server: the host's own server may still be starting
# (Start hosting asks it right after starting it), which used to read as a taken name (#28).
ACCOUNT_RETRY_WINDOW_S, ACCOUNT_RETRY_S = 10, 2


def _account_reply(address, *arguments, public=False):
    """The account tool's output, asked again for a few seconds while the server refuses the
    connection."""
    deadline = time.monotonic() + ACCOUNT_RETRY_WINDOW_S
    while True:
        out = _account_tool(address, *arguments, public=public)
        if _account_error(out) != 'connect' or time.monotonic() + ACCOUNT_RETRY_S > deadline:
            return out
        time.sleep(ACCOUNT_RETRY_S)


def _account_error(out):
    """What failed in the account tool's output: 'connect', 'timeout', the server's error name
    (Unauthorized, CreationExistingUsername, ...) or ''."""
    if '[connect] FAILED' in out:
        return 'connect'
    for line in out.splitlines():
        if line.startswith(('[login] FAILED:', '[create] FAILED:')):
            return line.split(':', 1)[1].strip()
    return 'timeout' if '[timeout]' in out else ''


def _account_failure(address, name, out, public=False):
    """The co-op account error for the player, from the account tool's output. All of these
    used to say "the name may be taken, or the invite is from another host" (#28)."""
    error = _account_error(out)
    if public:
        return _public_account_failure(address, name, error, out)
    if error in ('connect', 'timeout'):
        return CoopError(f'No answer from the co-op server at {address}. The host must be hosting '
                         '(launcher open), and both of you on Tailscale or the same network.')
    if error == 'Unauthorized':
        return CoopError("The invite code does not match the host's server: it is from an older "
                         'session or another host. Ask the host to copy the invite code again.')
    if error == 'LoginAlreadyLoggedIn':
        return CoopError(f'{name} is signed in on the host\'s server right now. Every player needs '
                         'their own co-op name; if it is yours, close the game that uses it first.')
    if error in ('CreationExistingUsername', 'CreationExistingEmail', 'LoginInvalidPassword'):
        return CoopError(f'{name} is already taken on the host\'s server, with another password. Use '
                         'the password you chose with this name before, or another co-op name.')
    if error == 'InvalidInput':
        return CoopError(f"The host's server does not accept the name {name}; choose another.")
    detail = error or (out.strip().splitlines() or ['no answer'])[-1]
    return CoopError(f"The host's server did not create the account ({detail}).")


def _public_account_failure(address, name, error, out):
    if error in ('connect', 'timeout'):
        return CoopError(f'No answer from the BBSC public server ({address}). Check your internet '
                         'connection, or try again later.')
    if error == 'LoginAlreadyLoggedIn':
        return CoopError(f'{name} is signed in on the BBSC public server right now. Close the game '
                         'that uses it first, or choose another co-op name.')
    if error in ('CreationExistingUsername', 'CreationExistingEmail', 'LoginInvalidPassword'):
        return CoopError(f'{name} is already taken on the BBSC public server, with another password. '
                         'Use the password of that account, or another co-op name.')
    if error == 'InvalidInput':
        return CoopError(f'The BBSC public server does not accept the name {name}; choose another.')
    detail = error or (out.strip().splitlines() or ['no answer'])[-1]
    return CoopError(f'The BBSC public server did not create the account ({detail}).')


# --- The BBSC public server --------------------------------------------------------------------

def public_server():
    """The BBSC public server from the server card in BBSC's package (tools\\BBSC-card-*.json):
    {'name', 'host', 'key'}. Its shadNet, game server and relay use the same ports as a host's."""
    client = package_dir('client')
    for card in sorted((client / 'tools').glob('BBSC-card-*.json')):
        try:
            data = json.loads(card.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        host, _, port = str(data.get('shadnet') or '').strip().partition(':')
        if not host:
            continue
        if port and port != str(SHADNET_PORT):
            raise CoopError(f'The BBSC public server uses port {port}, which this launcher does not '
                            f'support (it uses {SHADNET_PORT}).')
        return {'name': str(data.get('name') or host), 'host': host,
                'key': str(data.get('registration_key') or '')}
    raise CoopError('BBSC\'s package has no server card for the public server. Press Set up co-op '
                    'to download it again.')


def resolve_ipv4(host):
    """The server's IPv4 address: BBSC's account tool takes an address only, and the game's
    server settings get the same one."""
    try:
        ip = socket.getaddrinfo(host, SHADNET_PORT, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        if ip == '149.248.211.216' and host == 'play.seamlesshunt.com':
            return '199.195.193.131'
        return ip
    except (OSError, IndexError):
        if host == 'play.seamlesshunt.com':
            return '199.195.193.131'
        raise CoopError(f'Cannot find the BBSC public server {host}. Check your internet connection.') from None


# Players on the public server reach this PC's game straight over the internet (BBSC's own
# ALLOW-GAME.cmd allows the game the same way). Made only when the public server is chosen.
PUBLIC_RULE = f'{RULE_PREFIX} game (public server)'


def _public_firewall_script(game_exe):
    lines = ['$ErrorActionPreference = "Continue"']
    for protocol in ('UDP', 'TCP'):
        rule = f'{PUBLIC_RULE} {protocol}'
        lines.append(f"Remove-NetFirewallRule -DisplayName '{rule}' -ErrorAction SilentlyContinue")
        lines.append(f"New-NetFirewallRule -DisplayName '{rule}' -Direction Inbound -Program {_quoted(game_exe)} "
                     f"-Protocol {protocol} -RemoteAddress Any -Profile Any -Action Allow | Out-Null")
    return '\r\n'.join(lines) + '\r\n'


def public_setup_done(game_exe):
    command = (f"$r = Get-NetFirewallRule -DisplayName '{PUBLIC_RULE} UDP' -ErrorAction SilentlyContinue; "
               f"if ($r -and (($r | Get-NetFirewallApplicationFilter).Program -eq {_quoted(game_exe)})) {{ exit 0 }} else {{ exit 1 }}")
    try:
        return subprocess.run(['powershell', '-NoProfile', '-Command', command], timeout=30,
                              creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_public_setup(game_exe):
    """The firewall rule for public-server co-op; Windows asks once for administrator rights."""
    script = coop_dir() / 'setup-firewall-public.ps1'
    coop_dir().mkdir(parents=True, exist_ok=True)
    script.write_text(_public_firewall_script(game_exe), encoding='utf-8-sig')
    if not run_as_administrator('powershell.exe', f'-NoProfile -ExecutionPolicy Bypass -File "{script}"'):
        raise CoopError('Co-op on the public server needs a Yes on the Windows administrator prompt '
                        '(it lets other players connect to your game); the answer was No.')
    if not public_setup_done(game_exe):
        raise CoopError('The firewall rule was not made although Windows allowed the setup. '
                        'A firewall program other than Windows Defender Firewall may manage it; '
                        f'the setup script is {script}.')


# --- The game ------------------------------------------------------------------------------------

# --- Connection view (the Co-op page's "Connection details") ------------------------------------

# The host's ports a guest needs, by what they carry (TCP; the matching port is UDP and has no
# connect test).
GUEST_PORTS = (('Account server', SHADNET_PORT), ('Web API (summon signs)', WEBAPI_PORT),
               ('Game server', GAME_PORT), ('Relay (warps, world sync)', RELAY_PORT))
# BBSC timeline kinds about the connection: the relay, signs and joins, session state.
EVENT_KINDS = ('RELAY', 'JOIN', 'SESSION')


def port_open(address, port, timeout=2.0):
    try:
        with socket.create_connection((address, port), timeout=timeout):
            return True
    except OSError:
        return False


def ports_open(address, ports):
    """port_open for each port at once: an offline host costs one timeout, not one per port."""
    if not address:
        return [False] * len(ports)
    with ThreadPoolExecutor(max_workers=len(ports) or 1) as pool:
        return list(pool.map(lambda port: port_open(address, port), ports))


def connection_checks(game_exe, role, invite='', hosting=False, public=False):
    """[(label, ok, detail)] for the Co-op page: BBSC, the firewall rule, the network and, for a
    guest, each of the host's ports. Runs network checks: call it off the UI thread."""
    checks = []
    kinds = ('client',) if public else ('client', 'server')
    have = all(installed(kind) for kind in kinds)
    checks.append(('BBSC ' + VERSION, have, 'installed' if have else 'not downloaded yet'))
    if public:
        ok = public_setup_done(game_exe)
        checks.append(('Firewall rule for this game', ok, 'set' if ok else 'missing: press Open ports'))
        try:
            server = public_server()
            host = resolve_ipv4(server['host'])
        except (CoopError, OSError) as error:
            checks.append(('Public server', False, str(error) or 'not found'))
            return checks
        checks.append(('Public server', bool(host), f"{server['name']} ({host})" if host else 'name not resolved'))
        for (label, port), ok in zip(GUEST_PORTS, ports_open(host, [port for _, port in GUEST_PORTS])):
            checks.append((f'{label}, port {port}', ok, 'open' if ok else 'no answer'))
        return checks
    ok = setup_done(game_exe)
    checks.append(('Firewall rule for this game', ok, 'set' if ok else 'missing: press Open ports'))
    address, network = host_address()
    checks.append(('Your network', bool(address), f'{address} ({network})' if address else 'no network found: connect Tailscale'))
    if role == 'host':
        checks.append(('Your co-op servers', hosting, 'running' if hosting else 'not started: Start hosting'))
        return checks
    try:
        host, _key = read_invite(invite)
    except CoopError as error:
        checks.append(("Host's invite", False, str(error)))
        return checks
    checks.append(("Host's invite", True, host))
    for (label, port), ok in zip(GUEST_PORTS, ports_open(host, [port for _, port in GUEST_PORTS])):
        checks.append((f'{label}, port {port}', ok, 'open' if ok else 'no answer: is the host hosting, and on Tailscale?'))
    return checks


def connection_events(limit=14, folder=None):
    """The newest BBSC session's connection lines (EVENT_KINDS), oldest first, at most `limit`."""
    logs = Path(folder) if folder else package_dir('client') / 'bbsc' / 'logs'
    try:
        newest = max(logs.glob('bbsc-timeline-*.txt'), key=lambda f: f.stat().st_mtime)
        lines = newest.read_text(encoding='utf-8', errors='replace').splitlines()
    except (OSError, ValueError):
        return []
    picked = []
    for line in lines:
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] in EVENT_KINDS:
            picked.append(f'{parts[0]}  {parts[1]:<8} {parts[2]}')
    return picked[-limit:]


def coop_fps(choice):
    """BBSC 0.0.2 co-op frame rate: fixed at 60 (tested default), 90 or 120 FPS. Never unlocked."""
    if choice in ('120', '90'):
        return str(choice)
    return '60'


def co_op_environment(env, address, name, password, probe, save_copy=None, vblank=None, fps=None):
    """The normal game environment, pointed at the host's servers with BBSC loaded. run.py writes
    this launch's server redirects (user/host_overrides.json) from these values. Co-op respects
    your FPS setting (vblank); use None for default 60 FPS."""
    launcher = package_dir('client') / 'bbsc' / 'bbsc-launch.exe'
    # BBSC's own redirect (its play-bbport.ps1): the game server and the summon messenger the
    # BBSC game server's server info names, both on the host.
    overrides = coop_dir() / 'host_overrides.json'
    overrides.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({
        'https://ss4.scej-network.jp:20443': f'http://{address}:{GAME_PORT}',
        'http://thehuntersdream.com:18671/summon_messenger': f'http://{address}:{WEBAPI_PORT}',
        'https://thehuntersdream.com:18671/summon_messenger': f'http://{address}:{WEBAPI_PORT}',
    }, indent=2) + '\n'
    overrides.write_text(text, encoding='utf-8')
    # BBSC reads the same file itself, but only from <folder the game starts in>\user (run.py
    # starts it in the port's folder), its exe's folder\user or %APPDATA%\shadPS4. Every normal
    # online launch rewrites the port's user\host_overrides.json, so this copy serves this
    # co-op launch only.
    port_user = Path(probe).resolve().parent.parent / 'user'
    port_user.mkdir(parents=True, exist_ok=True)
    (port_user / 'host_overrides.json').write_text(text, encoding='utf-8')
    env = dict(env)
    # Co-op runs on the shadNet backend against the host's servers, never The Hunter's Dream's,
    # whatever pool the main online settings choose (run.py drops these again for BB_COOP=1).
    for key in ('BB_NET_BACKEND', 'BB_THD_TOKEN', 'BB_THD_ONLINE_ID', 'BB_THD_SERVER', 'BB_THD_AUTH',
                'BB_THD_RULESET', 'BB_FPS_LIMIT', 'BB_VBLANK_HZ'):
        env.pop(key, None)
    # BBSC's co-op kit (its Hunt Bell, Kin Bell and the rest, which replace the vanilla bells) is
    # only given after BBSC has copied the save folder BBSC_SAVE_DIR names (BBSC's
    # BackupBbscSaves; it finds saves only in shadPS4's layout otherwise). Copying the save the
    # running game has open failed every time, so the kit never came and a new character had no
    # bell to start co-op with. BBSC gets the copy this launcher made just before the session
    # (`save_copy`, backup_saves), which nothing has open; the bells still go into the live save.
    save_dir = (active_save_dir(save_copy) if save_copy else None) or \
        active_save_dir(Path(env.get('BB_USER_DIR') or port_user))
    if save_dir:
        env['BBSC_SAVE_DIR'] = str(save_dir)
    env.update({
        'BBSC_RELAY': f'{address}:{RELAY_PORT}',  # BBSC's relay (warps, world sync) on the host
        'BB_PROBE': str(launcher),
        'BBSC_EMULATOR': str(probe),
        'BB_ONLINE': '1',
        'BB_SHADNET_SERVER': f'{address}:{SHADNET_PORT}',
        'BB_SHADNET_WEBAPI': f'http://{address}:{WEBAPI_PORT}',
        'BB_HOST_OVERRIDES': str(overrides),
        'BB_SHADNET_NPID': name,
        'BB_SHADNET_PASSWORD': password,
        'BB_USER_NAME': name,
        'BB_COOP': '1',
        'BB_FPS': coop_fps(fps),
    })
    if vblank is not None:
        env['BB_VBLANK_HZ'] = str(vblank)
    return env


def active_save_dir(user_dir):
    """The game's save folder (SPRJ0005, userdata0000...) written most recently, or None."""
    newest = None
    for folder in Path(user_dir).glob('savedata/*/CUSA00207/SPRJ0005'):
        times = [f.stat().st_mtime for f in folder.glob('userdata00*') if f.is_file()]
        if times and (newest is None or max(times) > newest[0]):
            newest = (max(times), folder)
    return newest[1] if newest else None


def backup_saves(user_dir):
    """A copy of the saves before every co-op session (BBSC 0.0.1 is a first test)."""
    saves = Path(user_dir) / 'savedata'
    if not saves.is_dir():
        return None
    target = Path(user_dir) / 'coop-backups' / time.strftime('%Y%m%d-%H%M%S') / 'savedata'
    shutil.copytree(saves, target)
    return target.parent


# BBSC's co-op kit (bloodborne_re.cpp BbscKit) is goods rows that only BBSC fills in, and BBSC
# takes the vanilla bells it replaces out of the inventory. Outside co-op nothing fills those rows:
# the kit shows as "?GoodsName?" with a blank icon and there is no Beckoning Bell (reported
# 2026-10-30). Before an offline or online launch the kit goes back to the vanilla bells; the next
# co-op launch, BBSC swaps them for its kit again (it gives the kit whenever it is missing).
KIT_TO_VANILLA = {4016: 200, 4121: 205, 11201: 225, 11251: 111, 4313: None}  # Duel Bell: no vanilla bell
_GOODS_HANDLE, _GOODS_ID = 0xB0000000, 0x40000000


def _kit_entries(data, goods):
    """Offsets of the inventory slots holding `goods`: [slot][handle][item id][count], 4 bytes each."""
    key = (_GOODS_HANDLE | goods).to_bytes(4, 'little') + (_GOODS_ID | goods).to_bytes(4, 'little')
    found, at = [], data.find(key)
    while at != -1:
        if at >= 4 and at % 4 == 0:
            found.append(at - 4)
        at = data.find(key, at + 1)
    return found


def vanilla_bells_in(data):
    """`data` (one save file) with the kit back as vanilla bells; the Duel Bell's slot is emptied,
    as is a kit slot whose vanilla bell is already there. Returns (new data, changed slots)."""
    data, changed = bytearray(data), 0
    for kit, vanilla in KIT_TO_VANILLA.items():
        for slot in _kit_entries(data, kit):
            if vanilla is None or _kit_entries(data, vanilla):
                # An empty slot as the game writes it: slot id kept, no handle, item -1, count 0.
                data[slot + 4:slot + 16] = bytes(4) + b'\xff\xff\xff\xff' + bytes(4)
            else:
                data[slot + 4:slot + 8] = (_GOODS_HANDLE | vanilla).to_bytes(4, 'little')
                data[slot + 8:slot + 12] = (_GOODS_ID | vanilla).to_bytes(4, 'little')
            changed += 1
    return bytes(data), changed


def restore_vanilla_bells(user_dir):
    """Every save in `user_dir` with BBSC's kit back as vanilla bells, for a launch without BBSC.
    The saves are copied to coop-backups first. Returns the backup folder, or None if no save
    held the kit."""
    files = [f for f in Path(user_dir).glob('savedata/*/CUSA00207/SPRJ0005/*')
             if f.is_file() and f.name[:-4] in ('userdata', 'backup')]
    updates = {}
    for f in files:
        data = f.read_bytes()
        new, changed = vanilla_bells_in(data)
        if changed:
            updates[f] = new
    if not updates:
        return None
    backup = backup_saves(user_dir)
    for f, new in updates.items():
        f.write_bytes(new)
    return backup
