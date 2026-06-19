# 1c-buddy-mcp

Лёгкий standalone MCP-сервер для работы с [1C.ai](https://code.1c.ai) из
Codex и других MCP-клиентов. Запускается напрямую в Python через stdio: без
Docker, веб-чата, OpenAI-совместимого шлюза и отдельного HTTP-сервера.

Проект основан на MCP/API-реализации
[`ROCTUP/1c-buddy`](https://github.com/ROCTUP/1c-buddy). Последний проверенный
upstream commit: [`7f2b0305cd80e3a9f2cebb2dc69603fd7c7ab054`](https://github.com/ROCTUP/1c-buddy/commit/7f2b0305cd80e3a9f2cebb2dc69603fd7c7ab054).

## Инструменты

| Инструмент | Назначение |
| --- | --- |
| `ask_1c_ai` | Общие вопросы по платформе 1С и практическим сценариям |
| `explain_1c_syntax` | Объяснение объекта, метода, типа или конструкции 1С |
| `check_1c_code` | Синтаксическая проверка или code review BSL-кода |
| `modify_1c_code` | Изменение BSL-кода по явному заданию |
| `search_1c_documentation` | Поиск по документации платформы 1С:Предприятие |
| `search_its` | Поиск по базе знаний ИТС |
| `fetch_its` | Получение документа или раздела ИТС по `id` |
| `diff_1c_documentation_versions` | Сравнение документации между версиями платформы |

## Требования

- Python 3.10 или новее;
- Git;
- действующий токен 1C.ai в переменной `ONEC_AI_TOKEN`;
- Codex или другой MCP-клиент с поддержкой stdio.

## Установка в Windows PowerShell

```powershell
git clone https://github.com/VVi3ard/1c-buddy-mcp.git "$HOME\.codex\mcp\1c-buddy-mcp"
Set-Location "$HOME\.codex\mcp\1c-buddy-mcp"
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install .
```

Сохраните токен в пользовательском окружении и перезапустите Codex:

```powershell
[Environment]::SetEnvironmentVariable("ONEC_AI_TOKEN", "ВАШ_ТОКЕН", "User")
```

Не добавляйте токен в Git, README или публичные конфигурации.

## Установка в Linux/macOS

```bash
git clone https://github.com/VVi3ard/1c-buddy-mcp.git ~/.codex/mcp/1c-buddy-mcp
cd ~/.codex/mcp/1c-buddy-mcp
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
export ONEC_AI_TOKEN='ВАШ_ТОКЕН'
```

Для постоянного хранения переменной используйте защищённое хранилище или
конфигурацию оболочки с ограниченным доступом.

## Подключение к Codex

Добавьте в `C:\Users\<имя>\.codex\config.toml`:

```toml
[mcp_servers.onec-ai-1c]
command = 'C:\Users\<имя>\.codex\mcp\1c-buddy-mcp\.venv\Scripts\python.exe'
args = ["-m", "onec_buddy_mcp"]
cwd = 'C:\Users\<имя>\.codex\mcp\1c-buddy-mcp'
startup_timeout_sec = 30

[mcp_servers.onec-ai-1c.env]
ONEC_AI_UI_LANGUAGE = "russian"
ONEC_AI_TIMEOUT = "30"
MCP_TOOL_CALL_MODE = "direct"
```

Токен намеренно отсутствует в TOML: процесс получает `ONEC_AI_TOKEN` из
пользовательского окружения. После изменения конфигурации перезапустите Codex.

Для Linux/macOS укажите абсолютные пути к `.venv/bin/python` и каталогу
репозитория.

## Проверка

Установите зависимости разработки и запустите unit-тесты:

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Live-тест выполняется только по явному запросу и использует токен окружения:

```powershell
$env:RUN_LIVE_TESTS = "1"
& .\.venv\Scripts\python.exe -m pytest -m live -q
```

После перезапуска Codex проверьте список MCP-инструментов и выполните, например:

- `ask_1c_ai`: «Что такое ТаблицаЗначений?»;
- `check_1c_code`: синтаксическая проверка короткой процедуры;
- `search_1c_documentation`: поиск `HTTPСоединение` для нужной версии.

## Настройки

| Переменная | Обязательная | Значение по умолчанию |
| --- | --- | --- |
| `ONEC_AI_TOKEN` | да | — |
| `ONEC_AI_BASE_URL` | нет | `https://code.1c.ai` |
| `ONEC_AI_TIMEOUT` | нет | `30` |
| `ONEC_AI_UI_LANGUAGE` | нет | `russian` |
| `ONEC_AI_PROGRAMMING_LANGUAGE` | нет | пусто |
| `DEFAULT_SSL_VERSION` | нет | пусто |
| `DEFAULT_1C_CONFIGURATION` | нет | пусто |
| `MCP_TOOL_INPUT_MIN_LENGTH` | нет | `4` |
| `MCP_TOOL_INPUT_MAX_LENGTH` | нет | `100000` |
| `MCP_TOOL_CALL_MODE` | нет | `direct` |

`direct` вызывает специализированные upstream-инструменты для синтаксиса,
документации и ИТС. `standard` формулирует обычный запрос к 1C.ai и полезен как
режим совместимости при изменениях upstream.

## Обновление из upstream

Проекты имеют разные структуры и не предназначены для полного `git merge`.
Изменения 1C.ai API и MCP-инструментов переносятся контролируемо по инструкции
[docs/UPDATING_FROM_UPSTREAM.md](docs/UPDATING_FROM_UPSTREAM.md).

## Устранение проблем

- `ONEC_AI_TOKEN` missing: задайте пользовательскую переменную и полностью
  перезапустите Codex, чтобы новый процесс получил окружение.
- HTTP 401/403: токен отклонён 1C.ai или не передан процессу.
- HTTP 422: upstream изменил payload; сравните актуальные модули `1c-buddy` по
  руководству обновления.
- Сервер не появляется в Codex: проверьте абсолютные `command`, `cwd`, наличие
  `.venv` и запустите `python -m onec_buddy_mcp` вручную. В рабочем stdio-режиме
  процесс ожидает MCP-ввод и ничего не печатает в stdout.
- Поиск ИТС не возвращает данные: доступ зависит от возможностей аккаунта и
  текущих upstream-инструментов 1C.ai.

## Безопасность

- токен хранится как `SecretStr` и не включается в repr настроек;
- ошибки MCP не возвращают заголовок `Authorization`;
- логи пишутся в stderr, stdout зарезервирован для MCP;
- `.env`, виртуальные окружения и тестовые артефакты исключены из Git.

## Лицензия и авторство

Проект распространяется по [GNU AGPL v3](LICENSE). Реализация API-взаимодействия,
схемы инструментов и часть prompt-логики производны от
[`ROCTUP/1c-buddy`](https://github.com/ROCTUP/1c-buddy), также распространяемого
по GNU AGPL v3. Новый проект не является официальным продуктом фирмы «1С».
