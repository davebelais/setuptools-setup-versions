from setuptools import setup, find_packages

setup(
    name='setuptools-setup-versions',
    version="0.0.30",
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
        "setuptools>=39.0.1",
        "pip>=19.1.1",
        "more-itertools>=7.1.0"
    ]
)
