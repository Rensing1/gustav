import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchGustavMe } from '../lib/auth_forwarding.mjs';

test('a revoked shared session never falls back to another frontend identity', async () => {
  const calls = [];
  const result = await fetchGustavMe('gustav_session=revoked; gustav_bff_session=obsolete', {
    gustavWebInternalBase: 'http://backend', gustavFrontendInternalBase: 'http://frontend',
    fetchWithTimeoutImpl: async (url) => { calls.push(url); return new Response(null, { status: calls.length === 1 ? 401 : 200 }); },
  });
  assert.deepEqual(result, { ok: false, status: 401 });
  assert.deepEqual(calls, ['http://backend/api/me']);
});
