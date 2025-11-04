# Security Demo

## Overview

This demo showcases **multi-layer security** that prevents license theft, even if attackers discover API endpoints or intercept network traffic.

## 🎯 What's Implemented

### ✅ Layer 1: HMAC Request Signing
- Every request includes a cryptographic signature
- Uses vendor-specific secret embedded in client library
- Signature = HMAC-SHA256(tool|user|timestamp, vendor_secret)

### ✅ Layer 2: Timestamp Validation
- Requests expire after 5 minutes
- Prevents replay attacks
- Server rejects old timestamps

### ✅ Layer 3: Rate Limiting
- Already active in the application
- Prevents brute-force attacks

### 📚 Layers 4-7: Documented (Not Implemented)
- Client Certificates (mTLS)
- TPM/Secure Enclave binding
- IP Whitelisting
- Behavioral Analysis

See `LICENSE_THEFT_PREVENTION.md` for full technical details.

---

## 🚀 Quick Start

### 1. Run the Interactive Demo Script

```bash
./demo-security-attack.sh
```

This script demonstrates:
1. ✅ **Normal operation** - Legitimate client with valid signature
2. ❌ **Naive attack** - curl without signature (blocked)
3. ❌ **Sophisticated attack** - Wrong signature (blocked)
4. ❌ **Replay attack** - Old timestamp (blocked)

### 2. Visit the Web UI

Open http://localhost:8000/security-demo (or https://cloud-vs-automotive-demo.fly.dev/security-demo)

Features:
- Side-by-side comparison of legitimate vs attack requests
- 7-layer security explanation
- Interactive "try an attack" form
- Real-time feedback showing why attacks fail

### 3. Try the Client Library

```bash
cd clients/python
source .venv/bin/activate
python example.py http://localhost:8000
```

The client automatically adds HMAC signatures. Check the logs to see:
```
X-Signature: abc123...
X-Timestamp: 1234567890
X-Vendor-ID: techvendor
```

---

## 🔬 Technical Details

### How HMAC Works

**Client Side** (Python example):
```python
import hmac
import hashlib
import time

VENDOR_SECRET = "techvendor_secret_ecu_2025_demo_xyz789abc123def456"

timestamp = str(int(time.time()))
payload = f"{tool}|{user}|{timestamp}"
signature = hmac.new(
    VENDOR_SECRET.encode('utf-8'),
    payload.encode('utf-8'),
    hashlib.sha256
).hexdigest()

headers = {
    "X-Signature": signature,
    "X-Timestamp": timestamp,
    "X-Vendor-ID": "techvendor"
}
```

**Server Side** (`app/security.py`):
```python
# Extract headers
signature = request.headers.get("X-Signature")
timestamp = request.headers.get("X-Timestamp")

# Reconstruct expected signature
payload = f"{tool}|{user}|{timestamp}"
expected = hmac.new(
    VENDOR_SECRET.encode('utf-8'),
    payload.encode('utf-8'),
    hashlib.sha256
).hexdigest()

# Compare (constant-time to prevent timing attacks)
if hmac.compare_digest(signature, expected):
    # Valid!
else:
    # 403 Forbidden
```

### Security Benefits

1. **No API Keys in URLs**: Signature is in headers, not query strings
2. **Time-Limited**: Each signature expires after 5 minutes
3. **Vendor-Specific**: Each vendor has unique secret
4. **Tamper-Proof**: Changing payload invalidates signature
5. **Constant-Time Compare**: Prevents timing attacks

---

## 🎬 Demo Scenarios

### Scenario 1: Developer Conference
**Audience**: Technical developers

**Script** (5 minutes):
1. Show normal client working (30 sec)
2. Run `./demo-security-attack.sh` (2 min)
3. Open `/security-demo` page (1 min)
4. Q&A with live attacks (1.5 min)

**Key Message**: "Even if attackers find your API, they can't steal licenses"

### Scenario 2: Automotive Executive
**Audience**: Non-technical decision makers

**Script** (3 minutes):
1. Open `/security-demo` page
2. Click through the 7 layers
3. Try the interactive attack form
4. Show "Attack Blocked" message

**Key Message**: "Cloud is MORE secure than traditional on-premise licensing"

