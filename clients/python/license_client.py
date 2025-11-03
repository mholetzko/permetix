"""
License Server Client Library for Python

A simple, Pythonic client for interacting with the Mercedes-Benz license server.
Supports both synchronous and context manager patterns.
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import requests
from contextlib import contextmanager


class LicenseError(Exception):
    """Base exception for license operations"""
    pass


class NoLicensesAvailableError(LicenseError):
    """Raised when no licenses are available for borrowing"""
    def __init__(self, tool: str):
        super().__init__(f"No licenses available for tool: {tool}")
        self.tool = tool


@dataclass
class LicenseStatus:
    """License status information"""
    tool: str
    total: int
    borrowed: int
    available: int
    commit: int = 0
    max_overage: int = 0
    overage: int = 0
    in_commit: bool = True


class LicenseHandle:
    """
    License handle with context manager support.
    
    Automatically returns the license when used with 'with' statement.
    
    Example:
        with client.borrow("cad_tool", "alice") as license:
            print(f"Got license: {license.id}")
            # Use license
        # Automatically returned here
    """
    
    def __init__(self, license_id: str, tool: str, user: str, client: 'LicenseClient'):
        self.id = license_id
        self.tool = tool
        self.user = user
        self._client = client
        self._returned = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._returned:
            self.return_license()
        return False
    
    def return_license(self) -> None:
        """Explicitly return the license"""
        if self._returned:
            return
        self._client.return_license(self)
        self._returned = True
    
    def __repr__(self):
        return f"LicenseHandle(id='{self.id}', tool='{self.tool}', user='{self.user}')"


class LicenseClient:
    """
    Main license client class.
    
    Example:
        client = LicenseClient("http://localhost:8000")
        
        # Context manager (automatic return)
        with client.borrow("cad_tool", "alice") as license:
            print(f"Using license: {license.id}")
        
        # Manual return
        license = client.borrow("cad_tool", "bob")
        try:
            # Use license
            pass
        finally:
            license.return_license()
    """
    
    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize the license client.
        
        Args:
            base_url: Base URL of the license server
            timeout: Request timeout in seconds (default: 10)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def borrow(self, tool: str, user: str) -> LicenseHandle:
        """
        Borrow a license for a specific tool.
        
        Args:
            tool: Tool name (e.g., "cad_tool")
            user: Username
        
        Returns:
            LicenseHandle that can be used as a context manager
        
        Raises:
            NoLicensesAvailableError: If no licenses available
            LicenseError: On other errors
        
        Example:
            with client.borrow("cad_tool", "alice") as license:
                print(f"Got license: {license.id}")
        """
        url = f"{self.base_url}/licenses/borrow"
        payload = {"tool": tool, "user": user}
        
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 409:
                raise NoLicensesAvailableError(tool)
            
            response.raise_for_status()
            data = response.json()
            
            return LicenseHandle(
                license_id=data["id"],
                tool=tool,
                user=user,
                client=self
            )
        
        except requests.exceptions.RequestException as e:
            raise LicenseError(f"Failed to borrow license: {e}") from e
    
    def return_license(self, handle: LicenseHandle) -> None:
        """
        Return a borrowed license.
        
        Args:
            handle: License handle to return
        
        Raises:
            LicenseError: On error
        """
        url = f"{self.base_url}/licenses/return"
        payload = {"id": handle.id}
        
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        
        except requests.exceptions.RequestException as e:
            raise LicenseError(f"Failed to return license: {e}") from e
    
    def get_status(self, tool: str) -> LicenseStatus:
        """
        Get status for a specific tool.
        
        Args:
            tool: Tool name
        
        Returns:
            LicenseStatus object
        
        Raises:
            LicenseError: On error
        """
        url = f"{self.base_url}/licenses/{tool}/status"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return LicenseStatus(
                tool=data["tool"],
                total=data["total"],
                borrowed=data["borrowed"],
                available=data["available"],
                commit=data.get("commit", 0),
                max_overage=data.get("max_overage", 0),
                overage=data.get("overage", 0),
                in_commit=data.get("in_commit", True)
            )
        
        except requests.exceptions.RequestException as e:
            raise LicenseError(f"Failed to get status: {e}") from e
    
    def get_all_statuses(self) -> List[LicenseStatus]:
        """
        Get status for all tools.
        
        Returns:
            List of LicenseStatus objects
        
        Raises:
            LicenseError: On error
        """
        url = f"{self.base_url}/licenses/status"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return [
                LicenseStatus(
                    tool=item["tool"],
                    total=item["total"],
                    borrowed=item["borrowed"],
                    available=item["available"],
                    commit=item.get("commit", 0),
                    max_overage=item.get("max_overage", 0),
                    overage=item.get("overage", 0),
                    in_commit=item.get("in_commit", True)
                )
                for item in data
            ]
        
        except requests.exceptions.RequestException as e:
            raise LicenseError(f"Failed to get statuses: {e}") from e
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


@contextmanager
def license_client(base_url: str, timeout: int = 10):
    """
    Context manager for LicenseClient.
    
    Example:
        with license_client("http://localhost:8000") as client:
            with client.borrow("cad_tool", "alice") as license:
                print(f"Using license: {license.id}")
    """
    client = LicenseClient(base_url, timeout)
    try:
        yield client
    finally:
        client.close()

