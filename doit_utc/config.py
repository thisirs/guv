import os
from pathlib import Path
import importlib
from datetime import datetime
from schema import Schema, Or, And, Use, SchemaError

SEMESTER_VARIABLE = "DOIT_UTC_SEMESTER_PATH"


class ImproperlyConfigured(Exception):
    pass


class Settings:
    def __init__(self, cwd):
        self.cwd = cwd
        self.semester_directory = None
        self.settings = {}
        self.validation_schemes = {
            "UVS": (
                Schema(Or([str], (str,))),
                "La variable 'UVS' est incorrecte",
            ),
            "PLANNINGS": (
                Schema({str: dict}),
                "La variable 'PLANNINGS' est incorrecte",
            ),
            "CRENEAU_UV": (
                Schema(str),
                "La variable 'CRENEAU_UV' est incorrecte",
            ),
            "ENT_LISTING": (
                Schema(str),
                "La variable 'ENT_LISTING' est incorrecte",
            ),
            "AFFECTATION_LISTING": (
                Schema(str),
                "La variable 'AFFECTATION_LISTING' est incorrecte",
            ),
            "MOODLE_LISTING": (
                Schema(str),
                "La variable 'MOODLE_LISTING' est incorrecte",
            ),
            "SELECTED_PLANNINGS": (
                Schema([str]),
                "La variable 'SELECTED_PLANNINGS' est incorrecte",
            ),
            "DEFAULT_INSTRUCTOR": (
                Schema(str),
                "La variable 'DEFAULT_INSTRUCTOR' est incorrecte",
            ),
            "DEBUG": (
                Schema(Or(And(str, Use(int)), int)),
                "La variable 'DEBUG' est incorrecte",
            ),
            "SKIP_DAYS_C": (
                Schema(Or([datetime], (datetime,))),
                "La variable 'SKIP_DAYS_C' est incorrecte",
            ),
            "SKIP_DAYS_D": (
                Schema(Or([datetime], (datetime,))),
                "La variable 'SKIP_DAYS_D' est incorrecte",
            ),
            "SKIP_DAYS_T": (
                Schema(Or([datetime], (datetime,))),
                "La variable 'SKIP_DAYS_T' est incorrecte",
            ),
            "TURN": (
                Schema({datetime: str}),
                "La variable 'TURN' est incorrecte",
            )
        }
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
                self.settings["UV_DIR"] = os.path.basename(self.cwd)
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
                self.settings["UV_DIR"] = None
                self._load_default_semester_settings()
                self._load(Path(self.cwd) / "config.py")
        else:
            raise ImproperlyConfigured("Pas dans un dossier d'UV ou de semestre")

    def _load_default_semester_settings(self):
        self.settings["SEMESTER"] = os.path.basename(self.semester_directory)
        self.settings["SEMESTER_DIR"] = self.semester_directory
        self.settings["DOIT_CONFIG"] = {
            "dep_file": os.path.join(self.semester_directory, ".doit.db"),
            "verbosity": 2,
            "default_tasks": ["utc_uv_list_to_csv"],
        }
        self.settings["DEBUG"] = 0

    def _load_default_uv_settings(self):
        self.settings["DOIT_CONFIG"] = {
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
            self.settings[setting] = setting_value

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        # Load attributes from configuration files
        if not self._setup:
            self.setup()
            self._setup = True

        if name in os.environ:
            value = os.environ[name]
        elif name in self.settings:
            value = self.settings[name]
        else:
            raise ImproperlyConfigured(f"La variable '{name}' n'a été trouvée dans aucun fichier de configuration")

        if name in self.validation_schemes:
            try:
                schema, msg = self.validation_schemes[name]
                return schema.validate(value)
            except SchemaError as e:
                raise ImproperlyConfigured(msg)
        else:
            return value

    def __contains__(self, e):
        if not self._setup:
            self.setup()
            self._setup = True
        return e in self.settings


if SEMESTER_VARIABLE in os.environ:
    wd = os.environ.get(SEMESTER_VARIABLE)
else:
    wd = os.getcwd()

settings = Settings(wd)
