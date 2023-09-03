import re
import pytest
from pathlib import Path
from shutil import copytree


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
    def suffix(self):
        name = self.request._pyfuncitem.name
        return re.search(r"(\[[^]]+\])?$", name)[0]

    @property
    def name(self):
        """Return identifier of current node.

        Use `name` defined in `path_dependency`
        """

        # Get name of item at function scope level
        name = self.request._pyfuncitem.name


        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            return name

        name2 = marker.kwargs.get("name", None)
        if name2 is None:
            return name
        else:
            return name2 + self.suffix

    @property
    def path(self):
        """Return a temporary path that is a copy of the one of another test."""

        # Path to use
        path = self.tmp_path_factory.mktemp(self.request._pyfuncitem.name, numbered=False)

        # If not marked with path_dependency decorator, just return a
        # path.
        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            return path

        # Get name of dependency if any from `path_dependency` marker.
        # Add corresponding suffix if test is parametrized
        if marker.args and marker.args[0]:
            dep = marker.args[0] + self.suffix
        else:
            dep = None

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
        raise SkipSuccess
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if item.blah:
        rep.outcome = "passed"
