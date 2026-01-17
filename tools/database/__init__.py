"""Database analysis tools (engine-agnostic)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .query_analyzer import QueryAnalyzer

__all__ = [
    "QueryAnalyzer",
]
