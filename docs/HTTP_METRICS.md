# HTTP Metrics Tracking

## Where Metrics Are Fired

### 1. **Middleware (lines 48-73 in `app/main.py`)**
   - **Location**: `track_http_responses` middleware
   - **When**: Every HTTP request/response cycle
   - **What it tracks**:
     - `license_http_requests_total{route, method, status_code}` - All HTTP responses
     - `license_http_500_total{route}` - Only 500 errors (for backward compatibility)

### 2. **Normal Responses (lines 57-63)**
   - After `call_next(request)` completes successfully
   - Tracks the response status code (200, 404, 500, etc.)
   - Example: `GET /dashboard` → `status_code="200"`

### 3. **Exception Handling (lines 66-73)**
   - Catches unhandled exceptions (become 500s)
   - Tracks both `http_requests_total` and `http_500_total`
   - Example: `/faulty` endpoint raises exception → tracked as 500

## Available Metrics

### `license_http_requests_total`
- **Labels**: `route` (e.g., "/dashboard"), `method` (GET, POST), `status_code` ("200", "404", "500")
- **Type**: Counter
- **Use**: Track all HTTP traffic by route and status

### `license_http_500_total`
- **Labels**: `route`
- **Type**: Counter  
- **Use**: Quick 500 error tracking and alerting

## Prometheus Queries

### All 500s by route
```promql
sum by (route) (rate(license_http_500_total[1m]))
```

### All status codes by route
```promql
sum by (route, status_code) (rate(license_http_requests_total[1m]))
```

### Success rate (2xx)
```promql
sum(rate(license_http_requests_total{status_code=~"2.."}[1m])) / sum(rate(license_http_requests_total[1m]))
```

### Error rate (4xx + 5xx)
```promql
sum(rate(license_http_requests_total{status_code=~"[45].."}[1m])) / sum(rate(license_http_requests_total[1m]))
```

### 500s in last minute
```promql
sum(increase(license_http_500_total[1m]))
```

