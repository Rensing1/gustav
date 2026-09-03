#!/usr/bin/env bash
set -euo pipefail

build_log="$(mktemp "${TMPDIR:-/tmp}/gustav-frontend-build.XXXXXX")"
trap 'rm -f "${build_log}"' EXIT

./node_modules/.bin/vite build 2>&1 | tee "${build_log}"
node tooling/check-build-output.mjs "${build_log}"
node tooling/check-css-compatibility.mjs .svelte-kit/output/client/_app/immutable/assets
