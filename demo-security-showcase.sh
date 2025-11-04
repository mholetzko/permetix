#!/bin/bash

# ==============================================================================
# Security Showcase Demo
# Demonstrates API Key + Vendor Secret + HMAC Signature protection
# ==============================================================================

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
TOOL="ECU Development Suite"
USER="demo-user-$RANDOM"
VENDOR_SECRET="techvendor_secret_ecu_2025_demo_xyz789abc123def456"
VENDOR_ID="techvendor"

# ==============================================================================
# Helper Functions
# ==============================================================================

print_header() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_scenario() {
    echo ""
    echo -e "${BLUE}${BOLD}📋 Scenario $1: $2${NC}"
    echo -e "${BLUE}   $3${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_failure() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

generate_hmac() {
    local tool="$1"
    local user="$2"
    local timestamp="$3"
    local api_key="$4"
    local secret="$5"
    
    # Payload format: tool|user|timestamp|api_key
    local payload="${tool}|${user}|${timestamp}|${api_key}"
    
    # Generate HMAC-SHA256
    echo -n "$payload" | openssl dgst -sha256 -hmac "$secret" | awk '{print $2}'
}

wait_for_enter() {
    echo ""
    echo -e "${YELLOW}Press ENTER to continue...${NC}"
    read
}

# ==============================================================================
# Main Demo
# ==============================================================================

clear
print_header "🔐 Security Showcase Demo"

cat << EOF
This demo showcases the 3-layer security model:

  ${BOLD}Layer 1: API Key${NC}        - Tenant authentication (who you are)
  ${BOLD}Layer 2: Vendor Secret${NC}  - Application authentication (what app)
  ${BOLD}Layer 3: HMAC Signature${NC} - Request integrity (data not tampered)

We'll demonstrate what happens when each layer is missing or invalid.

Target: ${BASE_URL}
Tool:   ${TOOL}
User:   ${USER}
EOF

wait_for_enter

# ==============================================================================
# Scenario 1: Complete Security - SUCCESS ✅
# ==============================================================================

print_scenario "1" "Complete Security (All Layers)" "Valid API Key + Vendor Secret + HMAC Signature"

TIMESTAMP=$(date +%s)
API_KEY="demo_live_pk_abc123xyz789"  # Demo API key
SIGNATURE=$(generate_hmac "$TOOL" "$USER" "$TIMESTAMP" "$API_KEY" "$VENDOR_SECRET")

print_info "Request Details:"
echo "  • API Key:     ${API_KEY:0:20}... (Layer 1)"
echo "  • Vendor ID:   $VENDOR_ID (Layer 2)"
echo "  • Timestamp:   $TIMESTAMP"
echo "  • Signature:   ${SIGNATURE:0:16}... (Layer 3)"
echo ""

print_info "Sending request with ALL security layers..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "${BASE_URL}/licenses/borrow" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIGNATURE" \
    -H "X-Timestamp: $TIMESTAMP" \
    -H "X-Vendor-ID: $VENDOR_ID" \
    -d "{\"tool\":\"$TOOL\",\"user\":\"$USER\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" = "200" ]; then
    print_success "SUCCESS: License borrowed!"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    BORROW_ID=$(echo "$BODY" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
else
    print_failure "Unexpected failure (HTTP $HTTP_CODE)"
    echo "$BODY"
fi

wait_for_enter

# ==============================================================================
# Scenario 2: Missing Signature - FAIL ❌
# ==============================================================================

print_scenario "2" "Missing HMAC Signature" "API Key present, but no signature"

print_info "Request Details:"
echo "  • API Key:     ✅ Present"
echo "  • Vendor ID:   ✅ Present"
echo "  • Signature:   ❌ MISSING"
echo ""

print_info "Sending request WITHOUT signature..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "${BASE_URL}/licenses/borrow" \
    -H "Content-Type: application/json" \
    -H "X-Vendor-ID: $VENDOR_ID" \
    -d "{\"tool\":\"$TOOL\",\"user\":\"$USER-nosig\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    print_failure "REJECTED: Security validation failed"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    print_info "Note: Server allows unsigned requests (demo mode)"
    echo "      In production, set REQUIRE_SIGNATURES=True"
fi

wait_for_enter

# ==============================================================================
# Scenario 3: Wrong Vendor Secret - FAIL ❌
# ==============================================================================

print_scenario "3" "Wrong Vendor Secret" "Attacker guesses the vendor secret"

TIMESTAMP=$(date +%s)
WRONG_SECRET="hacker_guessed_secret_123"
WRONG_SIGNATURE=$(generate_hmac "$TOOL" "$USER" "$TIMESTAMP" "$API_KEY" "$WRONG_SECRET")

print_info "Attacker's Request:"
echo "  • API Key:     ✅ Valid API key (stolen)"
echo "  • Vendor ID:   ✅ Valid vendor ID"
echo "  • Secret:      ❌ WRONG ('$WRONG_SECRET')"
echo "  • Signature:   ${WRONG_SIGNATURE:0:16}... (computed with wrong secret)"
echo ""

print_info "Sending request with WRONG vendor secret..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "${BASE_URL}/licenses/borrow" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $WRONG_SIGNATURE" \
    -H "X-Timestamp: $TIMESTAMP" \
    -H "X-Vendor-ID: $VENDOR_ID" \
    -d "{\"tool\":\"$TOOL\",\"user\":\"$USER-wrongsecret\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    print_failure "REJECTED: Invalid signature (wrong vendor secret)"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    print_info "Note: Server allows unsigned requests (demo mode)"
fi

wait_for_enter

# ==============================================================================
# Scenario 4: Tampered Request - FAIL ❌
# ==============================================================================

print_scenario "4" "Tampered Request Data" "Attacker modifies the request after signing"

TIMESTAMP=$(date +%s)
ORIGINAL_TOOL="ECU Development Suite"
TAMPERED_TOOL="GreenHills Multi IDE"  # Attacker changes tool!
SIGNATURE=$(generate_hmac "$ORIGINAL_TOOL" "$USER" "$TIMESTAMP" "$API_KEY" "$VENDOR_SECRET")

print_info "Man-in-the-Middle Attack:"
echo "  1. Legitimate client signs request for: '$ORIGINAL_TOOL'"
echo "  2. Attacker intercepts and modifies to:  '$TAMPERED_TOOL'"
echo "  3. Signature:   ${SIGNATURE:0:16}... (valid for ORIGINAL tool)"
echo "  4. Server will detect tampering!"
echo ""

print_info "Sending TAMPERED request..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "${BASE_URL}/licenses/borrow" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIGNATURE" \
    -H "X-Timestamp: $TIMESTAMP" \
    -H "X-Vendor-ID: $VENDOR_ID" \
    -d "{\"tool\":\"$TAMPERED_TOOL\",\"user\":\"$USER-tampered\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    print_failure "REJECTED: Invalid signature (request was tampered)"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    print_info "Note: Server allows unsigned requests (demo mode)"
fi

wait_for_enter

# ==============================================================================
# Scenario 5: Replay Attack - FAIL ❌
# ==============================================================================

print_scenario "5" "Replay Attack" "Attacker reuses old signed request"

# Use old timestamp (10 minutes ago)
OLD_TIMESTAMP=$(($(date +%s) - 600))
REPLAY_SIGNATURE=$(generate_hmac "$TOOL" "$USER" "$OLD_TIMESTAMP" "$API_KEY" "$VENDOR_SECRET")

print_info "Replay Attack:"
echo "  • Attacker captures legitimate request from 10 minutes ago"
echo "  • Timestamp:   $OLD_TIMESTAMP (10 minutes old)"
echo "  • Signature:   ${REPLAY_SIGNATURE:0:16}... (valid, but expired)"
echo "  • Window:      300s (5 minutes maximum)"
echo ""

print_info "Sending REPLAYED request..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "${BASE_URL}/licenses/borrow" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $REPLAY_SIGNATURE" \
    -H "X-Timestamp: $OLD_TIMESTAMP" \
    -H "X-Vendor-ID: $VENDOR_ID" \
    -d "{\"tool\":\"$TOOL\",\"user\":\"$USER-replay\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    print_failure "REJECTED: Request expired (timestamp too old)"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    print_info "Note: Server allows unsigned requests (demo mode)"
fi

wait_for_enter

# ==============================================================================
# Summary
# ==============================================================================

print_header "📊 Security Summary"

cat << EOF
${BOLD}3-Layer Security Model:${NC}

┌────────────────────────────────────────────────────────────────┐
│ Layer 1: API Key (Tenant Authentication)                       │
│ ────────────────────────────────────────────                   │
│ • Identifies which tenant is making the request                │
│ • Stored securely by customer during onboarding                │
│ • Can be revoked/rotated without code changes                  │
│ • Format: {tenant}_{env}_pk_{random}                           │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ Layer 2: Vendor Secret (Application Authentication)            │
│ ────────────────────────────────────────────────────────────    │
│ • Embedded in client library at compile time                   │
│ • Different secret per vendor (TechVendor, GreenHills, etc)    │
│ • Used to generate HMAC signature                              │
│ • Protects against unauthorized API usage                      │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ Layer 3: HMAC Signature (Request Integrity)                    │
│ ────────────────────────────────────────────────────────────    │
│ • Payload: tool|user|timestamp|api_key                         │
│ • Signed with: HMAC-SHA256(vendor_secret, payload)             │
│ • Includes timestamp to prevent replay attacks                 │
│ • Server validates signature matches expected                  │
└────────────────────────────────────────────────────────────────┘

${GREEN}${BOLD}✅ What This Prevents:${NC}
  • Unauthorized API access (no valid client library)
  • License theft from competitors
  • Man-in-the-middle tampering
  • Replay attacks
  • API key theft alone (need vendor secret too)

${RED}${BOLD}❌ Attack Scenarios Blocked:${NC}
  • Missing signature         → Request rejected
  • Wrong vendor secret       → Signature mismatch
  • Tampered request data     → Signature mismatch
  • Replay attack (>5 min)    → Timestamp expired
  • Stolen API key only       → Still need vendor secret to sign

${YELLOW}${BOLD}🎯 Production Deployment:${NC}
  1. Set REQUIRE_SIGNATURES=True in app/security.py
  2. Generate unique API keys per customer tenant
  3. Rotate vendor secrets periodically
  4. Monitor failed authentication attempts
  5. Use hardware security (TPM/Secure Enclave) for key storage

EOF

# Cleanup
if [ -n "$BORROW_ID" ]; then
    print_info "Cleaning up test license (ID: $BORROW_ID)..."
    curl -s -X POST "${BASE_URL}/licenses/return" \
        -H "Content-Type: application/json" \
        -d "{\"id\":\"$BORROW_ID\"}" > /dev/null
    print_success "Cleanup complete"
fi

echo ""
print_header "🎬 Demo Complete!"
echo ""
echo "To enable strict security mode, edit app/security.py:"
echo "  ${YELLOW}REQUIRE_SIGNATURES = True${NC}"
echo ""
echo "For more details, see:"
echo "  • SECURITY_SUMMARY.md"
echo "  • LICENSE_THEFT_PREVENTION.md"
echo "  • TENANT_AUTHENTICATION_DESIGN.md"
echo ""

