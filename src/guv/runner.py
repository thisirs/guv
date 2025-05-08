import argparse
import importlib
import importlib.metadata
import inspect
import logging
import os
import re
import shlex
import shutil
import sys

import jinja2
from doit.cmd_base import NamespaceTaskLoader
from doit.doit_cmd import DoitMain

import guv
from . import tasks
from .config import settings
from .logger import logger
from .parser import get_parser
from .tasks.base import SemesterTask, TaskBase, UVTask


def create_uv_dirs(base_dir, uvs):
    for uv in uvs:
        uv_dir = os.path.join(base_dir, uv)
        doc_dir = os.path.join(uv_dir, "documents")
        gen_dir = os.path.join(uv_dir, "generated")

        logger.info("Création du dossier %s", os.path.relpath(uv_dir, os.getcwd()))
        os.makedirs(uv_dir, exist_ok=True)

        logger.info("Création du dossier %s", os.path.relpath(doc_dir, os.getcwd()))
        os.makedirs(doc_dir, exist_ok=True)

        logger.info("Création du dossier %s", os.path.relpath(gen_dir, os.getcwd()))
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dir = os.path.join(guv.__path__[0], "data", "templates")
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")

        logger.info("Création du fichier %s", os.path.relpath(new_path, os.getcwd()))
        if os.path.exists(new_path):
            raise FileExistsError("Le fichier `%s` existe déjà" % os.path.relpath(new_path, os.getcwd()))
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)


def run_creastesemester(args):
    base_dir = os.path.join(os.getcwd(), args.directory)
    doc_dir = os.path.join(base_dir, "documents")
    gen_dir = os.path.join(base_dir, "generated")

    logger.info("Création du dossier %s", os.path.relpath(base_dir, os.getcwd()))
    os.makedirs(base_dir, exist_ok=True)

    logger.info("Création du dossier %s", os.path.relpath(doc_dir, os.getcwd()))
    os.makedirs(doc_dir, exist_ok=True)

    logger.info("Création du dossier %s", os.path.relpath(gen_dir, os.getcwd()))
    os.makedirs(gen_dir, exist_ok=True)

    semester_name = args.semester or args.directory

    # Get semester_id of the form "P24"
    if (m := re.fullmatch("([aApP])([0-9]{2})", semester_name)) is not None:
        semester_id = semester_name.upper()
    elif (m := re.fullmatch("([aApP])([0-9]{4})", semester_name)) is not None:
        semester_id = m.group(1).upper() + m.group(2)[-2:]
    else:
        semester_id = None

    data_dir = os.path.join(guv.__path__[0], "data")
    context = {
        "UVS": ", ".join(f'"{e}"' for e in args.uv),
        "SEMESTER": args.directory,
    }

    # Copy file if it exists
    if semester_id is not None:
        creneau_uv = os.path.join(data_dir, f"Creneaux-UV_{semester_id}.pdf")
        if os.path.exists(creneau_uv):
            logger.info("Copie du fichier des créneaux du semestre %s", semester_id)
            new_path = os.path.join(doc_dir, "Creneaux-UV.pdf")
            shutil.copy(creneau_uv, new_path)
            context["CRENEAU_UV"] = '"documents/Creneaux-UV.pdf"'
        else:
            logger.info("Fichier des créneaux pour %s non trouvé, renseignez manuellement CRENEAU_UV", semester_name)
            context["CRENEAU_UV"] = None
    else:
        logger.info("Semestre non reconnu, renseignez manuellement CRENEAU_UV")
        context["CRENEAU_UV"] = None

    # Get template for config.py from semester_id
    tmpl_dir = os.path.join(data_dir, "templates")
    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
    try:
        if semester_id is not None:
            tmpl = jinja_env.get_template(f"semester_{semester_id}_config.py.jinja2")
            logger.info("Utilisation du fichier de configuration pour le semestre %s", semester_name)
        else:
            raise FileNotFoundError

    except (jinja2.exceptions.TemplateNotFound, FileNotFoundError):
        logger.info("Utilisation du fichier de configuration par défaut")
        tmpl = jinja_env.get_template("semester_default_config.py.jinja2")

    content = tmpl.render(context)
    new_path = os.path.join(base_dir, "config.py")

    logger.info("Création du fichier %s", os.path.relpath(new_path, os.getcwd()))
    if os.path.exists(new_path):
        raise FileExistsError("Le fichier %s existe déjà" % os.path.relpath(new_path, os.getcwd()))
    with open(new_path, "w", encoding="utf-8") as new_file:
        new_file.write(content)

    create_uv_dirs(base_dir, args.uv)
    return 0


def run_createuv(args):
    base_dir = os.getcwd()
    create_uv_dirs(base_dir, args.uv)
    return 0


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


def creastesemester_handler(other):
    createsemester_parser = argparse.ArgumentParser(
        prog="guv createsemester",
        description="Crée un dossier de semestre",
    )
    createsemester_parser.add_argument("directory")
    createsemester_parser.add_argument("--uv", nargs="*", default=[])
    createsemester_parser.add_argument("--semester")
    args = createsemester_parser.parse_args(other)
    return run_creastesemester(args)


def createuv_handler(other):
    logger.debug("Run createuv task")
    createuv_parser = argparse.ArgumentParser(
        prog="guv createuv",
        description="Crée des dossiers d'UV"
    )
    createuv_parser.add_argument("uv", nargs="+")
    args = createuv_parser.parse_args(other)
    return run_createuv(args)


def get_handlers():
    return {
        "createsemester": creastesemester_handler,
        "createuv": createuv_handler
    }


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

    parser = get_parser(task_loader.tasks)

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
        task_names = [klass.task_name() for t, klass in task_loader.namespace.items()]

        if "-h" in other or "--help" in other:
            parser = get_parser(task_loader.namespace)
            parser.parse_args(argv)
            return

        elif task_name is None:
            task_loader.namespace.update({
                "DOIT_CONFIG": {
                    "default_tasks": ["xls_student_data"]
                }
            })

            logger.debug("Run doit with default tasks")
            ret = DoitMain(task_loader).run([])

        elif task_name == "doit":
            logger.debug("Bypass call to doit")
            ret = DoitMain(task_loader).run(sys.argv[2:])

        elif task_name in task_names:
            ret = DoitMain(task_loader).run([task_name])

        elif task_name in handlers:
            handler = handlers[task_name]
            ret = handler(other)

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


