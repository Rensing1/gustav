FROM node:20-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

FROM node:20-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules

EXPOSE 3000

# Start the adapter-node bundle via `node build`.
CMD ["node", "build"]
