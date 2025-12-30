import subprocess
import tempfile
import pathlib
import shutil


class LaTeXCompileError(RuntimeError):
    pass

class LaTeXCompiler:
    def __init__(
        self,
        engine="lualatex",
        interaction="nonstopmode",
        halt_on_error=True,
        keep_temp_dir=False,
        num_runs=1,
    ):
        self.engine = engine
        self.interaction = interaction
        self.halt_on_error = halt_on_error
        self.keep_temp_dir = keep_temp_dir
        self.num_runs = num_runs

        if shutil.which(self.engine) is None:
            raise FileNotFoundError(
                f"LaTeX engine '{self.engine}' not found in PATH"
            )

    def compile(self, tex_file, output_pdf=None, jobname=None, extra_args=None):
        tex_file = pathlib.Path(tex_file).resolve()

        if not tex_file.exists():
            raise FileNotFoundError(tex_file)

        if jobname is None:
            jobname = tex_file.stem

        if output_pdf is None:
            output_pdf = tex_file.with_suffix(".pdf")
        else:
            output_pdf = pathlib.Path(output_pdf).resolve()

        with tempfile.TemporaryDirectory(prefix="latex-build-") as tmpdir:
            tmpdir = pathlib.Path(tmpdir)

            # Copy source into temp dir
            shutil.copy(tex_file, tmpdir / tex_file.name)

            for run in range(self.num_runs):
                cmd = [
                    self.engine,
                    f"-interaction={self.interaction}",
                    f"-output-directory={tmpdir}",
                    f"-jobname={jobname}",
                ]

                if self.halt_on_error:
                    cmd.append("-halt-on-error")

                if extra_args:
                    cmd.extend(extra_args)

                cmd.append(tex_file.name)

                proc = subprocess.run(
                    cmd,
                    cwd=tmpdir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if proc.returncode != 0:
                    raise LaTeXCompileError(
                        f"{self.engine} failed on run {run + 1}/{self.num_runs}\n\n"
                        f"STDOUT:\n{proc.stdout}\n\n"
                        f"STDERR:\n{proc.stderr}"
                    )

            pdf_path = tmpdir / f"{jobname}.pdf"

            if not pdf_path.exists():
                raise LaTeXCompileError(
                    f"Compilation finished without errors but no PDF was produced after {self.num_runs} runs."
                )

            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf_path, output_pdf)

            if self.keep_temp_dir:
                debug_dir = output_pdf.parent / f"{jobname}_latex_tmp"
                if debug_dir.exists():
                    shutil.rmtree(debug_dir)
                shutil.copytree(tmpdir, debug_dir)

        return output_pdf
