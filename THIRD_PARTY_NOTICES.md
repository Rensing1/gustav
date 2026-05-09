# Third-Party Notices (vendored assets)

This file documents third-party components that are **vendored into this
repository** (i.e. committed to git), including their license and where the
license text can be found.

For dependencies installed via package managers (Python/Node), see the
respective lock files (`package-lock.json`, Python deps) and run a license
scanner as part of your release process.

## H5P Core (static runtime assets)

- **Location:** `h5p-service/vendor/h5p/core/`
- **Upstream:** `https://github.com/h5p/h5p-php-library`
- **Revision:** `1.27.0` (tag)
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

## H5P Editor (static editor assets)

- **Location:** `h5p-service/vendor/h5p/editor/`
- **Upstream:** `https://github.com/h5p/h5p-editor-php-library`  
  **Revision:** `80b3b281ee9d064b563f242e8ee7a0026b5bf205` (2024-09-06, "Build CSS")
- **License:** GNU General Public License v3 (GPL-3.0, per upstream `composer.json`)  
  **License text:** `h5p-service/vendor/h5p/core/LICENSE.txt`
- **Notes:** This is a vendored snapshot of upstream H5P editor assets
  (JS/CSS/images/CKEditor build) served by the H5P sidecar.

### Included subcomponents inside the H5P editor snapshot

- **CKEditor 5 (custom build)**
  - **Location:** `h5p-service/vendor/h5p/editor/ckeditor/`
  - **License:** see upstream license file (copied into this repo)  
    **License text:** `h5p-service/vendor/h5p/editor/ckeditor/LICENSE.md`
- **Zebra Datepicker 1.9.11**
  - **Location:** `h5p-service/vendor/h5p/editor/libs/zebra_datepicker.min.js`
  - **License:** GNU Lesser General Public License v3 (LGPL-3.0)  
    **License text:** `h5p-service/vendor/h5p/editor/libs/zebra_datepicker.LICENSE.md`
- **h5p-image-cropper**
  - **Location:** `h5p-service/vendor/h5p/editor/libs/cropper.js`
  - **License:** MIT  
    **License text:** `h5p-service/vendor/h5p/editor/libs/h5p-image-cropper.LICENSE.txt`

## Lumi Education H5P Webcomponents (vendored derivative overrides)

The H5P sidecar uses Lumi Education's webcomponents (installed via npm at build
time), but we vendor two small override modules (derived from upstream) to keep
browser ESM compatible without a bundler.

- **Upstream package:** `@lumieducation/h5p-webcomponents`
- **Upstream license:** GNU General Public License v3 or later (GPL-3.0-or-later)  
  **License text:** `h5p-service/vendor/h5p/core/LICENSE.txt`
- **Vendored derivative files:**
  - `h5p-service/vendor/webcomponents/overrides/h5p-utils.js`
  - `h5p-service/vendor/webcomponents/overrides/dom-utils.js`
- **Local change:** only the import paths are adjusted; functional logic stays
  aligned with upstream (see file headers for rationale).

## Filius official example fixtures

- **Location:** `backend/tests/fixtures/filius/filius-official-*/`
- **Upstream:** `https://gitlab.com/filius1/filius`
- **Revision:** `dcd965f6139baef4c27cc6d3cc34106f6bebda40` (`version 2.10.1`)
- **License:** GNU General Public License v3 (GPL-3.0)
- **License text:** `LICENCE.md` section 13 covers GPLv3 compatibility via
  AGPLv3; upstream GPLv3 text is linked in each fixture `ATTRIBUTION.md`.
- **Notes:** The `.fls` files are unchanged upstream example projects used as
  parser/evidence test fixtures. Each fixture directory contains its own
  `ATTRIBUTION.md` with the original source path and pinned commit.

## inf-schule Filius example fixtures

- **Location:** `backend/tests/fixtures/filius/inf-schule-*/`
- **Upstream:** `https://inf-schule.de/rechnernetze/filius`
- **License:** Creative Commons Attribution-ShareAlike 4.0 International
  (CC BY-SA 4.0)
- **Notes:** The `.fls` files are unchanged inf-schule example projects used as
  parser/evidence test fixtures. Each fixture directory contains its own
  `ATTRIBUTION.md` with the source URL, context page, license link, and
  attribution details.

## How to update vendored assets (checklist)

When updating anything listed in this file:

1) Identify the upstream source (URL) and pin a specific revision (tag/commit).
2) Replace the vendored files under the documented `Location` path(s).
3) Verify license files are present and still apply (and add missing notices for bundled subcomponents).
4) Update the `Upstream`/`Revision` fields above (and add new entries when new vendored files appear).
5) Run local verification:
   - Rebuild affected services (e.g. `docker compose build h5p-service`).
   - Run the relevant contract tests (`.venv/bin/pytest -q backend/tests/test_h5p_* backend/tests/test_openapi_h5p_*`).
