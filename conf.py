"""Configuration for the Edinburgh Hydro-computation Group website."""

from datetime import date

project = "Edinburgh Hydro-computation Group"
author = "Edinburgh Hydro-computation Group"
copyright = f"{date.today().year}, {author}"

extensions = ["sphinx.ext.githubpages"]
templates_path = ["_templates"]
exclude_patterns = ["_build", ".venv", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]
html_css_files = ["site.css"]
html_title = "Edinburgh Hydro-computation Group"
html_short_title = "Hydro-computation"
html_show_sourcelink = False
html_show_sphinx = False
html_last_updated_fmt = ""
html_sidebars = {"**": []}
