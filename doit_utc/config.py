import os
import sys
from pathlib import Path
import importlib

SEMESTER_VARIABLE = "DOIT_UTC_SEMESTER_PATH"


class ImproperlyConfigured(Exception):
    pass


class Settings:
    def __init__(self, cwd):
        self.cwd = cwd
        self.semester_directory = None
        self._setup = False

    def setup(self):
        if (Path(self.cwd) / "config.py").exists():
            if (Path(self.cwd).parent / "config.py").exists():
                # In UV directory
                self.config_files = [
                    str(Path(self.cwd) / "config.py"),
                    str(Path(self.cwd).parent / "config.py")
                ]
                self.semester_directory = str(Path(self.cwd).parent)
                self.UV_DIR = os.path.basename(self.cwd)
                self._load_default_semester_settings()
                self._load(Path(self.cwd).parent / "config.py")
                self._load_default_uv_settings()
                self._load(Path(self.cwd) / "config.py")
            else:
                # In semester directory
                self.config_files = [
                    str(Path(self.cwd) / "config.py"),
                ]
                self.semester_directory = str(Path(self.cwd))
                self.UV_DIR = None
                self._load_default_semester_settings()
                self._load(Path(self.cwd) / "config.py")
        else:
            raise ImproperlyConfigured("Pas dans un dossier d'UV ou de semestre")

    def _load_default_semester_settings(self):
        self.SEMESTER = os.path.basename(self.semester_directory)
        self.SEMESTER_DIR = self.semester_directory
        self.DOIT_CONFIG = {
            "dep_file": os.path.join(self.semester_directory, ".doit.db"),
            "verbosity": 2,
            "default_tasks": ["utc_uv_list_to_csv"],
        }
        self.DEBUG = 0

    def _load_default_uv_settings(self):
        self.DOIT_CONFIG = {
            "dep_file": os.path.join(self.semester_directory, ".doit.db"),
            "verbosity": 2,
            "default_tasks": ["utc_uv_list_to_csv", "xls_student_data_merge"],
        }

    def _load(self, config_file):
        module_name = os.path.splitext(os.path.basename(config_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, config_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        settings = [s for s in dir(module) if s.isupper()]
        for setting in settings:
            setting_value = getattr(module, setting)
            setattr(self, setting, setting_value)

    def __getattr__(self, name):
        if not self._setup:
            self.setup()
            self._setup = True
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        if name in os.environ:
            return name
        elif name in self.__dict__:
            return self.__dict__[name]
        else:
            raise ImproperlyConfigured(f"La variable '{name}' n'a été trouvée dans aucun fichier de configuration")

    def __contains__(self, e):
        if not self._setup:
            self.setup()
            self._setup = True
        try:
            self.__getattr__(e)
            return True
        except (AttributeError, ImproperlyConfigured):
            return False


if SEMESTER_VARIABLE in os.environ:
    wd = os.environ.get(SEMESTER_VARIABLE)
else:
    wd = os.getcwd()

settings = Settings(wd)
