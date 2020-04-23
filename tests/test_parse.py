from urllib.parse import urljoin

from setuptools_setup_versions import parse, find


def test_parse():
    # type: (...) -> None
    with parse.SetupScript(
        find.setup_script_path(urljoin(__file__, '../'))
    ) as setup_script:
        for setup_call in setup_script.setup_calls:
            print(repr(setup_call))


if __name__ == '__main__':
    test_parse()