### Scenario 3: Security Audit
**Audience**: InfoSec team

**Script** (15 minutes):
1. Walk through `LICENSE_THEFT_PREVENTION.md`
2. Show code in `app/security.py`
3. Run attacks manually with curl
4. Discuss layers 4-7 (mTLS, TPM)
5. Review threat model

**Key Message**: "Defense in depth with 7 layers, even if one fails"

---

## 🛠️ Configuration

### Enable/Disable Security

**In `app/security.py`:**
```python
REQUIRE_SIGNATURES = False  # Set to True to enforce
```

When `False`: Signatures are validated if present, but not required
When `True`: All requests MUST have valid signatures

### Adjust Time Window

**In `app/security.py`:**
```python
SIGNATURE_VALID_WINDOW = 300  # seconds (5 minutes)
```

Increase for slow networks, decrease for higher security.

### Add More Vendors

**In `app/security.py`:**
```python
VENDOR_SECRETS = {
    "techvendor": "techvendor_secret_...",
    "newvendor": "newvendor_secret_...",  # Add here
}
```

Each vendor's client library should use their specific secret.

---

## 📊 Metrics

Security metrics are automatically tracked in Prometheus:

- `license_borrow_attempts_total{tool, user}` - All attempts
- `license_borrow_successes_total{tool, user}` - Successful
- `license_borrow_failures_total{tool, reason}` - Failed (includes "invalid_signature")

View in Grafana or query directly:
```promql
# Attack attempts (should be 0 or very low)
rate(license_borrow_failures_total{reason="invalid_signature"}[5m])
```

---

## 🐛 Troubleshooting

### "Security validation failed: Missing X-Signature"
**Cause**: Client not adding security headers  
**Fix**: Ensure `enable_security=True` in LicenseClient constructor

### "Request expired"
**Cause**: Clock skew between client and server  
**Fix**: Sync clocks with NTP, or increase `SIGNATURE_VALID_WINDOW`

### "Invalid signature"
**Cause**: Client and server using different secrets  
**Fix**: Check `VENDOR_SECRET` matches in both client and `app/security.py`

### Attack succeeds when it shouldn't
**Cause**: `REQUIRE_SIGNATURES = False` in production  
**Fix**: Set `REQUIRE_SIGNATURES = True` in `app/security.py`

---

## 📚 Additional Resources

- **LICENSE_THEFT_PREVENTION.md** - Full technical deep dive
- **CLOUD_LICENSE_PROTOCOL.md** - Complete architecture
- **MULTITENANT_ARCHITECTURE.md** - Multi-tenant security
- **clients/** - Reference implementations in Python, C, C++, Rust

---

## 🎓 Educational Notes

### Why This Matters for Automotive

Traditional automotive licensing (on-premise):
- ❌ License files can be copied
- ❌ Dongles can be cloned
- ❌ No real-time revocation
- ❌ Limited visibility into usage

Cloud-based licensing:
- ✅ Cryptographic authentication
- ✅ Real-time validation
- ✅ Instant revocation
- ✅ Full audit trail
- ✅ Behavioral analysis
- ✅ Multiple security layers

### Common Concerns Addressed

**Q: "What if the secret is extracted from the binary?"**  
A: Layer 3 (mTLS with client certificates) prevents this. Even with the secret, you need the certificate.

**Q: "What if someone clones the entire machine?"**  
A: Layer 4 (TPM/Secure Enclave) binds keys to specific hardware. Can't be cloned.

**Q: "What about offline usage?"**  
A: Short-lived tokens can be issued for offline work (e.g., 24-hour validity). Not covered in this demo.

**Q: "Is this overkill?"**  
A: For high-value software (ECU tools at $8k/license), defense-in-depth is essential. You only need 1-2 layers to stop casual attackers, but 7 layers stop determined adversaries.

---

## ✅ Success Criteria

Your demo is successful if the audience understands:

1. ✅ Cloud licensing is MORE secure than on-premise
2. ✅ Multiple layers provide defense-in-depth
3. ✅ Even API key theft doesn't compromise security
4. ✅ Real-time visibility enables faster incident response

---

**Ready to present?** Start with `./demo-security-attack.sh` or open `/security-demo` in your browser! 🚀

