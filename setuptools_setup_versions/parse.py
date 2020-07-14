import functools
import json
import os
import re
from collections import OrderedDict
from copy import deepcopy
from types import TracebackType
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pkg_resources
from more_itertools.recipes import grouper

from . import find

STRING_LITERAL_RE = (
    # Make sure the quote is not escaped
    r'(?<!\\)('
    # Triple-double
    r'"""(?:.|\n)*(?<!\\)"""|'
    # Triple-single
    r"'''(?:.|\n)*(?<!\\)'''|"
    # Double
    r'"[^\n]*(?<!\\)"(?!")|'
    # Single
    r"'[^\n]*(?<!\\)'(?!')"
    ')'
)


def _get_imbalance_index(
    text: str,
    imbalance: int = 0,
    boundary_characters: str = '()'
) -> int:
    """
    This function accepts text

    Parameters:

    - **text** (str)
    - **imbalance** (int) = 0
    - **boundary_characters** (str) = "()"

    Returns an integer where:

    - If the parenthesis are not balanced--the integer is the imbalance
      index at the end of the text (a negative number).

    - If the parenthesis are balanced--the integer is the index at which
      they become so (a positive integer).
    """
    index = 0
    length = len(text)
    while index < length and imbalance != 0:
        character = text[index]
        if character == boundary_characters[0]:
            imbalance -= 1
        elif character == boundary_characters[-1]:
            imbalance += 1
        index += 1
    return index if imbalance == 0 else imbalance


