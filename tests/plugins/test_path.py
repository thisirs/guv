import re
import pytest
from pathlib import Path
from shutil import copytree
import logging


logger = logging.getLogger(__name__)


class SkipSuccess(Exception):
    pass


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "path_dependency(dep=None, cache=False): mark test to run only on named environment",
    )

    config.option.order_dependencies = True


def path_dependency(dep=None, /, cache=False, name=None, propagate_suffix=False):
    """Mark that current test will reuse a path from another test."""

    def make_decorator(dep, cache):
        def decorator(func):
            depends = None if dep is None else [dep]
            name2 = name or func.__name__
            marker1 = pytest.mark.dependency(
                name=name2, depends=depends, scope="session"
            )
            marker2 = pytest.mark.path_dependency(dep, cache=cache, name=name2, propagate_suffix=propagate_suffix)
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

        logger.debug("Compute a path for node %s ...", self.request.node)

        # Path to use
        path = self.tmp_path_factory.mktemp(self.request._pyfuncitem.name, numbered=False)

        # If not marked with path_dependency decorator, just return a
        # path.
        marker = self.request.node.get_closest_marker("path_dependency")
        if marker is None:
            logger.debug("... no `path_dependency` marker, returning new path `%s`", path)
            return path

        # Get name of dependency if any from `path_dependency` marker.
        # Add corresponding suffix if test is parametrized
        if marker.args and marker.args[0]:
            if marker.kwargs.get("propagate_suffix", False):
                dep = marker.args[0] + self.suffix
            else:
                dep = marker.args[0]
            logger.debug("... dependence to test named %s", dep)
        else:
            logger.debug("... no dependence")
            dep = None

        cache = marker.kwargs.get("cache", False)

        old_path = self.retrieve_path(self.name)
        if cache and old_path and Path(old_path).exists():
            logger.debug(f"... found {self.name} in cache")
            self.copy_tree(old_path, str(path))
            self.save_path(path)
            logger.debug("... copy %s to %s and update cache", old_path, str(path))

            raise SkipSuccess("`test_path` is copied")

        if dep is not None:
            dep_path = self.retrieve_path(dep)
            logger.debug("... retrieve %s path associated to dependency %s", dep_path, dep)
            if not dep_path or not Path(dep_path).exists():
                pytest.skip(f"Unable to copy dependent path named {dep} from {dep_path} to {str(path)}")
            self.copy_tree(dep_path, str(path))
            logger.debug("... copy %s to %s and update cache", dep_path, str(path))

        self.save_path(path)
        logger.debug("... save association: %s -> %s", self.name, str(path))
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
