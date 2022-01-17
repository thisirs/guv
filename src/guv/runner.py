import argparse
import importlib
import inspect
import logging
import os
import re
import sys
import textwrap

import jinja2
from doit.cmd_base import NamespaceTaskLoader
from doit.doit_cmd import DoitMain

import guv

# Load settings from configuration files
from .config import logger, settings
from .exceptions import ImproperlyConfigured
from .tasks import (attendance, calendar, gradebook, grades, ical, instructors,
                    moodle, students, trombinoscope, utc)
from .tasks.base import (CliArgsInheritMixin, CliArgsMixin, ConfigOpt,
                         GroupOpt, TaskBase, UVTask)
from .utils import argument


class ModulesTaskLoader(NamespaceTaskLoader):
    def __init__(self, *modules):
        super().__init__()
        self.namespace = {}
        self.tasks = {}
        self.variables = {}

    def _load_tasks(self, *modules):
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

    def _load_variables(self, dictionary):
        self.variables.update(dictionary)
        self.namespace.update(dictionary)


try:
    task_loader = ModulesTaskLoader()
    task_loader._load_variables(settings.settings)
    task_loader._load_tasks(
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
    logger.debug("%s variables loaded", len(task_loader.variables))
except ImproperlyConfigured as e:
    msg = e.args[0]
    logger.error("%s : %s", msg, e.args[1])
    sys.exit()

# Load custom tasks
try:
    for fn in settings.TASKS:
        fp = os.path.join(settings.cwd, fn)
        if os.path.exists(fn):
            module_name = os.path.splitext(os.path.basename(fp))[0]
            spec = importlib.util.spec_from_file_location(module_name, fp)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[spec.name] = module
            task_loader._load_tasks(module)
        else:
            raise Exception("Le fichier de tâches n'existe pas :", fp)
except ImproperlyConfigured:
    logger.warning("Unable to load custom tasks")


def run_doit(args):
    try:
        sys.exit(DoitMain(task_loader).run(args))
    except Exception as e:
        if settings.DEBUG < logging.WARNING:
            raise e from e
        else:
            logger.error(e)
            sys.exit()


def generate_tasks():
    for name, ref in task_loader.tasks.items():
        if ref.__doc__ is None:
            doc = None
            full_doc = None
        else:
            doc, *rest = ref.__doc__.split("\n", maxsplit=1)
            if rest:
                # Remove {options} section from Sphinx
                rest = re.sub(" *\\{options\\}\n+", "", rest[0])
                full_doc = doc + "\n\n" + textwrap.dedent(rest)
            else:
                full_doc = doc

        task_name = re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", name).lower()

        # Skip non-task classes from loaded in gradebook.py
        if (
            ref is CliArgsInheritMixin
            or ref is ConfigOpt
            or ref is GroupOpt
        ):
            continue

        if issubclass(ref, CliArgsInheritMixin):
            yield (ref, task_name, doc, full_doc, ref(None, None, None).parser)
        elif issubclass(ref, CliArgsMixin):
            yield (
                ref,
                task_name,
                doc,
                full_doc,
                [argument(*arg.args, **arg.kwargs) for arg in ref.cli_args],
            )
        else:
            yield ref, task_name, doc, full_doc, []


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


def get_parser_shtab():
    import shtab

    file_complete = {
        "xls_grade_book_no_group": ['--marking-scheme'],
        "xls_grade_book_group": ['--marking-scheme'],
        "xls_grade_book_jury": ['--config']
    }

    parser = get_parser()
    subparsers = parser._actions[1]
    for task, subparser in subparsers._name_parser_map.items():
        if task in file_complete:
            for action in subparser._actions:
                if set(action.option_strings).intersection(set(file_complete[task])):
                    action.complete = shtab.FILE

    return parser


def get_parser(add_hidden=False):
    """Return an `argparse` parser by iterating on available tasks"""

    parser = argparse.ArgumentParser(prog="guv", description="")
    subparsers = parser.add_subparsers(dest="command")

    createsemester_parser = subparsers.add_parser(
        "createsemester",
        description="Crée un dossier de semestre",
        help="Crée un dossier de semestre",
    )
    createsemester_parser.add_argument("semester")
    createsemester_parser.add_argument("--uv", nargs="*", default=[])

    createuv_parser = subparsers.add_parser(
        "createuv", description="Crée des dossiers d'UV", help="Crée des dossiers d'UV"
    )
    createuv_parser.add_argument("uv", nargs="+")

    sp = subparsers.add_parser(
        "doit",
        description="Permet d'avoir accès aux commandes doit sous-jacentes",
        help="Permet d'avoir accès aux commandes doit sous-jacentes",
    )
    sp.add_argument("args", nargs=argparse.REMAINDER)

    # Sort tasks by task_name
    tasks = list(generate_tasks())
    tasks = sorted(tasks, key=lambda e: e[1])

    for ref, task_name, doc, full_doc, args in tasks:
        # Don't add hidden tasks (completion)
        if not add_hidden and hasattr(ref, "hidden") and ref.hidden:
            continue

        if isinstance(args, argparse.ArgumentParser):
            sp = subparsers.add_parser(
                task_name,
                add_help=False,
                help=doc,
                description=full_doc,
                formatter_class=argparse.RawDescriptionHelpFormatter,
                parents=[args],
            )
        else:
            sp = subparsers.add_parser(
                task_name,
                help=doc,
                description=full_doc,
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            for arg in args:
                sp.add_argument(*arg.args, **arg.kwargs)

    return parser


def main():
    parser = get_parser(add_hidden=True)
    args = parser.parse_args()

    if args.command is None:
        run_doit([])
    elif args.command == "createsemester":
        base_dir = os.path.join(os.getcwd(), args.semester)
        doc_dir = os.path.join(base_dir, "documents")
        gen_dir = os.path.join(base_dir, "generated")
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        try:
            tmpl = jinja_env.get_template(f"semester_config_{args.semester}.py")
        except jinja2.exceptions.TemplateNotFound:
            tmpl = jinja_env.get_template("semester_config.py")

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
    elif args.command == "createuv":
        create_uv_dirs(os.getcwd(), args.uv)
    elif args.command == "doit":
        run_doit(sys.argv[2:])
    else:
        # Run doit without command-line arguments to avoid errors.
        # Doit tasks can handle sys.argv itself
        run_doit(sys.argv[1:2])
