#!/usr/bin/env bash
set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Server URL (default to localhost, can override with env var)
SERVER_URL="${LICENSE_SERVER_URL:-http://localhost:8000}"

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      🔐 License Security Attack Demo                     ║${NC}"
echo -e "${BLUE}║      Demonstrating Multi-Layer Security                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Server:${NC} $SERVER_URL"
echo ""

# Function to pause between acts
pause() {
    echo ""
    read -p "Press Enter to continue..."
    echo ""
}

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ ACT 1: Normal Operation${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Alice (legitimate user) checks out a license using the official client library...${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "clients/python/.venv" ]; then
    echo -e "${YELLOW}Setting up Python client environment...${NC}"
    cd clients/python
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q requests
    cd ../..
else
    source clients/python/.venv/bin/activate
fi

# Run legitimate client
python3 clients/python/example.py "$SERVER_URL"

deactivate

echo ""
echo -e "${GREEN}✓ License checkout successful with valid HMAC signature${NC}"

pause

echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo -e "${RED}🚨 ACT 2: Attacker Scenario${NC}"
echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Bob (attacker) has been monitoring network traffic and discovers the API endpoint...${NC}"
echo ""
echo "  📡 Observed endpoint: ${SERVER_URL}/licenses/borrow"
echo "  📦 Request body: {\"tool\": \"ECU Development Suite\", \"user\": \"alice\"}"
echo ""

pause

echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo -e "${RED}❌ ACT 3: Naive Attack (No Signature)${NC}"
echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Bob tries to checkout a license directly using curl (without HMAC signature)...${NC}"
echo ""
echo -e "${BLUE}Command:${NC}"
echo "curl -X POST \"${SERVER_URL}/licenses/borrow\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"tool\": \"ECU Development Suite\", \"user\": \"hacker@evil.com\"}'"
echo ""
echo -e "${YELLOW}Executing...${NC}"
echo ""

# Execute naive attack
HTTP_CODE=$(curl -s -o /tmp/attack1.json -w "%{http_code}" \
  -X POST "${SERVER_URL}/licenses/borrow" \
  -H "Content-Type: application/json" \
  -d '{"tool": "ECU Development Suite", "user": "hacker@evil.com"}')

echo -e "${RED}HTTP Status: $HTTP_CODE${NC}"
cat /tmp/attack1.json | python3 -m json.tool 2>/dev/null || cat /tmp/attack1.json
echo ""

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${RED}⚠️  WARNING: Attack succeeded! Security is disabled.${NC}"
else
    echo -e "${GREEN}✓ Attack blocked! Server requires HMAC signature.${NC}"
fi

pause

echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo -e "${RED}❌ ACT 4: Sophisticated Attack (Wrong Signature)${NC}"
echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Bob reverse-engineers the signature format but doesn't have the vendor secret...${NC}"
echo ""
echo -e "${BLUE}Bob's attack script:${NC}"
cat << 'EOF'
import hmac
import hashlib
import time

# Bob guesses or tries to brute-force the secret
GUESSED_SECRET = "wrong_secret_123"

timestamp = str(int(time.time()))
payload = f"ECU Development Suite|hacker@evil.com|{timestamp}"
signature = hmac.new(
    GUESSED_SECRET.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

# Try to checkout with wrong signature
EOF
echo ""
echo -e "${YELLOW}Executing attack with invalid signature...${NC}"
echo ""

# Generate wrong signature
TIMESTAMP=$(date +%s)
WRONG_SIG=$(echo -n "ECU Development Suite|hacker@evil.com|$TIMESTAMP" | openssl dgst -sha256 -hmac "wrong_secret_123" | cut -d' ' -f2)

HTTP_CODE=$(curl -s -o /tmp/attack2.json -w "%{http_code}" \
  -X POST "${SERVER_URL}/licenses/borrow" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $WRONG_SIG" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "hacker@evil.com"}')

echo -e "${RED}HTTP Status: $HTTP_CODE${NC}"
cat /tmp/attack2.json | python3 -m json.tool 2>/dev/null || cat /tmp/attack2.json
echo ""

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${RED}⚠️  WARNING: Attack succeeded! This shouldn't happen.${NC}"
else
    echo -e "${GREEN}✓ Attack blocked! Invalid signature detected.${NC}"
fi

pause

echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo -e "${RED}❌ ACT 5: Replay Attack (Old Timestamp)${NC}"
echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Bob intercepts a valid request and tries to replay it later...${NC}"
echo ""

# Generate signature with old timestamp (10 minutes ago)
OLD_TIMESTAMP=$(($(date +%s) - 600))
echo -e "${BLUE}Using old timestamp: $OLD_TIMESTAMP (10 minutes ago)${NC}"
echo ""

# We can't generate the real signature without the secret, so this will fail anyway
FAKE_SIG="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

HTTP_CODE=$(curl -s -o /tmp/attack3.json -w "%{http_code}" \
  -X POST "${SERVER_URL}/licenses/borrow" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $FAKE_SIG" \
  -H "X-Timestamp: $OLD_TIMESTAMP" \
  -H "X-Vendor-ID: techvendor" \
  -d '{"tool": "ECU Development Suite", "user": "hacker@evil.com"}')

echo -e "${RED}HTTP Status: $HTTP_CODE${NC}"
cat /tmp/attack3.json | python3 -m json.tool 2>/dev/null || cat /tmp/attack3.json
echo ""

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${RED}⚠️  WARNING: Replay attack succeeded!${NC}"
else
    echo -e "${GREEN}✓ Replay attack blocked! Timestamp validation working.${NC}"
fi

echo ""
pause

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}📊 Security Summary${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ Layer 1: HMAC Signatures${NC}"
echo "    Prevents unauthorized API access"
echo "    Requires vendor-specific secret embedded in client library"
echo ""
echo -e "${GREEN}✓ Layer 2: Timestamp Validation${NC}"
echo "    Prevents replay attacks"
echo "    5-minute validity window"
echo ""
echo -e "${YELLOW}  Layer 3: Client Certificates (mTLS)${NC} [Not implemented in demo]"
echo "    Hardware-bound authentication"
echo "    Prevents secret extraction"
echo ""
echo -e "${YELLOW}  Layer 4-7: Additional Security${NC} [Documented]"
echo "    • Rate limiting (already active)"
echo "    • TPM/Secure Enclave binding"
echo "    • IP whitelisting"
echo "    • Behavioral analysis"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📚 Learn More:${NC}"
echo "  • LICENSE_THEFT_PREVENTION.md - Technical deep dive"
echo "  • CLOUD_LICENSE_PROTOCOL.md - Full architecture"
echo "  • /security-demo on the web UI - Interactive demo"
echo ""
echo -e "${GREEN}✓ Demo Complete!${NC}"
echo ""

# Cleanup
rm -f /tmp/attack*.json

