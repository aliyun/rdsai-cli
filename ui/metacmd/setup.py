"""Setup and reload meta commands."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

import aiohttp
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import PasswordProcessor, Processor, Transformation
from prompt_toolkit.shortcuts.choice_input import ChoiceInput
from prompt_toolkit.widgets import Frame
from pydantic import SecretStr

from config import LLMModel, LLMProvider, load_config, save_config
from ui.console import console
from ui.metacmd.registry import meta_command
from utils.aiohttp import new_client_session

if TYPE_CHECKING:
    from ui.repl import ShellREPL


class _Platform(NamedTuple):
    id: str
    name: str
    default_base_url: str
    suggested_models: list[str] | None = None
    needs_base_url: bool = True
    needs_max_output_tokens: bool = False


_PLATFORMS = [
    _Platform(
        id="qwen",
        name="Qwen (Alibaba Cloud)",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        suggested_models=["qwen3-max", "qwen-plus", "qwen-turbo"],
    ),
    _Platform(
        id="openai",
        name="OpenAI",
        default_base_url="https://api.openai.com/v1",
        suggested_models=[],
    ),
    _Platform(
        id="deepseek",
        name="DeepSeek",
        default_base_url="https://api.deepseek.com/v1",
        suggested_models=["deepseek-chat", "deepseek-reasoner"],
    ),
    _Platform(
        id="anthropic",
        name="Anthropic (Claude)",
        default_base_url="",
        suggested_models=[],
        needs_base_url=False,
        needs_max_output_tokens=True,
    ),
    _Platform(
        id="gemini",
        name="Google Gemini",
        default_base_url="",
        suggested_models=[],
        needs_base_url=False,
    ),
    _Platform(
        id="openai_compatible",
        name="OpenAI Compatible (Custom)",
        default_base_url="",
        suggested_models=[],
    ),
]

# Default context sizes for mainstream models (used as fallback when API doesn't provide info)
# Sources:
#   - OpenAI: https://platform.openai.com/docs/models
#   - Anthropic: https://docs.anthropic.com/claude/docs
#   - Google Gemini: https://ai.google.dev/models/gemini
#   - DeepSeek: https://api-docs.deepseek.com/quick_start/pricing
#   - Qwen: https://help.aliyun.com/zh/model-studio/
# Last updated: 2024-12
_MODEL_CONTEXT_SIZES: dict[str, int] = {
    # OpenAI models
    "gpt-4.1": 1_000_000,  # 1M tokens
    "gpt-4.1-mini": 1_000_000,  # 1M tokens
    "gpt-4.1-nano": 1_000_000,  # 1M tokens
    "gpt-4o": 128_000,  # 128K tokens
    "gpt-4o-mini": 128_000,  # 128K tokens
    "gpt-4-turbo": 128_000,  # 128K tokens
    "gpt-4-turbo-preview": 128_000,  # 128K tokens
    "gpt-4": 8_192,  # 8K tokens
    "gpt-4-32k": 32_768,  # 32K tokens
    "gpt-3.5-turbo": 16_385,  # 16K tokens
    "o1": 200_000,  # 200K tokens
    "o1-mini": 128_000,  # 128K tokens
    "o1-preview": 128_000,  # 128K tokens
    "o3": 200_000,  # 200K tokens
    "o3-mini": 200_000,  # 200K tokens
    # Anthropic Claude models (all support 200K by default)
    "claude-opus-4-20250514": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-7-sonnet-20250219": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-sonnet-20240620": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    # Alias names
    "claude-opus-4-0": 200_000,
    "claude-sonnet-4-0": 200_000,
    "claude-3.7-sonnet": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    # Google Gemini models
    "gemini-2.5-pro": 1_048_576,  # 1M tokens
    "gemini-2.5-flash": 1_048_576,  # 1M tokens
    "gemini-2.0-flash": 1_048_576,  # 1M tokens
    "gemini-2.0-flash-lite": 1_048_576,  # 1M tokens
    "gemini-1.5-pro": 2_097_152,  # 2M tokens
    "gemini-1.5-flash": 1_048_576,  # 1M tokens
    "gemini-1.5-flash-8b": 1_048_576,  # 1M tokens
    "gemini-1.0-pro": 32_760,  # ~32K tokens
    # DeepSeek models
    "deepseek-chat": 131_072,  # 128K tokens (V3)
    "deepseek-reasoner": 131_072,  # 128K tokens (R1)
    "deepseek-coder": 131_072,  # 128K tokens
    # Qwen models (Alibaba Cloud)
    "qwen3-max": 262_144,  # 256K tokens
}


def get_model_context_size(model_name: str) -> int | None:
    """Get the context size for a model from the predefined configuration.

    Args:
        model_name: The name of the model (case-insensitive, supports partial matching)

    Returns:
        The context size in tokens, or None if not found
    """
    # Exact match first (case-insensitive)
    model_lower = model_name.lower()
    for name, size in _MODEL_CONTEXT_SIZES.items():
        if name.lower() == model_lower:
            return size

    # Partial match (check if model_name starts with a known prefix)
    for name, size in _MODEL_CONTEXT_SIZES.items():
        if model_lower.startswith(name.lower()):
            return size

    # Check if any known model name is a prefix of the input
    for name, size in _MODEL_CONTEXT_SIZES.items():
        if model_lower.startswith(name.lower().split("-")[0]):
            # Match by family prefix (e.g., "gpt", "claude", "gemini")
            pass

    return None


@meta_command
async def setup(app: ShellREPL, args: list[str]):
    """Set up the RDSAI CLI model and language configuration"""
    result = await _setup()
    if not result:
        # user cancelled or error
        return

    config = load_config()
    config.language = result.language
    config.providers[result.platform.id] = LLMProvider(
        type=result.platform.id,
        base_url=result.base_url,
        api_key=result.api_key,
    )
    config.models[result.model_name] = LLMModel(
        provider=result.platform.id,
        model=result.model_name,
        max_context_size=result.max_context_size,
        max_output_tokens=result.max_output_tokens,
    )
    config.default_model = result.model_name

    save_config(config)
    console.print("[green]✓[/green] Configuration saved! Reloading...")
    await asyncio.sleep(1)
    console.clear()

    from exception import Reload

    raise Reload


class _SetupResult(NamedTuple):
    language: str
    platform: _Platform
    base_url: str
    api_key: SecretStr
    model_name: str
    max_context_size: int
    max_output_tokens: int | None = None


@dataclass
class _FormField:
    """A single form field."""

    name: str
    label: str
    default_value: str = ""
    placeholder: str = ""
    is_password: bool = False
    buffer: Buffer = field(default_factory=Buffer)

    def __post_init__(self):
        self.buffer.text = self.default_value

    @property
    def value(self) -> str:
        return self.buffer.text.strip()

    @property
    def display_value(self) -> str:
        if self.is_password and self.value:
            return "*" * min(len(self.value), 20)
        return self.value or "(empty)"


class _PlaceholderProcessor(Processor):
    """Show gray placeholder text when buffer is empty."""

    def __init__(self, placeholder: str):
        self.placeholder = placeholder

    def apply_transformation(self, transformation_input):
        if not transformation_input.document.text:
            # Show placeholder in gray italic when input is empty
            return Transformation([("gray italic", self.placeholder)])
        return Transformation(transformation_input.fragments)


class _FormResult(NamedTuple):
    """Result of a form submission."""

    submitted: bool
    values: dict[str, str]


async def _run_form(
    title: str,
    fields: list[_FormField],
) -> _FormResult:
    """Run a multi-field form with up/down navigation."""
    current_field_idx = 0
    submitted = False
    cancelled = False

    # Create persistent buffer controls for each field
    buffer_controls: list[BufferControl] = []
    for f in fields:
        input_processors: list[Processor] = []
        if f.is_password:
            input_processors.append(PasswordProcessor())

        if f.placeholder:
            input_processors.append(_PlaceholderProcessor(f.placeholder))
        buffer_controls.append(
            BufferControl(
                buffer=f.buffer,
                focusable=True,
                input_processors=input_processors,
            )
        )

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        nonlocal current_field_idx
        if current_field_idx > 0:
            current_field_idx -= 1
            # Focus the new field's buffer
            event.app.layout.focus(buffer_controls[current_field_idx])

    @kb.add("down")
    def _(event):
        nonlocal current_field_idx
        if current_field_idx < len(fields) - 1:
            current_field_idx += 1
            event.app.layout.focus(buffer_controls[current_field_idx])

    @kb.add("tab")
    def _(event):
        nonlocal current_field_idx
        if current_field_idx < len(fields) - 1:
            current_field_idx += 1
            event.app.layout.focus(buffer_controls[current_field_idx])

    @kb.add("s-tab")  # shift+tab
    def _(event):
        nonlocal current_field_idx
        if current_field_idx > 0:
            current_field_idx -= 1
            event.app.layout.focus(buffer_controls[current_field_idx])

    @kb.add("enter")
    def _(event):
        nonlocal current_field_idx, submitted
        if current_field_idx < len(fields) - 1:
            current_field_idx += 1
            event.app.layout.focus(buffer_controls[current_field_idx])
        else:
            # On last field, submit
            submitted = True
            event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _(event):
        nonlocal cancelled
        cancelled = True
        event.app.exit()

    def get_field_windows():
        windows = []
        # Calculate max label width for alignment
        max_label_len = max(len(f.label) for f in fields)

        for i, f in enumerate(fields):
            is_current = i == current_field_idx
            prefix = "▸ " if is_current else "  "

            # Label and input on the same line
            label_style = "bold" if is_current else ""
            label_text = f"{prefix}{f.label}:"
            label_width = len(prefix) + max_label_len + 2  # +2 for ": "

            row = VSplit(
                [
                    Window(
                        FormattedTextControl([(label_style, label_text)]),
                        width=label_width,
                        height=1,
                    ),
                    Window(
                        buffer_controls[i],
                        height=1,
                        style="bg:#1a1a2e" if is_current else "",
                    ),
                ]
            )
            windows.append(row)

            # Add spacing between fields
            windows.append(Window(height=1))

        return windows

    def get_layout():
        field_windows = get_field_windows()

        # Footer with instructions
        footer = Window(
            FormattedTextControl(
                [
                    ("class:footer", " [↑/↓] Switch field  [Tab] Next  [Enter] Confirm  [Esc] Cancel "),
                ]
            ),
            height=1,
            style="reverse",
        )

        body = HSplit(
            [
                Window(height=1),  # Top padding
                *field_windows,
                Window(),  # Flexible space
                footer,
            ]
        )

        return Layout(Frame(body, title=title), focused_element=buffer_controls[current_field_idx])

    # Create application with dynamic layout
    app: Application[None] = Application(
        layout=get_layout(),
        key_bindings=kb,
        full_screen=False,
        refresh_interval=0.1,
        mouse_support=False,
    )

    # Update layout on each render
    original_render = app._redraw

    def custom_redraw(*args, **kwargs):
        app.layout = get_layout()
        return original_render(*args, **kwargs)

    app._redraw = custom_redraw  # type: ignore

    await app.run_async()

    if cancelled:
        return _FormResult(submitted=False, values={})

    return _FormResult(
        submitted=submitted,
        values={f.name: f.value for f in fields},
    )


async def _setup() -> _SetupResult | None:
    # Step 1: Select language
    current_config = load_config()

    # Language configuration: display name -> language code
    language_options = {
        "English (en)": "en",
        "中文 (zh)": "zh",
    }

    # Build choices list with current language first
    all_choices = list(language_options.keys())
    current_language_code = current_config.language
    current_choice = next(
        (choice for choice, code in language_options.items() if code == current_language_code),
        all_choices[0],  # Default to English if not found
    )

    # Reorder choices to put current selection first
    language_choices = [current_choice] + [c for c in all_choices if c != current_choice]

    language_display = await _prompt_choice(
        header="Select language",
        choices=language_choices,
    )
    if not language_display:
        console.print("[yellow]Setup cancelled[/yellow]")
        return None

    language = language_options["English (en)"]

    # Step 2: Select platform
    platform_name = await _prompt_choice(
        header="Select the API platform",
        choices=[p.name for p in _PLATFORMS],
    )
    if not platform_name:
        console.print("[yellow]Setup cancelled[/yellow]")
        return None

    platform = next(p for p in _PLATFORMS if p.name == platform_name)

    # Step 3: Form input (Base URL, API Key, Model Name, etc.)
    while True:
        fields: list[_FormField] = []

        # Add base_url field only for providers that need it
        if platform.needs_base_url:
            fields.append(
                _FormField(
                    name="base_url",
                    label="Base API URL",
                    default_value=platform.default_base_url,
                    placeholder="Enter API base URL...",
                )
            )

        fields.append(
            _FormField(
                name="api_key",
                label="API Key",
                is_password=True,
                placeholder="Enter your API key...",
            )
        )
        fields.append(
            _FormField(
                name="model_name",
                label="Model Name",
                default_value=platform.suggested_models[0] if platform.suggested_models else "",
                placeholder="Enter model name (e.g., gpt-5.1)...",
            )
        )

        # Add max_output_tokens field for providers that need it (e.g., Anthropic)
        if platform.needs_max_output_tokens:
            fields.append(
                _FormField(
                    name="max_output_tokens",
                    label="Max Output Tokens",
                    default_value="4096",
                    placeholder="Enter max tokens (e.g., 4096)...",
                )
            )

        form_result = await _run_form(
            title=f" Configure {platform.name} ",
            fields=fields,
        )

        if not form_result.submitted:
            console.print("[yellow]Setup cancelled[/yellow]")
            return None

        # Validate fields
        base_url = form_result.values.get("base_url", "").strip()
        api_key = form_result.values.get("api_key", "").strip()
        model_name = form_result.values.get("model_name", "").strip()
        max_output_tokens_str = form_result.values.get("max_output_tokens", "").strip()

        errors = []
        # Base URL is required only for providers that need it
        if platform.needs_base_url and not base_url:
            errors.append("Base API URL is required")
        if not api_key:
            errors.append("API Key is required")
        if not model_name:
            errors.append("Model Name is required")
        if platform.needs_max_output_tokens and not max_output_tokens_str:
            errors.append("Max Output Tokens is required")
        if max_output_tokens_str and not max_output_tokens_str.isdigit():
            errors.append("Max Output Tokens must be a number")

        if errors:
            console.print("[red]Validation errors:[/red]")
            for err in errors:
                console.print(f"  [red]• {err}[/red]")
            console.print()

            retry = await _prompt_choice(
                header="What would you like to do?",
                choices=["Edit again", "Cancel setup"],
            )
            if retry != "Edit again":
                return None
            continue

        # Step 4: Confirm configuration
        confirm = await _prompt_choice(
            header="Confirm this configuration?",
            choices=["Yes, save and apply", "No, edit again", "Cancel"],
        )

        if confirm == "Yes, save and apply":
            # Fetch model details to get max_context_size
            console.print("[dim]Fetching model information...[/dim]")
            try:
                max_context_size = await _fetch_max_context_size(base_url, api_key, model_name, platform.id)
                if max_context_size is None:
                    max_context_size = 0  # 0 means unknown, context usage will not be displayed
                    console.print("[yellow]Could not fetch model info, context usage will not be displayed[/yellow]")
                else:
                    console.print(f"[green]✓[/green] Model max_context_size: {max_context_size}")
            except aiohttp.ClientError as e:
                console.print(f"[red]Network error while fetching model info: {e}[/red]")
                retry = await _prompt_choice(
                    header="What would you like to do?",
                    choices=["Continue without context size", "Edit again", "Cancel setup"],
                )
                if retry == "Continue without context size":
                    max_context_size = 0
                elif retry == "Edit again":
                    continue
                else:
                    # "Cancel setup" or None (Ctrl+C)
                    return None
            except (ValueError, TypeError, KeyError) as e:
                console.print(f"[red]Error parsing model info: {e}[/red]")
                retry = await _prompt_choice(
                    header="What would you like to do?",
                    choices=["Continue without context size", "Edit again", "Cancel setup"],
                )
                if retry == "Continue without context size":
                    max_context_size = 0
                elif retry == "Edit again":
                    continue
                else:
                    # "Cancel setup" or None (Ctrl+C)
                    return None

            # Parse max_output_tokens if provided
            max_output_tokens: int | None = None
            if max_output_tokens_str:
                max_output_tokens = int(max_output_tokens_str)

            return _SetupResult(
                language=language,
                platform=platform,
                base_url=base_url,
                api_key=SecretStr(api_key),
                model_name=model_name,
                max_context_size=max_context_size,
                max_output_tokens=max_output_tokens,
            )
        elif confirm == "No, edit again":
            continue
        else:
            console.print("[yellow]Setup cancelled[/yellow]")
            return None


async def _fetch_max_context_size(base_url: str, api_key: str, model_name: str, platform_id: str) -> int | None:
    """Fetch max_context_size from model API endpoint.

    Different platforms have different API formats and authentication methods.
    Falls back to predefined configuration only when API doesn't provide the info.

    Raises:
        aiohttp.ClientError: On network errors
        ValueError: On response parsing errors
    """
    predefined_size = get_model_context_size(model_name)
    if predefined_size is not None:
        return predefined_size

    if not base_url:
        return None

    # Just support Qwen from Api for now
    if platform_id not in "qwen":
        return None

    model_url = f"{base_url.rstrip('/')}/models/{model_name}"

    # Set up headers based on platform
    headers: dict[str, str] = {}
    if platform_id in ("qwen", "openai", "openai_compatible", "deepseek"):
        headers["Authorization"] = f"Bearer {api_key}"

    async with (
        new_client_session() as session,
        session.get(
            model_url,
            headers=headers,
            raise_for_status=True,
        ) as response,
    ):
        model_detail = await response.json()

    # Try different possible paths for max_context_size
    # Qwen format
    if "extra_info" in model_detail:
        extra_info = model_detail["extra_info"]
        if "default_envs" in extra_info and "max_tokens" in extra_info["default_envs"]:
            return int(extra_info["default_envs"]["max_tokens"])

    # OpenAI format (context_length)
    if "context_length" in model_detail:
        return int(model_detail["context_length"])

    # Generic format
    if "max_context_size" in model_detail:
        return int(model_detail["max_context_size"])
    if "max_tokens" in model_detail:
        return int(model_detail["max_tokens"])

    # API succeeded but didn't provide context size
    return None


async def _prompt_choice(*, header: str, choices: list[str]) -> str | None:
    if not choices:
        return None

    try:
        return await ChoiceInput(
            message=header,
            options=[(choice, choice) for choice in choices],
            default=choices[0],
        ).prompt_async()
    except (EOFError, KeyboardInterrupt):
        return None


@meta_command
def reload(app: ShellREPL, args: list[str]):
    """Reload configuration"""
    from exception import Reload

    raise Reload
