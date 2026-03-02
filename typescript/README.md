# mcp-chaos-monkey (TypeScript)

Chaos/fault injection framework for MCP (Model Context Protocol) projects. Inject faults at the transport level so resilience wrappers (circuit breakers, retries, timeouts) exercise naturally.

## Installation

```bash
npm install mcp-chaos-monkey
```

## Quick Start

```typescript
import { ChaosController, configureChaosLogger } from 'mcp-chaos-monkey';
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

## Production Safety

The framework **refuses to run** in production:

- `NODE_ENV=production` → throws immediately
- `CHAOS_ENABLED` must be `"true"` → prevents accidental activation

## Fault Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `latency` | Adds delay before real call | `delayMs` |
| `error` | Returns fake error response | `statusCode`, `message?` |
| `timeout` | Hangs then throws AbortError | `hangMs` |
| `malformed` | Returns corrupted response body | `corruptResponse` |
| `connection-refused` | Throws TypeError (network error) | — |
| `connection-drop` | Starts real request, aborts mid-stream | `afterBytes?` |
| `rate-limit` | Returns 429 with Retry-After | `retryAfterSeconds` |
| `schema-mismatch` | Strips fields from real response | `missingFields` |

All fault types support an optional `probability` field (0–1) for probabilistic injection.

## API

### Core

- `ChaosController.getInstance()` — singleton controller
- `controller.inject(target, config, durationMs?)` — inject a fault, returns fault ID
- `controller.clear(faultId)` — remove a specific fault
- `controller.clearAll()` — remove all faults
- `controller.getFault(target)` — get active fault config (or null)
- `controller.getActiveFaults()` — snapshot of all active faults
- `assertChaosAllowed()` — throws if not safe to run

### Interceptors

- `createChaosAwareFetch(target, originalFetch?)` — wrap fetch
- `wrapRedisWithChaos(client, target?)` — wrap Redis commands, returns unwrap function
- `chaosAuthMiddleware` — Express middleware for auth faults
- `createChaosAuthMiddleware(target?)` — factory for configurable target

### Scenarios

- `defineScenario({ name, description, faults, expectedBehavior, assertions })` — build a typed scenario

### Admin & CLI

- `registerChaosEndpoint(app)` — register Express REST endpoints at `/chaos/*`
- `runCli(argv)` — programmatic CLI entry point
- `npx mcp-chaos inject <target> <type> [flags]` — CLI usage

### Logger

- `configureChaosLogger(factory)` — set global logger factory (pino-compatible)
- `createConsoleLogger(name)` — default console-based logger

## License

MIT
