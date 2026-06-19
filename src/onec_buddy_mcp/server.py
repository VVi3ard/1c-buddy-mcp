"""FastMCP stdio entry point for the standalone 1C.ai tools."""

from __future__ import annotations

import logging
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .client import OneCAIClient
from .config import get_settings
from .errors import UpstreamError
from .limitations import append_tool_limitations
from .service import OneCToolService

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "1c-buddy-mcp",
    instructions=(
        "Инструменты 1С.ai для вопросов по платформе 1С, проверки и изменения "
        "BSL-кода, поиска по документации платформы и ИТС."
    ),
    log_level="WARNING",
)


async def _invoke(method: str, **kwargs: Any) -> str:
    """Create an isolated upstream client for one MCP invocation."""

    try:
        settings = get_settings()
        async with OneCAIClient(settings) as client:
            service = OneCToolService(client)
            operation = getattr(service, method)
            response = await operation(**kwargs)
            return append_tool_limitations(
                method,
                response,
                enabled=settings.ONEC_AI_INCLUDE_LIMITATIONS,
            )
    except (ValueError, UpstreamError) as exc:
        return f"Ошибка: {exc}"
    except Exception:
        logger.exception("Unexpected failure in MCP tool %s", method)
        return "Ошибка: непредвиденная ошибка при обращении к 1C.ai"


@mcp.tool()
async def ask_1c_ai(
    question: str,
    programming_language: str = "",
    ssl_version: str = "",
    configuration: str = "",
) -> str:
    """Общие вопросы по платформе 1С и практическим сценариям."""

    return await _invoke(
        "ask_1c_ai",
        question=question,
        programming_language=programming_language,
        ssl_version=ssl_version,
        configuration=configuration,
    )


@mcp.tool()
async def explain_1c_syntax(
    syntax_element: str,
    context: str = "",
    ssl_version: str = "",
    configuration: str = "",
) -> str:
    """Объяснение объекта, метода, типа или конструкции платформы 1С."""

    return await _invoke(
        "explain_1c_syntax",
        syntax_element=syntax_element,
        context=context,
        ssl_version=ssl_version,
        configuration=configuration,
    )


@mcp.tool()
async def check_1c_code(
    code: str,
    check_type: Literal["syntax", "review", "logic", "performance"] = "syntax",
    extended: bool = False,
) -> str:
    """Синтаксическая проверка или code review фрагмента BSL-кода."""

    return await _invoke(
        "check_1c_code",
        code=code,
        check_type=check_type,
        extended=extended,
    )


@mcp.tool()
async def modify_1c_code(instruction: str, code: str = "") -> str:
    """Изменение BSL-кода по явному заданию пользователя."""

    return await _invoke(
        "modify_1c_code",
        instruction=instruction,
        code=code,
    )


@mcp.tool()
async def search_1c_documentation(
    query: str,
    version: str = "v8.5.1",
) -> str:
    """Поиск по документации платформы 1С:Предприятие указанной версии."""

    return await _invoke(
        "search_1c_documentation",
        query=query,
        version=version,
    )


@mcp.tool()
async def search_its(
    query: str,
    ssl_version: str = "",
    configuration: str = "",
) -> str:
    """Поиск материалов в базе знаний ИТС с идентификаторами источников."""

    return await _invoke(
        "search_its",
        query=query,
        ssl_version=ssl_version,
        configuration=configuration,
    )


@mcp.tool()
async def fetch_its(id: str = "root") -> str:
    """Получение содержимого документа или раздела ИТС по идентификатору."""

    return await _invoke("fetch_its", item_id=id)


@mcp.tool()
async def diff_1c_documentation_versions(
    version_a: str,
    version_b: str,
    query: str = "",
) -> str:
    """Сравнение документации платформы между двумя версиями."""

    return await _invoke(
        "diff_1c_documentation_versions",
        version_a=version_a,
        version_b=version_b,
        query=query,
    )


def main() -> None:
    """Run the server using an MCP-safe stdio channel."""

    mcp.run(transport="stdio")
