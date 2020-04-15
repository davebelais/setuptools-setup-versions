from setuptools import setup, find_packages

setup(
    name='setuptools-setup-versions',
    version="0.0.33",
    description=(
        "Automatically update setup.py `install_requires` version numbers"
        "for PIP packages"
    ),
    author='David Belais',
    author_email='david@belais.me',
    python_requires='>=3.4',
    keywords='setuptools install_requires version',
    packages=find_packages(),
    install_requires=[
        "setuptools~=46.1.3",
        "pip~=20.0.2",
        "more-itertools~=8.2.0"
    ],
    extras_require={
        "test": [
            "pytest~=5.4.1"
        ],
        "dev": [
            "pytest~=5.4.1",
            "wheel~=0.34.2",
            "readme-md-docstrings~=0.0.10"
        ]
    }
)
