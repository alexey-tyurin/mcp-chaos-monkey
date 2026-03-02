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
    invoke(method: string, path: string, body?: unknown) {
      const handler = routes.get(`${method} ${path}`);
      if (!handler) throw new Error(`No route: ${method} ${path}`);

      const req = { body } as unknown;
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
    ChaosController.reset();
  });

  afterEach(() => {
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
});
