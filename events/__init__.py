from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loop.types import ContentPart, ToolCallPart

from utils.logging import logger

if TYPE_CHECKING:
    from events.message import ApprovalRequest, Event


type StreamMessage = Event | ApprovalRequest


class Stream:
    """
    A channel for communication between the loop and the UI during a loop run.
    """

    def __init__(self):
        self._queue = asyncio.Queue[StreamMessage]()
        self._loop_side = StreamLoopSide(self._queue)
        self._ui_side = StreamUISide(self._queue)

    @property
    def loop_side(self) -> StreamLoopSide:
        return self._loop_side

    @property
    def ui_side(self) -> StreamUISide:
        return self._ui_side

    def shutdown(self) -> None:
        logger.debug("Shutting down stream")
        self._queue.shutdown()


class StreamLoopSide:
    """
    The loop side of a stream.
    """

    def __init__(self, queue: asyncio.Queue[StreamMessage]):
        self._queue = queue

    def send(self, msg: StreamMessage) -> None:
        if not isinstance(msg, ContentPart | ToolCallPart):
            logger.debug("Sending stream message: {msg}", msg=msg)
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueShutDown:
            logger.info("Failed to send stream message, queue is shut down: {msg}", msg=msg)


class StreamUISide:
    """
    The UI side of a stream.
    """

    def __init__(self, queue: asyncio.Queue[StreamMessage]):
        self._queue = queue

    async def receive(self) -> StreamMessage:
        msg = await self._queue.get()
        if not isinstance(msg, ContentPart | ToolCallPart):
            logger.debug("Receiving stream message: {msg}", msg=msg)
        return msg

    def receive_nowait(self) -> StreamMessage | None:
        """
        Try receive a message without waiting. If no message is available, return None.
        """
        try:
            msg = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        if not isinstance(msg, ContentPart | ToolCallPart):
            logger.debug("Receiving stream message: {msg}", msg=msg)
        return msg
