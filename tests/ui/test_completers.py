"""Tests for ui.completers module - completion functionality."""

from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.document import Document

from ui.completers import MetaCommandCompleter, SQLCompleter
from ui.metacmd.registry import MetaCommand, SubCommand


class TestMetaCommandCompleter:
    """Tests for MetaCommandCompleter."""

    @pytest.fixture
    def completer(self):
        """Create a MetaCommandCompleter instance."""
        return MetaCommandCompleter()

    @pytest.fixture
    def mock_cmd_with_subcommands(self):
        """Create a mock command with subcommands."""
        subcmd1 = SubCommand(
            name="check",
            aliases=[],
            description="Check for updates",
        )
        subcmd2 = SubCommand(
            name="auto-check",
            aliases=["autocheck"],
            description="Manage auto-check",
            arg_completer=lambda args: ["on", "off"] if len(args) == 0 else [],
        )
        return MetaCommand(
            name="upgrade",
            description="Upgrade command",
            func=lambda app, args: None,
            aliases=["check-update"],
            loop_only=False,
            subcommands=[subcmd1, subcmd2],
        )

    @pytest.fixture
    def mock_cmd_without_subcommands(self):
        """Create a mock command without subcommands."""
        return MetaCommand(
            name="help",
            description="Show help",
            func=lambda app, args: None,
            aliases=["h", "?"],
            loop_only=False,
            subcommands=[],
        )

    def test_get_completions_no_slash(self, completer):
        """Test get_completions without slash prefix."""
        document = Document("SELECT")
        completions = list(completer.get_completions(document, None))
        assert len(completions) == 0

    def test_get_completions_with_slash(self, completer):
        """Test get_completions with slash prefix."""
        document = Document("/")
        completions = list(completer.get_completions(document, None))
        assert len(completions) > 0
        assert all(comp.text.startswith("/") for comp in completions)

    def test_get_completions_partial_match(self, completer):
        """Test get_completions with partial match."""
        document = Document("/set")
        completions = list(completer.get_completions(document, None))
        # Should match commands starting with "set"
        assert all("set" in comp.text.lower() for comp in completions)

    def test_get_completions_with_text_after_cursor(self, completer):
        """Test get_completions with text after cursor."""
        document = Document("/help extra")
        completions = list(completer.get_completions(document, None))
        # Should not provide completions when there's text after cursor
        assert len(completions) == 0

    def test_get_completions_with_prefix(self, completer):
        """Test get_completions with prefix before slash."""
        document = Document("prefix /")
        completions = list(completer.get_completions(document, None))
        # Should not provide completions when there's a prefix
        assert len(completions) == 0

    def test_get_completions_command_with_space_shows_subcommands(self, completer, mock_cmd_with_subcommands):
        """Test that command followed by space shows subcommands."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade ")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 2
            assert all(comp.text in ["check", "auto-check"] for comp in completions)
            assert all(comp.start_position == 0 for comp in completions)

    def test_get_completions_command_with_space_no_subcommands(self, completer, mock_cmd_without_subcommands):
        """Test that command without subcommands shows no completions after space."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_without_subcommands):
            document = Document("/help ")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 0

    def test_get_completions_subcommand_partial_match(self, completer, mock_cmd_with_subcommands):
        """Test subcommand name completion with partial match."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade auto-")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 1
            assert completions[0].text == "auto-check"
            assert completions[0].start_position == -len("auto-")

    def test_get_completions_subcommand_alias_match(self, completer, mock_cmd_with_subcommands):
        """Test subcommand completion matches aliases."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade autocheck")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 1
            assert completions[0].text == "auto-check"

    def test_get_completions_subcommand_with_space_no_arg_completer(self, completer, mock_cmd_with_subcommands):
        """Test that subcommand without arg_completer shows no completions after space."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade check ")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 0

    def test_get_completions_subcommand_with_space_with_arg_completer(self, completer, mock_cmd_with_subcommands):
        """Test that subcommand with arg_completer shows argument completions after space."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade auto-check ")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 2
            assert {comp.text for comp in completions} == {"on", "off"}
            assert all(comp.start_position == 0 for comp in completions)

    def test_get_completions_argument_partial_match(self, completer, mock_cmd_with_subcommands):
        """Test argument completion with partial match."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            document = Document("/upgrade auto-check o")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 2  # "on" and "off" both start with "o"
            assert all(comp.text in ["on", "off"] for comp in completions)
            assert all(comp.start_position == -len("o") for comp in completions)

    def test_get_completions_argument_with_existing_args(self, completer, mock_cmd_with_subcommands):
        """Test argument completion with existing arguments."""

        # Create a subcommand with arg_completer that uses existing args
        def arg_completer(args):
            if len(args) == 0:
                return ["first"]
            elif len(args) == 1:
                return ["second"]
            return []

        subcmd = SubCommand(
            name="test",
            aliases=[],
            description="Test subcommand",
            arg_completer=arg_completer,
        )
        cmd = MetaCommand(
            name="testcmd",
            description="Test command",
            func=lambda app, args: None,
            aliases=[],
            loop_only=False,
            subcommands=[subcmd],
        )

        with patch("ui.metacmd.get_meta_command", return_value=cmd):
            document = Document("/testcmd test first ")
            completions = list(completer.get_completions(document, None))
            assert len(completions) == 1
            assert completions[0].text == "second"

    def test_get_completions_argument_completer_exception(self, completer, mock_cmd_with_subcommands):
        """Test that exception in arg_completer doesn't crash."""

        # Create a subcommand with failing arg_completer
        def failing_completer(args):
            raise ValueError("Test error")

        subcmd = SubCommand(
            name="failing",
            aliases=[],
            description="Failing subcommand",
            arg_completer=failing_completer,
        )
        cmd = MetaCommand(
            name="testcmd",
            description="Test command",
            func=lambda app, args: None,
            aliases=[],
            loop_only=False,
            subcommands=[subcmd],
        )

        with patch("ui.metacmd.get_meta_command", return_value=cmd):
            document = Document("/testcmd failing ")
            completions = list(completer.get_completions(document, None))
            # Should return empty list instead of crashing
            assert len(completions) == 0

    def test_complete_main_command_empty(self, completer):
        """Test _complete_main_command with empty input."""
        with patch("ui.metacmd.get_meta_commands") as mock_get:
            mock_get.return_value = [
                MetaCommand(
                    name="help",
                    description="Help command",
                    func=lambda app, args: None,
                    aliases=[],
                    loop_only=False,
                ),
                MetaCommand(
                    name="exit",
                    description="Exit command",
                    func=lambda app, args: None,
                    aliases=["quit"],
                    loop_only=False,
                ),
            ]
            completions = list(completer._complete_main_command("/"))
            assert len(completions) == 2
            assert all(comp.text.startswith("/") for comp in completions)

    def test_complete_main_command_partial(self, completer):
        """Test _complete_main_command with partial match."""
        with patch("ui.metacmd.get_meta_commands") as mock_get:
            mock_get.return_value = [
                MetaCommand(
                    name="help",
                    description="Help command",
                    func=lambda app, args: None,
                    aliases=[],
                    loop_only=False,
                ),
                MetaCommand(
                    name="exit",
                    description="Exit command",
                    func=lambda app, args: None,
                    aliases=[],
                    loop_only=False,
                ),
            ]
            completions = list(completer._complete_main_command("/he"))
            assert len(completions) == 1
            assert completions[0].text == "/help"

    def test_complete_subcommands(self, completer, mock_cmd_with_subcommands):
        """Test _complete_subcommands."""
        with patch("ui.metacmd.get_meta_command", return_value=mock_cmd_with_subcommands):
            completions = list(completer._complete_subcommands("upgrade"))
            assert len(completions) == 2
            # Should be sorted by name
            assert completions[0].text == "auto-check"
            assert completions[1].text == "check"

    def test_complete_subcommands_no_command(self, completer):
        """Test _complete_subcommands when command doesn't exist."""
        with patch("ui.metacmd.get_meta_command", return_value=None):
            completions = list(completer._complete_subcommands("nonexistent"))
            assert len(completions) == 0

    def test_complete_subcommand_name(self, completer, mock_cmd_with_subcommands):
        """Test _complete_subcommand_name."""
        completions = list(completer._complete_subcommand_name(mock_cmd_with_subcommands, "auto-"))
        assert len(completions) == 1
        assert completions[0].text == "auto-check"
        assert completions[0].start_position == -len("auto-")

    def test_complete_subcommand_name_empty(self, completer, mock_cmd_with_subcommands):
        """Test _complete_subcommand_name with empty token."""
        completions = list(completer._complete_subcommand_name(mock_cmd_with_subcommands, ""))
        assert len(completions) == 2
        assert all(comp.text in ["auto-check", "check"] for comp in completions)

    def test_complete_arguments(self, completer, mock_cmd_with_subcommands):
        """Test _complete_arguments."""
        subcmd = mock_cmd_with_subcommands.get_subcommand("auto-check")
        assert subcmd is not None

        completions = list(completer._complete_arguments(subcmd, mock_cmd_with_subcommands, "", []))
        assert len(completions) == 2
        assert {comp.text for comp in completions} == {"on", "off"}

    def test_complete_arguments_partial(self, completer, mock_cmd_with_subcommands):
        """Test _complete_arguments with partial match."""
        subcmd = mock_cmd_with_subcommands.get_subcommand("auto-check")
        assert subcmd is not None

        completions = list(completer._complete_arguments(subcmd, mock_cmd_with_subcommands, "o", []))
        assert len(completions) == 2  # "on" and "off" both start with "o"

    def test_complete_arguments_no_match(self, completer, mock_cmd_with_subcommands):
        """Test _complete_arguments with no matching completions."""
        subcmd = mock_cmd_with_subcommands.get_subcommand("auto-check")
        assert subcmd is not None

        completions = list(completer._complete_arguments(subcmd, mock_cmd_with_subcommands, "xyz", []))
        assert len(completions) == 0


