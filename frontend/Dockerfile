FROM node:24-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS dev
COPY . .
CMD ["npm", "run", "dev"]

FROM base AS build
ARG VITE_API_URL
ARG VITE_TG_BOT_USERNAME
ENV VITE_API_URL=$VITE_API_URL \
    VITE_TG_BOT_USERNAME=$VITE_TG_BOT_USERNAME
COPY . .
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
