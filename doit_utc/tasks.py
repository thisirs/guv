import os
import sys
import re
import copy
from pathlib import Path
import argparse

from doit.exceptions import TaskFailed

from .config import settings, Settings, ImproperlyConfigured
from .utils_config import selected_uv, get_unique_uv, NotUVDirectory
from .utils import pformat


class TaskBase:
    """Subclass this to define tasks."""

    target_dir = "."
    target_name = None

    def __init__(self):
        name = self.__class__.__name__
        task_name = re.sub(r'(?<!^)(?<=[a-z])(?=[A-Z])', '_', name).lower()
        self.task_name = task_name
        self.doc = self.__class__.__doc__

    def setup(self):
        pass

    def run(self):
        pass

    @property
    def settings(self):
        return settings

    @classmethod
    def target_from(cls, **kwargs):
        target = os.path.join(
            settings.SEMESTER_DIR,
            cls.target_dir,
            cls.target_name
        )
        return pformat(target, **kwargs)

    def build_target(self, **kwargs):
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

        doit_task = {
            "doc": self.doc,
            "basename": self.task_name,
            "verbosity": 2
        }
        doit_task.update(kwargs)

        try:
            self.setup()
        except (ImproperlyConfigured, DependentTaskParserError, NotUVDirectory) as e:
            if hasattr(self, "targets"):
                doit_task["targets"] = self.targets
            elif hasattr(self, "target"):
                doit_task["targets"] = [self.target]

            tf = TaskFailed(str(e))
            doit_task["actions"] = [lambda: tf]
            return doit_task

        doit_task.update(dict(
            (a, getattr(self, a))
            for a in ["targets", "file_dep", "uptodate", "verbosity"]
            if a in dir(self)
        ))

        # Allow always_make attr
        if hasattr(self, "always_make"):
            doit_task["uptodate"] = [False]

        # Allow targets attr specified as single
        # target in target attr
        if "targets" not in doit_task:
            if hasattr(self, "target"):
                doit_task["targets"] = [self.target]

        # Catch any exception an action might trigger
        def action():
            try:
                return self.run()
            except Exception as e:
                if self.settings.DEBUG > 0:
                    raise e from e
                msg = " ".join(str(o) for o in e.args)
                return TaskFailed(msg)

        doit_task["actions"] = [action]
        return doit_task

    @classmethod
    def create_doit_tasks(cls):
        if cls in [TaskBase, UVTask, CliArgsMixin]:
            return  # avoid create tasks from base class 'Task'

        task_name = re.sub(r'(?<!^)(?<=[a-z])(?=[A-Z])', '_', cls.__name__).lower()
        doc = cls.__doc__

        try:
            if UVTask not in cls.__mro__:
                # La tâche n'est pas liée à une UV
                instance = cls()
                return instance.to_doit_task()
            elif cls.unique_uv:
                # La tâche ne s'applique qu'à une seule UV
                planning, uv, info = get_unique_uv()
                instance = cls(planning, uv, info)
                return instance.to_doit_task()
            else:
                # La tâche s'applique à un ensemble d'UV
                # Return a generator but make sure all build_task
                # functions are executed first.
                instances = [
                    cls(planning, uv, info)
                    for planning, uv, info in selected_uv()
                ]
                tasks = [
                    instance.to_doit_task(name=f"{instance.planning}_{instance.uv}")
                    for instance in instances
                ]

                return (t for t in tasks)

        except NotUVDirectory as e:
            tf = TaskFailed(str(e))
            return {
                "basename": task_name,
                "actions": [lambda: tf],
                "doc": doc
            }
        except Exception as e:
            # Exception inexpliquée, la construction de la tâche
            # échoue. Progager l'exception si DEBUG.
            if settings.DEBUG > 0:
                raise e from e
            tf = TaskFailed(str(e))
            return {
                "basename": task_name,
                "actions": [lambda: tf],
                "doc": doc
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
        target = os.path.join(
            settings.SEMESTER_DIR,
            kwargs["uv"],
            cls.target_dir,
            cls.target_name,
        )
        return pformat(target, **kwargs)

    def build_dep(self, fn):
        return os.path.join(self.settings.SEMESTER_DIR, self.uv, fn)

    def build_target(self, **kwargs):
        kw = self.__dict__
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
        if self._settings is None:
            self._settings = Settings(str(Path(settings.SEMESTER_DIR) / self.uv))
        return self._settings


class DependentTaskParserError(Exception):
    pass


class CliArgsMixin(TaskBase):
    def setup(self):
        super().setup()
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
