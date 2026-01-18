"""Connect to database interactively."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ui.console import console
from ui.metacmd.registry import meta_command
from ui.metacmd.setup import _run_form, _FormField
from utils.logging import logger

if TYPE_CHECKING:
    from ui.repl import ShellREPL
    from database.types import ConnectionContext


# ========== Base Connector ==========


class BaseConnector(ABC):
    """Base class for database connectors."""

    @abstractmethod
    def can_handle(self, args: list[str]) -> bool:
        """Check if this connector can handle the connection request.

        Args:
            args: Command line arguments

        Returns:
            True if this connector can handle the request, False otherwise
        """
        pass

    @abstractmethod
    async def connect(self, session, args: list[str]) -> ConnectionContext:
        """Execute connection logic and return ConnectionContext.

        Args:
            session: The session object to connect with
            args: Command line arguments

        Returns:
            ConnectionContext with connection status

        Raises:
            Exception: If connection fails
        """
        pass

    def get_display_name(self, connection: ConnectionContext) -> str:
        """Get display name for the connection.

        Args:
            connection: The connection context

        Returns:
            Display name string
        """
        return connection.display_name

    def get_extra_info(self, connection: ConnectionContext) -> list[str]:
        """Get extra information to display after connection.

        Args:
            connection: The connection context

        Returns:
            List of formatted info strings to display
        """
        return []


# ========== MySQL Connector ==========


class MySQLConnector(BaseConnector):
    """MySQL database connector."""

    def can_handle(self, args: list[str]) -> bool:
        """MySQL connector handles requests without URL arguments."""
        if not args:
            return True
        # Check if args contain only empty strings
        url = " ".join(args).strip()
        return not url

    async def connect(self, session, args: list[str]) -> ConnectionContext:
        """Connect to MySQL via interactive form."""
        # Define form fields
        fields = [
            _FormField(
                name="host",
                label="Host",
                default_value="localhost",
                placeholder="Database server hostname",
            ),
            _FormField(
                name="port",
                label="Port",
                default_value="3306",
                placeholder="Database server port",
            ),
            _FormField(
                name="user",
                label="Username",
                placeholder="Database username",
            ),
            _FormField(
                name="password",
                label="Password",
                is_password=True,
                placeholder="Database password (optional)",
            ),
            _FormField(
                name="database",
                label="Database",
                placeholder="Default database name (optional)",
            ),
        ]

        # Run interactive form
        result = await _run_form(title=" Connect to Database (MySQL)", fields=fields)

        if not result.submitted:
            raise ValueError("Connection cancelled by user")

        # Validate required fields
        host = result.values.get("host", "").strip()
        port_str = result.values.get("port", "").strip()
        user = result.values.get("user", "").strip()
        password = result.values.get("password", "").strip() or None
        database = result.values.get("database", "").strip() or None

        if not host:
            raise ValueError("Host is required")
        if not user:
            raise ValueError("Username is required")

        # Parse port
        try:
            port = int(port_str) if port_str else 3306
        except ValueError:
            raise ValueError("Invalid port number")

        # Connect to database
        console.print(f"[dim]Connecting to {user}@{host}:{port}...[/dim]")
        connection = session.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )

        return connection

    def get_extra_info(self, connection: ConnectionContext) -> list[str]:
        """MySQL doesn't have extra info to display."""
        return []


# ========== File/Data Source Connector ==========


