# mcp-chaos-monkey

Chaos/fault injection framework for [MCP (Model Context Protocol)](https://modelcontextprotocol.io) projects.

Inject faults at the transport level so resilience wrappers (circuit breakers, retries, timeouts) exercise naturally — without changing application code.

## Packages

| Package | Language | Status |
|---------|----------|--------|
| [`typescript/`](typescript/) | Node.js / TypeScript | Active |
| [`python/`](python/) | Python | Planned |

## Original Contribution

**mcp-chaos-monkey** is an original open-source contribution to the MCP ecosystem. No existing tool addressed systematic chaos testing for MCP-based systems, so this framework was created as a standalone, reusable npm package that any MCP project can adopt to validate its resilience stack under realistic failure conditions.

For a production-grade example of using mcp-chaos-monkey, see [reliable-mcp](https://github.com/alexey-tyurin/reliable-mcp) — an MCP Reliability Playbook that uses this framework for chaos testing with 21 automated fault injection scenarios.

## Features

- **8 fault types:** latency, error, timeout, malformed, connection-refused, connection-drop, rate-limit, schema-mismatch
- **Transport-level interception:** HTTP (fetch), Redis, auth middleware
- **Production safety:** hard guards prevent running in production
- **Zero runtime dependencies**
- **Pluggable logging:** bring your own logger (pino, winston, console)
- **Scenario builder:** define reproducible chaos scenarios
- **Admin REST API + CLI** for runtime fault injection

## Fault Types

| Type | What It Simulates | Key Fields |
|------|-------------------|------------|
| `latency` | Slow upstream (configurable delay) | `delayMs` |
| `error` | HTTP 500 / 502 / 503 from upstream | `statusCode`, `message?` |
| `timeout` | Upstream hangs indefinitely | `hangMs` |
| `malformed` | Corrupted JSON response body | `corruptResponse` |
| `connection-refused` | Service unreachable | -- |
| `connection-drop` | Connection starts then dies mid-response | `afterBytes?` |
| `rate-limit` | Upstream returns 429 with Retry-After | `retryAfterSeconds` |
| `schema-mismatch` | Valid JSON with missing fields | `missingFields` |

All fault types support an optional `probability` field (0–1) for probabilistic injection.

## Quick Start

See the [TypeScript README](typescript/README.md) for installation and usage.

## License

MIT
