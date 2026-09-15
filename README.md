# Edinburgh Hydro-computation Group website

A small, static Sphinx site for the group’s GitHub Pages repository. It is a deliberately focused starting point: a landing page, research overview, consultancy route, people page and contact details.

## Local preview

Create a virtual environment if you do not already have one, install the requirement, then build:

```bash
python -m pip install -r requirements.txt
make html
open _build/html/index.html
```

The source files are plain reStructuredText. `index.rst` is the landing page; the other top-level `.rst` files map to the navigation.

## Before publishing

1. Replace every bracketed placeholder in `people.rst` and `contact.rst` with verified details.
2. Replace the three example project cards in `research.rst` with a short, current selection.
3. Confirm the group’s agreed name, remit, logo and University affiliation wording.
4. Check the consultancy copy through the University’s relevant contracts or business-development route before making claims about services or terms.
5. In GitHub, set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**.

## Deployment

Pushing to `main` runs `.github/workflows/pages.yml`, which builds the site and deploys it to GitHub Pages. Pull requests run the build check but do not deploy.

The visual design is self-contained in `_static/site.css` and has no external theme or asset dependency.
