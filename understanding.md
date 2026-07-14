# SocialDashboard - Project Understanding

## Project Overview

**SocialDashboard** is a **Multi-Client Social Media Analytics Dashboard** built with **FastAPI**, **PostgreSQL**, **Redis/Celery**, and **AWS KMS**. It aggregates social media posts and engagement metrics from **Facebook**, **Instagram**, and **LinkedIn** for agency clients, using employee OAuth tokens for authentication.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SocialDashboard Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐    │
│  │   FastAPI    │◄────│  PostgreSQL  │     │       Redis          │    │
│  │   (API)      │     │  (Primary DB)│     │   (Celery Broker)    │    │
│  │  Port 8000   │     │  Port 5432   │     │   Port 6379          │    │
│  └──────┬───────┘     └──────────────┘     └──────────┬───────────┘    │
│         │                                              │               │
│         ▼                                              ▼               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │                    Celery Workers                             │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │     │
│  │  │ fb-queue    │  │ ig-queue    │  │ li-queue    │           │     │
│  │  │ (FB Pages)  │  │ (IG Biz)    │  │ (LI Orgs)   │           │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │     │
│  └──────────────────────────────────────────────────────────────┘     │
│         │                                              │               │
│         ▼                                              ▼               │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐     │
│  │  Meta Graph API  │    │ Instagram Graph  │    │ LinkedIn API │     │
│  │  (FB Pages)      │    │ API (IG Biz)     │    │ (Orgs)       │     │
│  └──────────────────┘    └──────────────────┘    └──────────────┘     │
│         │                                              │               │
│         └──────────────────────┬───────────────────────┘               │
│                                ▼                                        │
│                    ┌──────────────────────┐                             │
│                    │      AWS KMS         │                             │
│                    │  (Envelope Encrypt)  │                             │
│                    └──────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **API Framework** | FastAPI 0.110.0 |
| **Database** | PostgreSQL 16 + SQLAlchemy 2.0 (async-ready) |
| **ORM** | SQLAlchemy 2.0 Declarative |
| **Migrations** | Alembic (planned) |
| **Task Queue** | Celery 5.3.6 + Redis 7 |
| **Scheduler** | Celery Beat (cron-style) |
| **HTTP Client** | httpx 0.27.0 (async) |
| **Encryption** | AWS KMS (Envelope Encryption) + AES-GCM |
| **Auth** | OAuth 2.0 (Meta, LinkedIn) + JWT (planned) |
| **Config** | Pydantic Settings v2 |
| **Container** | Docker Compose v3.8 |

---

## Project Structure

```
SocialDashboard/
├── docker-compose.yml          # 5 services: db, redis, api, worker, beat
├── requirements.txt            # Python dependencies
├── app/
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings (env-driven)
│   ├── database.py             # SQLAlchemy engine/session
│   ├── main.py                 # FastAPI app + router registration
│   ├── models.py               # SQLAlchemy models (10 tables)
│   ├── security.py             # TokenVault (KMS + AES-GCM)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── analytics.py        # Read-only analytics endpoints
│   │   ├── oauth.py            # OAuth 2.0 flows (Meta, LinkedIn)
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   └── platforms.py    # Platform API clients (FB, IG, LI)
│   │   └── worker/
│   │       ├── __init__.py
│   │       ├── celery_app.py   # Celery config + beat schedule
│   │       └── tasks.py        # Celery tasks (sync logic)
```

---

## Data Model (SQLAlchemy Models)

### Core Entities

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `clients` | Agency clients | `id` (UUID), `name`, `brand_color`, `is_active` |
| `employees` | Agency staff who connect accounts | `id` (UUID), `email` (unique), `full_name`, `role` (admin/analyst/employee) |
| `employee_oauth_tokens` | Encrypted user OAuth tokens | `employee_id`, `provider` (FB/LI), `enc_access_token`, `enc_refresh_token`, `enc_data_key`, `token_iv`, `scopes` (JSONB), `expires_at`, `refresh_status` |
| `social_pages` | Connected pages/accounts | `employee_id`, `client_id` (nullable), `platform` (FB/IG/LI), `platform_page_id`, `page_name`, `enc_page_access_token`, `page_token_iv`, `ig_business_account_id`, `is_active`, `last_synced_at` |
| `posts` | Social media posts | `page_id` (FK), `platform`, `platform_post_id`, `caption`, `permalink_url`, `media_thumbnail_key`, `created_at`, `raw_response` (JSONB), `is_deleted` |
| `post_metrics` | Engagement snapshots | `post_id`, `snapshot_date`, `likes`, `comments`, `shares` |
| `sync_jobs` | Celery job tracking | `employee_id`, `page_id`, `job_type`, `status`, `started_at`, `finished_at`, `error_payload`, `retry_count` |
| `audit_logs` | Security audit trail | `actor_employee_id`, `action`, `resource_type`, `resource_id`, `metadata` (JSONB), `ip_address`, `created_at` |

