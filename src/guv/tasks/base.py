import os
import sys
import re
from pathlib import Path
import argparse

from doit.exceptions import TaskFailed

from ..exceptions import ImproperlyConfigured, NotUVDirectory, DependentTaskParserError
from ..config import settings, Settings, logger
from ..utils_config import selected_uv, get_unique_uv
from ..utils import pformat


class TaskBase:
    """Subclass this to define tasks."""

    target_dir = "."
    target_name = None

    def setup(self):
        logger.info("Setting up task `{}`".format(self.task_name()))

    def run(self):
        pass

    @property
    def settings(self):
        logger.info("Get settings for TaskBase {}".format(self.task_name()))

        return settings

    @classmethod
    def target_from(cls, **kwargs):
        """Return a target from the class of the task and keywords arguments

        The class attributes `target_dir` and `target_name` are used.
        They might contain variables in braces that are expanded by
        keyword arguments. Mainly used by other classes to refer to
        target of that class as a dependency.
        """

        target = os.path.join(
            settings.SEMESTER_DIR,
            cls.target_dir,
            cls.target_name
        )
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

        doit_task = {
            "doc": self.doc(),
            "basename": self.task_name(),
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
    def task_name(cls):
        return re.sub(r'(?<!^)(?<=[a-z])(?=[A-Z])', '_', cls.__name__).lower()

    @classmethod
    def doc(cls):
        return cls.__doc__

    @classmethod
    def create_doit_tasks(cls):
        """Called by doit to retrieve a task or a generator"""

        if cls in [TaskBase, UVTask, CliArgsMixin]:
            return  # avoid create tasks from base class 'Task'

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
                "basename": cls.task_name(),
                "actions": [lambda: tf],
                "doc": cls.doc()
            }
        except Exception as e:
            # Exception inexpliquée, la construction de la tâche
            # échoue. Progager l'exception si DEBUG.
            if settings.DEBUG > 0:
                raise e from e
            tf = TaskFailed(str(e))
            return {
                "basename": cls.task_name(),
                "actions": [lambda: tf],
                "doc": cls.doc()
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
        logger.info("Get settings for UVTask {}".format(self.uv))

        if self._settings is None:
            self._settings = Settings(str(Path(settings.SEMESTER_DIR) / self.uv))
        return self._settings


class CliArgsMixin(TaskBase):
    def setup(self):
        super().setup()
        self.parse_args()

    def parse_args(self):
        parser = argparse.ArgumentParser(
            description=self.doc(),
            prog=f"guv {self.task_name()}"
        )

        for arg in self.cli_args:
            parser.add_argument(*arg.args, **arg.kwargs)
        self.parser = parser

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
            def dummy(msg):
                raise DependentTaskParserError()
            self.parser.error = dummy

            args = self.parser.parse_args(args=[])

        # Set parsed arguments as attributes of self
        for key, value in args.__dict__.items():
            self.__setattr__(key, value)