class SetupScript(object):

    def __init__(self, path: Optional[str] = None ) -> None:
        self.path: Optional[str] = path
        self._original_source: Optional[str] = None
        self.setup_calls: List[SetupCall] = []
        self._setup_call_locations: List[str] = []
        self._setup_kwargs_code: Optional[str] = None
        if path is not None:
            self.open(path)

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: str,
        exc_value: str,
        traceback_: TracebackType
    ) -> None:
        pass

    def open(self, path: str) -> None:
        self.path = path
        with open(path, 'r') as setup_io:
            self._original_source = setup_io.read()
        self._parse()

    @property
    def _get_setup_kwargs_code(self) -> str:
        """
        This returns a modified version of the setup script which passes
        the keywords for each call to `setuptools.setup` to a dictionary, and
        appends that dictionary to a list: `SETUP_KWARGS`
        """
        script_parts = []
        setup_call_index = 0
        character_index = 0
        parenthesis_imbalance = 0
        in_setup_call = False
        # This is a list of tuples indicating the start and end indices
        # of a `setup` call within the script
        self._setup_call_locations = []  # Sequence[Tuple[int, int]]
        # Split the source of the setup script into chunks which represent
        # code vs string literals
        code: str
        string_literal: str
        for code, string_literal in grouper(
            re.split(STRING_LITERAL_RE, self._original_source),
            2,
            None
        ):
            # Parse the code portion
            if code:
                # Look for a call to `setuptools.setup` in the code portion
                for preceding_code, setup_call in grouper(
                    re.split(r'((?:setuptools\.)?\bsetup[\s]*\()', code),
                    2,
                    None
                ):
                    script_parts.append(preceding_code)
                    # Determine where the setup call ends, if we are inside it
                    if in_setup_call:
                        # We don't care about parenthesis in comments
                        relevant_preceding_code = preceding_code
                        if '#' in relevant_preceding_code:
                            relevant_preceding_code = (
                                relevant_preceding_code.split('#')[0]
                            )
                        # Determine if/where the parenthetical ends, or the
                        # imbalance resulting
                        parenthesis_imbalance = (
                            _get_imbalance_index(
                                relevant_preceding_code,
                                parenthesis_imbalance
                            )
                        )
                        # If `imbalance` is positive--it's the index where the
                        # imbalance ends
                        if parenthesis_imbalance > 0:
                            self._setup_call_locations[-1][-1] = (
                                character_index + parenthesis_imbalance
                            )
                            parenthesis_imbalance = 0
                            in_setup_call = False
                    # Parse the setup call, and modify the script to pass
                    # the keyword arguments to a dictionary
                    if setup_call:
                        self._setup_call_locations.append(
                            [character_index + len(preceding_code), None]
                        )
                        parenthesis_imbalance = -1
                        in_setup_call = True
                        script_parts.append(
                            'SETUP_KWARGS[%s] = dict(' % str(setup_call_index)
                        )
                        setup_call_index += 1
                character_index += len(code)
            if string_literal:
                script_parts.append(string_literal)
                character_index += len(string_literal)
        script_parts.insert(
            0,
            'SETUP_KWARGS = [%s]\n' % ', '.join(['None'] * setup_call_index)
        )
        return ''.join(script_parts)

    def _get_setup_kwargs(self) -> Sequence[Dict[str, Any]]:
        """
        Return an array of dictionaries where each represents the keyword
        arguments to a `setup` call
        """
        name_space = {
            '__file__': self.path
        }
        try:
            exec(self._get_setup_kwargs_code, name_space)
        except Exception:  # noqa
            # Only raise an error if the script could not finish populating all
            # of the setup keyword arguments
            if not (
                'SETUP_KWARGS' in name_space and
                name_space['SETUP_KWARGS'] and
                name_space['SETUP_KWARGS'][-1] is not None
            ):
                raise
        return name_space['SETUP_KWARGS']

    def _parse(self) -> None:
        """
        Parse all of the calls to `setuptools.setup`
        """
        parts = []
        setup_kwargs = self._get_setup_kwargs()
        length = len(setup_kwargs)
        character_index = 0
        for index in range(length):
            parts.append(
                self._original_source[
                    character_index:
                    self._setup_call_locations[index][0]
                ]
            )
            source = self._original_source[
                self._setup_call_locations[index][0]:
                self._setup_call_locations[index][1]
            ]
            self.setup_calls.append(
                SetupCall(
                    self,
                    source=source,
                    keyword_arguments=setup_kwargs[index]
                )
            )

    def __repr__(self):
        return str(self)

    def __str__(self) -> str:
        parts = []
        length = len(self.setup_calls)
        character_index = 0
        for index in range(length):
            parts.append(
                self._original_source[
                    character_index:
                    self._setup_call_locations[index][0]
                ]
            )
            setup_call = self.setup_calls[index]
            parts.append(str(setup_call))
            if index < length - 1:
                character_index = self._setup_call_locations[index + 1][0]
            index += 1
        character_index = self._setup_call_locations[-1][1] + 1
        parts.append(self._original_source[character_index:])
        return ''.join(parts) + '\n'

    def save(self, path: Optional[str] = None) -> bool:
        """
        Save the setup script to `path` and return a `bool` indicating whether
        changes were required
        """
        # If not path is provided, save to the original path from where the
        # setup script was sourced
        if path is None:
            path = self.path
        # A flag to determine whether any changes have been made
        modified = False
        # Try to open any existing source file at this path, and read that file
        # if found
        existing_source = None
        new_source = str(self)
        try:
            with open(path, 'r') as setup_io:
                existing_source = setup_io.read()
        except FileNotFoundError:
            pass
        # Only write to the file if the new contents will be different from
        # those previously existing
        if new_source != existing_source:
            modified = True
            with open(path, 'w') as setup_io:
                setup_io.write(new_source)
        # Return a boolean indicating whether the file needed to be modified
        return modified


