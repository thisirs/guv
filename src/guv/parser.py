import argparse
import re
import textwrap

from .tasks.base import CliArgsInheritMixin, CliArgsMixin, ConfigOpt, GroupOpt
from .utils import argument


def generate_tasks(tasks):
    for name, ref in tasks.items():
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


def get_parser(tasks, add_hidden=False):
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
    tasks = list(generate_tasks(tasks))
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
