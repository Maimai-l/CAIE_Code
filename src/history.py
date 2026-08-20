import os
from os.path import join, exists, dirname

# readline is optional; without it only line editing/history is lost.
try:
    import readline
except Exception:
    readline = None

# Installation directory (read-only at runtime, SPEC 8.13).
HOME_PATH = dirname(dirname(__file__))

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
