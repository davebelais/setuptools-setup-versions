import re
import sys
from traceback import format_exception
from typing import (
    Container, Iterable, Iterator, List, Optional, Union
)
from warnings import warn

import pkg_resources
from more_itertools import grouper

from . import find, parse
from .parse import split_requirement_version_specifiers


def _parse_version_number_string(
    version_number_string: str
) -> Union[str, int]:
    return (
        version_number_string
        if version_number_string == '*' else
        int(version_number_string)
    )


class Version:

    def __init__(
        self,
        version_string: str = ''
    ) -> None:
        # Validate parameters
        assert isinstance(version_string, str)
        # Initialize member data
        self.minor: Optional[Version] = None
        self.prefix: str = ''
        self.number: Union[int, str] = '*'
        if version_string:
            self._parse_version_string(version_string)

    def _parse_version_string(
        self,
        version_string: str
    ) -> None:
        prefix: str
        number_string: str
        version_string_parts: Iterator[str] = iter(re.split(
            r'([^\d*]+)', version_string
        ))
        self.number = _parse_version_number_string(next(version_string_parts))
        version: Version = self
        for prefix, number_string in grouper(version_string_parts, 2):
            version.minor = Version()
            version = version.minor
            version.prefix = prefix
            version.number = _parse_version_number_string(number_string)

    def __iter__(self) -> Iterable['Version']:
        return self._traverse()

    def _traverse(self) -> Iterable['Version']:
        yield self
        if self.minor is not None:
            version: Version
            for version in self.minor._traverse():
                yield version

    def truncate(self, specificity: int = 0, wildcard: bool = False) -> None:
        """
        Truncate the version identifier after the indicated `depth`
        (where 0 is the current depth), and apply a wildcard as the last
        version number if indicated.

        Parameters:

        - depth (int) = 0
        - wildcard (bool) = False: If `True`, make the most specific version
          identifier a wildcard.
        """
        assert specificity >= 0
        index: int
        version: Version
        parent_version: Optional[Version] = None
        for index, version in enumerate(self._traverse()):
            if index == specificity:
                if wildcard:
                    # Wildcards don't work with letter (alpha/beta/etc.)
                    # minor/micro releases, so we match the parent version
                    if version.prefix not in ('', '.'):
                        version = parent_version
                    if parent_version:
                        version.number = '*'
                elif version.minor and version.minor.prefix not in ('', '.'):
                    # Alpha/beta/release-candidates/etc. should be included
                    version = version.minor
                version.minor = None
                break
            parent_version = version

    def align_specificity(self, other: 'Version') -> None:
        """
        Align the level of specificity of this version with that of the
        provided `other` version.
        """
        assert isinstance(other, Version)
        index_plus_one: int
        version: Version
        depth: int = 0
        wildcard: bool = False
        for index, version in enumerate(other._traverse(), 0):
            depth = index
            if version.number == '*':
                wildcard = True
                break
        self.truncate(depth, wildcard=wildcard)

    def __len__(self) -> int:
        return sum(1 for _version in self._traverse())

    def __str__(self) -> str:
        return ''.join(
            f'{version.prefix}{str(version.number)}'
            for version in self._traverse()
        )

    def _compare(self, other: Union['Version', str]) -> int:
        """
        Compare this version to another version or version string, and return a
        negative number if `self` precedes `other`, 0 if they are equal, or a
        positive number if `other` precedes `self`
        """
        # Verify that the `other` can be compared with `self`
        if isinstance(other, str):
            other = Version(other)
        else:
            assert isinstance(other, Version)
        return self._compare_version(other)

    def _compare_version(self, other: 'Version') -> int:
        """
        Compare this version to another, and return a negative number if `self`
        precedes `other`, 0 if they are equal, or a positive number if `other`
        precedes `self`
        """
        for version in self._traverse():
            # Compare prefixes
            if version.prefix != other.prefix:
                if other.prefix == '':
                    return -1
                elif version.prefix == '':
                    return 1
                elif other.prefix == '.':
                    return -1
                elif version.prefix == '.':
                    return 1
                else:
                    return ord(version.prefix) - ord(other.prefix)
            # Compare version numbers
            if version.number == '*' or other.number == '*':
                # Return a match if either is a wildcard
                return 0
            if version.number != other.number:
                return version.number - other.number
        return 0

    def __gt__(self, other: Union['Version', str]) -> bool:
        return self._compare(other) > 0

    def __ge__(self, other: Union['Version', str]) -> bool:
        return self._compare(other) >= 0

    def __lt__(self, other: Union['Version', str]) -> bool:
        return self._compare(other) < 0

    def __le__(self, other: Union['Version', str]) -> bool:
        return self._compare(other) <= 0

    def __eq__(self, other: Union['Version', str]) -> bool:
        return self._compare(other) == 0

    def __bool__(self) -> bool:
        return True


