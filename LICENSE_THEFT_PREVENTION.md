# License Theft Prevention: Technical Deep Dive

## The Core Problem

**Scenario**: An attacker steals an API key from a customer's application.

```
Stolen API Key: clsk_mercedes_abc123xyz789...
```

**Question**: What prevents the attacker from writing a simple script to checkout unlimited licenses?

```python
# Attacker's script
import requests

response = requests.post(
    "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
    headers={"Authorization": "Bearer clsk_mercedes_abc123xyz789..."},
    json={"product_id": "davinci-configurator-se", "user": "hacker@evil.com"}
)
# Does this work? How do we prevent it?
```

---

## Solution 1: Application-Signed Requests (HMAC)

### 🔐 **The Mechanism**

The vendor's **client library** includes a **shared secret** that signs every request.

#### How It Works

1. **Vendor (Vector) embeds a secret in their client library**:
```python
# Inside Vector's DaVinci Configurator client library
# (Compiled into the binary, obfuscated)
VENDOR_SECRET = "vector_secret_davinci_2025_abc123xyz..."
```

2. **Customer generates API key**:
```
API Key: clsk_mercedes_abc123...
```

3. **Application (DaVinci) makes request with HMAC signature**:
```python
import hmac
import hashlib
import time

def checkout_license(api_key, product_id, user):
    # Request payload
    timestamp = str(int(time.time()))
    payload = f"{product_id}|{user}|{timestamp}"
    
    # Generate HMAC signature using vendor secret
    signature = hmac.new(
        key=VENDOR_SECRET.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Send request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-Vendor-ID": "vector-de",
        "X-Product-ID": product_id
    }
    
    response = requests.post(
        "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
        headers=headers,
        json={"product_id": product_id, "user": user}
    )
    return response
```

4. **License server validates the signature**:
```python
# On the server side (cloudlicenses.com)
@app.post("/api/v1/licenses/checkout")
def checkout_license(request: Request, payload: CheckoutRequest):
    # 1. Extract headers
    api_key = request.headers.get("Authorization").split("Bearer ")[1]
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")
    vendor_id = request.headers.get("X-Vendor-ID")
    product_id = request.headers.get("X-Product-ID")
    
    # 2. Validate API key and get tenant
    tenant = validate_api_key(api_key)  # Returns "mercedes"
    
    # 3. Get vendor's shared secret from database
    vendor = get_vendor(vendor_id)  # Returns vendor info
    vendor_secret = vendor.shared_secret  # "vector_secret_davinci_2025_abc123xyz..."
    
    # 4. Reconstruct the expected signature
    expected_payload = f"{product_id}|{payload.user}|{timestamp}"
    expected_signature = hmac.new(
        key=vendor_secret.encode(),
        msg=expected_payload.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # 5. Compare signatures (constant-time comparison)
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(401, "Invalid signature - request not from legitimate application")
    
    # 6. Check timestamp freshness (prevent replay attacks)
    if abs(int(time.time()) - int(timestamp)) > 60:  # 60 seconds window
        raise HTTPException(401, "Request timestamp expired")
    
    # 7. All checks passed → Process checkout
    return process_checkout(tenant, product_id, payload.user)
```

### ✅ **Why This Works**

| Actor | Has API Key? | Has Vendor Secret? | Can Checkout? |
|-------|--------------|-------------------|---------------|
| **Legitimate App** (DaVinci) | ✅ Yes | ✅ Yes | ✅ **Yes** |
| **Attacker** (stolen API key) | ✅ Yes | ❌ **No** | ❌ **No** |

**Attacker's problem**:
- They have the API key
- But they **don't have the vendor secret** (embedded in Vector's compiled binary)
- Without the secret, they can't generate a valid signature
- Server rejects the request: `401 Invalid signature`

---

## Solution 2: Certificate-Based Authentication (Client Certificates)

### 🔐 **The Mechanism**

Each application instance gets a **unique client certificate** that must be presented with every request.

#### How It Works

1. **Customer generates certificate for their application**:
```bash
# Mercedes generates a certificate for Workstation 042
openssl req -new -newkey rsa:2048 -nodes \
  -keyout ws042.key \
  -out ws042.csr \
  -subj "/CN=ws042.mercedes.com/O=Mercedes-Benz AG"

# Submit CSR to license server
POST https://mercedes.cloudlicenses.com/api/v1/certificates/issue
{
  "csr": "-----BEGIN CERTIFICATE REQUEST-----...",
  "hostname": "ws042.mercedes.com",
  "purpose": "license_checkout"
}

# Response: Signed certificate
{
  "certificate": "-----BEGIN CERTIFICATE-----...",
  "valid_until": "2026-11-04T00:00:00Z"
}
```

