import re
import textwrap
import argparse
import gettext
import os
from pathlib import Path

import guv

DOMAIN = "guv"
LOCALE_DIR = os.path.join(guv.__path__[0], "locale")
LANGUAGE = os.environ.get("LANG", "en_US").split(".")[0]
TEMPLATE_DIR = os.path.join(guv.__path__[0], "templates")

translation = gettext.translation(
    domain=DOMAIN, localedir=LOCALE_DIR, languages=[LANGUAGE], fallback=True
)

_ = translation.gettext
ngettext = translation.ngettext


class Docstring:
    """Descriptor that loads a localized text associated the class of object"""

    def __init__(self, identifier=None):
        self.identifier = identifier

    def __get__(self, obj, objtype=None):
        name = self.identifier or objtype.__name__
        return load_docstring(LOCALE_DIR, LANGUAGE, name + ".rst")


def get_parser(objtype):
    parser = None

    if hasattr(objtype, "doc_flag"):
        instance = objtype(None, None, None)
        parser = instance.parser
    elif hasattr(objtype, "cli_args"):
        parser = argparse.ArgumentParser(prog="guv", description="")
        for arg in objtype.cli_args:
            parser.add_argument(*arg.args, **arg.kwargs)

    return parser

def get_parser_doc(objtype):
    parser = get_parser(objtype)
    if parser is not None:
        docs = []
        hf = argparse.HelpFormatter("dummy")
        for action in parser._actions:
            action_header = hf._format_action_invocation(action)
            action_header = ", ".join(f"``{e}``" for e in action_header.split(", "))
            help_text = hf._expand_help(action)
            docs.append("- " + textwrap.indent(f"{action_header} : {help_text}", "  ")[2:])

        return """
Options
-------

{options}\n""".format(options="\n".join(docs))


class TaskDocstring:
    def __init__(self, replace_options=True):
        self.replace_options = replace_options

    def __get__(self, obj, objtype=None):
        class_name = objtype.__name__

        docstring = load_docstring(LOCALE_DIR, LANGUAGE, class_name + ".rst")
        cli_docstring = get_parser_doc(objtype) if self.replace_options else ""

        if "{options}" in docstring:
            def rep(m):
                indent = m.group(1)
                return textwrap.indent(cli_docstring, indent)

            docstring = re.sub("( *)(\\{options\\})", rep, docstring)

        return docstring


def load_docstring(locale_dir, lang, filename):
    base_path = Path(locale_dir) / lang / "texts" / f"{filename}"
    fallback_path = Path(locale_dir) / "en" / "texts" / f"{filename}"

    try:
        return base_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback_path.read_text(encoding="utf-8")


def _file(filename):
    return load_docstring(LOCALE_DIR, LANGUAGE, filename)


def get_localized_template_directories():
    return [
        os.path.join(guv.__path__[0], "data", "templates", LANGUAGE),
        os.path.join(guv.__path__[0], "data", "templates", "en")
    ]


