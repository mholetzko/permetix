# Operational Onboarding Guide for Permetrix Owner

## Overview

This guide explains the practical, step-by-step process for onboarding new vendors and customers as the owner/operator of Permetrix.

---

## 🏢 Customer Onboarding (Operational Process)

### Option 1: Self-Service Registration (Future)

**Ideal State**: Customers register themselves via web form
- Landing page with "Sign Up" button
- Automated email verification
- Automatic subdomain provisioning
- No manual intervention needed

**Status**: Not yet implemented

### Option 2: Manual Onboarding (Current)

**When to Use**: 
- Initial customers
- Enterprise customers requiring custom setup
- Customers referred by vendors

**Step-by-Step Process**:

#### Step 1: Collect Customer Information

Gather from customer or vendor:
- Company name
- Contact email (admin)
- Company domain (optional)
- CRM ID (if vendor-referred)
- Desired subdomain (optional, or auto-generate)

**Example**:
```
Company: Acme Corporation
Email: admin@acme.com
Domain: acme.com
CRM ID: CRM-ACME-001 (from Vector)
Subdomain: acme (auto-generated)
```

#### Step 2: Create Tenant via Admin Interface

**Option A: Using Fly.io SSH Console**

```bash
# SSH into the app
flyctl ssh console --app permetrix

# Run Python script to create tenant
python3 << 'EOF'
from app.db import get_connection
import uuid
from datetime import datetime

tenant_id = "acme"  # slugified company name
company_name = "Acme Corporation"
contact_email = "admin@acme.com"
crm_id = "CRM-ACME-001"

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
        company_name,
        f"{tenant_id}.permetrix.fly.dev",
        crm_id,
        "active",
        datetime.now().isoformat()
    ))
    
    # Create admin user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    # Password will be set via email verification
    password_hash = "pending"  # Temporary, user sets on first login
    
    cur.execute("""
        INSERT INTO users (
            user_id, tenant_id, email, password_hash,
            role, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        tenant_id,
        contact_email,
        password_hash,
        "admin",
        "pending_verification",
        datetime.now().isoformat()
    ))
    
    # Update tenant with admin user
    cur.execute("""
        UPDATE tenants SET admin_user_id = ? WHERE tenant_id = ?
    """, (user_id, tenant_id))
    
    conn.commit()
    print(f"✅ Tenant created: {tenant_id}")
    print(f"   Domain: {tenant_id}.permetrix.fly.dev")
    print(f"   Admin: {contact_email}")
EOF
```

**Option B: Using API Endpoint (Recommended)**

Create an admin API endpoint for easier onboarding:

```bash
# Using curl (requires admin API key)
curl -X POST https://permetrix.fly.dev/api/admin/tenants \
  -H "Authorization: Bearer <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Corporation",
    "contact_email": "admin@acme.com",
    "crm_id": "CRM-ACME-001",
    "tenant_id": "acme"
  }'
```

#### Step 3: Send Welcome Email

**Manual Email Template**:

```
Subject: Welcome to Permetrix - Acme Corporation

Hi [Admin Name],

Your Permetrix tenant has been set up!

Tenant Details:
- Company: Acme Corporation
- Subdomain: https://acme.permetrix.fly.dev
- Admin Email: admin@acme.com

Next Steps:
1. Visit: https://acme.permetrix.fly.dev
2. Click "Set Password" (link: https://acme.permetrix.fly.dev/setup?token=abc123)
3. Log in and generate API keys
4. Start using licenses!

If you have any questions, please contact support@permetrix.com

Best regards,
Permetrix Team
```

**Automated Email** (Future):
- System sends email automatically
- Includes verification token
- Password reset link

#### Step 4: Verify Subdomain Works

```bash
# Test subdomain is accessible
curl https://acme.permetrix.fly.dev/health

# Should return 200 OK
```

#### Step 5: Verify Tenant Isolation

```bash
# Test that tenant can only see their data
curl https://acme.permetrix.fly.dev/licenses/status

# Should return empty array (no licenses yet)
```

