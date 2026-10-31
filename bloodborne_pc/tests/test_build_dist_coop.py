import importlib.util
from pathlib import Path
import subprocess

spec = importlib.util.spec_from_file_location('build_dist_coop', Path(__file__).parents[2]/'scripts/build_dist.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

PACKAGE_SH = Path(__file__).parents[1]/'packaging/windows/package.sh'


def test_stage_without_coop_server_is_refused(tmp_path):
    # 4.2.5 shipped without bin/coop-server: hosts ran BBSC's shadnet.exe and guests never joined.
    assert build.coop_server_missing(tmp_path, env={})

    server = tmp_path/'bin'/build.COOP_SERVER
    server.parent.mkdir(parents=True)
    server.write_bytes(b'MZ')
    assert not build.coop_server_missing(tmp_path, env={})


def test_package_without_coop_server_needs_opt_out(tmp_path):
    assert not build.coop_server_missing(tmp_path, env={build.NO_COOP_SERVER: '1'})
    assert build.coop_server_missing(tmp_path, env={build.NO_COOP_SERVER: '0'})


def test_package_sh_stops_without_coop_server():
    text = PACKAGE_SH.read_text(encoding='utf-8')
    block = text[text.index('if [[ -f out/coop-server/shadnet.exe ]]'):]
    block = block[:block.index('\nfi\n') + 4]
    assert 'BB_PACKAGE_NO_COOP_SERVER' in block and 'exit 1' in block
    assert subprocess.run(['bash', '-n', str(PACKAGE_SH)], capture_output=True).returncode == 0
