from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import typer

from app import enable_logging
from config import VERSION
from exception import Reload

cli = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["--help"]},
    add_help_option=False,
    help="RDSAI CLI - The next-generation RDS Cli with AI",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"version {VERSION}")
        raise typer.Exit()


@cli.command()
def cli_main(
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Log debug information. Default: no.",
        ),
    ] = False,
    # Database connection parameters
    db_host: Annotated[
        str | None,
        typer.Option(
            "--host",
            "-h",
            help="Database server hostname (required).",
        ),
    ] = None,
    db_port: Annotated[
        int | None,
        typer.Option(
            "--port",
            "-P",
            help="Database server port (MySQL default: 3306).",
        ),
    ] = None,
    db_user: Annotated[
        str | None,
        typer.Option(
            "--user",
            "-u",
            help="Database username (required).",
        ),
    ] = None,
    db_password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="Database password.",
            hide_input=True,
        ),
    ] = None,
    db_database: Annotated[
        str | None,
        typer.Option(
            "--database",
            "-D",
            help="Default database name.",
        ),
    ] = None,
    ssl_ca: Annotated[
        str | None,
        typer.Option(
            "--ssl-ca",
            help="SSL CA certificate file path.",
        ),
    ] = None,
    ssl_cert: Annotated[
        str | None,
        typer.Option(
            "--ssl-cert",
            help="SSL client certificate file path.",
        ),
    ] = None,
    ssl_key: Annotated[
        str | None,
        typer.Option(
            "--ssl-key",
            help="SSL client private key file path.",
        ),
    ] = None,
    ssl_mode: Annotated[
        str | None,
        typer.Option(
            "--ssl-mode",
            help="SSL connection mode.",
        ),
    ] = None,
    yolo: Annotated[
        bool,
        typer.Option(
            "--yolo",
            "--yes",
            "-y",
            "--auto-approve",
            help="Automatically approve all actions. Default: no.",
        ),
    ] = False,
):
    """RDSAI Cli, your next CLI agent."""
    from app import Application
    from config import Session

    enable_logging(debug)

    # Create session - with or without database connection
    if db_host and db_user:
        # Validate non-empty strings when provided
        if not db_host.strip():
            raise typer.BadParameter("Database host cannot be empty", param_hint="--host")
        if not db_user.strip():
            raise typer.BadParameter("Database username cannot be empty", param_hint="--user")

        session = Session.create(
            host=db_host,
            user=db_user,
            port=db_port,
            password=db_password,
            database=db_database,
            ssl_ca=ssl_ca,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            ssl_mode=ssl_mode,
        )

        # Show warning if connection failed (but continue to shell)
        if not session.is_connected:
            error_msg = session.db_connection.error if session.db_connection else "Unknown error"
            typer.secho("Warning: Failed to connect to database", fg=typer.colors.RED, err=True)
            typer.secho(f"{error_msg}", fg=typer.colors.RED, err=True)
            typer.secho("Use /connect to reconnect or connect to a different database.", fg=typer.colors.RED, err=True)
    else:
        # No database parameters provided, create empty session
        session = Session.create_empty()

    async def _run() -> bool:
        async with await Application.create(session, yolo=yolo) as app:
            return await app.run()

    while True:
        try:
            succeeded = asyncio.run(_run())
            if succeeded:
                break
            sys.exit(1)
        except Reload:
            continue


if __name__ == "__main__":
    sys.exit(cli())
