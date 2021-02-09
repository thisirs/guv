import os
from pathlib import Path
import importlib
from datetime import date
import logging
from schema import Schema, Or, And, Use, SchemaError
from .exceptions import ImproperlyConfigured
from .schema_utils import Iterable

SEMESTER_VARIABLE = "GUV_SEMESTER_PATH"

LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


class Setting:
    def __init__(self, name, schema=None, help=None, default=None):
        self.name = name
        self.schema = schema
        self.help = help
        self.default = default

    def validate(self, value):
        if self.schema is None:
            return value
        try:
            return self.schema.validate(value)
        except SchemaError as e:
            raise ImproperlyConfigured(self.help) from e


_SETTING_LIST = [
    Setting(
        "UVS",
        schema=Schema(Or([str], (str,))),
        help="La variable 'UVS' est incorrecte : une liste des UV gérées est attendue",
    ),
    Setting(
        "PLANNINGS",
        schema=Schema({str: dict}),
        help="La variable 'PLANNINGS' est incorrecte: il faut que ce soit un dictionnaire dont les clés sont des plannings et les valeurs un dictionnaire de propriétés",
    ),
    Setting(
        "CRENEAU_UV",
        schema=Schema(str),
        help="La variable 'CRENEAU_UV' est incorrecte : un chemin relatif vers le fichier des créneaux est attendu",
    ),
    Setting(
        "ENT_LISTING",
        schema=Schema(str),
        help="La variable 'ENT_LISTING' est incorrecte : un chemin relatif vers l'effectif de l'UV disponible sur l'ENT est attendu",
    ),
    Setting(
        "AFFECTATION_LISTING",
        schema=Schema(Or(None, str)),
        help="La variable 'AFFECTATION_LISTING' est incorrecte : un chemin relatif vers les affectations aux Cours/TD/TP fourni par l'administration est attendu",
    ),
    Setting(
        "MOODLE_LISTING",
        schema=Schema(Or(None, str)),
        help="La variable 'MOODLE_LISTING' est incorrecte : un chemin relatif vers l'effectif fourni par Moodle est attendu",
    ),
    Setting(
        "SELECTED_PLANNINGS",
        schema=Schema([str]),
        help="La variable 'SELECTED_PLANNINGS' est incorrecte : une liste des plannings actifs est attendue",
    ),
    Setting(
        "DEFAULT_INSTRUCTOR",
        schema=Schema(str),
        help="La variable 'DEFAULT_INSTRUCTOR' est incorrecte : une chaîne de caractères est attendue",
    ),
    Setting(
        "DEBUG",
        schema=Schema(Or(
            int,
            And(str, Use(int)),
            And(
                str,
                lambda s: s.lower() in LEVELS.keys(),
                Use(lambda s: LEVELS[s.lower()])
            ),
        )),
        help="La variable 'DEBUG' est incorrecte : un entier est attendu",
        default=logging.WARNING
    ),
    Setting(
        "TASKS",
        schema=Schema([str]),
        help="La variable 'TASKS' est incorrecte : une liste de chemin vers des fichiers est attendue",
    ),
    Setting(
        "SKIP_DAYS_C",
        schema=Schema(Or([Or(date)], (Or(date)))),
        help="La variable 'SKIP_DAYS_C' est incorrecte : une liste d'objets `date` est attendue",
    ),
    Setting(
        "SKIP_DAYS_D",
        schema=Schema(Or([date], (date,))),
        help="La variable 'SKIP_DAYS_D' est incorrecte : une liste d'objets `date` est attendue",
    ),
    Setting(
        "SKIP_DAYS_T",
        schema=Schema(Or([date], (date,))),
        help="La variable 'SKIP_DAYS_T' est incorrecte : une liste d'objets `date` est attendu",
    ),
    Setting(
        "TURN",
        schema=Schema({date: str}),
        help="La variable 'TURN' est incorrecte : un dictionnaire d'objets vers un jour est attendu",
    ),
    Setting(
        "AGGREGATE_DOCUMENTS",
        schema=Schema(
            Or(
                And(None, Use(lambda x: [])),  # None -> []
                (Iterable(Or(None, str), callable)),  # Tuple of pairs
                [Iterable(Or(None, str), callable)],  # List of pairs
                And(
                    {Or(None, str): callable},
                    Use(lambda x: [[k, v] for k, v in x.items()]),
                ),
            )
        ),
        help="La variable 'AGGREGATE_DOCUMENTS' est incorrecte : un itérable de paires est attendu",
    ),
]

