import sys
import os

# Configuration file for the Sphinx documentation builder.

# -- Project information -----------------------------------------------------

project = 'VIStk'
copyright = '2025, bmi CAD Services'
author = 'Elijah Love'
master_doc = 'index'

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
