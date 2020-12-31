import functools
import unittest
from typing import Any

from setuptools_setup_versions.requirements import Version

lru_cache: Any = functools.lru_cache


class TestClient(unittest.TestCase):
    """
    TODO
    """

    def test_version(self) -> None:
        print(Version('0.1dev0'))


if __name__ == '__main__':
    unittest.main()
