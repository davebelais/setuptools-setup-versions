import functools
import unittest
from typing import Any
from urllib.parse import urljoin

from setuptools_setup_versions import find, parse
from setuptools_setup_versions.parse import \
    get_package_name_and_version_from_setup

lru_cache: Any = functools.lru_cache


class TestClient(unittest.TestCase):
    """
    TODO
    """

    @property  # type: ignore
    @lru_cache()
    def setup_script_path(self) -> str:
        return find.setup_script_path(urljoin(__file__, '../'))

    @property  # type: ignore
    @lru_cache()
    def setup_script(self) -> parse.SetupScript:
        return parse.SetupScript(self.setup_script_path)

    def test_parse(self) -> None:
        with self.setup_script as setup_script:
            key: str
            value: Any
            print("Setup keyword arguments: {")
            for key, value in setup_script.items():
                print(f'    "key": {repr(value)}')
            print("}")

    def test_get_package_name_and_version_from_setup(self) -> None:
        print(get_package_name_and_version_from_setup(
            self.setup_script_path
        ))


if __name__ == '__main__':
    unittest.main()
