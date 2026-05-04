# Security Headers

## CORS
- Allowed origins: `https://yourdomain.com`
- Allowed methods: `GET`, `POST`
- Allowed headers: `Authorization`, `Content-Type`
- Exposed headers: `X-Total-Count`

## Rate Limiting
- Authentication endpoint (`/api/auth/login`): 5 attempts per minute

## Security Headers
- **CSP**: `default-src 'self'`
- **HSTS**: `max-age=31536000; includeSubDomains; preload`
- **X-Frame-Options**: `DENY`

## Secrets
- `SECRET_KEY`: Rotated on 2026-05-03. Must be set in environment variables.