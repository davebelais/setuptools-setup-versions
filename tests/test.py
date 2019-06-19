import os
import sys
from copy import deepcopy
from traceback import print_tb, extract_tb, extract_stack, format_tb, format_exception

from setuptools_setup_versions import version
from sob.errors import get_exception_text
from sob.utilities import qualified_name

from setuptools_setup_versions import install_requires, parse, version, find
from setuptools_setup_versions.parse import SetupScript


def test_find():
    # type: (...) -> None
    assert find.setup_script_path('../').replace('\\', '/') == '../setup.py'
    assert find.setup_script_path('../setup.py').replace('\\', '/') == '../setup.py'


def test_version():
    # type: (...) -> None
    version.increment('../')


def test_install_requires():
    install_requires.update_versions('../', '>=')


if __name__ == '__main__':
    test_find()
    test_version()
    test_install_requires()
