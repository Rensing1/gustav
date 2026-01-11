#!/bin/sh
set -eu

# H5P service entrypoint
#
# Why:
#   The H5P sidecar stores content/libraries on a bind-mounted filesystem
#   (`/data/h5p`). To reduce the blast radius of potential vulnerabilities, we
#   run the Node process as the non-root `node` user.
#
# How:
#   - Start as root (Docker default) so we can ensure the storage directories
#     exist and are writable.
#   - `chown` the storage root to `node:node` (best-effort).
#   - Exec the actual command via `su-exec node:node ...`.

root="${H5P_STORAGE_ROOT:-/data/h5p}"

mkdir -p \
  "${root}" \
  "${root}/libraries" \
  "${root}/content" \
  "${root}/tmp" \
  "${root}/userdata" \
  "${root}/uploads"

if [ "$(id -u)" = "0" ]; then
  # Best-effort: If the bind mount is owned by a different UID/GID, this may
  # fail. In that case the service will fail fast via its own storage probe.
  chown -R node:node "${root}" 2>/dev/null || true
fi

exec su-exec node:node "$@"

