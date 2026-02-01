"""Test YAML duplicate key detection."""
import tempfile
from pathlib import Path

import pytest
import yaml

from guv.exceptions import GuvUserError
from guv.tasks.base import DuplicateKeysLoader


def test_yaml_duplicate_keys_error():
    """Test that duplicate keys in YAML raise an error."""
    yaml_content = """
key1: value1
key2: value2
key1: value3
"""

    with pytest.raises(GuvUserError) as exc_info:
        yaml.load(yaml_content, Loader=DuplicateKeysLoader)

    assert "Duplicate key 'key1'" in str(exc_info.value)
    assert "line 4" in str(exc_info.value)


def test_yaml_no_duplicate_keys_ok():
    """Test that YAML without duplicate keys loads correctly."""
    yaml_content = """
key1: value1
key2: value2
key3: value3
"""

    result = yaml.load(yaml_content, Loader=DuplicateKeysLoader)
    assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}


def test_yaml_nested_duplicate_keys_error():
    """Test that duplicate keys in nested structures raise an error."""
    yaml_content = """
outer:
  inner1: value1
  inner2: value2
  inner1: value3
"""

    with pytest.raises(GuvUserError) as exc_info:
        yaml.load(yaml_content, Loader=DuplicateKeysLoader)

    assert "Duplicate key 'inner1'" in str(exc_info.value)


def test_yaml_load_all_duplicate_keys():
    """Test that yaml.load_all also detects duplicates."""
    yaml_content = """
---
document: 1
key: value1
---
document: 2
key: value2
key: value3
"""

    with pytest.raises(GuvUserError) as exc_info:
        list(yaml.load_all(yaml_content, Loader=DuplicateKeysLoader))

    assert "Duplicate key 'key'" in str(exc_info.value)
