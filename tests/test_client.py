import json
from collections.abc import Callable

import httpx
import pytest

from onec_buddy_mcp.client import OneCAIClient
from onec_buddy_mcp.config import Settings
from onec_buddy_mcp.errors import UpstreamError


def sse(*events: dict) -> str:
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> OneCAIClient:
    settings = Settings(_env_file=None, ONEC_AI_TOKEN="secret-token")
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer secret-token"},
    )
    return OneCAIClient(settings=settings, http_client=http_client)


@pytest.mark.asyncio
async def test_create_conversation_and_cumulative_content() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if request.url.path.endswith("/conversations/"):
            return httpx.Response(200, json={"uuid": "conversation-1"})
        return httpx.Response(
            200,
            text=sse(
                {
                    "uuid": "assistant-1",
                    "role": "assistant",
                    "content": {"content": "При"},
                    "finished": False,
                },
                {
                    "uuid": "assistant-1",
                    "role": "assistant",
                    "content": {"content": "Привет"},
                    "finished": True,
                },
            ),
            headers={"content-type": "text/event-stream; charset=utf-8"},
        )

    async with make_client(handler) as client:
        conversation_id = await client.create_conversation()
        result = await client.send_prompt(conversation_id, instruction="test")

    assert bodies[0] == {
        "is_chat": True,
        "programming_language": "",
        "skill_name": "custom",
        "ui_language": "russian",
    }
    assert bodies[1] == {
        "content": {"content": {"instruction": "test"}, "tools": []},
        "parent_uuid": None,
        "role": "user",
    }
    assert result.final_text == "Привет"
    assert result.full_text == "Привет"
    assert result.assistant_uuid == "assistant-1"


@pytest.mark.asyncio
async def test_incremental_content_delta_is_accumulated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=sse(
                {
                    "uuid": "assistant-2",
                    "role": "assistant",
                    "content_delta": {"content": "При"},
                    "finished": False,
                },
                {
                    "uuid": "assistant-2",
                    "role": "assistant",
                    "content_delta": {"content": "вет"},
                    "finished": True,
                },
            ),
            headers={"content-type": "text/event-stream; charset=utf-8"},
        )

    async with make_client(handler) as client:
        result = await client.send_prompt("conversation-2", instruction="test")

    assert result.final_text == "Привет"
    assert result.full_text == "Привет"
    assert result.assistant_uuid == "assistant-2"


@pytest.mark.asyncio
async def test_exact_tool_call_posts_accepted_result() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        call_number = len(bodies)
        if call_number == 1:
            events = ({
                "uuid": "assistant-bootstrap",
                "role": "assistant",
                "content": {"content": "Готово"},
                "finished": True,
            },)
        elif call_number == 2:
            events = ({
                "uuid": "assistant-tool-uuid",
                "role": "assistant",
                "content": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "mcp__syntax-checker__validate",
                            "arguments": json.dumps({"code": "x"}),
                        },
                    }],
                },
                "finished": True,
            },)
        else:
            events = ({
                "uuid": "assistant-final",
                "role": "assistant",
                "content": {"content": "Синтаксических ошибок не найдено"},
                "finished": True,
            },)
        return httpx.Response(
            200,
            text=sse(*events),
            headers={"content-type": "text/event-stream; charset=utf-8"},
        )

    async with make_client(handler) as client:
        result = await client.call_exact_tool(
            "conversation-3",
            tool_name="mcp__syntax-checker__validate",
            arguments={"code": "x"},
        )

    assert bodies[2] == {
        "role": "tool",
        "parent_uuid": "assistant-tool-uuid",
        "content": [{
            "status": "accepted",
            "tool_call_id": "call-1",
            "content": None,
        }],
    }
    assert result.final_text == "Синтаксических ошибок не найдено"


@pytest.mark.asyncio
async def test_exact_tool_rejects_unexpected_name() -> None:
    call_number = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_number
        call_number += 1
        if call_number == 1:
            event = {
                "uuid": "assistant-bootstrap",
                "role": "assistant",
                "content": {"content": "Готово"},
                "finished": True,
            }
        else:
            event = {
                "uuid": "assistant-tool",
                "role": "assistant",
                "content": {
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "unexpected", "arguments": "{}"},
                    }],
                },
                "finished": True,
            }
        return httpx.Response(
            200,
            text=sse(event),
            headers={"content-type": "text/event-stream; charset=utf-8"},
        )

    async with make_client(handler) as client:
        with pytest.raises(UpstreamError, match="Unexpected upstream tool call"):
            await client.call_exact_tool(
                "conversation-4",
                tool_name="mcp__syntax-checker__validate",
                arguments={"code": "x"},
            )


@pytest.mark.asyncio
async def test_error_does_not_expose_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    async with make_client(handler) as client:
        with pytest.raises(UpstreamError) as exc_info:
            await client.create_conversation()

    assert "secret-token" not in str(exc_info.value)
