"""Model management meta commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from config.app import save_config
from loop import NeoLoop
from ui.console import console
from ui.metacmd.registry import SubCommand, meta_command

if TYPE_CHECKING:
    from ui.repl import ShellREPL


def _model_name_completer(args: list[str]) -> list[str]:
    """Provide model name completions for model subcommands."""
    # This will be called dynamically, so we need to get the app instance
    # For now, return empty list - can be enhanced later with dynamic lookup
    return []


@meta_command(
    aliases=["models"],
    loop_only=True,
    subcommands=[
        SubCommand(name="list", aliases=["ls"], description="List all configured models"),
        SubCommand(
            name="use", aliases=["switch"], description="Switch to a model", arg_completer=_model_name_completer
        ),
        SubCommand(
            name="delete", aliases=["del", "rm"], description="Delete a model", arg_completer=_model_name_completer
        ),
        SubCommand(
            name="info",
            aliases=[],
            description="Show detailed information about a model",
            arg_completer=_model_name_completer,
        ),
    ],
)
def model(app: ShellREPL, args: list[str]):
    """Manage models. Usage: /model [list|use|delete|info] [name]"""
    assert isinstance(app.loop, NeoLoop)

    if not args:
        # Default to list
        _model_list(app)
        return

    subcommand = args[0].lower()
    subargs = args[1:]

    match subcommand:
        case "list" | "ls":
            _model_list(app)
        case "use" | "switch":
            if not subargs:
                console.print("[red]Usage: /model use <name>[/red]")
                return
            _model_use(app, subargs[0])
        case "delete" | "del" | "rm":
            if not subargs:
                console.print("[red]Usage: /model delete <name>[/red]")
                return
            _model_delete(app, subargs[0])
        case "info":
            if not subargs:
                console.print("[red]Usage: /model info <name>[/red]")
                return
            _model_info(app, subargs[0])
        case _:
            # Treat as model name for quick switch
            _model_use(app, subcommand)


def _model_list(app: ShellREPL):
    """List all configured models."""
    assert isinstance(app.loop, NeoLoop)

    config = app.loop.runtime.config
    current_model = app.loop.runtime.llm.model_name if app.loop.runtime.llm else None

    if not config.models:
        console.print("[yellow]No models configured.[/yellow]")
        console.print("[dim]Add models to your config file (~/.rdsai-cli/config.json)[/dim]")
        return

    table = Table(show_header=True, header_style="bold", expand=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name")
    table.add_column("Provider", style="dim")
    table.add_column("Context Size", justify="right", style="dim")

    for idx, (name, model) in enumerate(config.models.items(), 1):
        is_current = name == current_model
        # Add * marker for current model
        display_name = f"[cyan]{name}[/cyan] [green](current)[/green]" if is_current else f"[cyan]{name}[/cyan]"

        # Format context size
        ctx_size = model.max_context_size
        if ctx_size >= 1_000_000:
            ctx_str = f"{ctx_size / 1_000_000:.1f}M"
        elif ctx_size >= 1_000:
            ctx_str = f"{ctx_size / 1_000:.0f}K"
        else:
            ctx_str = str(ctx_size)

        table.add_row(
            str(idx),
            display_name,
            model.provider,
            ctx_str,
        )

    console.print(table)
    console.print("\n[dim]Use /model use <name> to switch, /model delete <name> to remove[/dim]")


def _model_use(app: ShellREPL, model_name: str):
    """Switch to a specified model."""
    assert isinstance(app.loop, NeoLoop)

    from llm.llm import create_llm

    config = app.loop.runtime.config

    # Check if model exists
    if model_name not in config.models:
        console.print(f"[red]Model '{model_name}' not found.[/red]")
        console.print("[dim]Use /model list to see available models.[/dim]")
        return

    # Check if already using this model
    current_model = app.loop.runtime.llm.model_name if app.loop.runtime.llm else None
    if model_name == current_model:
        console.print(f"[yellow]Already using model '{model_name}'.[/yellow]")
        return

    model = config.models[model_name]
    if model.provider not in config.providers:
        console.print(f"[red]Provider '{model.provider}' not found in config.[/red]")
        return

    provider = config.providers[model.provider]

    try:
        new_llm = create_llm(provider, model)
        app.loop.switch_model(new_llm)

        # Persist to config
        config.default_model = model_name
        save_config(config)

        console.print(f"[green]✓[/green] Switched to model: [cyan]{model_name}[/cyan]")
    except Exception as e:
        console.print(f"[red]Failed to switch model: {e}[/red]")


def _model_delete(app: ShellREPL, model_name: str):
    """Delete a model from config."""
    assert isinstance(app.loop, NeoLoop)

    config = app.loop.runtime.config

    # Check if model exists
    if model_name not in config.models:
        console.print(f"[red]Model '{model_name}' not found.[/red]")
        return

    # Check if trying to delete current model
    current_model = app.loop.runtime.llm.model_name if app.loop.runtime.llm else None
    if model_name == current_model:
        console.print(f"[red]Cannot delete the currently active model.[/red]")
        console.print("[dim]Switch to another model first using /model use <name>[/dim]")
        return

    # Check if this is the default model
    if model_name == config.default_model:
        config.default_model = ""

    # Delete the model
    del config.models[model_name]

    # Save config
    try:
        save_config(config)
        console.print(f"[green]✓[/green] Model '{model_name}' deleted.")
    except Exception as e:
        console.print(f"[red]Failed to save config: {e}[/red]")


def _model_info(app: ShellREPL, model_name: str):
    """Show detailed information about a model."""
    assert isinstance(app.loop, NeoLoop)

    config = app.loop.runtime.config

    # Check if model exists
    if model_name not in config.models:
        console.print(f"[red]Model '{model_name}' not found.[/red]")
        return

    model = config.models[model_name]
    current_model = app.loop.runtime.llm.model_name if app.loop.runtime.llm else None
    is_current = model_name == current_model

    console.print(f"\n[bold cyan]{model_name}[/bold cyan]", end="")
    if is_current:
        console.print(" [green](current)[/green]")
    else:
        console.print()

    console.print(f"  [dim]Provider:[/dim]      {model.provider}")
    console.print(f"  [dim]Model ID:[/dim]      {model.model}")

    # Format context size
    ctx_size = model.max_context_size
    if ctx_size >= 1_000_000:
        ctx_str = f"{ctx_size:,} ({ctx_size / 1_000_000:.1f}M tokens)"
    elif ctx_size >= 1_000:
        ctx_str = f"{ctx_size:,} ({ctx_size / 1_000:.0f}K tokens)"
    else:
        ctx_str = f"{ctx_size:,} tokens"
    console.print(f"  [dim]Context Size:[/dim]  {ctx_str}")

    if model.max_output_tokens:
        console.print(f"  [dim]Max Output:[/dim]    {model.max_output_tokens:,} tokens")

    if model.capabilities:
        caps = ", ".join(model.capabilities)
        console.print(f"  [dim]Capabilities:[/dim]  {caps}")

    # Provider info
    if model.provider in config.providers:
        provider = config.providers[model.provider]
        console.print(f"\n  [dim]Provider Type:[/dim] {provider.type}")
        if provider.base_url:
            console.print(f"  [dim]Base URL:[/dim]      {provider.base_url}")

    console.print()
