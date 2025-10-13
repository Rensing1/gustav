# GUSTAV Auth Service

FastAPI-based authentication service for GUSTAV with HttpOnly cookie session management.

## Architecture Overview

This service provides secure authentication using:
- **HttpOnly Cookies** for XSS-immune session management
- **Supabase SQL Functions** for session storage (SECURITY DEFINER pattern)
- **JWT tokens** from Supabase Auth
- **No Service Role Key needed** - only uses Anon Key

### Key Design Decisions

1. **Supabase instead of Redis**: Pragmatic choice for <1000 users
   - 2-5ms latency vs 0.5ms is acceptable
   - No additional infrastructure needed
   - Unified backup with database
   - Automatic session cleanup via PostgreSQL

2. **Session Management**
   - Max 5 concurrent sessions per user
   - 90-minute sliding window timeout
   - Automatic activity tracking
   - Session fixation prevention
   - Rate limiting (10 sessions/hour per user)

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email/password, sets HttpOnly cookie
- `POST /auth/logout` - Logout and clear session
- `GET /auth/verify` - Verify session for nginx auth_request
- `POST /auth/refresh` - Refresh access token
- `GET /auth/session/info` - Get current session information

### Health Checks
- `GET /health` - Overall service health
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

## Configuration

Required environment variables:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
# SUPABASE_SERVICE_KEY NOT NEEDED! SQL functions handle authentication
JWT_SECRET=your-jwt-secret
COOKIE_DOMAIN=your-domain.com  # Use 'localhost' for development
ENVIRONMENT=development|production
```

## Session Storage Schema

Sessions are stored in the `auth_sessions` table:
```sql
CREATE TABLE auth_sessions (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL,
    user_email TEXT NOT NULL,
    user_role TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);
```

## Development

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
supabase migration up

# Start service
uvicorn app.main:app --reload --port 8000
```

### Testing
```bash
# Run tests
pytest tests/

# With coverage
pytest tests/ --cov=app --cov-report=html
```

## Deployment Options

### Option A: nginx auth_request (Production)
```nginx
location / {
    auth_request /auth/verify;
    auth_request_set $user_id $upstream_http_x_user_id;
    # ... proxy to Streamlit
}

location = /auth/verify {
    internal;
    proxy_pass http://auth:8000/auth/verify;
}
```

### Option B: FastAPI Middleware (Development)
The auth service can also run as middleware within the main FastAPI application.

## Security Features

- HttpOnly cookies (XSS-immune)
- Secure flag (HTTPS only in production)
- SameSite protection (CSRF mitigation)
- Session limits (5 per user)
- Activity timeout (90 minutes)
- IP/User-Agent tracking

## Performance

- In-memory cache with 5-minute TTL
- ~5ms session lookup (PostgreSQL)
- Automatic expired session cleanup
- Connection pooling via Supabase client

## Monitoring

Structured logging with metrics for:
- Login attempts/failures
- Session creation/deletion
- Token refresh success/failure
- Cache hit rates
- Active session count

## Migration from LocalStorage

This service replaces the previous LocalStorage-based session management which had session-bleeding issues. The migration is transparent to users - they will need to log in once after deployment.