import re
import functools
import shutil
import subprocess
import textwrap
from pathlib import Path
from shutil import copytree
from io import StringIO
import dbm
import pandas as pd

import pytest


BASE_DIR = Path(__file__).parent


class SkipSuccess(Exception):
    pass


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "path_dependency(dep=None, cache=False): mark test to run only on named environment",
    )

    config.option.order_dependencies = True


def path_dependency(dep=None, /, cache=False, name=None):
    def make_decorator(dep, cache):
        def decorator(func):
            depends = None if dep is None else [dep]
            name2 = name or func.__name__
            marker1 = pytest.mark.dependency(
                name=name2, depends=depends, scope="session"
            )
            marker2 = pytest.mark.path_dependency(dep, cache=cache, name=name2)
            return marker1(marker2(func))

        return decorator

    if callable(dep):
        return make_decorator(None, False)(dep)
    else:
        return make_decorator(dep, cache=cache)


class _TestPath:
    def __init__(self, request, tmp_path_factory):
        self.request = request
        self.tmp_path_factory = tmp_path_factory

    @property
    def name(self):
        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            return None

        return marker.kwargs.get("name", None)

    @property
    def path(self):
        path = self.tmp_path_factory.mktemp(self.request.node.name, numbered=False)

        # If not marked with path_dependency decorator, just return a
        # path.
        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            return path

        # Get name of dependency if any
        dep = marker.args[0] if marker.args else None

        cache = marker.kwargs.get("cache", False)

        print(f"Name of test is {self.name}")

        old_path = self.retrieve_path(self.name)
        if cache and old_path and Path(old_path).exists():
            self.copy_tree(old_path, str(path))
            self.save_path(path)
            raise SkipSuccess("`test_path` is copied")

        if dep is not None:
            dep_path = self.retrieve_path(dep)
            print(dep_path, dep)
            if not dep_path or not Path(dep_path).exists():
                pytest.skip(f"Unable to copy dependent path named {dep} from {dep_path} to {str(path)}")
            self.copy_tree(dep_path, str(path))

        self.save_path(path)
        return path

    def save_path(self, path):
        print(f"Saving {str(path)} at key {self.name}")
        cache = self.request.config.cache
        cache.set(self.name, str(path))

    def retrieve_path(self, dep):
        cache = self.request.config.cache
        return cache.get(dep, None)

    def copy_tree(self, old, new):
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


@pytest.fixture(scope="class")
def test_path(request, tmp_path_factory):
    return _TestPath(request, tmp_path_factory).path


class Guv:
    def __init__(self, base_dir, request):
        self.base_dir = base_dir
        self.cwd = base_dir
        self.request = request

    def __call__(self, cli_args="", input=None):
        cmdargs = ["guv"] + cli_args.split()
        p = subprocess.run(cmdargs, cwd=self.cwd, input=input, encoding="utf-8")
        ret = p.returncode

        class Result:
            def succeed(self):
                assert ret == 0

            def failed(self):
                assert ret != 0

        return Result()

    def store(self, **kwargs):
        cache = self.request.config.cache
        for key, value in kwargs.items():
            cache.set(self.request.node.name + key, key)

    def retrieve(self, key):
        cache = self.request.config.cache
        return cache.get(key)

    def copy_file(self, source, dest):
        """Copy file from data directory to `dest`"""

        source = BASE_DIR / "data" / source
        dest = self.cwd / dest
        shutil.copy(source, dest)

    def cd(self, *path):
        self.cwd = self.base_dir / Path(*path)

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



@pytest.fixture(scope="class")
def guv(test_path, request):
    return Guv(test_path, request)


class Guvcapfd():
    def __init__(self, capfd):
        self.capfd = capfd

    def stdout_search(self, *regexes):
        out = self.capfd.readouterr().out
        for regex in regexes:
            assert re.search(regex, out)

@pytest.fixture(scope="function")
def guvcapfd(capfd):
    return Guvcapfd(capfd)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    outcome = yield

    if outcome.excinfo is not None and isinstance(outcome.excinfo[1], SkipSuccess):
        item.blah = True
    else:
        item.blah = False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if item.blah:
        raise SkipSuccess("foobra")
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if item.blah:
        rep.outcome = "passed"


class Xlsx:
    def __init__(self, fpath):
        self.file_path = fpath
        self.df = pd.read_excel(str(self.file_path))

    def columns(self, *cols):
        assert not set(self.df.columns.values).symmetric_difference(set(cols))

    @property
    def nrow(self):
        return len(self.df)

    @property
    def ncol(self):
        return len(self.columns)


@pytest.fixture()
def xlsx():
    return Xlsx

