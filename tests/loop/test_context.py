"""Tests for loop.context module."""

from unittest.mock import patch

from loop.context import (
    DATABASE_REMINDER,
    ContextEntry,
    ContextManager,
    ContextType,
    InjectedContext,
    SessionState,
)


class TestContextEntry:
    """Tests for ContextEntry class."""

    def test_init_with_default_tag(self):
        """Test ContextEntry initialization with default tag."""
        entry = ContextEntry(type=ContextType.DATABASE, content="test content")
        assert entry.type == ContextType.DATABASE
        assert entry.content == "test content"
        assert entry.tag == "database_context"
        assert entry.priority == 0

    def test_init_with_custom_tag(self):
        """Test ContextEntry initialization with custom tag."""
        entry = ContextEntry(type=ContextType.QUERY, content="test content", tag="custom_tag", priority=10)
        assert entry.tag == "custom_tag"
        assert entry.priority == 10

    def test_format(self):
        """Test ContextEntry format method."""
        entry = ContextEntry(type=ContextType.DATABASE, content="test content")
        formatted = entry.format()
        assert "<database_context>" in formatted
        assert "</database_context>" in formatted
        assert "test content" in formatted


class TestSessionState:
    """Tests for SessionState class."""

    def test_init(self):
        """Test SessionState initialization."""
        state = SessionState()
        assert not state.is_injected(ContextType.DATABASE)
        assert state.get_cached(ContextType.DATABASE) is None

    def test_mark_injected(self):
        """Test marking context as injected."""
        state = SessionState()
        state.mark_injected(ContextType.DATABASE)
        assert state.is_injected(ContextType.DATABASE)
        assert not state.is_injected(ContextType.QUERY)

    def test_cache_content(self):
        """Test caching content."""
        state = SessionState()
        state.cache_content(ContextType.DATABASE, "cached content")
        assert state.get_cached(ContextType.DATABASE) == "cached content"

    def test_invalidate_cache_specific(self):
        """Test invalidating cache for specific type."""
        state = SessionState()
        state.cache_content(ContextType.DATABASE, "content1")
        state.cache_content(ContextType.QUERY, "content2")
        state.invalidate_cache(ContextType.DATABASE)
        assert state.get_cached(ContextType.DATABASE) is None
        assert state.get_cached(ContextType.QUERY) == "content2"

    def test_invalidate_cache_all(self):
        """Test invalidating all cache."""
        state = SessionState()
        state.cache_content(ContextType.DATABASE, "content1")
        state.cache_content(ContextType.QUERY, "content2")
        state.invalidate_cache()
        assert state.get_cached(ContextType.DATABASE) is None
        assert state.get_cached(ContextType.QUERY) is None

    def test_is_content_changed(self):
        """Test content change detection."""
        state = SessionState()
        assert state.is_content_changed(ContextType.QUERY, "content1") is True
        assert state.is_content_changed(ContextType.QUERY, "content1") is False
        assert state.is_content_changed(ContextType.QUERY, "content2") is True

    def test_clear_content_hash(self):
        """Test clearing content hash."""
        state = SessionState()
        state.is_content_changed(ContextType.QUERY, "content1")
        state.clear_content_hash(ContextType.QUERY)
        # After clearing, should detect as changed again
        assert state.is_content_changed(ContextType.QUERY, "content1") is True

    def test_reset(self):
        """Test resetting session state."""
        state = SessionState()
        state.mark_injected(ContextType.DATABASE)
        state.cache_content(ContextType.DATABASE, "content")
        state.is_content_changed(ContextType.QUERY, "content")
        state.reset()
        assert not state.is_injected(ContextType.DATABASE)
        assert state.get_cached(ContextType.DATABASE) is None
        assert state.is_content_changed(ContextType.QUERY, "content") is True


class TestInjectedContext:
    """Tests for InjectedContext class."""

    def test_init_empty(self):
        """Test InjectedContext initialization with empty parts."""
        context = InjectedContext()
        assert context.is_empty() is True
        assert context.format() == ""

    def test_init_with_parts(self):
        """Test InjectedContext initialization with parts."""
        context = InjectedContext(parts=["part1", "part2"])
        assert context.is_empty() is False
        assert "part1" in context.format()
        assert "part2" in context.format()

    def test_wrap_user_input_empty(self):
        """Test wrapping user input with empty context."""
        context = InjectedContext()
        result = context.wrap_user_input("user input")
        assert result == "user input"

    def test_wrap_user_input_with_context(self):
        """Test wrapping user input with context."""
        context = InjectedContext(parts=["context1", "context2"])
        result = context.wrap_user_input("user input")
        assert "context1" in result
        assert "context2" in result
        assert "user input" in result
        assert result.endswith("user input")


