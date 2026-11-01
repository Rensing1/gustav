import { test } from 'node:test';
import assert from 'node:assert/strict';
import { diagramConfig, diagramInputError } from './mermaid-policy.mjs';

test('bounds untrusted definitions and denies resource-bearing syntax', () => {
  assert.equal(diagramInputError('sequenceDiagram\nA->>B: https://example.org'), null);
  assert.equal(diagramInputError('x'.repeat(50_001)), 'diagram_too_large');
  for (const source of ['classDef red fill:url(https://example.org)', 'A@{img:"http://example.org"}', String.raw`classDef red fill:u\72l(https://example.org)`, '@import "https://example.org"']) {
    assert.equal(diagramInputError(source), 'invalid_diagram');
  }
});
test('locks every Mermaid configuration key for both output themes', () => {
  for (const theme of ['light', 'dark']) {
    const policy = diagramConfig(theme, ['theme', 'flowchart', 'sequence', 'themeCSS', 'securityLevel']);
    assert.equal(policy.securityLevel, 'strict');
    assert.equal(policy.htmlLabels, false);
    assert.ok(policy.secure.includes('flowchart'));
    assert.ok(policy.secure.includes('themeCSS'));
    assert.ok(policy.secure.includes('secure'));
  }
});
