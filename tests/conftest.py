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
    """Decorator that add two pytest marks."""

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
        """Return a temporary path that is a copy of the one of another test."""

        path = self.tmp_path_factory.mktemp(self.request.node.name, numbered=False)

        # If not marked with path_dependency decorator, just return a
        # path.
        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            return path

        # Get name of dependency if any
        dep = marker.args[0] if marker.args else None

        cache = marker.kwargs.get("cache", False)

        old_path = self.retrieve_path(self.name)
        if cache and old_path and Path(old_path).exists():
            self.copy_tree(old_path, str(path))
            self.save_path(path)
            raise SkipSuccess("`test_path` is copied")

        if dep is not None:
            dep_path = self.retrieve_path(dep)
            if not dep_path or not Path(dep_path).exists():
                pytest.skip(f"Unable to copy dependent path named {dep} from {dep_path} to {str(path)}")
            self.copy_tree(dep_path, str(path))

        self.save_path(path)
        return path

    def save_path(self, path):
        cache = self.request.config.cache
        cache.set(self.name, str(path))

    def retrieve_path(self, dep):
        cache = self.request.config.cache
        return cache.get(dep, None)

    def copy_tree(self, old, new):
        copytree(old, new, dirs_exist_ok=True)


@pytest.fixture(scope="class")
def test_path(request, tmp_path_factory):
    return _TestPath(request, tmp_path_factory).path


class Guv:
    def __init__(self, base_dir, request):
        self.base_dir = base_dir
        self.cwd = base_dir
        self.request = request

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)
        return self.request.param[name]

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

    def update_db(self):
        """Update absolute paths in guv db when directory if copied by tmp_path."""

        file_path_db = self.base_dir / self.semester / ".guv.db"
        new_part = re.search(r"pytest-\d+/[^/]+", str(file_path_db))[0]
        if file_path_db.exists():
            with dbm.open(str(file_path_db), "w") as db:
                for k in db.keys():
                    old_value = db[k]
                    new_value = re.sub(r"pytest-\d+/[^/]+", new_part, old_value.decode()).encode()
                    db[k] = new_value

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



@pytest.fixture(scope="class", params=[{"semester": "A2020"}])
def guv(test_path, request):
    g = Guv(test_path, request)
    g.update_db()
    return g


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


class Tabular:
    def __init__(self, file_path, sheet_name=0):
        self.file_path = file_path
        self.sheet_name = sheet_name
        self._df = None

    @property
    def df(self):
        if self._df is None:
            self._df = pd.read_excel(
                str(self.file_path), sheet_name=self.sheet_name, engine="openpyxl"
            )
        return self._df

    def __enter__(self):
        return self

    def check_columns(self, *cols):
        assert not set(self.df.columns.values).symmetric_difference(set(cols))

    @property
    def nrow(self):
        return len(self.df)

    @property
    def ncol(self):
        return len(self.df.columns)

    def __exit__(self, type, value, traceback):
        if type is None:
            book = openpyxl.load_workbook(str(self.file_path))
            writer = pd.ExcelWriter(
                str(self.file_path),
                engine="openpyxl",
                mode="a",
                if_sheet_exists="replace",
            )
            writer.book = book
            writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
            self.df.to_excel(writer, sheet_name=self.sheet_name, index=False)
            writer.save()


class Workbook:
    def __init__(self, file_path):
        self.file_path = file_path

    def __enter__(self):
        self.wb = openpyxl.load_workbook(self.file_path)
        return self

    def __exit__(self, type, value, traceback):
        if type is None:
            self.wb.save(str(self.file_path))


@pytest.fixture()
def xlsx():
    class Xlsx:
        @staticmethod
        def tabular(file_path, sheet_name=0):
            return Tabular(file_path, sheet_name=sheet_name)

        @staticmethod
        def workbook(file_path):
            return Workbook(file_path)
    return Xlsx


class Csv:
    def __init__(self, fpath, sep=","):
        self.file_path = fpath
        self.df = pd.read_csv(str(self.file_path), sep=sep)

    def check_columns(self, *cols):
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
