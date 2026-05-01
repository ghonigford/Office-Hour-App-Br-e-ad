"""Top-level conftest.

Having an empty ``conftest.py`` at the project root makes pytest treat the
repository root as the ``rootdir`` and adds it to ``sys.path`` so test modules
can do ``from optimize import ...`` and ``from app import ...`` without any
extra packaging boilerplate.
"""
