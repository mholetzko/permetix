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
echo -e "${BLUE}  License Client Examples Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Select language
echo -e "${BLUE}Select client language:${NC}"
echo "1) Python   (Recommended for quick start)"
echo "2) C        (Minimal dependencies)"
echo "3) C++      (Modern with RAII)"
echo "4) Rust     (Memory-safe, async)"
echo ""
read -p "Enter choice [1-4]: " lang_choice

case $lang_choice in
    1) LANGUAGE="python" ;;
    2) LANGUAGE="c" ;;
    3) LANGUAGE="cpp" ;;
    4) LANGUAGE="rust" ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}→ Selected: ${LANGUAGE}${NC}"
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

# Run the appropriate client
case $LANGUAGE in
    python)
        echo -e "${GREEN}→ Running Python client...${NC}"
        echo ""
        
        cd "${SCRIPT_DIR}/python"
        
        # Check if requests is installed
        if ! python3 -c "import requests" &> /dev/null; then
            echo -e "${YELLOW}⚠️  requests library not found${NC}"
            echo -e "${BLUE}Installing requests...${NC}"
            pip3 install requests
        fi
        
        chmod +x example.py
        python3 example.py "${SERVER_URL}"
        ;;
    
    c)
        echo -e "${GREEN}→ Running C client...${NC}"
        echo ""
        
        cd "${SCRIPT_DIR}/c"
        
        # Check if libcurl is available
        if ! pkg-config --exists libcurl 2>/dev/null && ! command -v curl-config &> /dev/null; then
            echo -e "${RED}❌ libcurl not found${NC}"
            echo "Please install libcurl:"
            echo "  Ubuntu/Debian: sudo apt-get install libcurl4-openssl-dev"
            echo "  macOS: brew install curl"
            exit 1
        fi
        
        # Build if needed
        if [ ! -f "license_client_example" ]; then
            echo -e "${BLUE}Building C client...${NC}"
            make
        fi
        
        ./license_client_example "${SERVER_URL}"
        ;;
    
    cpp)
        echo -e "${GREEN}→ Running C++ client...${NC}"
        echo ""
        
        cd "${SCRIPT_DIR}/cpp"
        
        # Check dependencies
        if ! pkg-config --exists jsoncpp 2>/dev/null; then
            echo -e "${RED}❌ jsoncpp not found${NC}"
            echo "Please install jsoncpp:"
            echo "  Ubuntu/Debian: sudo apt-get install libjsoncpp-dev"
            echo "  macOS: brew install jsoncpp"
            exit 1
        fi
        
        # Build if needed
        if [ ! -f "license_client_example" ]; then
            echo -e "${BLUE}Building C++ client...${NC}"
            make
        fi
        
        ./license_client_example "${SERVER_URL}"
        ;;
    
    rust)
        echo -e "${GREEN}→ Running Rust client...${NC}"
        echo ""
        
        cd "${SCRIPT_DIR}/rust"
        
        # Check if cargo is installed
        if ! command -v cargo &> /dev/null; then
            echo -e "${RED}❌ Rust/Cargo not found${NC}"
            echo "Please install Rust from: https://rustup.rs/"
            exit 1
        fi
        
        cargo run -- "${SERVER_URL}"
        ;;
esac

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Example complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo "Client implementations available:"
echo "  Python: ${SCRIPT_DIR}/python/"
echo "  C:      ${SCRIPT_DIR}/c/"
echo "  C++:    ${SCRIPT_DIR}/cpp/"
echo "  Rust:   ${SCRIPT_DIR}/rust/"
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

