# API Design Standards

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Route Conventions

### URL Structure
```
/api/v1/{resource}              # Collection
/api/v1/{resource}/{id}         # Individual item
/api/v1/{resource}/{id}/{sub}   # Nested resource
```

### Resource Naming
- Plural nouns: `/api/v1/stocks`, `/api/v1/watchlists`
- Lowercase, hyphen-separated: `/api/v1/macro-data`
- No verbs in URLs (use HTTP methods instead)

### HTTP Methods
| Method | Purpose | Example |
|--------|---------|---------|
| GET | Read | `GET /api/v1/stocks/600519` |
| POST | Create / trigger action | `POST /api/v1/analysis/run` |
| PUT | Full update | `PUT /api/v1/watchlists/1` |
| PATCH | Partial update | `PATCH /api/v1/watchlists/1` |
| DELETE | Remove | `DELETE /api/v1/watchlists/1` |

---

## 2. Response Format

### Success Response
```json
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

### Error Response
```json
{
  "code": 2001,
  "data": null,
  "message": "AkShare data source timeout: connection to api.akshare.com timed out after 5s"
}
```

### Error Code Ranges
| Range | Category | Examples |
|-------|----------|---------|
| 0 | Success | — |
| 1xxx | Client error | 1001=invalid parameter, 1002=missing required field, 1003=resource not found |
| 2xxx | Data source error | 2001=source timeout, 2002=source unavailable, 2003=data format error |
| 3xxx | LLM error | 3001=LLM timeout, 3002=LLM rate limited, 3003=invalid LLM response |
| 4xxx | System error | 4001=database error, 4002=config error, 4003=internal error |

---

## 3. Pagination

For list endpoints returning potentially large datasets:

```
GET /api/v1/stocks?page=1&page_size=20

Response:
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  },
  "message": "ok"
}
```

Defaults: `page=1`, `page_size=20`, max `page_size=100`.

---

## 4. Async Operations

For long-running tasks (full analysis, batch processing):

```
POST /api/v1/analysis/run
  Request: { "watchlist_id": 1 }
  Response: { "code": 0, "data": { "task_id": "abc-123" }, "message": "Task started" }

GET /api/v1/analysis/tasks/{task_id}
  Response: { "code": 0, "data": { "status": "running", "progress": 45 }, ... }

GET /api/v1/analysis/tasks/{task_id}/stream
  SSE stream: progress updates in real-time
```

---

## 5. API Documentation

- FastAPI auto-generates OpenAPI spec at `/docs` (Swagger UI)
- All endpoints must have:
  - Pydantic request/response models (auto-documented)
  - Summary and description in the route decorator
  - Example values in Pydantic models (`model_config = {"json_schema_extra": {"examples": [...]}}`)
