import sys
import re
import copy
from pathlib import Path
import argparse

from doit.exceptions import TaskFailed

from .config import semester_settings, SettingsUpdate, UVSettings
from .utils_config import selected_uv, get_unique_uv
from .utils import ParseArgsFailed, ParseArgAction


class TaskBase:
    """Subclass this to define tasks."""

    def __init__(self):
        name = self.__class__.__name__
        task_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        if task_name.startswith("task_"):
            task_name = task_name[5:]
        self.task_name = task_name
        self.doc = self.__class__.__doc__

    @classmethod
    def create_doit_tasks(cls):
        if cls in [TaskBase, UVTask, CliArgsMixin]:
            return  # avoid create tasks from base class 'Task'

        # Convert task name to snake-case
        task_name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
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
            if "targets" not in kw:
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
            elif hasattr(cls, "unique_uv") and cls.unique_uv:
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

        except ParseArgsFailed as e:  # Cli parser failed
            kw = {
                'actions': [ParseArgAction(e.parser, e.args)],
            }
            return kw
        except Exception as e:
            if semester_settings.DEBUG > 0:
                raise e from e
            tf = TaskFailed(e.args)
            kw["actions"] = [lambda: tf]
            return kw


class UVTask(TaskBase):
    unique_uv = True

    def __init__(self, planning, uv, info):
        super().__init__()
        self.planning, self.uv, self.info = planning, uv, info
        self._settings = None

    @property
    def settings(self):
        if self._settings is None:
            uv_config_file = Path(
                semester_settings.SEMESTER_DIR / self.uv / "config.py"
            )
            uv_settings = UVSettings(uv_config_file)
            self._settings = SettingsUpdate(copy.copy(semester_settings), uv_settings)
        return self._settings


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

        # Give access to parser with cli keyword (for shell completion)
        if len(argv) == 2 and argv[1] == "parsearg":
            raise ParseArgsFailed(self.parser)

        # Base task specified in command line
        if len(argv) >= 2 and argv[1] == self.task_name:
            sargv = argv[2:]
            args = self.parser.parse_args(sargv)
        else:
            # Test if dependant task needs arguments; current ones are not
            # relevant

            # If parse_args fails, don't show error message and don't sys.exit()
            def dummy(msg):
                raise Exception()
            self.parser.error = dummy

            args = self.parser.parse_args(args=[])

        # Set parsed arguments as attributes of self
        for key, value in args.__dict__.items():
            self.__setattr__(key, value)