class SetupCall(OrderedDict):

    def __init__(
        self,
        setup_script: SetupScript,
        source: str,
        keyword_arguments: Dict[str, Any]
    ) -> None:
        self.setup_script = setup_script
        self._value_locations = None
        self._kwargs = deepcopy(keyword_arguments)
        self._original_source: str = source
        self._modified = set()
        self._indent_length = 4
        self._indent_character = ' '
        self._indent = self._indent_character * self._indent_length
        self._keywords_value_locations = OrderedDict()
        for key, value in keyword_arguments.items():
            super().__setitem__(key, value)

    def _get_value_location(
        self,
        key: str,
        next_key: Optional[str] = None
    ) -> Tuple[int, int]:
        pattern = (
            r'(^.*?\b%s\s*=\s*)(.*?)(' % key +
            (
                r'\b%s\s*=.*?' % next_key
                if next_key else
                r''
            ) +
            r'[\s\r\n]*\)$)'
        )
        before, value = re.match(
            pattern,
            self._original_source,
            flags=re.DOTALL
        ).groups()[:2]
        start: int = len(before)
        end: int = start + len(value.rstrip(' ,\r\n'))
        return start, end

    @property
    def value_locations(self) -> List[Tuple[int, int]]:
        if self._value_locations is None:
            value_locations = []
            keys = tuple(self.keys())
            length = len(keys)
            for index in range(length - 1):
                key = keys[index]
                value_locations.append((
                    key,
                    self._get_value_location(
                        key, keys[index + 1]
                    )
                ))
            key = keys[-1]
            value_locations.append((key, self._get_value_location(key)))
            self._value_locations = value_locations
        return self._value_locations

    def __str__(self):
        return repr(self)

    def _repr_value(self, value: Any) -> str:
        value_lines = json.dumps(value, indent=self._indent_length).split('\n')
        if len(value_lines) > 1:
            for index in range(1, len(value_lines)):
                value_lines[index] = self._indent + value_lines[index]
        return '\n'.join(value_lines)

    def __repr__(self) -> str:
        """
        Return a representation of the `setup` call which can be used in this
        setup script
        """
        parts = []
        index = 0
        for key, location in self.value_locations:
            before = self._original_source[index:location[0]]
            if index and before[0] != ',':
                before = ',' + before
            parts.append(before)
            if self[key] == self._kwargs[key]:
                parts.append(self._original_source[location[0]:location[1]])
            else:
                parts.append(self._repr_value(self[key]))
            index = location[1]
        parts.append(
            self._original_source[index:]
        )
        return ''.join(parts)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Intercept `__setitem__` calls in order to flag the setup script as
        having been modified
        """
        if (key not in self) or self[key] != value:
            self._modified.add(key)
            super().__setitem__(key, value)


def get_package_name_and_version_from_setup(
    path: Optional[str] = None
) -> Tuple[str, Union[str, float, int]]:
    """
    Get the version # of a package
    """
    version: str = None
    name: str = None
    for setup_call in SetupScript(path).setup_calls:
        try:
            version = setup_call['version']
        except KeyError:
            pass
        try:
            name = setup_call['name']
        except KeyError:
            pass
        # We have a version and package name, so we are done
        if (version is not None) and (name is not None):
            break
    return name, version


def get_package_name_and_version_from_egg_info(
    directory: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse the egg's PKG-INFO and return the package name and version
    """
    name: Optional[str] = None
    version: Optional[str] = None
    pkg_info_path = os.path.join(directory, 'PKG-INFO')
    with open(pkg_info_path, 'r') as pkg_info_file:
        for line in pkg_info_file.read().split('\n'):
            if ':' in line:
                property_name, value = line.split(':')[:2]
                property_name = property_name.strip().lower()
                if property_name == 'version':
                    version = value.strip()
                    if name is not None:
                        break
                elif property_name == 'name':
                    name = value.strip()
                    if version is not None:
                        break
    return name, version


@functools.lru_cache()
def _get_package_names_versions() -> Dict[str, Any]:
    """
    This returns a dictionary mapping package names -> version
    """
    package_names_versions: Dict[str, Any] = {}
    for entry in pkg_resources.working_set.entries:
        egg_info_path: str
        name: str = ''
        version: str = ''
        try:
            egg_info_path = find.egg_info(entry)
        except (FileNotFoundError, NotADirectoryError):
            egg_info_path = ''
        if egg_info_path:
            name, version = get_package_name_and_version_from_egg_info(
                egg_info_path
            )
        else:
            try:
                setup_script_path: str = find.setup_script_path(entry)
                name, version = get_package_name_and_version_from_setup(
                    setup_script_path
                )
            except FileNotFoundError:
                # This indicates a package with no setup script *or*
                # egg-info was found, so it's not a package
                pass
        if name is not None:
            package_names_versions[name] = version
    return package_names_versions


@functools.lru_cache()
def get_package_version(package_name: str) -> str:
    normalized_package_name: str = package_name.replace('_', '-')
    version: Optional[str] = None
    try:
        version = pkg_resources.get_distribution(
            normalized_package_name
        ).version
    except pkg_resources.DistributionNotFound:
        # The package has no distribution information available--obtain it from
        # `setup.py`
        for name, version_ in _get_package_names_versions().items():
            # If the package name is a match, we will return the version found
            if name and name.replace('_', '-') == normalized_package_name:
                version = version_
                break
        if version is None:
            raise
    return version
