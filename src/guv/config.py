import importlib
import logging
import os
from datetime import date
from pathlib import Path

from schema import And, Or, Schema, SchemaError, Use

from .exceptions import ImproperlyConfigured
from .schema_utils import Iterable
from .utils import pformat

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
            msg = pformat(self.help, value=value)
            raise ImproperlyConfigured(msg) from e


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
        help="La variable 'CRENEAU_UV' est incorrecte : un chemin relatif vers le fichier pdf des créneaux ingénieur est attendu",
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
        help="La variable 'SELECTED_PLANNINGS' est incorrecte : une liste des plannings actifs est attendue et la variable vaut '{value}'",
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
        default=logging.INFO
    ),
    Setting(
        "TASKS",
        schema=Schema([str]),
        help="La variable 'TASKS' est incorrecte : une liste de chemin vers des fichiers est attendue",
        default=[]
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
        "DOCS",
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
        return name in self.settings and self.settings[name] is not None

    def SELECTED_PLANNINGS_default(self):
        return list(self.PLANNINGS.keys())

    def __getattr__(self, name):
        logger.debug(f"Accessing setting '{name}'")

        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        # Values from environ have precedence
        if name in os.environ:
            value = os.environ[name]
        # Next look at loaded settings
        elif name in self.settings:
            value = self.settings[name]
        # Look at dynamic default
        elif (name + "_default") in Settings.__dict__:
            value = Settings.__dict__[name + "_default"](self)
        # Look at static default
        elif name in DEFAULT_SETTINGS:
            value = DEFAULT_SETTINGS[name]
        else:
            raise ImproperlyConfigured(
                f"L'option `{name}` n'a pas pu être trouvée"
            )

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
                "default_tasks": ["xls_affectation"],
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
            logger.debug("Not in UV or semester directory")

    def load_file(self, config_file):
        logger.debug("Loading configuration file: {}".format(config_file))

        try:
            module_name = os.path.splitext(os.path.basename(config_file))[0]
            spec = importlib.util.spec_from_file_location(module_name, config_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except ImportError as e:
            logger.warning(f"Problème de chargement du fichier {config_file}, ignoré")
        except Exception as e:
            raise ImproperlyConfigured(f"Problème de chargement du fichier {config_file}", e) from e

        settings = [s for s in dir(module) if s.isupper()]
        for setting in settings:
            setting_value = getattr(module, setting)
            self._settings[setting] = setting_value


if SEMESTER_VARIABLE in os.environ:
    wd = os.environ.get(SEMESTER_VARIABLE)
else:
    wd = os.getcwd()

settings = Settings(wd)

class LogFormatter(logging.Formatter):

    formats = {
        logging.DEBUG: "DEBUG: %(msg)s",
        logging.INFO: "%(msg)s",
        logging.WARN: "\033[33mWARNING\033[0m: %(msg)s",
        logging.ERROR: "\033[31mERROR\033[0m: %(msg)s",
    }
    def format(self, record):
        return LogFormatter.formats.get(
            record.levelno, self._fmt) % record.__dict__

logger = logging.getLogger("guv")
handler = logging.StreamHandler()
handler.setFormatter(LogFormatter())
logger.setLevel(settings.DEBUG)
logger.addHandler(handler)
