from __future__ import annotations

from abc import ABC
from typing import IO

from loguru import logger

logger.remove()


class StreamToLogger(IO[str], ABC):
    def __init__(self, level: str = "ERROR"):
        self._level = level

    def write(self, buffer: str) -> int:
        for line in buffer.rstrip().splitlines():
            logger.opt(depth=1).log(self._level, line.rstrip())
        return len(buffer)

    def flush(self) -> None:
        pass
