#!/usr/bin/env bash
set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

APP_NAME="license-server-demo"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Reset Fly.io Database - Fresh Seed Data               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}⚠️  This will DELETE the database and reseed with fresh data${NC}"
echo -e "${YELLOW}⚠️  All existing borrows, overage charges, etc. will be LOST${NC}"
echo ""
echo -e "${GREEN}New seed data will include:${NC}"
echo "  • ECU Development Suite (20 licenses, 5 commit, 15 overage)"
echo "  • GreenHills Multi IDE (15 licenses, 10 commit, 5 overage)"
echo "  • AUTOSAR Configuration Tool (12 licenses, 8 commit, 4 overage)"
echo "  • CAN Bus Analyzer Pro (10 licenses, 10 commit, 0 overage)"
echo "  • Model-Based Design Studio (18 licenses, 6 commit, 12 overage)"
echo ""
read -p "Continue? Type 'yes' to proceed: " -r
echo

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${RED}❌ Aborted${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Method: SSH into machine and delete database file${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}1️⃣  Checking app status...${NC}"
if flyctl status -a "$APP_NAME" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ App is running${NC}"
else
    echo -e "${RED}✗ App not found or not running${NC}"
    echo "   Try: flyctl status -a $APP_NAME"
    exit 1
fi
echo ""

echo -e "${BLUE}2️⃣  Attempting to remove database file via SSH...${NC}"
if flyctl ssh console -a "$APP_NAME" -C "rm -f /data/licenses.db" 2>/dev/null; then
    echo -e "${GREEN}✓ Database file removed${NC}"
else
    echo -e "${YELLOW}⚠️  SSH method failed. Trying alternative...${NC}"
    echo ""
    echo -e "${BLUE}Alternative: Using fly deploy to force refresh${NC}"
    
    # Just restart the app - on next startup it will see missing DB and reseed
    echo -e "${BLUE}Restarting app (this will trigger reseed)...${NC}"
    flyctl apps restart "$APP_NAME"
    echo -e "${GREEN}✓ Restart initiated${NC}"
fi
echo ""

echo -e "${BLUE}3️⃣  Restarting app to trigger database reseed...${NC}"
flyctl apps restart "$APP_NAME"
echo -e "${GREEN}✓ App restarting${NC}"
echo ""

echo -e "${BLUE}4️⃣  Waiting for app to come back up (15 seconds)...${NC}"
for i in {15..1}; do
    echo -ne "   ${i}s remaining...\r"
    sleep 1
done
echo -e "   ${GREEN}✓ Done waiting${NC}               "
echo ""

echo -e "${BLUE}5️⃣  Verifying new database...${NC}"
echo ""

MAX_RETRIES=5
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s -f https://${APP_NAME}.fly.dev/licenses/status > /tmp/flyio_status.json 2>&1; then
        echo -e "${GREEN}✓ App is responding${NC}"
        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}📦 Fresh Seed Data:${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        
        # Parse and display nicely
        if command -v jq &> /dev/null; then
            cat /tmp/flyio_status.json | jq -r '.[] | "  ✓ \(.tool):\n    Total: \(.total) | Commit: \(.commit_qty) | Overage: \(.max_overage)\n    Prices: $\(.commit_price | floor) commit + $\(.overage_price_per_license | floor)/license\n"'
        else
            cat /tmp/flyio_status.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
for d in data:
    print(f\"  ✓ {d['tool']}:\")
    print(f\"    Total: {d['total']} | Commit: {d['commit_qty']} | Overage: {d['max_overage']}\")
    print(f\"    Prices: \${d['commit_price']:.0f} commit + \${d['overage_price_per_license']:.0f}/license\")
    print()
"
        fi
        
        rm -f /tmp/flyio_status.json
        break
    else
        RETRY=$((RETRY + 1))
        if [ $RETRY -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}⏳ App not ready yet, retrying in 5s... (attempt $RETRY/$MAX_RETRIES)${NC}"
            sleep 5
        else
            echo -e "${RED}✗ App still not responding after $MAX_RETRIES attempts${NC}"
            echo ""
            echo -e "${YELLOW}Check logs:${NC}"
            echo "  flyctl logs -a $APP_NAME"
            echo ""
            exit 1
        fi
    fi
done

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Database Reset Complete!                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}🌐 Live URLs:${NC}"
echo "  • Home:         https://${APP_NAME}.fly.dev/"
echo "  • Dashboard:    https://${APP_NAME}.fly.dev/dashboard"
echo "  • Vendor Portal: https://${APP_NAME}.fly.dev/vendor"
echo "  • Real-Time:    https://${APP_NAME}.fly.dev/realtime"
echo "  • API Status:   https://${APP_NAME}.fly.dev/licenses/status"
echo ""

echo -e "${GREEN}📊 Monitor:${NC}"
echo "  • Logs:    flyctl logs -a $APP_NAME"
echo "  • Status:  flyctl status -a $APP_NAME"
echo "  • SSH:     flyctl ssh console -a $APP_NAME"
echo ""

