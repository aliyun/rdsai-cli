"""Connect to database interactively."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ui.console import console
from ui.metacmd.registry import meta_command
from ui.metacmd.setup import _run_form, _FormField
from utils.logging import logger

if TYPE_CHECKING:
    from ui.repl import ShellREPL


@meta_command(aliases=["conn"])
async def connect(app: ShellREPL, args: list[str]):
    """Connect to a MySQL database interactively."""
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
    result = await _run_form(title=" Connect to MySQL ", fields=fields)

    if not result.submitted:
        console.print("[yellow]Connection cancelled[/yellow]")
        return

    # Validate required fields
    host = result.values.get("host", "").strip()
    port_str = result.values.get("port", "").strip()
    user = result.values.get("user", "").strip()
    password = result.values.get("password", "").strip() or None
    database = result.values.get("database", "").strip() or None

    if not host:
        console.print("[red]Host is required[/red]")
        return
    if not user:
        console.print("[red]Username is required[/red]")
        return

    # Parse port
    try:
        port = int(port_str) if port_str else 3306
    except ValueError:
        console.print("[red]Invalid port number[/red]")
        return

    # Connect to database
    console.print(f"[dim]Connecting to {user}@{host}:{port}...[/dim]")
    try:
        connection = session.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )

        if connection.is_connected:
            console.print(f"[green]✓ Connected to {connection.display_name}[/green]")
            # Update ShellREPL's db_service and query_history references
            app._db_service = connection.db_service
            app._query_history = connection.query_history
            # Update prompt session's db_service reference to refresh prompt display
            if app.prompt_session:
                app.prompt_session.refresh_db_service(connection.db_service)
            logger.info(
                "Connected to database via /connect: {display_name}",
                display_name=connection.display_name,
            )
        else:
            console.print(f"[red]Connection failed: {connection.error}[/red]")
            logger.warning(
                "Connection failed via /connect: {error}",
                error=connection.error,
            )
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
        logger.exception("Connection error via /connect")


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
