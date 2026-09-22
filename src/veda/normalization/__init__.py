"""
File: src/veda/normalization/__init__.py
Title: Normalization Package
Layer: Normalization layer
Status: Merged prototype foundation — Phase 5

Purpose
-------
Exports the four public normalizer functions. Downstream phases import
from veda.normalization rather than individual implementation modules.

Public API
----------
normalize_company_facts
normalize_filing_passage
normalize_usaspending_award
normalize_annual_report_passage

Does not
--------
Does not retrieve records, make network calls, import fixture data,
extract claims, detect conflicts, or build assessment packets.

Design notes
------------
The package marker is written last so all sibling modules exist before
the public imports are evaluated.
"""

from veda.normalization.annual_reports import normalize_annual_report_passage
from veda.normalization.filings import normalize_filing_passage
from veda.normalization.sec import normalize_company_facts
from veda.normalization.usaspending import normalize_usaspending_award

__all__ = [
    "normalize_company_facts",
    "normalize_filing_passage",
    "normalize_usaspending_award",
    "normalize_annual_report_passage",
]