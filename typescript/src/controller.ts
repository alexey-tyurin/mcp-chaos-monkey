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

  clear(faultId: string): void {
    this.faults.delete(faultId);
    logger.info({ faultId }, 'Chaos fault cleared');
  }

  clearAll(): void {
    this.faults.clear();
    logger.info('All chaos faults cleared');
  }

  getFault(target: FaultTarget): FaultConfig | null {
    for (const [id, fault] of this.faults) {
      if (fault.target !== target) continue;

      if (fault.expiresAt !== null && Date.now() > fault.expiresAt) {
        this.faults.delete(id);
        logger.info({ faultId: id }, 'Chaos fault expired');
        continue;
      }

      if (fault.config.probability !== undefined && Math.random() > fault.config.probability) {
        continue;
      }

      fault.requestCount++;
      // Continue iterating to clean up any remaining expired faults for this target
      const config = fault.config;
      for (const [remainingId, remainingFault] of this.faults) {
        if (remainingId === id) continue;
        if (remainingFault.target !== target) continue;
        if (remainingFault.expiresAt !== null && Date.now() > remainingFault.expiresAt) {
          this.faults.delete(remainingId);
        }
      }
      return config;
    }
    return null;
  }

  getActiveFaults(): readonly {
    id: string;
    target: FaultTarget;
    type: string;
    requestCount: number;
  }[] {
    const now = Date.now();
    const result: { id: string; target: FaultTarget; type: string; requestCount: number }[] = [];
    for (const [id, f] of this.faults) {
      if (f.expiresAt !== null && now > f.expiresAt) {
        this.faults.delete(id);
        continue;
      }
      result.push({
        id,
        target: f.target,
        type: f.config.type,
        requestCount: f.requestCount,
      });
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
