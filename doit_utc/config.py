import os
from pathlib import Path
import importlib

SEMESTER_VARIABLE = "DOIT_UTC_SEMESTER_PATH"


class Settings():
    def __init__(self):
        if SEMESTER_VARIABLE in os.environ:
            wd = os.environ.get(SEMESTER_VARIABLE)
        else:
            wd = os.getcwd()

        if (Path(wd).parent / "config.py").exists():
            self.config_files = [Path(wd).parent / "config.py"]
            if (Path(wd) / "config.py").exists():
                self.config_files += [Path(wd) / "config.py"]
        elif (Path(wd) / "config.py").exists():
            self.config_files = [Path(wd) / "config.py"]
        else:
            raise Exception("La variable SEMESTER_VARIABLE ne pointe pas")

        self._loaded = False

        # Default settings
        self.DEBUG = 0

    def __getattr__(self, name):
        if not self._loaded:
            self.load(self.config_file)
            self._loaded = True
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            raise AttributeError(f"Setting variable {name} not set in config.py file")

    def load(self, config_file):
        if not Path(config_file).exists():
            raise Exception

        module_name = os.path.splitext(os.path.basename(config_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, config_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for setting in dir(module):
            if setting.isupper():
                setting_value = getattr(module, setting)
                setattr(self, setting, setting_value)


settings = Settings()
