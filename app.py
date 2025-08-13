"""Compatibility shim for uvicorn entrypoint.

Run with:
  uvicorn app:app --reload
"""

from allergy_app.main import app  # noqa: F401

 