import os
from enum import Enum
from urllib.parse import urljoin

try:
    from typing import Tuple, Iterable, Sequence, Set
except ImportError:
    Tuple = Iterable = Sequence = Set = None


from setuptools_setup_versions import requirements


class SetupScriptComponents(Enum):

    # This indicates a shebang should be included
    SHEBANG = 0

    # This indicates a docstring should be included
    DOCSTRING = 1

    # This indicates more than one calls to `setuptools.setup` should be made
    MULTIPLE_SETUP_CALLS = 2

    # This indicates there should be some additional code prior to calling
    # `setup`
    PRE_SETUP_CODE = 3

    # This indicates the entire `setuptools` module will be imported instead of
    # just `setup` from that module
    IMPORT_SETUPTOOLS_MODULE = 4

    # This indicates that packages without any *.egg-info should be referenced
    INCLUDE_PACKAGES_WITHOUT_EGG_INFO = 5


def generate_setup_call(
    packages,               # type: Sequence[str]
    dev_packages=tuple(),   # type: Sequence[str]
    test_packages=tuple(),  # type: Sequence[str]
    qualified_name=False    # type: bool
):
    # type: (...) -> str
    """
    Generate a call to `setuptools.setup`, and include the
    """
    pass


def create_setup_script(
    elements,               # type: Set[int]
    packages,               # type: Sequence[str]
    dev_packages=tuple(),   # type: Sequence[str]
    test_packages=tuple()   # type: Sequence[str]
):
    # type: (...) -> Tuple[str, str]
    """
    Build a setup script
    """

    lines = []

    if SetupScriptComponents.SHEBANG in elements:
        lines.append(
            '#!/usr/bin/python\n\n'
        )

    if SetupScriptComponents.DOCSTRING in elements:
        lines.append(
            '"""\n'
            'This is a test.\n'
            'This is only a test.\n'
            '"""\n\n'
        )

    if SetupScriptComponents.IMPORT_SETUPTOOLS_MODULE in elements:
        lines.append('import setuptools\n\n')
    else:
        lines.append('from setuptools import setup\n\n')

    if SetupScriptComponents.PRE_SETUP_CODE in elements:
        lines.append(
            'if sys.version_info < (2, 7):\n'
            '    raise RuntimeError(\n'
            "        'Python versions previous to 2.7 are not supported'\n"
            '    )\n\n'
        )


def create_setup_scripts():
    # type: (...) -> Iterable[Tuple[str, str]]
    yield create_setup_script(
        {
            SetupScriptComponents.SHEBANG,
            SetupScriptComponents.DOCSTRING,
            SetupScriptComponents.MULTIPLE_SETUP_CALLS,
            SetupScriptComponents.PRE_SETUP_CODE,
            SetupScriptComponents.IMPORT_SETUPTOOLS_MODULE
        },
        ['pytest']
    )


def test_update_versions():
    # type: (...) -> None
    """
    Test finding the setup script for this package
    """

    # Go to the current package's directory
    os.chdir(urljoin(__file__, '../'))

    # Create a fake/temporary setup script
    for temp_setup_script_path, setup_script_after in create_setup_scripts():

        # Apply version updates
        requirements.update_setup(temp_setup_script_path)

        # Verify the outcome matches our expected result
        with open(temp_setup_script_path, 'r') as temp_setup_script_io:
            assert temp_setup_script_io.read() == setup_script_after

        # Delete the temp file
        os.remove(temp_setup_script_path)


if __name__ == '__main__':
    test_update_versions()
