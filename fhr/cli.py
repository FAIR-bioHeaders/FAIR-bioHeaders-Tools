"""Checkout marker for FAIR-bioHeaders-Specification's conformance script; not installed.

``scripts/check_conformance.py --converter CHECKOUT`` recognizes a converter
checkout by this file and imports ``fhr.cli``, which the root ``fhr.py`` module
makes an alias of ``bioheaders.cli``. ``fhr_schema.json`` here is likewise the
schema copy that ``scripts/check_release.py`` compares. Without an
``__init__.py`` this directory is not imported; ``import fhr`` loads ``fhr.py``.
"""

from bioheaders.cli import *  # noqa: F401,F403
