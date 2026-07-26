import sys
import os
import datetime
import pathlib
import tomllib

# Configuration file for the Sphinx documentation builder.

# -- Project information -----------------------------------------------------


def _project_version() -> str:
    """Read the version from pyproject.toml so it can never go stale here."""
    pyproject = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        with pyproject.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


project = 'VIStk'
copyright = f'2025-{datetime.date.today().year}, bmi CAD Services'
author = 'Elijah Love'
master_doc = 'index'
version = _project_version()
release = version

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
html_static_path = ['_static']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

def setup(app):
    app.add_css_file('VIStk.css')

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_book_theme'
html_title = "VIStk Documentation"

html_theme_options = {
    "home_page_in_toc": True,
    "toc_title": "Table of Contents",
}

nitpicky = False
