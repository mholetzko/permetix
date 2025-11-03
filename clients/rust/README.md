# Rust License Client

Modern, idiomatic Rust library for integrating with the Mercedes-Benz License Server.

## Features

- ✅ Async/await with tokio
- ✅ RAII semantics with Drop trait
- ✅ Strong type safety and error handling
- ✅ Automatic license return on drop
- ✅ Zero-cost abstractions
- ✅ Well-documented with cargo doc

## Requirements

- Rust 1.60+ (2021 edition)
- Cargo (comes with Rust)

Install Rust: https://rustup.rs/

## Build

```bash
cd clients/rust
cargo build --release
```

## Usage

### Run Example (Interactive)

The easiest way to run the example:

```bash
cd clients/rust
./run_example.sh
```

This interactive script will:
1. Check for Rust/Cargo
2. Let you choose the target (localhost, Fly.io, custom)
3. Run the example (builds automatically via cargo)

### Run Example (Manual)

```bash
# Against localhost
cargo run

# Against Fly.io
cargo run -- https://license-server-demo.fly.dev
```

### Add as Dependency

Add to your `Cargo.toml`:

```toml
[dependencies]
license_client = { path = "../clients/rust" }
tokio = { version = "1", features = ["full"] }
```

### Integrate into Your Application

```rust
use license_client::{LicenseClient, Result};

#[tokio::main]
async fn main() -> Result<()> {
    let client = LicenseClient::new("http://localhost:8000");
    
    // RAII: License automatically returned when dropped
    {
        let license = client.borrow("cad_tool", "my-user").await?;
        println!("Got license: {}", license.id());
        
        // Your application code here
        
    } // License automatically returned here
    
    Ok(())
}
```

### API Reference

```rust
/// Main client
pub struct LicenseClient {
    pub fn new(base_url: impl Into<String>) -> Self;
    pub async fn borrow(&self, tool: impl Into<String>, 
                        user: impl Into<String>) -> Result<LicenseHandle>;
    pub async fn get_status(&self, tool: impl Into<String>) -> Result<LicenseStatus>;
    pub async fn get_all_statuses(&self) -> Result<Vec<LicenseStatus>>;
}

/// RAII license handle
pub struct LicenseHandle {
    pub fn id(&self) -> &str;
    pub fn tool(&self) -> &str;
    pub fn user(&self) -> &str;
    pub async fn return_license(self) -> Result<()>;
}

/// Status information
pub struct LicenseStatus {
    pub tool: String,
    pub total: i32,
    pub borrowed: i32,
    pub available: i32,
    pub commit: i32,
    pub max_overage: i32,
    pub overage: i32,
    pub in_commit: bool,
}

/// Error types
pub enum LicenseError {
    RequestFailed(reqwest::Error),
    NoLicensesAvailable(String),
    HttpError(u16, String),
    InvalidResponse(String),
}
```

### RAII Automatic License Return

Rust's ownership system ensures licenses are returned:

```rust
async fn run_cad_application() -> Result<()> {
    let client = LicenseClient::new("http://localhost:8000");
    
    let license = client.borrow("cad_tool", "alice").await?;
    
    // Do work...
    if some_error() {
        return Err(...); // License automatically returned via Drop
    }
    
    // More work...
    some_operation()?; // Even if this panics, Drop is called!
    
    Ok(())
    // License automatically returned when leaving scope
}
```

### Error Handling

Rust's `?` operator makes error handling elegant:

```rust
async fn example() -> Result<()> {
    let client = LicenseClient::new("http://localhost:8000");
    
    match client.borrow("cad_tool", "user").await {
        Ok(license) => {
            // Use license
            Ok(())
        }
        Err(LicenseError::NoLicensesAvailable(tool)) => {
            eprintln!("No licenses for {}", tool);
            Ok(())
        }
        Err(e) => Err(e),
    }
}
```

## Example Output

```
===========================================
  License Client Example (Rust)
===========================================
Server: http://localhost:8000
Tool:   cad_tool
User:   rust-client-user
===========================================

✅ Client initialized

📊 Status before borrow:
   Total:     5
   Borrowed:  0
   Available: 5

🎫 Borrowing license...
✅ License borrowed successfully
   ID: abc123-def456-789

💼 Working with cad_tool for 5 seconds...
🔄 Explicitly returning license...
✅ License returned

📊 Status after return:
   Total:     5
   Borrowed:  0
   Available: 5

✅ Example complete
```

## Integration Example

```rust
use license_client::{LicenseClient, LicenseHandle, Result};
use std::sync::Arc;

struct CADApplication {
    client: LicenseClient,
    license: Option<LicenseHandle>,
}

impl CADApplication {
    fn new() -> Self {
        Self {
            client: LicenseClient::new("https://license-server-demo.fly.dev"),
            license: None,
        }
    }
    
    async fn run(&mut self) -> Result<()> {
        // Borrow license
        self.license = Some(
            self.client.borrow("cad_tool", get_username()).await?
        );
        
        // Run application
        self.main_loop().await?;
        
        // License automatically returned when dropped
        Ok(())
    }
    
    async fn main_loop(&self) -> Result<()> {
        // Your application code
        Ok(())
    }
}
```

## Testing

```bash
# Run tests
cargo test

# Run with output
cargo test -- --nocapture

# Check code
cargo clippy

# Format code
cargo fmt
```

## Documentation

Generate and view documentation:

```bash
cargo doc --open
```

## Performance

Rust's zero-cost abstractions mean:
- No runtime overhead
- Fast compilation
- Memory safe without garbage collection
- Comparable to C/C++ performance

## Safety

Rust guarantees:
- ✅ No null pointer dereferences
- ✅ No buffer overflows
- ✅ No data races
- ✅ Automatic memory management
- ✅ Thread safety

## Why Rust?

1. **Memory Safety** - No segfaults or memory leaks
2. **Concurrency** - Safe concurrent code with tokio
3. **Performance** - Zero-cost abstractions
4. **Modern** - Great tooling (cargo, rustfmt, clippy)
5. **Reliability** - Catch errors at compile time

