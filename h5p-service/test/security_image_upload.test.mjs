import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { H5PEditor } from '@lumieducation/h5p-server';

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64');
for (const fromFile of [false, true]) test(`real Lumi image upload from ${fromFile?'file':'bytes'}`, async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'gustav-image-'));
  try {
    const filename = path.join(directory,'image.png'); await writeFile(filename,png);
    const editor = Object.assign(Object.create(H5PEditor.prototype), {
      malwareScanners:[], fileSanitizers:[], config:{contentWhitelist:'png'},
      temporaryFileManager:{addFile:async (name,stream)=>{for await(const chunk of stream) assert.ok(chunk.length);return name;}},
    });
    const result = await editor.saveContentFile(undefined, {type:'image'},
      {name:'image.png',mimetype:'image/png',...(fromFile?{tempFilePath:filename}:{data:png})}, {id:'synthetic'});
    assert.equal(result.width,1); assert.equal(result.height,1);
    await assert.rejects(editor.saveContentFile(undefined,{type:'image'}, {name:'bad.png',mimetype:'image/png',data:Buffer.from('invalid')},{id:'synthetic'}));
  } finally { await rm(directory,{recursive:true,force:true}); }
});
