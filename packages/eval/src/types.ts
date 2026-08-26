import type { AgentMessage, AgentTurnOutput, FunnelStage } from '@salesops/types';

export interface EvalCase {
  id: string;
  suite: string;
  description: string;
  input: string;
  stage?: FunnelStage;
  locale?: string;
  history?: AgentMessage[];
  expectedToolCalls?: string[];
  forbiddenPhrases?: (string | RegExp)[];
  requiredPhrases?: (string | RegExp)[];
  customValidator?: (output: AgentTurnOutput) => boolean | Promise<boolean>;
}

export interface EvalResult {
  caseId: string;
  passed: boolean;
  error?: string;
  output?: AgentTurnOutput;
  latencyMs: number;
}

export interface EvalSuiteResult {
  suite: string;
  total: number;
  passed: number;
  failed: number;
  results: EvalResult[];
}
