"""Core type definitions for the loop system."""

from __future__ import annotations
from typing import TypeVar, Any, Union
from typing import Literal, ClassVar
from pydantic import BaseModel
import builtins


# --- Basic Type Aliases ---
T = TypeVar("T", bound=BaseModel)
JsonType = Union[dict[str, Any], list[Any], str, int, float, bool, None]


# --- Base Mixins ---
class MergeableMixin:
    """Mixin for objects that can be merged in place."""

    def merge_in_place(self, other: Any) -> None:
        """Merge another object into this one in place."""
        if hasattr(self, "text") and hasattr(other, "text"):
            self.text += other.text
        if hasattr(self, "arguments_part") and hasattr(other, "arguments_part"):
            self.arguments_part += other.arguments_part


# --- AI Usage and Step Result ---
class Usage(BaseModel):
    """Token usage statistics."""

    input: int = 0
    output: int = 0
    total: int = 0


# --- Content Parts ---
class TextPart(BaseModel, MergeableMixin):
    """Text content part."""

    type: Literal["text"] = "text"
    text: str


class ImageURL(BaseModel):
    """Image URL configuration."""

    url: str
    detail: str | None = None


class ImageURLPart(BaseModel, MergeableMixin):
    """Image content part."""

    type: Literal["image_url"] = "image_url"
    image_url: ImageURL | dict

    ImageURL: ClassVar[builtins.type[ImageURL]] = ImageURL


class AudioURL(BaseModel):
    """Audio URL configuration."""

    url: str


class AudioURLPart(BaseModel, MergeableMixin):
    """Audio content part."""

    type: Literal["audio_url"] = "audio_url"
    audio_url: AudioURL | dict

    AudioURL: ClassVar[builtins.type[AudioURL]] = AudioURL


class ThinkPart(BaseModel, MergeableMixin):
    """Thinking content part for AI reasoning."""

    type: Literal["thinking"] = "thinking"
    think: str  # Changed from 'thinking' to 'think' to match test usage


class FunctionBody(BaseModel):
    """Function call body definition."""

    name: str
    arguments: str | None


class ToolCall(BaseModel, MergeableMixin):
    """Tool call definition."""

    id: str
    type: Literal["function"] = "function"
    function: FunctionBody | dict

    FunctionBody: ClassVar[builtins.type[FunctionBody]] = FunctionBody


class ToolCallPart(BaseModel, MergeableMixin):
    """Tool call content part."""

    type: Literal["tool_calls"] = "tool_calls"
    tool_calls: list[ToolCall]
    arguments_part: str = ""


# Content part union type
ContentPart = TextPart | ImageURLPart | AudioURLPart | ThinkPart | ToolCallPart