### Enums

- `PlatformType`: `facebook`, `instagram`, `linkedin`
- `EmployeeRole`: `admin`, `analyst`, `employee`
- `TokenStatus`: `active`, `expired`, `failed`, `revoked`
- `SyncStatus`: `pending`, `running`, `success`, `failed`, `skipped`
- `SyncJobType`: `discover_pages`, `refresh_token`, `fetch_posts`, `fetch_metrics`

### Security Model (Envelope Encryption)

```
Plaintext Token
      │
      ▼
┌─────────────────────┐
│  Generate DEK       │  (AES-256 via KMS GenerateDataKey)
│  (Data Enc Key)     │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
Encrypt      Encrypt DEK
Token         with KMS
(AES-GCM)       │
    │           ▼
    │    ┌─────────────┐
    │    │  Store in DB│
    │    │ enc_token,  │
    │    │ enc_dek, iv │
    │    └─────────────┘
    │
    ▼
Decrypt: KMS Decrypt DEK → AES-GCM Decrypt token → Zero memory
```

**Storage per token:**
- `enc_access_token` (BYTEA): IV + Ciphertext
- `enc_data_key` (BYTEA): KMS-encrypted DEK
- `token_iv` / `page_token_iv` (BYTEA): 12-byte IV for AES-GCM

---

## API Endpoints

### Health & Discovery
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check (`{"status": "healthy", "version": "1.0"}`) |

### OAuth (Prefix: `/auth`)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/facebook/start` | Returns Facebook OAuth URL with scopes |
| `GET` | `/facebook/callback` | Handles FB callback (code exchange → page discovery) |
| `GET` | `/linkedin/start` | Returns LinkedIn OAuth URL |
| `GET` | `/linkedin/callback` | Handles LI callback |

**FB Scopes Requested:** `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`, `pages_manage_metadata`, `instagram_basic`, `instagram_manage_insights`, `business_management`

### Analytics (Prefix: `/api`, Read-Only)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/clients/{client_id}/posts` | Posts with aggregated metrics for a client (last N days) |

**Query Params:** `days` (default: 7)

**Response:**
```json
{
  "client_id": "uuid",
  "window_days": 7,
  "posts": [
    {
      "id": "uuid",
      "platform": "facebook",
      "caption": "Post text...",
      "url": "https://...",
      "created_at": "2024-01-15T10:30:00Z",
      "metrics": {"likes": 42, "comments": 5, "shares": 3}
    }
  ]
}
```

---

## Background Jobs (Celery)

### Queues
| Queue | Purpose | Tasks |
|-------|---------|-------|
| `fb-queue` | Facebook Page sync | `sync_page_facebook` |
| `ig-queue` | Instagram Business sync | `sync_page_instagram` |
| `li-queue` | LinkedIn Org sync | `sync_page_linkedin` |

### Beat Schedule (Cron)

| Task | Schedule | Purpose |
|------|----------|---------|
| `sync_all_employees` | Hourly (minute 0) | Fan-out to all active employees |
| `discover_all_employees` | Daily 02:30 | Discover new pages/accounts |
| `refresh_expiring_tokens` | Daily 03:00 | Refresh tokens expiring within 7 days |

### Task Flow

```
sync_all_employees (beat)
    │
    ├─► sync_employee(emp_1) ──► sync_page_facebook(page_1) [fb-queue]
    │                              └─► FacebookAPI.fetch_posts()
    │                              └─► Upsert posts + metrics
    │                              └─► Update page.last_synced_at
    │
    ├─► sync_employee(emp_2) ──► sync_page_instagram(page_2) [ig-queue]
    │                              └─► FacebookAPI.fetch_instagram_posts()
    │
    └─► sync_employee(emp_3) ──► sync_page_linkedin(page_3) [li-queue]
                                   └─► LinkedInAPI.fetch_posts() (2-step)
                                   └─► Fetch social actions per post
```

