import { describe, it, expect, vi } from 'vitest';
import { SpendLedgerService } from '../src/billing/spend_ledger.js';
import type { Database } from '../src/db/client.js';
import { REWILT_TENANT_ID } from '../src/db/seed.js';

describe('Custom-Tier Prepaid Model-Spend Ledger (WP-23)', () => {
  const tenantId = REWILT_TENANT_ID;

  it('records credit top-up and calculates running balance', async () => {
    const entries: Array<{
      id: string;
      tenantId: string;
      entryType: string;
      amountMinor: number;
      balanceAfterMinor: number;
      model?: string | null;
      inputTokens?: number;
      outputTokens?: number;
      sessionId?: string | null;
      reference?: string | null;
      createdAt: Date;
    }> = [];

    const mockDb = {
      select: vi.fn().mockReturnValue({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockReturnValue({
            orderBy: vi.fn().mockReturnValue({
              limit: vi.fn().mockImplementation(async () => {
                const latest = entries[entries.length - 1];
                return latest ? [{ balanceAfter: latest.balanceAfterMinor }] : [];
              })
            })
          })
        })
      }),
      insert: vi.fn().mockReturnValue({
        values: vi.fn().mockImplementation((val) => ({
          returning: vi.fn().mockImplementation(async () => {
            const row = { id: 'ledg_1', ...val, createdAt: new Date() };
            entries.push(row);
            return [row];
          })
        }))
      })
    } as unknown as Database;

    const ledgerService = new SpendLedgerService(mockDb);

    const creditEntry = await ledgerService.recordCredit(tenantId, 10000, 'Stripe checkout cs_123'); // €100.00
    expect(creditEntry.amountMinor).toBe(10000);
    expect(creditEntry.balanceAfterMinor).toBe(10000);
    expect(creditEntry.entryType).toBe('credit_topup');

    const bal = await ledgerService.getCurrentBalance(tenantId);
    expect(bal.balanceMinor).toBe(10000);
    expect(bal.balanceEur).toBe(100);
  });

  it('records model turn debits and produces itemized monthly statements', async () => {
    const sampleEntries = [
      {
        id: '1',
        tenantId,
        entryType: 'credit_topup',
        amountMinor: 5000,
        balanceAfterMinor: 5000,
        model: null,
        inputTokens: 0,
        outputTokens: 0,
        sessionId: null,
        reference: 'Initial deposit',
        createdAt: new Date('2026-08-01T10:00:00Z')
      },
      {
        id: '2',
        tenantId,
        entryType: 'turn_debit',
        amountMinor: -2,
        balanceAfterMinor: 4998,
        model: 'gemini-2.5-flash',
        inputTokens: 100,
        outputTokens: 50,
        sessionId: 'sess_1',
        reference: 'Turn 1',
        createdAt: new Date('2026-08-05T12:00:00Z')
      },
      {
        id: '3',
        tenantId,
        entryType: 'turn_debit',
        amountMinor: -5,
        balanceAfterMinor: 4993,
        model: 'mistral-small-latest',
        inputTokens: 200,
        outputTokens: 80,
        sessionId: 'sess_2',
        reference: 'Turn 2',
        createdAt: new Date('2026-08-10T15:00:00Z')
      }
    ];

    const mockDb = {
      select: vi.fn().mockImplementation((_fields) => ({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockReturnValue({
            orderBy: vi.fn().mockImplementation(() => {
              const promise = Promise.resolve(sampleEntries) as Promise<typeof sampleEntries> & {
                limit: (n: number) => Promise<Array<{ balanceAfter: number }>>;
              };
              promise.limit = vi.fn().mockResolvedValue([]);
              return promise;
            })
          })
        })
      }))
    } as unknown as Database;

    const ledgerService = new SpendLedgerService(mockDb);
    const statement = await ledgerService.getMonthlyStatement(tenantId, 2026, 8);

    expect(statement.totalCreditsMinor).toBe(5000);
    expect(statement.totalDebitsMinor).toBe(7);
    expect(statement.endingBalanceMinor).toBe(4993);
    expect(statement.tokensByModel['gemini-2.5-flash']?.inputTokens).toBe(100);
    expect(statement.tokensByModel['mistral-small-latest']?.outputTokens).toBe(80);
    expect(statement.tokensByModel['mistral-small-latest']?.totalCostMinor).toBe(5);
    expect(statement.entryCount).toBe(3);
  });
});
