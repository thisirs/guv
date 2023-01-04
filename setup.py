from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="guv",
    version="0.12.2",
    author="Sylvain Rousseau",
    author_email="sylvain.rousseau@hds.utc.fr",
    description="Programme d'aide à la gestion d'UV",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={"console_scripts": ["guv=guv.runner:main"]},
    include_package_data=True,
    license="MIT",
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
        "yapf",
        "requests"
    ],
)