class DuckDBConnector(BaseConnector):
    """File and data source connector (uses DuckDB as analysis engine)."""

    # Help information constants
    _SUPPORTED_FORMATS = [
        "[dim]💡 Supported formats:[/dim]",
        "[dim]   • Bare filename: file.csv (searches in current directory)[/dim]",
        "[dim]   • Local file paths: /path/to/file.csv, ./file.csv[/dim]",
        "[dim]   • file:///path/to/file.csv (for local files)[/dim]",
        "[dim]   • http://example.com/file.csv (for HTTP files)[/dim]",
        "[dim]   • https://example.com/file.csv (for HTTPS files)[/dim]",
        "[dim]   • CSV files: file.csv[/dim]",
        "[dim]   • Excel files: file.xlsx (Excel 2007+ format)[/dim]",
        "[dim]   • duckdb:///path/to/db.duckdb (for database files)[/dim]",
    ]

    def _print_supported_formats(self) -> None:
        """Print supported formats help information."""
        for line in self._SUPPORTED_FORMATS:
            console.print(line)

    def can_handle(self, args: list[str]) -> bool:
        """File connector handles URL arguments, local file paths, or bare filenames."""
        if not args:
            return False

        from database.duckdb_loader import DuckDBURLParser

        # Check each argument
        for arg in args:
            arg = arg.strip()
            if not arg:
                continue

            # Check if it has a protocol header
            if DuckDBURLParser.has_protocol(arg):
                return True

            # Check if it's a valid local file path (including bare filenames)
            if DuckDBURLParser.is_local_file_path(arg):
                return True

        return False

    async def connect(self, session, args: list[str]) -> ConnectionContext:
        """Connect to file(s) or data source(s) via URL(s) or local file path(s)."""
        from database.duckdb_loader import DuckDBURLParser
        from database.service import create_duckdb_connection_context

        # Parse URLs from arguments (support multiple files)
        urls: list[str] = []
        for arg in args:
            arg = arg.strip()
            if not arg:
                continue

            # Check if it has a protocol header (http://, https://, file://, duckdb://)
            if DuckDBURLParser.has_protocol(arg):
                urls.append(arg)
            elif DuckDBURLParser.is_local_file_path(arg):
                # Resolve file path (handles bare filenames by searching in current directory)
                try:
                    resolved_path = DuckDBURLParser.resolve_file_path(arg)
                    # Normalize resolved path to file:// URL
                    normalized_url = DuckDBURLParser.normalize_local_path(resolved_path)
                    urls.append(normalized_url)
                except ValueError as e:
                    # File not found or other path resolution error
                    error_msg = str(e)
                    console.print(f"[red]✗ {error_msg}[/red]")
                    self._print_supported_formats()
                    raise
            else:
                # Invalid format
                console.print(f"[red]✗ Invalid file path or URL: {arg}[/red]")
                self._print_supported_formats()
                raise ValueError(f"Invalid file path or URL: {arg}")

        if not urls:
            raise ValueError("At least one file path or URL is required")

        # Validate all URLs can be parsed
        parsed_urls = []
        try:
            for url in urls:
                parsed_url = DuckDBURLParser.parse(url)
                parsed_urls.append(parsed_url)
        except ValueError as e:
            console.print(f"[red]✗ Invalid URL format[/red]")
            console.print(f"[dim]{e}[/dim]")
            raise

        # Determine connection message based on URL type and count
        primary_parsed_url = parsed_urls[0]
        if len(urls) == 1:
            if primary_parsed_url.is_file_protocol:
                message = "Loading data from file..."
            elif primary_parsed_url.is_http_protocol:
                message = "Loading data from remote file..."
            elif primary_parsed_url.is_duckdb_protocol:
                if primary_parsed_url.is_memory:
                    message = "Connecting to in-memory data source..."
                else:
                    message = "Connecting to database file..."
            else:
                message = "Connecting to data source..."
        else:
            # Multiple files
            file_count = len([p for p in parsed_urls if p.is_file_protocol or p.is_http_protocol])
            if file_count == len(urls):
                message = f"Loading data from {len(urls)} files..."
            else:
                message = f"Connecting to {len(urls)} data sources..."

        # Connect to data source
        console.print(f"[dim]{message}[/dim]")

        # Disconnect existing connection if any
        session.disconnect()

        # Create connection context (supports single URL string or list of URLs)
        if len(urls) == 1:
            connection = create_duckdb_connection_context(urls[0])
        else:
            connection = create_duckdb_connection_context(urls)

        if not connection.is_connected:
            raise ValueError(f"Connection failed: {connection.error}")

        # Set connection in session
        session._db_connection = connection

        # Store parsed URLs in connection for later retrieval
        connection._parsed_urls = parsed_urls
        # For backward compatibility, also store primary URL
        connection._parsed_url = primary_parsed_url

        return connection

    def _format_file_load_info(
        self,
        table_name: str,
        row_count: int,
        column_count: int,
        original_url: str = "",
    ) -> str:
        """Format file load information."""
        if original_url:
            return (
                f"[green]✓ Loaded {original_url} → table '{table_name}' "
                f"({row_count} rows, {column_count} columns)[/green]"
            )
        else:
            return f"[green]✓ Loaded table '{table_name}' ({row_count} rows, {column_count} columns)[/green]"

    def get_extra_info(self, connection: ConnectionContext) -> list[str]:
        """Get file load information if available."""
        extra_info = []

        if hasattr(connection.db_service, "_duckdb_load_info"):
            load_info = connection.db_service._duckdb_load_info
            if load_info:
                # Load info is always a list now
                parsed_urls = []
                if hasattr(connection, "_parsed_urls"):
                    parsed_urls = connection._parsed_urls
                elif hasattr(connection, "_parsed_url"):
                    parsed_urls = [connection._parsed_url]

                for i, (table_name, row_count, column_count) in enumerate(load_info):
                    # Get original URL if available
                    original_url = ""
                    if i < len(parsed_urls):
                        original_url = parsed_urls[i].original_url

                    extra_info.append(self._format_file_load_info(table_name, row_count, column_count, original_url))

        return extra_info


# ========== Connection Handler ==========


