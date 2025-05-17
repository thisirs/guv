import argparse
import importlib
import importlib.metadata
import inspect
import logging
import os
import shlex
import sys

from doit.cmd_base import NamespaceTaskLoader
from doit.doit_cmd import DoitMain

from . import tasks
from .handlers import get_handlers
from .config import settings
from .logger import logger
from .parser import get_parser
from .tasks.base import SemesterTask, TaskBase, UVTask


def get_task_loader():
    task_loader = NamespaceTaskLoader()

    # Load tasks from guv
    m = inspect.getmembers(
        tasks,
        lambda v: inspect.isclass(v)
        and issubclass(v, TaskBase)
        and v not in [TaskBase, SemesterTask, UVTask],
    )
    logger.debug("%s core tasks loaded", len(m))
    task_loader.namespace = dict(m)

    # Load tasks from plugins
    plugin_tasks = []
    for entry_point in importlib.metadata.entry_points(group="guv_tasks"):
        name = entry_point.name
        task_class = entry_point.load()
        plugin_tasks.append((name, task_class))

    logger.debug("%s tasks loaded from plugins", len(plugin_tasks))
    task_loader.namespace.update(dict(plugin_tasks))

    return task_loader


def print_completer(shell="zsh"):
    import shtab

    task_loader = get_task_loader()

    shtab_complete = {
        "csv_create_groups": {
            "column": ["--grouping"],
            "columns": ["--ordered", "--affinity-groups", "--other-groups"]
        },
        "csv_for_upload": {
            "column": ["--grade-colname", "--comment-colname"]
        },
        "csv_groups": {
            "columns": ["--groups"]
        },
        "json_group": {
            "column": ["--group"]
        },
        "maggle_teams": {
            "column": ["group"]
        },
        "pdf_attendance": {
            "column": ["--group", "--tiers-temps"]
        },
        "pdf_attendance_full": {
            "column": ["--group"]
        },
        "pdf_trombinoscope": {
            "column": ["--group", "--subgroup"]
        },
        "xls_grade_book_group": {
            "column": ["--order-by", "--worksheets", "--group-by"],
            "columns": ["--extra-cols"],
            "file": ["--marking-scheme"]
        },
        "xls_grade_book_no_group": {
            "column": ["--order-by", "--worksheets"],
            "columns": ["--extra-cols"],
            "file": ["--marking-scheme"]
        },
        "xls_grade_book_jury": {
            "file": ["--config"]
        }
    }

    parser = get_parser(task_loader.namespace)

    preamble = {"zsh": """
_guv_column() {
    if test -e $(pwd)/generated/.columns.list; then
        local columns=("${(@f)$(cat $(pwd)/generated/.columns.list)}")
        _describe 'columns' columns
    fi
}

_guv_columns() {
    if test -e $(pwd)/generated/.columns.list; then
        local -a columns=("${(@f)$(cat $(pwd)/generated/.columns.list)}")
    fi

    _values -s , columns $columns
}

    """}

    subparsers = parser._actions[1]
    for task, subparser in subparsers._name_parser_map.items():
        if task in shtab_complete:
            for action in subparser._actions:
                if set(action.option_strings).intersection(set(shtab_complete[task].get("columns", []))):
                    action.complete = {"zsh": "_guv_columns"}

                if set(action.option_strings).intersection(set(shtab_complete[task].get("column", []))):
                    action.complete = {"zsh": "_guv_column"}

                if set(action.option_strings).intersection(set(shtab_complete[task].get("file", []))):
                    action.complete = shtab.FILE

    print(shtab.complete(parser, shell=shell, root_prefix="guv", preamble=preamble))


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(prog="guv", description="", add_help=False)
    parser.add_argument("command", nargs="?")
    args, other = parser.parse_known_args(argv)

    task_name = args.command
    ret = None
    try:
        task_loader = get_task_loader()
        handlers = get_handlers()

        if "-h" in other or "--help" in other:
            parser = get_parser(task_loader.namespace)
            parser.parse_args(argv)
            return

        if task_name in handlers:
            handler = handlers[task_name]
            ret = handler().run(other)
        else:
            task_loader.namespace.update(settings.settings)
            if task_name is None:
                logger.debug("Run doit with default tasks")
                ret = DoitMain(task_loader).run([])

            elif task_name == "doit":
                logger.debug("Bypass call to doit")
                ret = DoitMain(task_loader).run(sys.argv[2:])

            else:
                ret = DoitMain(task_loader).run([task_name])

    except Exception as e:
        if logger.level < logging.INFO:
            raise e from e
        else:
            logger.error(e)
            sys.exit(1)

    else:

        if (
            ret == 0
            and settings._settings is not None # Don't trigger settings loading that might fail
            and "SEMESTER_DIR" in settings._settings
            and sys.argv[1:]
        ):
            command_line = "guv " + " ".join(map(shlex.quote, sys.argv[1:])) + "\n"
            if "UV_DIR" in settings._settings and settings._settings["UV_DIR"] is not None:
                directory = settings._settings["UV_DIR"]
            else:
                directory = settings._settings["SEMESTER_DIR"]

            fp = os.path.join(directory, ".history")

            with open(fp, "a") as file:
                file.write(command_line)

    return ret


