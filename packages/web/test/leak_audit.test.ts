import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('Client Artifact Leak & Compliance Audit', () => {
  it('guarantees EU AI Act Art. 50 disclosure badge is present in Widget component', () => {
    const widgetFilePath = path.resolve(__dirname, '../src/ui/Widget.tsx');
    const content = fs.readFileSync(widgetFilePath, 'utf-8');

    expect(content).toContain('data-testid="eu-ai-act-disclosure-badge"');
    expect(content).toContain('Assistente de IA');
  });

  it('scans client UI bundle sources for leaked server secrets or environment variables', () => {
    const uiDir = path.resolve(__dirname, '../src/ui');
    const files = fs.readdirSync(uiDir);

    const forbiddenPatterns = [
      /DATABASE_URL/i,
      /STRIPE_SECRET_KEY/i,
      /GEMINI_API_KEY/i,
      /WHATSAPP_ACCESS_TOKEN/i,
      /postgres:\/\//i
    ];

    for (const file of files) {
      if (file.endsWith('.ts') || file.endsWith('.tsx') || file.endsWith('.js')) {
        const filePath = path.join(uiDir, file);
        const content = fs.readFileSync(filePath, 'utf-8');

        for (const pattern of forbiddenPatterns) {
          expect(
            pattern.test(content),
            `Security Alert: Client source file ${file} matched forbidden secret pattern ${pattern.toString()}`
          ).toBe(false);
        }
      }
    }
  });
});