def _get_updated_version_identifier(
    installed_version: str,
    required_version: Optional[str],
    operator: str
) -> str:
    version_string: str
    if ('<' in operator) or ('!' in operator):
        # Versions associated with inequalities and less-than operators
        # should not be updated
        version_string = required_version
    else:
        version: Version = Version(installed_version)
        if required_version:
            version.align_specificity(Version(required_version))
        elif operator == '~=':
            version.truncate(1)
        version_string = str(version)
    return version_string


def _get_updated_version_specifier(
    package_name: str,
    version_specifier: str,
    default_operator: Optional[str] = None
) -> str:
    """
    Get a requirement string updated to reflect the current package version
    """
    # Parse the requirement string
    requirement_operator: str
    version: str
    requirement_operator, version = re.match(
        r'^\s*([!~<>=]*)\s*(.*?)\s*$',
        version_specifier
    ).groups()
    if not requirement_operator:
        requirement_operator = default_operator
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
            'source environment, and therefore a version could not be '
            f'inferred:\n{"".join(format_exception(*sys.exc_info()))}'
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
    version_specifiers: List[str] = split_requirement_version_specifiers(
        requirement
    )
    package_identifier: str
    version_specifier: str
    package_identifier_and_options, version_specifier = (
        parse.PACKAGE_VERSION_PATTERN.match(
            version_specifiers.pop(0)
        ).groups()
    )
    package_identifier: str = (
        package_identifier_and_options.split('@')[0].split('[')[0]
    )
    if version_specifier or default_operator:
        version_specifiers.insert(0, version_specifier or '')
    return package_identifier_and_options + ','.join(
        _get_updated_version_specifier(
            package_identifier,
            version_specifier,
            default_operator
        )
        for version_specifier in version_specifiers
    )


def update_requirements_versions(
    requirements: List[str],
    default_operator: Optional[str] = None,
    ignore: Container[str] = ()
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
        package_identifier: str = parse.get_requirement_package_identifier(
            version_requirement
        )
        if (
            (package_identifier not in ignore) and
            (package_identifier.split('[')[0] not in ignore)
        ):
            try:
                requirements[index] = get_updated_version_requirement(
                    version_requirement,
                    default_operator=default_operator
                )
            except:  # noqa
               warn(''.join(format_exception(*sys.exc_info())))


def update_setup(
    package_directory_or_setup_script: Optional[str] = None,
    default_operator: Optional[str] = None,
    ignore: Container[str] = ()
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
        try:
            update_requirements_versions(
                setup_script['setup_requires'],
                default_operator=default_operator,
                ignore=ignore
            )
        except KeyError:
            pass
        try:
            update_requirements_versions(
                setup_script['install_requires'],
                default_operator=default_operator,
                ignore=ignore
            )
        except KeyError:
            pass
        try:
            for requirements in setup_script['extras_require'].values():
                update_requirements_versions(
                    requirements,
                    default_operator=default_operator,
                    ignore=ignore
                )
        except KeyError:
            pass
    modified = setup_script.save()
    return modified
