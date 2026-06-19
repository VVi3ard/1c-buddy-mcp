# Обновление из ROCTUP/1c-buddy

`1c-buddy-mcp` переносит только MCP- и 1C.ai-совместимую часть upstream. Полный
merge `ROCTUP/1c-buddy` не выполняется: его FastAPI, чат, OpenAI API, статика и
Docker находятся вне области проекта.

Текущий проверенный upstream commit:
`7f2b0305cd80e3a9f2cebb2dc69603fd7c7ab054`.

## 1. Добавить или обновить remote

```powershell
git remote get-url upstream 2>$null
git remote add upstream https://github.com/ROCTUP/1c-buddy.git
git fetch upstream
```

Если remote уже существует, команда `git remote add` не нужна. Запишите старый
commit из README и новый:

```powershell
$old = "7f2b0305cd80e3a9f2cebb2dc69603fd7c7ab054"
$new = git rev-parse upstream/main
```

Если основная ветка upstream называется иначе, используйте её фактическое имя.

## 2. Проверить релевантные модули

Выполните diff каждого пути отдельно:

```powershell
git diff $old $new -- app/mcp/upstream_tools_client.py
git diff $old $new -- app/mcp/handlers.py
git diff $old $new -- app/onec_models.py
git diff $old $new -- app/config.py
git diff $old $new -- app/streaming.py
git diff $old $new -- app/text_utils.py
git diff $old $new -- app/mcp/models.py
git diff $old $new -- app/mcp/http_transport.py
git diff $old $new -- app/mcp/session.py
```

Первые шесть файлов требуют обязательного просмотра. Последние три проверяются
на изменения MCP-схемы и поведения сессий; FastAPI-транспорт переносить не надо.

## 3. Карта переноса

| Upstream | Локальный модуль | Что проверять |
| --- | --- | --- |
| `app/mcp/upstream_tools_client.py` | `src/onec_buddy_mcp/client.py` | URL, headers, payload, SSE, UUID, tool call/result |
| `app/onec_models.py` | `src/onec_buddy_mcp/models.py` | поля запросов, chunks, tool results |
| `app/mcp/handlers.py` | `src/onec_buddy_mcp/service.py`, `server.py` | имена, схемы, defaults, prompts, upstream mappings |
| `app/config.py` | `src/onec_buddy_mcp/config.py` | только MCP/1C.ai-настройки |
| `app/streaming.py` | `src/onec_buddy_mcp/text.py`, `client.py` | очистка и сборка текста |
| `app/text_utils.py` | `src/onec_buddy_mcp/text.py` | ограничения и нормализация ввода |
| `app/mcp/models.py` | `src/onec_buddy_mcp/server.py` | MCP tool schemas/results |
| `app/mcp/http_transport.py` | обычно не переносится | версии MCP и ошибки транспорта |
| `app/mcp/session.py` | обычно не переносится | семантика изоляции разговоров |

Не копируйте `app/onec_client.py`: это клиент чат/OpenAI-потоков. В качестве
источника протокольной истины используется MCP-specific
`app/mcp/upstream_tools_client.py`.

## 4. Обновить через тесты

Перед изменением добавьте failing test для нового upstream-поведения:

- payload/SSE/tool flow — `tests/test_client.py`;
- schema, prompt или mapping — `tests/test_service.py`;
- публичное MCP-описание — `tests/test_server.py`.

После минимального переноса выполните:

```powershell
& .\.venv\Scripts\python.exe -m pytest -m "not live" -q
& .\.venv\Scripts\python.exe -m compileall -q src
git diff --check
```

Затем, при наличии тестового токена:

```powershell
$env:RUN_LIVE_TESTS = "1"
& .\.venv\Scripts\python.exe -m pytest -m live -q
```

Отдельно проверьте MCP handshake, список восьми инструментов и минимум два live
вызова: обычный (`ask_1c_ai`) и direct (`check_1c_code` или поиск документации).

## 5. Зафиксировать результат

Обновите полный upstream commit одновременно в:

- `README.md` — вводный раздел и ссылка на commit;
- этом файле — строка «Текущий проверенный upstream commit».

В commit message укажите диапазон проверки, например:

```text
chore: sync 1c-buddy protocol through <short-commit>
```

Если релевантных изменений нет, обновляйте commit только после успешного
просмотра всех путей и тестов. Не объявляйте совместимость с upstream commit,
который не был проверен.
