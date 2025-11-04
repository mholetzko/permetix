# Simple Makefile for C++ License Client

CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2

# Auto-detect platform and set paths
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    # macOS - check for Homebrew paths
    HOMEBREW_PREFIX := $(shell brew --prefix 2>/dev/null || echo /usr/local)
    CXXFLAGS += -I$(HOMEBREW_PREFIX)/include -I$(HOMEBREW_PREFIX)/opt/openssl@3/include
    LDFLAGS = -L$(HOMEBREW_PREFIX)/lib -L$(HOMEBREW_PREFIX)/opt/openssl@3/lib -lcurl -ljsoncpp -lcrypto
else
    # Linux
    LDFLAGS = -lcurl -ljsoncpp -lcrypto
endif

TARGET = license_client_example
SOURCES = license_client.cpp example.cpp
OBJECTS = $(SOURCES:.cpp=.o)

.PHONY: all clean test cmake-build

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(OBJECTS) -o $(TARGET) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)
	rm -rf build/

cmake-build:
	mkdir -p build
	cd build && cmake .. && make

test: $(TARGET)
	./$(TARGET)

test-remote: $(TARGET)
	./$(TARGET) https://license-server-demo.fly.dev

help:
	@echo "Available targets:"
	@echo "  all          - Build with make (default)"
	@echo "  cmake-build  - Build with CMake"
	@echo "  clean        - Remove build artifacts"
	@echo "  test         - Build and run against localhost"
	@echo "  test-remote  - Build and run against Fly.io"
	@echo ""
	@echo "Requirements:"
	@echo "  - libcurl-dev"
	@echo "  - libjsoncpp-dev"
	@echo ""
	@echo "Install on Ubuntu/Debian:"
	@echo "  sudo apt-get install libcurl4-openssl-dev libjsoncpp-dev"

