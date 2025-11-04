# Multi-Tenant TODO: Tenant-Aware Dashboards

## Current Status ❌

The multi-tenant **database schema** and **standalone demo** are complete, but the **main app** (Fly.io deployment) is NOT yet tenant-aware.

**What works**:
- ✅ Multi-tenant database schema (tenants, vendors, licenses with `tenant_id`)
- ✅ Standalone demo (`multitenant_demo.py`) with subdomain routing
- ✅ Overview page (`/multitenant`) showing architecture
- ✅ Vendor portal (in standalone demo)
- ✅ Customer dashboards (in standalone demo)

**What's missing**:
- ❌ Main app dashboards are NOT tenant-aware
- ❌ `/dashboard` doesn't filter by tenant
- ❌ `/config` doesn't filter by tenant
- ❌ `/realtime` doesn't filter by tenant
- ❌ Borrow/return endpoints don't scope by tenant

## What Needs to Be Done

### Option 1: Query Parameter Approach (Quickest)

Add `?tenant=bmw` to all dashboard URLs:
- `/dashboard?tenant=bmw`
- `/config?tenant=bmw`
- `/realtime?tenant=bmw`

**Pros**:
- ✅ Works without DNS changes
- ✅ Easy to demo on Fly.io
- ✅ Can switch tenants in browser

**Cons**:
- ❌ Not production-ready (URL-based isolation is weak)
- ❌ User can manually change tenant ID in URL

### Option 2: Subdomain Routing (Production-Ready)

Use real subdomains on Fly.io:
- `bmw.cloud-vs-automotive-demo.fly.dev`
- `mercedes.cloud-vs-automotive-demo.fly.dev`
- `audi.cloud-vs-automotive-demo.fly.dev`
- `vendor.cloud-vs-automotive-demo.fly.dev`

**Pros**:
- ✅ Production-ready isolation
- ✅ Proper multi-tenancy
- ✅ Cannot access other tenant's data

**Cons**:
- ❌ Requires DNS configuration on Fly.io
- ❌ More complex setup

### Option 3: Hybrid Approach (Recommended for Demo)

1. Keep standalone demo (`multitenant_demo.py`) for **local testing** with subdomains
2. Add **query parameter support** to main app for **Fly.io demo**
3. Document that production would use **subdomain routing**

## Implementation Plan

### Phase 1: Make Main App Tenant-Aware (Query Params)

#### 1.1 Add Middleware to Extract Tenant

```python
# In app/main.py

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    # Extract tenant from query parameter
    tenant_id = request.query_params.get("tenant")
    
    # Default to "demo" tenant if not specified (backward compatibility)
    if not tenant_id:
        tenant_id = "demo"
    
    # Store in request state
    request.state.tenant_id = tenant_id
    
    response = await call_next(request)
    return response
```

#### 1.2 Update Database Functions

Modify all functions in `app/db.py` to accept `tenant_id`:
- `borrow_license(tool, user, borrow_id, borrowed_at_iso, tenant_id)`
- `return_license(borrow_id, tenant_id)`
- `get_status(tool, tenant_id)`
- `get_all_tools(tenant_id)`
- etc.

#### 1.3 Update API Endpoints

Modify all endpoints to use `request.state.tenant_id`:
```python
@app.post("/licenses/borrow")
def borrow(request: Request, req: BorrowRequest):
    tenant_id = request.state.tenant_id
    success, is_overage = borrow_license(
        req.tool, req.user, borrow_id, now, tenant_id
    )
    # ...
```

#### 1.4 Update HTML Pages

Add tenant selector to dashboard pages:
```html
<select id="tenant-selector" onchange="switchTenant(this.value)">
  <option value="demo">Demo (Default)</option>
  <option value="bmw">BMW AG</option>
  <option value="mercedes">Mercedes-Benz AG</option>
  <option value="audi">Audi AG</option>
</select>

<script>
function switchTenant(tenant) {
  const url = new URL(window.location);
  url.searchParams.set('tenant', tenant);
  window.location.href = url.toString();
}
</script>
```

### Phase 2: Seed Multi-Tenant Data

On startup, seed the database with:
- **demo** tenant (current single-tenant data - backward compatibility)
- **bmw** tenant (2 products)
- **mercedes** tenant (2 products)
- **audi** tenant (2 products)
- **vector** vendor

### Phase 3: Update UI

#### 3.1 Dashboard (`/dashboard?tenant=bmw`)
- Show licenses for selected tenant only
- Display tenant name in header: "BMW AG • License Dashboard"
- Show vendor name per license

#### 3.2 Budget Config (`/config?tenant=bmw`)
- Only show licenses for selected tenant
- Update config for tenant's licenses only

#### 3.3 Real-Time (`/realtime?tenant=bmw`)
- Filter metrics by tenant
- Show tenant name in header
- Real-time buffer should be tenant-scoped

## Decision for User

**@matthias: Which approach do you prefer?**

### Option A: Query Parameters (Fast)
- ✅ Can deploy to Fly.io immediately
- ✅ Demo-friendly (just add `?tenant=bmw` to URL)
- ❌ Not production-ready

### Option B: Subdomain Routing (Production)
- ✅ Production-ready
- ✅ Proper isolation
- ❌ Requires Fly.io DNS setup

### Option C: Both (Recommended)
- ✅ Query params for main app (Fly.io demo)
- ✅ Subdomain routing for standalone demo (local)
- ✅ Best of both worlds

## Estimated Effort

**Option A (Query Params)**:
- ~2-3 hours implementation
- ~30 files to update

**Option B (Subdomains)**:
- ~4-5 hours implementation + Fly.io config
- ~30 files to update + DNS setup

**Option C (Both)**:
- ~2-3 hours (same as Option A, standalone demo already done)

## Current Workaround

Until tenant-aware dashboards are implemented, users can:
1. Visit `/multitenant` to see the architecture
2. Run `./start-multitenant-demo.sh` locally to test full multi-tenancy
3. Use the standalone demo with subdomain routing

## Summary

**You're right, bro!** 💯

Each tenant should have:
- ✅ **Their own dashboard** (NOT YET tenant-aware in main app)
- ✅ **Their own budget config** (NOT YET tenant-aware in main app)
- ✅ **Their own realtime dashboard** (NOT YET tenant-aware in main app)

The standalone demo (`multitenant_demo.py`) has this, but the main Fly.io app does NOT yet.

**Next step**: Implement Option C (query params for main app + keep standalone demo).

