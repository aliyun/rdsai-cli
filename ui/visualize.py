from __future__ import annotations

import asyncio
import random
from collections import deque
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from typing import NamedTuple

import streamingjson  # pyright: ignore[reportMissingTypeStubs]
from loop.types import (
    AudioURLPart,
    ContentPart,
    ImageURLPart,
    TextPart,
    ThinkPart,
    ToolCall,
    ToolCallPart,
)
from loop.toolset import ToolError, ToolOk, ToolResult, ToolReturnType
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.text import Text

from loop import StatusSnapshot
from tools import extract_tool_args
from ui.console import console
from ui.keyboard import KeyEvent, listen_for_keyboard
from utils.rich.columns import BulletColumns
from utils.rich.markdown import Markdown
from events import StreamMessage, StreamUISide
from events.message import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalPending,
    ApprovalGranted,
    ApprovalRejected,
    CompactionBegin,
    CompactionEnd,
    StatusUpdate,
    StepBegin,
    StepInterrupted,
)

MAX_SUBAGENT_TOOL_CALLS_TO_SHOW = 4

# Spinner text variants for content blocks (without trailing dots)
THINKING_TEXTS = [
    "Thinking...",
    "Contemplating...",
    "Reasoning...",
    "Analyzing...",
    "Reflecting...",
    "Considering...",
    "Deliberating...",
]

COMPOSING_TEXTS = [
    "Composing...",
    "Writing...",
    "Crafting...",
    "Generating...",
    "Creating...",
    "Formulating...",
    "Drafting...",
    "Preparing...",
]


EXPLAIN_COMPOSING_TEXTS = [
    "Explaining...",
    "Summarizing...",
    "Clarifying...",
    "Describing...",
]


async def visualize(
    stream: StreamUISide,
    *,
    initial_status: StatusSnapshot,
    cancel_event: asyncio.Event | None = None,
    agent_type: str = "normal",
):
    """
    A loop to consume agent events and visualize the agent behavior.

    Args:
        stream: Communication channel with the agent
        initial_status: Initial status snapshot
        cancel_event: Event that can be set (e.g., by ESC key) to cancel the run
        agent_type: Type of agent ("normal" or "explain") to use different spinner styles
    """
    view = _LiveView(initial_status, cancel_event, agent_type=agent_type)
    await view.visualize_loop(stream)


class _ContentBlock:
    def __init__(self, is_think: bool, agent_type: str = "normal"):
        self.is_think = is_think
        self.agent_type = agent_type

        # Select spinner text based on agent type
        if agent_type == "explain":
            text = random.choice(EXPLAIN_COMPOSING_TEXTS)
        else:
            text = random.choice(THINKING_TEXTS if is_think else COMPOSING_TEXTS)

        self._spinner = Spinner("dots2", text)
        self.raw_text = ""

    def compose(self) -> RenderableType:
        return self._spinner

    def compose_final(self) -> RenderableType:
        return BulletColumns(
            Markdown(
                self.raw_text,
                style="grey50 italic" if self.is_think else "",
            ),
            bullet_style="grey50",
        )

    def append(self, content: str) -> None:
        self.raw_text += content


