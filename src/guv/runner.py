import argparse
import importlib
import inspect
import logging
import os
import shlex
import sys

import jinja2
from doit.cmd_base import NamespaceTaskLoader
from doit.doit_cmd import DoitMain

import guv

from . import tasks
from .config import settings
# Load settings from configuration files
from .logger import logger
from .parser import get_parser
from .tasks.base import CliArgsMixin, TaskBase, UVTask


class ModuleTaskLoader(NamespaceTaskLoader):
    @staticmethod
    def from_modules(*modules):
        return ModuleTaskLoader(*modules)

    def __init__(self, *modules):
        super().__init__()
        self.namespace = {}
        self.tasks = {}
        self.variables = {}
        self.load_modules(*modules)

    def load_modules(self, *modules):
        for module in modules:
            m = inspect.getmembers(
                module,
                lambda v: inspect.isclass(v)
                and issubclass(v, TaskBase)
                and v not in [TaskBase, UVTask, CliArgsMixin],
            )
            logger.debug("%s tasks loaded from module `%s`", len(m), module)
            self.tasks.update(dict(m))
            self.namespace.update(dict(m))

    def load_variables(self, dictionary):
        self.variables.update(dictionary)
        self.namespace.update(dictionary)


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

        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")

        logger.info("Création du fichier %s", os.path.relpath(new_path, os.getcwd()))
        if os.path.exists(new_path):
            raise Exception("Le fichier `%s` existe déjà" % os.path.relpath(new_path, os.getcwd()))
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)


def run_creastesemester(args):
    base_dir = os.path.join(os.getcwd(), args.semester)
    doc_dir = os.path.join(base_dir, "documents")
    gen_dir = os.path.join(base_dir, "generated")

    logger.info("Création du dossier %s", os.path.relpath(base_dir, os.getcwd()))
    os.makedirs(base_dir, exist_ok=True)

    logger.info("Création du dossier %s", os.path.relpath(doc_dir, os.getcwd()))
    os.makedirs(doc_dir, exist_ok=True)

    logger.info("Création du dossier %s", os.path.relpath(gen_dir, os.getcwd()))
    os.makedirs(gen_dir, exist_ok=True)

    tmpl_dir = os.path.join(guv.__path__[0], "templates")
    jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
    try:
        tmpl = jinja_env.get_template(f"semester_config_{args.semester}.py.jinja2")
    except jinja2.exceptions.TemplateNotFound:
        tmpl = jinja_env.get_template("semester_config.py.jinja2")

    context = {
        "UVS": ", ".join(f'"{e}"' for e in args.uv),
        "SEMESTER": args.semester,
    }
    content = tmpl.render(context)
    new_path = os.path.join(base_dir, "config.py")

    logger.info("Création du fichier %s", os.path.relpath(new_path, os.getcwd()))
    if os.path.exists(new_path):
        raise Exception("Le fichier `%s` existe déjà" % os.path.relpath(new_path, os.getcwd()))
    with open(new_path, "w", encoding="utf-8") as new_file:
        new_file.write(content)

    create_uv_dirs(base_dir, args.uv)


def run_createuv(args):
    base_dir = os.getcwd()
    create_uv_dirs(base_dir, args.uv)


def load_custom_tasks(filenames):
    modules = []
    for fn in filenames:
        fp = os.path.join(settings.SEMESTER_DIR, fn)
        if os.path.exists(fn):
            module_name = os.path.splitext(os.path.basename(fp))[0]
            spec = importlib.util.spec_from_file_location(module_name, fp)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[spec.name] = module
            modules.append(module)
        else:
            raise Exception("Le fichier de tâches n'existe pas :", fp)

    return modules


def run_doit(task_loader, args):
    return DoitMain(task_loader).run(args)


def get_task_loader():
    task_loader = ModuleTaskLoader.from_modules(tasks)
    return task_loader


def run_task(task_name):
    """Load config.py files and run tasks."""

    task_loader = get_task_loader()

    # Add custom task and variables from config.py files
    task_loader.load_variables(settings.settings)
    modules = load_custom_tasks(settings.TASKS)
    task_loader.load_modules(*modules)

    if task_name is None:
        logger.debug("Run doit with default tasks")
        return run_doit(task_loader, [])

    if task_name == "doit":
        logger.debug("Bypass call to doit")
        return run_doit(task_loader, sys.argv[2:])

    # Run doit without command-line arguments to avoid errors.
    # Doit tasks can handle sys.argv themselves
    logger.debug("Run doit with task only")
    return run_doit(task_loader, [task_name])


def get_parser_shtab():
    import shtab

    task_loader = get_task_loader()

    file_complete = {
        "xls_grade_book_no_group": ['--marking-scheme'],
        "xls_grade_book_group": ['--marking-scheme'],
        "xls_grade_book_jury": ['--config']
    }

    parser = get_parser(task_loader.tasks)
    subparsers = parser._actions[1]
    for task, subparser in subparsers._name_parser_map.items():
        if task in file_complete:
            for action in subparser._actions:
                if set(action.option_strings).intersection(set(file_complete[task])):
                    action.complete = shtab.FILE

    return parser


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(prog="guv", description="", add_help=False)
    parser.add_argument("command", nargs="?")
    args, other = parser.parse_known_args(argv)

    try:
        ret = None
        if "-h" in other:
            task_loader = get_task_loader()
            parser = get_parser(task_loader.tasks)
            parser.parse_args(argv)

        if args.command == "createsemester":
            logger.debug("Run createsemester task")
            createsemester_parser = argparse.ArgumentParser(
                prog="guv createsemester",
                description="Crée un dossier de semestre",
            )
            createsemester_parser.add_argument("semester")
            createsemester_parser.add_argument("--uv", nargs="*", default=[])
            args = createsemester_parser.parse_args(other)
            ret = run_creastesemester(args)
        elif args.command == "createuv":
            logger.debug("Run createuv task")
            createuv_parser = argparse.ArgumentParser(
                prog="guv createuv",
                description="Crée des dossiers d'UV"
            )
            createuv_parser.add_argument("uv", nargs="+")
            args = createuv_parser.parse_args(other)
            ret = run_createuv(args)
        else:
            ret = run_task(args.command)

    except Exception as e:
        if logger.level < logging.INFO:
            raise e from e
        else:
            logger.error(e)
            sys.exit(1)

    else:
        # Don't trigger settings loading that might fail
        if settings._settings is not None and "SEMESTER_DIR" in settings._settings:
            command_line = "guv " + " ".join(map(shlex.quote, sys.argv[1:])) + "\n"
            fp = os.path.join(settings.SEMESTER_DIR, ".history")

            with open(fp, "a") as file:
                file.write(command_line)

    return ret
