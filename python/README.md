# mcp-chaos-monkey (Python)

Chaos/fault injection framework for [MCP (Model Context Protocol)](https://modelcontextprotocol.io) projects. Inject faults at the transport level so resilience wrappers (circuit breakers, retries, timeouts) exercise naturally.

**Zero runtime dependencies.** Optional deps for httpx, Redis, and Starlette interceptors.

## Installation

```bash
pip install mcp-chaos-monkey

# With optional interceptors
pip install mcp-chaos-monkey[httpx]       # HTTP interceptor
pip install mcp-chaos-monkey[redis]       # Redis interceptor
pip install mcp-chaos-monkey[starlette]   # Admin endpoints
pip install mcp-chaos-monkey[all]         # Everything
```

Requires Python >= 3.11.

## Quick Start

```python
import os
os.environ["CHAOS_ENABLED"] = "true"

from mcp_chaos_monkey import ChaosController, ErrorFault

# Inject a fault
controller = ChaosController.get_instance()
fault_id = controller.inject("weather-api", ErrorFault(status_code=503, message="Service unavailable"))

# Query the fault
fault = controller.get_fault("weather-api")
# → ErrorFault(status_code=503, message='Service unavailable')

# Clean up
controller.clear(fault_id)
```

### With MCP Python SDK

```python
import os
os.environ["CHAOS_ENABLED"] = "true"

import httpx
from mcp_chaos_monkey import ChaosController, ErrorFault, TimeoutFault
from mcp_chaos_monkey.interceptors import create_chaos_aware_client

# Create a chaos-aware httpx client for your MCP tool
client = create_chaos_aware_client("weather-api", httpx.AsyncClient())

# Inject a fault — all requests through this client now fail with 503
controller = ChaosController.get_instance()
controller.inject("weather-api", ErrorFault(status_code=503))

response = await client.get("https://api.weather.com/forecast")
# → Response [503]

# Inject a timeout — requests hang then raise ReadTimeout
controller.clear_all()
controller.inject("weather-api", TimeoutFault(hang_ms=10_000))

response = await client.get("https://api.weather.com/forecast")
# → raises httpx.ReadTimeout after 10s
```

## Architecture

Faults are injected **at the transport level**, sitting between your application code and the real service. This means resilience wrappers (circuit breakers, retries, timeouts) exercise naturally without mocking:

```
┌─────────────────────────────────────────────────────┐
│  Application Code                                   │
│  (MCP client, agent, tool handler)                  │
├─────────────────────────────────────────────────────┤
│  Resilience Layer                                   │
│  (circuit breaker, retry, timeout)                  │
├─────────────────────────────────────────────────────┤
│  ★ mcp-chaos-monkey ★                              │
│  (fault injection at transport level)               │
├─────────────────────────────────────────────────────┤
│  Transport                                          │
│  (httpx, redis-py, ASGI middleware)                 │
├─────────────────────────────────────────────────────┤
│  External Service                                   │
│  (API, database, auth provider)                     │
└─────────────────────────────────────────────────────┘
```

The key insight: faults are injected **below** the resilience layer so that circuit breakers, retries, and timeouts trigger organically — exactly as they would in a real outage.

## Production Safety

The framework **refuses to run** in production. Two hard guards must both pass:

1. `ENVIRONMENT` / `NODE_ENV` must **not** be `"production"` — throws immediately
2. `CHAOS_ENABLED` must be `"true"` — prevents accidental activation

```python
from mcp_chaos_monkey import assert_chaos_allowed
assert_chaos_allowed()  # raises ChaosNotAllowedError if unsafe
```

## Fault Types

| Type | What It Simulates | Dataclass | Key Fields |
|------|-------------------|-----------|------------|
| `latency` | Slow upstream | `LatencyFault` | `delay_ms` |
| `error` | HTTP 500/502/503 | `ErrorFault` | `status_code`, `message` |
| `timeout` | Upstream hangs | `TimeoutFault` | `hang_ms` |
| `malformed` | Corrupted JSON | `MalformedFault` | `corrupt_response` |
| `connection-refused` | Service unreachable | `ConnectionRefusedFault` | — |
| `connection-drop` | Mid-response failure | `ConnectionDropFault` | `after_bytes` |
| `rate-limit` | 429 Too Many Requests | `RateLimitFault` | `retry_after_seconds` |
| `schema-mismatch` | Missing JSON fields | `SchemaMismatchFault` | `missing_fields` |

All fault types support an optional `probability` field (0.0–1.0) for probabilistic injection.

## API Reference

### ChaosController

```python
from mcp_chaos_monkey import ChaosController, ErrorFault, LatencyFault

controller = ChaosController.get_instance()  # singleton

# Inject a fault — returns a unique fault ID
fault_id = controller.inject(
    "weather-api",
    LatencyFault(delay_ms=2000),
    duration_ms=30_000,  # optional: auto-expire after 30s
)

# Query faults
fault = controller.get_fault("weather-api")    # FaultConfig | None
active = controller.get_active_faults()         # list[ActiveFaultInfo]

# Clean up
controller.clear(fault_id)  # remove one
controller.clear_all()       # remove all

# Test isolation
ChaosController.reset()  # destroy singleton + clear all faults
```

### HTTP Interceptor (httpx)

Wraps an `httpx.AsyncClient` or `httpx.Client` with a chaos-aware transport:

```python
from mcp_chaos_monkey.interceptors import create_chaos_aware_client

# Wrap an existing async client
client = create_chaos_aware_client("weather-api", httpx.AsyncClient(base_url="..."))

# Or create a new one
client = create_chaos_aware_client("weather-api", base_url="https://api.weather.com")

# Sync variant
from mcp_chaos_monkey.interceptors.http_interceptor import create_chaos_aware_client_sync
sync_client = create_chaos_aware_client_sync("weather-api", httpx.Client())
```

### Redis Interceptor

Monkey-patches Redis client commands (`get`, `set`, `delete`, `hget`, `hset`, `expire`, `ttl`, `keys`, `mget`) to inject faults. Works with both sync `redis.Redis` and async `redis.asyncio.Redis`:

```python
import redis
from mcp_chaos_monkey import ChaosController, ErrorFault, LatencyFault, ConnectionRefusedFault
from mcp_chaos_monkey.interceptors import wrap_redis_with_chaos

# Your existing Redis client
redis_client = redis.Redis(host="localhost", port=6379)

# Wrap it with chaos — returns an unwrap function
unwrap = wrap_redis_with_chaos(redis_client, "redis")

# No fault active — commands work normally
redis_client.set("key", "value")
redis_client.get("key")  # → b"value"

# Inject a connection error — all Redis commands now raise ConnectionError
controller = ChaosController.get_instance()
controller.inject("redis", ErrorFault(status_code=500, message="connection lost"))

try:
    redis_client.get("key")
except ConnectionError as e:
    print(e)  # → "Chaos Redis error: connection lost"

# Simulate Redis being completely unreachable
controller.clear_all()
controller.inject("redis", ConnectionRefusedFault())

try:
    redis_client.set("key", "value")
except ConnectionError as e:
    print(e)  # → "Redis connection refused (chaos)"

# Add latency to simulate a slow Redis
controller.clear_all()
controller.inject("redis", LatencyFault(delay_ms=500))

redis_client.get("key")  # → takes 500ms, then returns b"value"

# Restore original Redis behavior
unwrap()
redis_client.get("key")  # → works instantly, no chaos
```

**Async Redis** works identically:

```python
import redis.asyncio as aioredis
from mcp_chaos_monkey.interceptors import wrap_redis_with_chaos

async_redis = aioredis.Redis(host="localhost", port=6379)
unwrap = wrap_redis_with_chaos(async_redis, "redis")

# Faults apply to async commands too
await async_redis.get("key")  # → chaos fault if active

unwrap()
```

### Auth Interceptor (ASGI Middleware)

ASGI middleware that intercepts authentication faults. Use it with Starlette, FastAPI, or any ASGI framework to simulate auth provider failures:

```python
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from mcp_chaos_monkey import ChaosController, ErrorFault, LatencyFault, TimeoutFault
from mcp_chaos_monkey.interceptors import ChaosAuthMiddleware, create_chaos_auth_middleware

# Your ASGI app
async def homepage(request):
    return JSONResponse({"status": "ok"})

app = Starlette(routes=[Route("/", homepage)])

# Add chaos auth middleware — targets "oauth-token" by default
app = ChaosAuthMiddleware(app, target="oauth-token")

# No fault active — requests pass through to your app
# GET / → 200, {"status": "ok"}

# Simulate auth provider returning 401
controller = ChaosController.get_instance()
controller.inject("oauth-token", ErrorFault(status_code=401, message="Token expired"))
# GET / → 401, {"error": "token_invalid", "message": "Token expired"}

# Simulate auth provider being slow (adds 2s delay before forwarding)
controller.clear_all()
controller.inject("oauth-token", LatencyFault(delay_ms=2000))
# GET / → 200 after 2s delay, {"status": "ok"}

# Simulate auth provider hanging (request never completes)
controller.clear_all()
controller.inject("oauth-token", TimeoutFault(hang_ms=30_000))
# GET / → hangs for 30s, client times out
```

**Custom auth target** — use the factory to target different auth mechanisms:

```python
# Protect API key validation
app = create_chaos_auth_middleware("api-key")(app)

# Now faults on "api-key" target affect this middleware
controller.inject("api-key", ErrorFault(status_code=403, message="Invalid API key"))
```

**Multiple auth targets with FastAPI:**

```python
from fastapi import FastAPI
from mcp_chaos_monkey.interceptors import ChaosAuthMiddleware

app = FastAPI()

# Stack middleware for different auth targets
app.add_middleware(ChaosAuthMiddleware, target="oauth-token")
app.add_middleware(ChaosAuthMiddleware, target="api-key")

@app.get("/")
async def root():
    return {"status": "ok"}
```

### Admin Endpoints

Framework-agnostic handler functions:

```python
from mcp_chaos_monkey import handle_status, handle_inject, handle_clear, handle_clear_all

# Use with any web framework
result = handle_status()             # {"faults": [...]}
result = handle_inject(body)         # {"fault_id": "..."}
result = handle_clear(body)          # {"cleared": "fault-id"}
result = handle_clear_all()          # {"cleared": "all"}
```

Optional Starlette integration:

```python
from mcp_chaos_monkey.admin_endpoint import create_starlette_routes
from starlette.applications import Starlette
from starlette.routing import Route

routes = create_starlette_routes()
app = Starlette(routes=routes)
```

This registers 4 routes:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/chaos/status` | List all active faults |
| `POST` | `/chaos/inject` | Inject a new fault |
| `POST` | `/chaos/clear` | Clear a specific fault |
| `POST` | `/chaos/clear-all` | Clear all faults |

### CLI Usage

```bash
# Set required env vars
export CHAOS_ENABLED=true

# Inject faults
mcp-chaos inject <target> <type> [--status N] [--delay N] [--duration N]
mcp-chaos clear <fault_id>
mcp-chaos clear-all
mcp-chaos status
```

**Examples:**

```bash
# Inject a 503 error on weather-api
mcp-chaos inject weather-api error --status 503

# Inject latency with auto-expiry after 30s
mcp-chaos inject redis latency --delay 2000 --duration 30

# Check what's active
mcp-chaos status

# Clean up
mcp-chaos clear-all
```

### Scenario Builder

Define reproducible chaos scenarios for structured testing:

```python
from mcp_chaos_monkey import define_scenario, ChaosScenario, ScenarioFault
from mcp_chaos_monkey import TimeoutFault, ErrorFault, ConnectionRefusedFault

api_timeout: ChaosScenario = define_scenario(
    name="weather-api-timeout",
    description="Weather API hangs for 10s — timeout fires, retries exhaust",
    faults=[
        ScenarioFault(target="weather-api", config=TimeoutFault(hang_ms=10_000)),
    ],
    expected_behavior="Each attempt times out at 5s. Retries fire and all fail.",
    assertions=[
        "Each retry attempt hits timeout at 5s",
        "Total latency bounded by retry * timeout",
    ],
)

# Cascading failure — multiple faults
cascading = define_scenario(
    name="cascading-redis-then-api",
    description="Redis drops, then weather API starts failing",
    faults=[
        ScenarioFault(target="redis", config=ConnectionRefusedFault()),
        ScenarioFault(target="weather-api", config=ErrorFault(status_code=503)),
    ],
    expected_behavior="System degrades to flight-only without cache.",
    assertions=["System remains responsive", "Flight queries still work end-to-end"],
)

# Temporary fault with auto-expiry
recovery = define_scenario(
    name="api-recovery",
    description="API fails then recovers — circuit should close",
    faults=[
        ScenarioFault(
            target="weather-api",
            config=ErrorFault(status_code=503),
            duration_ms=35_000,
        ),
    ],
    expected_behavior="Circuit opens, fault expires, circuit closes.",
    assertions=["Circuit transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED"],
)
```

### Pluggable Logger

By default, the library logs via stdlib `logging`. To use your own logger (e.g., structlog), call `configure_chaos_logger` once at startup:

```python
import structlog
from mcp_chaos_monkey import configure_chaos_logger

# structlog loggers satisfy ChaosLogger protocol directly
configure_chaos_logger(lambda name: structlog.get_logger(name))
```

The `ChaosLogger` protocol requires `debug`, `info`, `warning`, `error` methods matching Python's `logging.Logger`.

### Cross-Language Compatibility

The Python and TypeScript implementations share the same fault types, controller API, admin endpoints, CLI commands, and scenario interface. Fault configs can be exchanged as JSON between the two — `parse_fault_config()` accepts both camelCase (TypeScript) and snake_case (Python) keys:

```python
from mcp_chaos_monkey import parse_fault_config

# Both work:
fault = parse_fault_config({"type": "latency", "delayMs": 2000})     # camelCase
fault = parse_fault_config({"type": "latency", "delay_ms": 2000})    # snake_case
```

## Original Contribution

**mcp-chaos-monkey** is an original open-source contribution to the MCP ecosystem. No existing tool addressed systematic chaos testing for MCP-based systems, so this framework was created as a standalone, reusable package that any MCP project can adopt to validate its resilience stack under realistic failure conditions.

For a production-grade example of using mcp-chaos-monkey, see [reliable-mcp](https://github.com/alexey-tyurin/reliable-mcp) — an MCP Reliability Playbook that uses this framework for chaos testing with 21 automated fault injection scenarios.

## License

MIT
