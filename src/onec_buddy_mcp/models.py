"""Pydantic models for the current 1C.ai protocol."""

from typing import Any

from pydantic import BaseModel, Field


class ConversationRequest(BaseModel):
    is_chat: bool = True
    programming_language: str = ""
    skill_name: str = "custom"
    ui_language: str = "russian"


class ConversationResponse(BaseModel):
    uuid: str


class MessageContentInner(BaseModel):
    instruction: str


class MessageContentOuter(BaseModel):
    content: MessageContentInner
    tools: list[Any] = Field(default_factory=list)


class MessageRequest(BaseModel):
    content: MessageContentOuter
    parent_uuid: str | None = None
    role: str = "user"

    @classmethod
    def from_instruction(
        cls,
        instruction: str,
        parent_uuid: str | None = None,
    ) -> "MessageRequest":
        return cls(
            content=MessageContentOuter(
                content=MessageContentInner(instruction=instruction),
            ),
            parent_uuid=parent_uuid,
        )


class ContentDelta(BaseModel):
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: Any | None = None


class MessageChunk(BaseModel):
    uuid: str = ""
    role: str | None = None
    content: dict[str, Any] | None = None
    content_delta: ContentDelta | None = None
    parent_uuid: str | None = None
    finished: bool = False
    render_info: Any | None = None


class ToolResultItem(BaseModel):
    status: str = "accepted"
    tool_call_id: str
    content: Any | None = None


class ToolResultRequest(BaseModel):
    role: str = "tool"
    parent_uuid: str
    content: list[ToolResultItem]


class StreamResult(BaseModel):
    assistant_uuid: str | None = None
    final_text: str = ""
    full_text: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    tool_followups: list[dict[str, Any]] = Field(default_factory=list)
