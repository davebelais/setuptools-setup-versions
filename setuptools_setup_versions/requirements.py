import re
from typing import Optional, List
from warnings import warn
import sys
from traceback import format_exception

import pkg_resources

from setuptools_setup_versions import parse, find


def update_version(requirement, operator=None):
    # type: (str, Optional[str]) -> str
    """
    Get a requirement string updated to reflect the current package version
    """
    # Parse the requirement string
    parts = re.split(r'([~<>=]+)', requirement)
    if len(parts) == 3:  # The requirement includes a version
        referenced_package, package_operator, version = parts
        if operator:
            package_operator = operator
    else:  # The requirement does not yet include a version
        referenced_package = parts[0]
        if '@' in referenced_package:
            package_operator = version = None
        else:
            package_operator = operator
            version = '0' if operator else None
    referenced_package_name = referenced_package.split('@')[0]
    # Determine the package version currently installed for
    # this resource
    try:
        version = parse.get_package_version(
            referenced_package_name
        )
    except pkg_resources.DistributionNotFound:
        warn(
            'The `%s` packages were not present in the '
            'source environment, and therefore a version '
            'could not be inferred' % referenced_package
        )
    if package_operator:
        return referenced_package + package_operator + version
    elif referenced_package:
        return referenced_package
    else:
        return requirement


def update_versions(requirements, operator=None):
    # type: (List[str], Optional[str]) -> None
    for index in range(len(requirements)):
        try:
            requirements[index] = update_version(
                requirements[index],
                operator=operator
            )
        except:
            warn(''.join(format_exception(*sys.exc_info())))


def update_setup(
    package_directory_or_setup_script=None,
    operator=None
):
    # type: (Optional[str], Optional[str]) -> bool
    """
    Update setup.py installation requirements to (at minimum) require the
    version of each referenced package which is currently installed.

    Parameters:

        package_directory_or_setup_script (str):

            The directory containing the package. This directory must include a
            file named "setup.py".

        operator (str):

            An operator such as '~=', '>=' or '==' which will be applied to all
            package requirements. If not provided, existing operators will
            be used and only package version numbers will be updated.

    Returns:

         `True` if changes were made to setup.py, otherwise `False`
    """
    setup_script_path = find.setup_script_path(
        package_directory_or_setup_script
    )
    # Read the current `setup.py` configuration
    with parse.SetupScript(setup_script_path) as setup_script:
        for setup_call in setup_script.setup_calls:
            if 'install_requires' in setup_call:
                update_versions(
                    setup_call['install_requires'], operator=operator
                )
            if 'extras_require' in setup_call:
                for requirements in setup_call['extras_require'].values():
                    update_versions(requirements, operator=operator)
        modified = setup_script.save()
    return modified