#### Step 6: Notify Vendors (Optional)

If customer was referred by vendor:
- Vendor can now see customer in their portal
- Vendor can provision licenses

**Check Vendor Portal**:
```bash
# View customer in vendor portal
curl https://vendor.permetrix.fly.dev/api/vendor/customers \
  -H "Authorization: Bearer <vendor-api-key>"
```

---

## 🏭 Vendor Onboarding (Operational Process)

### Option 1: Self-Service Registration (Future)

**Ideal State**: Vendors register themselves
- Vendor portal sign-up page
- Automated verification
- Automatic API key generation
- No manual intervention

**Status**: Not yet implemented

### Option 2: Manual Onboarding (Current)

**When to Use**:
- Initial vendors
- Enterprise vendors
- Vendors requiring custom setup

**Step-by-Step Process**:

#### Step 1: Collect Vendor Information

Gather from vendor:
- Company name
- Contact email (admin)
- Product catalog (optional, can add later)
- Desired vendor_id (optional, or auto-generate)

**Example**:
```
Company: Vector Informatik GmbH
Email: sales@vector.com
Vendor ID: vector
Products:
  - DaVinci Configurator SE
  - DaVinci Configurator IDE
  - ASAP2 v20
```

#### Step 2: Create Vendor via Admin Interface

**Option A: Using Fly.io SSH Console**

```bash
# SSH into the app
flyctl ssh console --app permetrix

# Run Python script to create vendor
python3 << 'EOF'
from app.db import get_connection
from app.security import generate_api_key, hash_api_key
import uuid
from datetime import datetime

vendor_id = "vector"
vendor_name = "Vector Informatik GmbH"
contact_email = "sales@vector.com"

# Generate vendor API key
api_key = generate_api_key(prefix="vnd")
api_key_hash = hash_api_key(api_key)

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
        vendor_name,
        contact_email,
        api_key_hash,
        "active",
        datetime.now().isoformat()
    ))
    
    # Create admin user
    user_id = f"vendor_user_{uuid.uuid4().hex[:12]}"
    password_hash = "pending"
    
    cur.execute("""
        INSERT INTO users (
            user_id, vendor_id, email, password_hash,
            role, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        vendor_id,
        contact_email,
        password_hash,
        "vendor_admin",
        "pending_verification",
        datetime.now().isoformat()
    ))
    
    # Update vendor with admin user
    cur.execute("""
        UPDATE vendors SET admin_user_id = ? WHERE vendor_id = ?
    """, (user_id, vendor_id))
    
    conn.commit()
    print(f"✅ Vendor created: {vendor_id}")
    print(f"   API Key: {api_key}")  # SAVE THIS SECURELY!
    print(f"   Portal: https://vendor.permetrix.fly.dev")
EOF
```

**⚠️ IMPORTANT**: Save the API key securely! It won't be shown again.

**Option B: Using API Endpoint (Recommended)**

```bash
curl -X POST https://permetrix.fly.dev/api/admin/vendors \
  -H "Authorization: Bearer <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Vector Informatik GmbH",
    "contact_email": "sales@vector.com",
    "vendor_id": "vector"
  }'
```

#### Step 3: Send Welcome Email with API Key

**Manual Email Template**:

```
Subject: Welcome to Permetrix Vendor Portal - Vector Informatik

Hi [Vendor Name],

Your Permetrix vendor account has been set up!

Vendor Details:
- Company: Vector Informatik GmbH
- Vendor ID: vector
- Portal: https://vendor.permetrix.fly.dev
- Admin Email: sales@vector.com

API Key (SAVE THIS SECURELY):
vnd_live_abc123xyz789...

This API key is used to:
- Authenticate API requests
- Access vendor portal
- Provision licenses to customers

Next Steps:
1. Visit: https://vendor.permetrix.fly.dev
2. Set your password (link: https://vendor.permetrix.fly.dev/setup?token=xyz789)
3. Add your products to the catalog
4. Start provisioning licenses to customers!

Security Note:
- Keep your API key secure
- Never commit it to version control
- Rotate it if compromised

If you have any questions, please contact support@permetrix.com

Best regards,
Permetrix Team
```

