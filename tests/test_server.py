from typing import Any

import pytest

from onec_buddy_mcp import server


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
