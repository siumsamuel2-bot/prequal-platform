# Prequal Platform

Subcontractor compliance tracking platform for mid-market general contractors.

## Quick Start

### Development

```bash
cd prequal-platform
docker compose up --build
```

### Staging Deployment

```bash
cd prequal-platform
cp .env.staging.example .env
# Edit .env with your secrets
docker compose -f docker-compose.staging.yml --env-file .env up --build
```

## Documentation

- [Deployment Guide](prequal-platform/DEPLOYMENT.md) - Full staging deployment instructions
- [Production Deployment Runbook](prequal-platform/PRODUCTION_DEPLOYMENT.md) - Production deployment and operations
- [Architecture](prequal-platform/ARCHITECTURE.md) - Production architecture overview
- [API Documentation](prequal-platform/docs/) - API reference
- [Database Schema](database/README.md) - Database documentation
- [Monitoring Guide](prequal-platform/MONITORING.md) - Monitoring and alerting setup

## Architecture

```
Frontend (React/Vite) :3000
       ↓
Backend (FastAPI) :8000
       ↓
┌──────┼──────┐
│      │      │
PostgreSQL Redis PGAdmin
:5432   :6379  :5050
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React SPA |
| Backend | 8000 | FastAPI API |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache/sessions |
| PGAdmin | 5050 | Database UI (staging only) |

## Environment Variables

See [prequal-platform/.env.staging.example](prequal-platform/.env.staging.example) for required variables.

## Development

```bash
# Backend
cd prequal-platform
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend
cd prequal-platform
npm install
npm run dev
```

## Testing

```bash
# Backend tests
cd prequal-platform
pytest

# Frontend tests
cd prequal-platform
npm test
```

## Project Structure

```
├── prequal-platform/      # Main application
│   ├── api/               # FastAPI backend
│   ├── app/               # Application code
│   ├── database/          # Database layer
│   ├── tests/             # Test suite
│   └── docs/              # Documentation
├── database/              # Database schemas and seeds
├── docs/                  # Project documentation
└── terraform/             # Infrastructure as code
```

## License

Proprietary - Prequal Platform