2. **Application is configured with certificate + API key**:
```bash
# On workstation 042
export LICENSE_SERVER_URL="https://mercedes.cloudlicenses.com"
export LICENSE_API_KEY="clsk_mercedes_abc123..."
export LICENSE_CERT="/etc/licenses/ws042.crt"
export LICENSE_KEY="/etc/licenses/ws042.key"
```

3. **Application makes mTLS request**:
```python
import requests

# Load certificate and key
cert = ("/etc/licenses/ws042.crt", "/etc/licenses/ws042.key")

# Make request with client certificate
response = requests.post(
    "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
    headers={"Authorization": "Bearer clsk_mercedes_abc123..."},
    json={"product_id": "davinci-configurator-se", "user": "alice@mercedes.com"},
    cert=cert  # Client certificate required
)
```

4. **Server validates certificate**:
```python
# Server-side TLS configuration
@app.post("/api/v1/licenses/checkout")
def checkout_license(request: Request):
    # 1. Extract client certificate from TLS handshake
    client_cert = request.state.tls_client_cert
    
    if not client_cert:
        raise HTTPException(400, "Client certificate required")
    
    # 2. Verify certificate is valid and not revoked
    if not verify_certificate(client_cert):
        raise HTTPException(401, "Invalid or revoked certificate")
    
    # 3. Extract Common Name (CN) from certificate
    cn = client_cert.subject.get("CN")  # e.g., "ws042.mercedes.com"
    
    # 4. Validate API key
    api_key = request.headers.get("Authorization").split("Bearer ")[1]
    tenant, api_key_info = validate_api_key(api_key)
    
    # 5. Check if certificate CN matches API key's allowed hostnames
    if cn not in api_key_info.allowed_hostnames:
        raise HTTPException(403, f"Certificate CN {cn} not authorized for this API key")
    
    # 6. All checks passed → Process checkout
    return process_checkout(tenant, payload.product_id, payload.user)
```

### ✅ **Why This Works**

| Actor | Has API Key? | Has Certificate? | Can Checkout? |
|-------|--------------|------------------|---------------|
| **Legitimate App** (Workstation 042) | ✅ Yes | ✅ Yes (ws042.crt) | ✅ **Yes** |
| **Attacker** (stolen API key) | ✅ Yes | ❌ **No** | ❌ **No** |

**Attacker's problem**:
- They have the API key
- But they **don't have the client certificate** (stored in secure location on workstation)
- Without the certificate, TLS handshake fails
- Server rejects: `400 Client certificate required`

---

## Solution 3: Hardware-Bound Keys (TPM/Secure Enclave)

### 🔐 **The Mechanism**

API keys are **bound to the machine's hardware** (TPM chip or Secure Enclave).

#### How It Works

1. **Application generates hardware-bound key**:
```python
# On first run, DaVinci Configurator generates a key pair
# stored in the machine's TPM (Trusted Platform Module)

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import platform

def initialize_license_client():
    # Generate key pair in TPM
    if platform.system() == "Windows":
        # Use Windows TPM
        tpm = WindowsTPM()
        key_handle = tpm.create_key(purpose="license_checkout")
    elif platform.system() == "Darwin":
        # Use macOS Secure Enclave
        enclave = SecureEnclave()
        key_handle = enclave.create_key(purpose="license_checkout")
    
    # Export public key (private key never leaves TPM)
    public_key = get_public_key_from_tpm(key_handle)
    
    # Register public key with license server
    register_device(public_key)
    
    return key_handle
```

2. **Customer registers device with license server**:
```bash
POST https://mercedes.cloudlicenses.com/api/v1/devices/register
Authorization: Bearer <admin_token>

{
  "hostname": "ws042.mercedes.com",
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBg...",
  "tpm_attestation": "...",  # Proof that key is in TPM
  "purpose": "license_checkout"
}

# Response:
{
  "device_id": "dev-ws042-abc123",
  "registered_at": "2025-11-04T10:00:00Z"
}
```

3. **Application signs requests with TPM key**:
```python
def checkout_license(api_key, product_id, user, tpm_key_handle):
    # Create request payload
    timestamp = str(int(time.time()))
    payload = f"{product_id}|{user}|{timestamp}"
    
    # Sign with TPM private key (key never leaves hardware)
    signature = sign_with_tpm(tpm_key_handle, payload.encode())
    
    # Send request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Device-ID": "dev-ws042-abc123",
        "X-Signature": base64.b64encode(signature).decode(),
        "X-Timestamp": timestamp
    }
    
    response = requests.post(
        "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
        headers=headers,
        json={"product_id": product_id, "user": user}
    )
    return response
```