### Retry Policy
- `autoretry_for=(PlatformAPIError, httpx.HTTPStatusError)`
- `retry_backoff=60` (exponential: 60s, 120s, 240s)
- `max_retries=3`
- `retry_jitter=True` (prevents thundering herd)

---

## Platform Integrations

### Facebook Pages (Meta Graph API v19.0)
- **Endpoint:** `GET /{page_id}/posts`
- **Fields:** `id,message,created_time,permalink_url,full_picture,reactions.summary(total_count),comments.summary(total_count),shares`
- **Pagination:** Cursor-based (`paging.next`)
- **Rate Limits:** 429 (rate limit), 613 (BUC cost limit)
- **Max/page:** 100

### Instagram Business (Meta Graph API v19.0)
- **Endpoint:** `GET /{ig_user_id}/media`
- **Auth:** Uses **Facebook Page Access Token** (not IG user token)
- **Fields:** `id,caption,timestamp,media_url,thumbnail_url,permalink,like_count,comments_count,media_type`
- **No share count** (API limitation)
- **Pagination:** Cursor-based

### LinkedIn Organizations (API v2)
- **Endpoint:** `GET /ugcPosts` (offset pagination, max 50/page)
- **Projection:** Complex RESTli projection for nested fields
- **Auth:** `Authorization: Bearer {token}` + `X-Restli-Protocol-Version: 2.0.0`
- **Two-step metrics:**
  1. Fetch posts with `firstPublishedAt`
  2. For each post: `GET /socialActions/{post_urn}` → count by `$type` (Like/Comment/Reshare)
- **Rate Limit:** 429

---

## Security Implementation

### Token Encryption (TokenVault)
```python
# Encrypt
dek_plain, dek_encrypted = kms.generate_data_key(KeySpec='AES_256')
iv = os.urandom(12)
ciphertext = AESGCM(dek_plain).encrypt(iv, token.encode(), None)
del dek_plain  # Zero memory
# Store: (iv + ciphertext), dek_encrypted, iv

# Decrypt
dek_plain = kms.decrypt(CiphertextBlob=dek_encrypted)['Plaintext']
plaintext = AESGCM(dek_plain).decrypt(iv, ciphertext[12:], None).decode()
del dek_plain
```

### OAuth Flow (Facebook)
1. `GET /auth/facebook/start` → Returns auth URL with `state` (CSRF)
2. User authorizes → Facebook redirects to `/auth/facebook/callback?code=...&state=...`
3. Verify `state`
4. Exchange `code` → Short-lived token (1 hr)
5. Exchange → Long-lived token (60 days)
6. `GET /me/accounts` → Discover pages + page tokens
7. For each page: Encrypt page token → Store in `social_pages`
8. Background: `discover_all_employees` finds IG Business accounts linked to FB pages

### Audit Logging
Every sensitive action writes to `audit_logs`:
- `actor_employee_id`, `action`, `resource_type`, `resource_id`
- `metadata` (JSONB): Additional context
- `ip_address`: Client IP
- `created_at`: Timestamp

---

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@localhost:5432/agency` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery |
| `JWT_SECRET_KEY` | `super-secret-rs256-key` | JWT signing (future) |
| `KMS_KEY_ID` | `arn:aws:kms:...` | AWS KMS Key ARN for envelope encryption |
| `FB_APP_ID` | - | Meta App ID |
| `FB_APP_SECRET` | - | Meta App Secret |
| `FB_REDIRECT_URI` | `http://localhost:8000/auth/facebook/callback` | OAuth redirect |
| `LI_CLIENT_ID` | - | LinkedIn Client ID |
| `LI_CLIENT_SECRET` | - | LinkedIn Client Secret |
| `LI_REDIRECT_URI` | `http://localhost:8000/auth/linkedin/callback` | OAuth redirect |

---

## Deployment (Docker Compose)

### Services
```yaml
services:
  db:          # PostgreSQL 16
  redis:       # Redis 7
  api:         # FastAPI + Uvicorn (port 8000)
  worker:      # Celery worker (3 queues)
  beat:        # Celery beat scheduler
```

