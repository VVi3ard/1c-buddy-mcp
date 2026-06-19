# Tool limitations design

Every successful MCP tool response is supplemented with a deterministic Russian-language `Ограничения инструмента` section. The text is selected by the public tool name and is generated locally, after the upstream 1C.ai response, so it cannot be omitted or rewritten by the model.

Warnings are enabled by default and can be disabled with `ONEC_AI_INCLUDE_LIMITATIONS=false`. Error responses are left unchanged because no AI answer was produced. Public tool names, arguments and return type remain compatible.

The formatter is isolated from transport and upstream-client code. Unit tests cover every public tool, the environment switch and error handling; the full suite and one live stdio call provide final verification.