class Csv:
    def __init__(self, fpath, sep=","):
        self.file_path = fpath
        self.df = pd.read_csv(str(self.file_path), sep=sep)

    def columns(self, *cols):
        assert not set(self.df.columns.values).symmetric_difference(set(cols))

    @property
    def nrow(self):
        return len(self.df)

    @property
    def ncol(self):
        return len(self.columns)


@pytest.fixture()
def csv():
    return Csv



# class SemesterDir:
#     BASE_DIR_SUFFIX = "_base_dir"
#     RELATIVE_CWD_SUFFIX = "_relative_cwd"

#     # Dictionary of items whose keys are name of tests and whose
#     # values are tuples of length 2 of base directory and relative
#     # directory.
#     tmpdirs = {}

#     def __repr__(self):
#         return str(self.cwd)

#     @property
#     def cwd(self):
#         """Return current directory."""

#         return self.base_dir / self.relative_cwd

#     @property
#     def cached(self):
#         cached = False
#         try:
#             marks = self.request.function.pytestmark
#             for m in marks:
#                 if m.name == "cache":
#                     cached = True
#                     break
#         except (IndexError, AttributeError):
#             pass

#         return cached

#     @property
#     def use_tree_mark(self):
#         # Do we have to reuse an existing directory from another test?
#         use_tree_mark = None
#         try:
#             marks = self.request.function.pytestmark
#             for m in marks:
#                 if m.name == "use_tree":
#                     use_tree_mark = m
#                     break
#         except (IndexError, AttributeError):
#             pass

#         return use_tree_mark

#     @property
#     def test_name(self):
#         """Return name of current test."""

#         return self.request.function.__name__

#     def cached_base_dir(self, test_name=None):
#         """Return base directory from cache or None"""

#         base_dir_key = self.base_dir_key(test_name)
#         return self.request.config.cache.get(base_dir_key, None)

#     def cached_relative_cwd(self, test_name=None):
#         """Return relative cwd from cache or None"""

#         relative_cwd_key = self.relative_cwd_key(test_name)
#         return self.request.config.cache.get(relative_cwd_key, None)

#     def mktemp(self, test_name=None):
#         """Return a temporary directory for current test."""

#         if test_name is None:
#             test_name = self.test_name
#         return self.tmp_path_factory.mktemp(test_name, numbered=False)

#     def __init__(self, request, tmp_path_factory, capfd):
#         self.request = request
#         self.tmp_path_factory = tmp_path_factory
#         self.capfd = capfd

#         # If base directory is present in cache and does exist, copy
#         # it into new directory to avoid it being cleaned up, update
#         # the path in the cache and skip the test.
#         if self.cached_base_dir() and Path(self.cached_base_dir()).exists():
#             new_base_dir = self.mktemp()
#             self.copy_tree(self.cached_base_dir(), str(new_base_dir))
#             self.base_dir = new_base_dir
#             self.relative_cwd = Path(self.cached_relative_cwd())
#             self.cache_dir()
#             pytest.skip("The test is marked as cached and already run")

#         # If current test is reusing the base directory of a previous
#         # test
#         if self.use_tree_mark is not None:
#             # Get the name of that test from the use_tree mark
#             func = self.use_tree_mark.args[0]
#             if isinstance(func, str):
#                 base_test_name = func
#             else:
#                 base_test_name = func.__name__

#             # Has that base test already been executed in the same session?
#             # In that case it is in tmpdirs
#             if base_test_name in self.tmpdirs:
#                 # Copy base directory by default if test if from
#                 # current session
#                 copy = self.use_tree_mark.kwargs.get("copy", True)
#                 if copy:
#                     self.base_dir = self.mktemp()
#                     base_dir, relative_cwd = self.tmpdirs[base_test_name]
#                     self.relative_cwd = relative_cwd
#                     self.copy_tree(str(base_dir), str(self.base_dir))
#                 else:
#                     self.base_dir, self.relative_cwd = self.tmpdirs[base_test_name]

#                 # Register base directory and relative cwd for other
#                 # tests for current test session
#                 self.tmpdirs[self.test_name] = self.base_dir, self.relative_cwd

#             else:
#                 # Is that base test cached from a previous session?
#                 base_dir = self.cached_base_dir(base_test_name)
#                 relative_cwd = self.cached_relative_cwd(base_test_name)

#                 if base_dir is not None:
#                     # First copy base test to avoid it being cleaned up
#                     cache = self.request.config.cache

