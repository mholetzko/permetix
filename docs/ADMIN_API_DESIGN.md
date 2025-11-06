# Admin API Design

## Overview

The Admin API is a special API endpoint that allows you (as the Permetrix owner) to manage the platform without SSH access. It provides secure, programmatic access to onboarding and management operations.

---

## 🔐 Authentication & Authorization

### Admin API Key

**Concept**: A special API key that grants platform-wide admin privileges.

**Storage**:
- Stored as environment variable: `PERMETRIX_ADMIN_API_KEY`
- Set in Fly.io secrets: `flyctl secrets set PERMETRIX_ADMIN_API_KEY=admin_live_...`
- Never exposed to customers or vendors

**Generation**:
```python
import secrets
import string

def generate_admin_api_key():
    """Generate a secure admin API key"""
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) 
                          for _ in range(32))
    return f"admin_live_{random_part}"

# Example: admin_live_aB3xY9mN2pQ7rT5vW8zC1dF4gH6jK0lM
```

### Authorization Middleware

```python
from fastapi import HTTPException, Request
from functools import wraps

def require_admin(request: Request):
    """Check if request has valid admin API key"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    provided_key = auth_header.replace("Bearer ", "")
    admin_key = os.getenv("PERMETRIX_ADMIN_API_KEY")
    
    if not admin_key:
        raise HTTPException(500, "Admin API not configured")
    
    if provided_key != admin_key:
        raise HTTPException(403, "Invalid admin API key")
    
    return True

# Usage in endpoints
@app.post("/api/admin/tenants")
async def create_tenant(request: Request, ...):
    require_admin(request)  # Check admin access
    # ... create tenant logic
```

---

## 📡 API Endpoints

### Customer Management

#### Create Customer Tenant

```http
POST /api/admin/tenants
Authorization: Bearer admin_live_...
Content-Type: application/json

{
  "company_name": "Acme Corporation",
  "contact_email": "admin@acme.com",
  "tenant_id": "acme",  // Optional, auto-generated if not provided
  "crm_id": "CRM-ACME-001",  // Optional
  "company_domain": "acme.com"  // Optional
}
```

**Response**:
```json
{
  "tenant_id": "acme",
  "company_name": "Acme Corporation",
  "domain": "acme.permetrix.fly.dev",
  "status": "active",
  "admin_user_id": "user_abc123",
  "setup_token": "setup_xyz789",  // For password setup
  "created_at": "2025-11-06T10:00:00Z"
}
```

#### List All Tenants

```http
GET /api/admin/tenants
Authorization: Bearer admin_live_...
```

**Response**:
```json
{
  "tenants": [
    {
      "tenant_id": "acme",
      "company_name": "Acme Corporation",
      "domain": "acme.permetrix.fly.dev",
      "status": "active",
      "created_at": "2025-11-06T10:00:00Z",
      "admin_email": "admin@acme.com"
    }
  ]
}
```

#### Get Tenant Details

```http
GET /api/admin/tenants/{tenant_id}
Authorization: Bearer admin_live_...
```

#### Update Tenant Status

```http
PATCH /api/admin/tenants/{tenant_id}
Authorization: Bearer admin_live_...
Content-Type: application/json

{
  "status": "suspended"  // active, suspended, deleted
}
```

#### Delete Tenant

```http
DELETE /api/admin/tenants/{tenant_id}
Authorization: Bearer admin_live_...
```

---

### Vendor Management

#### Create Vendor

```http
POST /api/admin/vendors
Authorization: Bearer admin_live_...
Content-Type: application/json

{
  "vendor_name": "Vector Informatik GmbH",
  "contact_email": "sales@vector.com",
  "vendor_id": "vector"  // Optional, auto-generated if not provided
}
```

**Response**:
```json
{
  "vendor_id": "vector",
  "vendor_name": "Vector Informatik GmbH",
  "status": "active",
  "api_key": "vnd_live_abc123xyz789...",  // ⚠️ Only shown once!
  "admin_user_id": "vendor_user_xyz",
  "setup_token": "setup_abc789",
  "created_at": "2025-11-06T10:00:00Z"
}
```

#### List All Vendors

```http
GET /api/admin/vendors
Authorization: Bearer admin_live_...
```

#### Get Vendor Details

```http
GET /api/admin/vendors/{vendor_id}
Authorization: Bearer admin_live_...
```

