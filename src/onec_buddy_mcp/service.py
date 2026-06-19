"""Transport-independent implementation of the eight public MCP tools.

Tool schemas, prompts, and upstream mappings are derived from
ROCTUP/1c-buddy's ``app/mcp/handlers.py`` under GNU AGPL v3.
"""

from __future__ import annotations

from typing import Literal

from .client import OneCAIClient
from .models import StreamResult
from .text import prepare_input, sanitize_text


class OneCToolService:
    def __init__(self, client: OneCAIClient) -> None:
        self.client = client
        self.settings = client.settings

    async def ask_1c_ai(
        self,
        question: str,
        *,
        programming_language: str = "",
        ssl_version: str = "",
        configuration: str = "",
    ) -> str:
        prepared = self._required(question, "question")
        context = self._context_hint(configuration, ssl_version)
        if context:
            prepared = f"{prepared}\n\n{context}"
        conversation_id = await self.client.create_conversation(
            programming_language or None,
        )
        result = await self._task_or_prompt(
            conversation_id,
            instruction=prepared,
            skill="custom",
        )
        return self._extract_result(result)

    async def explain_1c_syntax(
        self,
        syntax_element: str,
        *,
        context: str = "",
        ssl_version: str = "",
        configuration: str = "",
    ) -> str:
        element = self._required(syntax_element, "syntax_element")
        question = f"Объясни синтаксис и использование: {element}"
        if context.strip():
            question += f" в контексте: {context.strip()}"
        project_context = self._context_hint(configuration, ssl_version)
        if project_context:
            question += f"\n\n{project_context}"
        conversation_id = await self.client.create_conversation()
        result = await self._task_or_prompt(
            conversation_id,
            instruction=question,
            skill="explain",
        )
        return self._extract_result(result)

    async def check_1c_code(
        self,
        code: str,
        *,
        check_type: Literal["syntax", "review", "logic", "performance"] = "syntax",
        extended: bool = False,
    ) -> str:
        prepared_code = self._required(code, "code")
        normalized_type = {
            "logic": "review",
            "performance": "review",
        }.get(check_type, check_type)
        conversation_id = await self.client.create_conversation()
        if self._direct_mode() and normalized_type == "syntax":
            result = await self.client.call_exact_tool(
                conversation_id,
                tool_name="mcp__syntax-checker__validate",
                arguments={"code": prepared_code, "extended": extended},
            )
        else:
            instruction = (
                self._check_syntax_prompt(prepared_code, extended)
                if normalized_type == "syntax"
                else self._check_review_prompt(prepared_code)
            )
            result = await self._task_or_prompt(
                conversation_id,
                instruction=instruction,
                skill="review",
            )
        return self._extract_result(result, include_details=True)

    async def modify_1c_code(self, instruction: str, code: str = "") -> str:
        prepared_instruction = self._required(instruction, "instruction")
        prompt = self._modify_prompt(prepared_instruction, code.strip())
        conversation_id = await self.client.create_conversation()
        result = await self._task_or_prompt(
            conversation_id,
            instruction=prompt,
            skill="modify",
        )
        return self._extract_result(result)

    async def search_1c_documentation(
        self,
        query: str,
        *,
        version: str = "v8.5.1",
    ) -> str:
        prepared_query = self._required(query, "query")
        prepared_version = version.strip() or "v8.5.1"
        conversation_id = await self.client.create_conversation()
        if self._direct_mode():
            result = await self.client.call_exact_tool(
                conversation_id,
                tool_name="mcp__knowledge-hub__Search_Documentation",
                arguments={"query": prepared_query, "version": prepared_version},
            )
        else:
            result = await self.client.send_prompt(
                conversation_id,
                instruction=(
                    "Найди информацию в документации платформы 1С:Предприятие. "
                    f"Используй документацию версии {prepared_version}. "
                    "Верни краткий, но информативный ответ по найденным данным.\n\n"
                    f"Запрос: {prepared_query}"
                ),
            )
        return self._extract_result(result, include_details=True)

    async def search_its(
        self,
        query: str,
        *,
        ssl_version: str = "",
        configuration: str = "",
    ) -> str:
        prepared_query = self._required(query, "query")
        resolved_configuration = (
            configuration.strip() or self.settings.DEFAULT_1C_CONFIGURATION.strip()
        )
        resolved_ssl = ssl_version.strip() or self.settings.DEFAULT_SSL_VERSION.strip()
        conversation_id = await self.client.create_conversation()
        if self._direct_mode():
            prefix = self._context_prefix(resolved_configuration, resolved_ssl)
            search_query = f"{prefix} {prepared_query}".strip()
            result = await self.client.call_exact_tool(
                conversation_id,
                tool_name="mcp__knowledge-hub__Search_ITS",
                arguments={"query": search_query},
            )
        else:
            context = self._context_hint(resolved_configuration, resolved_ssl)
            result = await self.client.send_prompt(
                conversation_id,
                instruction=(
                    "Выполни поиск в базе знаний ИТС по этому запросу. "
                    "Верни фактический результат и обязательно сохрани ссылки на источники.\n"
                    f"{context}\n\nЗапрос: {prepared_query}"
                ),
            )
        return self._extract_result(result, include_details=True)

    async def fetch_its(self, item_id: str = "root") -> str:
        prepared_id = item_id.strip() or "root"
        conversation_id = await self.client.create_conversation()
        if self._direct_mode():
            result = await self.client.call_exact_tool(
                conversation_id,
                tool_name="mcp__knowledge-hub__Fetch_ITS",
                arguments={"id": prepared_id},
            )
        else:
            result = await self.client.send_prompt(
                conversation_id,
                instruction=(
                    "Получить содержимое документа, каталога или базы ИТС по "
                    f"идентификатору.\n\nid: {prepared_id}"
                ),
            )
        return self._extract_result(result, include_details=True)

    async def diff_1c_documentation_versions(
        self,
        version_a: str,
        version_b: str,
        *,
        query: str = "",
    ) -> str:
        first = self._required(version_a, "version_a")
        second = self._required(version_b, "version_b")
        subject = query.strip()
        conversation_id = await self.client.create_conversation()
        if self._direct_mode():
            arguments = {"version_a": first, "version_b": second}
            if subject:
                arguments["query"] = subject
            result = await self.client.call_exact_tool(
                conversation_id,
                tool_name="mcp__knowledge-hub__Diff_Documentation_Versions",
                arguments=arguments,
            )
        else:
            scope = f"\nПредметная область: {subject}" if subject else ""
            result = await self.client.send_prompt(
                conversation_id,
                instruction=(
                    "Сравни документацию платформы 1С между двумя версиями и "
                    "верни различия.\n\n"
                    f"Более ранняя версия: {first}\n"
                    f"Более поздняя версия: {second}{scope}"
                ),
            )
        return self._extract_result(result, include_details=True)

    async def _task_or_prompt(
        self,
        conversation_id: str,
        *,
        instruction: str,
        skill: str,
    ) -> StreamResult:
        if self._direct_mode():
            return await self.client.call_task(
                conversation_id,
                instruction=instruction,
                skill=skill,
            )
        return await self.client.send_prompt(
            conversation_id,
            instruction=instruction,
        )

    def _required(self, value: str, name: str) -> str:
        return prepare_input(
            value,
            minimum=self.settings.MCP_TOOL_INPUT_MIN_LENGTH,
            maximum=self.settings.MCP_TOOL_INPUT_MAX_LENGTH,
            name=name,
        )

    def _direct_mode(self) -> bool:
        return self.settings.MCP_TOOL_CALL_MODE == "direct"

    def _context_prefix(self, configuration: str, ssl_version: str) -> str:
        parts: list[str] = []
        if configuration:
            parts.append(configuration)
        if ssl_version:
            parts.append(f"БСП {ssl_version}")
        return " ".join(parts)

    def _context_hint(self, configuration: str, ssl_version: str) -> str:
        resolved_configuration = (
            configuration.strip() or self.settings.DEFAULT_1C_CONFIGURATION.strip()
        )
        resolved_ssl = ssl_version.strip() or self.settings.DEFAULT_SSL_VERSION.strip()
        parts: list[str] = []
        if resolved_configuration:
            parts.append(f"конфигурация {resolved_configuration}")
        if resolved_ssl:
            parts.append(f"версия БСП {resolved_ssl}")
        return f"Контекст проекта: {', '.join(parts)}." if parts else ""

    @staticmethod
    def _check_review_prompt(code: str) -> str:
        return (
            "Проведи code review этого кода 1С. Найди ошибки, нарушения "
            "стандартов, риски и предложи исправленный вариант.\n\n"
            f"Код:\n```bsl\n{code}\n```"
        )

    @staticmethod
    def _check_syntax_prompt(code: str, extended: bool) -> str:
        suffix = " Используй расширенную проверку со стандартами 1С." if extended else ""
        return (
            "Проверь этот код 1С на синтаксические ошибки перед отправкой "
            f"пользователю.{suffix}\n\nКод:\n```bsl\n{code}\n```"
        )

    @staticmethod
    def _modify_prompt(instruction: str, code: str) -> str:
        prompt = (
            "Измени этот код 1С по заданию пользователя. Верни итоговый "
            "измененный код и кратко перечисли изменения.\n\n"
            f"Задание:\n{instruction}"
        )
        if code:
            prompt += f"\n\nКод:\n```bsl\n{code}\n```"
        return prompt

    @staticmethod
    def _extract_result(result: StreamResult, *, include_details: bool = False) -> str:
        blocks: list[str] = []
        for item in result.tool_results:
            markdown = str(item.get("response_markdown") or "").strip()
            if markdown and markdown != "✓ Инструмент выполнен":
                blocks.append(markdown)
            if include_details:
                blocks.extend(
                    str(detail)
                    for detail in item.get("response_details") or []
                    if detail
                )
        text = result.full_text or result.final_text
        if text:
            blocks.append(text)
        if not blocks and result.tool_followups:
            followup = result.tool_followups[-1].get("text")
            if followup:
                blocks.append(str(followup))
        return sanitize_text("\n".join(blocks))