class _ToolCallBlock:
    class FinishedSubCall(NamedTuple):
        call: ToolCall
        result: ToolReturnType

    def __init__(self, tool_call: ToolCall):
        self._tool_call_id = tool_call.id
        self._tool_name = tool_call.function.name
        self._lexer = streamingjson.Lexer()
        if tool_call.function.arguments is not None:
            self._lexer.append_string(tool_call.function.arguments)

        self._args = extract_tool_args(self._lexer, self._tool_name)
        self._result: ToolReturnType | None = None
        self._approval_status: str | None = None  # None, "pending", or "granted"

        self._spinning_dots = Spinner("dots", text="")
        self._renderable: RenderableType = self._compose()

    def compose(self) -> RenderableType:
        return self._renderable

    @property
    def finished(self) -> bool:
        return self._result is not None

    def append_args_part(self, args_part: str):
        if self.finished:
            return
        self._lexer.append_string(args_part)
        new_args = extract_tool_args(self._lexer, self._tool_name)
        if new_args != self._args:
            self._args = new_args
            self._renderable = self._compose()

    def finish(self, result: ToolReturnType):
        self._result = result
        self._renderable = self._compose()

    def set_approval_status(self, status: str | None) -> None:
        """Set the approval status and recompose."""
        self._approval_status = status
        self._renderable = self._compose()

    def _compose(self) -> RenderableType:
        lines: list[RenderableType] = []

        # Tool name headline - determine action based on state
        if self.finished:
            action = "Called"
        elif self._approval_status == "pending":
            action = "Waiting for approval"
        elif self._approval_status == "granted":
            action = "Using"
        else:
            action = "Using"

        lines.append(Text.from_markup(f"{action} [bold white]{self._tool_name}[/bold white]"))

        # Parameters as tree-style sub-lines
        args_list = list(self._args.items())
        for i, (key, value) in enumerate(args_list):
            param_line = Text()
            prefix = "└─ " if i == len(args_list) - 1 else "├─ "
            param_line.append(f"  {prefix}")
            param_line.append(f"{key}: ", style="dim")
            param_line.append(value)
            lines.append(param_line)

        # Render brief as additional content if available
        brief = self._result.brief if self.finished and self._result else None
        if brief and brief.strip():
            lines.append(Markdown(brief))

        # Determine bullet style based on status
        if self.finished:
            bullet_style = "green" if isinstance(self._result, ToolOk) else "red"
            return BulletColumns(
                Group(*lines),
                bullet=Text("⏺", style=bullet_style),
            )
        elif self._approval_status == "pending":
            # Show yellow dot for pending approval
            return BulletColumns(
                Group(*lines),
                bullet=Spinner("dots2", text="⏸", style="yellow"),
            )
        elif self._approval_status == "granted":
            return BulletColumns(
                Group(*lines),
                bullet=self._spinning_dots,
            )
        else:
            return BulletColumns(
                Group(*lines),
                bullet=self._spinning_dots,
            )


class _ApprovalPanelRenderer:
    """Base class for approval panel renderers."""

    title: str = "[yellow]⚠ Approval Requested[/yellow]"

    def __init__(self, request: ApprovalRequest):
        self.request = request

    def render_preamble(self) -> RenderableType | None:
        """Render content that should be printed BEFORE the panel (e.g., SQL statements).

        This content is printed separately using console.print() and won't be
        included in the Live view, avoiding truncation issues with long content.

        Returns:
            Renderable content to print before the panel, or None if nothing to print.
        """
        return None

    def render_header(self) -> list[RenderableType]:
        """Render the header section."""
        return [
            Text.assemble(
                Text.from_markup(f"[blue]{self.request.sender}[/blue]"),
                Text(f' is requesting approval to "{self.request.description}".'),
            ),
            Text(""),
        ]

    def render_body(self) -> list[RenderableType]:
        """Render the body section. Override in subclasses for custom content."""
        return []

    def render(self, options: list[RenderableType]) -> RenderableType:
        """Render the complete panel."""
        lines: list[RenderableType] = []
        lines.extend(self.render_header())
        lines.extend(self.render_body())
        lines.extend(options)

        return Panel(
            Group(*lines),
            title=self.title,
            border_style="yellow",
            padding=(1, 2),
            expand=True,
        )


