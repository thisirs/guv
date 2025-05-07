import importlib
import logging
import os
from datetime import date
from pathlib import Path

from schema import And, Or, Schema, SchemaError, Use

from .exceptions import ImproperlyConfigured, NotUVDirectory
from .logger import logger
from .utils import pformat, rel_to_dir_aux

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
        "DOCS",
    ),
    Setting(
        "MOODLE_ID",
        schema=Schema(int),
        help="Identifiant de l'UV/UE sur Moodle"
    ),
    Setting(
        "PORT",
        schema=Schema(int),
        help="Port pour l'envoi de courriel",
        default=587
    ),
    Setting(
        "SMTP_SERVER",
        schema=Schema(str),
        help="Serveur SMTP pour l'envoi de courriel",
        default="smtps.utc.fr"
    ),
    Setting(
        "FROM_EMAIL",
        schema=Schema(str),
        help="Adresse de courriel d'origine des courriels envoyés"
    ),
    Setting(
        "LOGIN",
        schema=Schema(str),
        help="Login pour le server smtp"
    )
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
    def __init__(self, conf_dir=None):
        if conf_dir is None:
            if SEMESTER_VARIABLE in os.environ:
                self.conf_dir = os.environ.get(SEMESTER_VARIABLE)
            else:
                self.conf_dir = os.getcwd()
        else:
            self.conf_dir = conf_dir

        self.cwd = os.getcwd()
        self._settings = None

    def __contains__(self, name):
        return name in self.settings and self.settings[name] is not None

    def __getitem__(self, name):
        return getattr(self, name)

    def __getattr__(self, name):
        logger.debug("Accessing setting `%s`", name)

        # if name == "create_doit_tasks":
        #     raise AttributeError("create_doit_tasks")

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
                f"La variable `{name}` n'a pas pu être trouvée"
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
        return (Path(self.conf_dir) / "config.py").exists() and (
            Path(self.conf_dir).parent / "config.py"
        ).exists()

    @property
    def is_semester_dir(self):
        return (Path(self.conf_dir) / "config.py").exists() and not (
            Path(self.conf_dir).parent / "config.py"
        ).exists()

    def load_settings(self):
        self._settings = {}
        self._settings["CWD"] = str(Path(self.cwd))
        if self.is_semester_dir:
            self.config_files = [str(Path(self.conf_dir) / "config.py")]
            self.semester_directory = str(Path(self.conf_dir))
            self._settings["UV_DIR"] = None
            self._settings["SEMESTER"] = os.path.basename(self.semester_directory)
            self._settings["SEMESTER_DIR"] = self.semester_directory
            self._settings["DOIT_CONFIG"] = {
                # "reporter": ZeroReporter,
                "dep_file": os.path.join(self.semester_directory, ".guv.db"),
                # "check_file_uptodate": "timestamp",
                "verbosity": 2,
                "default_tasks": ["xls_student_data"],
            }
            to_load = [Path(self.conf_dir) / "config.py"]

        elif self.is_uv_dir:
            self.config_files = [
                str(Path(self.conf_dir) / "config.py"),
                str(Path(self.conf_dir).parent / "config.py"),
            ]
            self.semester_directory = str(Path(self.conf_dir).parent)
            self._settings["UV_DIR"] = self.conf_dir
            self._settings["SEMESTER"] = os.path.basename(self.semester_directory)
            self._settings["SEMESTER_DIR"] = self.semester_directory
            self._settings["DOIT_CONFIG"] = {
                # "reporter": ZeroReporter,
                "dep_file": os.path.join(self.semester_directory, ".guv.db"),
                # "check_file_uptodate": "timestamp",
                "verbosity": 2,
                "default_tasks": ["xls_student_data"],
            }

            to_load = [
                Path(self.conf_dir).parent / "config.py",
                Path(self.conf_dir) / "config.py"
            ]
        else:
            raise NotUVDirectory("Pas dans un dossier d'UV/semestre")

        for config_file in to_load:
            try:
                self.load_file(config_file)
            except Exception as e:
                config_file = rel_to_dir_aux(config_file, self._settings["CWD"], self._settings["SEMESTER_DIR"])
                raise ImproperlyConfigured(f"Problème de chargement du fichier `{config_file}`: {e}") from e

    def load_file(self, config_file):
        logger.debug("Loading configuration file: `%s`", config_file)
        module_name = os.path.splitext(os.path.basename(config_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, config_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        settings = [s for s in dir(module) if s.isupper()]
        for setting in settings:
            setting_value = getattr(module, setting)
            self._settings[setting] = setting_value


settings = Settings()
