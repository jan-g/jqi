import os.path
from setuptools import setup, find_packages


def read_file(fn):
    with open(os.path.join(os.path.dirname(__file__), fn)) as f:
        return f.read()


setup(
    name="jqi",
    version="0.0.1",
    description="An interactive wrapper around jq",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    author="jang",
    author_email="jqi@ioctl.org",
    url="https://github.com/jan-g/jqi",
    license="Apache License 2.0",
    packages=find_packages(exclude=["test.*, *.test", "test*"]),

    entry_points={
        'console_scripts': [
            'jqi = jqi.cmd:main',
        ],
    },

    install_requires=[
        "sh",
        "prompt_toolkit",
    ],

    tests_require=[
        "pytest",
    ],
)
