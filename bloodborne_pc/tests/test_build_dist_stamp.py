import importlib.util
from pathlib import Path
import subprocess

spec = importlib.util.spec_from_file_location('build_dist_stamp', Path(__file__).parents[2]/'scripts/build_dist.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def checkout(tmp_path):
    root = tmp_path/'repo'
    port = root/'bloodborne_pc'
    for path in build.BUILD_INPUTS:
        target = port/path
        if '.' in target.name:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('#!/bin/sh\n')
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target/'keep.c').write_text('int x;\n')
    (port/'launcher').mkdir()
    (port/'launcher/ui.py').write_text('print(1)\n')
    def git(*command):
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@t', *command],
                       check=True, capture_output=True)
    git('init', '-q')
    git('add', '.')
    git('commit', '-qm', 'base')
    return port, git


def test_stamp_follows_engine_sources_only(tmp_path):
    port, git = checkout(tmp_path)
    base = build.build_inputs_stamp(port)
    assert base

    (port/'launcher/ui.py').write_text('print(2)\n')
    assert build.build_inputs_stamp(port) == base, 'a launcher edit needs no engine rebuild'

    (port/'src/keep.c').write_text('int y;\n')
    edited = build.build_inputs_stamp(port)
    assert edited != base, 'an uncommitted engine edit'

    git('commit', '-qam', 'edit')
    assert build.build_inputs_stamp(port).split()[1] == edited.split()[1], 'same sources, now committed'

    (port/'gpu/new.cpp').write_text('int z;\n')
    assert build.build_inputs_stamp(port) != edited, 'an untracked engine file'


def test_a_commit_without_engine_changes_does_not_rebuild(tmp_path):
    port, git = checkout(tmp_path)
    built = build.build_inputs_stamp(port)
    (port/'launcher/ui.py').write_text('print(3)\n')
    git('commit', '-qam', 'launcher only')
    now = build.build_inputs_stamp(port)
    assert now != built, 'the commit label moved'
    assert build.stamps_match(built, now)
    assert not build.stamps_match(None, now)
    assert not build.stamps_match('abc1234 0000000000000000', now)


def test_no_stamp_outside_git(tmp_path):
    assert build.build_inputs_stamp(tmp_path) is None
