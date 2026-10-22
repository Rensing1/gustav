import { execFileSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';

// A child process gives synchronous parser regressions a real wall-clock limit.
// Vitest's own timeout cannot interrupt a parser blocking its JavaScript thread.
describe('Markdown security under adversarial input', () => {
  it('bounds pathological and large inputs while retaining sanitizer and URL rules', () => {
    const result = execFileSync(process.execPath, ['--input-type=module', '--eval', `
      import assert from 'node:assert/strict';
      import { renderMarkdown, markdownPlainText } from './src/lib/utils/markdown.ts';
      const payloads = [
        '['.repeat(100_000),
        '*_'.repeat(50_000),
        '<script '.repeat(10_000),
        ('# Überschrift\\n\\nText **fett** und [Link](https://example.com)\\n\\n').repeat(2_000),
        '<svg onload=alert(1)><script>alert(1)</script></svg>[X](javascript:alert(1))',
      ];
      for (const source of payloads) {
        const html = renderMarkdown(source);
        assert.equal(typeof markdownPlainText(source), 'string');
        assert.ok(!/<(?:script|svg|iframe)\\b/i.test(html));
        assert.ok(!/href=["'](?:javascript|data):/i.test(html));
      }
      const link = renderMarkdown('[Link](https://example.com)');
      assert.ok(link.includes('target="_blank"'));
      assert.ok(link.includes('rel="noreferrer"'));
      console.log('safe');
    `], { cwd: process.cwd(), timeout: 10_000, encoding: 'utf8', maxBuffer: 64 * 1024 });
    expect(result.trim()).toBe('safe');
  }, 15_000);
});
