# Setting Up Subdomains on Fly.io

## Quick Start

Fly.io supports subdomains in two ways:
1. **Built-in `*.fly.dev` subdomains** (easiest, no DNS setup)
2. **Custom domain subdomains** (requires DNS configuration)

## Option 1: Using Built-in `*.fly.dev` Subdomains (Recommended for Testing)

Fly.io automatically provides wildcard subdomains for your app. No setup needed!

### How It Works

If your app is `permetrix`, you automatically get:
- `permetrix.fly.dev` (main domain)
- `*.permetrix.fly.dev` (any subdomain works!)

### Test It

```bash
# Your app is already accessible at:
https://permetrix.fly.dev

# Subdomains work automatically:
https://acme.permetrix.fly.dev
https://globex.permetrix.fly.dev
https://vendor.permetrix.fly.dev
```

**No certificates needed!** Fly.io automatically provides SSL certificates for all `*.fly.dev` subdomains.

### Verify It Works

```bash
# Test subdomain routing
curl -H "Host: acme.permetrix.fly.dev" https://permetrix.fly.dev/licenses/status

# Or use the actual subdomain
curl https://acme.permetrix.fly.dev/licenses/status
```

## Option 2: Custom Domain Subdomains (Production)

If you have a custom domain (e.g., `permetrix.com`), you can add subdomains.

### Step 1: Add Your Main Domain

```bash
# Add your main domain to Fly.io
flyctl certs add permetrix.com

# This will give you DNS instructions
# Add the CNAME record it provides to your DNS provider
```

### Step 2: Add Subdomains

```bash
# Add customer tenant subdomains
flyctl certs add acme.permetrix.com
flyctl certs add globex.permetrix.com

# Add vendor portal subdomain
flyctl certs add vendor.permetrix.com
```

### Step 3: Configure DNS

For each subdomain, add a CNAME record pointing to your Fly.io app:

```
Type    Name              Value
CNAME   acme              permetrix.fly.dev.
CNAME   globex            permetrix.fly.dev.
CNAME   vendor            permetrix.fly.dev.
```

Or if using a different DNS provider, point to your app's Fly.io domain.

### Step 4: Verify Certificates

```bash
# List all certificates
flyctl certs list

# Check certificate status
flyctl certs show acme.permetrix.com
```

### Step 5: Wait for Certificate Provisioning

Fly.io uses Let's Encrypt. Certificates are usually ready in 1-2 minutes:

```bash
# Check certificate status
flyctl certs show acme.permetrix.com

# Should show: "Issued" status
```

## Testing Locally

### Using `/etc/hosts` (macOS/Linux)

Edit `/etc/hosts` to test subdomain routing locally:

```bash
sudo nano /etc/hosts

# Add these lines:
127.0.0.1 acme.localhost
127.0.0.1 globex.localhost
127.0.0.1 vendor.localhost
```

Then access:
- `http://acme.localhost:8000`
- `http://globex.localhost:8000`
- `http://vendor.localhost:8000`

### Using `curl` with Host Header

```bash
# Test tenant routing
curl -H "Host: acme.localhost" http://localhost:8000/licenses/status

# Test vendor routing
curl -H "Host: vendor.localhost" http://localhost:8000/api/vendor/customers
```

## Verify Subdomain Routing Works

### 1. Check Middleware Logs

```bash
# View logs on Fly.io
flyctl logs

# Look for tenant_middleware debug messages:
# tenant_middleware host=acme.permetrix.fly.dev subdomain=acme context=tenant tenant_id=acme
```

### 2. Test Different Subdomains

```bash
# Test customer tenant
curl https://acme.permetrix.fly.dev/licenses/status

# Test vendor portal
curl https://vendor.permetrix.fly.dev/api/vendor/customers

# Test main domain
curl https://permetrix.fly.dev/
```

### 3. Check Request Context

Add a test endpoint to verify context:

```python
@app.get("/debug/context")
async def debug_context(request: Request):
    """Debug endpoint to check tenant context"""
    return {
        "host": request.headers.get("host"),
        "context": getattr(request.state, "context", None),
        "tenant_id": getattr(request.state, "tenant_id", None),
    }
```

Then test:
```bash
curl https://acme.permetrix.fly.dev/debug/context
# Should return: {"host": "acme.permetrix.fly.dev", "context": "tenant", "tenant_id": "acme"}
```

## Troubleshooting

### Subdomain Not Working

1. **Check DNS**:
   ```bash
   dig acme.permetrix.fly.dev
   # Should resolve to Fly.io IPs
   ```

2. **Check Certificate**:
   ```bash
   flyctl certs list
   # Should show certificate for subdomain
   ```

3. **Check App Logs**:
   ```bash
   flyctl logs
   # Look for tenant_middleware messages
   ```

### Certificate Not Issuing

1. **Verify DNS is correct**:
   ```bash
   dig acme.permetrix.com
   # Should point to Fly.io
   ```

2. **Check certificate status**:
   ```bash
   flyctl certs show acme.permetrix.com
   # Look for error messages
   ```

3. **Retry certificate**:
   ```bash
   flyctl certs remove acme.permetrix.com
   flyctl certs add acme.permetrix.com
   ```

### Middleware Not Extracting Tenant

1. **Check host header**:
   ```bash
   curl -v https://acme.permetrix.fly.dev/debug/context
   # Check the Host header in the request
   ```

2. **Verify middleware order**:
   - `tenant_middleware` should be before `track_http_responses`
   - Check `app/main.py` middleware order

3. **Check logs**:
   ```bash
   flyctl logs | grep tenant_middleware
   ```

## Production Checklist

- [ ] Main domain added to Fly.io
- [ ] All subdomains added (`flyctl certs add`)
- [ ] DNS CNAME records configured
- [ ] Certificates issued (check `flyctl certs list`)
- [ ] Middleware tested (check logs)
- [ ] Tenant isolation verified (test with different subdomains)
- [ ] Vendor portal accessible at `vendor.permetrix.fly.dev`
- [ ] Customer tenants accessible at `*.permetrix.fly.dev`

## Example: Complete Setup

```bash
# 1. Deploy your app
flyctl deploy

# 2. Add certificates (if using custom domain)
flyctl certs add permetrix.com
flyctl certs add acme.permetrix.com
flyctl certs add globex.permetrix.com
flyctl certs add vendor.permetrix.com

# 3. Configure DNS (at your DNS provider)
# Add CNAME records pointing to permetrix.fly.dev

# 4. Wait for certificates (1-2 minutes)
flyctl certs list

# 5. Test
curl https://acme.permetrix.com/licenses/status
curl https://vendor.permetrix.com/api/vendor/customers

# 6. Check logs
flyctl logs | grep tenant_middleware
```

## Quick Reference

```bash
# List all certificates
flyctl certs list

# Add certificate for subdomain
flyctl certs add <subdomain>.permetrix.com

# Check certificate status
flyctl certs show <subdomain>.permetrix.com

# Remove certificate
flyctl certs remove <subdomain>.permetrix.com

# View app logs
flyctl logs

# SSH into app (for debugging)
flyctl ssh console
```

