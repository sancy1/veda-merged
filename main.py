# filename: main.py
# title: Root Entry Point for Deployment Platforms
# description:
#     Deployment platforms such as FastAPI Cloud look for a module
#     named "main" at the repository root by default. This file
#     re-exports the FastAPI application from the merged package so
#     the platform's default discovery works.
#
#     The actual application lives at veda.interfaces.api:app. This
#     file only forwards the symbol.

from veda.interfaces.api import app

__all__ = ["app"]