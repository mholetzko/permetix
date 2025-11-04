#!/usr/bin/env bash
set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   License Server Stress Test Launcher                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}✗ Cargo (Rust) is not installed${NC}"
    echo ""
    echo "Please install Rust from: https://rustup.rs/"
    echo "Or run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo -e "${GREEN}✓ Cargo found${NC}"
echo ""

# Build the stress test tool
echo -e "${BLUE}🔨 Building stress test tool...${NC}"
cd "${SCRIPT_DIR}"
cargo build --release
echo -e "${GREEN}✅ Build complete${NC}"
echo ""

# Select deployment target
echo -e "${BLUE}Select deployment target:${NC}"
echo "1) Localhost (http://localhost:8000)"
echo "2) Fly.io Production (https://license-server-demo.fly.dev)"
echo "3) Custom URL"
echo ""
read -p "Enter choice [1-3]: " target_choice

case $target_choice in
    1)
        SERVER_URL="http://localhost:8000"
        echo -e "${BLUE}→ Using localhost${NC}"
        ;;
    2)
        SERVER_URL="https://license-server-demo.fly.dev"
        echo -e "${BLUE}→ Using Fly.io production${NC}"
        ;;
    3)
        read -p "Enter custom URL: " SERVER_URL
        echo -e "${BLUE}→ Using custom URL: ${SERVER_URL}${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice, using localhost${NC}"
        SERVER_URL="http://localhost:8000"
        ;;
esac

echo ""

# Select test profile
echo -e "${BLUE}Select test profile:${NC}"
echo "1) Light Load    (5 workers, 20 ops each = 100 total ops)"
echo "2) Medium Load   (10 workers, 50 ops each = 500 total ops)"
echo "3) Heavy Load    (20 workers, 100 ops each = 2000 total ops)"
echo "4) Extreme Load  (50 workers, 200 ops each = 10000 total ops)"
echo "5) Custom        (specify your own parameters)"
echo ""
read -p "Enter choice [1-5]: " profile_choice

case $profile_choice in
    1)
        WORKERS=5
        OPS=20
        HOLD_TIME=1
        RAMP_UP=0
        ;;
    2)
        WORKERS=10
        OPS=50
        HOLD_TIME=1
        RAMP_UP=2
        ;;
    3)
        WORKERS=20
        OPS=100
        HOLD_TIME=1
        RAMP_UP=5
        ;;
    4)
        WORKERS=50
        OPS=200
        HOLD_TIME=1
        RAMP_UP=10
        ;;
    5)
        read -p "Number of workers: " WORKERS
        read -p "Operations per worker: " OPS
        read -p "Hold time (seconds): " HOLD_TIME
        read -p "Ramp-up time (seconds): " RAMP_UP
        ;;
    *)
        echo -e "${RED}Invalid choice, using Light Load${NC}"
        WORKERS=5
        OPS=20
        HOLD_TIME=1
        RAMP_UP=0
        ;;
esac

echo ""
echo -e "${BLUE}Test Mode:${NC}"
echo "1) Full Cycle    (Borrow → Hold → Return)"
echo "2) Checkout Only (Borrow and keep)"
echo ""
read -p "Enter choice [1-2]: " mode_choice

case $mode_choice in
    1)
        MODE="full-cycle"
        ;;
    2)
        MODE="checkout-only"
        ;;
    *)
        MODE="full-cycle"
        ;;
esac

echo ""
echo -e "${BLUE}Tool Selection:${NC}"
  echo "1) Random (mix of all tools)"
  echo "2) ECU Development Suite"
  echo "3) GreenHills Multi IDE"
  echo "4) AUTOSAR Configuration Tool"
  echo "5) CAN Bus Analyzer Pro"
  echo "6) Model-Based Design Studio"
echo ""
read -p "Enter choice [1-7]: " tool_choice

case $tool_choice in
    1)
        TOOL="random"
        ;;
    2)
        TOOL="ECU Development Suite"
        ;;
    3)
        TOOL="GreenHills Multi IDE"
        ;;
    4)
        TOOL="AUTOSAR Configuration Tool"
        ;;
    5)
        TOOL="CAN Bus Analyzer Pro"
        ;;
    6)
        TOOL="Model-Based Design Studio"
        ;;
    *)
        TOOL="random"
        ;;
esac

echo ""
echo -e "${GREEN}🚀 Starting stress test...${NC}"
echo ""
sleep 1

# Run the stress test
"${SCRIPT_DIR}/target/release/stress" \
    --url "${SERVER_URL}" \
    --workers "${WORKERS}" \
    --operations "${OPS}" \
    --hold-time "${HOLD_TIME}" \
    --mode "${MODE}" \
    --tool "${TOOL}" \
    --ramp-up "${RAMP_UP}"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}✅ Stress test complete!${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "View metrics and dashboards:"
if [ "$SERVER_URL" == "http://localhost:8000" ]; then
    echo "  Dashboard:   http://localhost:8000"
    echo "  Grafana:     http://localhost:3000"
    echo "  Prometheus:  http://localhost:9090"
elif [ "$SERVER_URL" == "https://license-server-demo.fly.dev" ]; then
    echo "  Dashboard:   https://license-server-demo.fly.dev"
    echo "  Metrics:     https://license-server-demo.fly.dev/metrics"
    echo "  Grafana:     https://mholetzko.grafana.net"
else
    echo "  Server:      ${SERVER_URL}"
fi
echo ""

