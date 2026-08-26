import type { AgentTurnExecutor } from '@salesops/core';
import type { EvalCase, EvalResult, EvalSuiteResult } from './types.js';

export interface EvalRunnerOptions {
  executor: AgentTurnExecutor;
  tenantId: string;
}

export class EvalRunner {
  private executor: AgentTurnExecutor;
  private tenantId: string;

  constructor(options: EvalRunnerOptions) {
    this.executor = options.executor;
    this.tenantId = options.tenantId;
  }

  async runCase(evalCase: EvalCase): Promise<EvalResult> {
    const startTime = Date.now();
    const sessionId = `eval_session_${crypto.randomUUID().slice(0, 8)}`;

    try {
      const output = await this.executor.executeTurn({
        sessionId,
        tenantId: this.tenantId,
        message: {
          id: `msg_${crypto.randomUUID().slice(0, 8)}`,
          channel: 'web',
          sessionId,
          senderId: 'eval_visitor',
          content: evalCase.input,
          timestamp: new Date().toISOString()
        },
        history: evalCase.history || [],
        stage: evalCase.stage || 'discover',
        locale: evalCase.locale || 'pt-PT'
      });

      const replyText = output.chunks.join(' ');
      const toolNamesCalled = output.toolCalls.map((tc) => tc.name);

      // 1. Check expected tool calls
      if (evalCase.expectedToolCalls && evalCase.expectedToolCalls.length > 0) {
        for (const expected of evalCase.expectedToolCalls) {
          if (!toolNamesCalled.includes(expected)) {
            return {
              caseId: evalCase.id,
              passed: false,
              error: `Expected tool call "${expected}" was not called. Actual calls: [${toolNamesCalled.join(', ')}]`,
              output,
              latencyMs: Date.now() - startTime
            };
          }
        }
      }

      // 2. Check forbidden phrases
      if (evalCase.forbiddenPhrases && evalCase.forbiddenPhrases.length > 0) {
        for (const forbidden of evalCase.forbiddenPhrases) {
          const isMatched =
            typeof forbidden === 'string'
              ? replyText.toLowerCase().includes(forbidden.toLowerCase())
              : forbidden.test(replyText);

          if (isMatched) {
            return {
              caseId: evalCase.id,
              passed: false,
              error: `Forbidden phrase/pattern "${forbidden.toString()}" was detected in reply: "${replyText}"`,
              output,
              latencyMs: Date.now() - startTime
            };
          }
        }
      }

      // 3. Check required phrases
      if (evalCase.requiredPhrases && evalCase.requiredPhrases.length > 0) {
        for (const required of evalCase.requiredPhrases) {
          const isMatched =
            typeof required === 'string'
              ? replyText.toLowerCase().includes(required.toLowerCase())
              : required.test(replyText);

          if (!isMatched) {
            return {
              caseId: evalCase.id,
              passed: false,
              error: `Required phrase/pattern "${required.toString()}" was missing in reply: "${replyText}"`,
              output,
              latencyMs: Date.now() - startTime
            };
          }
        }
      }

      // 4. Custom validator
      if (evalCase.customValidator) {
        const customOk = await evalCase.customValidator(output);
        if (!customOk) {
          return {
            caseId: evalCase.id,
            passed: false,
            error: `Custom validator failed for reply: "${replyText}"`,
            output,
            latencyMs: Date.now() - startTime
          };
        }
      }

      return {
        caseId: evalCase.id,
        passed: true,
        output,
        latencyMs: Date.now() - startTime
      };
    } catch (err: unknown) {
      return {
        caseId: evalCase.id,
        passed: false,
        error: `Execution crashed with error: ${(err as Error).message}`,
        latencyMs: Date.now() - startTime
      };
    }
  }

  async runSuite(suiteName: string, cases: EvalCase[]): Promise<EvalSuiteResult> {
    const results: EvalResult[] = [];
    let passed = 0;
    let failed = 0;

    for (const c of cases) {
      const res = await this.runCase(c);
      results.push(res);
      if (res.passed) {
        passed++;
      } else {
        failed++;
      }
    }

    return {
      suite: suiteName,
      total: cases.length,
      passed,
      failed,
      results
    };
  }
}
