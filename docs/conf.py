# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))
import empd_admin
try:
    import sphinx_bootstrap_theme
except ImportError:
    sphinx_bootstrap_theme = None


# -- Project information -----------------------------------------------------

project = 'EMPD-admin'
copyright = '2019, Philipp S. Sommer'
author = 'Philipp S. Sommer'

# The full version, including alpha/beta/rc tags
release = empd_admin.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.githubpages',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'autodocsumm',
    'sphinxarg.ext',
    'IPython.sphinxext.ipython_console_highlighting',
    'IPython.sphinxext.ipython_directive',
    'sphinxcontrib.programoutput'
]

autodoc_default_options = {
    'autosummary': True,
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
if sphinx_bootstrap_theme:
    html_theme = 'bootstrap'
    html_theme_path = sphinx_bootstrap_theme.get_html_theme_path()
    html_theme_options = {
        'navbar_links': [
            ('EMPD2.github.io', 'https://EMPD2.github.io', True),
        ],
    }
else:
    html_theme = 'alabaster'


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_sidebars = {
    '**': []  # disable sidebar
    }

intersphinx_mapping = {
    'pandas': ('http://pandas.pydata.org/pandas-docs/stable/', None),
    'numpy': ('https://docs.scipy.org/doc/numpy/', None),
    'python': ('https://docs.python.org/3.7/', None),
    'git': ('https://gitpython.readthedocs.io/en/stable/', None),
    'github': ('https://pygithub.readthedocs.io/en/latest/', None),
}
