FROM node:20-alpine

WORKDIR /app

# Phase-0 spike: no external dependencies yet (keeps build deterministic).
COPY server.mjs /app/server.mjs

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.mjs"]
