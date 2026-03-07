import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ChaosController } from '../src/controller.js';

describe('ChaosController', () => {
  beforeEach(() => {
    process.env['CHAOS_ENABLED'] = 'true';
    process.env['NODE_ENV'] = 'test';
    ChaosController.reset();
  });

  afterEach(() => {
    ChaosController.reset();
  });

  it('returns a singleton instance', () => {
    const a = ChaosController.getInstance();
    const b = ChaosController.getInstance();
    expect(a).toBe(b);
  });

  describe('inject/clear lifecycle', () => {
    it('injects a fault and returns a fault id', () => {
      const controller = ChaosController.getInstance();
      const id = controller.inject('weather-api', { type: 'error', statusCode: 503 });

      expect(id).toBeTruthy();
      expect(typeof id).toBe('string');
    });

    it('getFault returns the injected fault config', () => {
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503 });

      const fault = controller.getFault('weather-api');
      expect(fault).not.toBeNull();
      expect(fault!.type).toBe('error');
    });

    it('getFault returns null for non-injected targets', () => {
      const controller = ChaosController.getInstance();
      const fault = controller.getFault('flight-api');
      expect(fault).toBeNull();
    });

    it('clear removes a specific fault', () => {
      const controller = ChaosController.getInstance();
      const id = controller.inject('weather-api', { type: 'error', statusCode: 503 });

      controller.clear(id);
      expect(controller.getFault('weather-api')).toBeNull();
    });

    it('clearAll removes all faults', () => {
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503 });
      controller.inject('flight-api', { type: 'timeout', hangMs: 5000 });

      controller.clearAll();
      expect(controller.getFault('weather-api')).toBeNull();
      expect(controller.getFault('flight-api')).toBeNull();
    });

    it('getActiveFaults returns a readonly snapshot', () => {
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503 });
      controller.inject('redis', { type: 'connection-refused' });

      const active = controller.getActiveFaults();
      expect(active).toHaveLength(2);
      expect(active[0]!.target).toBe('weather-api');
      expect(active[1]!.target).toBe('redis');
    });
  });

  describe('duration-based expiry', () => {
    it('expires faults after durationMs', () => {
      vi.useFakeTimers();
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503 }, 1000);

      expect(controller.getFault('weather-api')).not.toBeNull();

      vi.advanceTimersByTime(1100);
      expect(controller.getFault('weather-api')).toBeNull();

      vi.useRealTimers();
    });

    it('does not expire faults without duration', () => {
      vi.useFakeTimers();
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503 });

      vi.advanceTimersByTime(60000);
      expect(controller.getFault('weather-api')).not.toBeNull();

      vi.useRealTimers();
    });
  });

  describe('probabilistic skipping', () => {
    it('skips fault when probability check fails', () => {
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503, probability: 0 });

      // probability=0 means Math.random() always > 0, so always skipped
      const fault = controller.getFault('weather-api');
      expect(fault).toBeNull();
    });

    it('returns fault when probability is 1', () => {
      const controller = ChaosController.getInstance();
      controller.inject('weather-api', { type: 'error', statusCode: 503, probability: 1 });

      const fault = controller.getFault('weather-api');
      expect(fault).not.toBeNull();
    });
  });

  describe('probability validation', () => {
    it('rejects probability > 1 (Fix #10)', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('weather-api', { type: 'error', statusCode: 503, probability: 2.0 }),
      ).toThrow('probability must be between 0 and 1');
    });

    it('rejects probability < 0 (Fix #10)', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('weather-api', { type: 'error', statusCode: 503, probability: -0.5 }),
      ).toThrow('probability must be between 0 and 1');
    });

    it('accepts probability within [0, 1]', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('weather-api', { type: 'error', statusCode: 503, probability: 0.5 }),
      ).not.toThrow();
    });
  });

  describe('expired faults filtered from getActiveFaults (Fix #3)', () => {
    it('does not return expired faults in getActiveFaults', () => {
      vi.useFakeTimers();
      const controller = ChaosController.getInstance();
      controller.inject('active-target', { type: 'error', statusCode: 500 });
      controller.inject('expired-target', { type: 'latency', delayMs: 10 }, 100);

      vi.advanceTimersByTime(200);

      const faults = controller.getActiveFaults();
      const targets = faults.map(f => f.target);
      expect(targets).toContain('active-target');
      expect(targets).not.toContain('expired-target');

      vi.useRealTimers();
    });
  });

  describe('getFault cleans up expired faults for same target (Fix #9)', () => {
    it('cleans up expired faults when returning a match', () => {
      vi.useFakeTimers();
      const controller = ChaosController.getInstance();
      controller.inject('target', { type: 'latency', delayMs: 10 }, 100);
      controller.inject('target', { type: 'error', statusCode: 503 });

      vi.advanceTimersByTime(200);

      const fault = controller.getFault('target');
      expect(fault).not.toBeNull();
      expect(fault!.type).toBe('error');
      // The expired fault should have been cleaned up
      expect(controller.getActiveFaults()).toHaveLength(1);

      vi.useRealTimers();
    });
  });

  describe('durationMs validation', () => {
    it('rejects NaN durationMs', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('api', { type: 'error', statusCode: 503 }, NaN),
      ).toThrow('durationMs must be a non-negative finite number');
    });

    it('rejects negative durationMs', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('api', { type: 'error', statusCode: 503 }, -100),
      ).toThrow('durationMs must be a non-negative finite number');
    });

    it('rejects Infinity durationMs', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('api', { type: 'error', statusCode: 503 }, Infinity),
      ).toThrow('durationMs must be a non-negative finite number');
    });

    it('accepts zero durationMs', () => {
      const controller = ChaosController.getInstance();
      expect(() =>
        controller.inject('api', { type: 'error', statusCode: 503 }, 0),
      ).not.toThrow();
    });
  });

  describe('clear return value', () => {
    it('returns true when clearing an existing fault', () => {
      const controller = ChaosController.getInstance();
      const id = controller.inject('api', { type: 'error', statusCode: 503 });
      expect(controller.clear(id)).toBe(true);
    });

    it('returns false when clearing a non-existent fault', () => {
      const controller = ChaosController.getInstance();
      expect(controller.clear('non-existent-id')).toBe(false);
    });
  });

  describe('reset for isolation', () => {
    it('clears the singleton instance', () => {
      const a = ChaosController.getInstance();
      a.inject('weather-api', { type: 'error', statusCode: 503 });

      ChaosController.reset();

      const b = ChaosController.getInstance();
      expect(b).not.toBe(a);
      expect(b.getActiveFaults()).toHaveLength(0);
    });
  });

  describe('max faults limit (MEM-1)', () => {
    it('throws when exceeding MAX_FAULTS', () => {
      const controller = ChaosController.getInstance();
      for (let i = 0; i < 1000; i++) {
        controller.inject(`target-${String(i)}`, { type: 'error', statusCode: 500 });
      }
      expect(() =>
        controller.inject('one-too-many', { type: 'error', statusCode: 500 }),
      ).toThrow('Maximum number of active faults');
    });
  });

  describe('getActiveFaults does not mutate during iteration (BUG-1)', () => {
    it('safely handles expired faults without map mutation errors', () => {
      vi.useFakeTimers();
      const controller = ChaosController.getInstance();
      // Inject several faults with short durations interleaved with permanent ones
      controller.inject('a', { type: 'error', statusCode: 500 }, 100);
      controller.inject('b', { type: 'error', statusCode: 500 });
      controller.inject('c', { type: 'error', statusCode: 500 }, 100);
      controller.inject('d', { type: 'error', statusCode: 500 });

      vi.advanceTimersByTime(200);

      // Should not throw and should only return non-expired faults
      const faults = controller.getActiveFaults();
      const targets = faults.map(f => f.target);
      expect(targets).toContain('b');
      expect(targets).toContain('d');
      expect(targets).not.toContain('a');
      expect(targets).not.toContain('c');
      expect(faults).toHaveLength(2);

      vi.useRealTimers();
    });
  });
});
