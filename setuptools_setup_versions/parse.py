import json
import re


try:
    from typing import Optional, Tuple, Dict, Any
except ImportError:
    Optional = Tuple = Dict = Any = None


class SetupCall(object):

    def __init__(
        self,
        source,
        keyword_arguments
    ):
        self.source = source  # type: str
        self._keyword_arguments = keyword_arguments  # type: dict

        indentation = ''
        parameter_indentation = ''
        expand_tabs = True
        lines = self.source.split('\n')

        if len(lines) > 1:
            line = lines[-1]
            match = re.match(r'^[ ]+', line)
            if match:
                group = match.group()
                if group:
                    indentation = group
            if not indentation:
                match = re.match(r'^[\t]+', line)
                if match:
                    group = match.group()
                    if group:
                        indentation = group
                        expand_tabs = False
            parameter_indentation = indentation

        if len(lines) > 2:
            line = self.source.split('\n')[1]
            match = re.match(r'^[ ]+', line)
            if match:
                group = match.group()
                if group:
                    parameter_indentation = group
            if not parameter_indentation:
                match = re.match(r'^[\t]+', line)
                group = match.group()
                if group:
                    parameter_indentation = group
                    expand_tabs = False

        self._indentation = indentation
        self._parameter_indentation = parameter_indentation
        self._expand_tabs = expand_tabs

    def __str__(self):
        return self.source

    def repr(self):
        # type: (...) -> str
        return '\n'.join([
            'setuptools_setup_versions.parse.SetupCall(\n',
            '   %s,\n' % repr(self.source),
            '   %s,\n' % repr(self._keyword_arguments),
            ')'
        ])

    def __setitem__(self, key, value):
        # type: (str, Any) -> None

        if self[key] != value:

            source_parts = re.split(
                r'(\b%s[\s]*=)' % key,
                self.source
            )  # type: Sequence[str]

            existing_key_value_source = None

            if len(source_parts) > 2:

                source_parts[-1] = source_parts[-1].rstrip(')')

                name_space = {}

                for i in range(2, len(source_parts), 2):

                    source_value_representation_parts = []

                    potential_source_value_representation_parts = source_parts[i].split(',')

                    for source_value_representation_part in potential_source_value_representation_parts:

                        source_value_representation_parts.append(source_value_representation_part)

                        try:
                            exec(
                                'value = ' + ','.join(source_value_representation_parts),
                                name_space
                            )
                            break
                        except SyntaxError:
                            pass

                    existing_key_value_source = (
                        ''.join(source_parts[-2]) + ','.join(source_value_representation_parts)
                    ).rstrip()

                    break

            indent = len(self._parameter_indentation) - len(self._indentation)
            key_value_source = key + '=' + json.dumps(value, indent=indent)

            if self._parameter_indentation:
                key_value_source_lines = key_value_source.split('\n')
                if len(key_value_source_lines) > 1:
                    for i in range(1, len(key_value_source_lines)):
                        key_value_source_lines[i] = self._parameter_indentation + key_value_source_lines[i]
                key_value_source = '\n'.join(key_value_source_lines)

            if existing_key_value_source is None:

                lines = self.source.split('\n')
                if len(lines) > 1:
                    self.source = (
                        '\n'.join(lines[:-1]).rstrip(' ,') + ',\n' +
                        self._parameter_indentation + key_value_source +
                        lines[-1]
                    )
                else:
                    self.source = self.source.rstrip(',) ') + ', ' + key_value_source + ')'

            else:

                self.source = self.source.replace(existing_key_value_source, key_value_source)

            self._keyword_arguments[key] = value

    def __getitem__(self, key):
        # type: (str) -> Any
        return self._keyword_arguments[key]

    def items(self):
        return self._keyword_arguments.items()

    def __contains__(self, item):
        # type: (str) -> bool
        return item in self._keyword_arguments


def setup_calls(setup_script, name_space=None):
    # type: (str, Optional[dict]) -> Dict[str, Tuple[Tuple[Any], Dict[str, Any]]]
    """
    Returns a dictionary mapping the text of a call to setuptools.setup() with a tuple containing the arguments and
    keyword arguments passed to each
    """
    setup_calls_args_kwargs = {}  # type: Dict[str, Tuple[Tuple[Any], Dict[str, Any]]]

    script_parts = re.split(
        r'(\bsetup[\s]*\()',
        setup_script
    )  # type: Sequence[str]

    if name_space is None:
        name_space = {}

    if len(script_parts) > 2:

        for i in range(2, len(script_parts), 2):

            args_kwargs_etc = script_parts[i]

            potential_args_kwargs_parts = args_kwargs_etc.split(')')

            args_kwargs_parts = []

            for args_kwargs_part in potential_args_kwargs_parts:

                args_kwargs_parts.append(args_kwargs_part)

                try:
                    try:
                        exec(
                            (
                                'keyword_arguments = dict(%s)' % ')'.join(args_kwargs_parts)
                            ),
                            name_space
                        )
                        break
                    except:
                        exec(
                            (
                                script_parts[0] + '\n\n' +
                                'keyword_arguments = dict(%s)' % ')'.join(args_kwargs_parts)
                            ),
                            name_space
                        )
                        break
                except SyntaxError:
                    pass
                except NameError as e:
                    e.args = tuple(
                        ['This package can only parse simple `setuptools.setup()` calls--functions and ']
                    )

            keyword_arguments = name_space['keyword_arguments']

            source = script_parts[i-1] + ')'.join(args_kwargs_parts + [''])

            yield SetupCall(
                source,
                keyword_arguments
            )