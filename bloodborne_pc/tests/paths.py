"""Repository paths for the Python tests (run: python3 -m unittest discover -s tests)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))


def real_bash():
    """A Bash that runs scripts here, or None. On Windows `bash` on PATH is usually the WSL stub
    (WindowsApps or System32): it hands the script to Linux without the test's environment."""
    if os.name != 'nt':
        return shutil.which('bash')
    candidates = [shutil.which('bash'), r'C:\msys64\usr\bin\bash.exe', r'C:\Program Files\Git\bin\bash.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            parts = {part.lower() for part in Path(candidate).parts}
            if not parts & {'windowsapps', 'system32'}:
                return candidate
    return None


def with_bash_first(env):
    """env with real_bash()'s folder first on PATH: run.sh's tools, and the `bash` a re-exec finds."""
    return {**env, 'PATH': str(Path(real_bash()).parent) + os.pathsep + env.get('PATH', '')}
