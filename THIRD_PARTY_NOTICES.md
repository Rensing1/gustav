# Third-Party Notices (vendored assets)

This file documents third-party components that are **vendored into this
repository** (i.e. committed to git), including their license and where the
license text can be found.

For dependencies installed via package managers (Python/Node), see the
respective lock files (`package-lock.json`, Python deps) and run a license
scanner as part of your release process.

## H5P Core (static runtime assets)

- **Location:** `h5p-service/vendor/h5p/core/`
- **License:** GNU General Public License v3 (GPL-3.0)  
  **License text:** `h5p-service/vendor/h5p/core/LICENSE.txt`
- **Notes:** This is a vendored snapshot of upstream H5P core runtime assets
  (JS/CSS/fonts). When updating, also update this file with provenance info.

### Included subcomponents inside the H5P core snapshot

- **Open Sans fonts**
  - **Location:** `h5p-service/vendor/h5p/core/fonts/open-sans/`
  - **License:** Apache License 2.0  
    **License text:** `h5p-service/vendor/h5p/core/fonts/open-sans/LICENSE-2.0.txt`
- **jQuery 3.5.1**
  - **Location:** `h5p-service/vendor/h5p/core/js/jquery.js`
  - **License:** MIT (see header comment in the file)

## Lumi Education H5P Webcomponents (vendored derivative overrides)

The H5P sidecar serves Lumi Education's webcomponents from `node_modules`, but
we vendor two small override modules (derived from upstream) to keep browser
ESM compatible without a bundler.

- **Upstream package:** `@lumieducation/h5p-webcomponents`
- **Upstream license:** GNU General Public License v3 (GPL-3.0)  
  **License text (at build time):** `h5p-service/node_modules/@lumieducation/h5p-webcomponents/LICENSE`
- **Vendored derivative files:**
  - `h5p-service/vendor/webcomponents/overrides/h5p-utils.js`
  - `h5p-service/vendor/webcomponents/overrides/dom-utils.js`
- **Local change:** only the import paths are adjusted; functional logic stays
  aligned with upstream (see file headers for rationale).

