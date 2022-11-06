import re
import shutil
import subprocess
import textwrap
from pathlib import Path
import dbm
import pandas as pd
import openpyxl

import pytest

pytest_plugins = ["tests.plugins.test_path"]

BASE_DIR = Path(__file__).parent


class Guv:
    def __init__(self, base_dir, request, data):
        self.base_dir = base_dir
        self.cwd = base_dir
        self.request = request
        self.data = data

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)
        return self.data[name]

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

        new_dirname = self.base_dir.name
        basename = str(self.base_dir.parent)

        if file_path_db.exists():
            with dbm.open(str(file_path_db), "w") as db:
                for k in db.keys():
                    old_value = db[k]
                    new_value = re.sub(rf"{basename}/[^/]+", basename + "/" + new_dirname, old_value.decode()).encode()
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



@pytest.fixture(
    params=[
        {
            "semester": "A2022",
            "uvs": ["SY19", "SY02"],
            "creneaux_uv": "Creneaux-UV-def-A21.pdf",
        },
        {
            "semester": "P2022",
            "uvs": ["SY09", "SY02"],
            "creneaux_uv": "Creneaux-UV-P22_V02.pdf",
        },
        {
            "semester": "A2021",
            "uvs": ["SY19", "SY02"],
            "creneaux_uv": "Creneaux-UV-def-A21.pdf",
        },
    ],
    scope="session",
)
def guv_data(request):
    return request.param


from tests.plugins.test_path import _TestPath

@pytest.fixture(scope="class")
def my_test_path(request, tmp_path_factory, guv_data):
    return _TestPath(request, tmp_path_factory).path, guv_data


@pytest.fixture(scope="class")
def guv(my_test_path, request):
    foo_test_path, data = my_test_path
    g = Guv(foo_test_path, request, data)
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
            with pd.ExcelWriter(
                self.file_path, mode="a", if_sheet_exists="replace"
            ) as writer:
                self.df.to_excel(writer, sheet_name=self.sheet_name, index=False)


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
    def __init__(self, fpath, sep=",", encoding=None):
        self.file_path = fpath
        self.df = pd.read_csv(str(self.file_path), sep=sep, encoding=encoding)

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