#### Regenerate Vendor API Key

```http
POST /api/admin/vendors/{vendor_id}/regenerate-key
Authorization: Bearer admin_live_...
```

**Response**:
```json
{
  "vendor_id": "vector",
  "new_api_key": "vnd_live_new_key_...",  // ⚠️ Only shown once!
  "regenerated_at": "2025-11-06T10:00:00Z"
}
```

---

### User Management

#### List Tenant Users

```http
GET /api/admin/tenants/{tenant_id}/users
Authorization: Bearer admin_live_...
```

#### Create User for Tenant

```http
POST /api/admin/tenants/{tenant_id}/users
Authorization: Bearer admin_live_...
Content-Type: application/json

{
  "email": "developer@acme.com",
  "role": "developer",  // admin, developer, viewer
  "send_invite": true  // Send invitation email
}
```

#### Reset User Password

```http
POST /api/admin/users/{user_id}/reset-password
Authorization: Bearer admin_live_...
```

**Response**:
```json
{
  "user_id": "user_abc123",
  "reset_token": "reset_xyz789",
  "reset_link": "https://acme.permetrix.fly.dev/reset?token=reset_xyz789"
}
```

---

### Platform Statistics

#### Get Platform Overview

```http
GET /api/admin/stats
Authorization: Bearer admin_live_...
```

**Response**:
```json
{
  "tenants": {
    "total": 25,
    "active": 23,
    "suspended": 2
  },
  "vendors": {
    "total": 5,
    "active": 5
  },
  "licenses": {
    "total_provisioned": 150,
    "active_borrows": 45,
    "overage_count": 3
  },
  "revenue": {
    "monthly_commit": 50000.0,
    "monthly_overage": 1500.0
  }
}
```

---

## 🛠️ Implementation

### FastAPI Endpoints

