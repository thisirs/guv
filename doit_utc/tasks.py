import os
import sys
import re
import copy
from pathlib import Path
import argparse

from doit.exceptions import TaskFailed

from .config import semester_settings, SettingsUpdate, UVSettings
from .utils_config import selected_uv, get_unique_uv, NotUVDirectory
from .utils import pformat


class TaskBase:
    """Subclass this to define tasks."""

    def __init__(self):
        name = self.__class__.__name__
        task_name = re.sub(r'(?<!^)(?<=[a-z])(?=[A-Z])', '_', name).lower()
        if task_name.startswith("task_"):
            task_name = task_name[5:]
        self.task_name = task_name
        self.doc = self.__class__.__doc__

    @property
    def settings(self):
        return semester_settings

    @classmethod
    def build_target(cls, planning, uv, info):
        return os.path.join(
            semester_settings.SEMESTER_DIR, uv, cls.directory, cls.target_name
        )

    @classmethod
    def create_doit_tasks(cls):
        if cls in [TaskBase, UVTask, CliArgsMixin]:
            return  # avoid create tasks from base class 'Task'

        # Convert task name to snake-case
        task_name = re.sub(r'(?<!^)(?<=[a-z])(?=[A-Z])', '_', cls.__name__).lower()
        if task_name.startswith("task_"):
            task_name = task_name[5:]

        kw = {
            "doc": cls.__doc__,
            "basename": task_name,
            "verbosity": 2
        }

        def build_task(obj, **kwargs):
            kwargs.update(dict(
                (a, getattr(obj, a))
                for a in ["name", "targets", "file_dep", "uptodate", "verbosity"]
                if a in dir(obj)
            ))

            # Allow always_make attr
            if hasattr(obj, "always_make"):
                kwargs["uptodate"] = [False]

            # Allow targets attr specified as single
            # target in target attr
            if "targets" not in kwargs:
                if hasattr(obj, "target"):
                    kwargs["targets"] = [obj.target]

            # Catch any exception an action might trigger
            def wrapper(*args, **kwargs):
                try:
                    return obj.run(*args, **kwargs)
                except Exception as e:
                    if obj.settings.DEBUG > 0:
                        raise e from e
                    msg = " ".join(str(o) for o in e.args)
                    return TaskFailed(msg)

            kwargs["actions"] = [wrapper]

            return kwargs

        try:

            if UVTask not in cls.__mro__:
                # La tâche n'est pas liée à une UV
                instance = cls()
                return build_task(instance, **kw)
            elif cls.unique_uv:
                # La tâche ne s'applique qu'à une seule UV
                planning, uv, info = get_unique_uv()
                instance = cls(planning, uv, info)
                return build_task(instance, **kw)
            else:
                # La tâche s'applique à un ensemble d'UV
                # Return a generator but make sure all build_task
                # functions are executed first.
                tasks = [
                    build_task(cls(planning, uv, info), **kw, name=f"{planning}_{uv}")
                    for planning, uv, info in selected_uv()
                ]
                return (t for t in tasks)

        except NotUVDirectory as e:
            tf = TaskFailed(e.args)
            kw["actions"] = [lambda: tf]
            return kw
        except DependentTaskParserError as e:
            # La construction de la tâche a échoué car c'est une tâche
            # dépendante
            tf = TaskFailed(e.args)
            kw["actions"] = [lambda: tf]
            return kw
        except Exception as e:
            # Exception inexpliquée, la construction de la tâche
            # échoue. Donner éventuellement la pile d'appels
            if semester_settings.DEBUG > 0:
                raise e from e
            tf = TaskFailed(e.args)
            kw["actions"] = [lambda: tf]
            return kw


class UVTask(TaskBase):
    # Some UVTask might concern a unique UV or collection of UV
    unique_uv = True

    def __init__(self, planning, uv, info):
        super().__init__()
        self.planning, self.uv, self.info = planning, uv, info
        self._settings = None

    def document(self, fn):
        return str(Path(semester_settings.SEMESTER_DIR) / self.uv / "documents" / fn)

    def generated(self, fn):
        return str(Path(semester_settings.SEMESTER_DIR) / self.uv / "generated" / fn)

    @property
    def settings(self):
        if self._settings is None:
            uv_config_file = Path(semester_settings.SEMESTER_DIR) / self.uv
            uv_settings = UVSettings(uv_config_file)
            self._settings = SettingsUpdate(copy.copy(semester_settings), uv_settings)
        return self._settings


class DependentTaskParserError(Exception):
    pass


class CliArgsMixin(TaskBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parse_args()

    def parse_args(self):
        parser = argparse.ArgumentParser(
            description=self.doc,
            prog=f"doit-utc {self.task_name}"
        )

        for arg in self.cli_args:
            parser.add_argument(*arg.args, **arg.kwargs)
        self.parser = parser

        # Command-line arguments
        argv = sys.argv

        # Teste si la tâche courante est la tâche principale spécifiée
        # dans la ligne de commande ou une tâche dépendante.
        if len(argv) >= 2 and argv[1] == self.task_name:
            # Tâche principale
            sargv = argv[2:]
            args = self.parser.parse_args(sargv)
        else:
            # Tâche dépendante, la construction de la tâche est
            # impossible si elle demande des arguments en ligne de
            # commande

            # If parse_args fails, don't show error message and don't sys.exit()
            def dummy(msg):
                raise DependentTaskParserError()
            self.parser.error = dummy

            args = self.parser.parse_args(args=[])

        # Set parsed arguments as attributes of self
        for key, value in args.__dict__.items():
            self.__setattr__(key, value)
