"""MCP (Model Context Protocol) server — exposes Adhkar IR ops as tools.

Wire-compatible with the MCP JSON-RPC 2.0 schema over HTTP. We expose:
- search_cases(query, limit)
- get_case(case_id)
- search_observables(data_type?, value_contains?, limit?)
- summarize_case(case_id)

This is the server side: external AI clients (Claude Desktop, etc.) can
connect via the streamable HTTP transport at /v1/mcp/rpc with a bearer
token and call these tools as if they were Anthropic tools."""
