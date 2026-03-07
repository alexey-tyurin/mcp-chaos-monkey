import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { assertChaosAllowed } from '../src/guard.js';

describe('assertChaosAllowed', () => {
  const originalNodeEnv = process.env['NODE_ENV'];
  const originalChaosEnabled = process.env['CHAOS_ENABLED'];
  const originalEnvironment = process.env['ENVIRONMENT'];

  beforeEach(() => {
    delete process.env['NODE_ENV'];
    delete process.env['CHAOS_ENABLED'];
    delete process.env['ENVIRONMENT'];
  });

  afterEach(() => {
    if (originalNodeEnv !== undefined) {
      process.env['NODE_ENV'] = originalNodeEnv;
    } else {
      delete process.env['NODE_ENV'];
    }
    if (originalChaosEnabled !== undefined) {
      process.env['CHAOS_ENABLED'] = originalChaosEnabled;
    } else {
      delete process.env['CHAOS_ENABLED'];
    }
    if (originalEnvironment !== undefined) {
      process.env['ENVIRONMENT'] = originalEnvironment;
    } else {
      delete process.env['ENVIRONMENT'];
    }
  });

  it('throws when NODE_ENV is production', () => {
    process.env['NODE_ENV'] = 'production';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).toThrow(
      'FATAL: Chaos framework must never run in production',
    );
  });

  it('throws when CHAOS_ENABLED is not set', () => {
    process.env['NODE_ENV'] = 'test';

    expect(() => assertChaosAllowed()).toThrow(
      'Chaos framework not enabled. Set CHAOS_ENABLED=true',
    );
  });

  it('throws when CHAOS_ENABLED is not "true"', () => {
    process.env['NODE_ENV'] = 'test';
    process.env['CHAOS_ENABLED'] = 'false';

    expect(() => assertChaosAllowed()).toThrow(
      'Chaos framework not enabled. Set CHAOS_ENABLED=true',
    );
  });

  it('passes when NODE_ENV is not production and CHAOS_ENABLED is true', () => {
    process.env['NODE_ENV'] = 'test';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).not.toThrow();
  });

  it('passes when NODE_ENV is undefined and CHAOS_ENABLED is true', () => {
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).not.toThrow();
  });

  it('blocks when NODE_ENV is "Production" (case-insensitive, Fix #5)', () => {
    process.env['NODE_ENV'] = 'Production';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).toThrow(
      'FATAL: Chaos framework must never run in production',
    );
  });

  it('blocks when NODE_ENV is "PRODUCTION" (case-insensitive, Fix #5)', () => {
    process.env['NODE_ENV'] = 'PRODUCTION';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).toThrow(
      'FATAL: Chaos framework must never run in production',
    );
  });

  it('blocks when ENVIRONMENT is production (parity with Python guard)', () => {
    process.env['ENVIRONMENT'] = 'production';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).toThrow(
      'FATAL: Chaos framework must never run in production',
    );
  });

  it('blocks when ENVIRONMENT is Production (case-insensitive)', () => {
    process.env['ENVIRONMENT'] = 'Production';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).toThrow(
      'FATAL: Chaos framework must never run in production',
    );
  });

  it('passes when ENVIRONMENT is not production', () => {
    process.env['ENVIRONMENT'] = 'staging';
    process.env['CHAOS_ENABLED'] = 'true';

    expect(() => assertChaosAllowed()).not.toThrow();
  });
});
