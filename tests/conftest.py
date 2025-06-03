import re
import shutil
import shlex
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
    def __init__(self, base_dir, request, data, collection_dir):
        self.base_dir = base_dir
        self.cwd = base_dir
        self.request = request
        self.data = data
        self.collection_dir = collection_dir

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)
        return self.data[name]

    def __call__(self, cli_args="", input=None):
        cmdargs = ["guv"] + shlex.split(cli_args)
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

    def create_file(self, dest, content):
        dest = self.cwd / dest
        with open(dest, "w") as f:
            f.write(content)

    def copy_file(self, source, dest):
        """Copy file from data directory to `dest`"""

        source = BASE_DIR / "data" / source
        dest = self.cwd / dest
        shutil.copy(source, dest)

    def check_output_file(self, source):
        assert source.exists()
        shutil.copy(source, self.collection_dir)

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


@pytest.fixture(scope="session")
def guv_data_current(request):
    return {
        "semester": "P2025",
        "uvs": ["SY09", "SY02"],
    }

@pytest.fixture(scope="session")
def collection_dir(tmp_path_factory):
    """Central place to collect all test-created files."""
    return tmp_path_factory.mktemp("collected_test_outputs")


from tests.plugins.test_path import _TestPath


@pytest.fixture(scope="class")
def guv(request, tmp_path_factory, guv_data_current, collection_dir):
    path = _TestPath(request, tmp_path_factory).path
    g = Guv(path, request, guv_data_current, collection_dir)
    g.update_db()
    return g


class Guvcapfd:
    def __init__(self, capfd):
        self.capfd = capfd
        self._outerr = None

    def reset(self):
        self._outerr = None

    @property
    def outerr(self):
        if self._outerr is None:
            out, err = self.capfd.readouterr()
            self._outerr = out + err
        return self._outerr

    def stdout_search(self, *regexes):
        for regex in regexes:
            assert re.search(regex, self.outerr)

    def no_warning(self):
        assert not re.search("Warning:", self.outerr)
        assert not re.search("WARNING", self.outerr)


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
            excel_file = pd.ExcelFile(str(self.file_path))
            if not isinstance(self.sheet_name, str):
                sheet_name = excel_file.sheet_names[int(self.sheet_name)]
                self.sheet_name = sheet_name
            self._df = pd.read_excel(excel_file, sheet_name=self.sheet_name, engine="openpyxl")
        return self._df

    @df.setter
    def df(self, df):
        self._df = df

    def __enter__(self):
        return self

    def contains(self, *cols):
        for col in cols:
            assert col in self.df.columns

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
