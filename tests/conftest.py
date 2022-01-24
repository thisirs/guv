import os
import re
import subprocess
import shutil
from shutil import copytree
from pathlib import Path
import textwrap
import dbm
import pytest
import openpyxl

BASE_DIR = Path(__file__).parent


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "use_tree: mark test to run only on named environment"
    )
    config.addinivalue_line(
        "markers", "cache: mark test to run only on named environment"
    )


class SemesterDir:
    BASE_DIR_SUFFIX = "_base_dir"
    RELATIVE_CWD_SUFFIX = "_relative_cwd"

    # Dictionary of items whose keys are name of tests and whose
    # values are tuples of length 2 of base directory and relative
    # directory.
    tmpdirs = {}

    def __repr__(self):
        return str(self.cwd)

    @property
    def cwd(self):
        """Return current directory."""

        return self.base_dir / self.relative_cwd

    @property
    def cached(self):
        cached = False
        try:
            marks = self.request.function.pytestmark
            for m in marks:
                if m.name == "cache":
                    cached = True
                    break
        except (IndexError, AttributeError):
            pass

        return cached

    @property
    def use_tree_mark(self):
        # Do we have to reuse an existing directory from another test?
        use_tree_mark = None
        try:
            marks = self.request.function.pytestmark
            for m in marks:
                if m.name == "use_tree":
                    use_tree_mark = m
                    break
        except (IndexError, AttributeError):
            pass

        return use_tree_mark

    @property
    def test_name(self):
        """Return name of current test."""

        return self.request.function.__name__

    def cached_base_dir(self, test_name=None):
        """Return base directory from cache or None"""

        base_dir_key = self.base_dir_key(test_name)
        return self.request.config.cache.get(base_dir_key, None)

    def cached_relative_cwd(self, test_name=None):
        """Return relative cwd from cache or None"""

        relative_cwd_key = self.relative_cwd_key(test_name)
        return self.request.config.cache.get(relative_cwd_key, None)

    def mktemp(self, test_name=None):
        """Return a temporary directory for current test."""

        if test_name is None:
            test_name = self.test_name
        return self.tmp_path_factory.mktemp(test_name, numbered=False)

    def __init__(self, request, tmp_path_factory, capfd):
        self.request = request
        self.tmp_path_factory = tmp_path_factory
        self.capfd = capfd

        # If base directory is present in cache and does exist, copy
        # it into new directory to avoid it being cleaned up, update
        # the path in the cache and skip the test.
        if self.cached_base_dir() and Path(self.cached_base_dir).exists():
            new_base_dir = self.mktemp()
            self.copy_tree(self.cached_base_dir(), str(new_base_dir))
            self.base_dir = new_base_dir
            self.relative_cwd = Path(self.cached_relative_cwd())
            self.cache_dir()
            pytest.skip("The test is marked as cached and already run")

        # If current test is reusing the base directory of a previous
        # test
        if self.use_tree_mark is not None:
            # Get the name of that test from the use_tree mark
            func = self.use_tree_mark.args[0]
            if isinstance(func, str):
                base_test_name = func
            else:
                base_test_name = func.__name__

            # Has that base test already been executed in the same session?
            # In that case it is in tmpdirs
            if base_test_name in self.tmpdirs:
                # Copy base directory by default if test if from
                # current session
                copy = self.use_tree_mark.kwargs.get("copy", True)
                if copy:
                    self.base_dir = self.mktemp()
                    base_dir, relative_cwd = self.tmpdirs[base_test_name]
                    self.relative_cwd = relative_cwd
                    self.copy_tree(str(base_dir), str(self.base_dir))
                else:
                    self.base_dir, self.relative_cwd = self.tmpdirs[base_test_name]

                # Register base directory and relative cwd for other
                # tests for current test session
                self.tmpdirs[self.test_name] = self.base_dir, self.relative_cwd

            else:
                # Is that base test cached from a previous session?
                base_dir = self.cached_base_dir(base_test_name)
                relative_cwd = self.cached_relative_cwd(base_test_name)

                if base_dir is not None:
                    # First copy base test to avoid it being cleaned up
                    cache = self.request.config.cache

                    # Has it already been copied from another test
                    # using same base test?
                    try:
                        new_base_dir = self.mktemp(test_name=base_test_name)
                    except FileExistsError:
                        pass
                    else:
                        self.copy_tree(base_dir, str(new_base_dir))
                        cache.set(self.base_dir_key(test_name=base_test_name), str(new_base_dir))
                        cache.set(self.relative_cwd_key(test_name=base_test_name), relative_cwd)
                        base_dir = str(new_base_dir)

                    self.relative_cwd = Path(relative_cwd)
                    # Copy base directory by default if cached
                    copy = self.use_tree_mark.kwargs.get("copy", True)
                    if copy:
                        self.base_dir = self.mktemp()
                        self.copy_tree(base_dir, str(self.base_dir))
                    else:
                        self.base_dir = Path(base_dir)

                    # Register base directory and relative cwd for other
                    # tests for current test session
                    self.tmpdirs[self.test_name] = self.base_dir, self.relative_cwd
                else:
                    raise Exception("On demande le dossier du test ", base_test_name)

        else:
            # No use_tree mark, creating own temp directory and store
            # it for further reference
            self.base_dir = self.mktemp()
            self.relative_cwd = Path(".")
            self.tmpdirs[self.test_name] = (self.base_dir, self.relative_cwd)

    def base_dir_key(self, test_name=None):
        if test_name is None:
            test_name = self.test_name
        return "cache/" + test_name + self.BASE_DIR_SUFFIX

    def relative_cwd_key(self, test_name=None):
        if test_name is None:
            test_name = self.test_name
        return "cache/" + test_name + self.RELATIVE_CWD_SUFFIX

    def run_cli(self, *args):
        cmdargs = ["guv"] + list(args)
        popen = subprocess.Popen(cmdargs, cwd=self.cwd, env=dict(os.environ, DEBUG="1"))
        ret = popen.wait()
        return ret

    def run_func(self, *args):
        os.chdir(str(self.cwd))
        from guv.runner import main

        return main(args)

    def change_relative_cwd(self, *parts):
        self.relative_cwd = Path(*parts)

        # Update self.tmpdirs
        base_dir, _ = self.tmpdirs[self.test_name]
        self.tmpdirs[self.test_name] = (base_dir, self.relative_cwd)

    def cache_dir(self):
        if self.cached:
            cache = self.request.config.cache
            cache.set(self.base_dir_key(), str(self.base_dir))
            cache.set(self.relative_cwd_key(), str(self.relative_cwd))

    def copy_file(self, source, dest):
        """Copy file from data directory to `dest`"""

        source = BASE_DIR / "data" / source
        dest = self.cwd / dest
        shutil.copy(source, dest)

    def write_excel(self, filename, cell, value):
        filepath = self.cwd / filename
        wb = openpyxl.load_workbook(str(filepath))
        ws = wb.worksheets[0]
        ws[cell] = value
        wb.save(str(filepath))

    def change_config(self, *args, **kwargs):
        """Change config.py file in current working directory."""

        config = self.cwd / "config.py"
        with open(config, "a") as f:
            f.write("\n\n")
            for arg in args:
                f.write(textwrap.dedent(arg))
                f.write("\n\n")
            for k, v in kwargs.items():
                if isinstance(v, str):
                    f.write(f"{k}='{v}'\n\n")
                else:
                    f.write(f"{k}={v}\n\n")

    def assert_err_search(self, *regexes):
        err = self.capfd.readouterr().err
        for regex in regexes:
            assert re.search(regex, err)

    def assert_out_search(self, *regexes):
        out = self.capfd.readouterr().out
        for regex in regexes:
            assert re.search(regex, out)

    def copy_tree(self, old, new):
        """Copy whole tree from `old` to `new`.

        Make sure the db file reflects path changes.

        """

        copytree(old, new, dirs_exist_ok=True)
        self.fix_db(Path(new) / "A2020" / ".guv.db", old, new)

    def fix_db(self, db_name, old, new):
        "Update values in database."

        db_path = Path(new, "A2020", db_name)
        if db_path.exists():
            with dbm.open(str(db_path), "w") as db:
                for k in db.keys():
                    old_value = db[k]
                    new_value = old_value.decode().replace(old, new).encode()
                    db[k] = new_value


@pytest.fixture
def semester_dir(request, tmp_path_factory, capfd):
    """Setup a semester file tree in which to run the test."""

    sd = SemesterDir(request, tmp_path_factory, capfd)
    yield sd
    sd.cache_dir()
