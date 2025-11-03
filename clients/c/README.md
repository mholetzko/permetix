# C License Client

Simple C library for integrating with the Mercedes-Benz License Server.

## Features

- ✅ Simple API with 4 main functions
- ✅ No external dependencies except libcurl
- ✅ Error handling with descriptive messages
- ✅ Lightweight and fast
- ✅ ANSI C compatible

## Requirements

```bash
# Ubuntu/Debian
sudo apt-get install libcurl4-openssl-dev

# macOS
brew install curl

# Fedora/RHEL
sudo dnf install libcurl-devel
```

## Build

```bash
cd clients/c
make
```

## Usage

### Run Example (Interactive)

The easiest way to run the example:

```bash
cd clients/c
./run_example.sh
```

This interactive script will:
1. Check for dependencies (libcurl)
2. Build the client if needed
3. Let you choose the target (localhost, Fly.io, custom)
4. Run the example

### Run Example (Manual)

```bash
# Against localhost
./license_client_example

# Against Fly.io
./license_client_example https://license-server-demo.fly.dev
```

### Integrate into Your Application

```c
#include "license_client.h"

int main() {
    // Initialize
    license_client_init("http://localhost:8000");
    
    // Borrow a license
    license_handle_t handle;
    if (license_borrow("cad_tool", "my-user", &handle) == 0) {
        printf("Got license: %s\n", handle.id);
        
        // Your application code here
        
        // Return when done
        license_return(&handle);
    }
    
    // Cleanup
    license_client_cleanup();
    return 0;
}
```

### API Reference

```c
// Initialize the client (call once at startup)
int license_client_init(const char *base_url);

// Borrow a license
int license_borrow(const char *tool, const char *user, 
                   license_handle_t *handle);

// Return a license
int license_return(const license_handle_t *handle);

// Check license status
int license_get_status(const char *tool, license_status_t *status);

// Get error message
const char* license_get_error(void);

// Cleanup (call at shutdown)
void license_client_cleanup(void);
```

### Return Values

- `0` - Success
- `-1` - Error (check `license_get_error()`)
- `-2` - No licenses available (only for `license_borrow`)

## Example Output

```
===========================================
  License Client Example (C)
===========================================
Server: http://localhost:8000
Tool:   cad_tool
User:   c-client-user
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
🔄 Returning license...
✅ License returned successfully

📊 Status after return:
   Total:     5
   Borrowed:  0
   Available: 5

✅ Client cleaned up
```

## Integration Example

Typical usage in a CAD application:

```c
#include "license_client.h"

int main() {
    license_client_init("https://license-server-demo.fly.dev");
    
    license_handle_t license;
    int result = license_borrow("cad_tool", get_username(), &license);
    
    if (result == 0) {
        // Run your CAD application
        run_cad_application();
        
        // Return license when application exits
        license_return(&license);
    } else if (result == -2) {
        show_error("No licenses available. Please try again later.");
    } else {
        show_error(license_get_error());
    }
    
    license_client_cleanup();
    return 0;
}
```

## Thread Safety

The current implementation uses a global CURL handle and is **not thread-safe**. For multi-threaded applications, either:
1. Use locks around license operations
2. Create thread-local CURL handles
3. Initialize one client per thread

## Error Handling

Always check return values and use `license_get_error()` for detailed error messages:

```c
if (license_borrow("cad_tool", "user", &handle) != 0) {
    fprintf(stderr, "Error: %s\n", license_get_error());
}
```

