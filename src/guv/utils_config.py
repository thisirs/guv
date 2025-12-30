from collections import defaultdict
import os
import shutil
import time
import zipfile

from .config import settings
from .exceptions import (AbortWithBody, GuvUserError, ImproperlyConfigured,
                         NotUVDirectory)
from .logger import logger
from .translations import _
from .utils import render_latex_template, rel_to_dir_aux
from .latex_compiler import LaTeXCompiler


def rel_to_dir(path, ref_dir=None):
    """Make `path` relative to `root` if inside guv managed directory"""
    if ref_dir is None:
        ref_dir = settings.CWD
    return rel_to_dir_aux(path, ref_dir, settings.SEMESTER_DIR)


def check_filename(filename, errors="raise", **kwargs):
    if errors not in ("raise", "warning", "silent"):
        raise ValueError("invalid error value specified")

    if os.path.exists(filename):
        return True

    fn = rel_to_dir(filename, kwargs["base_dir"])
    msg = _("The file `{fn}` does not exist").format(fn=fn)

    if errors == "raise":
        raise ImproperlyConfigured(msg)
    elif errors == "warning":
        logger.warning(msg)
    elif errors == "silent":
        return False
    else:
        raise ValueError("invalid error value specified")


def configured_uv(uvs):
    # Collect uv to plannings in PLANNINGS
    uv2plannings = defaultdict(list)
    for plng, props in settings.PLANNINGS.items():
        if "UVS" not in props and "UES" not in props:
            raise ImproperlyConfigured(_("The planning `{plng}` does not have a key `UVS` or `UES`.").format(plng=plng))
        for uv in props.get("UVS", []) + props.get("UES", []):
            uv2plannings[uv].append(plng)

    for uv in uvs:
        # Check that all uv are in UVS
        if uv not in settings.UVS:
            raise NotUVDirectory(
                _("The UV `{uv}` is not recognized because it is not registered in the `UVS` variable.").format(uv=uv)
            )

        # Check that UV directory exists
        if not os.path.exists(os.path.join(settings.SEMESTER_DIR, uv)):
            raise ImproperlyConfigured(
                _("The folder for the UV {uv} does not exist.").format(uv=uv)
            )

        if uv not in uv2plannings:
            raise ImproperlyConfigured(_("The UV `{uv}` does not have an associated planning in `PLANNINGS`").format(uv=uv))

        plannings = uv2plannings[uv]
        if len(plannings) > 1:
            raise ImproperlyConfigured(_("The UV `{uv}` has multiple associated plannings in `PLANNINGS`").format(uv=uv))

        yield [plannings[0], uv, {"uv": uv, "planning": plannings[0]}]


def selected_uv():
    """Génère les UV configurées dans le fichier config.py du semestre suivant le dossier courant."""

    if "SEMESTER" not in settings:
        raise NotUVDirectory(_("The task must be executed in a UV/semester folder"))

    if settings.UV_DIR is not None:
        yield get_unique_uv()
        return

    uvs = settings.UVS
    yield from configured_uv(uvs)


def get_unique_uv():
    """Return only one UV if in UV directory."""

    if "UV_DIR" not in settings or settings.UV_DIR is None:
        raise NotUVDirectory(_("The task must be executed in a UV folder"))

    uv = os.path.basename(settings.UV_DIR)
    conf_uvs = configured_uv([uv])

    return list(conf_uvs)[0]


def ask_choice(prompt, choices={}):
    while True:
        try:
            choice = input(prompt)
            if choice not in choices.keys():
                raise ValueError
        except ValueError:
            continue
        else:
            break

    return choices[choice]


class Output:
    def __init__(self, target, protected=False):
        self._target = target
        self.protected = protected
        self.action = None

    def __enter__(self):
        if os.path.exists(self._target):
            if self.protected:
                self.action = ask_choice(
                    _("The file `{fn}` already exists. ").format(fn=rel_to_dir(self._target, settings.SEMESTER_DIR)) + _("Overwrite (d), keep (g), save (s), cancel (a)? "),
                    choices={
                        _("d"): "overwrite",
                        _("g"): "keep",
                        _("s"): "backup",
                        _("a"): "abort",
                    },
                )
            else:
                self.action = "overwrite"
        else:
            self.action = "write"

        return self

    def _prepare(self):
        if self.action == "abort":
            raise GuvUserError(_("Cancellation"))
        if self.action == "keep":
            raise AbortWithBody
        if self.action == "backup":
            parts = os.path.splitext(self._target)
            timestr = time.strftime("_%Y%m%d-%H%M%S")
            target0 = parts[0] + timestr + parts[1]
            os.rename(self._target, target0)
            logger.info(_("Backup to `%s`"), rel_to_dir(target0))
        elif self.action == "overwrite":
            logger.info(_("Overwriting the file `%s`"), rel_to_dir(self._target))
        elif self.action == "write":
            dirname = os.path.dirname(self._target)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            logger.info(_("Writing the file `%s`"), rel_to_dir(self._target))

    @property
    def target(self):
        self._prepare()
        return self._target

    def __exit__(self, type, value, traceback):
        if type is None:
            return
        if type is AbortWithBody:
            return True
        if issubclass(type, GuvUserError):
            return False


def render_from_contexts(template, contexts, save_tex=False, target=None):
    """Render `template` with different `contexts` and save using `target`.

    Rendered in a temporary directory by `render_latex_template`.
    `target` should be a name without extension. A zip of pdf
    extension will be added.

    """
    pdfs = []
    texs = []
    errors = []  # Store all errors encountered

    for context in contexts:
        try:
            tex_filepath = render_latex_template(template, context)
            texs.append(tex_filepath)
        except Exception as e:
            errors.append(GuvUserError(_("Error in creating the .tex file:"), str(e)))
            continue  # Skip PDF generation for this context, but continue with others

        try:
            compiler = LaTeXCompiler(num_runs=2)
            pdf_filepath = compiler.compile(tex_filepath)
            pdfs.append(pdf_filepath)
        except Exception as e:
            errors.append(GuvUserError(_("Error in creating the .pdf file:"), str(e)))
            continue  # Skip PDF for this context, but continue with others

    # Copy successful PDFs
    if len(pdfs) == 1:
        with Output(target + ".pdf") as out:
            shutil.move(pdfs[0], out.target)
    elif len(pdfs) > 1:
        with Output(target + ".zip") as out:
            with zipfile.ZipFile(out.target, "w") as z:
                for filepath in pdfs:
                    z.write(filepath, os.path.basename(filepath))

    # Copy all .tex files if requested
    if save_tex:
        if len(texs) == 1:
            with Output(target + ".tex") as out:
                shutil.move(texs[0], out.target)
        elif len(texs) > 1:
            with Output(target + "_source.zip") as out:
                with zipfile.ZipFile(out.target, "w") as z:
                    for filepath in texs:
                        z.write(filepath, os.path.basename(filepath))

    # Raise all errors at the end if any occurred
    if errors:
        raise errors[0]  # Or combine errors as needed (e.g., raise ExceptionGroup)
