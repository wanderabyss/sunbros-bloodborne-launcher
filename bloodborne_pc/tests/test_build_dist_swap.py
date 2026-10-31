import importlib.util
from pathlib import Path
import zipfile
from unittest import mock
import pytest

spec = importlib.util.spec_from_file_location('build_dist_swap', Path(__file__).parents[2]/'scripts/build_dist.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def package(tmp_path, prefix='app'):
    archive = tmp_path/'app.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(prefix+'/Bloodborne.exe', b'new')
        z.writestr(prefix+'/_internal/shiboken6/Shiboken.pyd', b'complete')
    target = tmp_path/'app'
    target.mkdir()
    (target/'Bloodborne.exe').write_bytes(b'old')
    (target/'bbport.ini').write_text('saved=1')
    (target/'mods').mkdir()
    (target/'mods/custom.txt').write_text('user mod')
    return archive, target


def test_old_package_remains_complete_until_replacement_ready(tmp_path):
    archive, target = package(tmp_path)
    def before_swap(folder):
        assert (folder/'Bloodborne.exe').read_bytes() == b'old'
        assert list(tmp_path.glob('.bbport-unpack-*/app/_internal/shiboken6/Shiboken.pyd'))
    with mock.patch.object(build, 'kill_processes_in_directory', side_effect=before_swap):
        build.unzip_archive(archive, target)
    assert (target/'Bloodborne.exe').read_bytes() == b'new'
    assert (target/'_internal/shiboken6/Shiboken.pyd').read_bytes() == b'complete'
    assert (target/'bbport.ini').read_text() == 'saved=1'
    assert (target/'mods/custom.txt').read_text() == 'user mod'


def test_failed_swap_restores_previous_package(tmp_path):
    archive, target = package(tmp_path)
    rename = Path.rename
    def fail_new(source, destination):
        if source.name == 'app' and source.parent.name.startswith('.bbport-unpack-'):
            raise OSError('simulated swap failure')
        return rename(source, destination)
    with mock.patch.object(build, 'kill_processes_in_directory'), mock.patch.object(Path, 'rename', fail_new):
        with pytest.raises(OSError):
            build.unzip_archive(archive, target)
    assert (target/'Bloodborne.exe').read_bytes() == b'old'
    assert (target/'bbport.ini').read_text() == 'saved=1'


def test_wrong_archive_root_does_not_change_existing_package(tmp_path):
    archive, target = package(tmp_path, 'other')
    with pytest.raises(ValueError):
        build.unzip_archive(archive, target)
    assert (target/'Bloodborne.exe').read_bytes() == b'old'
