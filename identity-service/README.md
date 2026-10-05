# Prequal Identity Service

Authentication and user management microservice for the Prequal platform.

## Overview

This service extracts the authentication and user management functionality from the monolith into a separate microservice as part of Phase 2 of the microservice migration plan.

## Features

- **User Authentication**: JWT-based login with session rotation
- **Session Management**: 15-minute expiry with automatic token rotation
- **Redis-backed Sessions**: Fast session lookup and invalidation
- **User Management**: CRUD operations for users and organizations
- **Rate Limiting**: Login attempt rate limiting
- **Security**: Secure password hashing (PBKDF2-SHA256), security headers

## API Endpoints

### Authentication (`/api/v1/auth`)
- `POST /login` - User login, returns session token and rotation token
- `POST /logout` - Invalidate current session
- `POST /logout-all` - Invalidate all sessions for user
- `POST /session/rotate` - Rotate session token using rotation token

### Users (`/api/v1/users`)
- `POST /` - Create new user
- `GET /` - List users with filters
- `GET /{user_id}` - Get user by ID
- `PATCH /{user_id}` - Update user
- `DELETE /{user_id}` - Delete user

### Organizations (`/api/v1/users/organizations`)
- `POST /` - Create organization
- `GET /` - List organizations
- `GET /{org_id}` - Get organization by ID

## Tech Stack

- **Framework**: FastAPI 0.115
- **Database**: PostgreSQL with SQLAlchemy 2.0
- **Cache**: Redis with redis-py async
- **Authentication**: JWT tokens with rotation
- **Password Hashing**: PBKDF2-SHA256 (29000 rounds)
- **Testing**: pytest with asyncio support

## Project Structure

```
identity-service/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration settings
│   ├── database.py             # Database connection and session management
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py           # SQLAlchemy models (User, UserSession, Organization)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── security.py         # Security utilities (hashing, tokens, Redis sessions)
│   └── api/
│       ├── __init__.py
│       ├── router.py           # API router
│       └── endpoints/
│           ├── __init__.py
│           ├── auth.py         # Authentication endpoints
│           └── users.py        # User management endpoints
├── tests/
│   ├── conftest.py
│   └── test_auth.py            # Authentication tests
├── requirements.txt
├── Dockerfile
└── README.md
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | Auto-constructed from parts |
| `POSTGRES_SERVER` | PostgreSQL host | localhost |
| `POSTGRES_USER` | PostgreSQL user | postgres |
| `POSTGRES_PASSWORD` | PostgreSQL password | **Required** |
| `POSTGRES_DB` | Database name | identity_service |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `REDIS_URL` | Redis connection URL | Auto-constructed from parts |
| `REDIS_HOST` | Redis host | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `REDIS_DB` | Redis database | 0 |
| `REDIS_PASSWORD` | Redis password | (empty) |
| `SESSION_EXPIRY_SECONDS` | Session TTL | 900 (15 min) |
| `CORS_ALLOWED_ORIGINS` | CORS origins | http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173 |

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Docker

```bash
# Build
docker build -t prequal-identity-service .

# Run
docker run -p 8001:8001 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e REDIS_URL=redis://redis:6379/0 \
  prequal-identity-service
```

## Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Health Check

```bash
curl http://localhost:8001/health
# Returns: {"status": "healthy", "service": "prequal-identity-service"}
```

## Migration from Monolith

This service was extracted from the Prequal monolith backend. The following components were adapted:

- `app/api/endpoints/auth.py` → Identity service auth endpoints (with Redis session storage)
- `app/models/models.py` → User, UserSession, Organization models
- `app/schemas/schemas.py` → Auth and user schemas
- `app/services/security.py` → Security utilities + Redis session management

## Dependencies

### Infrastructure (DevOps to provision)
- PostgreSQL database (`identity_service`)
- Redis instance (database 0)

### Networking (DevOps to configure)
- API Gateway (Kong) routing for `/api/v1/auth/*` and `/api/v1/users/*`
- Service discovery for identity-service:8001

## Security Considerations

- All passwords hashed with PBKDF2-SHA256 (29000 rounds)
- Session tokens: 32 bytes URL-safe, 15-minute expiry
- Rotation tokens: 16 bytes URL-safe, single-use
- Rate limiting: 5 login attempts per 5 minutes per IP
- Security headers on all responses
- CORS restricted to configured origins