class _DDLApprovalRenderer(_ApprovalPanelRenderer):
    """Renderer for DDL approval requests with SQL code block and risk indicator."""

    title = "[yellow]⚠ DDL Approval Required[/yellow]"

    # Risk level configuration: (prefix, style, label)
    RISK_LEVELS: list[tuple[str, str, str]] = [
        ("DROP", "red bold", "⚠ HIGH RISK"),
        ("TRUNCATE", "red bold", "⚠ HIGH RISK"),
        ("ALTER", "yellow", "⚡ MEDIUM RISK"),
    ]
    DEFAULT_RISK = ("green", "✓ LOW RISK")

    def render_preamble(self) -> RenderableType | None:
        """Render SQL statement separately before the panel to avoid truncation."""
        tool_args = self.request.tool_args or {}
        sql_statement = tool_args.get("sql_statement", "")

        if not sql_statement:
            return None

        # Render SQL with syntax highlighting in a separate panel
        sql_syntax = Syntax(
            sql_statement.strip(),
            "sql",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
            padding=(0, 1),
        )
        return Panel(
            sql_syntax,
            title="[bold]SQL Statement[/bold]",
            border_style="blue",
            padding=(0, 0),
            expand=True,
        )

    def render_header(self) -> list[RenderableType]:
        return [
            Text.assemble(
                Text.from_markup(f"[blue]{self.request.sender}[/blue]"),
                Text(" is requesting approval to execute DDL."),
            ),
            Text(""),
        ]

    def render_body(self) -> list[RenderableType]:
        lines: list[RenderableType] = []
        tool_args = self.request.tool_args or {}

        sql_statement = tool_args.get("sql_statement", "")
        description = tool_args.get("description", self.request.description)

        # Risk indicator
        risk_style, risk_label = self._get_risk_level(sql_statement)
        lines.append(Text(risk_label, style=risk_style))
        lines.append(Text(""))

        # Description
        if description:
            lines.append(Text.from_markup(f"[bold]Description:[/bold] {description}"))
            lines.append(Text(""))

        return lines

    def _get_risk_level(self, sql: str) -> tuple[str, str]:
        """Determine risk level based on SQL statement."""
        sql_upper = sql.strip().upper()
        for prefix, style, label in self.RISK_LEVELS:
            if sql_upper.startswith(prefix):
                return style, label
        return self.DEFAULT_RISK


class _SysbenchApprovalRenderer(_ApprovalPanelRenderer):
    """Renderer for Sysbench tool approval requests with full parameter display."""

    title = "[yellow]⚠ Sysbench Approval Required[/yellow]"

    def render_header(self) -> list[RenderableType]:
        return [
            Text.assemble(
                Text.from_markup(f"[blue]{self.request.sender}[/blue]"),
                Text(f" is requesting approval to execute {self.request.action}."),
            ),
            Text(""),
        ]

    def render_body(self) -> list[RenderableType]:
        """Render full parameter list for sysbench tools."""
        lines: list[RenderableType] = []
        tool_args = self.request.tool_args or {}

        if not tool_args:
            return lines

        # Format parameters in a readable way
        lines.append(Text.from_markup("[bold]Parameters:[/bold]"))
        lines.append(Text(""))

        # Parameter display order and labels
        param_labels = {
            "test_type": "Test Type",
            "tables": "Tables",
            "table_size": "Table Size",
            "threads": "Threads",
            "time": "Duration (seconds)",
            "events": "Events",
            "rate": "Rate Limit (TPS)",
            "report_interval": "Report Interval (seconds)",
        }

        # Display parameters in order
        for param_key, param_label in param_labels.items():
            if param_key in tool_args:
                value = tool_args[param_key]
                # Format large numbers with commas
                if isinstance(value, int) and value >= 1000:
                    value_str = f"{value:,}"
                else:
                    value_str = str(value)
                lines.append(Text(f"  {param_label}: {value_str}"))

        # Display any other parameters not in the standard list
        for param_key, param_value in tool_args.items():
            if param_key not in param_labels:
                value_str = str(param_value)
                if isinstance(param_value, int) and param_value >= 1000:
                    value_str = f"{param_value:,}"
                lines.append(Text(f"  {param_key}: {value_str}"))

        lines.append(Text(""))

        # Add warning about database load
        lines.append(Text.from_markup("[yellow]⚠ This will put significant load on the database.[/yellow]"))

        return lines


# Registry of custom renderers by action name
_APPROVAL_RENDERERS: dict[str, type[_ApprovalPanelRenderer]] = {
    "DDLExecutor": _DDLApprovalRenderer,
    "SysbenchPrepare": _SysbenchApprovalRenderer,
    "SysbenchRun": _SysbenchApprovalRenderer,
    "SysbenchCleanup": _SysbenchApprovalRenderer,
}


