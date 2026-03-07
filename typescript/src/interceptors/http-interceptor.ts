import { ChaosController } from '../controller.js';
import type { FaultTarget, FaultConfig } from '../fault-types.js';
import { getLogger } from '../logger.js';

const logger = getLogger('chaos-http');

export function createChaosAwareFetch(
  target: FaultTarget,
  originalFetch: typeof globalThis.fetch = globalThis.fetch,
): typeof globalThis.fetch {
  return async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const controller = ChaosController.getInstance();
    const fault = controller.getFault(target);

    if (!fault) {
      return originalFetch(input, init);
    }

    logger.debug({ target, faultType: fault.type }, 'Chaos fault triggered');

    return applyFault(fault, input, init, originalFetch);
  };
}

async function applyFault(
  fault: FaultConfig,
  input: string | URL | Request,
  init: RequestInit | undefined,
  originalFetch: typeof globalThis.fetch,
): Promise<Response> {
  switch (fault.type) {
    case 'latency': {
      await delay(fault.delayMs);
      return originalFetch(input, init);
    }
    case 'error': {
      return new Response(
        JSON.stringify({ error: fault.message ?? 'Chaos injected error' }),
        { status: fault.statusCode, headers: { 'Content-Type': 'application/json' } },
      );
    }
    case 'timeout': {
      await delay(fault.hangMs);
      throw new DOMException('The operation was aborted', 'AbortError');
    }
    case 'connection-refused': {
      throw new TypeError('fetch failed (chaos: connection refused)');
    }
    case 'rate-limit': {
      return new Response(
        JSON.stringify({ error: 'Too Many Requests' }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(fault.retryAfterSeconds),
          },
        },
      );
    }
    case 'malformed': {
      return new Response(
        '<<<CORRUPTED_RESPONSE>>>{{{{not json',
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    case 'schema-mismatch': {
      const realResponse = await originalFetch(input, init);
      let body: Record<string, unknown>;
      try {
        body = await realResponse.clone().json() as Record<string, unknown>;
      } catch {
        logger.warn({ target: input }, 'schema-mismatch: upstream response is not valid JSON, returning as-is');
        return realResponse;
      }
      for (const field of fault.missingFields) {
        Reflect.deleteProperty(body, field);
      }
      const headers = new Headers(realResponse.headers);
      headers.delete('content-length');
      return new Response(JSON.stringify(body), {
        status: realResponse.status,
        headers,
      });
    }
    case 'connection-drop': {
      const chaosAbort = new AbortController();
      const existingSignal = init?.signal;
      const combinedSignal = existingSignal
        ? AbortSignal.any([chaosAbort.signal, existingSignal])
        : chaosAbort.signal;
      const mergedInit = { ...init, signal: combinedSignal };
      const fetchPromise = originalFetch(input, mergedInit);
      const abortDelayMs = fault.afterBytes ?? 0;
      setTimeout(() => { chaosAbort.abort(); }, abortDelayMs);
      return fetchPromise;
    }
    default: {
      const _exhaustive: never = fault;
      throw new Error(`Unhandled fault type: ${(_exhaustive as FaultConfig).type}`);
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