#                     # Has it already been copied from another test
#                     # using same base test?
#                     try:
#                         new_base_dir = self.mktemp(test_name=base_test_name)
#                     except FileExistsError:
#                         pass
#                     else:
#                         self.copy_tree(base_dir, str(new_base_dir))
#                         cache.set(self.base_dir_key(test_name=base_test_name), str(new_base_dir))
#                         cache.set(self.relative_cwd_key(test_name=base_test_name), relative_cwd)
#                         base_dir = str(new_base_dir)

#                     self.relative_cwd = Path(relative_cwd)
#                     # Copy base directory by default if cached
#                     copy = self.use_tree_mark.kwargs.get("copy", True)
#                     if copy:
#                         self.base_dir = self.mktemp()
#                         self.copy_tree(base_dir, str(self.base_dir))
#                     else:
#                         self.base_dir = Path(base_dir)

#                     # Register base directory and relative cwd for other
#                     # tests for current test session
#                     self.tmpdirs[self.test_name] = self.base_dir, self.relative_cwd
#                 else:
#                     raise Exception("On demande le dossier du test ", base_test_name)

#         else:
#             # No use_tree mark, creating own temp directory and store
#             # it for further reference
#             self.base_dir = self.mktemp()
#             self.relative_cwd = Path(".")
#             self.tmpdirs[self.test_name] = (self.base_dir, self.relative_cwd)

#     def base_dir_key(self, test_name=None):
#         if test_name is None:
#             test_name = self.test_name
#         return "cache/" + test_name + self.BASE_DIR_SUFFIX

#     def relative_cwd_key(self, test_name=None):
#         if test_name is None:
#             test_name = self.test_name
#         return "cache/" + test_name + self.RELATIVE_CWD_SUFFIX

#     def run_cli(self, cli_args):
#         cmdargs = ["guv"] + cli_args.split()
#         popen = subprocess.Popen(cmdargs, cwd=self.cwd, env=dict(os.environ, DEBUG="1"))
#         ret = popen.wait()
#         return ret

#     def run_func(self, *args):
#         os.chdir(str(self.cwd))
#         from guv.runner import main

#         return main(args)

#     def change_relative_cwd(self, *parts):
#         self.relative_cwd = Path(*parts)

#         # Update self.tmpdirs
#         base_dir, _ = self.tmpdirs[self.test_name]
#         self.tmpdirs[self.test_name] = (base_dir, self.relative_cwd)

#     def cache_dir(self):
#         if self.cached:
#             cache = self.request.config.cache
#             cache.set(self.base_dir_key(), str(self.base_dir))
#             cache.set(self.relative_cwd_key(), str(self.relative_cwd))

#     def copy_file(self, source, dest):
#         """Copy file from data directory to `dest`"""

#         source = BASE_DIR / "data" / source
#         dest = self.cwd / dest
#         shutil.copy(source, dest)

#     def write_excel(self, filename, cell, value):
#         filepath = self.cwd / filename
#         wb = openpyxl.load_workbook(str(filepath))
#         ws = wb.worksheets[0]
#         ws[cell] = value
#         wb.save(str(filepath))

#     def change_config(self, *args, **kwargs):
#         """Change config.py file in current working directory."""

#         config = self.cwd / "config.py"
#         with open(config, "a") as f:
#             f.write("\n\n")
#             for arg in args:
#                 f.write(textwrap.dedent(arg))
#                 f.write("\n\n")
#             for k, v in kwargs.items():
#                 if isinstance(v, str):
#                     f.write(f"{k}='{v}'\n\n")
#                 else:
#                     f.write(f"{k}={v}\n\n")

#     def assert_err_search(self, *regexes):
#         err = self.capfd.readouterr().err
#         for regex in regexes:
#             assert re.search(regex, err)

#     def assert_out_search(self, *regexes):
#         out = self.capfd.readouterr().out
#         for regex in regexes:
#             assert re.search(regex, out)

#     def copy_tree(self, old, new):
#         """Copy whole tree from `old` to `new`.

#         Make sure the db file reflects path changes.

#         """

#         copytree(old, new, dirs_exist_ok=True)
#         self.fix_db(Path(new) / "A2020" / ".guv.db", old, new)

#     def fix_db(self, db_name, old, new):
#         "Update values in database."

#         db_path = Path(new, "A2020", db_name)
#         if db_path.exists():
#             with dbm.open(str(db_path), "w") as db:
#                 for k in db.keys():
#                     old_value = db[k]
#                     new_value = old_value.decode().replace(old, new).encode()
#                     db[k] = new_value


# @pytest.fixture
# def semester_dir(request, tmp_path_factory, capfd):
#     """Setup a semester file tree in which to run the test."""

#     sd = SemesterDir(request, tmp_path_factory, capfd)
#     yield sd
#     sd.cache_dir()
