"""Tests for memory store."""

from memory.models import MemoryCategory, MemoryEntry
from memory.store import MAX_MEMORIES, MemoryStore


def test_save_and_count(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        entry = store.save(MemoryEntry(category=MemoryCategory.NOTE, content="test"))
        assert entry.created_at
        assert entry.updated_at
        assert store.count() == 1
    finally:
        store.close()


def test_save_with_embedding(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="test", embedding=[0.1, 0.2]))
        assert store.list_all()[0].embedding == [0.1, 0.2]
    finally:
        store.close()


def test_save_enforces_limit(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        for index in range(MAX_MEMORIES):
            store.save(MemoryEntry(category=MemoryCategory.NOTE, content=f"entry {index}"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="new entry"))
        contents = [entry.content for entry in store.list_all(limit=MAX_MEMORIES)]
        assert store.count() == MAX_MEMORIES
        assert "entry 0" not in contents
        assert "new entry" in contents
    finally:
        store.close()


def test_fts_search_and_category_filter(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="MySQL slow query optimization"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="MySQL general tips"))
        results = store.search("MySQL slow", category=MemoryCategory.FACT)
        assert len(results) == 1
        assert results[0].category == MemoryCategory.FACT
        assert "slow query" in results[0].content
    finally:
        store.close()


def test_empty_and_no_result_search(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="hello world"))
        assert store.search("") == []
        assert store.search("nonexistent xyz") == []
    finally:
        store.close()


def test_embedding_search(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        first = store.save(MemoryEntry(category=MemoryCategory.NOTE, content="a", embedding=[1.0, 0.0]))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="b", embedding=[0.0, 1.0]))
        results = store.search_by_embedding([0.9, 0.1])
        assert results[0].id == first.id
    finally:
        store.close()


def test_delete_removes_from_search(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        entry = store.save(MemoryEntry(category=MemoryCategory.FACT, content="unique searchable content"))
        assert store.delete(entry.id) is True
        assert store.delete("missing") is False
        assert store.search("unique searchable") == []
    finally:
        store.close()


def test_list_order_category_and_pagination(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    try:
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="first"))
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="second"))
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="third"))
        assert store.list_all(limit=10)[0].content == "third"
        assert store.count(category=MemoryCategory.FACT) == 2
        assert len(store.list_all(limit=1, offset=1)) == 1
    finally:
        store.close()
