import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ChaosController } from '../src/controller.js';
import { runCli } from '../src/cli.js';

describe('runCli', () => {
  let stdoutOutput: string;

  beforeEach(() => {
    process.env['CHAOS_ENABLED'] = 'true';
    process.env['NODE_ENV'] = 'test';
    ChaosController.reset();
    stdoutOutput = '';
    vi.spyOn(process.stdout, 'write').mockImplementation((chunk: string | Uint8Array) => {
      stdoutOutput += String(chunk);
      return true;
    });
  });

  afterEach(() => {
    ChaosController.reset();
    vi.restoreAllMocks();
  });

  it('prints usage for unknown commands', () => {
    runCli(['unknown']);
    expect(stdoutOutput).toContain('Usage:');
  });

  it('prints usage when inject is called without args', () => {
    runCli(['inject']);
    expect(stdoutOutput).toContain('Usage:');
  });

  it('injects a fault via CLI', () => {
    runCli(['inject', 'weather-api', 'error', '--status', '503']);
    expect(stdoutOutput).toContain('Injected fault:');

    const controller = ChaosController.getInstance();
    const fault = controller.getFault('weather-api');
    expect(fault).not.toBeNull();
    expect(fault!.type).toBe('error');
  });

  it('accepts any string as target', () => {
    runCli(['inject', 'my-custom-target', 'latency', '--delay', '200']);
    expect(stdoutOutput).toContain('Injected fault:');

    const controller = ChaosController.getInstance();
    expect(controller.getFault('my-custom-target')).not.toBeNull();
  });

  it('rejects invalid fault types', () => {
    runCli(['inject', 'weather-api', 'not-a-fault']);
    expect(stdoutOutput).toContain('Invalid fault type');
  });

  it('clears a specific fault', () => {
    const controller = ChaosController.getInstance();
    const faultId = controller.inject('redis', { type: 'connection-refused' });

    runCli(['clear', faultId]);
    expect(stdoutOutput).toContain(`Cleared fault: ${faultId}`);
    expect(controller.getFault('redis')).toBeNull();
  });

  it('clears all faults', () => {
    const controller = ChaosController.getInstance();
    controller.inject('weather-api', { type: 'error', statusCode: 503 });
    controller.inject('redis', { type: 'connection-refused' });

    runCli(['clear-all']);
    expect(stdoutOutput).toContain('All faults cleared');
    expect(controller.getActiveFaults()).toHaveLength(0);
  });

  it('shows status with no active faults', () => {
    runCli(['status']);
    expect(stdoutOutput).toContain('No active faults');
  });

  it('shows status with active faults', () => {
    const controller = ChaosController.getInstance();
    controller.inject('weather-api', { type: 'error', statusCode: 503 });

    runCli(['status']);
    expect(stdoutOutput).toContain('Active faults (1)');
    expect(stdoutOutput).toContain('weather-api');
    expect(stdoutOutput).toContain('[error]');
  });

  it('converts duration from seconds to milliseconds', () => {
    runCli(['inject', 'weather-api', 'error', '--status', '503', '--duration', '30']);
    expect(stdoutOutput).toContain('Injected fault:');
  });
});
