from setuptools import setup

setup(
    name='setuptools-setup-versions',
    version="1.4.1",
    description=(
        "Automatically update setup.py `install_requires`, `extras_require`,"
        "and/or `setup_requires` version numbers for PIP packages"
    ),
    author='David Belais',
    author_email='david@belais.me',
    python_requires='~=3.6',
    keywords='setuptools install_requires version',
    packages=[
        'setuptools_setup_versions'
    ],
    install_requires=[
        "setuptools>=50.0",
        "pip~=20.2",
        "more-itertools~=8.5"
    ],
    extras_require={
        "test": [
            "tox~=3.19",
            "pytest~=5.4"
        ],
        "dev": [
            "twine~=3.2",
            "tox~=3.19",
            "pytest~=5.4",
            "wheel~=0.35",
            "readme-md-docstrings>=0.1.0,<1"
        ]
    }
)
