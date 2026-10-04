# LOM P1 — Governed MCP Interoperability Adapter

Status: DEVELOPMENT / NON-PRODUCTION / METADATA-ONLY

P1 allows LOM to understand MCP discovery metadata while preserving existing LOM connector, action, capability and human-gate authority.

Protocol baseline: **MCP 2026-07-28**.

MCP server claims are never authority. A tool is eligible only when the exact tool name has a local LOM binding to the canonical connector registry, action `READ_ONLY_OBSERVATION`, capability `cap.observe.readonly`, and an already-permitted resource scope.

P1 supports protocol-version validation, server capability projection, tools/resources/prompts metadata normalization, denial of unbound tools, recognition of the Tasks extension, and task-handle/status validation.

P1 does not enable live HTTP/stdio connections, OAuth/DCR, credentials, `tools/call`, resource reads, prompt fetch, task polling/update/cancel, write-capable tools, or Production actions. An MCP task with `input_required` always enters a HUMAN_GATE and is never auto-answered.

Authority: PREPARE_PR ceiling; execution NONE; Production HUMAN_ONLY; protected-main HUMAN_ONLY; network DISABLED; credentials NONE; task runtime DISABLED; server authority untrusted.
