import re
from copy import copy
from typing import Optional, List
from warnings import warn
import sys
from traceback import format_exception

import pkg_resources

from setuptools_setup_versions import parse, find


def _align_version_specificity(
    installed_version: str,
    required_version: Optional[str],
    default_specificity: int = 2
) -> str:
    version: str
    installed_version_parts: List[str] = installed_version.split('.')
    if required_version and required_version != '0':
        reference_version_parts: List[str] = required_version.split('.')
        version_parts_length: int = len(installed_version_parts)
        reference_version_parts_length: int = len(reference_version_parts)
        version_parts: List[str] = installed_version_parts[
            :(
                reference_version_parts_length
                if (
                    version_parts_length > reference_version_parts_length
                ) else
                None
            )
        ]
        if reference_version_parts[-1].strip() == '*':
            version_parts[-1] = '*'
        version = '.'.join(version_parts)
    else:
        version = '.'.join(installed_version_parts[:default_specificity])
    return version


def _get_updated_version_identifier(
    installed_version: str,
    required_version: Optional[str],
    operator: str
) -> str:
    version: str = installed_version
    if operator == '~=' or (
        required_version and
        operator == '==' and
        required_version.rstrip().endswith('*')
    ):
        version = _align_version_specificity(
            installed_version,
            required_version,
            2
        )
    elif ('<' in operator) or ('!' in operator):
        # Versions associated with inequalities and less-than operators
        # should not be updated
        version = required_version
    return version


def update_version(
    requirement,
    operator=None,
    package_name=None
):
    # type: (str, Optional[str], Optional[str]) -> str
    """
    Get a requirement string updated to reflect the current package version
    """
    leftovers: List[str] = []
    if ',' in requirement:
        leftovers = requirement.split(',')
        requirement = leftovers.pop(0)
    package_identifier: str
    # Parse the requirement string
    parts = re.split(r'([~<>=]+)', requirement)
    if len(parts) == 3:  # The requirement includes a version
        package_identifier, package_operator, version = parts
    else:  # The requirement does not yet include a version
        package_identifier = parts[0]
        if '@' in package_identifier:
            package_operator = version = None
        else:
            package_operator = operator
            version = '0' if operator else None
    if package_identifier:
        package_name = package_identifier.split('@')[0]
    # Determine the package version currently installed for
    # this resource
    try:
        version = _get_updated_version_identifier(
            parse.get_package_version(
                package_name
            ),
            version,
            package_operator
        )
    except pkg_resources.DistributionNotFound:
        warn(
            'The `%s` packages were not present in the '
            'source environment, and therefore a version '
            'could not be inferred' % package_identifier
        )
    new_requirement: List[str] = []
    package_identifier: str = (
        package_name
        if package_identifier else
        ''
    )
    if package_operator:
        new_requirement.append(
            package_identifier + package_operator + version
        )
    elif package_identifier:
        new_requirement.append(package_identifier)
    else:
        new_requirement.append(requirement)
    leftover: str
    for leftover in leftovers:
        new_requirement.append(
            update_version(
                leftover.strip(),
                operator=None,
                package_name=package_name
            )
        )
    return ','.join(new_requirement)


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