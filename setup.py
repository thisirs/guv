from setuptools import setup

setup(name='doit_utc',
      version='0.1',
      author='Sylvain Rousseau',
      author_email='sylvain.rousseau@hds.utc.fr',
      entry_points={
          'console_scripts': ['doit-utc=doit_utc.runner:main']
      },
      license='MIT',
      packages=['doit_utc'],
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
          "browser_cookie3"
      ]
)
