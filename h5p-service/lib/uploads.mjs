/** Bound disk uploads and clean their temporary files on every response path.
 * Authentication and CSRF guards remain the responsibility of route composition.
 * Paths come only from this storage engine, never from client-controlled input.
 */
import { randomUUID } from 'node:crypto';
import { unlink } from 'node:fs/promises';
import path from 'node:path';
import multer from 'multer';

const files = Symbol('temporary upload paths');

export function createUploads({ directory, maxBytes }) {
  const parser = multer({
    storage: multer.diskStorage({
      destination: directory,
      filename(req, file, callback) {
        const suffix = String(file.originalname || 'upload.bin').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
        const name = `${randomUUID()}-${suffix}`;
        req[files].add(path.join(directory, name));
        callback(null, name);
      },
    }),
    limits: { fileSize: maxBytes },
  });
  const wrap = middleware => (req, res, next) => {
    req[files] = new Set();
    const cleanup = async () => {
      await Promise.allSettled([...req[files]].map(file => unlink(file)));
    };
    // Keep paths until parsing ends: an abort can race the initial file open.
    res.once('finish', cleanup);
    res.once('close', cleanup);
    req.once('aborted', cleanup);
    middleware(req, res, error => {
      if (error || req.aborted || res.destroyed) void cleanup();
      next(error);
    });
  };
  return {
    uploadImport: { single: field => wrap(parser.single(field)) },
    uploadAjax: wrap(parser.fields([{ name: 'file', maxCount: 1 }, { name: 'h5p', maxCount: 1 }])),
  };
}
