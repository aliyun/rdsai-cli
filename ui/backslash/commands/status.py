"""Status command implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)
from ui.console import console

if TYPE_CHECKING:
    from database import DatabaseService


@backslash_command(
    char="s",
    name="status",
    category=CommandCategory.SESSION,
)
def cmd_status(ctx: CommandContext) -> CommandResult | None:
    """Get status information from the server."""
    if not ctx.db_service or not ctx.db_service.is_connected():
        console.print("[red]Not connected to server.[/red]")
        return CommandResult(success=False)

    console.print("-" * 60)

    # Connection info
    info = ctx.db_service.get_connection_info()
    console.print(f"Connection id:\t\t{info.get('connection_id', 'N/A')}")

    # Current database and user
    current_db = info.get("database") or ""
    console.print(f"Current database:\t{current_db}")

    current_user = _get_current_user(ctx.db_service)
    console.print(f"Current user:\t\t{current_user}")

    # SSL status
    ssl_status = _get_ssl_status(ctx.db_service)
    console.print(f"SSL:\t\t\t{ssl_status}")

    # Server version
    version = _get_server_version(ctx.db_service)
    console.print(f"Server version:\t\t{version}")

    # Protocol version
    protocol = _get_protocol_version(ctx.db_service)
    if protocol:
        console.print(f"Protocol version:\t{protocol}")

    # Connection type
    host = info.get("host", "localhost")
    port = info.get("port", 3306)
    console.print(f"Connection:\t\t{host} via TCP/IP")
    console.print(f"TCP port:\t\t{port}")

    # Character sets
    charsets = _get_character_sets(ctx.db_service)
    if charsets:
        console.print(f"Server characterset:\t{charsets.get('server', 'N/A')}")
        console.print(f"Db     characterset:\t{charsets.get('database', 'N/A')}")
        console.print(f"Client characterset:\t{charsets.get('client', 'N/A')}")
        console.print(f"Conn.  characterset:\t{charsets.get('connection', 'N/A')}")

    # Transaction and autocommit state
    tx_state = info.get("transaction_state", "NOT_IN_TRANSACTION")
    autocommit = info.get("autocommit", True)
    console.print(f"Autocommit:\t\t{'on' if autocommit else 'off'}")

    if tx_state != "NOT_IN_TRANSACTION":
        console.print(f"Transaction:\t\t[yellow]active[/yellow]")

    # Server uptime and statistics
    stats = _get_server_stats(ctx.db_service)
    if stats:
        if "uptime" in stats:
            console.print(f"\nUptime:\t\t\t{_format_uptime(stats['uptime'])}")
        if "threads" in stats:
            console.print(f"Threads:\t\t{stats['threads']}")
        if "questions" in stats:
            console.print(f"Questions:\t\t{stats['questions']}")
        if "slow_queries" in stats:
            console.print(f"Slow queries:\t\t{stats['slow_queries']}")

    console.print("-" * 60)
    return None


def _get_current_user(db_service: DatabaseService) -> str:
    """Get current user from server."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return "N/A"
        client.execute("SELECT USER()")
        result = client.fetchone()
        return result[0] if result else "N/A"
    except Exception:
        return "N/A"


def _get_server_version(db_service: DatabaseService) -> str:
    """Get server version."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return "N/A"
        client.execute("SELECT VERSION()")
        result = client.fetchone()
        return result[0] if result else "N/A"
    except Exception:
        return "N/A"


def _get_protocol_version(db_service: DatabaseService) -> str | None:
    """Get protocol version."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return None
        # This is MySQL-specific
        if hasattr(client, "conn") and hasattr(client.conn, "_protocol_version"):
            return str(client.conn._protocol_version)
        return None
    except Exception:
        return None


def _get_ssl_status(db_service: DatabaseService) -> str:
    """Get SSL connection status."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return "Not in use"
        client.execute("SHOW STATUS LIKE 'Ssl_cipher'")
        result = client.fetchone()
        if result and result[1]:
            return f"Cipher in use is {result[1]}"
        return "Not in use"
    except Exception:
        return "Not in use"


def _get_character_sets(db_service: DatabaseService) -> dict[str, str]:
    """Get character set information."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return {}
        client.execute("""
            SELECT @@character_set_client, @@character_set_connection,
                   @@character_set_server, @@character_set_database
        """)
        result = client.fetchone()
        if result:
            return {
                "client": result[0] or "N/A",
                "connection": result[1] or "N/A",
                "server": result[2] or "N/A",
                "database": result[3] or "N/A",
            }
        return {}
    except Exception:
        return {}


def _get_server_stats(db_service: DatabaseService) -> dict[str, int]:
    """Get server statistics."""
    try:
        client = db_service.get_active_connection()
        if not client:
            return {}

        stats: dict[str, int] = {}

        # Get uptime
        client.execute("SHOW GLOBAL STATUS LIKE 'Uptime'")
        result = client.fetchone()
        if result:
            stats["uptime"] = int(result[1])

        # Get threads
        client.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
        result = client.fetchone()
        if result:
            stats["threads"] = int(result[1])

        # Get questions
        client.execute("SHOW GLOBAL STATUS LIKE 'Questions'")
        result = client.fetchone()
        if result:
            stats["questions"] = int(result[1])

        # Get slow queries
        client.execute("SHOW GLOBAL STATUS LIKE 'Slow_queries'")
        result = client.fetchone()
        if result:
            stats["slow_queries"] = int(result[1])

        return stats
    except Exception:
        return {}


def _format_uptime(seconds: int) -> str:
    """Format uptime in human-readable form."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} min")
    if secs > 0 or not parts:
        parts.append(f"{secs} sec")

    return " ".join(parts)
