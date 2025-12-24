"""Console configuration for RDSAI CLI."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

# Markdown style keys that should be disabled (rendered as plain text)
_MARKDOWN_STYLE_KEYS = (
    "markdown.paragraph",
    "markdown.block_quote",
    "markdown.hr",
    "markdown.item",
    "markdown.item.bullet",
    "markdown.item.number",
    "markdown.link",
    "markdown.link_url",
    "markdown.h1",
    "markdown.h1.border",
    "markdown.h2",
    "markdown.h3",
    "markdown.h4",
    "markdown.h5",
    "markdown.h6",
    "markdown.em",
    "markdown.strong",
    "markdown.s",
    "status.spinner",
)

_NEUTRAL_MARKDOWN_THEME = Theme(
    {key: "none" for key in _MARKDOWN_STYLE_KEYS},
    inherit=True,
)

console: Console = Console(highlight=False, theme=_NEUTRAL_MARKDOWN_THEME)
