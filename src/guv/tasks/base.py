import argparse
import logging
import os
import re
import sys
from pathlib import Path
import datetime

import yaml
from doit.exceptions import TaskFailed
from doit.tools import config_changed

from ..config import Settings, settings
from ..exceptions import (DependentTaskParserError, ImproperlyConfigured,
                          NotUVDirectory)
from ..logger import logger
from ..utils import pformat
from ..utils_ask import prompt_number
from ..utils_config import get_unique_uv, selected_uv


class TaskBase:
    """Subclass this to define tasks."""

    target_dir = "."
    target_name = None

    def setup(self):
        """Préparation de la tâche.

        Doit initialiser l'attribut `file_dep` et `target` pour
        préserver l'arbre des dépendances avant éventuellement
        d'échouer avec les exceptions `ImproperlyConfigured`,
        `DependentTaskParserError`, `NotUVDirectory` seulement. Doit
        appeler la méthode `parse_args` si l'interface `CliArgsMixin`
        est utilisée.

        """

        logger.debug("Setting up task `%s`", self.task_name())

    def run(self):
        """Exécution de la tâche.

        Toutes les exceptions sont rattrapées et renvoie un
        `TaskFailed` à `doit` en mode normal. En mode debug, aucune
        exception n'est rattrapée.

        """
        pass

    @property
    def settings(self):
        logger.debug("Get settings for TaskBase `%s`", self.task_name())

        return settings

    @classmethod
    def target_from(cls, **kwargs):
        """Return a target from the class of the task and keywords arguments

        The class attributes `target_dir` and `target_name` are used.
        They might contain variables in braces that are expanded by
        keyword arguments. Mainly used by other classes to refer to
        target of that class as a dependency.
        """

        target = os.path.join(settings.SEMESTER_DIR, cls.target_dir, cls.target_name)
        return pformat(target, **kwargs)

    def build_target(self, **kwargs):
        """Return a target from current task and keywords arguments

        The class attributes `target_dir` and `target_name` are used.
        They might contain variables in braces that are expanded by
        keyword arguments.
        """

        kw = self.__dict__
        kw["target_dir"] = self.target_dir
        kw["target_name"] = self.target_name
        kw.update(kwargs)
        target = os.path.join(
            settings.SEMESTER_DIR,
            kw["target_dir"],
            kw["target_name"],
        )
        return pformat(target, **kw)

    def to_doit_task(self, **kwargs):
        """Build a doit task from current instance"""

        doit_task = {"doc": self.doc(), "basename": self.task_name(), "verbosity": 2}
        if "name" in kwargs:
            doit_task["name"] = kwargs["name"]

        try:
            self.setup()
        except (ImproperlyConfigured, DependentTaskParserError, NotUVDirectory) as e:
            # Set actions as failed if failed to set up
            tf = TaskFailed(str(e))
            doit_task["actions"] = [lambda: tf]
            logger.debug("Task `%s` failed: %s", self.task_name(), type(e))
        else:
            # Catch any exception an action might trigger
            def action():
                try:
                    return self.run()
                except Exception as e:
                    if settings.DEBUG <= logging.DEBUG:
                        raise e from e
                    msg = " ".join(str(o) for o in e.args)
                    return TaskFailed(msg)

            doit_task["actions"] = [action]

        doit_task.update(
            dict(
                (a, getattr(self, a))
                for a in ["targets", "file_dep", "verbosity"]
                if a in dir(self)
            )
        )

        # Allow uptodate attr
        if hasattr(self, "uptodate"):
            uptodate = self.uptodate
            if isinstance(uptodate, bool):
                doit_task["uptodate"] = [uptodate]
            elif isinstance(uptodate, dict):
                def serialize(obj):
                    if isinstance(obj, datetime.date):
                        return obj.isoformat()
                    if isinstance(obj, dict):
                        return {serialize(k): serialize(v) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [serialize(e) for e in obj]
                    return obj
                props = {k: serialize(v) for k, v in uptodate.items()}
                doit_task["uptodate"] = [config_changed(props)]
            else:
                raise RuntimeError("Unsupported value for uptodate", uptodate)

        # Allow targets attr specified as single
        # target in target attr
        if "targets" not in doit_task:
            if hasattr(self, "target"):
                doit_task["targets"] = [self.target]

        def format_task(doit_task):
            return "\n".join(f"{key}: {value}" for key, value in doit_task.items()
                             if key not in ["doc"])

        logger.debug("Task properties are:")
        logger.debug(format_task(doit_task))

        return doit_task

    @classmethod
    def task_name(cls):
        return re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", cls.__name__).lower()

    @classmethod
    def doc(cls):
        return cls.__doc__

    @classmethod
    def create_doit_tasks_aux(cls):
        # La tâche n'est pas liée à une UV. On vérifie qu'on
        # est dans un dossier d'UV ou de semestre.
        if "SEMESTER_DIR" not in settings:
            raise NotUVDirectory("Pas dans un dossier d'UV/semestre")
        instance = cls()
        return instance.to_doit_task()

    @classmethod
    def create_doit_tasks(cls):
        """Called by doit to retrieve a task or a generator"""

        if cls in [TaskBase, UVTask]:
            return  # avoid create tasks from base classes

        try:
            return cls.create_doit_tasks_aux()
        except (NotUVDirectory, ImproperlyConfigured) as e:
            logger.debug("Task `%s` failed: %s", cls.task_name(), type(e))
            tf = TaskFailed(e.args[0])
            return {
                "basename": cls.task_name(),
                "actions": [lambda: tf],
                "doc": cls.doc(),
            }
        except Exception as e:
            # Exception inexpliquée, la construction de la tâche
            # échoue. Progager l'exception si DEBUG.
            if settings.DEBUG < logging.WARNING:
                raise e from e
            tf = TaskFailed(str(e.args))
            return {
                "basename": cls.task_name(),
                "actions": [lambda: tf],
                "doc": cls.doc(),
            }


class UVTask(TaskBase):
    # Some UVTask might concern a unique UV or collection of UV
    unique_uv = True

    def __init__(self, planning, uv, info):
        super().__init__()
        self.planning, self.uv, self.info = planning, uv, info
        self._settings = None

    @classmethod
    def target_from(cls, **kwargs):
        """Return a target from the class of the task and keywords arguments"""

        target = os.path.join(
            settings.SEMESTER_DIR,
            kwargs["uv"],
            cls.target_dir,
            cls.target_name,
        )
        return pformat(target, **kwargs)

    def build_dep(self, fn):
        """Return pathname of a dependency relative to UV directory"""
        return os.path.join(self.settings.SEMESTER_DIR, self.uv, fn)

    def build_target(self, **kwargs):
        """Return a pathname of the target"""

        kw = self.__dict__.copy()
        kw["target_dir"] = self.target_dir
        kw["target_name"] = self.target_name
        kw.update(kwargs)
        target = os.path.join(
            settings.SEMESTER_DIR,
            kw["uv"],
            kw["target_dir"],
            kw["target_name"],
        )
        return pformat(target, **kw)

    @property
    def settings(self):
        logger.debug("Get settings for UVTask `%s`", self.uv)

        if self._settings is None:
            self._settings = Settings(str(Path(settings.SEMESTER_DIR) / self.uv))
        return self._settings

    @classmethod
    def create_doit_tasks_aux(cls):
        if cls.unique_uv:
            # La tâche ne s'applique qu'à une seule UV
            planning, uv, info = get_unique_uv()
            instance = cls(planning, uv, info)
            return instance.to_doit_task()
        else:
            # La tâche s'applique à un ensemble d'UV
            # Return a generator but make sure all build_task
            # functions are executed first.
            instances = [
                cls(planning, uv, info) for planning, uv, info in selected_uv()
            ]
            tasks = [
                instance.to_doit_task(
                    name=f"{instance.planning}_{instance.uv}",
                    uv=instance.uv
                )
                for instance in instances
            ]

            if not tasks:
                raise ImproperlyConfigured("Aucune UV/UE renseignée dans la variables `UVS`")

            return (t for t in tasks)


class CliArgsMixin:
    """Mixin class that adds a `parse_args` function.

    The `parse_args` function must be used in the `setup` function.
    The parser is built with the `cli_args` attribute.

    """

    cli_args = []

    def __init__(self):
        self._parser = None

    @property
    def parser(self):
        """Return a parser with arguments from cli_args"""

        if self._parser is None:
            parser = argparse.ArgumentParser(
                description=self.doc(), prog=f"guv {self.task_name()}"
            )

            for arg in self.cli_args:
                parser.add_argument(*arg.args, **arg.kwargs)
            self._parser = parser

        return self._parser

    def parse_args(self):
        # Command-line arguments
        argv = sys.argv

        # Teste si la tâche courante est la tâche principale spécifiée
        # dans la ligne de commande ou une tâche dépendante.
        if len(argv) >= 2 and argv[1] == self.task_name():
            # Tâche principale
            sargv = argv[2:]
            args = self.parser.parse_args(sargv)
        else:
            # Tâche dépendante, la construction de la tâche est
            # impossible si elle demande des arguments en ligne de
            # commande

            # If parse_args fails, don't show error message and don't sys.exit()
            parser = self.parser

            def dummy(msg):
                raise DependentTaskParserError()

            parser.error = dummy
            args = parser.parse_args(args=[])

        # Set parsed arguments as attributes of self
        for key, value in args.__dict__.items():
            self.__setattr__(key, value)


class CliArgsInheritMixin(CliArgsMixin):
    """Mixin allowing more flexibility on the generated cli parser"""

    name_required = True
    name_default = None

    def add_arguments(self):
        self._parser = argparse.ArgumentParser()
        if self.name_required:
            self.add_argument(
                "--name", required=True, help="Nom de la feuille de notes"
            )
        else:
            self.add_argument(
                "--name",
                required=False,
                default=self.name_default,
                help="Nom de la feuille de notes",
            )

    def add_argument(self, *args, **kwargs):
        self._parser.add_argument(*args, **kwargs)

    def get_columns(self, **kwargs):
        return []

    # Overridden to allow for a custom parser not relying on cli_args
    # class attribute.
    @property
    def parser(self):
        self.add_arguments()
        return self._parser


class ConfigOpt(CliArgsInheritMixin):
    """Add a config option"""

    config_argname = "--config"
    config_help = "Fichier de configuration"
    config_required = True

    def add_arguments(self):
        super().add_arguments()
        metavar = self.config_argname.strip("-").replace("-", "_").upper()
        self.add_argument(
            self.config_argname,
            metavar=metavar,
            dest="config_file",
            help=self.config_help,
            required=self.config_required,
        )

    @property
    def config(self):
        """Call `build_config` and cache result."""

        if not hasattr(self, "_config") or self._config is None:
            self._config = self.build_config()
        return self._config

    def build_config(self):
        """Build config from cli argument or ask for it if required"""

        config_file = self.config_file
        if config_file is not None:
            return self.parse_config(config_file)
        elif self.config_required:
            return self.ask_config()
        else:
            return None

    def validate_config(self, config):
        """Return a valid configuration.

        Return a default configuration if `config` is None.
        """

        raise NotImplementedError()

    def ask_config(self):
        """Return a configuration by asking user."""

        raise NotImplementedError()

    def parse_config(self, config_file):
        if not os.path.exists(config_file):
            raise Exception(f"{self.config_help} `{config_file}` non trouvé")

        with open(config_file, "r") as stream:
            config = list(yaml.load_all(stream, Loader=yaml.SafeLoader))[0]
            config = self.validate_config(config)
            return config


class MultipleConfigOpt(CliArgsInheritMixin):
    """Add a config option"""

    config_argname = "--config"
    config_help = "Fichiers de configuration"
    config_required = True
    config_number = "Combien de fichiers de configuration ?"

    def add_arguments(self):
        super().add_arguments()
        metavar = self.config_argname.strip("-").replace("-", "_").upper()
        metavar = f"{metavar},[{metavar},...]"
        self.add_argument(
            self.config_argname,
            metavar=metavar,
            dest="config_files",
            type=lambda t: [s.strip() for s in t.split(",")],
            help=self.config_help,
            required=self.config_required,
        )

    @property
    def config(self):
        """Call `build_config` and cache result."""

        if not hasattr(self, "_config") or self._config is None:
            self._config = self.build_config()
        return self._config

    def build_config(self):
        """Build config from cli argument or ask for it if required"""

        config_files = self.config_files
        if config_files:
            return self.parse_config(config_files)
        elif not self.config_required:
            return self.ask_config()
        else:
            return None

    def parse_config(self, config_files):
        configs = []

        for config_file in config_files:
            if not os.path.exists(config_file):
                raise Exception(f"{self.config_help} `{config_file}` non trouvé")

            with open(config_file, "r") as stream:
                config = list(yaml.load_all(stream, Loader=yaml.SafeLoader))[0]
                config = self.validate_config(config)
                configs.append(config)

        return configs

    def ask_one_config(self):
        raise NotImplementedError()

    def ask_config(self):
        configs = []
        n_marking_schemes = prompt_number(self.config_number, default="1")

        for i in range(n_marking_schemes):
            config = self.ask_one_config()
            validated_config = self.validate_config(config)
            configs.append(validated_config)

        return configs


class GroupOpt(CliArgsInheritMixin):
    """Classe pour la spécification d'une colonne dénotant des sous-groupes"""

    def add_arguments(self):
        super().add_arguments()
        self.add_argument("--group", dest="subgroup_by")

    def get_columns(self, **kwargs):
        columns = super().get_columns(**kwargs)

        if self.subgroup_by is not None:
            columns.append((self.subgroup_by, "raw", 6))

        return columns