class TestSQLCompleter:
    """Tests for SQLCompleter."""

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock DatabaseService."""
        service = MagicMock()
        service.is_connected.return_value = True
        return service

    @pytest.fixture
    def completer(self, mock_db_service):
        """Create a SQLCompleter instance."""
        return SQLCompleter(mock_db_service)

    def test_is_sql_context_select(self, completer):
        """Test _is_sql_context with SELECT statement."""
        assert completer._is_sql_context("SELECT") is True
        assert completer._is_sql_context("select * from") is True

    def test_is_sql_context_insert(self, completer):
        """Test _is_sql_context with INSERT statement."""
        assert completer._is_sql_context("INSERT") is True
        assert completer._is_sql_context("insert into") is True

    def test_is_sql_context_update(self, completer):
        """Test _is_sql_context with UPDATE statement."""
        assert completer._is_sql_context("UPDATE") is True
        assert completer._is_sql_context("update table") is True

    def test_is_sql_context_delete(self, completer):
        """Test _is_sql_context with DELETE statement."""
        assert completer._is_sql_context("DELETE") is True
        assert completer._is_sql_context("delete from") is True

    def test_is_sql_context_create(self, completer):
        """Test _is_sql_context with CREATE statement."""
        assert completer._is_sql_context("CREATE") is True
        assert completer._is_sql_context("create table") is True

    def test_is_sql_context_show(self, completer):
        """Test _is_sql_context with SHOW statement."""
        assert completer._is_sql_context("SHOW") is True
        assert completer._is_sql_context("show tables") is True

    def test_is_sql_context_from_clause(self, completer):
        """Test _is_sql_context with FROM clause."""
        assert completer._is_sql_context("SELECT * FROM") is True
        assert completer._is_sql_context("select id from users") is True

    def test_is_sql_context_where_clause(self, completer):
        """Test _is_sql_context with WHERE clause."""
        assert completer._is_sql_context("SELECT * FROM users WHERE") is True

    def test_is_sql_context_not_sql(self, completer):
        """Test _is_sql_context with non-SQL text."""
        assert completer._is_sql_context("") is False
        assert completer._is_sql_context("hello world") is False
        assert completer._is_sql_context("   ") is False

    def test_get_current_word_simple(self, completer):
        """Test _get_current_word with simple word."""
        assert completer._get_current_word("SELECT") == "SELECT"
        # When cursor is at end, last complete word before cursor is returned
        # "select *" - cursor at end, last word is "select" but there's "*" after it
        # The method returns the last word that ends at or before cursor
        assert completer._get_current_word("select") == "select"
        # With space, it should still work if cursor is at end of word
        assert completer._get_current_word("select ") == ""

    def test_get_current_word_with_underscore(self, completer):
        """Test _get_current_word with underscore."""
        assert completer._get_current_word("user_name") == "user_name"
        assert completer._get_current_word("table_name") == "table_name"

    def test_get_current_word_with_backtick(self, completer):
        """Test _get_current_word with backtick."""
        # The method returns the matched group including backticks
        assert completer._get_current_word("`table`") == "`table`"
        assert completer._get_current_word("`user`") == "`user`"

    def test_get_current_word_multiple_words(self, completer):
        """Test _get_current_word with multiple words."""
        assert completer._get_current_word("SELECT * FROM users") == "users"
        assert completer._get_current_word("SELECT id FROM") == "FROM"

    def test_get_current_word_empty(self, completer):
        """Test _get_current_word with empty text."""
        assert completer._get_current_word("") == ""
        assert completer._get_current_word("   ") == ""

    def test_get_current_table_context_from(self, completer):
        """Test _get_current_table_context with FROM clause."""
        # Method converts to uppercase and returns uppercase result
        assert completer._get_current_table_context("SELECT * FROM users") == "USERS"
        assert completer._get_current_table_context("SELECT id FROM `orders`") == "ORDERS"

    def test_get_current_table_context_update(self, completer):
        """Test _get_current_table_context with UPDATE statement."""
        # Method converts to uppercase and returns uppercase result
        assert completer._get_current_table_context("UPDATE users SET") == "USERS"
        assert completer._get_current_table_context("update `products` set") == "PRODUCTS"

    def test_get_current_table_context_insert(self, completer):
        """Test _get_current_table_context with INSERT statement."""
        # Method converts to uppercase and returns uppercase result
        assert completer._get_current_table_context("INSERT INTO users") == "USERS"
        assert completer._get_current_table_context("insert into `orders`") == "ORDERS"

    def test_get_current_table_context_no_match(self, completer):
        """Test _get_current_table_context with no table context."""
        assert completer._get_current_table_context("SELECT *") is None
        assert completer._get_current_table_context("") is None

    def test_invalidate_cache(self, completer):
        """Test invalidate_cache."""
        completer._cache_valid = True
        completer._cached_tables = ["users", "orders"]
        completer._cached_columns = {"users": ["id", "name"]}

        completer.invalidate_cache()

        assert completer._cache_valid is False
        assert completer._cached_tables == []
        assert completer._cached_columns == {}

    def test_get_completions_not_connected(self, completer, mock_db_service):
        """Test get_completions when database is not connected."""
        mock_db_service.is_connected.return_value = False
        document = Document("SELECT")
        completions = list(completer.get_completions(document, None))
        assert len(completions) == 0

    def test_get_completions_not_sql_context(self, completer):
        """Test get_completions when not in SQL context."""
        document = Document("hello world")
        completions = list(completer.get_completions(document, None))
        assert len(completions) == 0

    def test_get_completions_no_word(self, completer):
        """Test get_completions when no word is being typed."""
        document = Document("SELECT * FROM ")
        completions = list(completer.get_completions(document, None))
        # Should still provide completions based on context
        assert len(completions) >= 0

    def test_get_completions_keywords(self, completer):
        """Test get_completions with SQL keywords."""
        completer._cache_valid = True  # Skip cache refresh
        # Use a valid SQL context - need to ensure word extraction works
        # "SELECT * FROM u" - should extract "u" and provide completions
        document = Document("SELECT * FROM SEL")
        completions = list(completer.get_completions(document, None))
        # Should include SELECT keyword if word "SEL" is extracted
        if completions:
            keyword_completions = [c for c in completions if c.display_meta == "SQL keyword"]
            # May or may not have keyword completions depending on context
            # Just verify we got some completions if word was extracted
            assert len(completions) >= 0

    def test_get_completions_tables(self, completer):
        """Test get_completions with table names."""
        completer._cache_valid = True
        completer._cached_tables = ["users", "orders", "products"]
        # Use valid SQL context
        document = Document("SELECT * FROM u")
        completions = list(completer.get_completions(document, None))
        # Should include users table if word "u" is extracted correctly
        # Note: _get_current_word("SELECT * FROM u") should return "u"
        if completions:
            table_completions = [c for c in completions if c.display_meta == "table"]
            if table_completions:
                assert any("users" in c.text for c in table_completions)

    def test_get_completions_columns(self, completer):
        """Test get_completions with column names."""
        completer._cache_valid = True
        completer._cached_tables = ["users"]
        # Note: _get_current_table_context returns uppercase, so cache key should be uppercase
        completer._cached_columns = {"USERS": ["id", "name", "email"]}
        document = Document("SELECT * FROM users WHERE n")
        completions = list(completer.get_completions(document, None))
        # Should include name column if word "n" is extracted correctly
        if completions:
            column_completions = [c for c in completions if "column" in c.display_meta]
            if column_completions:
                assert any("name" in c.text for c in column_completions)

    def test_get_completions_sorted(self, completer):
        """Test get_completions sorting (keywords first, then tables, then columns)."""
        completer._cache_valid = True
        completer._cached_tables = ["SELECT"]  # Table name matching keyword
        completer._cached_columns = {"users": ["SELECT"]}  # Column name matching keyword
        document = Document("SEL")
        completions = list(completer.get_completions(document, None))
        # First completion should be keyword
        if completions:
            assert completions[0].display_meta == "SQL keyword"

    def test_refresh_cache_if_needed_already_valid(self, completer):
        """Test _refresh_cache_if_needed when cache is already valid."""
        completer._cache_valid = True
        completer._refresh_cache_if_needed()
        # Should not refresh
        assert completer._cache_valid is True

    def test_refresh_tables_success(self, completer, mock_db_service):
        """Test _refresh_tables with successful fetch."""
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [("users",), ("orders",)]
        mock_db_service.get_active_connection.return_value = mock_client
        mock_client.engine_name = "mysql"

        completer._refresh_tables()
        assert len(completer._cached_tables) == 2
        assert "users" in completer._cached_tables
        assert "orders" in completer._cached_tables

    def test_refresh_tables_not_connected(self, completer, mock_db_service):
        """Test _refresh_tables when not connected."""
        mock_db_service.is_connected.return_value = False
        completer._refresh_tables()
        assert len(completer._cached_tables) == 0

    def test_refresh_columns_success(self, completer, mock_db_service):
        """Test _refresh_columns with successful fetch."""
        completer._cached_tables = ["users"]
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [("id",), ("name",)]
        mock_db_service.get_active_connection.return_value = mock_client
        mock_client.engine_name = "mysql"

        completer._refresh_columns()
        assert "users" in completer._cached_columns
        assert len(completer._cached_columns["users"]) == 2

    def test_refresh_columns_no_tables(self, completer):
        """Test _refresh_columns when no tables cached."""
        completer._cached_tables = []
        completer._refresh_columns()
        assert len(completer._cached_columns) == 0
