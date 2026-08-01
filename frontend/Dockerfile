# =============================================================================
# ADs Growth System - Frontend Dockerfile
# =============================================================================

# Development stage
FROM node:26-alpine AS development

WORKDIR /app

# Copy package files (.npmrc carries legacy-peer-deps for @tremor/react vs react 19)
COPY package*.json .npmrc ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =============================================================================
# Production build stage
# =============================================================================
FROM node:26-alpine AS build

WORKDIR /app

# VITE_* args must match what the frontend code reads via import.meta.env
# (VITE_API_URL includes the /api/v1 path; VITE_WS_URL includes the /ws path)
ARG VITE_API_URL=https://api.stratumai.app/api/v1
ENV VITE_API_URL=$VITE_API_URL
ARG VITE_WS_URL=
ENV VITE_WS_URL=$VITE_WS_URL
ARG VITE_SENTRY_DSN=
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .
RUN npm run build

# Production stage - Nginx serves static files
FROM nginx:alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Railway assigns dynamic PORT; nginx:alpine uses envsubst on templates
ENV PORT=80

EXPOSE ${PORT}

CMD ["nginx", "-g", "daemon off;"]
