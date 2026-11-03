FROM node:24-slim

WORKDIR /srv/frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build
RUN chown -R node /srv/frontend
USER node
EXPOSE 3000
CMD ["npm", "start"]
