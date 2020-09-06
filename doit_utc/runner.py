import os
import sys
import inspect
import argparse
import jinja2

from doit.doit_cmd import DoitMain
from doit.cmd_base import NamespaceTaskLoader

import doit_utc


class ModulesTaskLoader(NamespaceTaskLoader):
    def __init__(self, *modules):
        super().__init__()
        self.namespace = {}
        for module in modules:
            self.namespace.update(dict(inspect.getmembers(module)))


def run_doit(args):
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
    modules = [
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
    ]
    sys.exit(DoitMain(ModulesTaskLoader(*modules)).run(args))


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


def main():
    if len(sys.argv) == 1:
        run_doit([])
    elif len(sys.argv) >= 2:
        first_arg = sys.argv[1]
        if first_arg == "doit":
            run_doit(sys.argv[2:])
        elif first_arg in [
                "auto",
                "clean",
                "dumpdb",
                "forget",
                "ignore",
                "info",
                "list",
                "reset-dep",
                "run",
                "strace",
                "help"]:
            run_doit(sys.argv[1:])
        elif first_arg == "tabcompletion":
            # Handle tabcompletion argument specially
            pass
        elif first_arg == "createsemester":
            parser = argparse.ArgumentParser()
            parser.add_argument("createsemester")
            parser.add_argument("semester")
            parser.add_argument("--uv", nargs="*", default=[])
            args = parser.parse_args()
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

        elif first_arg == "createuv":
            parser = argparse.ArgumentParser()
            parser.add_argument("createuv")
            parser.add_argument("uv", nargs="+")
            args = parser.parse_args()
            create_uv_dirs(os.getcwd(), args.uv)
        else:
            # Run doit without command-line arguments to avoid errors.
            # Doit tasks can handle sys.argv itself
            run_doit(sys.argv[1:2])
