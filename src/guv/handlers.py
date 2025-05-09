import argparse
import os

import guv
import jinja2

from guv.logger import logger


class CreateSemesterHandler:
    def get_parser(self):
        createsemester_parser = argparse.ArgumentParser(
            prog="guv createsemester",
            description="Crée un dossier de semestre",
        )
        createsemester_parser.add_argument("directory")
        createsemester_parser.add_argument("--uv", nargs="*", default=[])
        createsemester_parser.add_argument("--semester")

        return createsemester_parser

    def run(self, other):
        parser = self.get_parser()
        args = parser.parse_args(other)
        base_dir = os.path.join(os.getcwd(), args.directory)
        doc_dir = os.path.join(base_dir, "documents")
        gen_dir = os.path.join(base_dir, "generated")

        logger.info("Création du dossier %s", os.path.relpath(base_dir, os.getcwd()))
        os.makedirs(base_dir, exist_ok=True)

        logger.info("Création du dossier %s", os.path.relpath(doc_dir, os.getcwd()))
        os.makedirs(doc_dir, exist_ok=True)

        logger.info("Création du dossier %s", os.path.relpath(gen_dir, os.getcwd()))
        os.makedirs(gen_dir, exist_ok=True)

        data_dir = os.path.join(guv.__path__[0], "data")
        context = {
            "UVS": ", ".join(f'"{e}"' for e in args.uv),
            "SEMESTER": args.directory,
        }

        # Get template for config.py from semester_id
        tmpl_dir = os.path.join(data_dir, "templates")
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))
        tmpl = jinja_env.get_template("semester_config.py.jinja2")
        content = tmpl.render(context)
        new_path = os.path.join(base_dir, "config.py")

        logger.info("Création du fichier %s", os.path.relpath(new_path, os.getcwd()))
        if os.path.exists(new_path):
            raise FileExistsError("Le fichier %s existe déjà" % os.path.relpath(new_path, os.getcwd()))
        with open(new_path, "w", encoding="utf-8") as new_file:
            new_file.write(content)

        create_uv_dirs(base_dir, args.uv)
        return 0

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


def run_createuv(args):
    base_dir = os.getcwd()
    create_uv_dirs(base_dir, args.uv)
    return 0


class CreateUvHandler:
    def get_parser(self):
        logger.debug("Run createuv task")
        createuv_parser = argparse.ArgumentParser(
            prog="guv createuv",
            description="Crée des dossiers d'UV"
        )
        createuv_parser.add_argument("uv", nargs="+")

        return createuv_parser

    def run(self, other):
        parser = self.get_parser()
        args = parser.parse_args(other)
        run_createuv(args)
