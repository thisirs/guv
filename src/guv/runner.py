import importlib
import inspect
import logging
import os
import sys

import jinja2
from doit.cmd_base import NamespaceTaskLoader
from doit.doit_cmd import DoitMain

import guv

# Load settings from configuration files
from .logger import logger
from .config import settings
from .exceptions import ImproperlyConfigured
from .tasks import (attendance, calendar, gradebook, grades, ical, instructors,
                    moodle, students, trombinoscope, utc)
from .tasks.base import TaskBase, UVTask, CliArgsMixin
from .parser import get_parser, get_parser_shtab


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
        os.makedirs(uv_dir, exist_ok=True)
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")
        if os.path.exists(new_path):
            raise Exception("File config.py already exists")
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)


def run_creastesemester(args):
    base_dir = os.path.join(os.getcwd(), args.semester)
    doc_dir = os.path.join(base_dir, "documents")
    gen_dir = os.path.join(base_dir, "generated")
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(doc_dir, exist_ok=True)
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
    if os.path.exists(new_path):
        raise Exception("File config.py already exists")
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
    sys.exit(DoitMain(task_loader).run(args))


def run_task(task_loader, task_name):
    """Load config.py files and run tasks."""

    try:
        task_loader.load_variables(settings.settings)
        modules = load_custom_tasks(settings.TASKS)
        task_loader.load_modules(*modules)
    except Exception as e:
        if logger.level < logging.INFO:
            raise e from e
        else:
            logger.error(e)
            return 1

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


def main(argv=sys.argv):
    task_loader = ModuleTaskLoader.from_modules(
        instructors,
        utc,
        grades,
        students,
        trombinoscope,
        moodle,
        ical,
        calendar,
        attendance,
        gradebook,
    )
    logger.debug("%s tasks loaded", len(task_loader.tasks))

    parser = get_parser(task_loader.tasks, add_hidden=True)
    args = parser.parse_args()
    task_name = args.command

    if task_name == "createsemester":
        logger.debug("Run createsemester task")
        return run_creastesemester(args)

    if task_name == "createuv":
        logger.debug("Run createuv task")
        return run_createuv(args)

    return run_task(task_loader, task_name)

