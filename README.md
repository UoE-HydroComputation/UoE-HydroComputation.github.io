# E-COM — Edinburgh Coastal Ocean Modelling Group website

A small, static Sphinx site for the group’s GitHub Pages repository. It is a deliberately focused starting point: a landing page, research overview, consultancy route, people page and contact details.

## Local preview

Create a virtual environment if you do not already have one, install the requirement, then build:

```bash
python -m pip install -r requirements.txt
make html
open _build/html/index.html
```

The source files are plain reStructuredText. `index.rst` is the landing page; the other top-level `.rst` files map to the navigation.

## Publications

The editable, group-owned publication record is [`Publications.bib`](Publications.bib). The Publications page uses BibBase to render this file as a live bibliography. To add or correct an entry, edit the BibTeX file, commit it and allow the Pages deployment to complete. No manual changes to `publications.rst` are needed for ordinary bibliography updates.

## Before publishing

1. Replace every bracketed placeholder in `people.rst` and `contact.rst` with verified details.
2. Replace the three example project cards in `research.rst` with a short, current selection.
3. Configure the enquiry form, as described below.
4. Confirm the E-COM remit, logo and University affiliation wording.
5. Check the consultancy copy through the University’s relevant contracts or business-development route before making claims about services or terms.
6. In GitHub, set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**.

## Enquiry form setup

The native-styled form in `contact.rst` uses [Formspree](https://formspree.io/) as its submission service. GitHub Pages cannot send email itself. Formspree receives a submission and sends notification emails without exposing the recipient addresses in the public source code.

1. Create a Formspree account using the group’s agreed owner account, then create a new form.
2. In Formspree, add `a.angeloudis@ed.ac.uk` and `c.jordan@ed.ac.uk` as notification recipients. Confirm both addresses through the verification emails. If the selected Formspree plan only permits one recipient, use an approved University shared mailbox or distribution list as that recipient instead.
3. Copy the form endpoint ID—for example, `xabcdeyz` from `https://formspree.io/f/xabcdeyz`—into the `action` value in `contact.rst`, replacing `REPLACE_WITH_FORMSPREE_FORM_ID`.
4. Submit a test using the live Pages site. The notification subject is set in the form as `[E-COM-Enquiry] New website enquiry`; retain that prefix for consistent filtering.
5. Confirm with the appropriate University team that Formspree is an acceptable processor for basic contact information. The form deliberately asks for minimal personal data and warns users not to send sensitive or confidential material.

## Deployment

Pushing to `main` runs `.github/workflows/pages.yml`, which builds the site and deploys it to GitHub Pages. Pull requests run the build check but do not deploy.

The visual design is self-contained in `_static/site.css` and has no external theme or asset dependency.
