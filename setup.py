# Copyright (C) 2014 Mejorando.la - www.mejorando.la
# Yohan Graterol - <y@mejorando.la>
import sys
import os
import subprocess

from setuptools import setup

data_files = [('etc', ['etc/myapp.cfg'])]

PUBLISH_CMD = "python setup.py register sdist upload"
TEST_PUBLISH_CMD = 'python setup.py register -r test sdist upload -r test'

if 'publish' in sys.argv:
    status = subprocess.call(PUBLISH_CMD, shell=True)
    sys.exit(status)

if 'publish_test' in sys.argv:
    status = subprocess.call(TEST_PUBLISH_CMD, shell=True)
    sys.exit()


def read(fname):
    with open(fname) as fp:
        content = fp.read()
    return content

setup(
    name='zoort',
    version="0.1.6",
    description='A Python script for automatic MongoDB backups',
    long_description=read("README.rst"),
    author='Yohan Graterol',
    author_email='y@mejorando.la | yograterol@fedoraproject.org',
    url='https://github.com/yograterol/zoort',
    install_requires=['docopt', 'fabric', 'boto', 'requests',
                      'python-dateutil', 'sqlalchemy'],
    license=read("LICENSE"),
    zip_safe=False,
    keywords='zoort, mongodb, backups',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    py_modules=["zoort"],
    entry_points={
        'console_scripts': [
            "zoort = zoort:main"
        ]
    },
    include_package_data=True,
    data_files=[('/etc/zoort', ['etc/config.json', ])]
)
