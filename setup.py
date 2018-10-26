from setuptools import setup

setup(
    name='setuptools-setup-versions',

    version="0.0.5",

    description=(
        "Automatically update setup.py `install_requires` version #'s for PIP packages and increment setup.py version"
    ),

    url='https://bitbucket.org/davebelais/setuptools-setup-versions',

    author='David Belais',
    author_email='david@belais.me',

    classifiers=[
        'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        # 'Programming Language :: Python :: 2.7',
        # 'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.2',
        # 'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],

    keywords='setuptools version install_requires',

    packages=['setuptools_setup_versions'],

    install_requires=[
        "setuptools>=39.0.1",
        "pip>=18.1"
    ]
)


