import { createHmac, timingSafeEqual } from 'node:crypto';
import type { Express, Request, Response } from 'express';
import { assertChaosAllowed } from './guard.js';
import { ChaosController } from './controller.js';
import type { FaultConfig } from './fault-types.js';
import { isFaultTarget } from './fault-types.js';
import { getLogger } from './logger.js';

const logger = getLogger('chaos-admin');

const VALID_FAULT_TYPES = new Set([
  'latency', 'error', 'timeout', 'malformed',
  'connection-refused', 'connection-drop', 'rate-limit', 'schema-mismatch',
]);

function checkAdminAuth(req: Request, res: Response): boolean {
  const requiredToken = process.env['CHAOS_ADMIN_TOKEN'];
  if (requiredToken === undefined) {
    res.status(403).json({ error: 'CHAOS_ADMIN_TOKEN is not set — admin access denied. Set CHAOS_ADMIN_TOKEN to enable admin endpoints.' });
    return false;
  }
  if (requiredToken === '') {
    res.status(403).json({ error: 'CHAOS_ADMIN_TOKEN is set but empty — refusing access' });
    return false;
  }
  const provided = req.headers['authorization']?.replace(/^Bearer /, '') ?? '';
  const key = 'chaos-admin-auth';
  const a = createHmac('sha256', key).update(provided).digest();
  const b = createHmac('sha256', key).update(requiredToken).digest();
  if (!timingSafeEqual(a, b)) {
    res.status(403).json({ error: 'Invalid or missing CHAOS_ADMIN_TOKEN' });
    return false;
  }
  return true;
}

interface InjectBody {
  target: string;
  config: { type: string; [key: string]: unknown };
  durationMs?: number;
}

const REQUIRED_NUMBER_FIELDS: Record<string, string[]> = {
  'latency': ['delayMs'],
  'error': ['statusCode'],
  'timeout': ['hangMs'],
  'rate-limit': ['retryAfterSeconds'],
};

function validateFaultConfig(config: { type: string; [key: string]: unknown }): string | null {
  const requiredFields = REQUIRED_NUMBER_FIELDS[config.type];
  if (requiredFields) {
    for (const field of requiredFields) {
      const val = config[field];
      if (val === undefined || typeof val !== 'number' || !Number.isFinite(val)) {
        return `config.${field} must be a finite number for fault type '${config.type}'`;
      }
    }
  }
  if (config.type === 'schema-mismatch') {
    const mf = config['missingFields'];
    if (mf === undefined || !Array.isArray(mf) || !mf.every((v: unknown) => typeof v === 'string')) {
      return 'config.missingFields must be an array of strings for fault type \'schema-mismatch\'';
    }
  }
  if (config.type === 'malformed') {
    const cr = config['corruptResponse'];
    if (cr === undefined || typeof cr !== 'boolean') {
      return 'config.corruptResponse must be a boolean for fault type \'malformed\'';
    }
  }
  if (requiredFields) {
    for (const field of requiredFields) {
      const val = config[field] as number;
      if (val < 0) {
        return `config.${field} must be a non-negative number for fault type '${config.type}'`;
      }
    }
  }
  if (config['message'] !== undefined && typeof config['message'] !== 'string') {
    return 'config.message must be a string';
  }
  return null;
}

export function registerChaosEndpoint(app: Express): void {
  assertChaosAllowed();

  app.get('/chaos/status', (req: Request, res: Response) => {
    if (!checkAdminAuth(req, res)) return;
    try {
      const controller = ChaosController.getInstance();
      const faults = controller.getActiveFaults();
      res.json({ faults });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error({ error: message }, 'Chaos status failed');
      res.status(500).json({ error: 'Failed to get chaos status' });
    }
  });

  app.post('/chaos/inject', (req: Request, res: Response) => {
    if (!checkAdminAuth(req, res)) return;
    try {
      const body = req.body as InjectBody;
      if (!isFaultTarget(body?.target)) {
        res.status(400).json({ error: 'Missing required field: target (non-empty string)' });
        return;
      }
      if (!body.config || typeof body.config !== 'object' || !VALID_FAULT_TYPES.has(body.config.type)) {
        res.status(400).json({ error: `Missing or invalid field: config.type (must be one of: ${[...VALID_FAULT_TYPES].join(', ')})` });
        return;
      }
      const validationError = validateFaultConfig(body.config);
      if (validationError) {
        res.status(400).json({ error: validationError });
        return;
      }
      if (body.durationMs !== undefined) {
        if (typeof body.durationMs !== 'number' || !Number.isFinite(body.durationMs) || body.durationMs < 0) {
          res.status(400).json({ error: 'durationMs must be a non-negative finite number' });
          return;
        }
      }
      const controller = ChaosController.getInstance();
      const faultId = controller.inject(
        body.target,
        body.config as FaultConfig,
        body.durationMs,
      );
      res.json({ faultId });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error({ error: message }, 'Chaos inject failed');
      res.status(500).json({ error: 'Failed to inject fault' });
    }
  });

  app.post('/chaos/clear', (req: Request, res: Response) => {
    if (!checkAdminAuth(req, res)) return;
    try {
      const body = req.body as { faultId: string } | undefined;
      if (!body?.faultId || typeof body.faultId !== 'string') {
        res.status(400).json({ error: 'Missing required field: faultId' });
        return;
      }
      const controller = ChaosController.getInstance();
      controller.clear(body.faultId);
      res.json({ cleared: body.faultId });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error({ error: message }, 'Chaos clear failed');
      res.status(500).json({ error: 'Failed to clear fault' });
    }
  });

  app.post('/chaos/clear-all', (req: Request, res: Response) => {
    if (!checkAdminAuth(req, res)) return;
    try {
      const controller = ChaosController.getInstance();
      controller.clearAll();
      res.json({ cleared: 'all' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error({ error: message }, 'Chaos clear-all failed');
      res.status(500).json({ error: 'Failed to clear all faults' });
    }
  });

  if (process.env['CHAOS_ADMIN_TOKEN'] === undefined) {
    logger.warn('CHAOS_ADMIN_TOKEN is not set — admin endpoints will reject all requests');
  }
  logger.info('Chaos admin endpoints registered at /chaos/*');
}
