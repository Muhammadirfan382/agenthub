import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig([
  globalIgnores(['dist', 'coverage', 'node_modules']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: 'Rendering raw HTML is not allowed. Render text, or sanitize in a dedicated component.',
        },
      ],
      // Demo data may only be consumed by the demo service implementations.
      // Components must go through the service layer so Phase 2 can swap in
      // real API services without touching UI code.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/features/demo', '@/features/demo/*', '**/features/demo/*'],
              message: 'Import demo data only from src/services/demo. UI code must use the service layer.',
            },
          ],
        },
      ],
    },
  },
  {
    // The only places allowed to read demo data directly.
    files: ['src/services/demo/**/*.{ts,tsx}', 'src/features/demo/**/*.{ts,tsx}', 'src/**/*.test.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    rules: { 'no-restricted-imports': 'off' },
  },
  {
    // Test helpers and the route table export non-component values by design.
    files: ['src/test/**/*.{ts,tsx}', 'src/**/*.test.{ts,tsx}', 'src/app/routes.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
]);
