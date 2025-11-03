#!/usr/bin/env python3
"""
Example usage of the license client library
"""

import sys
import time
from license_client import LicenseClient, NoLicensesAvailableError, LicenseError


def main():
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    tool = "cad_tool"
    user = "python-client-user"
    
    print("=" * 45)
    print("  License Client Example (Python)")
    print("=" * 45)
    print(f"Server: {server_url}")
    print(f"Tool:   {tool}")
    print(f"User:   {user}")
    print("=" * 45)
    print()
    
    # Create client
    client = LicenseClient(server_url)
    print("✅ Client initialized\n")
    
    try:
        # Get status before borrowing
        status = client.get_status(tool)
        print("📊 Status before borrow:")
        print(f"   Total:     {status.total}")
        print(f"   Borrowed:  {status.borrowed}")
        print(f"   Available: {status.available}\n")
        
        # Borrow a license (using context manager for automatic return)
        print("🎫 Borrowing license...")
        with client.borrow(tool, user) as license:
            print("✅ License borrowed successfully")
            print(f"   ID: {license.id}\n")
            
            # Simulate work
            print(f"💼 Working with {tool} for 5 seconds...")
            time.sleep(5)
            
            print("🔄 Returning license (automatic via context manager)...")
        
        print("✅ License returned\n")
        
        # Get status after returning
        status = client.get_status(tool)
        print("📊 Status after return:")
        print(f"   Total:     {status.total}")
        print(f"   Borrowed:  {status.borrowed}")
        print(f"   Available: {status.available}\n")
        
        print("✅ Example complete")
        
    except NoLicensesAvailableError as e:
        print(f"⚠️  {e}")
        return 1
    except LicenseError as e:
        print(f"❌ {e}")
        return 1
    finally:
        client.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

