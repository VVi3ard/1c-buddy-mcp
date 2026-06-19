from typing import Any

import pytest

from onec_buddy_mcp.config import Settings
from onec_buddy_mcp.models import StreamResult
from onec_buddy_mcp.service import OneCToolService


class FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.conversations = 0

    async def create_conversation(
        self,
        programming_language: str | None = None,
    ) -> str:
        self.conversations += 1
        self.calls.append(
            ("create_conversation", {"programming_language": programming_language}),
        )
        return f"conversation-{self.conversations}"

    async def call_task(self, conversation_id: str, **kwargs: Any) -> StreamResult:
        self.calls.append(("call_task", {"conversation_id": conversation_id, **kwargs}))
        return StreamResult(final_text="task result", full_text="task result")

    async def send_prompt(self, conversation_id: str, **kwargs: Any) -> StreamResult:
        self.calls.append(("send_prompt", {"conversation_id": conversation_id, **kwargs}))
        return StreamResult(final_text="prompt result", full_text="prompt result")

    async def call_exact_tool(
        self,
        conversation_id: str,
        **kwargs: Any,
    ) -> StreamResult:
        self.calls.append(
            ("call_exact_tool", {"conversation_id": conversation_id, **kwargs}),
        )
        return StreamResult(final_text="direct result", full_text="direct result")


def make_service(**overrides: Any) -> tuple[OneCToolService, FakeClient]:
    settings = Settings(
        _env_file=None,
        ONEC_AI_TOKEN="secret-token",
        **overrides,
    )
    client = FakeClient(settings)
    return OneCToolService(client), client  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_ask_1c_ai_uses_custom_task_and_project_context() -> None:
    service, client = make_service(
        DEFAULT_SSL_VERSION="3.1",
        DEFAULT_1C_CONFIGURATION="ERP",
    )

    answer = await service.ask_1c_ai("Как выполнить запрос?")

    assert answer == "task result"
    method, call = client.calls[-1]
    assert method == "call_task"
    assert call["skill"] == "custom"
    assert "конфигурация ERP" in call["instruction"]
    assert "версия БСП 3.1" in call["instruction"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected_skill"),
    [
        ("explain", "explain"),
        ("review", "review"),
        ("modify", "modify"),
    ],
)
async def test_task_operations_use_expected_skills(
    operation: str,
    expected_skill: str,
) -> None:
    service, client = make_service()

    if operation == "explain":
        await service.explain_1c_syntax("ТаблицаЗначений")
    elif operation == "review":
        await service.check_1c_code("Процедура Тест()\nКонецПроцедуры", check_type="review")
    else:
        await service.modify_1c_code("Переименуй процедуру", "Процедура Тест()")

    method, call = client.calls[-1]
    assert method == "call_task"
    assert call["skill"] == expected_skill


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected_tool", "expected_arguments"),
    [
        (
            "syntax",
            "mcp__syntax-checker__validate",
            {"code": "Процедура Тест()", "extended": True},
        ),
        (
            "documentation",
            "mcp__knowledge-hub__Search_Documentation",
            {"query": "HTTPСоединение", "version": "v8.3.27"},
        ),
        (
            "its",
            "mcp__knowledge-hub__Search_ITS",
            {"query": "обновление конфигурации"},
        ),
        (
            "fetch",
            "mcp__knowledge-hub__Fetch_ITS",
            {"id": "its-123"},
        ),
        (
            "diff",
            "mcp__knowledge-hub__Diff_Documentation_Versions",
            {"version_a": "v8.3.26", "version_b": "v8.3.27", "query": "HTTP"},
        ),
    ],
)
async def test_direct_operations_use_exact_upstream_tools(
    operation: str,
    expected_tool: str,
    expected_arguments: dict[str, Any],
) -> None:
    service, client = make_service()

    if operation == "syntax":
        await service.check_1c_code("Процедура Тест()", extended=True)
    elif operation == "documentation":
        await service.search_1c_documentation("HTTPСоединение", version="v8.3.27")
    elif operation == "its":
        await service.search_its("обновление конфигурации")
    elif operation == "fetch":
        await service.fetch_its("its-123")
    else:
        await service.diff_1c_documentation_versions(
            "v8.3.26",
            "v8.3.27",
            query="HTTP",
        )

    method, call = client.calls[-1]
    assert method == "call_exact_tool"
    assert call["tool_name"] == expected_tool
    assert call["arguments"] == expected_arguments


@pytest.mark.asyncio
async def test_standard_mode_uses_prompt_flow() -> None:
    service, client = make_service(MCP_TOOL_CALL_MODE="standard")

    answer = await service.search_1c_documentation("HTTPСоединение")

    assert answer == "prompt result"
    assert client.calls[-1][0] == "send_prompt"


@pytest.mark.asyncio
async def test_empty_input_fails_before_conversation() -> None:
    service, client = make_service()

    with pytest.raises(ValueError, match="question"):
        await service.ask_1c_ai(" ")

    assert client.conversations == 0


@pytest.mark.asyncio
async def test_search_its_prefixes_explicit_context() -> None:
    service, client = make_service()

    await service.search_its(
        "регламентное задание",
        configuration="ERP",
        ssl_version="3.1",
    )

    _, call = client.calls[-1]
    assert call["arguments"] == {"query": "ERP БСП 3.1 регламентное задание"}
