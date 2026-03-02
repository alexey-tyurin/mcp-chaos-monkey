# mcp-chaos-monkey (TypeScript)

Chaos/fault injection framework for [MCP (Model Context Protocol)](https://modelcontextprotocol.io) projects. Inject faults at the transport level so resilience wrappers (circuit breakers, retries, timeouts) exercise naturally.

**Zero runtime dependencies.** Optional peer deps for Express and Redis interceptors.

## Installation

```bash
npm install mcp-chaos-monkey
```

## Quick Start

```typescript
import { ChaosController } from 'mcp-chaos-monkey';
import { createChaosAwareFetch } from 'mcp-chaos-monkey/interceptors/http';

// Inject a fault
const controller = ChaosController.getInstance();
const faultId = controller.inject('weather-api', {
  type: 'error',
  statusCode: 503,
  message: 'Service unavailable',
});

// Wrap fetch — faults are applied automatically
const fetch = createChaosAwareFetch('weather-api');
const response = await fetch('https://api.weather.com/forecast');
// → Response { status: 503 }

// Clean up
controller.clear(faultId);
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
│  (fetch, Redis, auth middleware)                    │
├─────────────────────────────────────────────────────┤
│  External Service                                   │
│  (API, database, auth provider)                     │
└─────────────────────────────────────────────────────┘
```

The key insight: faults are injected **below** the resilience layer so that circuit breakers, retries, and timeouts trigger organically — exactly as they would in a real outage.

## Production Safety

The framework **refuses to run** in production. Two hard guards must both pass:

1. `NODE_ENV` must **not** be `"production"` — throws immediately
2. `CHAOS_ENABLED` must be `"true"` — prevents accidental activation

```typescript
// These checks happen automatically when ChaosController is created.
// You can also call them explicitly:
import { assertChaosAllowed } from 'mcp-chaos-monkey';
assertChaosAllowed(); // throws if unsafe
```

## Fault Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `latency` | Adds delay before real call | `delayMs` |
| `error` | Returns fake error response | `statusCode`, `message?` |
| `timeout` | Hangs then throws AbortError | `hangMs` |
| `malformed` | Returns corrupted response body | `corruptResponse` |
| `connection-refused` | Throws TypeError (network error) | -- |
| `connection-drop` | Starts real request, aborts mid-stream | `afterBytes?` |
| `rate-limit` | Returns 429 with Retry-After | `retryAfterSeconds` |
| `schema-mismatch` | Strips fields from real response | `missingFields` |

All fault types support an optional `probability` field (0--1) for probabilistic injection.

## API Reference

### ChaosController

```typescript
import { ChaosController } from 'mcp-chaos-monkey';

const controller = ChaosController.getInstance(); // singleton

// Inject a fault — returns a unique fault ID
const faultId = controller.inject('weather-api', {
  type: 'latency',
  delayMs: 2000,
}, 30_000); // optional: auto-expire after 30s

// Query faults
const fault = controller.getFault('weather-api');   // FaultConfig | null
const all = controller.getActiveFaults();            // readonly snapshot

// Clean up
controller.clear(faultId);  // remove one
controller.clearAll();       // remove all

// Test isolation
ChaosController.reset(); // destroy singleton + clear all faults
```

### HTTP Interceptor

Wraps `fetch` to apply faults for a given target:

```typescript
import { createChaosAwareFetch } from 'mcp-chaos-monkey/interceptors/http';

// Wrap globalThis.fetch (default)
const fetch = createChaosAwareFetch('weather-api');

// Or wrap a custom fetch
const fetch = createChaosAwareFetch('weather-api', myCustomFetch);
```

### Redis Interceptor

Wraps Redis commands (`get`, `set`, `del`, `hget`, `hset`, `expire`, `ttl`, `keys`, `mget`):

```typescript
import { wrapRedisWithChaos } from 'mcp-chaos-monkey/interceptors/redis';

const unwrap = wrapRedisWithChaos(redisClient, 'redis');

// Later: restore original methods
unwrap();
```

### Auth Interceptor

Express middleware that intercepts auth-related faults:

```typescript
import { chaosAuthMiddleware, createChaosAuthMiddleware } from 'mcp-chaos-monkey/interceptors/auth';

// Fixed target: 'oauth-token'
app.use(chaosAuthMiddleware);

// Configurable target
app.use(createChaosAuthMiddleware('api-key'));
```

### Custom Targets with TypeScript Type Safety

`FaultTarget` is an open `string` type, so you can inject faults for any target. For project-specific type safety, define your own union:

```typescript
import type { FaultTarget } from 'mcp-chaos-monkey';
import { ChaosController } from 'mcp-chaos-monkey';

// Your project's targets
type MyTarget = 'weather-api' | 'flight-api' | 'redis' | 'oauth-token';

function injectTypedFault(target: MyTarget, ...args: Parameters<ChaosController['inject']> extends [any, ...infer R] ? R : never) {
  return ChaosController.getInstance().inject(target, ...args);
}

// Type-safe: only your targets accepted
injectTypedFault('weather-api', { type: 'error', statusCode: 503 });
// injectTypedFault('typo-api', ...); // TypeScript error
```

You can also create a stricter type guard:

```typescript
const MY_TARGETS = ['weather-api', 'flight-api', 'redis', 'oauth-token'] as const;
type MyTarget = typeof MY_TARGETS[number];

function isMyTarget(value: unknown): value is MyTarget {
  return typeof value === 'string' && (MY_TARGETS as readonly string[]).includes(value);
}
```

### Express Admin Endpoints

Register REST endpoints for runtime fault management:

```typescript
import { registerChaosEndpoint } from 'mcp-chaos-monkey/admin';

registerChaosEndpoint(app);
```

This registers 4 routes:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/chaos/status` | List all active faults |
| `POST` | `/chaos/inject` | Inject a new fault |
| `POST` | `/chaos/clear` | Clear a specific fault |
| `POST` | `/chaos/clear-all` | Clear all faults |

**Example requests:**

```bash
# Check status
curl http://localhost:3000/chaos/status

# Inject a fault
curl -X POST http://localhost:3000/chaos/inject \
  -H 'Content-Type: application/json' \
  -d '{"target":"weather-api","config":{"type":"error","statusCode":503}}'

# Clear a fault
curl -X POST http://localhost:3000/chaos/clear \
  -H 'Content-Type: application/json' \
  -d '{"faultId":"weather-api-1234-abc"}'

# Clear all
curl -X POST http://localhost:3000/chaos/clear-all
```

### CLI Usage

The package ships a CLI tool for managing faults from the terminal:

```bash
# Install globally or use npx
npx mcp-chaos inject <target> <type> [--status N] [--delay N] [--duration N]
npx mcp-chaos clear <faultId>
npx mcp-chaos clear-all
npx mcp-chaos status
```

**Examples:**

```bash
# Inject a 503 error on weather-api
npx mcp-chaos inject weather-api error --status 503

# Inject latency with auto-expiry after 30s
npx mcp-chaos inject redis latency --delay 2000 --duration 30

# Check what's active
npx mcp-chaos status

# Clean up
npx mcp-chaos clear-all
```

**Note:** `CHAOS_ENABLED=true` and `NODE_ENV!=production` must be set in the environment.

### Scenario Builder

Define reproducible chaos scenarios for structured testing:

```typescript
import { defineScenario } from 'mcp-chaos-monkey';
import type { ChaosScenario } from 'mcp-chaos-monkey';

const apiTimeout: ChaosScenario = defineScenario({
  name: 'weather-api-timeout',
  description: 'Weather API hangs for 10s — timeout fires, retries exhaust',
  faults: [
    { target: 'weather-api', config: { type: 'timeout', hangMs: 10_000 } },
  ],
  expectedBehavior: 'Each attempt times out at 5s. Retries fire and all fail.',
  assertions: [
    'Each retry attempt hits timeout at 5s',
    'Total latency bounded by retry * timeout',
    'Partial response includes flight data',
  ],
});

// Cascading failure — multiple faults
const cascading: ChaosScenario = defineScenario({
  name: 'cascading-redis-then-api',
  description: 'Redis drops, then weather API starts failing',
  faults: [
    { target: 'redis', config: { type: 'connection-refused' } },
    { target: 'weather-api', config: { type: 'error', statusCode: 503 } },
  ],
  expectedBehavior: 'System degrades to flight-only without cache.',
  assertions: [
    'System remains responsive',
    'Flight queries still work end-to-end',
  ],
});

// Temporary fault with auto-expiry
const recovery: ChaosScenario = defineScenario({
  name: 'api-recovery',
  description: 'API fails then recovers — circuit should close',
  faults: [
    { target: 'weather-api', config: { type: 'error', statusCode: 503 }, durationMs: 35_000 },
  ],
  expectedBehavior: 'Circuit opens, fault expires, circuit closes.',
  assertions: ['Circuit transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED'],
});
```

### Pluggable Logger

By default, the library logs to `console.*`. To use your own logger (e.g., pino), call `configureChaosLogger` once at startup:

```typescript
import { configureChaosLogger } from 'mcp-chaos-monkey';
import pino from 'pino';

// Pino's Logger satisfies ChaosLogger directly — no adapter needed
configureChaosLogger((name) => pino({ name }));
```

The `ChaosLogger` interface requires `debug`, `info`, `warn`, `error` methods with pino-compatible signatures.

## License

MIT
