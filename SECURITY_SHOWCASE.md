# 🔐 Security Showcase Demo

## Quick Start

### Run the Interactive Demo

```bash
# Start the license server (if not already running)
uvicorn app.main:app --reload

# In another terminal, run the security showcase
./demo-security-showcase.sh
```

This will demonstrate 5 attack scenarios:
1. ✅ **Complete Security** - All layers present (SUCCESS)
2. ❌ **Missing Signature** - No HMAC signature (FAIL)
3. ❌ **Wrong Vendor Secret** - Attacker guesses wrong secret (FAIL)
4. ❌ **Tampered Request** - Man-in-the-middle attack (FAIL)
5. ❌ **Replay Attack** - Reusing old signed request (FAIL)

---

## 🎯 What This Demonstrates

### Real-World Attack Prevention

**Scenario: Competitor tries to steal licenses**

A competitor company (let's call them "HackerCorp") wants to use your customer's licenses without paying:

1. **They capture an API key** from network traffic ❌ Won't work!
   - Still need vendor secret to generate valid signatures
   
2. **They reverse-engineer the client library** ❌ Won't work!
   - Vendor secret is embedded, but signatures include API key
   - Can't use their own API key with stolen vendor secret
   
3. **They intercept a valid request and replay it** ❌ Won't work!
   - Timestamps expire after 5 minutes
   - Each request needs unique timestamp
   
4. **They modify a captured request** ❌ Won't work!
   - HMAC signature includes all request data
   - Any change invalidates the signature

### Why This Matters for Automotive

Traditional automotive licensing (dongles, node-locked):
- ❌ Can be cloned/shared
- ❌ No audit trail
- ❌ Expensive support (shipping dongles)
- ❌ Can't revoke remotely

Cloud licensing with 3-layer security:
- ✅ Cannot be cloned (cryptographic signatures)
- ✅ Complete audit trail (every request logged)
- ✅ Instant provisioning/revocation
- ✅ Real-time monitoring

---

## 🔬 Technical Deep Dive

### How the Security Works

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CLIENT SIDE (e.g., Python client)                            │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Request: Borrow "ECU Development Suite" for user "alice"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. BUILD PAYLOAD                                                 │
│    tool = "ECU Development Suite"                               │
│    user = "alice"                                               │
│    timestamp = 1704067200                                       │
│    api_key = "acme_live_pk_xyz789"                              │
│                                                                  │
│    payload = "ECU Development Suite|alice|1704067200|acme_..."  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SIGN WITH VENDOR SECRET (embedded in client library)         │
│    vendor_secret = "techvendor_secret_ecu_2025_demo_xyz789..."  │
│                                                                  │
│    signature = HMAC-SHA256(vendor_secret, payload)              │
│              = "a3f8c9d2e1b4a7f6c5d8e9f2a3b6c7d8e9f1a2b3c4..." │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SEND HTTP REQUEST                                             │
│    POST /licenses/borrow                                         │
│    Headers:                                                      │
│      X-Signature: a3f8c9d2e1b4a7f6c5d8e9f2a3b6c7d8e9f1a2b3...  │
│      X-Timestamp: 1704067200                                     │
│      X-Vendor-ID: techvendor                                     │
│    Body:                                                         │
│      {"tool": "ECU Development Suite", "user": "alice"}         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. SERVER VALIDATION                                             │
│    ✓ Check timestamp (< 5 minutes old?)                         │
│    ✓ Lookup vendor_secret for "techvendor"                      │
│    ✓ Rebuild payload from request body                          │
│    ✓ Compute expected_signature = HMAC-SHA256(secret, payload)  │
│    ✓ Compare signatures (constant-time to prevent timing attack)│
│                                                                  │
│    if signatures match:                                          │
│      → Process license borrow                                    │
│    else:                                                         │
│      → Reject with 403 Forbidden                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Security Layers Explained

### Layer 1: API Key (Tenant Authentication)

**Purpose**: Identify which customer tenant is making the request

**Format**: `{tenant}_{environment}_pk_{random}`
- Example: `acme_live_pk_xY9kL3mN8pQ2rT5wZ`

**Properties**:
- ✅ Unique per customer tenant
- ✅ Can be rotated/revoked without code changes
- ✅ Logged for audit trail
- ✅ Scoped to specific permissions (borrow, return, status)
- ❌ Not enough alone (attacker could steal and reuse)

**Storage**:
- Customer: Environment variable or config file
- Server: Hashed in database (bcrypt/SHA256)

---

### Layer 2: Vendor Secret (Application Authentication)

**Purpose**: Verify request comes from legitimate vendor application

**Format**: Long random string
- Example: `techvendor_secret_ecu_2025_demo_xyz789abc123def456`

**Properties**:
- ✅ Embedded in client library at compile time
- ✅ Different secret per vendor
- ✅ Used to generate HMAC signatures
- ✅ Never transmitted over network (only signature is sent)
- ❌ If compromised, can be rotated (deploy new client version)

**Storage**:
- Client: Compiled into binary (obfuscated)
- Server: Database or secure key management system
- Production: Hardware Security Module (HSM) or Secure Enclave

---

### Layer 3: HMAC Signature (Request Integrity)

**Purpose**: Prove request hasn't been tampered with

**Algorithm**: HMAC-SHA256

**Inputs**:
1. Vendor Secret (Layer 2)
2. Payload: `tool|user|timestamp|api_key`

**Properties**:
- ✅ Unique per request (includes timestamp)
- ✅ Cryptographically binds all request parameters
- ✅ Cannot be forged without vendor secret
- ✅ Prevents replay attacks (timestamp validation)
- ✅ Prevents tampering (any change invalidates signature)

**Validation**:
```python
# Server reconstructs payload
payload = f"{tool}|{user}|{timestamp}|{api_key}"

# Compute expected signature
expected = HMAC-SHA256(vendor_secret, payload)

# Constant-time comparison (prevent timing attacks)
if hmac.compare_digest(received_signature, expected):
    allow_request()
else:
    reject_request()
```

---

## 🎬 Demo Scenarios

### Scenario 1: ✅ Complete Security (SUCCESS)

**Request**:
```bash
curl -X POST http://localhost:8000/licenses/borrow \
  -H "X-Signature: a3f8c9d2e1b4a7f6..." \
  -H "X-Timestamp: 1704067200" \
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "alice"}'
```

**Result**: ✅ `200 OK` - License borrowed successfully

---

### Scenario 2: ❌ Missing Signature (FAIL)

**Request**:
```bash
curl -X POST http://localhost:8000/licenses/borrow \
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "hacker"}'
```

**Result**: ❌ `403 Forbidden` - Missing X-Signature header

---

### Scenario 3: ❌ Wrong Vendor Secret (FAIL)

**Attack**: Attacker guesses vendor secret as `"hacker_secret_123"`

**Request**:
```bash
# Signature computed with WRONG secret
curl -X POST http://localhost:8000/licenses/borrow \
  -H "X-Signature: wrong_signature_abc123..." \
  -H "X-Timestamp: 1704067200" \
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "hacker"}'
```

**Result**: ❌ `403 Forbidden` - Invalid signature

**Why**: Signature computed with wrong secret doesn't match server's expectation

---

### Scenario 4: ❌ Tampered Request (FAIL)

**Attack**: Man-in-the-middle intercepts request and changes tool

**Original Request** (signed by client):
- Tool: `"ECU Development Suite"`
- Signature: `a3f8c9d2e1b4a7f6...` (valid for ECU)

**Modified Request** (by attacker):
- Tool: `"GreenHills Multi IDE"` ⚠️ Changed!
- Signature: `a3f8c9d2e1b4a7f6...` (still for ECU)

**Result**: ❌ `403 Forbidden` - Invalid signature

**Why**: Server recomputes signature with new tool name, doesn't match

---

### Scenario 5: ❌ Replay Attack (FAIL)

**Attack**: Attacker captures valid request from 10 minutes ago and resends it

**Request**:
```bash
curl -X POST http://localhost:8000/licenses/borrow \
  -H "X-Signature: a3f8c9d2e1b4a7f6..." \
  -H "X-Timestamp: 1704066600" \  # 10 minutes old!
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "alice"}'
```

**Result**: ❌ `403 Forbidden` - Request expired (timestamp difference: 600s)

**Why**: Timestamp is older than 5-minute window (300 seconds)

---

## 🔧 Production Configuration

### Enable Strict Security Mode

Edit `app/security.py`:

```python
# Configuration
REQUIRE_SIGNATURES = True  # ← Change to True for production
SIGNATURE_VALID_WINDOW = 300  # 5 minutes
```

### Rotate Vendor Secret

1. Generate new secret:
   ```python
   import secrets
   new_secret = f"techvendor_secret_{secrets.token_urlsafe(32)}"
   ```

2. Update `VENDOR_SECRETS` in `app/security.py`

3. Rebuild and redeploy client libraries

4. Notify customers to update

### API Key Management

```python
from app.db import generate_api_key, revoke_api_key

# Generate for customer
api_key, key_id = generate_api_key(
    tenant_id="acme",
    name="Production Key",
    environment="live"
)
print(f"API Key (SHOW ONCE): {api_key}")
print(f"Key ID: {key_id}")

# Revoke if compromised
revoke_api_key(key_id)
```

---

## 📊 Monitoring & Alerts

### Failed Authentication Attempts

```python
# In app/main.py - borrow endpoint
if not is_valid:
    logger.warning(
        "Security check failed: %s | IP: %s | User: %s | Tool: %s",
        error_msg,
        request.client.host,
        req.user,
        req.tool
    )
```

### Set up alerts for:
- ❌ High rate of signature failures (potential attack)
- ❌ Expired timestamp attempts (replay attack)
- ❌ Unknown vendor IDs (reconnaissance)
- ❌ Same API key from multiple IPs (stolen key)

---

## 🎯 Comparison: Traditional vs Cloud Security

| Aspect | Traditional (Dongle) | Cloud (3-Layer) |
|--------|---------------------|-----------------|
| **Cloning** | ❌ Possible with hardware tools | ✅ Impossible (crypto signatures) |
| **Theft** | ❌ Physical theft | ✅ Prevented by HMAC |
| **Sharing** | ❌ Can pass dongle around | ✅ API key + secret required |
| **Revocation** | ❌ Must physically retrieve | ✅ Instant (revoke API key) |
| **Audit Trail** | ❌ No visibility | ✅ Every request logged |
| **Tampering** | ❌ Can modify local license | ✅ Signature validation |
| **Replay** | ❌ Can replay license files | ✅ Timestamp prevents |
| **Cost** | ❌ High ($50-200 per dongle) | ✅ Low (API calls) |

---

## 🚀 Next Steps

1. **Run the demo**: `./demo-security-showcase.sh`
2. **Enable strict mode**: Set `REQUIRE_SIGNATURES=True`
3. **Monitor logs**: Watch for failed auth attempts
4. **Rotate secrets**: Every 90 days
5. **Customer onboarding**: Provide API keys securely

For more details:
- `SECURITY_SUMMARY.md` - High-level overview
- `LICENSE_THEFT_PREVENTION.md` - Deep dive on crypto
- `TENANT_AUTHENTICATION_DESIGN.md` - API key architecture

