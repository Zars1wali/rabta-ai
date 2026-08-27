import { eq, and, desc, sql, gte, lte } from 'drizzle-orm';
import type { Database } from '../db/client.js';
import { spendLedger } from '../db/schema.js';

export type SpendLedgerEntryType = 'credit_topup' | 'turn_debit' | 'refund' | 'adjustment';

export interface SpendLedgerEntry {
  id: string;
  tenantId: string;
  entryType: SpendLedgerEntryType;
  amountMinor: number;
  balanceAfterMinor: number;
  model: string | null;
  inputTokens: number;
  outputTokens: number;
  sessionId: string | null;
  reference: string | null;
  createdAt: Date;
}

export interface MonthlySpendStatement {
  tenantId: string;
  year: number;
  month: number;
  startingBalanceMinor: number;
  totalCreditsMinor: number;
  totalDebitsMinor: number;
  endingBalanceMinor: number;
  tokensByModel: Record<string, { inputTokens: number; outputTokens: number; totalCostMinor: number }>;
  entryCount: number;
}

export class SpendLedgerService {
  constructor(private db: Database) {}

  async getCurrentBalance(tenantId: string): Promise<{ balanceMinor: number; balanceEur: number }> {
    const [latest] = await this.db
      .select({ balanceAfter: spendLedger.balanceAfterMinor })
      .from(spendLedger)
      .where(eq(spendLedger.tenantId, tenantId))
      .orderBy(desc(spendLedger.createdAt))
      .limit(1);

    const balanceMinor = latest ? latest.balanceAfter : 0;
    return {
      balanceMinor,
      balanceEur: Math.round(balanceMinor) / 100
    };
  }

  async recordCredit(
    tenantId: string,
    amountMinor: number,
    reference?: string
  ): Promise<SpendLedgerEntry> {
    const current = await this.getCurrentBalance(tenantId);
    const newBalance = current.balanceMinor + Math.abs(amountMinor);

    const [entry] = await this.db
      .insert(spendLedger)
      .values({
        tenantId,
        entryType: 'credit_topup',
        amountMinor: Math.abs(amountMinor),
        balanceAfterMinor: newBalance,
        reference: reference || 'Prepaid credit top-up'
      })
      .returning();

    return {
      id: entry!.id,
      tenantId: entry!.tenantId,
      entryType: entry!.entryType as SpendLedgerEntryType,
      amountMinor: entry!.amountMinor,
      balanceAfterMinor: entry!.balanceAfterMinor,
      model: entry!.model,
      inputTokens: entry!.inputTokens ?? 0,
      outputTokens: entry!.outputTokens ?? 0,
      sessionId: entry!.sessionId,
      reference: entry!.reference,
      createdAt: entry!.createdAt
    };
  }

  async recordDebit(options: {
    tenantId: string;
    amountMinor: number;
    model: string;
    inputTokens: number;
    outputTokens: number;
    sessionId?: string;
    reference?: string;
  }): Promise<SpendLedgerEntry> {
    const current = await this.getCurrentBalance(options.tenantId);
    const debitAmount = -Math.abs(options.amountMinor);
    const newBalance = current.balanceMinor + debitAmount;

    const [entry] = await this.db
      .insert(spendLedger)
      .values({
        tenantId: options.tenantId,
        entryType: 'turn_debit',
        amountMinor: debitAmount,
        balanceAfterMinor: newBalance,
        model: options.model,
        inputTokens: options.inputTokens,
        outputTokens: options.outputTokens,
        sessionId: options.sessionId,
        reference: options.reference || `Turn debit: ${options.model}`
      })
      .returning();

    return {
      id: entry!.id,
      tenantId: entry!.tenantId,
      entryType: entry!.entryType as SpendLedgerEntryType,
      amountMinor: entry!.amountMinor,
      balanceAfterMinor: entry!.balanceAfterMinor,
      model: entry!.model,
      inputTokens: entry!.inputTokens ?? 0,
      outputTokens: entry!.outputTokens ?? 0,
      sessionId: entry!.sessionId,
      reference: entry!.reference,
      createdAt: entry!.createdAt
    };
  }

  async getMonthlyStatement(
    tenantId: string,
    year: number,
    month: number
  ): Promise<MonthlySpendStatement> {
    const startDate = new Date(Date.UTC(year, month - 1, 1, 0, 0, 0));
    const endDate = new Date(Date.UTC(year, month, 0, 23, 59, 59, 999));

    // 1. Get entries in month
    const entries = await this.db
      .select()
      .from(spendLedger)
      .where(
        and(
          eq(spendLedger.tenantId, tenantId),
          gte(spendLedger.createdAt, startDate),
          lte(spendLedger.createdAt, endDate)
        )
      )
      .orderBy(spendLedger.createdAt);

    // 2. Get starting balance before period
    const [prior] = await this.db
      .select({ balanceAfter: spendLedger.balanceAfterMinor })
      .from(spendLedger)
      .where(
        and(
          eq(spendLedger.tenantId, tenantId),
          sql`${spendLedger.createdAt} < ${startDate}`
        )
      )
      .orderBy(desc(spendLedger.createdAt))
      .limit(1);

    const startingBalanceMinor = prior ? prior.balanceAfter : 0;

    let totalCreditsMinor = 0;
    let totalDebitsMinor = 0;
    const tokensByModel: Record<string, { inputTokens: number; outputTokens: number; totalCostMinor: number }> = {};

    for (const e of entries) {
      if (e.amountMinor > 0) {
        totalCreditsMinor += e.amountMinor;
      } else {
        totalDebitsMinor += Math.abs(e.amountMinor);
      }

      if (e.model) {
        const modelStats = tokensByModel[e.model] || { inputTokens: 0, outputTokens: 0, totalCostMinor: 0 };
        modelStats.inputTokens += e.inputTokens || 0;
        modelStats.outputTokens += e.outputTokens || 0;
        modelStats.totalCostMinor += Math.abs(e.amountMinor);
        tokensByModel[e.model] = modelStats;
      }
    }

    const endingBalanceMinor = startingBalanceMinor + totalCreditsMinor - totalDebitsMinor;

    return {
      tenantId,
      year,
      month,
      startingBalanceMinor,
      totalCreditsMinor,
      totalDebitsMinor,
      endingBalanceMinor,
      tokensByModel,
      entryCount: entries.length
    };
  }
}
