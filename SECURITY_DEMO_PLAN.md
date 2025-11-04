# License Security Demo Plan

## 🎯 Goal

Demonstrate how the multi-layered security prevents license theft, even if API keys are stolen.

## 🎬 Demo Scenario

### Act 1: Normal Operation ✅
**Alice (legitimate user) checks out a license:**
```bash
# Using official client library (with HMAC signature)
./clients/python/run_example.sh
✅ License checked out successfully
```

### Act 2: API Key Stolen 🚨
**Bob (attacker) steals Alice's API key from logs/environment:**
```bash
# Attacker finds the API key
API_KEY="clsk_acme_abc123xyz789..."
```

### Act 3: Naive Attack Fails ❌
**Bob tries to use the stolen API key directly:**
```bash
curl -X POST "https://cloud-vs-automotive-demo.fly.dev/licenses/borrow" \
  -H "Authorization: Bearer clsk_acme_abc123xyz789..." \
  -H "Content-Type: application/json" \
  -d '{"tool": "ECU Development Suite", "user": "hacker@evil.com"}'

❌ 403 Forbidden: Missing or invalid HMAC signature
```

### Act 4: Sophisticated Attack Also Fails ❌
**Bob reverse-engineers the HMAC signature format but doesn't have the vendor secret:**
```python
# Attacker's script (missing the real vendor secret)
import hmac
signature = hmac.new(b"guessed_secret", b"payload", hashlib.sha256).hexdigest()

❌ 403 Forbidden: Invalid signature
```

### Act 5: Even More Sophisticated Attack Fails ❌
**Bob extracts the vendor secret from the client library binary:**
```bash
# Attacker decompiles the Python client or reverse-engineers the binary
VENDOR_SECRET = "techvendor_secret_ecu_2025_demo..."

# Now Bob can generate valid HMAC signatures!
# But wait... we have Layer 2 and 3...
```

**Layer 2: Client Certificates (mTLS)**
```bash
# Bob's request is rejected because he doesn't have the client certificate
❌ 403 Forbidden: Client certificate required
```

**Layer 3: Hardware Keys (TPM/Secure Enclave)**
```bash
# Even if Bob has the certificate, it's bound to Alice's TPM
# Bob cannot extract the private key from the TPM
❌ 403 Forbidden: Invalid hardware attestation
```

---

## 🛠️ Implementation Options

### Option 1: Quick Demo (HMAC Only) ⚡
**Effort**: 1-2 hours  
**Shows**: Basic request signing

**What to build**:
1. Add `X-Signature` and `X-Timestamp` headers to all client libraries
2. Add server-side HMAC validation middleware
3. Create `demo-security.sh` script showing attack scenarios
4. Store vendor secrets in database or config

**Demo commands**:
```bash
# Show it working
./demo-security.sh normal

# Show naive attack failing
./demo-security.sh naive-attack

# Show sophisticated attack failing
./demo-security.sh sophisticated-attack
```

### Option 2: Full Security Stack (HMAC + mTLS) 🔐
**Effort**: 4-6 hours  
**Shows**: Production-grade security

**What to build**:
1. Generate client certificates for each tenant
2. Configure FastAPI to require client certs
3. Update all clients to use certificates
4. Add certificate validation on server
5. Demo script showing all 3 layers

### Option 3: Visual Demo Only (No Code) 📊
**Effort**: 30 minutes  
**Shows**: Conceptual understanding

**What to build**:
1. Interactive presentation page showing attack scenarios
2. Animated flow diagrams
3. Code snippets (non-functional, for illustration)
4. "Try the attack" form that always fails with educational messages

---

## 🎨 Recommended Approach: **Option 1 + Visual Demo**

**Why**:
- Quick to implement (~2 hours total)
- Demonstrates real security concepts
- Visually impressive for presentations
- Educational without being too complex

**Implementation**:

### 1. Backend (30 min)
```python
# app/security.py
from fastapi import Request, HTTPException
import hmac
import hashlib
import time

VENDOR_SECRETS = {
    "techvendor": "techvendor_secret_ecu_2025_demo_xyz789abc123",
    # In production, stored securely in database
}

def validate_hmac_signature(
    request: Request,
    tool: str,
    user: str,
    vendor_id: str = "techvendor"
) -> bool:
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")
    
    if not signature or not timestamp:
        return False
    
    # Prevent replay attacks (5 minute window)
    if abs(int(time.time()) - int(timestamp)) > 300:
        raise HTTPException(status_code=403, detail="Request expired")
    
    # Reconstruct expected signature
    payload = f"{tool}|{user}|{timestamp}"
    expected_signature = hmac.new(
        VENDOR_SECRETS[vendor_id].encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    return True
```

### 2. Client Libraries (45 min)
Update each client to add HMAC signatures:

**Python**:
```python
def borrow_with_security(self, tool: str, user: str):
    timestamp = str(int(time.time()))
    payload = f"{tool}|{user}|{timestamp}"
    signature = hmac.new(
        VENDOR_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-Vendor-ID": "techvendor"
    }
    # ... make request
```

### 3. Demo Script (30 min)
```bash
#!/bin/bash
# demo-security-attack.sh

echo "🎬 License Security Demo"
echo ""

echo "✅ Act 1: Normal checkout (with valid signature)"
python3 clients/python/example.py
echo ""

echo "🚨 Act 2: Attacker steals API key"
echo "   API_KEY=clsk_acme_stolen_key"
echo ""

echo "❌ Act 3: Naive attack (no signature)"
curl -X POST "http://localhost:8000/licenses/borrow" \
  -H "Content-Type: application/json" \
  -d '{"tool": "ECU Development Suite", "user": "hacker"}'
echo ""

echo "❌ Act 4: Sophisticated attack (wrong signature)"
python3 security-demos/fake-client.py
echo ""

echo "📊 Security layers demonstrated:"
echo "   1. ✅ HMAC signatures prevent unauthorized access"
echo "   2. ✅ Timestamp validation prevents replay attacks"
echo "   3. ✅ Vendor-specific secrets isolate products"
```

### 4. Visual Demo Page (15 min)
Add `/security-demo` page showing:
- Side-by-side comparison of legitimate vs attack requests
- Live "try to hack" form (always fails with educational messages)
- Animated flow showing signature validation
- Links to documentation

---

## 🎯 Best Demo Flow for Presentation

1. **Show normal operation** (30 seconds)
   - `./clients/python/run_example.sh`
   - License checked out ✅

2. **Show the attack** (2 minutes)
   - Open `demo-security-attack.sh`
   - Run through each scenario
   - Watch them all fail ❌

3. **Explain the architecture** (3 minutes)
   - Open `/security-demo` page
   - Walk through the 7 layers visually
   - Show code snippets

4. **Q&A with live demo** (5 minutes)
   - "What if someone reverse-engineers the secret?" → Show mTLS layer
   - "What if they clone the machine?" → Show TPM/hardware binding
   - "What about DDoS?" → Show rate limiting (already implemented!)

---

## 🚀 Quick Start

Want me to implement **Option 1 + Visual Demo**? I can have it ready in ~2 hours:

1. ✅ HMAC signature middleware in FastAPI
2. ✅ Updated Python client with signatures
3. ✅ Demo script showing attack scenarios
4. ✅ Visual `/security-demo` page
5. ✅ Documentation update

This gives you a **production-quality security demo** that's:
- ✅ Technically accurate
- ✅ Visually impressive
- ✅ Educational for automotive audiences
- ✅ Quick to run in presentations

**Should I build this?** 🎯

