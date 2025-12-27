"""MCP server management meta commands."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.table import Table

from loop import NeoLoop
from tools.mcp.client import get_connection_pool
from tools.mcp.config import MCPServerConfig
from tools.mcp.toolset import MCPTool, connect_and_load_tools
from ui.console import console
from ui.metacmd.registry import SubCommand, meta_command
from utils.logging import logger

if TYPE_CHECKING:
    from ui.repl import ShellREPL


MCP_CONNECT_TIMEOUT = 60  # seconds


def _mcp_server_name_completer(args: list[str]) -> list[str]:
    """Provide server name completions for MCP subcommands."""
    # This will be called dynamically, so we need to get the app instance
    # For now, return empty list - can be enhanced later with dynamic lookup
    return []


@meta_command(
    loop_only=True,
    subcommands=[
        SubCommand(name="list", aliases=["ls"], description="List all configured MCP servers"),
        SubCommand(
            name="view",
            aliases=["info"],
            description="View details of a server",
            arg_completer=_mcp_server_name_completer,
        ),
        SubCommand(
            name="connect", aliases=[], description="Connect to a server", arg_completer=_mcp_server_name_completer
        ),
        SubCommand(
            name="disconnect",
            aliases=[],
            description="Disconnect from a server",
            arg_completer=_mcp_server_name_completer,
        ),
        SubCommand(name="enable", aliases=[], description="Enable a server", arg_completer=_mcp_server_name_completer),
        SubCommand(
            name="disable", aliases=[], description="Disable a server", arg_completer=_mcp_server_name_completer
        ),
        SubCommand(name="reload", aliases=[], description="Reload MCP configuration"),
    ],
)
async def mcp(app: ShellREPL, args: list[str]):
    """Manage MCP servers. Usage: /mcp [list|view|connect|disconnect|enable|disable|reload]"""
    assert isinstance(app.loop, NeoLoop)

    if not args:
        _mcp_list(app)
        return

    subcommand = args[0].lower()
    subargs = args[1:]

    match subcommand:
        case "list" | "ls":
            _mcp_list(app)
        case "view" | "info":
            if not subargs:
                console.print("[red]Usage: /mcp view <server_name>[/red]")
                return
            _mcp_view(app, subargs[0])
        case "connect":
            if not subargs:
                console.print("[red]Usage: /mcp connect <server_name>[/red]")
                return
            await _mcp_connect(app, subargs[0])
        case "disconnect":
            if not subargs:
                console.print("[red]Usage: /mcp disconnect <server_name>[/red]")
                return
            await _mcp_disconnect(app, subargs[0])
        case "enable":
            if not subargs:
                console.print("[red]Usage: /mcp enable <server_name>[/red]")
                return
            await _mcp_set_enabled(app, subargs[0], True)
        case "disable":
            if not subargs:
                console.print("[red]Usage: /mcp disable <server_name>[/red]")
                return
            await _mcp_set_enabled(app, subargs[0], False)
        case "reload":
            await _mcp_reload(app)
        case _:
            console.print(f"[red]Unknown command: {subcommand}[/red]")
            console.print("[dim]Usage: /mcp [list|view|connect|disconnect|enable|disable|reload][/dim]")


def _mcp_list(app: ShellREPL):
    """List all configured MCP servers and their status."""
    assert isinstance(app.loop, NeoLoop)

    mcp_config = app.loop.runtime.mcp_config
    if not mcp_config or not mcp_config.servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        console.print("[dim]Add servers to ~/.rdsai-cli/mcp.yaml[/dim]")
        return

    pool = get_connection_pool()

    table = Table(show_header=True, header_style="bold", expand=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Transport", style="dim")
    table.add_column("Enabled", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Tools", justify="right", style="dim")

    for idx, server in enumerate(mcp_config.servers, 1):
        is_connected = pool.is_connected(server.name)
        is_connecting = pool.is_connecting(server.name)

        # Enabled indicator
        enabled_str = "[green]✓[/green]" if server.enabled else "[dim]○[/dim]"

        # Status indicator
        if is_connected:
            status_str = "[green]● Connected[/green]"
            # Count tools from this server
            tool_count = _count_server_tools(app, server.name)
            tools_str = str(tool_count) if tool_count > 0 else "-"
        elif is_connecting:
            status_str = "[yellow]◐ Connecting...[/yellow]"
            tools_str = "-"
        else:
            status_str = "[dim]○ Disconnected[/dim]"
            tools_str = "-"

        table.add_row(
            str(idx),
            f"[cyan]{server.name}[/cyan]",
            server.transport,
            enabled_str,
            status_str,
            tools_str,
        )

    console.print(table)
    console.print()
    console.print(
        "[dim]Commands: /mcp view <name>, /mcp connect <name>, "
        "/mcp disconnect <name>, /mcp enable <name>, /mcp disable <name>[/dim]"
    )


def _count_server_tools(app: ShellREPL, server_name: str) -> int:
    """Count tools loaded from a specific MCP server."""
    assert isinstance(app.loop, NeoLoop)
    count = 0
    for tool in app.loop.toolset.tools:
        if isinstance(tool, MCPTool) and tool._server_name == server_name:
            count += 1
    return count


async def _mcp_connect(app: ShellREPL, server_name: str):
    """Connect to an MCP server with timeout."""
    assert isinstance(app.loop, NeoLoop)

    mcp_config = app.loop.runtime.mcp_config
    if not mcp_config:
        console.print("[red]No MCP configuration loaded.[/red]")
        return

    server = mcp_config.get_server(server_name)
    if not server:
        console.print(f"[red]Server '{server_name}' not found in config.[/red]")
        console.print("[dim]Use /mcp list to see available servers.[/dim]")
        return

    # Check if server is enabled
    if not server.enabled:
        console.print(f"[yellow]Server '{server_name}' is not enabled.[/yellow]")
        console.print(f"[dim]Use /mcp enable {server_name} to enable it first.[/dim]")
        return

    pool = get_connection_pool()

    if pool.is_connected(server_name):
        console.print(f"[yellow]Server '{server_name}' is already connected.[/yellow]")
        return

    console.print(f"[dim]Connecting to {server_name} ({server.transport})...[/dim]")

    try:
        # Connect with timeout and get tools
        tools = await asyncio.wait_for(connect_and_load_tools(server), timeout=MCP_CONNECT_TIMEOUT)

        # Add tools to the dynamic toolset
        added_count = app.loop.toolset.add_tools(tools)

        logger.info(
            "MCP connect: server={name}, tools_loaded={loaded}, tools_added={added}, toolset_version={version}",
            name=server_name,
            loaded=len(tools),
            added=added_count,
            version=app.loop.toolset.version,
        )

        console.print(f"[green]✓[/green] Connected to [cyan]{server_name}[/cyan]. Loaded {added_count} tools.")

    except asyncio.TimeoutError:
        logger.error("Timeout connecting to MCP server: {name}", name=server_name)
        console.print(f"[red]✗ Connection timeout ({MCP_CONNECT_TIMEOUT}s)[/red]")
    except Exception as e:
        logger.error("Failed to connect to MCP server: {error}", error=e)
        console.print(f"[red]✗ Failed to connect: {e}[/red]")


async def _mcp_disconnect(app: ShellREPL, server_name: str):
    """Disconnect from an MCP server."""
    assert isinstance(app.loop, NeoLoop)

    pool = get_connection_pool()

    if not pool.is_connected(server_name):
        console.print(f"[yellow]Server '{server_name}' is not connected.[/yellow]")
        return

    # Remove tools from this server using DynamicToolset API
    removed_count = app.loop.toolset.remove_tools_by(lambda t: isinstance(t, MCPTool) and t._server_name == server_name)

    logger.info(
        "MCP disconnect: server={name}, tools_removed={removed}, toolset_version={version}",
        name=server_name,
        removed=removed_count,
        version=app.loop.toolset.version,
    )

    # Disconnect
    await pool.disconnect(server_name)

    console.print(f"[green]✓[/green] Disconnected from [cyan]{server_name}[/cyan]. Removed {removed_count} tools.")


def _mcp_view(app: ShellREPL, server_name: str):
    """View detailed information about an MCP server."""
    assert isinstance(app.loop, NeoLoop)

    mcp_config = app.loop.runtime.mcp_config
    if not mcp_config:
        console.print("[red]No MCP configuration loaded.[/red]")
        return

    server = mcp_config.get_server(server_name)
    if not server:
        console.print(f"[red]Server '{server_name}' not found in config.[/red]")
        return

    pool = get_connection_pool()
    is_connected = pool.is_connected(server_name)
    is_connecting = pool.is_connecting(server_name)

    # Header
    console.print(f"\n[bold cyan]{server_name}[/bold cyan]", end="")
    if is_connected:
        console.print(" [green](connected)[/green]")
    elif is_connecting:
        console.print(" [yellow](connecting...)[/yellow]")
    else:
        console.print(" [dim](disconnected)[/dim]")

    # Server details
    console.print(f"  [dim]Enabled:[/dim]    {'Yes' if server.enabled else 'No'}")
    console.print(f"  [dim]Transport:[/dim]  {server.transport}")

    if server.transport == "stdio":
        console.print(f"  [dim]Command:[/dim]    {server.command}")
        if server.args:
            console.print(f"  [dim]Args:[/dim]       {' '.join(server.args)}")
        if server.env:
            console.print(f"  [dim]Env:[/dim]        {len(server.env)} variables")
    else:
        console.print(f"  [dim]URL:[/dim]        {server.url}")
        if server.headers:
            console.print(f"  [dim]Headers:[/dim]    {len(server.headers)} headers")

    if server.include_tools:
        console.print(f"  [dim]Include:[/dim]    {', '.join(server.include_tools)}")
    if server.exclude_tools:
        console.print(f"  [dim]Exclude:[/dim]    {', '.join(server.exclude_tools)}")

    # Tools (if connected)
    if is_connected:
        tools = [t for t in app.loop.toolset.tools if isinstance(t, MCPTool) and t._server_name == server_name]
        if tools:
            console.print(f"\n  [bold]Tools ({len(tools)}):[/bold]")

            tool_table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
            tool_table.add_column("#", style="dim", width=4, justify="right")
            tool_table.add_column("Name", style="cyan")
            tool_table.add_column("Annotations", style="dim")
            tool_table.add_column("Description", style="dim")

            for i, tool in enumerate(tools, 1):
                name = tool.name[:45] if len(tool.name) > 45 else tool.name
                annotations = tool.get_annotations_display()

                # Take only the first line of description and truncate
                first_line = tool.description.split("\n")[0].strip()
                desc = first_line[:50] + "..." if len(first_line) > 50 else first_line

                tool_table.add_row(
                    f"{i}.",
                    name,
                    f"({annotations})" if annotations else "",
                    desc,
                )

            console.print(tool_table)

    console.print()


async def _mcp_set_enabled(app: ShellREPL, server_name: str, enabled: bool):
    """Enable or disable an MCP server in config."""
    assert isinstance(app.loop, NeoLoop)

    mcp_config = app.loop.runtime.mcp_config
    if not mcp_config:
        console.print("[red]No MCP configuration loaded.[/red]")
        return

    server = mcp_config.get_server(server_name)
    if not server:
        console.print(f"[red]Server '{server_name}' not found in config.[/red]")
        return

    pool = get_connection_pool()

    # If disabling, disconnect first if connected or connecting
    if not enabled and (pool.is_connected(server_name) or pool.is_connecting(server_name)):
        console.print(f"[dim]Disconnecting from {server_name}...[/dim]")
        await _mcp_disconnect(app, server_name)

    # Find and update the server config
    for i, s in enumerate(mcp_config.servers):
        if s.name == server_name:
            # Create new config with updated enabled status
            updated = MCPServerConfig(**{**s.model_dump(), "enabled": enabled})
            mcp_config.servers[i] = updated
            break

    # Save to file
    try:
        mcp_config.save()
        action = "Enabled" if enabled else "Disabled"
        console.print(f"[green]✓[/green] {action} server [cyan]{server_name}[/cyan].")
    except Exception as e:
        console.print(f"[red]Failed to save config: {e}[/red]")


async def _mcp_reload(app: ShellREPL):
    """Reload MCP configuration and reconnect enabled servers."""
    assert isinstance(app.loop, NeoLoop)

    from tools.mcp.config import load_mcp_config

    # Get current config file path
    old_config = app.loop.runtime.mcp_config
    config_file = old_config._config_file if old_config else None

    console.print("[dim]Reloading MCP configuration...[/dim]")

    try:
        new_config = load_mcp_config(config_file)
        if not new_config:
            console.print("[yellow]No MCP configuration found.[/yellow]")
            return

        app.loop.runtime.mcp_config = new_config

        # Disconnect all current MCP connections
        pool = get_connection_pool()
        for server_name in list(pool.connected_servers):
            await _mcp_disconnect(app, server_name)

        # Connect enabled servers
        enabled_servers = new_config.get_enabled_servers()
        if enabled_servers:
            console.print(f"[dim]Connecting to {len(enabled_servers)} enabled server(s)...[/dim]")
            for server in enabled_servers:
                await _mcp_connect(app, server.name)

        console.print(
            f"[green]✓[/green] Reloaded. {len(new_config.servers)} servers configured, {len(enabled_servers)} enabled."
        )

    except Exception as e:
        logger.error("Failed to reload MCP config: {error}", error=e)
        console.print(f"[red]Failed to reload: {e}[/red]")