class TestContextManager:
    """Tests for ContextManager class."""

    def test_init(self):
        """Test ContextManager initialization."""
        manager = ContextManager()
        assert not manager.has(ContextType.DATABASE)
        assert not manager.is_database_injected

    def test_add(self):
        """Test adding context entry."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "test content")
        assert manager.has(ContextType.DATABASE)
        entry = manager.get(ContextType.DATABASE)
        assert entry is not None
        assert entry.content == "test content"

    def test_add_empty_content(self):
        """Test adding empty content should not add entry."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "")
        assert not manager.has(ContextType.DATABASE)
        manager.add(ContextType.DATABASE, "   ")
        assert not manager.has(ContextType.DATABASE)

    def test_add_with_custom_tag_and_priority(self):
        """Test adding context with custom tag and priority."""
        manager = ContextManager()
        manager.add(ContextType.QUERY, "content", tag="custom", priority=5)
        entry = manager.get(ContextType.QUERY)
        assert entry.tag == "custom"
        assert entry.priority == 5

    def test_remove(self):
        """Test removing context entry."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "content")
        assert manager.remove(ContextType.DATABASE) is True
        assert not manager.has(ContextType.DATABASE)
        assert manager.remove(ContextType.DATABASE) is False

    def test_get(self):
        """Test getting context entry."""
        manager = ContextManager()
        assert manager.get(ContextType.DATABASE) is None
        manager.add(ContextType.DATABASE, "content")
        entry = manager.get(ContextType.DATABASE)
        assert entry is not None
        assert entry.content == "content"

    def test_has(self):
        """Test checking if context type exists."""
        manager = ContextManager()
        assert not manager.has(ContextType.DATABASE)
        manager.add(ContextType.DATABASE, "content")
        assert manager.has(ContextType.DATABASE)

    def test_clear(self):
        """Test clearing all context entries."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "content1")
        manager.add(ContextType.QUERY, "content2")
        manager.clear()
        assert not manager.has(ContextType.DATABASE)
        assert not manager.has(ContextType.QUERY)

    def test_set_database_context(self):
        """Test setting database context."""
        manager = ContextManager()
        manager.set_database_context("db info")
        assert manager.has(ContextType.DATABASE)
        entry = manager.get(ContextType.DATABASE)
        assert entry.content == "db info"

    def test_set_query_context(self):
        """Test setting query context."""
        manager = ContextManager()
        manager.set_query_context("query result")
        assert manager.has(ContextType.QUERY)
        entry = manager.get(ContextType.QUERY)
        assert entry.content == "query result"

    def test_reset_session(self):
        """Test resetting session."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "content")
        manager._session.mark_injected(ContextType.DATABASE)
        manager.reset_session()
        assert not manager.has(ContextType.DATABASE)
        assert not manager.is_database_injected

    @patch("loop.context._load_database_connection_info")
    def test_build_without_database_connection(self, mock_load):
        """Test build without database connection."""
        mock_load.return_value = None
        manager = ContextManager()
        context = manager.build()
        assert context.is_empty()

    @patch("loop.context._load_database_connection_info")
    def test_build_with_database_connection_first_time(self, mock_load):
        """Test build with database connection first time."""
        mock_load.return_value = "Host: localhost\nPort: 3306"
        manager = ContextManager()
        context = manager.build()
        assert not context.is_empty()
        assert "localhost" in context.format()
        assert manager.is_database_injected

    @patch("loop.context._load_database_connection_info")
    def test_build_with_database_connection_subsequent(self, mock_load):
        """Test build with database connection subsequent times."""
        mock_load.return_value = "Host: localhost\nPort: 3306"
        manager = ContextManager()
        # First build
        context1 = manager.build()
        assert manager.is_database_injected
        # Second build should use reminder
        context2 = manager.build()
        assert DATABASE_REMINDER in context2.format()

    @patch("loop.context._load_database_connection_info")
    def test_build_with_query_context_unchanged(self, mock_load):
        """Test build with unchanged query context."""
        mock_load.return_value = None
        manager = ContextManager()
        manager.set_query_context("same content")
        context1 = manager.build()
        assert "same content" in context1.format()
        # Set same content again
        manager.set_query_context("same content")
        context2 = manager.build()
        # Should not include duplicate query context
        assert context2.format().count("same content") == 0

    @patch("loop.context._load_database_connection_info")
    def test_build_with_query_context_changed(self, mock_load):
        """Test build with changed query context."""
        mock_load.return_value = None
        manager = ContextManager()
        manager.set_query_context("content1")
        context1 = manager.build()
        assert "content1" in context1.format()
        # Set different content
        manager.set_query_context("content2")
        context2 = manager.build()
        assert "content2" in context2.format()

    @patch("loop.context._load_database_connection_info")
    def test_build_priority_ordering(self, mock_load):
        """Test build respects priority ordering."""
        mock_load.return_value = None
        manager = ContextManager()
        manager.add(ContextType.QUERY, "query", priority=1)
        manager.add(ContextType.DATABASE, "database", priority=2)
        context = manager.build()
        parts = context.format().split("\n\n")
        # Higher priority should come first
        assert "database" in parts[0] or parts[0] == "database"

    @patch("loop.context._load_database_connection_info")
    def test_build_database_connection_changed(self, mock_load):
        """Test build when database connection info changes."""
        manager = ContextManager()
        # First connection
        mock_load.return_value = "Host: localhost\nPort: 3306"
        context1 = manager.build()
        assert manager.is_database_injected
        # Connection changed
        mock_load.return_value = "Host: newhost\nPort: 3307"
        context2 = manager.build()
        # Should reset injection state and inject full info again
        assert "newhost" in context2.format()
        assert manager.is_database_injected

    def test_wrap_user_input(self):
        """Test wrap_user_input convenience method."""
        manager = ContextManager()
        manager.add(ContextType.DATABASE, "db info")
        result = manager.wrap_user_input("user query")
        assert "db info" in result
        assert "user query" in result
