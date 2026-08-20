import os
from os.path import join, exists, dirname

# readline is optional; without it only line editing/history is lost.
try:
    import readline
except Exception:
    readline = None

# The package directory (bundled scripts, notification data).
PACKAGE_DIR = dirname(os.path.abspath(__file__))
# Installation root of a git checkout (VERSION, docs, the git repo for -u).
# Under pip this points into site-packages and is only used by code that
# checks for a git checkout first (SPEC 8.13/8.14).
HOME_PATH = dirname(PACKAGE_DIR)

# User state directory (SPEC 8.9): config, history, packages.
STATE_DIR = os.environ.get('CPC_HOME') or join(os.path.expanduser('~'), '.cpc')
os.makedirs(STATE_DIR, exist_ok=True)


class Cmd:
    def __init__(self, state_dir=STATE_DIR, save_name='history', history_size=1000):
        self.history_size = history_size
        self.path = join(state_dir, save_name)

    def preloop(self):
        if readline and exists(self.path):
            try:
                readline.read_history_file(self.path)
            except Exception:
                # A broken history file must not break the session.
                pass

    def postloop(self):
        if readline:
            try:
                readline.set_history_length(self.history_size)
                readline.write_history_file(self.path)
            except Exception:
                pass
