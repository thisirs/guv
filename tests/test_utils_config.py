import sys
from unittest import mock
import pytest
import types


@pytest.fixture
def mock_settings():
    mock_settings = types.SimpleNamespace()
    mock_settings.SEMESTER_DIR = "/root/P2025"
    mock_settings.CWD = "/root/P2025"
    return mock_settings


@pytest.fixture(autouse=False)
def patch_guv_config(mock_settings):
    sys.modules.pop("guv.config", None)
    sys.modules.pop("guv.utils_config", None)

    mock_config = mock.Mock(settings=mock_settings)
    with mock.patch.dict(sys.modules, {"guv.config": mock_config}):
        yield

    sys.modules.pop("guv.config", None)
    sys.modules.pop("guv.utils_config", None)


data = (
    ("/root/P2025/config.py", "/root/P2025", "config.py"),
    ("/elsewhere/P2025/config.py", "/root/P2025", "/elsewhere/P2025/config.py"),
)
@pytest.mark.parametrize("path, root, expected", data)
def test_rel_to_dir(patch_guv_config, path, root, expected):
    from guv.utils_config import rel_to_dir

    result = rel_to_dir(path, root)
    assert result == expected
