import os

from setuptools import setup, find_packages


dir_path = os.path.abspath(os.path.dirname(__file__))

version_contents = {}
with open(os.path.join(dir_path, "src", "pyfinbot", "version.py"), encoding="utf-8") as f:
    exec(f.read(), version_contents)

with open(os.path.join(dir_path, "README.md"), "r", encoding="utf-8") as file:
    long_description = file.read()


install_requires = [
]


setup(
    name=version_contents["PROJECT_NAME_TEXT"],
    version=version_contents["VERSION"],
    author=version_contents["AUTHOR"],
    author_email=version_contents["AUTHOR_EMAIL"],
    maintainer=version_contents["AUTHOR"],
    maintainer_email=version_contents["AUTHOR_EMAIL"],
    description=version_contents["DESCRIPTION"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=version_contents["URL"],
    packages_dir={"": "src"},
    packages=find_packages(where=version_contents["PROJECT_NAME"]),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Finance :: Database",
    ],
    keywords="python, finance, database",
    python_requires=">=3.10.0",
    install_requires=install_requires,
)
