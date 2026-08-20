import os
import json
from .history import HOME_PATH, STATE_DIR
from .config_funcs import *


class _Config:
    def __init__(self, name, default_val, update_obj=None):
        self.name = name
        self.default_val = default_val
        self.val = default_val
        self.update_obj = update_obj

    def update(self, value):
        if self.update_obj:
            self.update_obj.update(self, value)
        else:
            self.val = value

    def _init_update(self, value):
        self.val = value


class Config:
    def __init__(self, config_file_name='config.json'):
        self.config_path = os.path.join(STATE_DIR, config_file_name)
        self.config = {
            'remote': _Config('remote', 'https://github.com/iewnfod/CAIE_Code.git', remote_update),
            'dev': _Config('dev', False, dev_mod),
            'integrity-protection': _Config('integrity-protection', False, integrity_protection),
            'branch': _Config('branch', 'stable', branch_update),
            'rl': _Config('recursion-limit', 1000, recursive_limit),
            'dev.simulate-update': _Config('dev.simulate-update', False, simulate_update),
            'auto-update': _Config('auto-update', False, auto_update),
            'last-auto-update': _Config('last-auto-update', 0, last_auto_update),
            'interval-update': _Config('interval-update', 604800, interval_update),
            'default-package-path': _Config('default-package-path', os.path.join(STATE_DIR, 'packages'), default_package_path),
        }
        self._load()

    def _load(self):
        path = self.config_path
        if not os.path.exists(path):
            # One-time migration from the old in-installation config file.
            legacy = os.path.join(HOME_PATH, '.cpc_config.json')
            if os.path.exists(legacy):
                path = legacy
            else:
                return
        try:
            with open(path, 'r') as f:
                stored = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        for key, val in stored.items():
            if key in self.config:
                self.config[key]._init_update(val)
        if path is not self.config_path:
            self.write_config()

    def write_config(self):
        data = {key: self.config[key].val for key in sorted(self.config)}
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=4)

    def update_config(self, opt_name, value):
        if opt_name in self.config:
            # Values keep their case; enum-like configs normalize themselves
            # (SPEC 8.9).
            self.config[opt_name].update(value)
            self.write_config()
            print(f'Successfully set `{opt_name}` to `{self.config[opt_name].val}`')
        else:
            self.err_config(opt_name)

    def reset_config(self):
        try:
            os.remove(self.config_path)
            print('Successfully reset all configs.')
        except FileNotFoundError:
            print('Successfully reset all configs.')
        except OSError as e:
            print(f'Error deleting config file: {e}')

    def output_available_configs(self):
        print('Available configs: ')
        for i in self.config.keys():
            print(f'\t{i}')

    def err_config(self, opt_name):
        print(f'Unknown config: {opt_name}')
        self.output_available_configs()

    def get_config(self, opt_name):
        if opt_name in self.config:
            return self.config[opt_name].val
        self.err_config(opt_name)

    def get_default_config(self, opt_name):
        if opt_name in self.config:
            return self.config[opt_name].default_val
        self.err_config(opt_name)
