"""MCP-specific asynchronous client for the current 1C.ai protocol.

The protocol behavior is derived from ROCTUP/1c-buddy's
``app/mcp/upstream_tools_client.py`` under GNU AGPL v3.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import Settings, get_settings
from .errors import UpstreamError
from .models import (
    ConversationRequest,
    ConversationResponse,
    MessageChunk,
    MessageRequest,
    StreamResult,
    ToolResultItem,
    ToolResultRequest,
)
from .text import sanitize_text

logger = logging.getLogger(__name__)


class OneCAIClient:
    """Minimal 1C.ai client required by the standalone MCP tools."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.ONEC_AI_BASE_URL
        self._last_assistant_uuid: dict[str, str | None] = {}
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.settings.ONEC_AI_TIMEOUT,
                read=None,
                write=self.settings.ONEC_AI_TIMEOUT,
                pool=self.settings.ONEC_AI_TIMEOUT,
            ),
            headers={
                "Accept": "*/*",
                "Accept-Charset": "utf-8",
                "Accept-Language": "ru-ru,en-us;q=0.8,en;q=0.7",
                **self.settings.authorization_headers(),
                "Content-Type": "application/json; charset=utf-8",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/chat/",
                "User-Agent": "1c-buddy-mcp/0.1",
            },
        )

    async def __aenter__(self) -> "OneCAIClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def create_conversation(
        self,
        programming_language: str | None = None,
    ) -> str:
        request_data = ConversationRequest(
            programming_language=(
                programming_language
                if programming_language is not None
                else self.settings.ONEC_AI_PROGRAMMING_LANGUAGE
            ),
            ui_language=self.settings.ONEC_AI_UI_LANGUAGE,
        )
        url = f"{self.base_url}/chat_api/v1/conversations/"
        try:
            response = await self._client.post(
                url,
                json=request_data.model_dump(),
                headers={"Session-Id": ""},
            )
        except httpx.RequestError as exc:
            raise UpstreamError("Network error creating conversation") from exc
        if response.status_code != 200:
            raise self._response_error("Conversation create error", response)
        try:
            conversation = ConversationResponse.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise UpstreamError("Invalid conversation response") from exc
        self._last_assistant_uuid[conversation.uuid] = None
        return conversation.uuid

    async def send_prompt(
        self,
        conversation_id: str,
        *,
        instruction: str,
        parent_uuid: str | None = None,
    ) -> StreamResult:
        result = await self._send_user_message(
            conversation_id,
            instruction,
            parent_uuid=parent_uuid,
        )
        aggregate = result.model_copy(deep=True)
        while result.tool_calls and result.assistant_uuid:
            result = await self._respond_to_tool_call(
                conversation_id,
                assistant_uuid=result.assistant_uuid,
                tool_call=result.tool_calls[-1],
            )
            aggregate.assistant_uuid = result.assistant_uuid or aggregate.assistant_uuid
            aggregate.final_text = result.final_text or aggregate.final_text
            aggregate.full_text = self._merge_text(
                aggregate.full_text,
                result.full_text or result.final_text,
            )
            aggregate.tool_calls = list(result.tool_calls)
            aggregate.tool_results.extend(result.tool_results)
            aggregate.tool_followups.extend(result.tool_followups)
        return aggregate

    async def call_task(
        self,
        conversation_id: str,
        *,
        instruction: str,
        skill: str,
        parent_uuid: str | None = None,
    ) -> StreamResult:
        del skill  # Current upstream uses the instruction flow for these tasks.
        result = await self.send_prompt(
            conversation_id,
            instruction=instruction,
            parent_uuid=parent_uuid,
        )
        task_text = self._extract_task_result(result.tool_calls)
        if task_text:
            result.final_text = task_text
            result.full_text = self._merge_text(result.full_text, task_text)
            result.tool_calls = []
        return result

    async def call_exact_tool(
        self,
        conversation_id: str,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        parent_uuid: str | None = None,
    ) -> StreamResult:
        assistant_uuid, tool_call_id = await self._request_exact_tool_call(
            conversation_id,
            tool_name=tool_name,
            arguments=arguments,
            parent_uuid=parent_uuid,
        )
        payload = ToolResultRequest(
            parent_uuid=assistant_uuid,
            content=[ToolResultItem(tool_call_id=tool_call_id)],
        ).model_dump()
        return await self._collect_stream(conversation_id, payload)

    async def _send_user_message(
        self,
        conversation_id: str,
        instruction: str,
        *,
        parent_uuid: str | None = None,
    ) -> StreamResult:
        payload = MessageRequest.from_instruction(
            instruction,
            parent_uuid=parent_uuid,
        ).model_dump()
        return await self._collect_stream(conversation_id, payload)

    async def _ensure_assistant_uuid(
        self,
        conversation_id: str,
        parent_uuid: str | None,
    ) -> str:
        if parent_uuid:
            return parent_uuid
        remembered = self._last_assistant_uuid.get(conversation_id)
        if remembered:
            return remembered
        bootstrap = await self._send_user_message(
            conversation_id,
            "Ответь одним словом: Готово.",
        )
        if not bootstrap.assistant_uuid:
            raise UpstreamError("Unable to obtain assistant parent UUID")
        return bootstrap.assistant_uuid

    async def _request_exact_tool_call(
        self,
        conversation_id: str,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        parent_uuid: str | None,
    ) -> tuple[str, str]:
        resolved_parent = await self._ensure_assistant_uuid(
            conversation_id,
            parent_uuid,
        )
        instruction = (
            "Внутренняя инструкция.\n"
            f"Нужно вернуть ровно один tool call для {tool_name}.\n"
            "Не используй другие инструменты.\n"
            "Сохрани все символы в аргументах без изменений.\n"
            "Используй ровно эти JSON-аргументы: "
            f"{json.dumps(arguments, ensure_ascii=False)}\n"
            "Не отвечай обычным текстом до tool call."
        )
        result = await self._send_user_message(
            conversation_id,
            instruction,
            parent_uuid=resolved_parent,
        )
        if not result.assistant_uuid or not result.tool_calls:
            raise UpstreamError(f"Unable to obtain upstream tool call for {tool_name}")
        tool_call = result.tool_calls[0]
        function = tool_call.get("function") or {}
        tool_call_id = tool_call.get("id")
        if function.get("name") != tool_name or not tool_call_id:
            raise UpstreamError(f"Unexpected upstream tool call for {tool_name}")
        return result.assistant_uuid, str(tool_call_id)

    async def _respond_to_tool_call(
        self,
        conversation_id: str,
        *,
        assistant_uuid: str,
        tool_call: dict[str, Any],
    ) -> StreamResult:
        function = tool_call.get("function") or {}
        if not function.get("name") or not tool_call.get("id"):
            raise UpstreamError("Upstream tool call is missing tool name or id")
        payload = ToolResultRequest(
            parent_uuid=assistant_uuid,
            content=[ToolResultItem(tool_call_id=str(tool_call["id"]))],
        ).model_dump()
        return await self._collect_stream(conversation_id, payload)

    async def _collect_stream(
        self,
        conversation_id: str,
        payload: dict[str, Any],
    ) -> StreamResult:
        result = StreamResult()
        url = f"{self.base_url}/chat_api/v1/conversations/{conversation_id}/messages"
        accumulated = ""
        current_assistant_uuid: str | None = None
        last_tool_call_id = ""
        try:
            stream_context = self._client.stream(
                "POST",
                url,
                json=payload,
                headers={"Accept": "text/event-stream"},
            )
            async with stream_context as response:
                if response.status_code != 200:
                    await response.aread()
                    raise self._response_error("Message send error", response)
                response.encoding = "utf-8"
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw_json = line[5:].strip()
                    if not raw_json or raw_json == "[DONE]":
                        continue
                    try:
                        chunk = MessageChunk.model_validate_json(raw_json)
                    except (ValueError, TypeError) as exc:
                        logger.warning("Ignoring invalid 1C.ai SSE event: %s", exc)
                        continue
                    if chunk.role == "assistant" and chunk.uuid:
                        current_assistant_uuid = chunk.uuid
                    if chunk.role == "tool" and chunk.finished:
                        self._append_tool_results(result, chunk.render_info)
                        continue
                    content = chunk.content or {}
                    tool_calls = content.get("tool_calls")
                    if isinstance(tool_calls, list) and tool_calls:
                        result.tool_calls = tool_calls
                        last_tool_call_id = str(tool_calls[-1].get("id") or "")
                    cumulative = content.get("content")
                    if cumulative is None:
                        cumulative = content.get("text")
                    if isinstance(cumulative, str):
                        accumulated = cumulative
                    elif chunk.content_delta and chunk.content_delta.content is not None:
                        accumulated += chunk.content_delta.content
                    if accumulated:
                        result.full_text = accumulated
                    if chunk.finished and chunk.role == "assistant":
                        result.assistant_uuid = chunk.uuid or current_assistant_uuid
                        result.final_text = accumulated.strip()
                        result.full_text = accumulated.strip()
                        break
        except httpx.RequestError as exc:
            raise UpstreamError("Network error sending message") from exc
        if not result.assistant_uuid and current_assistant_uuid:
            result.assistant_uuid = current_assistant_uuid
        if result.assistant_uuid:
            self._last_assistant_uuid[conversation_id] = result.assistant_uuid
        if not result.final_text:
            result.final_text = result.full_text.strip()
        result.final_text = sanitize_text(result.final_text)
        result.full_text = sanitize_text(result.full_text)
        if last_tool_call_id and result.full_text and result.tool_results:
            result.tool_followups.append(
                {"tool_call_id": last_tool_call_id, "text": result.full_text},
            )
        return result

    @staticmethod
    def _append_tool_results(result: StreamResult, render_info: Any) -> None:
        if not isinstance(render_info, list):
            return
        for item in render_info:
            if not isinstance(item, dict):
                continue
            details = item.get("details") or {}
            result.tool_results.append(
                {
                    "tool_call_id": item.get("tool_call_id", ""),
                    "tool_name": item.get("tool_name", ""),
                    "response_markdown": item.get("response_markdown") or "",
                    "response_details": details.get("response_details") or [],
                    "hide_after": item.get("hide_after", True),
                },
            )

    @staticmethod
    def _merge_text(current: str, candidate: str) -> str:
        current = current.strip()
        candidate = candidate.strip()
        if not candidate or candidate in current:
            return current
        if not current or current in candidate:
            return candidate
        return f"{current}\n\n{candidate}"

    @staticmethod
    def _extract_task_result(tool_calls: list[dict[str, Any]]) -> str | None:
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            if function.get("name") != "TaskResult":
                continue
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    continue
            if isinstance(arguments, dict) and isinstance(arguments.get("result"), str):
                return sanitize_text(arguments["result"])
        return None

    @staticmethod
    def _response_error(message: str, response: httpx.Response) -> UpstreamError:
        data: dict[str, Any] = {"upstream_status": response.status_code}
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            detail = parsed.get("message") or parsed.get("detail")
            if isinstance(detail, str):
                data["detail"] = detail[:2000]
        return UpstreamError(message, status_code=response.status_code, data=data)
