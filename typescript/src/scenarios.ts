import type { FaultTarget, FaultConfig } from './fault-types.js';

export interface ChaosScenario {
  name: string;
  description: string;
  faults: readonly { target: FaultTarget; config: FaultConfig; durationMs?: number }[];
  expectedBehavior: string;
  assertions: readonly string[];
}

interface ScenarioBuilder {
  name: string;
  description: string;
  faults: { target: FaultTarget; config: FaultConfig; durationMs?: number }[];
  expectedBehavior: string;
  assertions: string[];
}

/** Build a ChaosScenario with a fluent-ish config object. */
export function defineScenario(builder: ScenarioBuilder): ChaosScenario {
  if (!builder.name) {
    throw new Error('Scenario name is required');
  }
  if (builder.faults.length === 0) {
    throw new Error('Scenario must have at least one fault');
  }
  return {
    name: builder.name,
    description: builder.description,
    faults: builder.faults,
    expectedBehavior: builder.expectedBehavior,
    assertions: builder.assertions,
  };
}
