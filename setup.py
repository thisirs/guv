from setuptools import setup

from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="doit_utc",
    version="0.1",
    author="Sylvain Rousseau",
    author_email="sylvain.rousseau@hds.utc.fr",
    description="Programme d'aide à la gestion d'une UV",
    long_description=long_description,
    long_description_content_type="text/markdown",
    entry_points={"console_scripts": ["doit-utc=doit_utc.runner:main"]},
    license="MIT",
    packages=["doit_utc"],
    zip_safe=False,
    install_requires=[
        "datetime",
        "doit",
        "icalendar",
        "jinja2",
        "latex",
        "markdown",
        "numpy",
        "openpyxl",
        "pandas",
        "pynliner",
        "PyPDF2",
        "tabula-py",
        "unidecode",
        "oyaml",
        "aiohttp",
        "browser_cookie3",
        "xlrd",
        "schema",
    ],
)
