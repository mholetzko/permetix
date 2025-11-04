# Multi-Tenant License Server Demo

## Overview

This demo showcases a **multi-tenant SaaS architecture** where:
- **Vendors** (like TechVendor) can manage customers and provision licenses
- **Customers** (like Acme, Globex, Initech) each have isolated tenant environments
- Each tenant has its own subdomain for complete isolation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  MULTI-TENANT LICENSE SERVER                 │
└─────────────────────────────────────────────────────────────┘

Vendor Portal                       Customer Tenants
vendor.localhost:8001               acme.localhost:8001
                                    globex.localhost:8001
                                    initech.localhost:8001

┌──────────────────────┐           ┌──────────────────────┐
│  TechVendor          │           │  Acme Tenant         │
│                      │           │                      │
│  • View customers    │───────▶   │  • View licenses     │
│  • Provision licenses│           │  • Monitor usage     │
│  • Manage products   │           │  • See vendors       │
└──────────────────────┘           └──────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# If not already done
source .venv/bin/activate
pip install fastapi uvicorn
```

### 2. Run the Demo

```bash
python multitenant_demo.py
```

### 3. Visit the Portals

**Vendor Portal** (TechVendor):
- URL: http://vendor.localhost:8001
- Features:
  - View all customers (Acme, Globex, Initech)
  - Provision new licenses to customers
  - See customer activity

**Customer Tenants**:
- **Acme**: http://acme.localhost:8001
- **Globex**: http://globex.localhost:8001
- **Initech**: http://initech.localhost:8001

Each tenant shows:
- Licensed products
- Usage statistics (in use / total)
- Commit vs. overage status
- Vendor information

## Demo Workflow

### Scenario: TechVendor Provisions License to Acme

1. **Open Vendor Portal**:
   ```
   http://vendor.localhost:8001
   ```

2. **View Customers**:
   - See Acme, Globex, Initech listed with their CRM IDs
   - See how many active licenses each has

3. **Provision New License**:
   - Click "Provision New License"
   - Select customer: BMW
   - Select product: Greenhills Multi 8.2
   - Set quantities:
     - Total: 20
     - Commit: 5
     - Max Overage: 15
   - Click "Provision License"

4. **Switch to BMW Tenant**:
   ```
   http://bmw.localhost:8001
   ```

5. **View New License**:
   - See the new "Greenhills Multi 8.2" license
   - Shows vendor: Vector Informatik GmbH
   - Shows 0/20 in use (idle status)

## Database Schema

### Multi-Tenant Tables

**tenants** (Customers):
```sql
CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,      -- bmw, mercedes, audi
    company_name TEXT NOT NULL,       -- BMW AG
    domain TEXT,                      -- bmw.com
    crm_id TEXT UNIQUE,              -- CRM-BMW-001
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL
);
```

**vendors** (Software Vendors):
```sql
CREATE TABLE vendors (
    vendor_id TEXT PRIMARY KEY,       -- vector
    vendor_name TEXT NOT NULL,        -- Vector Informatik GmbH
    contact_email TEXT,
    api_key_hash TEXT,
    created_at TEXT NOT NULL
);
```

**license_packages** (Vendor → Tenant):
```sql
CREATE TABLE license_packages (
    package_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,          -- bmw
    vendor_id TEXT NOT NULL,          -- vector
    product_id TEXT NOT NULL,         -- davinci-se
    product_name TEXT NOT NULL,       -- DaVinci Configurator SE
    crm_opportunity_id TEXT,          -- CRM-OPP-BMW-001
    status TEXT DEFAULT 'active',
    provisioned_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY(vendor_id) REFERENCES vendors(vendor_id)
);
```

**licenses** (Actual Licenses):
```sql
CREATE TABLE licenses (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,          -- bmw (isolation!)
    package_id TEXT,
    tool TEXT NOT NULL,
    total INTEGER NOT NULL,
    borrowed INTEGER NOT NULL DEFAULT 0,
    commit_qty INTEGER DEFAULT 0,
    max_overage INTEGER DEFAULT 0,
    commit_price REAL DEFAULT 0.0,
    overage_price_per_license REAL DEFAULT 0.0,
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY(package_id) REFERENCES license_packages(package_id),
    UNIQUE(tenant_id, tool)           -- One license per tool per tenant
);
```

## Key Features

### 1. **Subdomain Routing**

The middleware extracts the subdomain from the `Host` header:

```python
host = request.headers.get("host", "").split(":")[0]
subdomain = host.split(".")[0]

if subdomain in ["bmw", "mercedes", "audi"]:
    request.state.tenant_id = subdomain
    request.state.context = "tenant"
elif subdomain == "vendor":
    request.state.context = "vendor"
```

### 2. **Tenant Isolation**

All database queries are scoped by `tenant_id`:

```python
# Get licenses for specific tenant only
SELECT * FROM licenses WHERE tenant_id = 'bmw'

