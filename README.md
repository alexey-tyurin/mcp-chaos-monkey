# mcp-chaos-monkey

Chaos/fault injection framework for [MCP (Model Context Protocol)](https://modelcontextprotocol.io) projects.

Inject faults at the transport level so resilience wrappers (circuit breakers, retries, timeouts) exercise naturally — without changing application code.

## Packages

| Package | Language | Status |
|---------|----------|--------|
| [`typescript/`](typescript/) | Node.js / TypeScript | Active |
| [`python/`](python/) | Python | Planned |

## Features

- **8 fault types:** latency, error, timeout, malformed, connection-refused, connection-drop, rate-limit, schema-mismatch
- **Transport-level interception:** HTTP (fetch), Redis, auth middleware
- **Production safety:** hard guards prevent running in production
- **Zero runtime dependencies**
- **Pluggable logging:** bring your own logger (pino, winston, console)
- **Scenario builder:** define reproducible chaos scenarios
- **Admin REST API + CLI** for runtime fault injection

## Quick Start

See the [TypeScript README](typescript/README.md) for installation and usage.

## License

MIT
