/** Pluggable logger interface — pino's Logger satisfies this directly. */
export interface ChaosLogger {
  debug(obj: Record<string, unknown>, msg: string): void;
  info(obj: Record<string, unknown>, msg: string): void;
  info(msg: string): void;
  warn(obj: Record<string, unknown>, msg: string): void;
  error(obj: Record<string, unknown>, msg: string): void;
}

export type ChaosLoggerFactory = (name: string) => ChaosLogger;

let loggerFactory: ChaosLoggerFactory = createConsoleLogger;

/** Create a default console-based logger. */
export function createConsoleLogger(name: string): ChaosLogger {
  const prefix = `[${name}]`;
  return {
    debug(objOrMsg: Record<string, unknown> | string, msg?: string): void {
      if (typeof objOrMsg === 'string') {
        console.debug(prefix, objOrMsg);
      } else {
        console.debug(prefix, msg, objOrMsg);
      }
    },
    info(objOrMsg: Record<string, unknown> | string, msg?: string): void {
      if (typeof objOrMsg === 'string') {
        console.info(prefix, objOrMsg);
      } else {
        console.info(prefix, msg, objOrMsg);
      }
    },
    warn(objOrMsg: Record<string, unknown> | string, msg?: string): void {
      if (typeof objOrMsg === 'string') {
        console.warn(prefix, objOrMsg);
      } else {
        console.warn(prefix, msg, objOrMsg);
      }
    },
    error(objOrMsg: Record<string, unknown> | string, msg?: string): void {
      if (typeof objOrMsg === 'string') {
        console.error(prefix, objOrMsg);
      } else {
        console.error(prefix, msg, objOrMsg);
      }
    },
  } as ChaosLogger;
}

/** Set the global logger factory. Call once at startup. */
export function configureChaosLogger(factory: ChaosLoggerFactory): void {
  loggerFactory = factory;
}

/** Internal — used by all library modules. */
export function getLogger(name: string): ChaosLogger {
  return loggerFactory(name);
}
