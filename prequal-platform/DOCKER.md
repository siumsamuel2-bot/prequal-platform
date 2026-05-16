# Docker Development Setup

This document describes how to use Docker Compose for local development of the Prequal Platform.

## Quick Start

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v
```

## Services

The development stack includes:

| Service     | Port      | Description                          |
|-------------|-----------|--------------------------------------|
| frontend    | 5173      | React/Vite development server        |
| backend     | 8000      | FastAPI application                  |
| db          | 5432      | PostgreSQL database                  |
| redis       | 6379      | Redis cache                          |

## Hot Reloading

Both frontend and backend support hot reloading during development:

- **Frontend**: Vite dev server automatically reloads on file changes
- **Backend**: Uvicorn with watchfiles monitors Python source files

Volume mounts are configured for:
- `./app` - Backend application code
- `./api` - Backend API code
- `./alembic` - Database migrations
- `./src` - Frontend source (via root mount)

## Accessing Services

Once running, access the services at:

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432 (postgres:postgres@db:5432/prequal)
- **Redis**: localhost:6379

## Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update values as needed (defaults work for local development)

## Database Persistence

Data is stored in a Docker volume (`postgres_data`), so it persists across container restarts. To start fresh:

```bash
docker compose down -v
docker compose up -d
```

## Production Deployment

For production deployments, use:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Backend won't start
- Check logs: `docker compose logs backend`
- Verify database is healthy: `docker compose ps`
- Check DATABASE_URL environment variable

### Frontend can't connect to backend
- Ensure backend is running and healthy
- Check VITE_API_URL in frontend environment
- Verify CORS settings in backend

### Database connection issues
- Ensure db service is healthy: `docker compose ps db`
- Check credentials match in `.env`
- Try: `docker compose down -v` to reset database

## File Structure

```
prequal-platform/
├── docker-compose.yml          # Development configuration
├── docker-compose.prod.yml     # Production configuration
├── docker-compose.staging.yml  # Staging configuration
├── Dockerfile.backend          # Backend image
├── Dockerfile.frontend         # Frontend image
├── .env.example                # Environment template
└── DOCKER.md                   # This file
```