def _get_approval_renderer(request: ApprovalRequest) -> _ApprovalPanelRenderer:
    """Get the appropriate renderer for an approval request."""
    renderer_cls = _APPROVAL_RENDERERS.get(request.action, _ApprovalPanelRenderer)
    # Only use custom renderer if tool_args is provided
    if renderer_cls != _ApprovalPanelRenderer and not request.tool_args:
        renderer_cls = _ApprovalPanelRenderer
    return renderer_cls(request)


class _ApprovalRequestPanel:
    def __init__(self, request: ApprovalRequest):
        self.request = request
        self.options = [
            ("Approve", ApprovalResponse.APPROVE),
            ("Approve for this session", ApprovalResponse.APPROVE_FOR_SESSION),
            ("Reject, tell RDSAI CLI what to run instead.", ApprovalResponse.REJECT),
        ]
        self.selected_index = 0
        self._renderer = _get_approval_renderer(request)

    def render(self) -> RenderableType:
        """Render the approval menu as a panel."""
        return self._renderer.render(self._render_options())

    def _render_options(self) -> list[RenderableType]:
        """Render the menu options."""
        options: list[RenderableType] = []
        for i, (option_text, _) in enumerate(self.options):
            if i == self.selected_index:
                options.append(Text(f"→ {option_text}", style="cyan"))
            else:
                options.append(Text(f"  {option_text}", style="grey50"))
        return options

    def move_up(self):
        """Move selection up."""
        self.selected_index = (self.selected_index - 1) % len(self.options)

    def move_down(self):
        """Move selection down."""
        self.selected_index = (self.selected_index + 1) % len(self.options)

    def get_selected_response(self) -> ApprovalResponse:
        """Get the approval response based on selected option."""
        return self.options[self.selected_index][1]


class _StatusBlock:
    def __init__(self, initial: StatusSnapshot) -> None:
        self.text = Text("", justify="right", style="grey50")
        self.update(initial)

    def render(self) -> RenderableType:
        return self.text

    def update(self, status: StatusSnapshot) -> None:
        if status.context_usage < 0:
            self.text.plain = ""
        else:
            self.text.plain = f"context: {status.context_usage:.1%}"


@asynccontextmanager
async def _keyboard_listener(handler: Callable[[KeyEvent], None]):
    async def _keyboard():
        async for event in listen_for_keyboard():
            handler(event)

    task = asyncio.create_task(_keyboard())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


