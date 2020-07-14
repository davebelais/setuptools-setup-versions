import os
import sys
from subprocess import getstatusoutput
from urllib.parse import urljoin

from setuptools_setup_versions import find


def test_setup_script_path() -> None:
    """
    Test finding the setup script for this package
    """
    # Go to the current package's directory
    os.chdir(urljoin(__file__, '../'))
    # Verify the expected results
    assert find.setup_script_path('./').replace('\\', '/') == './setup.py'
    assert find.setup_script_path(
        './setup.py'
    ).replace('\\', '/') == './setup.py'


def test_egg_info() -> None:
    """
    Test finding egg info for this package
    """

    # Go to this package's directory
    os.chdir(urljoin(__file__, '../'))

    # Generate egg-info for this package
    command = '%s ./setup.py egg_info' % sys.executable
    status, output = getstatusoutput(command)

    # Raise an error for a non-zero exit status
    if status:
        raise OSError(output)

    # Verify the expected results
    assert find.egg_info('./') == './setuptools_setup_versions.egg-info'


if __name__ == '__main__':
    test_setup_script_path()
    test_egg_info()
