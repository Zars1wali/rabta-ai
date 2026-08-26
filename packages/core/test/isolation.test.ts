import { describe, it, expect } from 'vitest';
import ts from 'typescript';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

describe('Tenant Isolation AST Guard', () => {
  it('asserts every tenant-scoped repository method requires and filters by tenantId', () => {
    const reposPath = path.resolve(__dirname, '../src/db/repositories.ts');
    const fileContent = fs.readFileSync(reposPath, 'utf-8');

    const sourceFile = ts.createSourceFile(
      'repositories.ts',
      fileContent,
      ts.ScriptTarget.Latest,
      true
    );

    const classes: ts.ClassDeclaration[] = [];
    ts.forEachChild(sourceFile, (node) => {
      if (ts.isClassDeclaration(node)) {
        classes.push(node);
      }
    });

    expect(classes.length).toBeGreaterThanOrEqual(5);

    for (const cls of classes) {
      const className = cls.name?.text ?? 'AnonymousClass';
      const methods = cls.members.filter(ts.isMethodDeclaration);

      for (const method of methods) {
        const methodName = method.name.getText(sourceFile);
        if (methodName.startsWith('_') || methodName === 'mapItemRowToCatalogItem') {
          continue; // skip private helpers
        }

        const methodText = method.getText(sourceFile);

        // Every method in tenant repositories (except TenantRepository itself where it's tenant-level)
        // must explicitly reference tenantId or tenants.id
        if (className === 'TenantRepository') {
          expect(methodText).toMatch(/(tenantId|slug|tenants\.id|tenants\.slug)/);
        } else {
          // In CatalogRepository, SessionRepository, MessageRepository, LeadRepository, ToolCallRepository
          expect(
            methodText.includes('tenantId') || methodText.includes('tenant_id'),
            `Method ${className}.${methodName} must explicitly filter or insert by tenantId for strict multi-tenant isolation.`
          ).toBe(true);
        }
      }
    }
  });

  it('fails if a simulated leaky query lacks tenantId', () => {
    const leakyQueryCode = `
      export class LeakyRepo {
        async getAllOrders() {
          return await this.db.select().from(catalogItems);
        }
      }
    `;

    const sourceFile = ts.createSourceFile(
      'leaky.ts',
      leakyQueryCode,
      ts.ScriptTarget.Latest,
      true
    );

    let hasViolation = false;
    ts.forEachChild(sourceFile, (node) => {
      if (ts.isClassDeclaration(node)) {
        for (const member of node.members) {
          if (ts.isMethodDeclaration(member)) {
            const text = member.getText(sourceFile);
            if (!text.includes('tenantId') && !text.includes('tenant_id')) {
              hasViolation = true;
            }
          }
        }
      }
    });

    expect(hasViolation).toBe(true);
  });
});