class _LiveView:
    def __init__(
        self,
        initial_status: StatusSnapshot,
        cancel_event: asyncio.Event | None = None,
        agent_type: str = "normal",
    ):
        self._cancel_event = cancel_event
        self._agent_type = agent_type

        self._mooning_spinner: Spinner | None = None
        self._compacting_spinner: Spinner | None = None

        self._current_content_block: _ContentBlock | None = None
        self._tool_call_blocks: dict[str, _ToolCallBlock] = {}
        self._last_tool_call_block: _ToolCallBlock | None = None
        self._approval_request_queue = deque[ApprovalRequest]()
        self._current_approval_request_panel: _ApprovalRequestPanel | None = None
        self._reject_all_following = False
        self._status_block = _StatusBlock(initial_status)
        self._pending_approvals: dict[str, str] = {}  # Track pending approvals before ToolCall arrives

        self._need_recompose = False
        self._need_trailing_newline = False  # Track if we need an empty line after tool calls

    async def visualize_loop(self, stream: StreamUISide):
        with Live(
            self.compose(),
            console=console,
            refresh_per_second=10,
            transient=True,
            vertical_overflow="visible",
        ) as live:

            def keyboard_handler(event: KeyEvent) -> None:
                self.dispatch_keyboard_event(event)
                if self._need_recompose:
                    live.update(self.compose())
                    self._need_recompose = False

            def update_display() -> None:
                """Update the live display."""
                live.update(self.compose())

            def finish_loop(is_interrupt: bool) -> None:
                """Cleanup and update display when loop finishes."""
                self.cleanup(is_interrupt)
                update_display()

            async with _keyboard_listener(keyboard_handler):
                while True:
                    # Check for cancellation before waiting
                    if self._cancel_event is not None and self._cancel_event.is_set():
                        finish_loop(is_interrupt=True)
                        break

                    # Wait for message
                    try:
                        msg = await stream.receive()
                    except asyncio.QueueShutDown:
                        finish_loop(is_interrupt=False)
                        break

                    # Check for cancellation after receiving message
                    if self._cancel_event is not None and self._cancel_event.is_set():
                        finish_loop(is_interrupt=True)
                        break

                    # Process the received message
                    if isinstance(msg, StepInterrupted):
                        finish_loop(is_interrupt=True)
                        break

                    try:
                        self.dispatch_stream_message(msg)
                        if self._need_recompose:
                            update_display()
                            self._need_recompose = False
                    except asyncio.QueueShutDown:
                        finish_loop(is_interrupt=False)
                        break

    def refresh_soon(self) -> None:
        self._need_recompose = True

    def compose(self) -> RenderableType:
        """Compose the live view display content."""
        blocks: list[RenderableType] = []
        if self._mooning_spinner is not None:
            blocks.append(self._mooning_spinner)
        elif self._compacting_spinner is not None:
            blocks.append(self._compacting_spinner)
            if self._current_approval_request_panel is not None:
                blocks.append(self._current_approval_request_panel.render())
        else:
            if self._current_content_block is not None:
                blocks.append(self._current_content_block.compose())
            for tool_call in self._tool_call_blocks.values():
                blocks.append(tool_call.compose())
            # Show approval panel after tool calls
            if self._current_approval_request_panel is not None:
                blocks.append(self._current_approval_request_panel.render())
        blocks.append(self._status_block.render())
        return Group(*blocks)

    def dispatch_stream_message(self, msg: StreamMessage) -> None:
        """Dispatch the stream message to UI components."""
        assert not isinstance(msg, StepInterrupted)  # handled in visualize_loop

        if isinstance(msg, StepBegin):
            self.cleanup(is_interrupt=False)
            if self._agent_type == "explain":
                self._mooning_spinner = Spinner("bouncingBar", "")
            else:
                self._mooning_spinner = Spinner("moon", "")
            self.refresh_soon()
            return

        if self._mooning_spinner is not None:
            self._mooning_spinner = None
            self.refresh_soon()

        match msg:
            case CompactionBegin():
                self._compacting_spinner = Spinner("balloon2", "Compacting...")
                self.refresh_soon()
            case CompactionEnd():
                self._compacting_spinner = None
                self.refresh_soon()
            case StatusUpdate(status=status):
                self._status_block.update(status)
            case TextPart() | ImageURLPart() | AudioURLPart() | ThinkPart() | ToolCallPart():
                self.append_content(msg)
            case ToolCall():
                self.append_tool_call(msg)
            case ToolCallPart():
                self.append_tool_call_part(msg)
            case ToolResult():
                self.append_tool_result(msg)
            case ApprovalPending(tool_call_id=tool_call_id):
                self.handle_approval_pending(tool_call_id)
            case ApprovalGranted(tool_call_id=tool_call_id):
                self.handle_approval_granted(tool_call_id)
            case ApprovalRejected(tool_call_id=tool_call_id):
                self.handle_approval_rejected(tool_call_id)
            case ApprovalRequest():
                self.request_approval(msg)

    def dispatch_keyboard_event(self, event: KeyEvent) -> None:
        # handle ESC key or Ctrl+C to cancel the run
        if event in (KeyEvent.ESCAPE, KeyEvent.CTRL_C) and self._cancel_event is not None:
            self._cancel_event.set()
            return

        if not self._current_approval_request_panel:
            # just ignore any keyboard event when there's no approval request
            return

        match event:
            case KeyEvent.UP:
                self._current_approval_request_panel.move_up()
                self.refresh_soon()
            case KeyEvent.DOWN:
                self._current_approval_request_panel.move_down()
                self.refresh_soon()
            case KeyEvent.ENTER:
                resp = self._current_approval_request_panel.get_selected_response()
                self._current_approval_request_panel.request.resolve(resp)
                if resp == ApprovalResponse.APPROVE_FOR_SESSION:
                    to_remove_from_queue: list[ApprovalRequest] = []
                    for request in self._approval_request_queue:
                        # approve all queued requests with the same action
                        if request.action == self._current_approval_request_panel.request.action:
                            request.resolve(ApprovalResponse.APPROVE_FOR_SESSION)
                            to_remove_from_queue.append(request)
                    for request in to_remove_from_queue:
                        self._approval_request_queue.remove(request)
                elif resp == ApprovalResponse.REJECT:
                    # one rejection should stop the step immediately
                    while self._approval_request_queue:
                        self._approval_request_queue.popleft().resolve(ApprovalResponse.REJECT)
                    self._reject_all_following = True
                self.show_next_approval_request()
            case _:
                # just ignore any other keyboard event
                return

    def cleanup(self, is_interrupt: bool) -> None:
        """Cleanup the live view on step end or interruption."""
        self.flush_content()

        # Don't cleanup tool_call_blocks that are waiting for approval or granted
        # These blocks should persist across steps until they complete
        # But finished blocks (including rejected ones) should be flushed
        blocks_to_finish = []
        for block in self._tool_call_blocks.values():
            if not block.finished:
                # Only finish blocks that are not in approval workflow
                # Blocks with approval_status "pending" or "granted" should be kept
                if block._approval_status not in ("pending", "granted"):
                    blocks_to_finish.append(block)

        for block in blocks_to_finish:
            # this should not happen, but just in case
            block.finish(ToolError(message="", brief="Interrupted") if is_interrupt else ToolOk(output=""))

        # Only flush finished blocks (not approval-pending/granted ones)
        self.flush_finished_tool_calls()
        self._flush_trailing_newline()  # Print deferred empty line at cleanup

        while self._approval_request_queue:
            # should not happen, but just in case
            self._approval_request_queue.popleft().resolve(ApprovalResponse.REJECT)
        self._current_approval_request_panel = None
        self._reject_all_following = False

        # Don't clear _last_tool_call_block if it's in approval workflow
        if self._last_tool_call_block is not None:
            if self._last_tool_call_block._approval_status in ("pending", "granted"):
                # Keep the reference for approval workflow
                pass
            else:
                self._last_tool_call_block = None

    def flush_content(self) -> None:
        """Flush the current content block."""
        if self._current_content_block is not None:
            console.print(self._current_content_block.compose_final())
            console.print()  # Add empty line after content block
            self._current_content_block = None
            self.refresh_soon()

    def flush_finished_tool_calls(self) -> None:
        """Flush all leading finished tool call blocks.

        Tool calls are printed without empty lines between them.
        Empty line is deferred until next content block or cleanup.
        """
        tool_call_ids = list(self._tool_call_blocks.keys())

        for tool_call_id in tool_call_ids:
            block = self._tool_call_blocks[tool_call_id]
            if not block.finished:
                break

            self._tool_call_blocks.pop(tool_call_id)
            console.print(block.compose())
            self._need_trailing_newline = True  # Defer empty line
            if self._last_tool_call_block == block:
                self._last_tool_call_block = None

        self.refresh_soon()

    def _flush_trailing_newline(self) -> None:
        """Print deferred empty line after tool calls if needed."""
        if self._need_trailing_newline:
            console.print()
            self._need_trailing_newline = False

    def append_content(self, part: ContentPart) -> None:
        match part:
            case ThinkPart(think=text) | TextPart(text=text):
                if not text:
                    return
                is_think = isinstance(part, ThinkPart)
                if self._current_content_block is None:
                    self._flush_trailing_newline()
                    self._current_content_block = _ContentBlock(is_think, agent_type=self._agent_type)
                    self.refresh_soon()
                elif self._current_content_block.is_think != is_think:
                    self.flush_content()
                    self._current_content_block = _ContentBlock(is_think, agent_type=self._agent_type)
                    self.refresh_soon()
                self._current_content_block.append(text)
            case _:
                pass

    def append_tool_call(self, tool_call: ToolCall) -> None:
        self.flush_content()
        # Check if we have a pending approval for this tool_call_id
        # This can happen when ApprovalPending is sent before ToolCall
        block = self._tool_call_blocks.get(tool_call.id)
        if block is None:
            # Create new block
            block = _ToolCallBlock(tool_call)
            self._tool_call_blocks[tool_call.id] = block

            # Check if there's a pending approval status to apply
            if hasattr(self, "_pending_approvals") and tool_call.id in self._pending_approvals:
                status = self._pending_approvals.pop(tool_call.id)
                block.set_approval_status(status)

        self._last_tool_call_block = block
        self.refresh_soon()

    def append_tool_call_part(self, part: ToolCallPart) -> None:
        if not part.arguments_part:
            return
        if self._last_tool_call_block is None:
            return
        self._last_tool_call_block.append_args_part(part.arguments_part)
        self.refresh_soon()

    def append_tool_result(self, result: ToolResult) -> None:
        if block := self._tool_call_blocks.get(result.tool_call_id):
            block.finish(result.result)
            self.flush_finished_tool_calls()
            self.refresh_soon()

    def handle_approval_pending(self, tool_call_id: str) -> None:
        """Handle ApprovalPending message - mark tool call as waiting for approval.

        This may be called before ToolCall is received, so we need to create a placeholder block.
        """
        block = self._tool_call_blocks.get(tool_call_id)
        if block is None:
            # ToolCall hasn't been received yet, store pending status
            if not hasattr(self, "_pending_approvals"):
                self._pending_approvals: dict[str, str] = {}
            self._pending_approvals[tool_call_id] = "pending"
            return
        block.set_approval_status("pending")
        self.refresh_soon()

    def handle_approval_granted(self, tool_call_id: str) -> None:
        """Handle ApprovalGranted message - mark tool call as approved and ready to execute."""
        block = self._tool_call_blocks.get(tool_call_id)
        if block is None:
            # Store granted status if block doesn't exist yet
            if not hasattr(self, "_pending_approvals"):
                self._pending_approvals: dict[str, str] = {}
            self._pending_approvals[tool_call_id] = "granted"
            return
        block.set_approval_status("granted")
        self.refresh_soon()

    def handle_approval_rejected(self, tool_call_id: str) -> None:
        """Handle ApprovalRejected message - mark tool call as rejected and finish it."""
        block = self._tool_call_blocks.get(tool_call_id)
        if block is None:
            # Block doesn't exist, nothing to do
            return

        block.finish(ToolError(message="Tool execution rejected by user.", brief="Rejected"))
        self.flush_finished_tool_calls()
        self.refresh_soon()

    def request_approval(self, request: ApprovalRequest) -> None:
        # If we're rejecting all following requests, reject immediately
        if self._reject_all_following:
            request.resolve(ApprovalResponse.REJECT)
            return

        self._approval_request_queue.append(request)

        if self._current_approval_request_panel is None:
            console.bell()
            self.show_next_approval_request()

    def show_next_approval_request(self) -> None:
        """
        Show the next approval request from the queue.
        If there are no pending requests, clear the current approval panel.
        """
        if not self._approval_request_queue:
            if self._current_approval_request_panel is not None:
                self._current_approval_request_panel = None
                self.refresh_soon()
            return

        while self._approval_request_queue:
            request = self._approval_request_queue.popleft()
            if request.resolved:
                # skip resolved requests
                continue

            # Print trailing newline to separate from previous output
            self._flush_trailing_newline()

            # Print preamble (e.g., SQL statement) separately before the panel
            # This ensures long content is fully displayed without truncation
            renderer = _get_approval_renderer(request)
            preamble = renderer.render_preamble()
            if preamble is not None:
                console.print(preamble)

            self._current_approval_request_panel = _ApprovalRequestPanel(request)
            self.refresh_soon()
            break
