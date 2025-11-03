# Python License Client

Pythonic client library for integrating with the Mercedes-Benz License Server.

## Features

- ✅ Simple, idiomatic Python API
- ✅ Context manager support (automatic return)
- ✅ Type hints for better IDE support
- ✅ Exception-based error handling
- ✅ Both sync patterns supported
- ✅ Minimal dependencies (only `requests`)

## Requirements

- Python 3.7+
- requests library

## Installation

```bash
cd clients/python
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

## Usage

### Run Example

```bash
# Against localhost
python example.py

# Against Fly.io
python example.py https://license-server-demo.fly.dev

# Make it executable
chmod +x example.py
./example.py
```

### Integrate into Your Application

#### Using Context Manager (Recommended)

```python
from license_client import LicenseClient, NoLicensesAvailableError

client = LicenseClient("http://localhost:8000")

try:
    # Automatic return when exiting 'with' block
    with client.borrow("cad_tool", "alice") as license:
        print(f"Got license: {license.id}")
        # Your application code here
    # License automatically returned here
    
except NoLicensesAvailableError:
    print("No licenses available")
finally:
    client.close()
```

#### Manual Return

```python
from license_client import LicenseClient

client = LicenseClient("http://localhost:8000")

license = client.borrow("cad_tool", "alice")
try:
    print(f"Using license: {license.id}")
    # Your application code
finally:
    license.return_license()
    client.close()
```

#### Client as Context Manager

```python
from license_client import license_client

with license_client("http://localhost:8000") as client:
    with client.borrow("cad_tool", "alice") as license:
        print(f"Using license: {license.id}")
# Both license and client automatically closed
```

### API Reference

```python
class LicenseClient:
    def __init__(self, base_url: str, timeout: int = 10):
        """Initialize the client"""
    
    def borrow(self, tool: str, user: str) -> LicenseHandle:
        """Borrow a license (returns context manager)"""
    
    def return_license(self, handle: LicenseHandle) -> None:
        """Return a license"""
    
    def get_status(self, tool: str) -> LicenseStatus:
        """Get status for a tool"""
    
    def get_all_statuses(self) -> List[LicenseStatus]:
        """Get status for all tools"""
    
    def close(self):
        """Close the session"""

class LicenseHandle:
    """Context manager for automatic license return"""
    id: str
    tool: str
    user: str
    
    def return_license(self) -> None:
        """Explicitly return the license"""

@dataclass
class LicenseStatus:
    tool: str
    total: int
    borrowed: int
    available: int
    commit: int
    max_overage: int
    overage: int
    in_commit: bool

class LicenseError(Exception):
    """Base exception for license operations"""

class NoLicensesAvailableError(LicenseError):
    """Raised when no licenses available"""
```

### Error Handling

```python
from license_client import (
    LicenseClient, 
    LicenseError, 
    NoLicensesAvailableError
)

client = LicenseClient("http://localhost:8000")

try:
    with client.borrow("cad_tool", "user") as license:
        # Use license
        pass
except NoLicensesAvailableError:
    print("No licenses available, try again later")
except LicenseError as e:
    print(f"License error: {e}")
finally:
    client.close()
```

## Example Output

```
=============================================
  License Client Example (Python)
=============================================
Server: http://localhost:8000
Tool:   cad_tool
User:   python-client-user
=============================================

✅ Client initialized

📊 Status before borrow:
   Total:     5
   Borrowed:  0
   Available: 5

🎫 Borrowing license...
✅ License borrowed successfully
   ID: abc123-def456-789

💼 Working with cad_tool for 5 seconds...
🔄 Returning license (automatic via context manager)...
✅ License returned

📊 Status after return:
   Total:     5
   Borrowed:  0
   Available: 5

✅ Example complete
```

## Integration Examples

### Flask Application

```python
from flask import Flask, request
from license_client import LicenseClient, NoLicensesAvailableError

app = Flask(__name__)
client = LicenseClient("https://license-server-demo.fly.dev")

@app.route("/run-analysis", methods=["POST"])
def run_analysis():
    user = request.json.get("user")
    
    try:
        with client.borrow("analysis_tool", user) as license:
            result = perform_analysis()
            return {"status": "success", "result": result}
    except NoLicensesAvailableError:
        return {"status": "error", "message": "No licenses available"}, 409

@app.teardown_appcontext
def cleanup(error=None):
    client.close()
```

### Django View

```python
from django.http import JsonResponse
from license_client import LicenseClient, NoLicensesAvailableError

client = LicenseClient("https://license-server-demo.fly.dev")

def run_simulation(request):
    user = request.user.username
    
    try:
        with client.borrow("simulation", user) as license:
            result = run_sim_engine()
            return JsonResponse({"status": "success", "data": result})
    except NoLicensesAvailableError:
        return JsonResponse(
            {"status": "error", "message": "No licenses available"},
            status=409
        )
```

### Long-Running Process

```python
from license_client import LicenseClient

def process_data():
    client = LicenseClient("http://localhost:8000")
    
    try:
        # Hold license for entire process
        license = client.borrow("data_processor", "batch-job")
        
        try:
            for batch in get_batches():
                process_batch(batch)
        finally:
            license.return_license()
    finally:
        client.close()
```

### Async Usage (with threading)

```python
from concurrent.futures import ThreadPoolExecutor
from license_client import LicenseClient

def process_item(item):
    client = LicenseClient("http://localhost:8000")
    try:
        with client.borrow("processor", f"worker-{item}") as license:
            return do_work(item)
    finally:
        client.close()

# Process items in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(process_item, items))
```

## Type Hints

The library includes full type hints for better IDE support:

```python
from typing import List
from license_client import LicenseClient, LicenseStatus

def get_available_tools(client: LicenseClient) -> List[str]:
    statuses: List[LicenseStatus] = client.get_all_statuses()
    return [s.tool for s in statuses if s.available > 0]
```

## Testing

```python
# test_license_client.py
import pytest
from license_client import LicenseClient, NoLicensesAvailableError

def test_borrow_and_return():
    client = LicenseClient("http://localhost:8000")
    
    with client.borrow("cad_tool", "test-user") as license:
        assert license.id
        assert license.tool == "cad_tool"
    
    client.close()

def test_no_licenses():
    client = LicenseClient("http://localhost:8000")
    
    # Borrow all licenses first
    licenses = []
    try:
        for i in range(10):
            licenses.append(client.borrow("cad_tool", f"user-{i}"))
    except NoLicensesAvailableError:
        pass
    
    # This should raise
    with pytest.raises(NoLicensesAvailableError):
        client.borrow("cad_tool", "test")
    
    # Cleanup
    for lic in licenses:
        lic.return_license()
    client.close()
```

## Why Python?

1. **Simple** - Clean, readable code
2. **Context Managers** - Automatic resource cleanup
3. **Type Hints** - Better IDE support and documentation
4. **Minimal Deps** - Only requires `requests`
5. **Flexible** - Works with any Python web framework
6. **Tested** - Works with Python 3.7+

## Comparison with Other Clients

| Feature | Python | C | C++ | Rust |
|---------|--------|---|-----|------|
| Context Manager | ✅ | ❌ | ❌ (RAII) | ✅ |
| Type Hints | ✅ | ❌ | ✅ | ✅ |
| Auto Return | ✅ | ❌ | ✅ | ✅ |
| Easy Integration | ✅✅ | ⭐ | ⭐⭐ | ⭐⭐ |
| Performance | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

Choose Python for:
- Web applications (Flask, Django, FastAPI)
- Data processing pipelines
- Automation scripts
- Rapid prototyping
- Ease of integration

