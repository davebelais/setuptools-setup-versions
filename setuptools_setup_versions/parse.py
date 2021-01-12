import functools
import json
import logging
import os
import re
import sys
from collections import OrderedDict
from copy import deepcopy
from io import IOBase
from itertools import chain, starmap
from multiprocessing import Pool
from subprocess import getstatusoutput
from types import TracebackType
from typing import (
    Any, Collection, Container, Dict, Iterable, List, Optional, Pattern, Set,
    Tuple, Union
)

import pkg_resources
from more_itertools import chunked
from more_itertools.recipes import grouper
from packaging.utils import canonicalize_name

from . import find

PACKAGE_VERSION_PATTERN: Pattern = re.compile(
    r'^\s*([^\s~<>=]*)?\s*([~<>=].*?)?\s*$'
)
STRING_LITERAL_RE = (
    # Make sure the quote is not escaped
    r'(?<!\\)('
    # Triple-double
    r'"""(?:.|\n)*?(?<!\\)"""|'
    # Triple-single
    r"'''(?:.|\n)*?(?<!\\)'''|"
    # Double
    r'"[^\n]*?(?<!\\)"(?!")|'
    # Single
    r"'[^\n]*?(?<!\\)'(?!')"
    ')'
)
_SETUP_CALL_PATTERN: Pattern = re.compile(
    r'((?:setuptools\.)?\bsetup\b[\s]*\()'
)
INDENT_LENGTH: int = 4
INDENT: str = " " * INDENT_LENGTH


def split_requirement_version_specifiers(requirement: str) -> List[str]:
    """
    >>> split_requirement_version_specifiers(
    ...     'package_name[option-a,option-b]>=1.1,<2.0.1'
    ... )
    ['package_name[option-a,option-b]>=1.1', '<2.0.1']
    """
    if ']' in requirement:
        # Package options were specified
        parts: List[str] = requirement.split(']')
        package_specifier: str = f"{']'.join(parts[:-1])}]"
        version_specifiers: List[str] = parts[-1].split(',')
        return [
            f'{package_specifier}{version_specifiers[0]}'
        ] + version_specifiers[1:]
    else:
        return requirement.split(',')


def get_requirement_package_identifier(requirement: str) -> str:
    return (
        PACKAGE_VERSION_PATTERN.match(
            split_requirement_version_specifiers(requirement)[0]
        ).groups()[0].strip().split('@')[0]
    )


def _get_imbalance(
    text: str,
    boundary_characters: str = '()'
) -> int:
    """
    This function accepts text, and returns a negative integer to indicate
    the number of opening boundary characters are unmatched, or a positive
    integer to indicate the number of closing boundary characters which are
    unmatched.

    Parameters:

    - **text** (str)
    - **boundary_characters** (str) = "()"
    """
    index: int
    character: str
    imbalance: int = 0
    for character in text:
        if character == boundary_characters[0]:
            imbalance -= 1
        elif character == boundary_characters[-1]:
            imbalance += 1
    return imbalance


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