#### Step 4: Add Products to Catalog (Optional)

Vendor can add products later, or you can add them during onboarding:

```bash
# Add products via API
curl -X POST https://vendor.permetrix.fly.dev/api/vendor/products \
  -H "Authorization: Bearer <vendor-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "davinci-se",
    "product_name": "DaVinci Configurator SE",
    "description": "AUTOSAR configuration tool"
  }'
```

#### Step 5: Verify Vendor Portal Access

```bash
# Test vendor can see customers
curl https://vendor.permetrix.fly.dev/api/vendor/customers \
  -H "Authorization: Bearer <vendor-api-key>"

# Should return list of customers (empty initially)
```

---

## 🛠️ Admin Tools & Commands

### Quick Reference Commands

#### List All Tenants

```bash
flyctl ssh console --app permetrix -C "python3 -c \"
from app.db import get_connection
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT tenant_id, company_name, status, domain FROM tenants')
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]} ({row[2]}) - {row[3]}')
\""
```

#### List All Vendors

```bash
flyctl ssh console --app permetrix -C "python3 -c \"
from app.db import get_connection
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT vendor_id, vendor_name, status FROM vendors')
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]} ({row[2]})')
\""
```

#### Check Tenant Status

```bash
curl https://acme.permetrix.fly.dev/health
```

#### Generate API Key for Tenant

```bash
flyctl ssh console --app permetrix -C "python3 -c \"
from app.db import get_connection
from app.security import generate_api_key, hash_api_key
tenant_id = 'acme'
api_key = generate_api_key()
api_key_hash = hash_api_key(api_key)
with get_connection(readonly=False) as conn:
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO api_keys (key_id, tenant_id, key_hash, name, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (f'key_{uuid.uuid4().hex[:12]}', tenant_id, api_key_hash, 'Admin Key', datetime.now().isoformat()))
    conn.commit()
    print(f'API Key: {api_key}')
\""
```

---

## 📋 Onboarding Checklist

### Customer Onboarding Checklist

- [ ] Collect customer information
- [ ] Create tenant record in database
- [ ] Create admin user account
- [ ] Verify subdomain is accessible
- [ ] Send welcome email with setup link
- [ ] Verify tenant isolation works
- [ ] Test API key generation
- [ ] Notify referring vendor (if applicable)
- [ ] Document in CRM/tracking system

### Vendor Onboarding Checklist

- [ ] Collect vendor information
- [ ] Create vendor record in database
- [ ] Generate vendor API key
- [ ] Create admin user account
- [ ] Send welcome email with API key
- [ ] Add products to catalog (optional)
- [ ] Verify vendor portal access
- [ ] Test license provisioning
- [ ] Document in CRM/tracking system

---

## 🔐 Security Best Practices

### API Key Management

1. **Never log API keys** in plain text
2. **Store securely** (password manager, encrypted storage)
3. **Rotate regularly** (every 90 days)
4. **Revoke immediately** if compromised

### Access Control

1. **Use admin API key** for onboarding operations
2. **Limit admin access** to necessary personnel only
3. **Audit all onboarding** actions
4. **Monitor for suspicious activity**

### Data Privacy

1. **Verify customer identity** before creating tenant
2. **Confirm vendor legitimacy** before onboarding
3. **Protect customer data** (GDPR compliance)
4. **Secure communication** (encrypted emails)

---

## 🚀 Future Automation

### Phase 1: Self-Service Registration

- Web forms for customer/vendor sign-up
- Automated email verification
- Automatic subdomain provisioning
- Self-service password setup

### Phase 2: Admin Dashboard

- Web UI for onboarding management
- Customer/vendor list view
- One-click tenant creation
- Automated email sending

### Phase 3: Full Automation

