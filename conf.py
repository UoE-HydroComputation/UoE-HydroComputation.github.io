"""Configuration for the E-COM website."""

from datetime import date

project = "E-COM — Edinburgh Coastal Ocean Modelling Group"
author = "E-COM — Edinburgh Coastal Ocean Modelling Group"
copyright = f"{date.today().year}, {author}"

extensions = ["sphinx.ext.githubpages"]
templates_path = ["_templates"]
exclude_patterns = ["_build", ".venv", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]
html_css_files = ["site.css"]
html_title = "E-COM — Edinburgh Coastal Ocean Modelling Group"
html_short_title = "E-COM"
html_show_sourcelink = False
html_show_sphinx = False
html_last_updated_fmt = ""
html_sidebars = {"**": []}
