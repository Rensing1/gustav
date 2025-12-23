FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci --omit=dev

COPY server.mjs /app/server.mjs
COPY vendor /app/vendor

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.mjs"]
