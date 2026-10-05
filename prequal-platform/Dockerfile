# syntax=docker/dockerfile:1
# Dockerfile for Prequal Platform
# Multi-stage build for Node.js application with optimized caching

# Stage 1: Build
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files first for better layer caching
COPY package*.json package-lock.json* ./

# Install dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Stage 2: Production
FROM node:18-alpine AS production

# Set working directory
WORKDIR /app

# Copy built application from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# Install production dependencies only with cache mount
RUN --mount=type=cache,target=/root/.npm \
    npm ci --only=production

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001
USER nextjs

# Expose port
EXPOSE 3000

# Start application
CMD ["npm", "start"]