# C++ License Client

Modern C++17 library for integrating with the Mercedes-Benz License Server.

## Features

- ✅ Modern C++17 with RAII semantics
- ✅ Automatic license return when handle goes out of scope
- ✅ Exception-based error handling
- ✅ Type-safe API with move semantics
- ✅ JSON parsing with jsoncpp
- ✅ CMake and Makefile build support

## Requirements

```bash
# Ubuntu/Debian
sudo apt-get install libcurl4-openssl-dev libjsoncpp-dev cmake

# macOS (if jsoncpp is not available, use nlohmann-json instead)
brew install curl jsoncpp cmake
# OR
brew install curl nlohmann-json cmake

# Fedora/RHEL
sudo dnf install libcurl-devel jsoncpp-devel cmake
```

### macOS Installation Issue?

If you get "json/json.h not found" on macOS, install dependencies:

```bash
# Check if jsoncpp is installed
brew list jsoncpp || brew install jsoncpp

# If still not working, find the include path
brew info jsoncpp

# You may need to add include path to Makefile
# Add: -I/opt/homebrew/include
```

## Build

### Using Make:
```bash
cd clients/cpp
make
```

### Using CMake:
```bash
cd clients/cpp
mkdir build && cd build
cmake ..
make
```

## Usage

### Run Example

```bash
# Against localhost
./license_client_example

# Against Fly.io
./license_client_example https://license-server-demo.fly.dev
```

### Integrate into Your Application

```cpp
#include "license_client.hpp"

using namespace license;

int main() {
    try {
        LicenseClient client("http://localhost:8000");
        
        // RAII: License automatically returned when handle destroyed
        {
            auto license = client.borrow("cad_tool", "my-user");
            std::cout << "Got license: " << license.id() << std::endl;
            
            // Your application code here
            
        } // License automatically returned here
        
    } catch (const NoLicensesAvailableException& e) {
        std::cerr << "No licenses available" << std::endl;
    } catch (const LicenseException& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    return 0;
}
```

### API Reference

```cpp
namespace license {

// Main client class
class LicenseClient {
public:
    explicit LicenseClient(const std::string& base_url);
    
    LicenseHandle borrow(const std::string& tool, 
                         const std::string& user);
    void return_license(const LicenseHandle& handle);
    LicenseStatus get_status(const std::string& tool);
    std::vector<LicenseStatus> get_all_statuses();
};

// RAII license handle (move-only)
class LicenseHandle {
public:
    const std::string& id() const;
    const std::string& tool() const;
    const std::string& user() const;
    bool is_valid() const;
    void return_license();
};

// Status information
struct LicenseStatus {
    std::string tool;
    int total, borrowed, available;
    int commit, max_overage, overage;
    bool in_commit;
};

// Exceptions
class LicenseException : public std::runtime_error {};
class NoLicensesAvailableException : public LicenseException {};

}
```

### RAII Automatic License Return

The key feature is automatic license return using RAII:

```cpp
void run_cad_application() {
    LicenseClient client("http://localhost:8000");
    
    auto license = client.borrow("cad_tool", "alice");
    
    // Do work...
    if (some_error()) {
        return; // License automatically returned via destructor
    }
    
    // More work...
    if (another_error()) {
        throw std::runtime_error("Error"); // License still returned!
    }
    
    // License automatically returned when leaving scope
}
```

### Move Semantics

`LicenseHandle` is move-only to prevent accidental copies:

```cpp
auto license = client.borrow("cad_tool", "alice");

// Move is OK
auto moved_license = std::move(license);

// Copy is deleted (won't compile)
// auto copy = license; // ERROR!
```

## Example Output

```
===========================================
  License Client Example (C++)
===========================================
Server: http://localhost:8000
Tool:   cad_tool
User:   cpp-client-user
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
🔄 License will be automatically returned...
✅ License returned (RAII)

📊 Status after return:
   Total:     5
   Borrowed:  0
   Available: 5

✅ Example complete
```

## Integration Example

```cpp
#include "license_client.hpp"
#include <memory>

class CADApplication {
public:
    CADApplication() 
        : client_("https://license-server-demo.fly.dev") {}
    
    void run() {
        try {
            // Borrow license for entire application lifetime
            license_ = std::make_unique<LicenseHandle>(
                client_.borrow("cad_tool", get_username())
            );
            
            // Run application
            main_loop();
            
        } catch (const NoLicensesAvailableException&) {
            show_error("No licenses available");
        }
    }
    
private:
    LicenseClient client_;
    std::unique_ptr<LicenseHandle> license_;
    
    void main_loop() {
        // Your application code
    }
};
```

## Thread Safety

The client can be used from multiple threads if each thread has its own instance. The `LicenseHandle` is not thread-safe and should not be shared between threads.

## Error Handling

Always use try-catch blocks to handle exceptions:

```cpp
try {
    auto license = client.borrow("cad_tool", "user");
} catch (const NoLicensesAvailableException& e) {
    // Handle no licenses
} catch (const LicenseException& e) {
    // Handle other errors
    std::cerr << "Error: " << e.what() << std::endl;
}
```