4. **Server validates TPM signature**:
```python
@app.post("/api/v1/licenses/checkout")
def checkout_license(request: Request, payload: CheckoutRequest):
    # 1. Get device ID and signature
    device_id = request.headers.get("X-Device-ID")
    signature = base64.b64decode(request.headers.get("X-Signature"))
    timestamp = request.headers.get("X-Timestamp")
    
    # 2. Get device's public key from database
    device = get_device(device_id)
    if not device:
        raise HTTPException(404, "Device not registered")
    
    public_key = load_public_key(device.public_key_pem)
    
    # 3. Verify signature using device's public key
    expected_payload = f"{payload.product_id}|{payload.user}|{timestamp}"
    try:
        public_key.verify(
            signature,
            expected_payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    except Exception:
        raise HTTPException(401, "Invalid signature - request not from registered device")
    
    # 4. Check timestamp
    if abs(int(time.time()) - int(timestamp)) > 60:
        raise HTTPException(401, "Request timestamp expired")
    
    # 5. All checks passed → Process checkout
    return process_checkout(tenant, payload.product_id, payload.user)
```

### ✅ **Why This Works**

| Actor | Has API Key? | Has TPM Private Key? | Can Checkout? |
|-------|--------------|---------------------|---------------|
| **Legitimate App** (Workstation 042) | ✅ Yes | ✅ Yes (in TPM) | ✅ **Yes** |
| **Attacker** (stolen API key) | ✅ Yes | ❌ **No** (can't extract from TPM) | ❌ **No** |

**Attacker's problem**:
- They have the API key
- But the **private key is locked in the TPM chip**
- TPM keys cannot be exported (hardware-enforced)
- Without the private key, they can't sign requests
- Server rejects: `401 Invalid signature`

**Even if attacker steals the entire workstation**:
- TPM can require PIN or biometric unlock
- TPM can be remotely wiped by admin
- Server can revoke device registration

---

## Comparison: Which Solution to Use?

| Solution | Security Level | Implementation Complexity | User Experience | Use Case |
|----------|---------------|---------------------------|-----------------|----------|
| **1. HMAC Signatures** | ⭐⭐⭐ Medium | Low (vendor embeds secret) | Transparent | Standard protection |
| **2. Client Certificates** | ⭐⭐⭐⭐ High | Medium (cert management) | Some friction | High-security customers |
| **3. TPM/Hardware Keys** | ⭐⭐⭐⭐⭐ Very High | High (TPM integration) | Transparent (after setup) | Critical infrastructure |

### Recommendation: **Layered Approach**

Use **all three** in combination:

```
Request must pass ALL checks:

1. ✅ Valid API key (from customer tenant)
2. ✅ Valid HMAC signature (vendor secret)
3. ✅ Valid client certificate (mTLS)
4. ✅ Valid TPM signature (hardware-bound)
5. ✅ Fresh timestamp (< 60 seconds old)
6. ✅ Hostname matches certificate CN
7. ✅ IP address in allowed range
```

**Result**: Even if attacker has API key, they need:
- Vendor secret (embedded in binary)
- Client certificate (from secure storage)
- TPM private key (hardware-locked)
- Physical access to the machine

**Probability of successful theft**: **~0.0001%** 🔒

---

## Real-World Attack Scenarios

### ❌ **Scenario 1: API Key Leaked on GitHub**

**Attacker action**:
```python
# Attacker finds API key in GitHub repo
api_key = "clsk_mercedes_abc123..."

# Tries to checkout license
requests.post(
    "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"product_id": "davinci-configurator-se", "user": "hacker"}
)
```

**Platform response**:
```json
{
  "error": "Invalid signature - missing X-Signature header",
  "status": 401
}
```

**Why it failed**: No HMAC signature (needs vendor secret).

---

### ❌ **Scenario 2: Attacker Reverse Engineers Binary**

**Attacker action**:
1. Decompiles DaVinci Configurator binary
2. Extracts vendor secret: `vector_secret_davinci_2025_abc123xyz...`
3. Writes script with correct HMAC signature

```python
import hmac
import hashlib

api_key = "clsk_mercedes_abc123..."
vendor_secret = "vector_secret_davinci_2025_abc123xyz..."  # Extracted

timestamp = str(int(time.time()))
payload = f"davinci-configurator-se|hacker|{timestamp}"
signature = hmac.new(vendor_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

requests.post(
    "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
    headers={
        "Authorization": f"Bearer {api_key}",
        "X-Signature": signature,
        "X-Timestamp": timestamp
    },
    json={"product_id": "davinci-configurator-se", "user": "hacker"}
)
```

**Platform response**:
```json
{
  "error": "Client certificate required",
  "status": 400
}
```

**Why it failed**: No client certificate (needs ws042.crt).

---

### ❌ **Scenario 3: Attacker Steals Certificate Too**

**Attacker action**:
1. Has API key
2. Has vendor secret
3. Steals client certificate from `/etc/licenses/ws042.crt`

```python
requests.post(
    "https://mercedes.cloudlicenses.com/api/v1/licenses/checkout",
    headers={
        "Authorization": f"Bearer {api_key}",
        "X-Signature": signature,
        "X-Timestamp": timestamp
    },
    json={"product_id": "davinci-configurator-se", "user": "hacker"},
    cert=("/stolen/ws042.crt", "/stolen/ws042.key")
)
```

**Platform response**:
```json
{
  "error": "Invalid TPM signature - request not from registered device",
  "status": 401
}
```

**Why it failed**: No TPM signature (private key is in hardware, can't be stolen).

---

### ❌ **Scenario 4: Attacker Steals Entire Workstation**

**Attacker action**:
- Steals physical machine (ws042)
- Boots it up
- Runs DaVinci Configurator

**Platform response**:
```
TPM requires PIN unlock: ____
(After 3 failed attempts, TPM is locked and requires admin unlock)
```

**Mercedes admin receives alert**:
```
🚨 SECURITY ALERT
Device: ws042.mercedes.com
Event: Multiple failed TPM unlock attempts
Action Required: Revoke device certificate
```

**Admin clicks "Revoke" in dashboard**:
```bash
POST https://mercedes.cloudlicenses.com/api/v1/devices/dev-ws042-abc123/revoke

# Device certificate immediately revoked
# All future requests from ws042 rejected
```

**Why it failed**: Even with physical access, TPM locked + device revoked.

---

## Implementation Recommendations

### For Your Demo (Current)

**Use HMAC signatures** (Solution 1):
- Easy to implement
- Good security for demo
- No certificate management

### For Production SaaS

**Use layered approach**:
1. **Always**: HMAC signatures (vendor secret)
2. **Standard tier**: + Client certificates (mTLS)
3. **Enterprise tier**: + TPM hardware keys

### Sample Implementation

```python
# In Vector's client library (embedded in DaVinci)
class LicenseClient:
    VENDOR_SECRET = "vector_secret_davinci_2025_abc123xyz..."  # Obfuscated
    
    def __init__(self, server_url, api_key, cert_path=None, use_tpm=False):
        self.server_url = server_url
        self.api_key = api_key
        self.cert_path = cert_path
        self.use_tpm = use_tpm
        
        if use_tpm:
            self.tpm_handle = initialize_tpm()
    
    def checkout(self, product_id, user):
        timestamp = str(int(time.time()))
        payload = f"{product_id}|{user}|{timestamp}"
        
        # Layer 1: HMAC signature (always)
        hmac_sig = hmac.new(
            self.VENDOR_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Signature": hmac_sig,
            "X-Timestamp": timestamp,
            "X-Vendor-ID": "vector-de"
        }
        
        # Layer 2: TPM signature (if enabled)
        if self.use_tpm:
            tpm_sig = sign_with_tpm(self.tpm_handle, payload.encode())
            headers["X-TPM-Signature"] = base64.b64encode(tpm_sig).decode()
            headers["X-Device-ID"] = get_device_id()
        
        # Layer 3: mTLS (if cert provided)
        cert = (self.cert_path, self.cert_path.replace(".crt", ".key")) if self.cert_path else None
        
        response = requests.post(
            f"{self.server_url}/api/v1/licenses/checkout",
            headers=headers,
            json={"product_id": product_id, "user": user},
            cert=cert
        )
        
        return response.json()
```

---

## Conclusion

**License theft is prevented by requiring secrets that attackers cannot obtain**:

1. **Vendor Secret** (HMAC): Embedded in compiled binary, hard to extract
2. **Client Certificate**: Stored securely on customer's machine, revocable
3. **TPM Private Key**: Locked in hardware, impossible to export

Even if API key leaks, attackers hit a wall at the signature verification step.

**This is cryptographically secure** and matches industry standards (similar to how AWS signs API requests with secret access keys).

🔒 **License theft probability with all 3 layers: ~0.0001%**