SETTINGS = {
    setting.name: setting for setting in _SETTING_LIST
}

DEFAULT_SETTINGS = {
    setting.name: setting.default for setting in _SETTING_LIST if setting.default is not None
}

VALIDATION_SCHEMES = {
    setting.name: setting.schema for setting in _SETTING_LIST if setting.schema is not None
}


class Settings:
    def __init__(self, cwd):
        self.cwd = cwd
        self._settings = None

    def __contains__(self, name):
        return name in self.settings

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        # Get value in environ or settings
        if name in os.environ:
            value = os.environ[name]
        elif name in self.settings:
            value = self.settings[name]
        elif name in DEFAULT_SETTINGS:
            value = DEFAULT_SETTINGS[name]
        else:
            raise ImproperlyConfigured

        if name in SETTINGS:
            setting = SETTINGS[name]
            return setting.validate(value)
        else:
            return value

    @property
    def settings(self):
        if self._settings is None:
            self.load_settings()
        return self._settings

    @property
    def is_uv_dir(self):
        return (Path(self.cwd) / "config.py").exists() and (
            Path(self.cwd).parent / "config.py"
        ).exists()

    @property
    def is_semester_dir(self):
        return (Path(self.cwd) / "config.py").exists() and not (
            Path(self.cwd).parent / "config.py"
        ).exists()

    def load_settings(self):
        self._settings = {}
        if self.is_semester_dir:
            self.config_files = [str(Path(self.cwd) / "config.py")]
            self.semester_directory = str(Path(self.cwd))
            self._settings["UV_DIR"] = None
            self._settings["SEMESTER"] = os.path.basename(self.semester_directory)
            self._settings["SEMESTER_DIR"] = self.semester_directory
            self._settings["DOIT_CONFIG"] = {
                "dep_file": os.path.join(self.semester_directory, ".doit.db"),
                "verbosity": 2,
                "default_tasks": ["utc_uv_list_to_csv"],
            }
            self.load_file(Path(self.cwd) / "config.py")

        elif self.is_uv_dir:
            self.config_files = [
                str(Path(self.cwd) / "config.py"),
                str(Path(self.cwd).parent / "config.py"),
            ]
            self.semester_directory = str(Path(self.cwd).parent)
            self._settings["UV_DIR"] = os.path.basename(self.cwd)
            self._settings["SEMESTER"] = os.path.basename(self.semester_directory)
            self._settings["SEMESTER_DIR"] = self.semester_directory
            self._settings["DOIT_CONFIG"] = {
                "dep_file": os.path.join(self.semester_directory, ".doit.db"),
                "verbosity": 2,
                "default_tasks": ["utc_uv_list_to_csv", "xls_student_data_merge"],
            }

            self.load_file(Path(self.cwd).parent / "config.py")
            self.load_file(Path(self.cwd) / "config.py")

        else:
            logger.info("Not in UV or semester directory")

    def load_file(self, config_file):
        logger.info("Loading configuration file: {}".format(config_file))

        module_name = os.path.splitext(os.path.basename(config_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, config_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        settings = [s for s in dir(module) if s.isupper()]
        for setting in settings:
            setting_value = getattr(module, setting)
            self._settings[setting] = setting_value


if SEMESTER_VARIABLE in os.environ:
    wd = os.environ.get(SEMESTER_VARIABLE)
else:
    wd = os.getcwd()

settings = Settings(wd)

logging.basicConfig(format="%(message)s")
logger = logging.getLogger("guv")
logger.setLevel(settings.DEBUG)