```python
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import os

app = FastAPI()

# Admin API key from environment
ADMIN_API_KEY = os.getenv("PERMETRIX_ADMIN_API_KEY")

def verify_admin(request: Request):
    """Dependency to verify admin API key"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    provided_key = auth_header.replace("Bearer ", "")
    
    if not ADMIN_API_KEY:
        raise HTTPException(500, "Admin API not configured")
    
    if provided_key != ADMIN_API_KEY:
        raise HTTPException(403, "Invalid admin API key")
    
    return True

# Request models
class CreateTenantRequest(BaseModel):
    company_name: str
    contact_email: str
    tenant_id: Optional[str] = None
    crm_id: Optional[str] = None
    company_domain: Optional[str] = None

class CreateVendorRequest(BaseModel):
    vendor_name: str
    contact_email: str
    vendor_id: Optional[str] = None

# Endpoints
@app.post("/api/admin/tenants")
async def create_tenant(
    req: CreateTenantRequest,
    request: Request,
    _: bool = Depends(verify_admin)
):
    """Create a new customer tenant"""
    from app.db import get_connection
    from app.security import generate_setup_token
    import uuid
    from datetime import datetime
    
    # Generate tenant_id if not provided
    tenant_id = req.tenant_id or slugify(req.company_name)
    
    # Check if tenant already exists
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT tenant_id FROM tenants WHERE tenant_id = ?", (tenant_id,))
        if cur.fetchone():
            raise HTTPException(409, f"Tenant {tenant_id} already exists")
    
    # Create tenant
    domain = f"{tenant_id}.permetrix.fly.dev"
    setup_token = generate_setup_token()
    
    with get_connection(readonly=False) as conn:
        cur = conn.cursor()
        
        # Create tenant
        cur.execute("""
            INSERT INTO tenants (
                tenant_id, company_name, domain, crm_id,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            req.company_name,
            domain,
            req.crm_id,
            "active",
            datetime.now().isoformat()
        ))
        
        # Create admin user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        cur.execute("""
            INSERT INTO users (
                user_id, tenant_id, email, password_hash,
                role, status, created_at, setup_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            tenant_id,
            req.contact_email,
            "pending",  # User sets on first login
            "admin",
            "pending_verification",
            datetime.now().isoformat(),
            setup_token
        ))
        
        # Update tenant with admin user
        cur.execute("""
            UPDATE tenants SET admin_user_id = ? WHERE tenant_id = ?
        """, (user_id, tenant_id))
        
        conn.commit()
    
    return {
        "tenant_id": tenant_id,
        "company_name": req.company_name,
        "domain": domain,
        "status": "active",
        "admin_user_id": user_id,
        "setup_token": setup_token,
        "setup_link": f"https://{domain}/setup?token={setup_token}",
        "created_at": datetime.now().isoformat()
    }

@app.post("/api/admin/vendors")
async def create_vendor(
    req: CreateVendorRequest,
    request: Request,
    _: bool = Depends(verify_admin)
):
    """Create a new vendor"""
    from app.db import get_connection
    from app.security import generate_api_key, hash_api_key, generate_setup_token
    import uuid
    from datetime import datetime
    
    # Generate vendor_id if not provided
    vendor_id = req.vendor_id or slugify(req.vendor_name)
    
    # Check if vendor already exists
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT vendor_id FROM vendors WHERE vendor_id = ?", (vendor_id,))
        if cur.fetchone():
            raise HTTPException(409, f"Vendor {vendor_id} already exists")
    
    # Generate vendor API key
    api_key = generate_api_key(prefix="vnd")
    api_key_hash = hash_api_key(api_key)
    setup_token = generate_setup_token()
    
    with get_connection(readonly=False) as conn:
        cur = conn.cursor()
        
        # Create vendor
        cur.execute("""
            INSERT INTO vendors (
                vendor_id, vendor_name, contact_email,
                api_key_hash, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            vendor_id,
            req.vendor_name,
            req.contact_email,
            api_key_hash,
            "active",
            datetime.now().isoformat()
        ))
        
        # Create admin user
        user_id = f"vendor_user_{uuid.uuid4().hex[:12]}"
        cur.execute("""
            INSERT INTO users (
                user_id, vendor_id, email, password_hash,
                role, status, created_at, setup_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            vendor_id,
            req.contact_email,
            "pending",
            "vendor_admin",
            "pending_verification",
            datetime.now().isoformat(),
            setup_token
        ))
        
        # Update vendor with admin user
        cur.execute("""
            UPDATE vendors SET admin_user_id = ? WHERE vendor_id = ?
        """, (user_id, vendor_id))
        
        conn.commit()
    
    return {
        "vendor_id": vendor_id,
        "vendor_name": req.vendor_name,
        "status": "active",
        "api_key": api_key,  # ⚠️ Only shown once!
        "admin_user_id": user_id,
        "setup_token": setup_token,
        "setup_link": f"https://vendor.permetrix.fly.dev/setup?token={setup_token}",
        "created_at": datetime.now().isoformat()
    }

@app.get("/api/admin/tenants")
async def list_tenants(
    request: Request,
    _: bool = Depends(verify_admin)
):
    """List all tenants"""
    from app.db import get_connection
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                t.tenant_id, t.company_name, t.domain, t.status,
                t.created_at, u.email as admin_email
            FROM tenants t
            LEFT JOIN users u ON t.admin_user_id = u.user_id
            ORDER BY t.created_at DESC
        """)
        
        tenants = []
        for row in cur.fetchall():
            tenants.append({
                "tenant_id": row[0],
                "company_name": row[1],
                "domain": row[2],
                "status": row[3],
                "created_at": row[4],
                "admin_email": row[5]
            })
    
    return {"tenants": tenants}

@app.get("/api/admin/stats")
async def get_platform_stats(
    request: Request,
    _: bool = Depends(verify_admin)
):
    """Get platform statistics"""
    from app.db import get_connection
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Tenant stats
        cur.execute("SELECT COUNT(*) FROM tenants")
        total_tenants = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tenants WHERE status = 'active'")
        active_tenants = cur.fetchone()[0]
        
        # Vendor stats
        cur.execute("SELECT COUNT(*) FROM vendors")
        total_vendors = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vendors WHERE status = 'active'")
        active_vendors = cur.fetchone()[0]
        
        # License stats
        cur.execute("SELECT COUNT(*) FROM licenses")
        total_licenses = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM borrows")
        active_borrows = cur.fetchone()[0]
    
    return {
        "tenants": {
            "total": total_tenants,
            "active": active_tenants
        },
        "vendors": {
            "total": total_vendors,
            "active": active_vendors
        },
        "licenses": {
            "total_provisioned": total_licenses,
            "active_borrows": active_borrows
        }
    }
```

---

## 🔒 Security Considerations

### 1. API Key Storage

