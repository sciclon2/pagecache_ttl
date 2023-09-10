import inspect
import os
import sys

from setuptools import find_packages, setup, Extension
from setuptools.command.test import test as TestCommand

__location__ = os.path.join(
    os.getcwd(), os.path.dirname(inspect.getfile(inspect.currentframe()))
)

version = "0.0.30"


def get_install_requirements(path):
    content = open(os.path.join(__location__, path)).read()
    requires = [req for req in content.split("\\n") if req != ""]
    return requires


setup(
    name="pagecache_ttl",
    version=version,
    description="Monitor the minimal TTL of cached pages by the OS",
    author="Datastreaming",
    author_email="storage@adevinta.com",
    packages=find_packages(include=["pagecache"]),
    install_requires=get_install_requirements("requirements/requirements.txt"),
    test_suite="tests",
    zip_safe=False,
    entry_points={"console_scripts": ["pagecache=pagecache.cli:main"]},
    ext_modules=[
          Extension('cache', ['pagecache/src/cachemodule.c']),
      ],
)
