import os
import sys
import re
import inspect
import argparse
import jinja2

from doit.doit_cmd import DoitMain
from doit.cmd_base import NamespaceTaskLoader
import doit_utc

from .tasks import TaskBase, UVTask, CliArgsMixin
from .utils import argument

# Load settings from configuration files
from .config import semester_settings
from .config import uv_settings

from . import dodo_instructors
from . import dodo_utc
from . import dodo_grades
from . import dodo_students
from . import dodo_trombinoscope
from . import dodo_moodle
from . import dodo_ical
from . import dodo_calendar
from . import dodo_attendance


class ModulesTaskLoader(NamespaceTaskLoader):
    def __init__(self, *modules):
        super().__init__()
        self.namespace = {}
        for module in modules:
            self.namespace.update(dict(inspect.getmembers(module)))


task_loader = ModulesTaskLoader(
    semester_settings,
    uv_settings,
    dodo_instructors,
    dodo_utc,
    dodo_grades,
    dodo_students,
    dodo_trombinoscope,
    dodo_moodle,
    dodo_ical,
    dodo_calendar,
    dodo_attendance,
)


def run_doit(args):
    sys.exit(DoitMain(task_loader).run(args))


def generate_tasks():
    namespace = {
        k: v
        for k, v in task_loader.namespace.items()
        if inspect.isclass(v) and issubclass(v, TaskBase)
    }

    for name, ref in namespace.items():
        if ref in [TaskBase, UVTask, CliArgsMixin]:
            continue

        if ref.__doc__ is None:
            doc = ""
        else:
            # First line
            doc = ref.__doc__.split("\n")[0]

        task_name = re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", name).lower()

        if issubclass(ref, CliArgsMixin):
            yield (
                task_name,
                doc,
                [argument(*arg.args, **arg.kwargs) for arg in ref.cli_args],
            )
        else:
            yield task_name, doc, []


def create_uv_dirs(base_dir, uvs):
    for uv in uvs:
        uv_dir = os.path.join(base_dir, uv)
        doc_dir = os.path.join(uv_dir, "documents")
        gen_dir = os.path.join(uv_dir, "generated")
        os.makedirs(uv_dir, exist_ok=True)
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dir = os.path.join(doit_utc.__path__[0], 'templates')
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")
        with open(new_path, 'w', encoding='utf-8') as new_file:
            new_file.write(content)


def createsemester_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("createsemester")
    parser.add_argument("semester")
    parser.add_argument("--uv", nargs="*", default=[])
    return parser


def createuv_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("createuv")
    parser.add_argument("uv", nargs="+")
    return parser


def main():
    parser = argparse.ArgumentParser(prog="doit-utc", description="")
    subparsers = parser.add_subparsers(dest="command")

    createsemester_parser = subparsers.add_parser(
        "createsemester", help="Crée un dossier de semestre"
    )
    createsemester_parser.add_argument("semester")
    createsemester_parser.add_argument("--uv", nargs="*", default=[])

    createuv_parser = subparsers.add_parser(
        "createuv",
        help="Crée des dossiers d'UV"
    )
    createuv_parser.add_argument("createuv")
    createuv_parser.add_argument("uv", nargs="+")

    subparsers.add_parser(
        "tabcompletion",
        help="Écrit un fichier d'autocomplétion pour zsh"
    )

    subparsers.add_parser(
        "doit",
        help="Permet d'avoir accès aux commandes doit sous-jacentes"
    )

    for task_name, doc, args in generate_tasks():
        sp = subparsers.add_parser(task_name, help=doc)
        for arg in args:
            sp.add_argument(*arg.args, **arg.kwargs)

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

        tmpl_dir = os.path.join(doit_utc.__path__[0], 'templates')
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("semester_config.py")

        context = {"UVS": ", ".join(f'"{e}"' for e in args.uv)}
        content = tmpl.render(context)
        new_path = os.path.join(base_dir, "config.py")
        with open(new_path, 'w', encoding='utf-8') as new_file:
            new_file.write(content)

        create_uv_dirs(base_dir, args.uv)
    elif args.command == "createuv":
        create_uv_dirs(os.getcwd(), args.uv)
    elif args.command == "tabcompletion":
        from .zargparse import fake_parse_args
        fake_parse_args(parser)
    elif args.command == "doit":
        run_doit(sys.argv[2:])
    else:
        # Run doit without command-line arguments to avoid errors.
        # Doit tasks can handle sys.argv itself
        run_doit(sys.argv[1:2])