```bash
# Set admin API key as Fly.io secret
flyctl secrets set PERMETRIX_ADMIN_API_KEY=admin_live_abc123xyz789... --app permetrix

# Never commit to git!
# Add to .gitignore
echo "PERMETRIX_ADMIN_API_KEY" >> .gitignore
```

### 2. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/admin/tenants")
@limiter.limit("10/minute")  # Limit admin operations
async def create_tenant(...):
    ...
```

### 3. Audit Logging

```python
def log_admin_action(request: Request, action: str, details: dict):
    """Log all admin actions for audit trail"""
    logger.info(
        f"admin_action action={action} ip={request.client.host} details={details}",
        extra={
            "action": action,
            "ip": request.client.host,
            "details": details
        }
    )

@app.post("/api/admin/tenants")
async def create_tenant(req: CreateTenantRequest, request: Request, ...):
    log_admin_action(request, "create_tenant", {"tenant_id": tenant_id})
    # ... create tenant
```

### 4. IP Whitelisting (Optional)

```python
ALLOWED_ADMIN_IPS = os.getenv("PERMETRIX_ADMIN_ALLOWED_IPS", "").split(",")

def verify_admin(request: Request):
    """Verify admin API key and IP"""
    # ... verify API key ...
    
    # Optional: IP whitelist
    if ALLOWED_ADMIN_IPS and request.client.host not in ALLOWED_ADMIN_IPS:
        raise HTTPException(403, "IP not whitelisted for admin access")
    
    return True
```

---

## 📝 Usage Examples

### Using curl

```bash
# Set admin API key
export ADMIN_KEY="admin_live_abc123xyz789..."

# Create customer tenant
curl -X POST https://permetrix.fly.dev/api/admin/tenants \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Corporation",
    "contact_email": "admin@acme.com",
    "tenant_id": "acme"
  }'

# Create vendor
curl -X POST https://permetrix.fly.dev/api/admin/vendors \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Vector Informatik GmbH",
    "contact_email": "sales@vector.com",
    "vendor_id": "vector"
  }'

# List all tenants
curl https://permetrix.fly.dev/api/admin/tenants \
  -H "Authorization: Bearer $ADMIN_KEY"

# Get platform stats
curl https://permetrix.fly.dev/api/admin/stats \
  -H "Authorization: Bearer $ADMIN_KEY"
```

### Using Python Script

```python
import requests
import os

ADMIN_KEY = os.getenv("PERMETRIX_ADMIN_API_KEY")
BASE_URL = "https://permetrix.fly.dev"

headers = {
    "Authorization": f"Bearer {ADMIN_KEY}",
    "Content-Type": "application/json"
}

# Create tenant
response = requests.post(
    f"{BASE_URL}/api/admin/tenants",
    headers=headers,
    json={
        "company_name": "Acme Corporation",
        "contact_email": "admin@acme.com",
        "tenant_id": "acme"
    }
)
print(response.json())

# List tenants
response = requests.get(
    f"{BASE_URL}/api/admin/tenants",
    headers=headers
)
print(response.json())
```

---

## 🎯 Benefits

1. **No SSH Required**: Manage platform from anywhere
2. **Scriptable**: Automate onboarding with scripts
3. **Auditable**: All actions logged
4. **Secure**: API key authentication
5. **Fast**: Direct database operations
6. **Flexible**: Easy to extend with new endpoints

---

## 🚀 Setup Instructions

### 1. Generate Admin API Key

```python
import secrets
import string

def generate_admin_key():
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) 
                          for _ in range(32))
    return f"admin_live_{random_part}"

print(generate_admin_key())
# Example: admin_live_aB3xY9mN2pQ7rT5vW8zC1dF4gH6jK0lM
```

### 2. Set as Fly.io Secret

```bash
flyctl secrets set PERMETRIX_ADMIN_API_KEY=admin_live_... --app permetrix
```

### 3. Test Admin API

```bash
curl https://permetrix.fly.dev/api/admin/stats \
  -H "Authorization: Bearer admin_live_..."
```

---

## 📋 Admin API Checklist

- [ ] Generate admin API key
- [ ] Set as Fly.io secret
- [ ] Implement admin endpoints
- [ ] Add authentication middleware
- [ ] Add audit logging
- [ ] Add rate limiting
- [ ] Test all endpoints
- [ ] Document API usage
- [ ] Create onboarding scripts