### Running
```bash
docker-compose up --build
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/

---

## Key Implementation Details

### Field Selection Optimization (Meta)
Both FB and IG API calls use explicit `fields` parameter to:
- Reduce BUC (Billion User Calls) point cost
- Minimize payload size
- Only request needed metrics

### Pagination Handling
| Platform | Type | Implementation |
|----------|------|----------------|
| Facebook | Cursor | Follow `paging.next` URL |
| Instagram | Cursor | Follow `paging.next` URL |
| LinkedIn | Offset | Increment `start` by `count` (50) |

### Memory Safety (Chapter 10.4)
```python
plaintext_token = vault.decrypt(...)
try:
    # Use token
finally:
    del plaintext_token  # Zero out immediately
```

### Error Handling
- Custom `PlatformAPIError` for 429/613/401
- Celery `autoretry_for` with exponential backoff
- Structured error payloads in `sync_jobs.error_payload` (JSONB)

---

## Missing / Incomplete Features

| Feature | Status | Notes |
|---------|--------|-------|
| LinkedIn OAuth callback | ⚠️ Stub only | `/auth/linkedin/callback` not implemented |
| Instagram OAuth flow | ⚠️ Via FB | IG Business accounts discovered via FB pages |
| JWT Authentication | ❌ Not implemented | `JWT_SECRET_KEY` in config but unused |
| Alembic Migrations | ❌ Not configured | Uses `Base.metadata.create_all()` (dev only) |
| Token Refresh Logic | ⚠️ Stub in tasks | `refresh_expiring_tokens` task exists but logic incomplete |
| Page Discovery Background Job | ⚠️ Stub | `discover_all_employees` task not implemented |
| Post Upsert Logic | ⚠️ Placeholder | `sync_page_facebook` has `pass` for DB writes |
| Instagram Sync Task | ❌ Missing | `sync_page_instagram` task not defined |
| LinkedIn Sync Task | ❌ Missing | `sync_page_linkedin` task not defined |
| Pagination for Analytics | ❌ Not implemented | No offset/limit on `/clients/{id}/posts` |
| Rate Limit Handling | ⚠️ Basic | Only raises exception, no backoff/retry in API layer |
| Tests | ❌ None | No test files present |
| Frontend | ❌ None | API-only backend |

---

## Development Workflow

### Local Setup
```bash
# 1. Create venv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install deps
pip install -r requirements.txt

# 3. Start services (Docker)
docker-compose up -d db redis

# 4. Run migrations (when Alembic added)
alembic upgrade head

# 5. Start API
uvicorn app.main:app --reload

# 6. Start worker (separate terminal)
celery -A app.worker.celery_app worker -l info -Q fb-queue,ig-queue,li-queue

# 7. Start beat (separate terminal)
celery -A app.worker.celery_app beat -l info
```

### Environment File (.env)
```env
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/agency
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secure-random-key
KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/abcdef
FB_APP_ID=your-app-id
FB_APP_SECRET=your-app-secret
FB_REDIRECT_URI=http://localhost:8000/auth/facebook/callback
LI_CLIENT_ID=your-li-client-id
LI_CLIENT_SECRET=your-li-client-secret
LI_REDIRECT_URI=http://localhost:8000/auth/linkedin/callback
```

---

## Next Steps / Recommendations

1. **Implement Alembic migrations** - Replace `create_all()` with proper migrations
2. **Complete OAuth flows** - LinkedIn callback, token refresh logic
3. **Implement missing Celery tasks** - `sync_page_instagram`, `sync_page_linkedin`, `discover_all_employees`, `refresh_expiring_tokens`
4. **Add post upsert logic** - ON CONFLICT DO UPDATE for posts + metrics
5. **Add JWT authentication** - Protect API endpoints
6. **Add pagination to analytics** - Limit/offset for large datasets
7. **Implement rate limit handling** - Exponential backoff in platform clients
8. **Add unit/integration tests** - pytest + testcontainers
9. **Add monitoring** - Prometheus metrics, structured logging
10. **Add API versioning** - `/api/v1/` prefix

---

## References

- **Meta Graph API Docs**: https://developers.facebook.com/docs/graph-api
- **Instagram Graph API**: https://developers.facebook.com/docs/instagram-api
- **LinkedIn Marketing API**: https://learn.microsoft.com/en-us/linkedin/marketing/
- **AWS KMS Envelope Encryption**: https://docs.aws.amazon.com/kms/latest/developerguide/envelope-encryption.html
- **Celery Best Practices**: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- **FastAPI Security**: https://fastapi.tiangolo.com/tutorial/security/