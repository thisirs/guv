"""Translation and documentation system for guv.

This module provides:
- Gettext-based internationalization (_() function)
- Docstring management for tasks and operations
- Conversion between RST (for Sphinx) and plain text (for argparse)
"""
import re
import textwrap
import argparse
import gettext
import os
from pathlib import Path
from importlib.resources import files


# ============================================================================
# i18n Setup
# ============================================================================

DOMAIN = "guv"
LOCALE_DIR = str(files("guv") / "locale")
LANGUAGE = os.environ.get("LANG", "en_US").split("_")[0]
TEMPLATE_DIR = str(files("guv") / "templates")

translation = gettext.translation(
    domain=DOMAIN, localedir=LOCALE_DIR, languages=[LANGUAGE], fallback=True
)

_ = translation.gettext
ngettext = translation.ngettext


# ============================================================================
# File Loading
# ============================================================================

def load_docstring(locale_dir, lang, filename):
    """Load RST docstring from locale directory with fallback to English.

    Args:
        locale_dir: Base locale directory path
        lang: Language code (e.g., 'en', 'fr')
        filename: RST filename (e.g., 'TaskName.rst')

    Returns:
        RST content as string

    Raises:
        FileNotFoundError: If file not found in both lang and fallback
    """
    base_path = Path(locale_dir) / lang / "texts" / filename
    fallback_path = Path(locale_dir) / "en" / "texts" / filename

    try:
        return base_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback_path.read_text(encoding="utf-8")


def _file(filename):
    """Convenience wrapper to load file from current locale."""
    return load_docstring(LOCALE_DIR, LANGUAGE, filename)


def get_localized_template_directories():
    """Return list of template directories for current locale with fallback."""
    return [
        str(files("guv") / "data" / "templates" / LANGUAGE),
        str(files("guv") / "data" / "templates" / "en")
    ]


# ============================================================================
# CLI Options Formatting
# ============================================================================

def get_parser(objtype):
    """Extract argparse parser from a task or operation class.

    Args:
        objtype: Task or operation class

    Returns:
        argparse.ArgumentParser or None if class has no CLI args
    """
    # Check for doc_flag attribute (older style)
    if hasattr(objtype, "doc_flag"):
        instance = objtype(None, None, None)
        return instance.parser

    # Check for cli_args attribute (newer style)
    if hasattr(objtype, "cli_args"):
        parser = argparse.ArgumentParser(prog="guv", description="")
        for arg in objtype.cli_args:
            parser.add_argument(*arg.args, **arg.kwargs)
        return parser

    return None


def format_cli_options(objtype, format='rst'):
    """Generate formatted CLI options documentation.

    Args:
        objtype: Task or operation class with CLI arguments
        format: 'rst' for Sphinx (with backticks), 'plain' for terminal

    Returns:
        Formatted options string, or empty string if no options
    """
    parser = get_parser(objtype)
    if parser is None:
        return ""

    lines = []
    hf = argparse.HelpFormatter("dummy")

    for action in parser._actions:
        # Get option names (e.g., "-g, --groups GROUPS")
        invocation = hf._format_action_invocation(action)

        # Format option names based on output format
        if format == 'rst':
            invocation = ", ".join(f"``{opt}``" for opt in invocation.split(", "))

        # Get help text
        help_text = hf._expand_help(action)

        # Format as list item with indented continuation
        lines.append("- " + textwrap.indent(f"{invocation} : {help_text}", "  ")[2:])

    if format == 'rst':
        return """
Options
-------

{options}
""".format(options="\n".join(lines))
    else:
        return "\n".join(lines)


# ============================================================================
# RST to Plain Text Conversion
# ============================================================================

def rst_to_plain(rst_text):
    """Convert RST markup to plain text for terminal display.

    Strips common RST elements including:
    - {options} placeholder
    - Backticks (inline code and interpreted text)
    - Directive blocks (.. code::, .. note::, etc.)
    - Section underlines
    - Field lists (:param:, etc.)

    Args:
        rst_text: RST-formatted string

    Returns:
        Plain text with RST markup removed
    """
    text = rst_text

    # Remove {options} placeholder
    text = re.sub(r' *\{options\}\n*', '', text)

    # Remove double backticks (inline code: ``code``)
    text = re.sub(r'``([^`]+)``', r'\1', text)

    # Remove single backticks (interpreted text: `text`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove directive blocks (.. code:: lang, .. note::, etc.)
    text = re.sub(r'\.\. \w+::[^\n]*\n', '', text)

    # Remove section underlines (lines of -, =, ~, etc.)
    text = re.sub(r'\n[-=~^"#*+`]{3,}\n', '\n', text)

    # Remove field list syntax (:param:`name`)
    text = re.sub(r':[\w-]+:`([^`]+)`', r'\1', text)

    # Clean up excessive blank lines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    return text.strip()


# ============================================================================
# Docstring Class
# ============================================================================

class Docstring:
    """Manages documentation for tasks and operations.

    Loads RST docstrings from locale files and provides methods to render
    them in different formats:
    - Sphinx format: RST with {options} replaced by formatted CLI args
    - Plain format: Clean text for argparse, no RST markup, no {options}

    Can be used as a class descriptor or called directly.

    Args:
        class_name: Name of the class (used to find RST file)
        objtype: The class itself (needed to extract CLI args)

    Example as descriptor:
        class MyTask(TaskBase):
            __doc__ = Docstring()

    Example direct usage:
        doc = Docstring('MyTask', MyTask)
        sphinx_doc = doc.as_sphinx()
        plain_doc = doc.as_plain()
    """

    def __init__(self, class_name=None, objtype=None):
        """Initialize docstring manager.

        When used as descriptor, class_name and objtype are set in __get__.
        """
        self._class_name = class_name
        self._objtype = objtype
        self._rst_content = None

    def __get__(self, obj, objtype=None):
        """Descriptor protocol: return Sphinx-formatted docstring.

        When accessed as a class attribute (e.g., MyTask.__doc__), returns
        RST docstring with {options} placeholder replaced.
        """
        if objtype is None:
            return self

        # Create instance configured for this class
        instance = Docstring(objtype.__name__, objtype)
        return instance.as_sphinx()

    def _load_rst(self):
        """Load RST content from file (cached)."""
        if self._rst_content is None:
            if self._class_name is None:
                raise ValueError("class_name must be set before loading")
            self._rst_content = load_docstring(
                LOCALE_DIR, LANGUAGE, f"{self._class_name}.rst"
            )
        return self._rst_content

    def as_sphinx(self):
        """Return Sphinx-formatted documentation (RST with options replaced).

        Returns:
            RST string with {options} placeholder replaced by formatted CLI args
        """
        rst = self._load_rst()

        # Replace {options} placeholder if present
        if "{options}" in rst and self._objtype is not None:
            cli_options = format_cli_options(self._objtype, format='rst')

            # Handle indentation: preserve the indent level of {options}
            def replace_with_indent(match):
                indent = match.group(1)
                return textwrap.indent(cli_options, indent)

            rst = re.sub(r'( *)(\{options\})', replace_with_indent, rst)

        return rst

    def as_plain(self):
        """Return plain text documentation (no RST, no options).

        Returns:
            Clean text suitable for argparse help
        """
        rst = self._load_rst()
        return rst_to_plain(rst)
