# Licensing

## GUSTAV

The GUSTAV source code is licensed under the **GNU Affero General Public License
v3 (AGPL-3.0)**.

- Full license text: `LICENCE.md`

## Third-party components

GUSTAV includes third-party components. Some of them are **vendored into this
repository** (committed to git) and may be under different licenses.

- Vendored assets list + license locations: `THIRD_PARTY_NOTICES.md`

## H5P (GPL) vendored assets — project decision

GUSTAV vendors the H5P core/editor runtime assets in this repository to enable
in-browser authoring and playback via the H5P sidecar (`h5p-service/`).

These H5P assets (and some bundled subcomponents) are licensed under **GPL-3.0**
and other upstream licenses. This is an explicit project decision and is
tracked in `THIRD_PARTY_NOTICES.md` (including the in-repo license text paths).

If you redistribute GUSTAV (as source or as a built deployment artifact), you
also redistribute these vendored assets and must comply with their upstream
license terms. This document is not legal advice; refer to the included license
texts.

## Updating vendored assets

When updating or adding vendored assets:

1. Keep the upstream provenance (project + version/commit) traceable.
2. Ensure the license text is present in the repository (or referenced via an
   existing in-repo license file).
3. Update `THIRD_PARTY_NOTICES.md` accordingly.