- Vendor referral system
- Automated approval workflows
- Integration with CRM systems
- Automated provisioning

---

## 📞 Support & Troubleshooting

### Common Issues

**Issue**: Subdomain not accessible
- **Check**: DNS propagation (wait 1-2 minutes)
- **Check**: Fly.io app status
- **Fix**: Verify subdomain in tenant record

**Issue**: Customer can't log in
- **Check**: User status (should be "active")
- **Check**: Password hash (should not be "pending")
- **Fix**: Resend setup email

**Issue**: Vendor can't see customers
- **Check**: Vendor API key is valid
- **Check**: Customers have vendor's products
- **Fix**: Verify vendor_id in license_packages

### Getting Help

- **Documentation**: See `docs/ONBOARDING_JOURNEYS.md`
- **Logs**: `flyctl logs --app permetrix`
- **Database**: `flyctl ssh console --app permetrix`

---

## 📝 Example Onboarding Workflow

### Customer: Acme Corporation

```
1. Customer contacts: "We want to use Permetrix"
2. You collect: company name, email, CRM ID
3. You run: Admin API to create tenant
4. System: Creates tenant, admin user, provisions subdomain
5. You send: Welcome email with setup link
6. Customer: Sets password, generates API keys
7. Vendor: Provisions licenses to Acme
8. Customer: Starts using licenses
```

### Vendor: Vector Informatik

```
1. Vendor contacts: "We want to sell licenses via Permetrix"
2. You collect: company name, email, product catalog
3. You run: Admin API to create vendor
4. System: Creates vendor, admin user, generates API key
5. You send: Welcome email with API key
6. Vendor: Sets password, adds products
7. Vendor: Views customers, provisions licenses
8. Customers: Can use vendor's products
```

---

## 🎯 Quick Start Commands

### Onboard Customer (One-Liner)

```bash
# Create customer tenant
flyctl ssh console --app permetrix -C "python3 << 'EOF'
from app.db import get_connection
import uuid
from datetime import datetime

tenant_id = 'acme'
company_name = 'Acme Corporation'
email = 'admin@acme.com'

with get_connection(readonly=False) as conn:
    cur = conn.cursor()
    cur.execute('INSERT INTO tenants (tenant_id, company_name, domain, status, created_at) VALUES (?, ?, ?, ?, ?)',
                (tenant_id, company_name, f'{tenant_id}.permetrix.fly.dev', 'active', datetime.now().isoformat()))
    user_id = f'user_{uuid.uuid4().hex[:12]}'
    cur.execute('INSERT INTO users (user_id, tenant_id, email, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user_id, tenant_id, email, 'pending', 'admin', 'pending_verification', datetime.now().isoformat()))
    conn.commit()
    print(f'✅ Created: {tenant_id}.permetrix.fly.dev')
EOF
"
```

### Onboard Vendor (One-Liner)

```bash
# Create vendor
flyctl ssh console --app permetrix -C "python3 << 'EOF'
from app.db import get_connection
from app.security import generate_api_key, hash_api_key
import uuid
from datetime import datetime

vendor_id = 'vector'
vendor_name = 'Vector Informatik GmbH'
email = 'sales@vector.com'

api_key = generate_api_key(prefix='vnd')
api_key_hash = hash_api_key(api_key)

with get_connection(readonly=False) as conn:
    cur = conn.cursor()
    cur.execute('INSERT INTO vendors (vendor_id, vendor_name, contact_email, api_key_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (vendor_id, vendor_name, email, api_key_hash, 'active', datetime.now().isoformat()))
    user_id = f'vendor_user_{uuid.uuid4().hex[:12]}'
    cur.execute('INSERT INTO users (user_id, vendor_id, email, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user_id, vendor_id, email, 'pending', 'vendor_admin', 'pending_verification', datetime.now().isoformat()))
    conn.commit()
    print(f'✅ Created vendor: {vendor_id}')
    print(f'   API Key: {api_key}')
EOF
"
```

