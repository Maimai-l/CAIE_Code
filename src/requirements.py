import importlib
import sys

# (pip package name, import name)
requirements = [
    ('ply', 'ply'),
    ('chardet', 'chardet'),
    ('colorama', 'colorama'),
]


def test_requirements():
    """SPEC 8.8: never install packages behind the user's back; name the
    missing ones and the command that installs them, then exit."""
    missing = []
    for package_name, import_name in requirements:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(package_name)
    if missing:
        sys.stderr.write(
            'missing required package(s): ' + ', '.join(missing) + '\n'
            'install them with:\n'
            f'    {sys.executable} -m pip install ' + ' '.join(missing) + '\n')
        sys.exit(2)
