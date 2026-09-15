# Minimal convenience targets for local development.

SPHINXBUILD ?= sphinx-build
SOURCEDIR    = .
BUILDDIR     = _build

.PHONY: html clean

html:
	$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)"

clean:
	$(SPHINXBUILD) -M clean "$(SOURCEDIR)" "$(BUILDDIR)"

