import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ChaosController } from '../src/controller.js';
import { createChaosAwareFetch } from '../src/interceptors/http-interceptor.js';

describe('createChaosAwareFetch', () => {
  let controller: ChaosController;

  beforeEach(() => {
    process.env['CHAOS_ENABLED'] = 'true';
    process.env['NODE_ENV'] = 'test';
    ChaosController.reset();
    controller = ChaosController.getInstance();
  });

  afterEach(() => {
    ChaosController.reset();
  });

  it('calls original fetch when no fault is active', async () => {
    const mockFetch = vi.fn(async () => new Response('ok', { status: 200 }));
    const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

    const response = await chaosAwareFetch('http://example.com');
    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledOnce();
  });

  describe('latency fault', () => {
    it('delays then calls real fetch', async () => {
      vi.useFakeTimers();
      const mockFetch = vi.fn(async () => new Response('ok', { status: 200 }));
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'latency', delayMs: 500 });

      const promise = chaosAwareFetch('http://example.com');
      await vi.advanceTimersByTimeAsync(600);
      const response = await promise;

      expect(response.status).toBe(200);
      expect(mockFetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });
  });

  describe('error fault', () => {
    it('returns a fake response with the status code', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'error', statusCode: 503, message: 'Service down' });

      const response = await chaosAwareFetch('http://example.com');
      expect(response.status).toBe(503);

      const body = await response.json() as { error: string };
      expect(body.error).toBe('Service down');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('uses default message when none provided', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'error', statusCode: 500 });

      const response = await chaosAwareFetch('http://example.com');
      const body = await response.json() as { error: string };
      expect(body.error).toBe('Chaos injected error');
    });
  });

  describe('timeout fault', () => {
    it('hangs then throws AbortError', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'timeout', hangMs: 10 });

      await expect(chaosAwareFetch('http://example.com')).rejects.toThrow(
        'The operation was aborted',
      );
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('connection-refused fault', () => {
    it('throws TypeError', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'connection-refused' });

      await expect(chaosAwareFetch('http://example.com')).rejects.toThrow(TypeError);
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('rate-limit fault', () => {
    it('returns 429 with Retry-After header', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('flight-api', mockFetch);

      controller.inject('flight-api', { type: 'rate-limit', retryAfterSeconds: 60 });

      const response = await chaosAwareFetch('http://example.com');
      expect(response.status).toBe(429);
      expect(response.headers.get('Retry-After')).toBe('60');
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('malformed fault', () => {
    it('returns corrupted non-JSON body with 200 status', async () => {
      const mockFetch = vi.fn();
      const chaosAwareFetch = createChaosAwareFetch('weather-mcp', mockFetch);

      controller.inject('weather-mcp', { type: 'malformed', corruptResponse: true });

      const response = await chaosAwareFetch('http://example.com');
      expect(response.status).toBe(200);

      const text = await response.text();
      expect(text).toContain('CORRUPTED');
      expect(() => JSON.parse(text)).toThrow();
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('schema-mismatch fault', () => {
    it('calls real fetch then strips fields', async () => {
      const original = { city: 'NYC', temperature: 72, humidity: 45 };
      const mockFetch = vi.fn(async () =>
        new Response(JSON.stringify(original), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', {
        type: 'schema-mismatch',
        missingFields: ['temperature', 'humidity'],
      });

      const response = await chaosAwareFetch('http://example.com');
      const body = await response.json() as Record<string, unknown>;

      expect(body['city']).toBe('NYC');
      expect(body['temperature']).toBeUndefined();
      expect(body['humidity']).toBeUndefined();
      expect(mockFetch).toHaveBeenCalledOnce();
    });

    it('returns original response when upstream is not JSON (Fix #1)', async () => {
      const mockFetch = vi.fn(async () =>
        new Response('<html>Error</html>', {
          status: 500,
          headers: { 'Content-Type': 'text/html' },
        }),
      );
      const chaosAwareFetch = createChaosAwareFetch('html-api', mockFetch);

      controller.inject('html-api', {
        type: 'schema-mismatch',
        missingFields: ['foo'],
      });

      const response = await chaosAwareFetch('http://example.com');
      expect(response.status).toBe(500);
      const text = await response.text();
      expect(text).toContain('<html>');
    });

    it('returns original response when upstream JSON is an array (Fix #12)', async () => {
      const arr = [{ id: 1 }, { id: 2 }];
      const mockFetch = vi.fn(async () =>
        new Response(JSON.stringify(arr), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
      const chaosAwareFetch = createChaosAwareFetch('array-api', mockFetch);

      controller.inject('array-api', {
        type: 'schema-mismatch',
        missingFields: ['id'],
      });

      const response = await chaosAwareFetch('http://example.com');
      expect(response.status).toBe(200);
      const body = await response.json() as unknown;
      // Should return original array as-is since it's not an object
      expect(Array.isArray(body)).toBe(true);
      expect((body as { id: number }[])[0]!.id).toBe(1);
    });

    it('does not pass through stale Content-Length after field removal (Fix #2)', async () => {
      const original = { city: 'NYC', temperature: 72, humidity: 45 };
      const originalBody = JSON.stringify(original);
      const mockFetch = vi.fn(async () =>
        new Response(originalBody, {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': String(originalBody.length),
          },
        }),
      );
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', {
        type: 'schema-mismatch',
        missingFields: ['temperature', 'humidity'],
      });

      const response = await chaosAwareFetch('http://example.com');
      // Content-Length should not be the old value
      expect(response.headers.get('content-length')).toBeNull();
    });
  });

  describe('connection-drop fault', () => {
    it('aborts immediately when afterMs is not set (defaults to 0)', async () => {
      const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((resolve, reject) => {
          const signal = init?.signal;
          if (signal?.aborted) {
            reject(new DOMException('The operation was aborted', 'AbortError'));
            return;
          }
          signal?.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted', 'AbortError'));
          });
        });
      });
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'connection-drop' });

      await expect(chaosAwareFetch('http://example.com')).rejects.toThrow('aborted');
      expect(mockFetch).toHaveBeenCalledOnce();
    });

    it('uses afterMs as abort delay in ms', async () => {
      vi.useFakeTimers();
      let aborted = false;
      const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((resolve, reject) => {
          const signal = init?.signal;
          if (signal?.aborted) {
            aborted = true;
            reject(new DOMException('The operation was aborted', 'AbortError'));
            return;
          }
          signal?.addEventListener('abort', () => {
            aborted = true;
            reject(new DOMException('The operation was aborted', 'AbortError'));
          });
        });
      });
      const chaosAwareFetch = createChaosAwareFetch('weather-api', mockFetch);

      controller.inject('weather-api', { type: 'connection-drop', afterMs: 200 });

      const promise = chaosAwareFetch('http://example.com').catch((e: unknown) => e);

      // Should not have aborted yet at 100ms
      await vi.advanceTimersByTimeAsync(100);
      expect(aborted).toBe(false);

      // Should abort at 200ms
      await vi.advanceTimersByTimeAsync(150);
      const result = await promise;
      expect(result).toBeInstanceOf(DOMException);
      expect((result as DOMException).name).toBe('AbortError');

      vi.useRealTimers();
    });
  });

  describe('schema-mismatch with Request object input (Fix #6)', () => {
    it('handles Request input with sensitive headers without leaking them', async () => {
      const mockFetch = vi.fn(async () =>
        new Response('not json', { status: 200 }),
      );
      const chaosAwareFetch = createChaosAwareFetch('secret-api', mockFetch);

      controller.inject('secret-api', {
        type: 'schema-mismatch',
        missingFields: ['field'],
      });

      const request = new Request('http://example.com/api', {
        headers: { Authorization: 'Bearer super-secret-token' },
      });

      // Spy on console.warn to capture the logger output
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const response = await chaosAwareFetch(request);
      // Should return the original response when JSON parsing fails
      expect(response.status).toBe(200);

      // Verify the console.warn was called and does NOT contain the auth token
      if (warnSpy.mock.calls.length > 0) {
        const logOutput = JSON.stringify(warnSpy.mock.calls);
        expect(logOutput).not.toContain('super-secret-token');
        // Should contain the URL string
        expect(logOutput).toContain('http://example.com/api');
      }

      warnSpy.mockRestore();
    });
  });
});
