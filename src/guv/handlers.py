import importlib.metadata
import argparse
import os

import jinja2

from guv.logger import logger
from .translations import _, get_localized_template_directories


def get_handlers():
    plugin_handlers = []
    for entry_point in importlib.metadata.entry_points(group="guv_handlers"):
        name = entry_point.name
        func = entry_point.load()
        plugin_handlers.append((name, func))

    logger.debug("%s handlers loaded from plugins", len(plugin_handlers))

    core_handlers = {
        "createsemester": CreateSemesterHandler,
        "createuv": CreateUvHandler
    }
    core_handlers.update(plugin_handlers)
    return core_handlers


class CreateSemesterHandler:
    def add_parser(self, subparser=None):
        if subparser is None:
            parser = argparse.ArgumentParser(
                prog="guv createsemester",
                description=_("Create a semester folder"),
            )
        else:
            parser = subparser.add_parser(
                "createsemester",
                description=_("Create a semester folder"),
            )

        parser.add_argument("directory")
        parser.add_argument("--uv", nargs="*", default=[])
        parser.add_argument("--semester")

        if subparser is None:
            return parser
        else:
            return subparser

    def run(self, other):
        parser = self.add_parser()
        args = parser.parse_args(other)
        base_dir = os.path.join(os.getcwd(), args.directory)
        doc_dir = os.path.join(base_dir, "documents")
        gen_dir = os.path.join(base_dir, "generated")

        logger.info(_("Creating folder %s"), os.path.relpath(base_dir, os.getcwd()))
        os.makedirs(base_dir, exist_ok=True)

        logger.info(_("Creating folder %s"), os.path.relpath(doc_dir, os.getcwd()))
        os.makedirs(doc_dir, exist_ok=True)

        logger.info(_("Creating folder %s"), os.path.relpath(gen_dir, os.getcwd()))
        os.makedirs(gen_dir, exist_ok=True)

        context = {
            "UVS": ", ".join(f'"{e}"' for e in args.uv),
            "SEMESTER": args.directory,
        }

        # Get template for config.py from semester_id
        tmpl_dirs = get_localized_template_directories()
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dirs))
        tmpl = jinja_env.get_template("semester_config.py.jinja2")
        content = tmpl.render(context)
        new_path = os.path.join(base_dir, "config.py")

        logger.info(_("Creating file %s"), os.path.relpath(new_path, os.getcwd()))
        if os.path.exists(new_path):
            raise FileExistsError(_("The file %s already exists") % os.path.relpath(new_path, os.getcwd()))
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)

        create_uv_dirs(base_dir, args.uv)
        return 0

def create_uv_dirs(base_dir, uvs):
    for uv in uvs:
        uv_dir = os.path.join(base_dir, uv)
        doc_dir = os.path.join(uv_dir, "documents")
        gen_dir = os.path.join(uv_dir, "generated")

        logger.info(_("Creating folder %s"), os.path.relpath(uv_dir, os.getcwd()))
        os.makedirs(uv_dir, exist_ok=True)

        logger.info(_("Creating folder %s"), os.path.relpath(doc_dir, os.getcwd()))
        os.makedirs(doc_dir, exist_ok=True)

        logger.info(_("Creating folder %s"), os.path.relpath(gen_dir, os.getcwd()))
        os.makedirs(gen_dir, exist_ok=True)

        tmpl_dirs = get_localized_template_directories()
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dirs))
        tmpl = jinja_env.get_template("uv_config.py")

        context = {}
        content = tmpl.render(context)
        new_path = os.path.join(uv_dir, "config.py")

        logger.info(_("Creating file %s"), os.path.relpath(new_path, os.getcwd()))
        if os.path.exists(new_path):
            raise FileExistsError(_("The file `%s` already exists") % os.path.relpath(new_path, os.getcwd()))
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)


def run_createuv(args):
    base_dir = os.getcwd()
    create_uv_dirs(base_dir, args.uv)
    return 0


class CreateUvHandler:
    def add_parser(self, subparser=None):
        if subparser is None:
            parser = argparse.ArgumentParser(
                prog="guv createuv",
            description=_("Create UV folders")
            )
        else:
            parser = subparser.add_parser(
                "createuv",
            description=_("Create UV folders")
            )

        parser.add_argument("uv", nargs="+")

        if subparser is None:
            return parser
        else:
            return subparser

    def run(self, other):
        parser = self.add_parser()
        args = parser.parse_args(other)
        run_createuv(args)
