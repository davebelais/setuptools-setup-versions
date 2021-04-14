#!/usr/bin/env python3
"""
This script updates installation requirements in ../setup.py
"""
import os
from subprocess import getstatusoutput

from setuptools_setup_versions import requirements


def run(command: str) -> None:
    status: int
    output: str
    print(command)
    status, output = getstatusoutput(command)
    if status:
        raise OSError(output)
    print(output)


if __name__ == "__main__":
    # `cd` into the repository's root directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Update `setup.py` to require currently installed versions of all packages
    requirements.update_setup(default_operator="~=")
    run("black setup.py")
