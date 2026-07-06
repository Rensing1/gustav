import path from "node:path";

import express from "express";


export function mountPublicStaticAssets(app) {
  // Public browser runtime assets.
  //
  // These files must stay reachable without a session cookie because the
  // browser needs them before the authenticated H5P model endpoints can render
  // any visible editor/player UI.

  // Overrides for Lumi webcomponents to keep browser ESM compatible without a bundler.
  // These files remove bare imports like `deepmerge` and `await-lock`.
  app.use(
    "/webcomponents",
    express.static(path.join("/app", "vendor", "webcomponents", "overrides"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned -> always revalidate (prevents stale JS after redeploys).
      maxAge: 0,
      extensions: ["js"],
    }),
  );

  // Serve Lumi web components (ES modules).
  app.use(
    "/webcomponents",
    express.static(
      path.join("/app", "node_modules", "@lumieducation", "h5p-webcomponents", "build", "es2015"),
      // Note: Lumi's ES2015 build uses extensionless relative imports like
      // `import ... from './h5p-editor'`. Browsers do not auto-append `.js`,
      // so we enable a `.js` fallback to make those imports resolve.
      // Not versioned -> always revalidate (prevents stale JS after redeploys).
      { cacheControl: true, etag: true, lastModified: true, maxAge: 0, extensions: ["js"] },
    ),
  );

  // Global H5P theme overrides (Option B).
  app.use(
    "/theme",
    express.static(path.join("/app", "vendor", "theme"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned -> always revalidate (prevents stale CSS after redeploys).
      maxAge: 0,
      extensions: ["css"],
    }),
  );

  // Vendor shims required by the webcomponents when used directly in a browser
  // (without a bundler). The upstream build has bare imports like `deepmerge`
  // and `await-lock`, which must be resolved via an import map.
  app.use(
    "/webcomponents/vendor",
    express.static(path.join("/app", "vendor", "webcomponents"), {
      cacheControl: true,
      etag: true,
      lastModified: true,
      // Not versioned -> always revalidate (prevents stale JS after redeploys).
      maxAge: 0,
    }),
  );
}
