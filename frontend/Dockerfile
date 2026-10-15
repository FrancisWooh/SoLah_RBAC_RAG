FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# VITE_* values are baked into the JS at build time. Empty = same-origin
# relative URLs (/api/...), which nginx proxies to the backend.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Production bundles for `npm run preview` (user site and admin site).
# The dev compose files bind-mount ./frontend over /app and run `npm run dev`,
# so these are only used by docker-compose.prod.yml.
RUN npm run build && npx vite build --mode admin --outDir dist-admin

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