class SetupCall(OrderedDict):

    def __init__(
        self,
        source: str,
        keyword_arguments: Dict[str, Any],
        start: int = 0,
        stop: int = 0,
        line_length: int = 79
    ) -> None:
        super().__init__()
        assert isinstance(keyword_arguments, dict)
        self.start = start
        self.stop = stop
        self.line_length = line_length
        self._value_locations = None
        self._kwargs = deepcopy(keyword_arguments)
        self._original_source: str = source
        for key, value in keyword_arguments.items():
            super().__setitem__(key, value)

    def _get_value_location(
        self,
        key: str,
        next_key: Optional[str] = None
    ) -> Tuple[int, int]:
        pattern = (
            r'(^.*?\b{}\s*=\s*)(.*?)('.format(key) +
            (
                r'\b{}\s*=.*?'.format(next_key)
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
        value_locations: List[Tuple[str, Tuple[int, int]]] = []
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
        return value_locations

    def __str__(self):
        return repr(self)

    def _repr_value(self, value: Any) -> str:
        value_lines = json.dumps(value, indent=INDENT_LENGTH).split('\n')
        if len(value_lines) > 1:
            for index, line in enumerate(value_lines[1:], 1):
                line_length: int = len(line)
                if (
                    line_length + INDENT_LENGTH <
                    self.line_length
                ):
                    value_lines[index] = f'{INDENT}{line}'
                else:
                    value: Union[str, Any] = None
                    try:
                        value = json.loads(
                            line.rstrip(',').lstrip()
                        )
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(value, str):
                        value_lines[index] = f'{INDENT}{line}'
                        continue
                    indent: str = '{}{}'.format(
                        INDENT,
                        re.match(r'(^[ ]*)[^ ]', line).groups()[0]
                    )
                    indent_length: int = len(indent)
                    value_lines[index] = (
                        '{indent}(\n'
                        '{string_chunks}\n'
                        '{indent}){comma}'
                    ).format(
                        indent=indent,
                        string_chunks='\n'.join(
                            [
                                f'{indent}{INDENT}"{"".join(chunk)}"'
                                for chunk in chunked(
                                    value,
                                    (
                                        self.line_length
                                        - (indent_length + INDENT_LENGTH)
                                        - 2
                                    )
                                )
                            ]
                        ),
                        comma=line[-1] if line[-1] != '"' else ''
                    )
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


def _get_setup_call_start_indices_and_parenthesis_imbalance(
    code: str,
    parenthesis_imbalance: int = 0
) -> Tuple[List[int], int]:
    setup_call_character_indices: List[int] = []
    subsequent_setup_call_character_indices: List[int] = []
    preceding_code: str
    setup_call: str
    code_length: int = len(code)
    preceding_code, setup_call = next(iter(grouper(  # noqa
        _SETUP_CALL_PATTERN.split(code),
        2,
        None
    )))
    if setup_call and re.match(
        r'^.*\b(def|class)[ ]+$',
        preceding_code,
        re.DOTALL
    ):
        preceding_code += setup_call
        setup_call = None
    preceding_code_length: int = len(preceding_code or '')
    setup_call_length: int = len(setup_call or '')
    if preceding_code:
        parenthesis_imbalance += _get_imbalance(
            preceding_code
        )
    if setup_call:
        if parenthesis_imbalance == 0:
            setup_call_character_indices.append(preceding_code_length)
            parenthesis_imbalance += _get_imbalance(
                setup_call
            )
        else:
            parenthesis_imbalance += _get_imbalance(
                setup_call
            )
            preceding_code += setup_call
            preceding_code_length += setup_call_length
            setup_call = None
            setup_call_length = 0
    character_index: int = preceding_code_length + setup_call_length
    if character_index < code_length:
        subsequent_setup_call_character_indices, parenthesis_imbalance = (
            _get_setup_call_start_indices_and_parenthesis_imbalance(
                code[character_index:],
                parenthesis_imbalance
            )
        )
    return (
        setup_call_character_indices + [
            (character_index + subsequent_character_index)
            for subsequent_character_index in (
                subsequent_setup_call_character_indices
            )
        ],
        parenthesis_imbalance
    )


def _get_setup_call_indices_and_parenthesis_imbalance(
    code: str,
    parenthesis_imbalance: int = 0,
    offset: int = 0
) -> Tuple[List[Tuple[int, int]], int]:
    start_indices: List[int]
    range_indices: List[Tuple[int, int]] = []
    start_indices, parenthesis_imbalance = (
        _get_setup_call_start_indices_and_parenthesis_imbalance(
            code,
            parenthesis_imbalance
        )
    )
    index: int
    start_index: Optional[int]
    next_index: Optional[int]
    stop_index: Optional[int]
    for start_index, next_index in zip(
        start_indices,
        start_indices[1:] + [None]
    ):
        try:
            stop_index = (
                code[start_index:next_index].rindex(')') +
                start_index + 1
            )
        except ValueError:
            stop_index = None
        range_indices.append((
            offset + start_index,
            None if stop_index is None else offset + stop_index
        ))
    return range_indices, parenthesis_imbalance


def _get_setup_call_stop_index(setup_call: str) -> int:
    pass


class SetupScript:

    def __init__(
        self,
        input: Union[str, IOBase]
    ) -> None:
        self._input: Union[str, IOBase] = input
        self._setup_call_locations: List[Tuple[int, int]] = []

    @property
    @functools.lru_cache()
    def path(self) -> Optional[str]:
        return (
            self._input
            if (
                isinstance(self._input, str) and
                os.path.exists(self._input)
            ) else getattr(
                self._input,
                'url',
                getattr(
                    self._input,
                    'name',
                    None
                )
            )
        )

    def __iter__(self) -> Iterable[str]:
        used_keys: Set[str] = set()
        setup_call: SetupCall
        for setup_call in self._setup_calls:
            for key in setup_call.keys():
                if key not in used_keys:
                    yield key
                    used_keys.add(key)

    def items(self) -> Iterable[Tuple[str, Any]]:
        used_keys: Set[str] = set()
        setup_call: SetupCall
        for setup_call in self._setup_calls:
            for key, value in setup_call.items():
                if key not in used_keys:
                    yield key, value
                    used_keys.add(key)

    def keys(self) -> Set[str]:
        return set(key for key in self)

    def __getitem__(self, key: str) -> Any:
        setup_call: SetupCall
        for setup_call in self._setup_calls:
            try:
                return setup_call[key]
            except KeyError:
                pass
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @property
    @functools.lru_cache()
    def _source(self) -> str:
        source: Union[str, bytes]
        if isinstance(self._input, str):
            try:
                with open(self._input, 'r') as setup_io:
                    source = setup_io.read()
            except FileNotFoundError:
                if '\n' in self._input:
                    source = self._input
                else:
                    raise
        else:
            assert isinstance(self._input, IOBase)
            source = self._input.read()  # noqa
        return source

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: str,
        exc_value: str,
        traceback_: TracebackType
    ) -> None:
        pass

    @property
    @functools.lru_cache()
    def _setup_call_character_ranges(self) -> List[Tuple[int, int]]:
        start: int
        stop: int
        code: str
        preceding_code: str
        setup_call: str
        character_index: int = 0
        setup_calls_character_ranges: List[Tuple[int, int]] = []
        parenthesis_imbalance: int = 0
        for code, string_literal in grouper(
            re.split(STRING_LITERAL_RE, self._source),
            2,
            None
        ):
            code_length: int = len(code or '')
            string_literal_length: int = len(string_literal or '')
            if code:
                setup_call_ranges, parenthesis_imbalance = (
                    _get_setup_call_indices_and_parenthesis_imbalance(
                        code,
                        parenthesis_imbalance,
                        offset=character_index
                    )
                )
                if (
                    setup_call_ranges
                ) and (
                    setup_calls_character_ranges
                ) and (
                    setup_calls_character_ranges[-1][-1] is None
                ):
                    # ...we left off inside a setup call
                    setup_calls_character_ranges[-1] = (
                        setup_calls_character_ranges[-1][0],
                        (
                            code[:setup_call_ranges[0][0]].rindex(')') +
                            1
                        )
                    )
                for start, stop in setup_call_ranges:
                    setup_calls_character_ranges.append(
                        (
                            start,
                            stop
                        )
                    )
            character_index += code_length + string_literal_length
        return setup_calls_character_ranges

    @property
    @functools.lru_cache()
    def _setup_kwargs_source(self) -> str:
        """
        This returns a modified version of the setup script which passes
        the keywords for each call to `setuptools.setup` to a dictionary, and
        appends that dictionary to a list: `SETUP_KWARGS`
        """
        setup_call_character_ranges: List[Tuple[int, int]] = (
            self._setup_call_character_ranges
        )
        script_parts: List[str] = [
            'SETUP_KWARGS = [{}]\n'.format(
                ', '.join(['None'] * len(setup_call_character_ranges))
            )
        ]
        previous: int = 0
        setup_call: str
        start: int
        stop: int
        start_stop: Tuple[int, int]
        for index, start_stop in enumerate(setup_call_character_ranges):
            start, stop = start_stop
            script_parts.append(
                self._source[previous:start]
            )
            setup_call = self._source[start:stop]
            script_parts.append(
                'SETUP_KWARGS[{}] = dict{}'.format(
                    index,
                    setup_call[setup_call.index('('):]
                )
            )
            previous = stop
        if previous:
            script_parts.append(
                self._source[previous:]
            )
        return ''.join(script_parts)

    @property
    @functools.lru_cache()
    def _setup_calls(self) -> List[SetupCall]:
        before: str
        setup_calls: List[SetupCall] = []
        name_space = {
            '__file__': self.path
        }
        try:
            exec(self._setup_kwargs_source, name_space)
        except Exception:  # noqa
            # Only raise an error if the script could not finish populating all
            # of the setup keyword arguments
            if not (
                'SETUP_KWARGS' in name_space and
                name_space['SETUP_KWARGS'] and
                name_space['SETUP_KWARGS'][-1] is not None
            ):
                raise
        for index, kwargs in enumerate(name_space['SETUP_KWARGS']):
            if kwargs is not None:
                start = self._setup_call_character_ranges[index][0]
                stop = self._setup_call_character_ranges[index][1]
                before = self._source[:start]
                setup_calls.append(SetupCall(
                    source=self._source[start:stop],
                    keyword_arguments=kwargs,
                    line_length=79 - (
                        len(before) - (
                            before.rindex('\n') + 1
                        )
                    ),
                    start=start,
                    stop=stop
                ))
        return setup_calls

    def __repr__(self):
        return str(self)

    def __str__(self) -> str:
        parts = []
        previous: int = 0
        for setup_call in self._setup_calls:
            parts.append(
                self._source[
                    previous:
                    setup_call.start
                ]
            )
            parts.append(str(setup_call))
            previous = setup_call.stop
        if previous is not None:
            parts.append(self._source[previous:])
        return ''.join(parts).rstrip() + '\n'

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


@functools.lru_cache()
def get_package_name_and_version_from_setup(
    path: Optional[str] = None
) -> Tuple[Union[str, float, int], ...]:
    """
    Get the version # of a package
    """
    setup_script: SetupScript = SetupScript(path)
    name_and_version: Tuple[Union[str, float, int], ...] = ()
    key: str
    for parameter in ('name', 'version'):
        try:
            name_and_version += (setup_script[parameter],)
        except KeyError:
            raise RuntimeError(
                f'The parameter "{parameter}" was not found for `setup` in '
                f'{path}:\n\n{setup_script._setup_kwargs_source}'
            )
    return name_and_version


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
def _get_source_package_names_versions() -> Dict[str, Any]:
    """
    This returns a dictionary mapping package names -> version
    """
    package_names_versions: Dict[str, Any] = {}
    for entry in pkg_resources.working_set.entries:
        egg_info_path: str
        name: str = ''
        version: str = ''
        try:
            # First look for a setup script
            setup_script_path: str = find.setup_script_path(entry)
            name, version = get_package_name_and_version_from_setup(
                setup_script_path
            )
        except (FileNotFoundError, RuntimeError):
            try:
                egg_info_path = find.egg_info(entry)
                if egg_info_path:
                    name, version = get_package_name_and_version_from_egg_info(
                        egg_info_path
                    )
            except (FileNotFoundError, NotADirectoryError):
                pass
        if name:
            package_names_versions[name] = version
    return package_names_versions


@functools.lru_cache()
def _get_source_package_version(normalized_package_name: str) -> str:
    name: str
    version: str
    for name, version in _get_source_package_names_versions().items():
        # If the package name is a match, we will return the version found
        if name and canonicalize_name(name) == normalized_package_name:
            return version
    return ''


@functools.lru_cache()
def get_package_version(package_name: str) -> str:
    normalized_package_name: str = canonicalize_name(package_name)
    return (
        _get_source_package_version(normalized_package_name) or
        pkg_resources.get_distribution(
            normalized_package_name
        ).version
    )


def _get_freeze_source_packages(
    exclude: Iterable[str] = (),
    include: Union[str, Iterable[str]] = ()
) -> Dict[str, str]:
    """
    Get a dictionary of package names mapped to a version requirement
    identifier for packages found in the root of a `sys.path` directory
    """
    exclude = set(exclude)
    include = {include} if isinstance(include, str) else set(include)
    source_package_names: Dict[str, str] = OrderedDict()
    version: str
    source_package_name: str
    for source_package_name, version in (
        _get_source_package_names_versions().items()
    ):
        source_package_name = canonicalize_name(source_package_name)
        package_version = f'{source_package_name}=={version}'
        if source_package_name not in exclude:
            if (not include) or (source_package_name in include):
                source_package_names[source_package_name] = package_version
    return source_package_names


@functools.lru_cache()
def _get_installed_required_package_names(
    package_name: str,
    parallelize: bool = False,
    exclude: Collection[str] = ()
) -> Set[str]:
    """
    Get the package name for all of a package's requirements, including extras
    """
    package_name = canonicalize_name(package_name)
    exclude = set(exclude) | {package_name}
    distribution_requires: Iterable[str]
    required_package_names: Set[str]
    try:
        distribution: pkg_resources.Distribution = (
            pkg_resources.get_distribution(
                package_name
            )
        )
        required_package_names = set(map(
            lambda required_distribution: canonicalize_name(
                required_distribution.name
            ),
            distribution.requires(
                extras=tuple(filter(
                    lambda key: key is not None,
                    getattr(distribution, '_dep_map', {}).keys()
                ))
            )
        ))
    except pkg_resources.DistributionNotFound as distribution_not_found_error:
        found: bool = False
        required_package_names = set()
        for entry in pkg_resources.working_set.entries:
            try:
                setup_script_path: str = find.setup_script_path(entry)
                setup_script: SetupScript = SetupScript(setup_script_path)
                found = canonicalize_name(
                    setup_script.get('name', '')
                ) == package_name
                if found:
                    for requirement in (
                        list(setup_script.get('install_requires', [])) +
                        list(setup_script.get('setup_requires', [])) +
                        list(chain(*setup_script.get(
                            'extras_require', {}
                        ).values()))
                    ):
                        required_package_names.add(
                            canonicalize_name(
                                get_requirement_package_identifier(
                                    requirement
                                )
                            )
                        )
                    break
            except FileNotFoundError:
                continue
            if found:
                break
        if not found:
            return required_package_names
    required_package_names -= exclude
    if required_package_names:
        logging.info(
            '"{}" requires: "{}"'.format(
                package_name,
                '", "'.join(required_package_names)
            )
        )
    if not required_package_names:
        return required_package_names
    exclude |= required_package_names
    parallelize_recursive_calls: bool = False
    if parallelize and len(required_package_names) < 2:
        parallelize = False
        parallelize_recursive_calls = True
    exclude = tuple(sorted(exclude))
    arguments: Iterable[Tuple[str, bool, Tuple[str, ...]]] = (
        (
            required_package_name,
            parallelize_recursive_calls,
            exclude
        )
        for required_package_name in
        required_package_names
    )
    if parallelize:
        pool: Pool
        with Pool() as pool:
            required_package_names |= set(chain(*pool.starmap(
                _get_installed_required_package_names,
                arguments
            )))
    else:
        required_package_names |= set(chain(*starmap(
            _get_installed_required_package_names,
            arguments
        )))
    return required_package_names


def _flatten_requirements(
    requirements: Iterable[str],
    exclude: Union[str, Collection[str]] = ()
) -> Iterable[str]:
    exclude = set(
        canonicalize_name(package_name)
        for package_name in (
            (exclude,)
            if isinstance(exclude, str) else
            exclude
        )
    )
    requirements = set(
        canonicalize_name(package_name)
        for package_name in (
            (requirements,)
            if isinstance(requirements, str) else
            requirements
        )
    ) - exclude
    return chain(*(
        (package_name,) +
        tuple(_get_installed_required_package_names(  # noqa
            package_name,
            True,
            tuple(sorted(exclude))
        ))
        for package_name in requirements
    ))


def _get_pip_freeze(editable: bool = False) -> Iterable[Tuple[str, str]]:
    status: int
    output: str
    status, output = getstatusoutput(
        f'{sys.executable} -m pip freeze'
    )
    if status:
        raise OSError(output)
    # Get all installed packages
    for requirement in output.split('\n'):
        is_editable_requirement: bool = (
            requirement.startswith('-e ') or
            requirement.startswith('--editable ')
        )
        package_name = requirement
        # Get the package name
        if is_editable_requirement:
            if '#egg=' in requirement:
                package_name = canonicalize_name(
                    requirement.split('#egg=')[-1]
                )
            else:
                package_name = ' '.join(requirement.split(' ')[1:])
        if (not editable) and is_editable_requirement:
            requirement = package_name
        if '==' in package_name:
            package_name = canonicalize_name(package_name.split('==')[0])
        elif (not editable) or (not is_editable_requirement):
            requirement = (
                f'{package_name}=='
                f'{_get_source_package_version(package_name)}'
            )
        yield package_name, requirement


def get_freeze(
    editable: bool = False,
    exclude: Union[str, Collection[str]] = (),
    include: Union[str, Collection[str]] = ()
) -> Iterable[str]:
    """
    Iterate over the packages installed/referenced in the current environment.

    Parameters:

    - editable (bool) = False: If `False` (the default), editable packages
      will be returned as a package name + version identifier rather than
      an editable requirement referencing a VCS.
    """
    requirement: str
    package_name: str
    # Normalize excluded/included package names and expand to include packages
    # required by the excluded/included package
    include = set(_flatten_requirements(include, exclude=exclude))
    exclude = exclude if include else set(_flatten_requirements(exclude))
    source_package_names_requirements: Dict[str, str] = (
        _get_freeze_source_packages(
            exclude=exclude,
            include=include
        )
    )
    # Get the output of `pip freeze`
    for package_name, requirement in _get_pip_freeze(editable):
        if package_name not in exclude:
            if (not include) or (package_name in include):
                # Make sure the package wasn't among the source packages
                # already yielded
                if package_name in source_package_names_requirements:
                    if editable:
                        yield requirement
                        del source_package_names_requirements[package_name]
                else:
                    yield requirement
    for package_name, requirement in source_package_names_requirements.items():
        if package_name not in exclude:
            if (not include) or (package_name in include):
                yield requirement