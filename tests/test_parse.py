from setuptools_setup_versions import install_requires, find


def test_find():
    # type: (...) -> None
    assert find.setup_script_path('../').replace('\\', '/') == '../setup.py'
    assert find.setup_script_path(
        '../setup.py'
    ).replace('\\', '/') == '../setup.py'


def test_install_requires():
    install_requires.update_versions('../', '>=')


if __name__ == '__main__':
    test_find()
    test_install_requires()
