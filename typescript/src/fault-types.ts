/** What can be disrupted — open string type for any target. */
export type FaultTarget = string;

/** Validates that a value is a non-empty string suitable as a fault target. */
export function isFaultTarget(value: unknown): value is FaultTarget {
  return typeof value === 'string' && value.length > 0;
}

/** Types of faults that can be injected. */
export type FaultConfig =
  | { type: 'latency'; delayMs: number; probability?: number }
  | { type: 'error'; statusCode: number; message?: string; probability?: number }
  | { type: 'timeout'; hangMs: number; probability?: number }
  | { type: 'malformed'; corruptResponse: boolean; probability?: number }
  | { type: 'connection-refused'; probability?: number }
  | { type: 'connection-drop'; afterBytes?: number; probability?: number }
  | { type: 'rate-limit'; retryAfterSeconds: number; probability?: number }
  | { type: 'schema-mismatch'; missingFields: string[]; probability?: number };
