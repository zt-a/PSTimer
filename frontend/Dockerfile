# build stage
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# SPA fallback + API/WS proxy to the backend service
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
