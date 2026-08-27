import { describe, it, expect, vi } from 'vitest';
import {
  parseOwnerCommand,
  OwnerControlPlane,
  type WhatsAppChannelConfig
} from '../src/channels/index.js';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '../src/db/seed.js';
import type { SessionRepository, TenantRepository } from '../src/db/repositories.js';
import type { TenantConfig } from '@salesops/types';

describe('Owner WhatsApp Control Plane (WP-22)', () => {
  const controlPlane = new OwnerControlPlane();

  const customTenantConfig: TenantConfig = {
    ...REWILT_TENANT_CONFIG,
    channels: [
      {
        kind: 'whatsapp',
        ownerPhones: ['351910000001', '+351 910 000 002']
      } as unknown as WhatsAppChannelConfig
    ]
  };

  it('parses valid owner slash commands', () => {
    expect(parseOwnerCommand('/pause')).toEqual({ type: 'pause', targetPhone: undefined, raw: '/pause' });
    expect(parseOwnerCommand('/pause 351912345678')).toEqual({ type: 'pause', targetPhone: '351912345678', raw: '/pause 351912345678' });
    expect(parseOwnerCommand('/resume')).toEqual({ type: 'resume', targetPhone: undefined, raw: '/resume' });
    expect(parseOwnerCommand('/status')).toEqual({ type: 'status', raw: '/status' });
    expect(parseOwnerCommand('/takeover 351912345678')).toEqual({ type: 'takeover', targetPhone: '351912345678', raw: '/takeover 351912345678' });
    expect(parseOwnerCommand('/help')).toEqual({ type: 'help', raw: '/help' });

    expect(parseOwnerCommand('Olá, boa tarde!')).toBeNull();
  });

  it('verifies authorized owner phone numbers and isolates customer numbers', () => {
    expect(controlPlane.isOwnerPhone(customTenantConfig, '351910000001')).toBe(true);
    expect(controlPlane.isOwnerPhone(customTenantConfig, '+351910000002')).toBe(true);
    expect(controlPlane.isOwnerPhone(customTenantConfig, '351999999999')).toBe(false);
  });

  it('executes /pause and /resume commands updating session state', async () => {
    const mockSessionRepo = {
      updateTurn: vi.fn().mockResolvedValue({ id: 'wa_351912345678' })
    } as unknown as SessionRepository;

    const mockTenantRepo = {} as unknown as TenantRepository;

    // 1. /pause for specific customer
    const pauseRes = await controlPlane.executeCommand({
      command: { type: 'pause', targetPhone: '351912345678', raw: '/pause 351912345678' },
      tenantConfig: customTenantConfig,
      sessionRepo: mockSessionRepo,
      tenantRepo: mockTenantRepo
    });

    expect(pauseRes.actionTaken).toBe('paused');
    expect(pauseRes.replyText).toContain('351912345678');
    expect(mockSessionRepo.updateTurn).toHaveBeenCalledWith(
      REWILT_TENANT_ID,
      'wa_351912345678',
      { stage: 'handoff' }
    );

    // 2. /resume for specific customer
    const resumeRes = await controlPlane.executeCommand({
      command: { type: 'resume', targetPhone: '351912345678', raw: '/resume 351912345678' },
      tenantConfig: customTenantConfig,
      sessionRepo: mockSessionRepo,
      tenantRepo: mockTenantRepo
    });

    expect(resumeRes.actionTaken).toBe('resumed');
    expect(mockSessionRepo.updateTurn).toHaveBeenCalledWith(
      REWILT_TENANT_ID,
      'wa_351912345678',
      { stage: 'discover' }
    );
  });

  it('executes /takeover transitioning customer session to handoff', async () => {
    const mockSessionRepo = {
      updateTurn: vi.fn().mockResolvedValue({ id: 'wa_351912345678' })
    } as unknown as SessionRepository;

    const takeoverRes = await controlPlane.executeCommand({
      command: { type: 'takeover', targetPhone: '351912345678', raw: '/takeover 351912345678' },
      tenantConfig: customTenantConfig,
      sessionRepo: mockSessionRepo,
      tenantRepo: {} as unknown as TenantRepository
    });

    expect(takeoverRes.actionTaken).toBe('takeover_initiated');
    expect(takeoverRes.replyText).toContain('Assunção de Conversa');
    expect(mockSessionRepo.updateTurn).toHaveBeenCalledWith(
      REWILT_TENANT_ID,
      'wa_351912345678',
      { stage: 'handoff' }
    );
  });

  it('executes /status and returns operational store health', async () => {
    const statusRes = await controlPlane.executeCommand({
      command: { type: 'status', raw: '/status' },
      tenantConfig: customTenantConfig,
      sessionRepo: {} as unknown as SessionRepository,
      tenantRepo: {} as unknown as TenantRepository
    });

    expect(statusRes.actionTaken).toBe('status_reported');
    expect(statusRes.replyText).toContain('Rewilt Sales Ops');
    expect(statusRes.replyText).toContain('STANDARD');
  });
});
