import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import importPlugin from 'eslint-plugin-import-x';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: {
      'import-x': importPlugin
    },
    languageOptions: {
      parserOptions: {
        projectService: {
          allowDefaultProject: ['*.ts']
        },
        tsconfigRootDir: import.meta.dirname
      }
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { 'argsIgnorePattern': '^_', 'varsIgnorePattern': '^_' }
      ],
      'no-console': ['warn', { 'allow': ['warn', 'error', 'info'] }]
    }
  },
  // Boundary rules
  {
    files: ['packages/types/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@salesops/core*', '@salesops/web*', 'apps/*', 'next*', 'react*', 'stripe*'],
              message: 'packages/types is a frozen contract and must have zero runtime dependencies beyond zod.'
            }
          ]
        }
      ]
    }
  },
  {
    files: ['packages/core/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@salesops/web*', 'apps/*', 'next*', 'react*', 'stripe*'],
              message: 'packages/core must remain transport-agnostic and cannot import web/UI/framework modules.'
            }
          ]
        }
      ]
    }
  },
  {
    files: ['adapters/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@salesops/core*', '@salesops/web*', 'apps/*'],
              message: 'Adapters must depend only on @salesops/types.'
            }
          ]
        }
      ]
    }
  },
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/coverage/**',
      '**/Zars_PoC/**',
      '**/*.d.ts',
      '**/*.js',
      '**/*.mjs'
    ]
  }
);
