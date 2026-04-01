# Build stage
FROM node:20-slim AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Build the app
RUN npm run build

# Stage 2: Serve with Nginx for production-style build
# (We will use a separate Nginx container in docker-compose,
#  but this Dockerfile handles the static file generation)
FROM busybox:latest
COPY --from=build /app/dist /dist
CMD ["cp", "-rv", "/dist/.", "/app-dist/"]
