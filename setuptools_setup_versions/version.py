import os
import re
from numbers import Number

from . import find, parse


try:
    from collections import Optional
except ImportError:
    Optional = None


def get(package_directory_or_setup_script=None):
    # type: (Optional[str]) -> Union[str, float, int]
    """
    Get the version # of a package
    """
    setup_script_path = find.setup_script_path(package_directory_or_setup_script)

    with open(setup_script_path) as setup_file:

        setup_file_contents = setup_file.read()

        for setup_call in parse.setup_calls(
            setup_file_contents,
            name_space=dict(
                __file__=os.path.abspath(setup_script_path)
            )
        ):

            try:
                version = setup_call['version']
                break
            except KeyError:
                pass

    return version


def increment(package_directory_or_setup_script=None):
    # type: (Optional[str]) -> bool
    """
    Increment the version # of the referenced package by the least significant amount possible
    """

    setup_script_path = find.setup_script_path(package_directory_or_setup_script)

    with open(setup_script_path) as setup_file:

        new_setup_file_contents = setup_file_contents = setup_file.read()

        for setup_call in parse.setup_calls(
            setup_file_contents,
            name_space=dict(
                __file__=os.path.abspath(setup_script_path)
            )
        ):

            original_source = str(setup_call)

            try:
                version = setup_call['version']
            except KeyError:
                version = None

            if isinstance(version, str):

                dot_version_etc = re.split(r'([^\d.]+)', version)

                if dot_version_etc:

                    dot_version = dot_version_etc[0]
                    etc = ''.join(dot_version_etc[1:])
                    version_list = list(dot_version.split('.'))
                    version_list[-1] = str(int(version_list[-1]) + 1)
                    new_version = '.'.join(version_list) + etc

                    setup_call['version'] = new_version

            elif isinstance(version, int):

                setup_call['version'] += 1

            elif isinstance(version, Number):

                version_string = str(version)

                if '.' in version_string:
                    setup_call['version'] += 1.0/(10.0**len(version_string.split('.')[-1]))
                else:
                    setup_call['version'] += 1

            new_source = str(setup_call)

            if new_source != original_source:
                new_setup_file_contents = new_setup_file_contents.replace(original_source, new_source)

    updated = False  # type: bool

    if new_setup_file_contents != setup_file_contents:
        with open(setup_script_path, 'w') as setup_file:
            setup_file.write(new_setup_file_contents)
        updated = True

    return updated
