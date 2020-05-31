import sys
import re
import argparse

from doit.exceptions import TaskFailed

from .utils import selected_uv, get_unique_uv
from .utils_noconfig import ParseArgsFailed, ParseArgAction


class TaskBase(object):
    """Subclass this to define tasks."""

    def __init__(self, *args, **kwargs):
        name = self.__class__.__name__
        task_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        if task_name.startswith("task_"):
            task_name = task_name[5:]
        self.task_name = task_name
        self.doc = self.__class__.__doc__

    @classmethod
    def create_doit_tasks(cls):
        if cls in [TaskBase, SingleUVTask, CliArgsMixin, MultipleUVTask]:
            return  # avoid create tasks from base class 'Task'

        # Convert task name to snake-case
        task_name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        if task_name.startswith("task_"):
            task_name = task_name[5:]

        kw = {
            "doc": cls.__doc__,
            "basename": task_name
        }
        try:
            if cls is MultipleUVTask:
                def generator():
                    for planning, uv, info in selected_uv():
                        instance = cls(planning, uv, info)
                        kw.update(dict(
                            (a, getattr(instance, a))
                            for a in ["name", "targets", "file_dep", "uptodate", "verbosity"]
                            if a in dir(instance)
                        ))
                        kw["actions"] = [instance.run]
                        yield kw
                return generator()
            else:
                instance = cls()
                kw.update(dict(
                    (a, getattr(instance, a))
                    for a in ["name", "targets", "file_dep", "uptodate", "verbosity"]
                    if a in dir(instance)
                ))
                kw["actions"] = [instance.run]
                return kw

        except ParseArgsFailed as e:  # Cli parser failed
            kw = {
                'actions': [ParseArgAction(e.parser, e.args)],
            }
            return kw
        except Exception as e:
            tf = TaskFailed(e.args)
            kw["actions"] = [lambda: tf]
            return kw


class SingleUVTask(TaskBase):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.planning, self.uv, self.info = get_unique_uv()


class MultipleUVTask(TaskBase):
    def __init__(self, planning, uv, info):
        super().__init__()
        self.planning, self.uv, self.info = planning, uv, info


class CliArgsMixin(TaskBase):
    def __init__(self, *args, **kwargs):
        super().__init__()
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
        if len(argv) < 2:          # doit_utc a_task [args]
            raise Exception("Wrong number of arguments in sys.argv")

        # Give access to parser with cli keyword (for shell completion)
        if len(argv) == 2 and argv[1] == "parsearg":
            raise ParseArgsFailed(self.parser)

        # Base task specified in command line
        base_task = argv[1]

        if self.task_name == base_task:  # Args are relevant
            sargv = argv[2:]
            args = self.parser.parse_args(sargv)
        else:
            # Test if dependant task needs arguments; current ones are not
            # relevant

            # If parse_args fails, don't show error message and don't sys.exit()
            def dummy(msg):
                raise ParseArgsFailed(self.parser)
            self.parser.error = dummy

            args = self.parser.parse_args(args=[])

        for key, value in args.__dict__.items():
            self.__setattr__(key, value)
