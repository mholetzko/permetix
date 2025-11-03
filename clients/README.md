# License Server Client Libraries

Multi-language client libraries for integrating with the Mercedes-Benz License Server.

## 🚀 Quick Start

**Interactive launcher for all clients:**

```bash
./clients/launch_examples.sh
```

This will let you choose:
1. Language (Python, C, C++, Rust)
2. Target (localhost, Fly.io, custom)
3. Automatically builds and runs the example

## Available Clients

### 🐍 [Python Client](python/)
- Simple, Pythonic API with context managers
- Type hints for IDE support
- Only requires `requests` library
- Perfect for web apps and scripts
- **Use case:** Flask/Django apps, data pipelines, automation

### 🔷 [C Client](c/)
- Simple ANSI C library
- Uses libcurl for HTTP
- Minimal dependencies
- Great for embedded systems or legacy codebases
- **Use case:** CAD applications, simulation tools

### 🔷 [C++ Client](cpp/)
- Modern C++17 with RAII semantics
- Automatic license return via destructor
- Exception-based error handling
- CMake and Makefile support
- **Use case:** Modern desktop applications, game engines

### 🦀 [Rust Client](rust/)
- Async/await with tokio
- Memory-safe with zero-cost abstractions
- Strong type system
- Cargo for easy integration
- **Use case:** High-performance services, CLI tools

## Quick Start (Individual Clients)

### Python
```bash
cd clients/python
pip install -r requirements.txt
python example.py
```

### C
```bash
cd clients/c
make
./license_client_example
```

### C++
```bash
cd clients/cpp
make
./license_client_example
```

### Rust
```bash
cd clients/rust
cargo run
```

## Feature Comparison

| Feature | Python | C | C++ | Rust |
|---------|--------|---|-----|------|
| Async Support | ❌ | ❌ | ❌ | ✅ |
| Context Manager | ✅ | ❌ | ✅ (RAII) | ✅ |
| Memory Safety | GC | Manual | Manual | Guaranteed |
| Error Handling | Exceptions | Return codes | Exceptions | Result<T> |
| Dependencies | requests | libcurl | libcurl, jsoncpp | reqwest, tokio |
| Type Hints | ✅ | ❌ | ✅ | ✅ |
| Ease of Use | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ |
| Performance | ⭐⭐ | ⚡⚡⚡ | ⚡⚡⚡ | ⚡⚡⚡ |

## Common Usage Pattern

All clients follow a similar pattern:

### Python
```python
from license_client import LicenseClient

client = LicenseClient("http://localhost:8000")

with client.borrow("cad_tool", "user") as license:
    # Use license
    pass
# Automatically returned
```

### C
```c
license_client_init("http://localhost:8000");

license_handle_t handle;
if (license_borrow("cad_tool", "user", &handle) == 0) {
    // Use license
    license_return(&handle);
}

license_client_cleanup();
```

### C++
```cpp
LicenseClient client("http://localhost:8000");

{
    auto license = client.borrow("cad_tool", "user");
    // Use license
} // Automatically returned
```

### Rust
```rust
let client = LicenseClient::new("http://localhost:8000");

{
    let license = client.borrow("cad_tool", "user").await?;
    // Use license
} // Automatically returned
```

## Integration Examples

### CAD Application (C)
```c
int main() {
    license_client_init("https://license-server-demo.fly.dev");
    
    license_handle_t license;
    if (license_borrow("cad_tool", get_user(), &license) == 0) {
        run_cad_application();
        license_return(&license);
    }
    
    license_client_cleanup();
}
```

### Game Engine (C++)
```cpp
class GameEngine {
    LicenseClient client_{"https://license-server-demo.fly.dev"};
    std::unique_ptr<LicenseHandle> license_;
    
public:
    void start() {
        license_ = std::make_unique<LicenseHandle>(
            client_.borrow("game_engine", get_user())
        );
        game_loop();
    }
};
```

### CLI Tool (Rust)
```rust
#[tokio::main]
async fn main() -> Result<()> {
    let client = LicenseClient::new("https://license-server-demo.fly.dev");
    let _license = client.borrow("analysis_tool", &get_user()).await?;
    run_analysis().await
}
```

## Server URLs

### Local Development
```
http://localhost:8000
```

### Production (Fly.io)
```
https://license-server-demo.fly.dev
```

## API Endpoints Used

All clients interact with these endpoints:

- `POST /licenses/borrow` - Borrow a license
- `POST /licenses/return` - Return a license
- `GET /licenses/{tool}/status` - Get tool status
- `GET /licenses/status` - Get all statuses

## Requirements

### Python
```bash
pip install requests
```

### C
```bash
# Ubuntu/Debian
sudo apt-get install libcurl4-openssl-dev

# macOS
brew install curl
```

### C++
```bash
# Ubuntu/Debian
sudo apt-get install libcurl4-openssl-dev libjsoncpp-dev

# macOS
brew install curl jsoncpp
```

### Rust
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Testing Against Production

All clients support testing against the deployed Fly.io instance:

```bash
# C
./license_client_example https://license-server-demo.fly.dev

# C++
./license_client_example https://license-server-demo.fly.dev

# Rust
cargo run -- https://license-server-demo.fly.dev
```

## Documentation

Each client has detailed documentation:

- [C README](c/README.md) - API reference, examples, integration guide
- [C++ README](cpp/README.md) - Modern C++ features, RAII patterns
- [Rust README](rust/README.md) - Async patterns, safety guarantees

## Choosing a Client

**Choose Python if:**
- Building web applications (Flask, Django, FastAPI)
- Need rapid development and easy integration
- Want simple, readable code
- Working on data pipelines or automation
- Prefer minimal dependencies

**Choose C if:**
- Working with legacy codebases
- Need minimal dependencies
- Targeting embedded systems
- Prefer simple, straightforward API

**Choose C++ if:**
- Want modern language features
- Need automatic resource management (RAII)
- Building desktop applications
- Familiar with STL and modern C++

**Choose Rust if:**
- Building new systems from scratch
- Need guaranteed memory safety
- Want async/await support
- Prefer compile-time error checking
- Building high-performance services

## Contributing

Each client follows language-specific best practices:
- **C**: ANSI C, minimal allocations, clear error codes
- **C++**: Modern C++17, RAII, move semantics, exceptions
- **Rust**: Idiomatic Rust, async/await, Result<T>, ownership

## License

MIT License - See individual client directories for details.

