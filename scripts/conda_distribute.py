# !/usr/bin/python3
import os
from tempfile import gettempdir
from subprocess import getstatusoutput
from setuptools_setup_versions import install_requires

REPOSITORY_DIRECTORY = os.path.dirname(
    os.path.dirname(
        __file__
    )
)
PACKAGE_NAME = REPOSITORY_DIRECTORY.split('/')[-1].split('\\')[-1]


def run(command: str) -> str:
    status, output = getstatusoutput(command)
    # Create an error if a non-zero exit status is encountered
    if status:
        raise OSError(output)
    else:
        print(output)
    return output


if __name__ == '__main__':
    try:
        # Create recipe
        directory: str = gettempdir() + '/conda-skeleton'
        os.makedirs(directory, exist_ok=True)
        os.chdir(directory)
        run(
            'conda skeleton pypi ' + PACKAGE_NAME
        )
        # Build
        run(
            'conda config --set anaconda_upload yes'
        )
        run(
            'conda-build ' + PACKAGE_NAME
        )
    finally:
        exec(
            open('./clean.py').read(),
            {'__file__': os.path.abspath('./clean.py')}
        )

