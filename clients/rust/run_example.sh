#!/usr/bin/env bash
set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Rust License Client Example${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if cargo is installed
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}❌ Rust/Cargo not found${NC}"
    echo "Please install Rust from: https://rustup.rs/"
    exit 1
fi

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
echo -e "${GREEN}→ Running Rust client example...${NC}"
echo ""

cd "${SCRIPT_DIR}"
cargo run -- "${SERVER_URL}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Example complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo "Useful links:"
if [ "$SERVER_URL" == "http://localhost:8000" ]; then
    echo "  Dashboard:   http://localhost:8000"
    echo "  Grafana:     http://localhost:3000"
    echo "  Prometheus:  http://localhost:9090"
elif [ "$SERVER_URL" == "https://license-server-demo.fly.dev" ]; then
    echo "  Dashboard:   https://license-server-demo.fly.dev"
    echo "  Presentation: https://license-server-demo.fly.dev/presentation"
else
    echo "  Server:      ${SERVER_URL}"
fi
echo ""

