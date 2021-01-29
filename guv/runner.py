import os
import sys
import re
import inspect
import argparse
import jinja2
import textwrap

from doit.doit_cmd import DoitMain
from doit.cmd_base import NamespaceTaskLoader
import guv

from .exceptions import ImproperlyConfigured
from .tasks import TaskBase, UVTask, CliArgsMixin
from .utils import argument

# Load settings from configuration files
from .config import settings
from . import dodo_instructors
from . import dodo_utc
from . import dodo_grades
from . import dodo_students
from . import dodo_trombinoscope
from . import dodo_moodle
from . import dodo_ical
from . import dodo_calendar
from . import dodo_attendance

from .dodo_grades import XlsGradeSheet


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
            self.tasks.update(dict(m))
            self.namespace.update(dict(m))

    def _load_variables(self, dictionary):
        self.variables.update(dictionary)
        self.namespace.update(dictionary)


# On force le chargement des variables dans settings pour qu'elle
# figure dans le task_loader. Si aucun fichier de configuration n'est
# trouvé, on continue
try:
    settings.setup()
except ImproperlyConfigured:
    pass

task_loader = ModulesTaskLoader()
task_loader._load_variables(settings.settings)
task_loader._load_tasks(
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
    # On force le rechargement des variables pour déclencher une
    # exception si aucun fichier de configuration n'est trouvé
    settings.setup()
    sys.exit(DoitMain(task_loader).run(args))


def generate_tasks():
    for name, ref in task_loader.tasks.items():
        if ref.__doc__ is None:
            doc = None
            full_doc = None
        else:
            doc, *rest = ref.__doc__.split("\n", maxsplit=1)
            if rest:
                full_doc = doc + "\n\n" + textwrap.dedent(rest[0])
            else:
                full_doc = doc

        task_name = re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", name).lower()

        if issubclass(ref, CliArgsMixin):
            yield (
                task_name,
                doc,
                full_doc,
                [argument(*arg.args, **arg.kwargs) for arg in ref.cli_args],
            )
        elif ref is XlsGradeSheet:
            yield (
                task_name,
                doc,
                full_doc,
                [argument("args", nargs=argparse.REMAINDER)]
            )
        else:
            yield task_name, doc, full_doc, []


def create_uv_dirs(base_dir, uvs):
    for uv in uvs:
        uv_dir = os.path.join(base_dir, uv)
        doc_dir = os.path.join(uv_dir, "documents")
        gen_dir = os.path.join(uv_dir, "generated")
        os.makedirs(uv_dir, exist_ok=True)
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dir = os.path.join(guv.__path__[0], 'templates')
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")
        if os.path.exists(new_path):
            raise Exception("File config.py already exists")
        with open(new_path, 'w', encoding='utf-8') as new_file:
            new_file.write(content)

def get_parser():
    parser = argparse.ArgumentParser(prog="guv", description="")
    subparsers = parser.add_subparsers(dest="command")

    createsemester_parser = subparsers.add_parser(
        "createsemester", description="Crée un dossier de semestre"
    )
    createsemester_parser.add_argument("semester")
    createsemester_parser.add_argument("--uv", nargs="*", default=[])

    createuv_parser = subparsers.add_parser(
        "createuv",
        description="Crée des dossiers d'UV"
    )
    createuv_parser.add_argument("uv", nargs="+")

    subparsers.add_parser(
        "tabcompletion",
        description="Écrit un fichier d'autocomplétion pour zsh",
    )

    sp = subparsers.add_parser(
        "doit",
        description="Permet d'avoir accès aux commandes doit sous-jacentes"
    )
    sp.add_argument("args", nargs=argparse.REMAINDER)

    for task_name, doc, full_doc, args in generate_tasks():
        sp = subparsers.add_parser(task_name, help=doc, description=full_doc, formatter_class=argparse.RawDescriptionHelpFormatter)
        for arg in args:
            sp.add_argument(*arg.args, **arg.kwargs)

    return parser


def main():
    parser = get_parser()
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

        tmpl_dir = os.path.join(guv.__path__[0], 'templates')
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("semester_config.py")

        context = {
            "UVS": ", ".join(f'"{e}"' for e in args.uv),
            "SEMESTER": args.semester
        }
        content = tmpl.render(context)
        new_path = os.path.join(base_dir, "config.py")
        if os.path.exists(new_path):
            raise Exception("File config.py already exists")
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
