"""
File: src/veda/providers/base.py
Title: Evidence Provider Abstract Base
Layer: Provider retrieval layer
Status: Merged prototype foundation — Phase 4

Purpose
-------
Defines the abstract contract implemented by every live and fixture
provider.

Public API
----------
EvidenceProvider

Network policy
--------------
This module performs no network I/O and imports no fixture data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import SourceType


class EvidenceProvider(ABC):
    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @property
    @abstractmethod
    def is_fixture(self) -> bool:
        ...

    @abstractmethod
    def retrieve(self, request: ProviderRequest) -> ProviderResult:
        ...
