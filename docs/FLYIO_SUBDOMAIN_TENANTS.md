# Fly.io Subdomain-Based Multi-Tenant Routing

## Overview

This document explains how to implement subdomain-based tenant routing on Fly.io with vendor/customer segregation.

## Architecture

### Subdomain Structure

```
acme.permetrix.fly.dev      → Acme Corporation (customer tenant)
globex.permetrix.fly.dev    → Globex Industries (customer tenant)
vendor.permetrix.fly.dev    → Vendor Portal (Vector, Greenhills, etc.)
permetrix.fly.dev           → Main landing page
```

### Tenant Isolation

- **Customer Tenants**: Each customer gets their own subdomain with isolated data
- **Vendor Portal**: Vendors can see all customers and provision licenses
- **Data Segregation**: All database queries are scoped by `tenant_id`

## Implementation

### 1. Middleware for Subdomain Extraction

The middleware extracts the tenant from the `Host` header:

```python
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    parts = host.split(".")
    
    # Extract subdomain (first part before first dot)
    if len(parts) >= 3:  # subdomain.domain.tld
        subdomain = parts[0]
    else:
        subdomain = None
    
    # Determine context
    if subdomain == "vendor":
        request.state.context = "vendor"
        request.state.tenant_id = None
    elif subdomain:
        # Check if subdomain is a valid tenant
        request.state.context = "tenant"
        request.state.tenant_id = subdomain
    else:
        request.state.context = "main"
        request.state.tenant_id = None
    
    response = await call_next(request)
    return response
```

### 2. Database Schema

```sql
-- Tenants (customers)
CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,           -- e.g., "acme", "globex"
    company_name TEXT NOT NULL,           -- "Acme Corporation"
    domain TEXT,                          -- "acme.permetrix.fly.dev"
    crm_id TEXT UNIQUE,                   -- Vendor's CRM reference
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- Vendors
CREATE TABLE vendors (
    vendor_id TEXT PRIMARY KEY,           -- e.g., "vector", "greenhills"
    vendor_name TEXT NOT NULL,            -- "Vector Informatik GmbH"
    contact_email TEXT,
    created_at TEXT NOT NULL
);

-- License packages (vendor provisions to tenant)
CREATE TABLE license_packages (
    package_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    crm_opportunity_id TEXT,
    status TEXT DEFAULT 'active',
    provisioned_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY(vendor_id) REFERENCES vendors(vendor_id)
);

-- Licenses (scoped by tenant)
CREATE TABLE licenses (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,              -- ISOLATION KEY
    package_id TEXT,
    tool TEXT NOT NULL,
    total INTEGER NOT NULL,
    borrowed INTEGER NOT NULL DEFAULT 0,
    commit_qty INTEGER DEFAULT 0,
    max_overage INTEGER DEFAULT 0,
    commit_price REAL DEFAULT 0.0,
    overage_price_per_license REAL DEFAULT 0.0,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(tenant_id, tool)
);

-- Borrows (scoped by tenant)
CREATE TABLE borrows (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,              -- ISOLATION KEY
    license_id TEXT,
    tool TEXT NOT NULL,
    user TEXT NOT NULL,
    borrowed_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
);

-- API Keys (scoped by tenant)
CREATE TABLE api_keys (
    key_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,              -- ISOLATION KEY
    key_hash TEXT NOT NULL,
    name TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
);
```

### 3. Route Handlers with Tenant Context

```python
@app.get("/licenses/status")
async def get_status(request: Request):
    """Get license status - scoped to current tenant"""
    if request.state.context != "tenant":
        raise HTTPException(403, "Tenant context required")
    
    tenant_id = request.state.tenant_id
    # All queries automatically scoped to tenant_id
    return get_tenant_licenses(tenant_id)

@app.get("/api/vendor/customers")
async def get_vendor_customers(request: Request):
    """Get all customers - vendor portal only"""
    if request.state.context != "vendor":
        raise HTTPException(403, "Vendor context required")
    
    return get_all_tenants()
```

### 4. Vendor/Customer Segregation

**Vendor Portal** (`vendor.permetrix.fly.dev`):
- View all customers
- Provision licenses to customers
- Configure budgets per customer
- See customer activity

**Customer Tenant** (`acme.permetrix.fly.dev`):
- See only their own licenses
- Borrow/return licenses
- Configure their own budget restrictions
- Generate API keys for their tenant

