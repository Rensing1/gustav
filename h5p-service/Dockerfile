FROM node:24.18.0-alpine AS fonts
WORKDIR /fonts
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM node:24.18.0-alpine

WORKDIR /app

COPY h5p-service/package.json h5p-service/package-lock.json /app/
RUN npm ci --omit=dev

RUN apk add --no-cache su-exec

COPY h5p-service/server.mjs /app/server.mjs
COPY h5p-service/lib /app/lib
COPY h5p-service/routes /app/routes
COPY h5p-service/vendor /app/vendor
COPY h5p-service/entrypoint.sh /app/entrypoint.sh
COPY frontend/src/lib/styles/theme-tokens.css /app/vendor/theme/theme-tokens.css
COPY --from=fonts /fonts/node_modules/@fontsource/inter /app/vendor/theme/fonts/inter
COPY --from=fonts /fonts/node_modules/@fontsource/space-grotesk /app/vendor/theme/fonts/space-grotesk

ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["node", "server.mjs"]
