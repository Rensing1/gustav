/** Run inside the local renderer container against its real Mermaid/Chromium service. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

async function render(sources, maxOutputBytes = 8 * 1024 * 1024) {
  return fetch('http://diagram-renderer:3001/render', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(30_000),
    body: JSON.stringify({
      diagrams: sources.map((source) => ({
        id: createHash('sha256').update(source).digest('hex'), source
      })),
      budget_ms: 20_000, max_output_bytes: maxOutputBytes
    })
  });
}

test('keeps render-time content errors between valid diagrams local', async () => {
  const response = await render([
    'flowchart LR\nA-->B',
    'sankey-beta\nA,B,1\nB,A,1',
    'sequenceDiagram\nA->>B: Hello'
  ]);
  assert.equal(response.status, 200);
  const { diagrams } = await response.json();
  assert.equal(diagrams.length, 3);
  assert.deepEqual(Object.keys(diagrams[1]).sort(), ['error', 'id']);
  assert.equal(diagrams[1].error, 'invalid_diagram');
  for (const index of [0, 2]) {
    assert.equal(Buffer.from(diagrams[index].png, 'base64').subarray(1, 4).toString(), 'PNG');
  }
});

test('reports a breached output budget as a stable 413', async () => {
  const response = await render(['flowchart LR\nA-->B'], 1);
  assert.equal(response.status, 413);
  assert.deepEqual(await response.json(), { error: 'output_too_large' });
  assert.equal(response.headers.get('cache-control'), 'no-store');
});
