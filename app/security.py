"""
Security middleware for license server
Implements HMAC-based request signing to prevent unauthorized API access
"""

import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request, HTTPException
import logging

logger = logging.getLogger(__name__)

# Vendor secrets - in production, these would be stored securely in database
# Each vendor's client library is compiled with their unique secret
VENDOR_SECRETS = {
    "techvendor": "techvendor_secret_ecu_2025_demo_xyz789abc123def456",
}

# Configuration
SIGNATURE_VALID_WINDOW = 300  # 5 minutes - prevents replay attacks
REQUIRE_SIGNATURES = False  # Set to True to enforce (start with False for demo)


def generate_signature(tool: str, user: str, timestamp: str, vendor_id: str = "techvendor") -> str:
    """
    Generate HMAC signature for a request.
    This is what the client library does before sending a request.
    
    Args:
        tool: The tool being borrowed
        user: The user requesting the license
        timestamp: Unix timestamp as string
        vendor_id: Vendor identifier
    
    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    if vendor_id not in VENDOR_SECRETS:
        raise ValueError(f"Unknown vendor: {vendor_id}")
    
    # Create payload: tool|user|timestamp
    payload = f"{tool}|{user}|{timestamp}"
    
    # Generate HMAC signature
    signature = hmac.new(
        VENDOR_SECRETS[vendor_id].encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    logger.debug(f"Generated signature for payload: {payload}")
    return signature


def validate_signature(
    request: Request,
    tool: str,
    user: str,
    require: bool = None
) -> tuple[bool, Optional[str]]:
    """
    Validate HMAC signature on incoming request.
    
    Args:
        request: FastAPI request object
        tool: The tool being borrowed
        user: The user requesting the license
        require: Override global REQUIRE_SIGNATURES setting
    
    Returns:
        (is_valid, error_message)
    """
    # Determine if we should enforce signatures
    enforce = require if require is not None else REQUIRE_SIGNATURES
    
    # Extract security headers
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")
    vendor_id = request.headers.get("X-Vendor-ID", "techvendor")
    
    # If headers are missing
    if not signature or not timestamp:
        if enforce:
            logger.warning(f"Missing security headers from {request.client.host}")
            return False, "Missing X-Signature or X-Timestamp headers"
        else:
            logger.debug("Security headers missing, but not required")
            return True, None
    
    # Validate vendor
    if vendor_id not in VENDOR_SECRETS:
        logger.warning(f"Unknown vendor ID: {vendor_id}")
        return False, f"Unknown vendor: {vendor_id}"
    
    # Validate timestamp (prevent replay attacks)
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        time_diff = abs(current_time - request_time)
        
        if time_diff > SIGNATURE_VALID_WINDOW:
            logger.warning(f"Request timestamp too old: {time_diff}s (max {SIGNATURE_VALID_WINDOW}s)")
            return False, f"Request expired (timestamp difference: {time_diff}s)"
    except ValueError:
        logger.warning(f"Invalid timestamp format: {timestamp}")
        return False, "Invalid timestamp format"
    
    # Reconstruct expected signature
    payload = f"{tool}|{user}|{timestamp}"
    expected_signature = hmac.new(
        VENDOR_SECRETS[vendor_id].encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (constant-time to prevent timing attacks)
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(f"Invalid signature from {request.client.host} for {vendor_id}")
        logger.debug(f"Expected: {expected_signature}, Got: {signature}")
        return False, "Invalid signature"
    
    logger.info(f"Valid signature from {request.client.host} for {vendor_id}/{tool}")
    return True, None


def get_vendor_secret(vendor_id: str) -> Optional[str]:
    """
    Get vendor secret for client library usage.
    In production, this would require authentication.
    """
    return VENDOR_SECRETS.get(vendor_id)

