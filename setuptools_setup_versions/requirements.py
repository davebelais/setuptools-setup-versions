import re
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


def _get_updated_version_specifier(
    package_name: str,
    version_specifier: str,
    operator: Optional[str] = None
) -> str:
    """
    Get a requirement string updated to reflect the current package version
    """
    # Parse the requirement string
    requirement_operator: str
    version: str
    requirement_operator, version = re.match(
        r'^\s*([~<>=]*)\s*(.*?)\s*$',
        version_specifier
    ).groups()
    if not requirement_operator:
        requirement_operator = operator
    # Determine the package version currently installed for
    # this resource
    try:
        version = _get_updated_version_identifier(
            parse.get_package_version(
                package_name
            ),
            version,
            requirement_operator
        )
    except pkg_resources.DistributionNotFound:
        warn(
            f'The `{package_name}` package was not present in the '
            'source environment, and therefore a version could not be inferred'
        )
    return requirement_operator + version


def get_updated_version_requirement(
    requirement: str,
    default_operator: Optional[str] = None
) -> str:
    """
    Return the provided package requirement updated to reflect the currently
    installed version of the package.

    - version_requirement ([str]): A PEP-440 compliant package requirement.
    - default_operator (str) = None: If specified, package requirements
      which did not already have a version specifier will be assigned the
      current package version with this operator. If not specified—package
      requirements without a version specifier will remain as-is.
    """
    version_specifiers: List[str] = requirement.split(',')
    package_identifier: str
    version_specifier: str
    package_identifier, version_specifier = re.match(
        r'^\s*([^\s~<>=]*)?\s*([~<>=].*?)\s*$',
        version_specifiers.pop(0)
    ).groups()
    if version_specifier:
        version_specifiers.insert(0, version_specifier)
    return package_identifier + ','.join(
        _get_updated_version_specifier(
            package_identifier.split('@')[0],
            version_specifier,
            default_operator
        )
        for version_specifier in version_specifiers
    )


def update_requirements_versions(
    requirements: List[str],
    default_operator: Optional[str] = None
) -> None:
    """
    Update (in-place) the version specifiers for a list of requirements.

    - requirements ([str]): A list of PEP-440 compliant package requirement.
    - default_operator (str) = None: If specified, package requirements
      which do not have a version specifier will be assigned the current
      package version with this operator.
    """
    index: int
    version_requirement: str
    for index, version_requirement in enumerate(requirements):
        try:
            requirements[index] = get_updated_version_requirement(
                version_requirement,
                default_operator=default_operator
            )
        except:  # noqa
            warn(''.join(format_exception(*sys.exc_info())))


def update_setup(
    package_directory_or_setup_script: Optional[str] = None,
    default_operator: Optional[str] = None
) -> bool:
    """
    Update setup.py installation requirements to (at minimum) require the
    version of each referenced package which is currently installed.

    Parameters:

    - package_directory_or_setup_script (str): The directory containing the
      package. This directory must include a file named "setup.py".
    - operator (str): An operator such as '~=', '>=' or '==' which will be
      applied to all package requirements. If not provided, existing operators
      will  be used and only package version numbers will be updated.

    Returns: `True` if changes were made to setup.py, otherwise `False`
    """
    setup_script_path: str = find.setup_script_path(
        package_directory_or_setup_script
    )
    # Read the current `setup.py` configuration
    setup_script: parse.SetupScript
    with parse.SetupScript(setup_script_path) as setup_script:
        for setup_call in setup_script.setup_calls:
            if 'setup_requires' in setup_call:
                update_requirements_versions(
                    setup_call['setup_requires'],
                    default_operator=default_operator
                )
            if 'install_requires' in setup_call:
                update_requirements_versions(
                    setup_call['install_requires'],
                    default_operator=default_operator
                )
            if 'extras_require' in setup_call:
                for requirements in setup_call['extras_require'].values():
                    update_requirements_versions(
                        requirements, default_operator=default_operator
                    )
        modified = setup_script.save()
    return modified