# BMW cannot see Mercedes licenses
SELECT * FROM licenses WHERE tenant_id = 'mercedes'  # Different data
```

### 3. **Vendor Portal**

Vector can:
- **View all customers** who have their licenses
- **Provision new licenses** with a few clicks
- **See customer activity** (how many licenses each has)

### 4. **Customer Dashboard**

Each tenant (BMW, Mercedes, Audi) sees:
- Only their licenses (isolated by `tenant_id`)
- Which vendor provided each license
- Real-time usage statistics
- Commit vs. overage status

## API Endpoints

### Vendor Endpoints

**GET /api/vendor/customers**
- Lists all customers who have licenses from this vendor
- Returns: `[{tenant_id, company_name, crm_id, active_licenses}]`

**POST /api/vendor/provision**
- Provisions a new license to a customer
- Body:
  ```json
  {
    "tenant_id": "bmw",
    "product_id": "greenhills-multi",
    "product_name": "Greenhills Multi 8.2",
    "total": 20,
    "commit_qty": 5,
    "max_overage": 15,
    "commit_price": 8000.0,
    "overage_price_per_license": 800.0
  }
  ```

### Tenant Endpoints

**GET /api/tenant/licenses**
- Lists all licenses for the current tenant (extracted from subdomain)
- Automatically scoped to `request.state.tenant_id`
- Returns: `[{id, tool, total, borrowed, vendor_name, ...}]`

## Testing Multi-Tenancy

### Test Isolation

1. **Provision license to BMW**:
   - Go to http://vendor.localhost:8001
   - Provision "Greenhills Multi 8.2" to BMW

2. **Check BMW can see it**:
   - Go to http://bmw.localhost:8001
   - Should see "Greenhills Multi 8.2"

3. **Check Mercedes CANNOT see it**:
   - Go to http://mercedes.localhost:8001
   - Should NOT see "Greenhills Multi 8.2" (only sees their own licenses)

### Test Vendor View

1. **Go to Vendor Portal**:
   - http://vendor.localhost:8001

2. **See all customers**:
   - BMW AG
   - Mercedes-Benz AG
   - Audi AG

3. **Click "View Dashboard →" for any customer**:
   - Opens that tenant's dashboard in new tab
   - Shows only that tenant's licenses

## Demo Data

On startup, the demo seeds:

**3 Tenants**:
- BMW AG (bmw.localhost:8001)
- Mercedes-Benz AG (mercedes.localhost:8001)
- Audi AG (audi.localhost:8001)

**1 Vendor**:
- Vector Informatik GmbH

**6 Initial Licenses** (2 per tenant):
- DaVinci Configurator SE (20 total, 5 commit, 15 overage)
- DaVinci Configurator IDE (10 total, 10 commit, 0 overage)

## Extending the Demo

### Add More Vendors

```python
# In seed_multitenant_demo_data()
cur.execute(
    "INSERT OR IGNORE INTO vendors(...) VALUES (...)",
    ("greenhills", "Greenhills Software", "sales@greenhills.com", now)
)
```

### Add More Tenants

```python
tenants.append({
    "id": "tesla",
    "name": "Tesla Inc",
    "domain": "tesla.com",
    "crm_id": "CRM-TESLA-004"
})
```

### Add More Products

```python
products.append({
    "id": "matlab",
    "name": "MATLAB Enterprise",
    "total": 50,
    "commit": 20,
    "overage": 30,
    "commit_price": 10000.0,
    "overage_price": 1000.0
})
```

## Production Deployment

For production, replace `localhost` subdomains with real domains:

**Vendor Portal**:
- vendors.cloudlicenses.com

**Customer Tenants**:
- bmw.cloudlicenses.com
- mercedes.cloudlicenses.com
- audi.cloudlicenses.com

Update DNS with wildcard subdomain:
```
*.cloudlicenses.com  →  Your server IP
```

FastAPI will handle subdomain routing automatically!

## Next Steps

This demo shows the **foundation** for a full multi-tenant SaaS. To make it production-ready:

1. ✅ **Add authentication** (OAuth 2.0 for vendors, JWT for tenants)
2. ✅ **Add API keys** (per-tenant keys for application integration)
3. ✅ **Add tenant-scoped borrows** (update borrow/return logic to be tenant-aware)
4. ✅ **Add billing** (track costs per tenant, export invoices for vendors)
5. ✅ **Add observability** (Prometheus metrics per tenant)
6. ✅ **Add HMAC signatures** (prevent license theft, as documented)

## Troubleshooting

### "Cannot connect to subdomain"

**Problem**: Browser can't resolve `bmw.localhost:8001`

**Solution**: On most systems, `.localhost` subdomains work automatically. If not:

**macOS/Linux**:
```bash
echo "127.0.0.1 bmw.localhost mercedes.localhost audi.localhost vendor.localhost" | sudo tee -a /etc/hosts
```

**Windows**:
1. Edit `C:\Windows\System32\drivers\etc\hosts` as Administrator
2. Add:
   ```
   127.0.0.1 bmw.localhost
   127.0.0.1 mercedes.localhost
   127.0.0.1 audi.localhost
   127.0.0.1 vendor.localhost
   ```

### Database Error

**Problem**: `sqlite3.OperationalError: table already exists`

**Solution**: Delete the old database:
```bash
rm multitenant_demo.db
python multitenant_demo.py
```

## Summary

This demo proves the **multi-tenant architecture** works:
- ✅ Subdomain routing (tenant isolation)
- ✅ Vendor portal (manage customers)
- ✅ License provisioning (vendor → tenant)
- ✅ Tenant dashboards (isolated views)
- ✅ Database isolation (tenant_id scoping)

**This is the foundation for cloudlicenses.com!** 🚀

