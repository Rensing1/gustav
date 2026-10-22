import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import http from 'node:http';
import test from 'node:test';
import express from 'express';
import { createUploads } from '../lib/uploads.mjs';
import { getPublicOrigin } from '../lib/runtime_guards.mjs';

async function fixture(run) {
  const directory = await mkdtemp(path.join(tmpdir(), 'gustav-upload-'));
  const app = express();
  const { uploadImport } = createUploads({ directory, maxBytes: 1024 });
  app.post('/upload', (req, res, next) => req.get('x-test-authorized') === 'yes' ? next() : res.sendStatus(403),
    uploadImport.single('file'), (req, res) => res.sendStatus(req.query.fail ? 400 : 201));
  app.use((error, req, res, next) => res.status(error.code === 'LIMIT_FILE_SIZE' ? 413 : 400).end());
  const server = app.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  const empty = async () => {
    for (let i=0;i<100;i++) {
      if ((await readdir(directory)).length === 0) return;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.deepEqual(await readdir(directory), []);
  };
  try { await run({ base, directory, empty }); }
  finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await rm(directory, { recursive:true,force:true }); }
}

for (const [name, size, authorized, suffix, status] of [
  ['success',1024,true,'',201], ['early rejection',100,true,'?fail=1',400],
  ['limit',1025,true,'',413], ['unauthorized',100,false,'',403],
]) test(`upload ${name} leaves no temporary file`, () => fixture(async ({ base, empty }) => {
  const body = new FormData(); body.set('file', new Blob([new Uint8Array(size)]), 'image.png');
  const result = await fetch(base+'/upload'+suffix, { method:'POST', headers:{'x-test-authorized':authorized?'yes':'no'}, body });
  assert.equal(result.status,status); await empty();
}));

test('an interrupted multipart stream is cleaned up', () => fixture(async ({base, directory, empty}) => {
  const request = http.request(base+'/upload', {method:'POST', headers:{'x-test-authorized':'yes', 'content-type':'multipart/form-data; boundary=gustav'}});
  request.on('error', () => {});
  request.write('--gustav\r\nContent-Disposition: form-data; name="file"; filename="partial.png"\r\nContent-Type: image/png\r\n\r\npartial');
  for(let i=0;i<100 && !(await readdir(directory)).length;i++) await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal((await readdir(directory)).length,1);
  request.destroy(); await empty();
}));

test('untrusted forwarded headers cannot replace the public origin', () => {
  const req = { protocol:'http', socket:{remoteAddress:'127.0.0.1'}, app:{get:()=>()=>false},
    get:name=>({'host':'app.example','x-forwarded-proto':'https','x-forwarded-host':'evil.example'})[name] };
  assert.equal(getPublicOrigin(req),'http://app.example');
});
