from typing import Any

import pytest

from onec_buddy_mcp import server
from onec_buddy_mcp.limitations import append_tool_limitations


@pytest.mark.asyncio
async def test_server_lists_all_public_tools() -> None:
    tools = await server.mcp.list_tools()

    assert {tool.name for tool in tools} == {
        "ask_1c_ai",
        "explain_1c_syntax",
        "check_1c_code",
        "modify_1c_code",
        "search_1c_documentation",
        "search_its",
        "fetch_its",
        "diff_1c_documentation_versions",
    }


@pytest.mark.asyncio
async def test_registered_tool_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_invoke(method: str, **kwargs: Any) -> str:
        captured.update({"method": method, **kwargs})
        return "Ответ"

    monkeypatch.setattr(server, "_invoke", fake_invoke)

    result = await server.mcp.call_tool(
        "ask_1c_ai",
        {"question": "Как выполнить запрос?"},
    )

    assert captured == {
        "method": "ask_1c_ai",
        "question": "Как выполнить запрос?",
        "programming_language": "",
        "ssl_version": "",
        "configuration": "",
    }
    content, structured = result
    assert content[0].text == "Ответ"
    assert structured == {"result": "Ответ"}


@pytest.mark.parametrize(
    ("tool_name", "expected"),
    [
        ("ask_1c_ai", "фактические ошибки"),
        ("explain_1c_syntax", "официальную документацию"),
        ("check_1c_code", "переданный фрагмент"),
        ("modify_1c_code", "не применён и не протестирован"),
        ("search_1c_documentation", "индекса документации"),
        ("search_its", "другому продукту"),
        ("fetch_its", "идентификатора и прав доступа"),
        ("diff_1c_documentation_versions", "не доказывает отсутствие изменений"),
    ],
)
def test_append_tool_specific_limitations(tool_name: str, expected: str) -> None:
    result = append_tool_limitations(tool_name, "Ответ")

    assert result.startswith("## Ответ\n\nОтвет")
    assert "## Ограничения инструмента" in result
    assert expected in result


def test_limitations_can_be_disabled() -> None:
    assert append_tool_limitations("ask_1c_ai", "Ответ", enabled=False) == "Ответ"


def test_error_response_is_not_reformatted() -> None:
    response = "Ошибка: сервис недоступен"

    assert append_tool_limitations("ask_1c_ai", response) == response
