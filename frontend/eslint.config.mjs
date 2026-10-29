import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsxA11y from "eslint-plugin-jsx-a11y";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // eslint-config-next registers jsx-a11y with a subset of rules; enable the full recommended set.
  {
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // Scrollable table regions must be focusable for keyboard users (axe: scrollable-region-focusable).
      "jsx-a11y/no-noninteractive-tabindex": ["error", { roles: ["tabpanel", "region"], tags: [] }],
    },
  },
  globalIgnores([".next/**", ".next-*/**", "out/**", "build/**", "next-env.d.ts", "playwright-report/**", "test-results/**", "coverage/**"]),
]);

export default eslintConfig;
