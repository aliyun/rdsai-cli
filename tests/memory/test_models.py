"""Tests for memory models."""

import pytest

from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry


def test_all_categories_exist():
    assert MemoryCategory.PREFERENCE.value == "preference"
    assert MemoryCategory.DECISION.value == "decision"
    assert MemoryCategory.ENVIRONMENT.value == "environment"
    assert MemoryCategory.FACT.value == "fact"
    assert MemoryCategory.NOTE.value == "note"


def test_memory_entry_defaults():
    entry = MemoryEntry(category=MemoryCategory.NOTE, content="test")
    assert len(entry.id) == 16
    assert entry.tags == []
    assert entry.embedding == []
    assert entry.created_at == ""
    assert entry.updated_at == ""


def test_format_for_context_no_tags():
    entry = MemoryEntry(category=MemoryCategory.FACT, content="MySQL supports window functions")
    assert entry.format_for_context() == "[fact] MySQL supports window functions"


def test_format_for_context_with_tags():
    entry = MemoryEntry(
        category=MemoryCategory.ENVIRONMENT,
        content="Production DB on RDS",
        tags=["production", "aws"],
    )
    assert entry.format_for_context() == "[environment [production, aws]] Production DB on RDS"


def test_content_validation():
    with pytest.raises(Exception):
        MemoryEntry(category=MemoryCategory.NOTE, content="")
    with pytest.raises(Exception):
        MemoryEntry(category=MemoryCategory.NOTE, content="x" * 4001)


def test_create_memory_request():
    request = CreateMemoryRequest(category=MemoryCategory.DECISION, content="Use InnoDB", tags=["mysql"])
    assert request.category == MemoryCategory.DECISION
    assert request.tags == ["mysql"]
