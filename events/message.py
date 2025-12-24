from __future__ import annotations

import asyncio
import uuid
from enum import Enum
from typing import Any

from loop.types import (
    ContentPart,
    ToolCall,
    ToolCallPart,
    ThinkPart,
)
from loop.toolset import ToolResult
from pydantic import BaseModel, Field

from loop import StatusSnapshot


class StepBegin(BaseModel):
    """
    Indicates the beginning of a new agent step.
    This event must be sent before any other event in the step.
    """

    n: int
    """The step number."""


class StepInterrupted(BaseModel):
    """Indicates the current step was interrupted, either by user intervention or an error."""

    pass


class CompactionBegin(BaseModel):
    """
    Indicates that a compaction just began.
    This event must be sent during a step, which means, between `StepBegin` and the next
    `StepBegin` or `StepInterrupted`. And, there must be a `CompactionEnd` directly following
    this event.
    """

    pass


class CompactionEnd(BaseModel):
    """
    Indicates that a compaction just ended.
    This event must be sent directly after a `CompactionBegin` event.
    """

    pass


class StatusUpdate(BaseModel):
    status: StatusSnapshot
    """The snapshot of the current loop status."""


class ApprovalPending(BaseModel):
    """Indicates that a tool call is waiting for approval."""

    tool_call_id: str
    """The ID of the tool call waiting for approval."""


class ApprovalGranted(BaseModel):
    """Indicates that a tool call has been approved and execution can begin."""

    tool_call_id: str
    """The ID of the tool call that was approved."""


class ApprovalRejected(BaseModel):
    """Indicates that a tool call has been rejected by the user."""

    tool_call_id: str
    """The ID of the tool call that was rejected."""


type ControlFlowEvent = StepBegin | StepInterrupted | CompactionBegin | CompactionEnd | StatusUpdate
"""Any control flow event."""
type Event = (
    ControlFlowEvent
    | ContentPart
    | ToolCall
    | ToolCallPart
    | ToolResult
    | ThinkPart
    | ApprovalPending
    | ApprovalGranted
    | ApprovalRejected
)
"""Any event, including control flow and content/tooling events."""


class ApprovalResponse(Enum):
    APPROVE = "approve"
    APPROVE_FOR_SESSION = "approve_for_session"
    REJECT = "reject"


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_call_id: str
    sender: str
    action: str
    description: str
    tool_args: dict[str, Any] | None = None  # Tool arguments for detailed display

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._future = asyncio.Future[ApprovalResponse]()

    async def wait(self) -> ApprovalResponse:
        """
        Wait for the request to be resolved or cancelled.

        Returns:
            ApprovalResponse: The response to the approval request.
        """
        return await self._future

    def resolve(self, response: ApprovalResponse) -> None:
        """
        Resolve the approval request with the given response.
        This will cause the `wait()` method to return the response.
        """
        self._future.set_result(response)

    @property
    def resolved(self) -> bool:
        """Whether the request is resolved."""
        return self._future.done()
