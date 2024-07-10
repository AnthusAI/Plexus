# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Plexus'
copyright = '2024, Anthus AI Solutions'
author = 'Anthus AI Solutions'
release = '0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
]

templates_path = ['_templates']
exclude_patterns = [
    '*_test.*'
]

import os
import sys
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'plexus'))
sys.path.insert(0, basedir)

autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'show-inheritance': False,
    'special-members': '__init__',
}
autoclass_content = 'both'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
