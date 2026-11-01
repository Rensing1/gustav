FROM node:24.22.1-bookworm-slim AS deps
WORKDIR /app
COPY diagram-renderer/package*.json ./
RUN npm ci --omit=dev

# The upstream image supplies a matching browser and its system libraries.
# Pin the digest so a tag change cannot silently change PDF rendering.
FROM ghcr.io/puppeteer/puppeteer:25.16.0@sha256:956a72e3d523c76606efaad23392fbe33950370189f749715222c7427f57392b
USER root
COPY --from=deps /usr/local/bin/node /usr/local/bin/node
ENV PUPPETEER_CACHE_DIR=/home/pptruser/.cache/puppeteer
ENV XDG_CONFIG_HOME=/tmp/config
ENV XDG_CACHE_HOME=/tmp/cache
RUN node -e 'require("puppeteer").executablePath().then(p => require("node:fs").symlinkSync(p, "/usr/local/bin/gustav-chromium"))'
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY diagram-renderer/package.json diagram-renderer/server.mjs ./
COPY diagram-renderer/mermaid-policy.mjs ./
USER 10042
EXPOSE 3001
ENTRYPOINT []
CMD ["node", "server.mjs"]
