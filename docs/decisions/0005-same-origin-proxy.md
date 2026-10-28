# 0005 — Browser reaches the API through a Next.js same-origin rewrite

**Status:** Accepted · 2026-10-28

## Decision
Next.js rewrites `/api/v1/*` to the FastAPI service. Server Components call FastAPI on the internal URL from `API_INTERNAL_URL` (server-only env).

## Consequences
- No public CORS policy in production; the backend address is not exposed.
- Rate limiting must trust the proxy's `X-Forwarded-For`, configured explicitly.
