import { assertChaosAllowed } from './guard.js';
import type { FaultConfig, FaultTarget } from './fault-types.js';
import { getLogger } from './logger.js';

interface ActiveFault {
  target: FaultTarget;
  config: FaultConfig;
  activatedAt: number;
  expiresAt: number | null;
  requestCount: number;
}

const logger = getLogger('chaos-controller');

const MAX_FAULTS = 1000;

export class ChaosController {
  private faults = new Map<string, ActiveFault>();
  private static instance: ChaosController | null = null;

  constructor() {
    assertChaosAllowed();
  }

  static getInstance(): ChaosController {
    if (!ChaosController.instance) {
      ChaosController.instance = new ChaosController();
    }
    return ChaosController.instance;
  }

  inject(target: FaultTarget, config: FaultConfig, durationMs?: number): string {
    if (config.probability !== undefined && (config.probability < 0 || config.probability > 1)) {
      throw new Error(`probability must be between 0 and 1, got ${String(config.probability)}`);
    }
    if (durationMs !== undefined && (typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0)) {
      throw new Error('durationMs must be a non-negative finite number');
    }
    this.sweepExpired();
    if (this.faults.size >= MAX_FAULTS) {
      throw new Error(`Maximum number of active faults (${String(MAX_FAULTS)}) exceeded. Clear some faults first.`);
    }
    const id = `${target}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.faults.set(id, {
      target,
      config,
      activatedAt: Date.now(),
      expiresAt: durationMs !== undefined ? Date.now() + durationMs : null,
      requestCount: 0,
    });
    logger.warn({ faultId: id, target, faultType: config.type }, 'Chaos fault injected');
    return id;
  }

  clear(faultId: string): boolean {
    const existed = this.faults.delete(faultId);
    logger.info({ faultId }, existed ? 'Chaos fault cleared' : 'Chaos fault not found');
    return existed;
  }

  clearAll(): void {
    this.faults.clear();
    logger.info('All chaos faults cleared');
  }

  private sweepExpired(): void {
    const now = Date.now();
    for (const [id, fault] of this.faults) {
      if (fault.expiresAt !== null && now > fault.expiresAt) {
        this.faults.delete(id);
        logger.info({ faultId: id }, 'Chaos fault expired');
      }
    }
  }

  getFault(target: FaultTarget): FaultConfig | null {
    const expired: string[] = [];
    let matchedConfig: FaultConfig | null = null;

    for (const [id, fault] of this.faults) {
      if (fault.target !== target) continue;

      if (fault.expiresAt !== null && Date.now() > fault.expiresAt) {
        expired.push(id);
        continue;
      }

      if (matchedConfig === null) {
        if (fault.config.probability !== undefined && Math.random() > fault.config.probability) {
          // First-match semantics: only the first matching fault for a target is
          // evaluated. If its probability check fails, no further faults are tried.
          break;
        }
        fault.requestCount++;
        matchedConfig = fault.config;
      }
    }

    for (const id of expired) {
      this.faults.delete(id);
      logger.info({ faultId: id }, 'Chaos fault expired');
    }

    return matchedConfig;
  }

  getActiveFaults(): readonly {
    id: string;
    target: FaultTarget;
    type: string;
    requestCount: number;
  }[] {
    const now = Date.now();
    const expired: string[] = [];
    const result: { id: string; target: FaultTarget; type: string; requestCount: number }[] = [];
    for (const [id, f] of this.faults) {
      if (f.expiresAt !== null && now > f.expiresAt) {
        expired.push(id);
        continue;
      }
      result.push({
        id,
        target: f.target,
        type: f.config.type,
        requestCount: f.requestCount,
      });
    }
    for (const id of expired) {
      this.faults.delete(id);
    }
    return result;
  }

  static reset(): void {
    if (ChaosController.instance) {
      ChaosController.instance.clearAll();
    }
    ChaosController.instance = null;
  }
}
