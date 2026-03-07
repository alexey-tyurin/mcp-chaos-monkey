import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ChaosController } from '../src/controller.js';
import { registerChaosEndpoint } from '../src/admin-endpoint.js';

function createMockApp() {
  const routes = new Map<string, (...args: unknown[]) => void>();

  return {
    get: vi.fn((path: string, handler: (...args: unknown[]) => void) => {
      routes.set(`GET ${path}`, handler);
    }),
    post: vi.fn((path: string, handler: (...args: unknown[]) => void) => {
      routes.set(`POST ${path}`, handler);
    }),
    routes,
    invoke(method: string, path: string, body?: unknown, headers?: Record<string, string>) {
      const handler = routes.get(`${method} ${path}`);
      if (!handler) throw new Error(`No route: ${method} ${path}`);

      const req = { body, headers: headers ?? {} } as unknown;
      const res = {
        json: vi.fn().mockReturnThis(),
        status: vi.fn().mockReturnThis(),
      };
      handler(req, res);
      return res;
    },
  };
}

describe('registerChaosEndpoint', () => {
  beforeEach(() => {
    process.env['CHAOS_ENABLED'] = 'true';
    process.env['NODE_ENV'] = 'test';
    delete process.env['CHAOS_ADMIN_TOKEN'];
    ChaosController.reset();
  });

  afterEach(() => {
    delete process.env['CHAOS_ADMIN_TOKEN'];
    ChaosController.reset();
  });

  it('registers all 4 routes', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    expect(app.get).toHaveBeenCalledWith('/chaos/status', expect.any(Function));
    expect(app.post).toHaveBeenCalledWith('/chaos/inject', expect.any(Function));
    expect(app.post).toHaveBeenCalledWith('/chaos/clear', expect.any(Function));
    expect(app.post).toHaveBeenCalledWith('/chaos/clear-all', expect.any(Function));
  });

  it('GET /chaos/status returns empty faults initially', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('GET', '/chaos/status');
    expect(res.json).toHaveBeenCalledWith({ faults: [] });
  });

  it('POST /chaos/inject injects a fault', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      target: 'weather-api',
      config: { type: 'error', statusCode: 503 },
    });

    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ faultId: expect.any(String) }),
    );
  });

  it('POST /chaos/clear clears a specific fault', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const controller = ChaosController.getInstance();
    const faultId = controller.inject('weather-api', { type: 'error', statusCode: 503 });

    const res = app.invoke('POST', '/chaos/clear', { faultId });
    expect(res.json).toHaveBeenCalledWith({ cleared: faultId });
  });

  it('POST /chaos/clear-all clears all faults', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const controller = ChaosController.getInstance();
    controller.inject('weather-api', { type: 'error', statusCode: 503 });

    const res = app.invoke('POST', '/chaos/clear-all');
    expect(res.json).toHaveBeenCalledWith({ cleared: 'all' });
    expect(controller.getActiveFaults()).toHaveLength(0);
  });

  it('rejects inject with missing target (Fix #5)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      config: { type: 'error', statusCode: 503 },
    });
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('target') }),
    );
  });

  it('rejects inject with invalid config.type (Fix #5)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      target: 'api',
      config: { type: 'bogus' },
    });
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('config.type') }),
    );
  });

  it('rejects clear with missing faultId (Fix #5)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/clear', {});
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('faultId') }),
    );
  });

  it('blocks requests when CHAOS_ADMIN_TOKEN is set and no auth provided (Fix #4)', () => {
    process.env['CHAOS_ADMIN_TOKEN'] = 'secret123';
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('GET', '/chaos/status');
    expect(res.status).toHaveBeenCalledWith(403);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('CHAOS_ADMIN_TOKEN') }),
    );
  });

  it('allows requests with correct CHAOS_ADMIN_TOKEN (Fix #4)', () => {
    process.env['CHAOS_ADMIN_TOKEN'] = 'secret123';
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('GET', '/chaos/status', undefined, {
      authorization: 'Bearer secret123',
    });
    expect(res.json).toHaveBeenCalledWith({ faults: [] });
  });

  it('uses prefix-based Bearer stripping (Fix #6)', () => {
    process.env['CHAOS_ADMIN_TOKEN'] = 'Bearer extra';
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    // Token itself contains "Bearer " — only the prefix should be stripped
    const res = app.invoke('GET', '/chaos/status', undefined, {
      authorization: 'Bearer Bearer extra',
    });
    expect(res.json).toHaveBeenCalledWith({ faults: [] });
  });

  it('rejects inject with missing required numeric field (Fix #7)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      target: 'api',
      config: { type: 'latency' },  // missing delayMs
    });
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('delayMs') }),
    );
  });

  it('rejects inject with non-numeric required field (Fix #7)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      target: 'api',
      config: { type: 'error', statusCode: 'not-a-number' },
    });
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: expect.stringContaining('statusCode') }),
    );
  });

  it('accepts valid config with all required fields (Fix #7)', () => {
    const app = createMockApp();
    registerChaosEndpoint(app as never);

    const res = app.invoke('POST', '/chaos/inject', {
      target: 'api',
      config: { type: 'latency', delayMs: 500 },
    });
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ faultId: expect.any(String) }),
    );
  });
});