## Fly.io Configuration

### 1. Update `fly.toml`

```toml
app = "permetrix"
primary_region = "iad"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

[[services]]
  protocol = "tcp"
  internal_port = 8000

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    grace_period = "5s"
    method = "GET"
    path = "/health"
```

### 2. Add Subdomains to Fly.io

```bash
# Add subdomain for customer tenant
flyctl certs add acme.permetrix.fly.dev

# Add subdomain for vendor portal
flyctl certs add vendor.permetrix.fly.dev

# List all certificates
flyctl certs list
```

### 3. DNS Configuration

For each subdomain, add a CNAME record:

```
acme.permetrix.fly.dev    CNAME    permetrix.fly.dev
globex.permetrix.fly.dev  CNAME    permetrix.fly.dev
vendor.permetrix.fly.dev  CNAME    permetrix.fly.dev
```

Or use Fly.io's automatic DNS:

```bash
# Fly.io automatically creates DNS entries for *.permetrix.fly.dev
# Just add the certificates above
```

## Testing Locally

### Using `/etc/hosts` (macOS/Linux)

```bash
# Add to /etc/hosts
127.0.0.1 acme.localhost
127.0.0.1 globex.localhost
127.0.0.1 vendor.localhost
```

Then access:
- `http://acme.localhost:8000`
- `http://globex.localhost:8000`
- `http://vendor.localhost:8000`

### Using `localhost.run` or `ngrok` for Testing

```bash
# Expose local server
ngrok http 8000

# Access via ngrok subdomain
# https://abc123.ngrok.io → main
# Use custom domains: acme.abc123.ngrok.io
```

## Security Considerations

### 1. Tenant Isolation

- **Always** scope queries by `tenant_id`
- Never trust client-provided tenant IDs
- Extract tenant from subdomain only

### 2. API Key Validation

```python
def validate_api_key(api_key: str, tenant_id: str) -> bool:
    """Validate API key belongs to tenant"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT key_id FROM api_keys
            WHERE tenant_id = ? AND key_hash = ?
        """, (tenant_id, hash_api_key(api_key)))
        return cur.fetchone() is not None
```

### 3. Vendor Authentication

Vendors should authenticate via:
- API keys (stored in `vendors` table)
- Session-based auth for web portal
- OAuth2 for programmatic access

## Example Flow

### 1. Vendor Provisions License

```
POST vendor.permetrix.fly.dev/api/vendor/provision
{
  "tenant_id": "acme",
  "product_id": "davinci-se",
  "product_name": "DaVinci Configurator SE",
  "total": 20,
  "commit_qty": 5,
  "max_overage": 15,
  "crm_opportunity_id": "CRM-ACME-001"
}
```

### 2. Customer Uses License

```
GET acme.permetrix.fly.dev/licenses/status
Authorization: Bearer <acme-api-key>

Response:
{
  "licenses": [
    {
      "tool": "DaVinci Configurator SE",
      "total": 20,
      "borrowed": 3,
      "available": 17
    }
  ]
}
```

### 3. Customer Borrows License

```
POST acme.permetrix.fly.dev/licenses/borrow
Authorization: Bearer <acme-api-key>
X-Signature: <hmac-signature>
X-Timestamp: <timestamp>

{
  "tool": "DaVinci Configurator SE",
  "user": "developer@acme.com"
}
```

## Migration Path

1. **Phase 1**: Add middleware, keep single-tenant mode
2. **Phase 2**: Add multi-tenant tables, migrate data
3. **Phase 3**: Enable subdomain routing
4. **Phase 4**: Migrate customers to subdomains

## Monitoring

Track tenant usage:

```python
# Prometheus metrics with tenant label
borrow_attempts = Counter(
    "license_borrow_attempts_total",
    "Total borrow attempts",
    ["tenant_id", "tool", "user"]
)
```

## Troubleshooting

### Subdomain Not Working

1. Check DNS: `dig acme.permetrix.fly.dev`
2. Check certificate: `flyctl certs list`
3. Check middleware logs: `flyctl logs`

### Tenant Isolation Issues

1. Verify all queries include `WHERE tenant_id = ?`
2. Check middleware sets `request.state.tenant_id`
3. Audit API endpoints for tenant scoping

