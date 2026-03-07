export function assertChaosAllowed(): void {
  const env = process.env['ENVIRONMENT']?.toLowerCase();
  const nodeEnv = process.env['NODE_ENV']?.toLowerCase();
  if (env === 'production' || nodeEnv === 'production') {
    throw new Error('FATAL: Chaos framework must never run in production');
  }
  if (process.env['CHAOS_ENABLED'] !== 'true') {
    throw new Error('Chaos framework not enabled. Set CHAOS_ENABLED=true');
  }
}
