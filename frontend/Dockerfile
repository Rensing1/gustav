FROM node:24.18.0-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

FROM node:24.18.0-alpine AS build

WORKDIR /app

RUN apk add --no-cache bash

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24.18.0-alpine AS runtime-deps

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

FROM node:24.18.0-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
COPY --from=runtime-deps /app/node_modules ./node_modules

EXPOSE 3000

# Start the adapter-node bundle via `node build`.
CMD ["node", "build"]