class ConnectionHandler:
    """Handler for managing database connections."""

    _connectors: list[BaseConnector] = []

    @classmethod
    def register_connector(cls, connector: BaseConnector) -> None:
        """Register a new connector.

        Args:
            connector: The connector instance to register
        """
        cls._connectors.append(connector)

    @classmethod
    async def connect(cls, session, app, args: list[str]) -> None:
        """Handle connection request by routing to appropriate connector.

        Args:
            session: The session object
            app: The ShellREPL application instance
            args: Command line arguments
        """
        # Find a connector that can handle this request
        connector = None
        for c in cls._connectors:
            if c.can_handle(args):
                connector = c
                break

        if connector is None:
            console.print("[red]✗ No connector available for this connection type[/red]")
            console.print("[dim]  Use /connect without arguments for MySQL interactive connection[/dim]")
            console.print(
                "[dim]  Use /connect <filename> to connect to a file in current directory (e.g., flights.csv)[/dim]"
            )
            console.print(
                "[dim]  Use /connect <file> to connect to a local file (e.g., /path/to/file.csv, ./file.csv)[/dim]"
            )
            console.print("[dim]  Use /connect <url> to connect to a remote file or data source[/dim]")
            console.print("[dim]  Use /connect file1.csv file2.csv to connect to multiple files[/dim]")
            return

        # Execute connection
        try:
            connection = await connector.connect(session, args)

            if connection.is_connected:
                # Update app references
                cls._update_app_references(app, connection)

                # Display connection success
                display_name = connector.get_display_name(connection)
                console.print(f"[green]✓ Connected to {display_name}[/green]")

                # Display extra info if available
                extra_info = connector.get_extra_info(connection)
                for info in extra_info:
                    console.print(info)

                # Log connection
                logger.info(
                    "Connected to database via /connect: {display_name}",
                    display_name=display_name,
                )
            else:
                console.print(f"[red]✗ Connection failed: {connection.error}[/red]")
                logger.warning(
                    "Connection failed via /connect: {error}",
                    error=connection.error,
                )
        except ValueError as e:
            # User cancellation or validation errors
            error_msg = str(e)
            if "cancelled" not in error_msg.lower():
                console.print(f"[red]✗ {error_msg}[/red]")
            else:
                console.print("[yellow]Connection cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Connection error: {e}[/red]")
            logger.exception("Connection error via /connect")

    @classmethod
    def _update_app_references(cls, app, connection: ConnectionContext) -> None:
        """Update ShellREPL references after connection.

        Args:
            app: The ShellREPL application instance
            connection: The connection context
        """
        app._db_service = connection.db_service
        app._query_history = connection.query_history
        # Update prompt session's db_service reference to refresh prompt display
        if app.prompt_session:
            app.prompt_session.refresh_db_service(connection.db_service)


# ========== Initialize Connectors ==========


def _initialize_connectors():
    """Initialize and register all connectors."""
    ConnectionHandler.register_connector(MySQLConnector())
    ConnectionHandler.register_connector(DuckDBConnector())


_initialize_connectors()


# ========== Meta Commands ==========


@meta_command(aliases=["conn"])
async def connect(app: ShellREPL, args: list[str]):
    """Connect to a database (MySQL) or data source (files, URLs)."""
    from loop.neoloop import NeoLoop

    # Get session from runtime
    if not isinstance(app.loop, NeoLoop):
        console.print("[red]This command requires NeoLoop runtime[/red]")
        return

    session = app.loop.runtime.session

    # Check if already connected
    if session.is_connected:
        db_conn = session.db_connection
        display_name = db_conn.display_name if db_conn else "unknown"
        console.print(f"[yellow]Already connected to: {display_name}[/yellow]")
        console.print("[dim]Use /disconnect first to disconnect, or continue to connect to a new database.[/dim]")

    # Delegate to ConnectionHandler
    await ConnectionHandler.connect(session, app, args)


@meta_command(aliases=["disconn"])
def disconnect(app: ShellREPL, args: list[str]):
    """Disconnect from the current database."""
    from loop.neoloop import NeoLoop

    if not isinstance(app.loop, NeoLoop):
        console.print("[red]This command requires NeoLoop runtime[/red]")
        return

    session = app.loop.runtime.session

    if not session.is_connected:
        console.print("[yellow]Not connected to any database[/yellow]")
        return

    db_conn = session.db_connection
    display_name = db_conn.display_name if db_conn else "unknown"

    # Disconnect
    session.disconnect()

    # Clear ShellREPL's db_service and query_history references
    app._db_service = None
    app._query_history = None
    # Update prompt session's db_service reference to refresh prompt display
    if app.prompt_session:
        app.prompt_session.refresh_db_service(None)

    console.print(f"[green]✓ Disconnected from {display_name}[/green]")
    logger.info("Disconnected from database via /disconnect")
