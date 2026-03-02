import { describe, it, expect } from 'vitest';
import { defineScenario } from '../src/scenarios.js';
import type { ChaosScenario } from '../src/scenarios.js';

describe('defineScenario', () => {
  it('creates a valid scenario from builder config', () => {
    const scenario: ChaosScenario = defineScenario({
      name: 'api-timeout',
      description: 'API hangs for 10s',
      faults: [{ target: 'weather-api', config: { type: 'timeout', hangMs: 10_000 } }],
      expectedBehavior: 'Circuit opens after retries exhaust',
      assertions: ['Circuit transitions to OPEN'],
    });

    expect(scenario.name).toBe('api-timeout');
    expect(scenario.faults).toHaveLength(1);
    expect(scenario.faults[0]!.config.type).toBe('timeout');
    expect(scenario.assertions).toHaveLength(1);
  });

  it('supports multiple faults in a scenario', () => {
    const scenario = defineScenario({
      name: 'cascading-failure',
      description: 'Redis and API both fail',
      faults: [
        { target: 'redis', config: { type: 'connection-refused' } },
        { target: 'weather-api', config: { type: 'error', statusCode: 503 } },
      ],
      expectedBehavior: 'System degrades gracefully',
      assertions: ['System still responds', 'Flight data still works'],
    });

    expect(scenario.faults).toHaveLength(2);
    expect(scenario.assertions).toHaveLength(2);
  });

  it('supports optional durationMs on faults', () => {
    const scenario = defineScenario({
      name: 'temporary-error',
      description: 'Temporary API error that self-heals',
      faults: [
        { target: 'weather-api', config: { type: 'error', statusCode: 503 }, durationMs: 35_000 },
      ],
      expectedBehavior: 'Circuit opens then closes after fault expires',
      assertions: ['Recovery is automatic'],
    });

    expect(scenario.faults[0]!.durationMs).toBe(35_000);
  });

  it('throws when name is empty', () => {
    expect(() =>
      defineScenario({
        name: '',
        description: 'test',
        faults: [{ target: 'api', config: { type: 'connection-refused' } }],
        expectedBehavior: 'test',
        assertions: [],
      }),
    ).toThrow('Scenario name is required');
  });

  it('throws when faults array is empty', () => {
    expect(() =>
      defineScenario({
        name: 'no-faults',
        description: 'test',
        faults: [],
        expectedBehavior: 'test',
        assertions: [],
      }),
    ).toThrow('Scenario must have at least one fault');
  });
});
