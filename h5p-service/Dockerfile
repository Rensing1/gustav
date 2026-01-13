FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci --omit=dev

RUN apk add --no-cache su-exec

COPY server.mjs /app/server.mjs
COPY lib /app/lib
COPY vendor /app/vendor
COPY entrypoint.sh /app/entrypoint.sh

ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["node", "server.mjs"]
