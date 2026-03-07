import { ChaosController } from '../controller.js';
import type { FaultTarget } from '../fault-types.js';
import type { Request, Response, NextFunction } from 'express';
import { getLogger } from '../logger.js';

const logger = getLogger('chaos-auth');

/** Fixed middleware that targets 'oauth-token'. */
export function chaosAuthMiddleware(_req: Request, res: Response, next: NextFunction): void {
  applyAuthFault('oauth-token', res, next);
}

/** Factory for creating auth middleware with a configurable target. */
export function createChaosAuthMiddleware(
  target: FaultTarget = 'oauth-token',
): (req: Request, res: Response, next: NextFunction) => void {
  return (_req: Request, res: Response, next: NextFunction): void => {
    applyAuthFault(target, res, next);
  };
}

function applyAuthFault(target: FaultTarget, res: Response, next: NextFunction): void {
  const controller = ChaosController.getInstance();
  const fault = controller.getFault(target);

  if (!fault) {
    next();
    return;
  }

  logger.debug({ faultType: fault.type }, 'Chaos auth fault triggered');

  switch (fault.type) {
    case 'error':
      res.status(fault.statusCode).json({
        error: 'token_invalid',
        message: fault.message ?? 'Authentication failed (chaos)',
      });
      return;
    case 'latency':
      setTimeout(() => { next(); }, fault.delayMs);
      return;
    case 'timeout':
      // Hang for the specified duration then send 504 to avoid leaking connections
      setTimeout(() => {
        try {
          if (!res.writableEnded) {
            res.status(504).json({ error: 'Gateway Timeout (chaos)' });
          }
        } catch (err: unknown) {
          logger.error({ error: err instanceof Error ? err.message : String(err) }, 'Failed to send chaos timeout response');
        }
      }, fault.hangMs);
      return;
    default:
      next();
  }
}
