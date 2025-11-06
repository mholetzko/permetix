import os
import time
import uuid
import asyncio
import json
import urllib.parse
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from .db import initialize_database, borrow_license, return_license, get_status, update_budget_config, get_all_tools, get_overage_charges, get_all_tenants, get_vendor_customers, provision_license_to_tenant, create_tenant, create_vendor, get_all_vendors, delete_tenant, delete_vendor, get_connection

# App version for observability/journey (surfaced in logs & API)
APP_VERSION = os.getenv("APP_VERSION", "dev")

# OpenTelemetry initialization
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize OpenTelemetry
resource = Resource.create({
    "service.name": "license-server",
    "service.version": APP_VERSION,
})

trace_provider = TracerProvider(resource=resource)

# Parse headers - support both URL-encoded (Authorization=Basic%20...) and standard (Authorization: Basic ...)
try:
    headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers = {}
    if headers_str:
        # Handle URL-encoded format (Authorization=Basic%20...) - Grafana Cloud format
        if "=" in headers_str and ("%20" in headers_str or "%3D" in headers_str):
            # URL decode: Authorization=Basic%20... -> Authorization=Basic ...
            decoded = urllib.parse.unquote(headers_str)
            # Convert to dict format: Authorization=Basic ... -> {"Authorization": "Basic ..."}
            if "=" in decoded:
                key, value = decoded.split("=", 1)
                headers[key] = value
        # Standard format: "Authorization: Basic ..." or "key1: value1, key2: value2"
        elif ":" in headers_str:
            if "," in headers_str:
                # Multiple headers
                for header in headers_str.split(","):
                    if ":" in header:
                        key, value = header.split(":", 1)
                        headers[key.strip()] = value.strip()
            else:
                # Single header
                key, value = headers_str.split(":", 1)
                headers[key.strip()] = value.strip()

    # Only pass headers if we have them (OTLPSpanExporter may not accept empty dict)
    exporter_kwargs = {
        "endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4318/v1/traces"),
    }
    if headers:
        exporter_kwargs["headers"] = headers

    processor = BatchSpanProcessor(
        OTLPSpanExporter(**exporter_kwargs)
    )
    trace_provider.add_span_processor(processor)
    trace.set_tracer_provider(trace_provider)
except Exception as e:
    # Don't fail app startup if OpenTelemetry config is wrong
    # Logger not initialized yet, use print
    print(f"WARNING: Failed to configure OpenTelemetry tracing: {e}. App will continue without tracing.")
    trace.set_tracer_provider(TracerProvider(resource=resource))  # Fallback to no-op provider

app = FastAPI(title="License Server", version="0.1.0")

# Instrument FastAPI app with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Structured logging - stdout only (Fly.io captures stdout automatically)
import logging

# In-memory log buffer for scraping (keeps last 1000 log entries)
class LogBuffer:
    def __init__(self, max_size=1000):
        self.buffer = deque(maxlen=max_size)
        self.lock = asyncio.Lock()
    
    def append(self, record):
        """Append a log record to the buffer"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "pathname": record.pathname,
            "lineno": record.lineno,
        }
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'trace_id'):
            log_entry['trace_id'] = record.trace_id
        self.buffer.append(log_entry)
    
    def get_recent_logs(self, limit=100):
        """Get recent log entries in Promtail/Loki compatible format"""
        recent = list(self.buffer)[-limit:]
        # Format as plain text (one entry per line) for Promtail to scrape
        lines = []
        for entry in recent:
            # Format: timestamp level name message [extra_fields]
            line = f"{entry['timestamp']} {entry['level']} {entry['name']} {entry['message']}"
            if 'request_id' in entry:
                line += f" request_id={entry['request_id']}"
            if 'trace_id' in entry:
                line += f" trace_id={entry['trace_id']}"
            lines.append(line)
        return "\n".join(lines)

# Global log buffer
log_buffer = LogBuffer(max_size=1000)

# Custom log handler that writes to buffer
class BufferLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_buffer.append(record)
        except Exception:
            pass  # Don't fail if buffer append fails

# Configure logging
logger = logging.getLogger("license-server")
logger.setLevel(logging.INFO)

# Buffer handler (for scraping)
buffer_handler = BufferLogHandler()
logger.addHandler(buffer_handler)

# Console handler (always active for local development and Fly.io stdout)
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Logging configured - stdout only (Fly.io captures stdout automatically)
# View logs at: https://fly-metrics.net/d/fly-logs/fly-logs?orgId=1332768&var-app=license-server-demo
logger.info("Logging configured - stdout only (Fly.io will capture logs automatically)")

# Log OpenTelemetry status after logger is initialized
try:
    if trace.get_tracer_provider() and hasattr(trace.get_tracer_provider(), 'resource'):
        logger.info("OpenTelemetry tracing configured successfully")
except Exception:
    pass  # Skip if tracing not configured


# Prometheus metrics
borrow_attempts = Counter("license_borrow_attempts_total", "Total borrow attempts", ["tool", "user"]) 
borrow_successes = Counter("license_borrow_success_total", "Total successful borrows", ["tool", "user"]) 
borrow_failures = Counter("license_borrow_failure_total", "Total failed borrow attempts", ["tool", "reason"]) 
borrow_duration = Histogram("license_borrow_duration_seconds", "Borrow operation duration", ["tool"]) 
borrowed_gauge = Gauge("licenses_borrowed", "Currently borrowed licenses per tool", ["tool"]) 
total_licenses_gauge = Gauge("licenses_total", "Total licenses available per tool", ["tool"])
overage_gauge = Gauge("licenses_overage", "Current overage count per tool", ["tool"])
commit_gauge = Gauge("licenses_commit", "Commit quantity per tool", ["tool"])
max_overage_gauge = Gauge("licenses_max_overage", "Max overage allowed per tool", ["tool"])
at_max_overage_gauge = Gauge("licenses_at_max_overage", "Whether tool is at max overage (1) or not (0)", ["tool"])
overage_checkouts = Counter("license_overage_checkouts_total", "Total overage checkouts", ["tool", "user"]) 
# HTTP status code metrics - tracks all responses by route and status code
http_requests_total = Counter("license_http_requests_total", "Total HTTP requests by route and status code", ["route", "method", "status_code"])
http_500_total = Counter("license_http_500_total", "Total HTTP 500 responses emitted by the app", ["route"])  # Kept for backward compatibility
http_request_duration = Histogram("license_http_request_duration_seconds", "HTTP request duration in seconds", ["route", "method", "status_code"])


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Extract tenant from subdomain for multi-tenant routing on Fly.io"""
    host = request.headers.get("host", "").split(":")[0]  # Remove port
    parts = host.split(".")
    
    # Extract subdomain (first part before first dot)
    # Examples:
    #   acme.permetrix.fly.dev → subdomain = "acme"
    #   vendor.permetrix.fly.dev → subdomain = "vendor"
    #   permetrix.fly.dev → subdomain = None
    if len(parts) >= 3:  # subdomain.domain.tld
        subdomain = parts[0]
    else:
        subdomain = None
    
    # Determine context
    if subdomain == "vendor":
        request.state.context = "vendor"
        request.state.tenant_id = None
    elif subdomain:
        # Check if subdomain is a valid tenant (will be validated in routes)
        request.state.context = "tenant"
        request.state.tenant_id = subdomain
    else:
        request.state.context = "main"
        request.state.tenant_id = None
    
    # Log tenant context for debugging
    if subdomain:
        logger.debug(f"tenant_middleware host={host} subdomain={subdomain} context={request.state.context} tenant_id={request.state.tenant_id}")
    
    response = await call_next(request)
    return response


@app.middleware("http")
async def track_http_responses(request: Request, call_next):
    """Track all HTTP responses by route, method, status code, duration, and request ID."""
    request_id = str(uuid.uuid4())[:8]  # Short request ID for traceability
    route = request.url.path
    method = request.method
    start_time = time.perf_counter()
    
    # Get OpenTelemetry trace context if available
    span = trace.get_current_span()
    trace_id = None
    span_id = None
    if span and span.get_span_context().is_valid:
        trace_context = span.get_span_context()
        trace_id = format(trace_context.trace_id, '032x')
        span_id = format(trace_context.span_id, '016x')
    
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        status = response.status_code
        
        # Track all status codes
        http_requests_total.labels(route=route, method=method, status_code=str(status)).inc()
        http_request_duration.labels(route=route, method=method, status_code=str(status)).observe(duration)
        
        # Log request with trace ID and OpenTelemetry trace context
        log_msg = f"request route={route} method={method} status={status} duration={duration:.3f} request_id={request_id}"
        if trace_id:
            log_msg += f" trace_id={trace_id} span_id={span_id}"
        logger.info(log_msg, extra={"request_id": request_id, "trace_id": trace_id} if trace_id else {"request_id": request_id})
        
        # Also track 500s specifically (for backward compatibility and easier alerting)
        if status == 500:
            http_500_total.labels(route=route).inc()
            logger.warning("500 response route=%s method=%s request_id=%s trace_id=%s", route, method, request_id, trace_id or "none", 
                          extra={"request_id": request_id, "trace_id": trace_id} if trace_id else {"request_id": request_id})
        
        # Add request ID and trace ID to response header for traceability
        response.headers["X-Request-ID"] = request_id
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response
    except Exception as e:
        duration = time.perf_counter() - start_time
        # Catch unhandled exceptions (these become 500s)
        http_requests_total.labels(route=route, method=method, status_code="500").inc()
        http_request_duration.labels(route=route, method=method, status_code="500").observe(duration)
        http_500_total.labels(route=route).inc()
        logger.error("unhandled exception route=%s method=%s request_id=%s trace_id=%s duration=%.3f error=%s", 
                     route, method, request_id, trace_id or "none", duration, str(e),
                     extra={"request_id": request_id, "trace_id": trace_id} if trace_id else {"request_id": request_id})
        raise


# Real-time metrics buffer (keeps last 6 hours)
# Each event is stored with timestamp for time-based retention
REALTIME_RETENTION_HOURS = 6
REALTIME_RETENTION_SECONDS = REALTIME_RETENTION_HOURS * 3600

class RealtimeMetricsBuffer:
    """Thread-safe buffer for real-time metrics with 6-hour retention"""
    def __init__(self):
        self.borrows = deque(maxlen=100000)  # ~28 per second for 6 hours
        self.returns = deque(maxlen=100000)
        self.failures = deque(maxlen=10000)
        
        # Per-tool aggregated metrics (for charting)
        # Structure: { tool_name: deque([(timestamp, borrow_count, users_list)]) }
        self.tool_metrics = {}
        
    def add_borrow(self, tool: str, user: str, is_overage: bool, borrow_id: str):
        """Record a borrow event"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "borrow",
            "tool": tool,
            "user": user,
            "is_overage": is_overage,
            "id": borrow_id
        }
        self.borrows.append(event)
        self._cleanup_old_events()
    
    def add_return(self, borrow_id: str, user: str = None):
        """Record a return event"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "return",
            "id": borrow_id,
            "user": user
        }
        self.returns.append(event)
        self._cleanup_old_events()
    
    def add_failure(self, tool: str, user: str, reason: str):
        """Record a failure event"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "failure",
            "tool": tool,
            "user": user,
            "reason": reason
        }
        self.failures.append(event)
        self._cleanup_old_events()
    
    def _cleanup_old_events(self):
        """Remove events older than 6 hours"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=REALTIME_RETENTION_SECONDS)
        cutoff_iso = cutoff.isoformat()
        
        # Clean borrows
        while self.borrows and self.borrows[0]["timestamp"] < cutoff_iso:
            self.borrows.popleft()
        
        # Clean returns
        while self.returns and self.returns[0]["timestamp"] < cutoff_iso:
            self.returns.popleft()
        
        # Clean failures
        while self.failures and self.failures[0]["timestamp"] < cutoff_iso:
            self.failures.popleft()
    
    def get_recent_events(self, seconds: int = 60):
        """Get events from the last N seconds (max 6 hours)"""
        # Limit to retention period
        seconds = min(seconds, REALTIME_RETENTION_SECONDS)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        cutoff_iso = cutoff.isoformat()
        
        recent_borrows = [e for e in self.borrows if e["timestamp"] >= cutoff_iso]
        recent_returns = [e for e in self.returns if e["timestamp"] >= cutoff_iso]
        recent_failures = [e for e in self.failures if e["timestamp"] >= cutoff_iso]
        
        return {
            "borrows": recent_borrows,
            "returns": recent_returns,
            "failures": recent_failures
        }
    
    def get_stats_summary(self):
        """Get summary statistics"""
        return {
            "total_events": len(self.borrows) + len(self.returns) + len(self.failures),
            "borrow_count": len(self.borrows),
            "return_count": len(self.returns),
            "failure_count": len(self.failures),
            "retention_hours": REALTIME_RETENTION_HOURS,
            "oldest_event": self.borrows[0]["timestamp"] if self.borrows else None
        }
    
    def aggregate_tool_metrics(self, window_seconds: int = 60):
        """Aggregate borrow events into per-tool, per-minute data points for charting
        
        This creates time-series data that persists when users switch tool views.
        Aggregates events into 1-minute buckets.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        cutoff_iso = cutoff.isoformat()
        
        # Get recent borrows within window
        recent_borrows = [e for e in self.borrows if e["timestamp"] >= cutoff_iso]
        
        # Group by tool and minute
        tool_data = {}
        for event in recent_borrows:
            tool = event["tool"]
            if tool not in tool_data:
                tool_data[tool] = {}
            
            # Round timestamp to minute
            event_time = datetime.fromisoformat(event["timestamp"])
            minute_key = event_time.replace(second=0, microsecond=0).isoformat()
            
            if minute_key not in tool_data[tool]:
                tool_data[tool][minute_key] = {
                    "count": 0,
                    "users": set(),
                    "overage_count": 0
                }
            
            tool_data[tool][minute_key]["count"] += 1
            tool_data[tool][minute_key]["users"].add(event["user"])
            if event.get("is_overage"):
                tool_data[tool][minute_key]["overage_count"] += 1
        
        # Convert to sorted list format
        result = {}
        for tool, minutes in tool_data.items():
            result[tool] = [
                {
                    "timestamp": ts,
                    "count": data["count"],
                    "users": list(data["users"]),
                    "overage_count": data["overage_count"]
                }
                for ts, data in sorted(minutes.items())
            ]
        
        return result
    
    def get_tool_history(self, tool: str, window_seconds: int = 1800):
        """Get aggregated history for a specific tool
        
        Returns time-series data suitable for charting
        """
        all_metrics = self.aggregate_tool_metrics(window_seconds)
        return all_metrics.get(tool, [])

# Global instance
realtime_buffer = RealtimeMetricsBuffer()


class BorrowRequest(BaseModel):
    tool: str = Field(..., min_length=1)
    user: str = Field(..., min_length=1)


class BorrowResponse(BaseModel):
    id: str
    tool: str
    user: str
    borrowed_at: str


class ReturnRequest(BaseModel):
    id: str = Field(..., min_length=1)


class StatusResponse(BaseModel):
    tool: str
    total: int
    borrowed: int
    available: int
    commit: int = 0
    max_overage: int = 0
    overage: int = 0
    in_commit: bool = True
    commit_price: float = 0.0
    overage_price_per_license: float = 0.0
    current_overage_cost: float = 0.0
    total_cost: float = 0.0


class BorrowRecord(BaseModel):
    id: str
    tool: str
    user: str
    borrowed_at: str


class FrontendError(BaseModel):
    message: str
    stack: Optional[str] = None
    source: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None


class BudgetConfigRequest(BaseModel):
    tool: str
    total: int = Field(..., ge=1)
    commit: int = Field(..., ge=0)
    max_overage: int = Field(..., ge=0)
    commit_price: float = Field(..., ge=0.0)
    overage_price_per_license: float = Field(..., ge=0.0)
class SpendProtectionRequest(BaseModel):
    tool: str
    max_spend: Optional[float] = Field(None, ge=0.0)


class RequestMorePayload(BaseModel):
    tool: str
    message: Optional[str] = None
    requested_total: Optional[int] = Field(None, ge=0)
    requested_overage: Optional[int] = Field(None, ge=0)



class AddCustomerRequest(BaseModel):
    tenant_id: str
    company_name: str
    domain: Optional[str] = None
    crm_id: Optional[str] = None


class ProvisionLicenseRequest(BaseModel):
    tenant_id: str
    product_id: str
    product_name: str
    total: int
    commit_qty: int
    max_overage: int
    commit_price: float = 1000.0
    overage_price_per_license: float = 100.0
    crm_opportunity_id: Optional[str] = None


@app.on_event("startup")
def startup_event() -> None:
    # Seed some tools unless running tests
    if os.getenv("LICENSE_DB_SEED", "true").lower() == "true":
        # Seed with automotive software development tools
        tools_config = [
            {"tool": "ECU Development Suite", "total": 20, "commit_qty": 5, "max_overage": 15, "commit_price": 5000.0, "overage_price_per_license": 500.0},
            {"tool": "GreenHills Multi IDE", "total": 15, "commit_qty": 10, "max_overage": 5, "commit_price": 8000.0, "overage_price_per_license": 800.0},
            {"tool": "AUTOSAR Configuration Tool", "total": 12, "commit_qty": 8, "max_overage": 4, "commit_price": 4000.0, "overage_price_per_license": 400.0},
            {"tool": "CAN Bus Analyzer Pro", "total": 10, "commit_qty": 10, "max_overage": 0, "commit_price": 2000.0, "overage_price_per_license": 0.0},
            {"tool": "Model-Based Design Studio", "total": 18, "commit_qty": 6, "max_overage": 12, "commit_price": 6000.0, "overage_price_per_license": 600.0},
        ]
        initialize_database(tools_config)
        logger.info("database initialized with seed data for automotive tools")
    else:
        initialize_database()
        logger.info("database initialized without seed data")
    logger.info("app_version=%s", APP_VERSION)


@app.post("/licenses/borrow", response_model=BorrowResponse)
def borrow(req: BorrowRequest, request: Request):
    # Validate HMAC signature
    from app.security import validate_signature
    # Extract API key from Authorization header (Bearer <key>)
    auth_header = request.headers.get("Authorization", "")
    api_key = ""
    if auth_header.lower().startswith("bearer "):
        api_key = auth_header.split(" ", 1)[1].strip()
    
    # If API key is provided, validate it (reject invalid keys)
    if api_key:
        try:
            from .db import validate_api_key as db_validate_api_key
            api_key_details = db_validate_api_key(api_key)
            if not api_key_details:
                logger.warning("invalid api key provided")
                raise HTTPException(status_code=403, detail="Invalid API key")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            raise HTTPException(status_code=500, detail="API key validation failed")
    
    # Check if this is a browser request (web UI) - skip signature validation for browser requests
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    user_agent = request.headers.get("User-Agent", "")
    is_browser_request = origin or referer or ("Mozilla" in user_agent or "Chrome" in user_agent or "Safari" in user_agent or "Firefox" in user_agent)
    
    # For browser requests without signature headers, skip validation
    # For API clients (with signature headers), always validate
    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")
    has_signature_headers = signature and timestamp
    
    if has_signature_headers:
        # API client with signature - validate it
        is_valid, error_msg = validate_signature(request, req.tool, req.user, api_key=api_key, require=True)
        if not is_valid:
            logger.warning("Security check failed: %s", error_msg)
            raise HTTPException(status_code=403, detail=f"Security validation failed: {error_msg}")
    elif is_browser_request:
        # Browser request without signature - allow it (web UI)
        logger.debug("Browser request detected, skipping signature validation")
    else:
        # Non-browser request without signature - require it
        is_valid, error_msg = validate_signature(request, req.tool, req.user, api_key=api_key, require=True)
        if not is_valid:
            logger.warning("Security check failed: %s", error_msg)
            raise HTTPException(status_code=403, detail=f"Security validation failed: {error_msg}")
    
    start = time.perf_counter()
    borrow_attempts.labels(req.tool, req.user).inc()
    borrow_id = str(uuid.uuid4())
    borrowed_at = datetime.now(timezone.utc).isoformat()
    # Enforce spend protection before attempting overage borrows
    # Check current status
    status_snapshot = get_status(req.tool)
    if status_snapshot:
        borrowed_now = int(status_snapshot["borrowed"])
        commit_now = int(status_snapshot["commit"])
        overage_now = max(borrowed_now - commit_now, 0)
        will_be_overage = borrowed_now >= commit_now
        if will_be_overage:
            from .db import get_customer_max_spend, get_month_to_date_overage_cost
            max_spend = get_customer_max_spend(req.tool)
            if max_spend is not None:
                current_cost = get_month_to_date_overage_cost(req.tool)
                # Estimated next overage cost
                next_cost = float(status_snapshot.get("overage_price_per_license", 0.0))
                if current_cost + next_cost > max_spend:
                    logger.warning("borrow blocked by max spend tool=%s user=%s cost=%.2f next=%.2f cap=%.2f", req.tool, req.user, current_cost, next_cost, max_spend)
                    raise HTTPException(status_code=403, detail="Customer max spend reached for this period")

    ok, is_overage = borrow_license(req.tool, req.user, borrow_id, borrowed_at)
    duration = time.perf_counter() - start
    borrow_duration.labels(req.tool).observe(duration)
    if not ok:
        # record failure reason
        status = get_status(req.tool)
        reason = "unknown"
        if status is None:
            reason = "unknown_tool"
        elif status["borrowed"] >= status["total"]:
            reason = "exhausted"
        elif status["overage"] >= status["max_overage"]:
            reason = "max_overage"
        borrow_failures.labels(req.tool, reason).inc()
        # Record failure in real-time buffer
        realtime_buffer.add_failure(req.tool, req.user, reason)
        logger.warning("borrow failed tool=%s user=%s reason=%s", req.tool, req.user, reason)
        raise HTTPException(status_code=409, detail=f"No licenses available for {req.tool}")
    # update gauges
    status = get_status(req.tool)
    if status:
        borrowed_gauge.labels(req.tool).set(status["borrowed"])
        total_licenses_gauge.labels(req.tool).set(status["total"])
        overage_gauge.labels(req.tool).set(status["overage"])
        commit_gauge.labels(req.tool).set(status["commit"])
        max_overage_gauge.labels(req.tool).set(status["max_overage"])
        at_max_overage_gauge.labels(req.tool).set(1 if status["overage"] >= status["max_overage"] else 0)
    borrow_successes.labels(req.tool, req.user).inc()
    
    # Track overage checkouts
    if is_overage:
        overage_checkouts.labels(req.tool, req.user).inc()
    
    # Record in real-time buffer
    realtime_buffer.add_borrow(req.tool, req.user, is_overage, borrow_id)
    
    overage_str = " (overage)" if is_overage else ""
    logger.info("borrow success tool=%s user=%s id=%s borrowed=%d/%d%s", req.tool, req.user, borrow_id, status["borrowed"], status["total"] if status else -1, overage_str)
    return BorrowResponse(id=borrow_id, tool=req.tool, user=req.user, borrowed_at=borrowed_at)


@app.get("/faulty")
def faulty() -> Dict[str, str]:
    """Deliberately return a 500 for demo/alerting purposes."""
    logger.debug("faulty endpoint triggered, simulating error")
    logger.error("faulty endpoint error=simulated failure for demo")
    raise HTTPException(status_code=500, detail="Simulated failure")


@app.post("/licenses/return")
def return_(req: ReturnRequest) -> Dict[str, str]:
    tool = return_license(req.id)
    if tool is None:
        logger.warning("return failed id=%s not_found=1", req.id)
        raise HTTPException(status_code=404, detail="Borrow record not found")
    
    # Record in real-time buffer
    realtime_buffer.add_return(req.id)
    
    status = get_status(tool)
    if status:
        borrowed_gauge.labels(tool).set(status["borrowed"])
        total_licenses_gauge.labels(tool).set(status["total"])
        overage_gauge.labels(tool).set(status["overage"])
        commit_gauge.labels(tool).set(status["commit"])
        max_overage_gauge.labels(tool).set(status["max_overage"])
        at_max_overage_gauge.labels(tool).set(1 if status["overage"] >= status["max_overage"] else 0)
    logger.info("return success id=%s tool=%s borrowed=%d/%d", req.id, tool, status["borrowed"] if status else -1, status["total"] if status else -1)
    return {"status": "ok", "tool": tool}


@app.get("/licenses/{tool}/status", response_model=StatusResponse)
def status(tool: str):
    s = get_status(tool)
    if s is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return StatusResponse(**s)


@app.get("/licenses/status", response_model=List[StatusResponse])
def status_all():
    from .db import get_connection
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tool, total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license FROM licenses ORDER BY tool ASC")
        rows = cur.fetchall()
        result: List[StatusResponse] = []
        for r in rows:
            total = int(r["total"])
            borrowed = int(r["borrowed"])
            commit = int(r["commit_qty"] or 0)
            max_overage = int(r["max_overage"] or 0)
            commit_price = float(r["commit_price"] or 0.0)
            overage_price = float(r["overage_price_per_license"] or 0.0)
            overage = max(borrowed - commit, 0)
            
            # Calculate accumulated overage costs from overage_charges table (persists even after return)
            cur.execute("SELECT COUNT(*) as cnt FROM overage_charges WHERE tool = ?", (r["tool"],))
            overage_charges_count = int(cur.fetchone()["cnt"] or 0)
            current_overage_cost = overage_charges_count * overage_price
            total_cost = commit_price + current_overage_cost
            
            result.append(StatusResponse(
                tool=r["tool"],
                total=total,
                borrowed=borrowed,
                available=max(total - borrowed, 0),
                commit=commit,
                max_overage=max_overage,
                overage=overage,
                in_commit=borrowed <= commit,
                commit_price=commit_price,
                overage_price_per_license=overage_price,
                current_overage_cost=current_overage_cost,
                total_cost=total_cost
            ))
        return result


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/logs")
def logs(limit: int = 100):
    """Get recent logs in plain text format for Promtail scraping
    
    Args:
        limit: Maximum number of log entries to return (default 100, max 1000)
    
    Returns:
        Plain text log entries, one per line, in format suitable for Promtail scraping
    """
    limit = min(max(limit, 1), 1000)  # Clamp between 1 and 1000
    log_data = log_buffer.get_recent_logs(limit=limit)
    return Response(
        content=log_data,
        media_type="text/plain",
        headers={
            "X-Log-Entries": str(limit),
            "Cache-Control": "no-cache"
        }
    )


@app.get("/realtime/stats")
def realtime_stats(window: int = 60):
    """Get real-time buffer statistics and recent events
    
    Args:
        window: Time window in seconds (default 60, max 21600 for 6 hours)
    """
    # Limit window to retention period
    window = min(window, REALTIME_RETENTION_SECONDS)
    
    return {
        **realtime_buffer.get_stats_summary(),
        f"recent_{window}s": realtime_buffer.get_recent_events(window),
        "window_seconds": window
    }


@app.get("/realtime/stream")
async def realtime_stream(request: Request):
    """Server-Sent Events stream for real-time metrics"""
    async def event_generator():
        last_sent = time.time()
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("realtime stream client disconnected")
                break
            
            # Send update every 2 seconds
            now = time.time()
            if now - last_sent >= 2.0:
                # Get current status for all tools
                status_all_tools = []
                try:
                    tools = get_all_tools()
                    for tool_data in tools:
                        s = get_status(tool_data["tool"])
                        if s:
                            status_all_tools.append(s)
                except Exception as e:
                    logger.error(f"Error getting status in realtime stream: {e}")
                
                # Get recent events (last 60 seconds for rate calculation)
                recent_60s = realtime_buffer.get_recent_events(60)
                
                # Calculate rates (per minute, based on last 60 seconds)
                borrow_rate = len(recent_60s["borrows"])  # events in last 60s = per minute
                return_rate = len(recent_60s["returns"])
                failure_rate = len(recent_60s["failures"])
                
                # Calculate overage rate (from last 60s)
                total_borrows = len(recent_60s["borrows"])
                overage_borrows = sum(1 for b in recent_60s["borrows"] if b.get("is_overage"))
                overage_rate = (overage_borrows / total_borrows * 100) if total_borrows > 0 else 0
                
                # Get per-tool aggregated metrics (for persistent charts)
                # This is the key: server maintains history per tool
                tool_metrics = realtime_buffer.aggregate_tool_metrics(window_seconds=REALTIME_RETENTION_SECONDS)
                
                # Build event data
                data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tools": status_all_tools,
                    "rates": {
                        "borrow_per_min": borrow_rate,
                        "return_per_min": return_rate,
                        "failure_per_min": failure_rate,
                        "overage_percent": round(overage_rate, 1)
                    },
                    "recent_events": {
                        "borrows": recent_60s["borrows"][-10:],  # Last 10 from 60s window
                        "returns": recent_60s["returns"][-10:],
                        "failures": recent_60s["failures"][-10:]
                    },
                    "buffer_stats": realtime_buffer.get_stats_summary(),
                    "tool_metrics": tool_metrics  # Add per-tool time-series data
                }
                
                # Send as SSE
                yield f"data: {json.dumps(data)}\n\n"
                last_sent = now
            
            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# Static frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def root():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    with open("app/static/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/welcome", response_class=HTMLResponse)
def welcome_page():
    with open("app/static/welcome.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/realtime", response_class=HTMLResponse)
def realtime_page():
    with open("app/static/realtime.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/frontend-error")
def frontend_error(err: FrontendError):
    logger.warning(
        "frontend error msg=%s source=%s line=%s col=%s url=%s ua=%s",
        err.message,
        err.source,
        str(err.lineno),
        str(err.colno),
        err.url,
        err.userAgent,
    )
    return {"status": "ok"}


# DevOps Overview page removed - now integrated into presentation
# @app.get("/overview", response_class=HTMLResponse)
# def overview_page():
#     with open("app/static/overview.html", "r", encoding="utf-8") as f:
#         return f.read()


@app.get("/presentation", response_class=HTMLResponse)
def presentation_page():
    with open("app/static/presentation.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/multitenant", response_class=HTMLResponse)
def multitenant_page():
    """Multi-tenant demo overview page"""
    with open("app/static/multitenant.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/version")
def get_version() -> Dict[str, str]:
    return {"version": APP_VERSION}


@app.get("/config/budget")
def get_budget_config():
    """Get budget configuration for all tools"""
    tools = get_all_tools()
    # Enrich with spend protection and month-to-date cost
    from .db import get_customer_max_spend, get_month_to_date_overage_cost
    enriched = []
    for t in tools:
        tool_name = t.get("tool")
        max_spend = get_customer_max_spend(tool_name)
        mtd_cost = get_month_to_date_overage_cost(tool_name)
        remaining = None
        if max_spend is not None:
            remaining = max(0.0, float(max_spend) - float(mtd_cost))
        item = dict(t)
        item["customer_max_spend"] = max_spend
        item["month_to_date_overage_cost"] = mtd_cost
        item["remaining_spend"] = remaining
        enriched.append(item)
    return {"tools": enriched}


@app.put("/config/budget")
def update_budget(req: BudgetConfigRequest):
    """Update budget configuration for a tool (customer restrictions only)"""
    from app.db import set_customer_budget_restrictions
    
    success, error_msg = set_customer_budget_restrictions(
        req.tool, 
        req.total, 
        req.commit, 
        req.max_overage
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Also update pricing if changed
    if not update_budget_config(req.tool, req.total, req.commit, req.max_overage, req.commit_price, req.overage_price_per_license):
        raise HTTPException(status_code=400, detail="Failed to update pricing")
    
    logger.info("customer budget restricted tool=%s total=%d commit=%d max_overage=%d", req.tool, req.total, req.commit, req.max_overage)
    return {"status": "ok", "tool": req.tool}


@app.put("/config/protection")
def update_spend_protection(req: SpendProtectionRequest):
    """Update customer max spend protection for a tool"""
    from .db import set_customer_max_spend
    if not set_customer_max_spend(req.tool, req.max_spend):
        raise HTTPException(status_code=400, detail="Tool not found")
    logger.info("customer max spend updated tool=%s max_spend=%s", req.tool, str(req.max_spend))
    return {"status": "ok", "tool": req.tool, "max_spend": req.max_spend}


@app.post("/api/customer/request-more")
def customer_request_more(req: RequestMorePayload):
    """Customers can request more capacity; stored for vendor review (demo)."""
    from .db import get_connection
    try:
        with get_connection(False) as conn:
            cur = conn.cursor()
            # Create table if not exists
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS request_more (
                    id TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    message TEXT,
                    requested_total INTEGER,
                    requested_overage INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            rid = str(uuid.uuid4())
            created_at = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO request_more(id, tool, message, requested_total, requested_overage, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (rid, req.tool, (req.message or ""), req.requested_total, req.requested_overage, created_at)
            )
            conn.commit()
        logger.info("customer_request_more id=%s tool=%s msg=%s total=%s overage=%s", rid, req.tool, (req.message or ""), str(req.requested_total), str(req.requested_overage))
        return {"status": "queued", "id": rid}
    except Exception as e:
        logger.error(f"request_more failed: {e}")
        raise HTTPException(500, "Failed to submit request")


@app.put("/api/vendor/budget")
def update_vendor_budget(req: BudgetConfigRequest):
    """Update vendor-controlled budget for a tool (vendor portal only)"""
    from app.db import set_vendor_budget
    
    if not set_vendor_budget(req.tool, req.total, req.commit, req.max_overage):
        raise HTTPException(status_code=400, detail="Tool not found")
    
    # Also update pricing
    if not update_budget_config(req.tool, req.total, req.commit, req.max_overage, req.commit_price, req.overage_price_per_license):
        raise HTTPException(status_code=400, detail="Failed to update pricing")
    
    logger.info("vendor budget set tool=%s total=%d commit=%d max_overage=%d", req.tool, req.total, req.commit, req.max_overage)
    return {"status": "ok", "tool": req.tool}


@app.get("/api/vendor/budget/{tool}")
def get_vendor_budget(tool: str):
    """Get vendor and customer budget configuration"""
    from app.db import get_budget_config
    
    config = get_budget_config(tool)
    if not config:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return config


@app.get("/config", response_class=HTMLResponse)
def config_page():
    with open("app/static/config.html", "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# CUSTOMER API KEY MANAGEMENT (self-service)
# ============================================================================

class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1)
    environment: str = Field("live")  # live | test | dev
    tenant_id: Optional[str] = None  # demo: optional single-tenant


@app.get("/api/keys")
def list_api_keys_endpoint(tenant_id: Optional[str] = None):
    """List API keys for the current customer (demo: tenant optional)."""
    from .db import list_api_keys
    try:
        keys = list_api_keys(tenant_id)
        return {"keys": keys}
    except Exception as e:
        logger.error(f"Error listing api keys: {e}")
        raise HTTPException(500, "Failed to list API keys")


@app.post("/api/keys")
def create_api_key_endpoint(req: CreateApiKeyRequest):
    """Generate a new API key (shown once)."""
    from .db import generate_api_key
    try:
        api_key, key_id = generate_api_key(tenant_id=req.tenant_id, name=req.name, environment=req.environment)
        logger.info("api_key_created key_id=%s tenant=%s env=%s", key_id, req.tenant_id, req.environment)
        return {"key_id": key_id, "api_key": api_key}
    except Exception as e:
        logger.error(f"Error generating api key: {e}")
        raise HTTPException(500, "Failed to generate API key")


@app.delete("/api/keys/{key_id}")
def revoke_api_key_endpoint(key_id: str):
    """Revoke an API key by ID."""
    from .db import revoke_api_key
    try:
        ok = revoke_api_key(key_id)
        if not ok:
            raise HTTPException(404, "API key not found")
        logger.info("api_key_revoked key_id=%s", key_id)
        return {"status": "revoked", "key_id": key_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking api key: {e}")
        raise HTTPException(500, "Failed to revoke API key")


@app.get("/security-demo", response_class=HTMLResponse)
def security_demo_page():
    """Security demonstration page"""
    with open("app/static/security-demo.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/borrows", response_model=List[BorrowRecord])
def list_borrows(user: Optional[str] = None):
    # Simple listing of current borrows
    from .db import get_connection, initialize_database
    # ensure tables exist
    initialize_database()
    with get_connection(False) as conn:
        cur = conn.cursor()
        if user:
            cur.execute(
                "SELECT id, tool, user, borrowed_at FROM borrows WHERE user = ? ORDER BY borrowed_at DESC",
                (user,),
            )
        else:
            cur.execute("SELECT id, tool, user, borrowed_at FROM borrows ORDER BY borrowed_at DESC")
        rows = cur.fetchall()
        return [BorrowRecord(id=r["id"], tool=r["tool"], user=r["user"], borrowed_at=r["borrowed_at"]) for r in rows]


@app.get("/overage-charges")
def list_overage_charges(tool: Optional[str] = None):
    """Get all overage charges, optionally filtered by tool"""
    charges = get_overage_charges(tool)
    return {"charges": charges}


# ============================================================================
# VENDOR PORTAL ENDPOINTS
# ============================================================================

@app.get("/vendor", response_class=HTMLResponse)
def vendor_portal_page():
    """Vendor portal UI"""
    with open("app/static/vendor.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/vendor/customers")
def get_customers():
    """Get all customers for the vendor (Vector)"""
    try:
        # Check if multi-tenant tables exist
        from .db import get_connection
        with get_connection(True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'")
            if not cur.fetchone():
                # Multi-tenant tables don't exist yet, return demo data
                return {
                    "customers": [
                        {"tenant_id": "demo", "company_name": "Demo Company", "domain": "demo.com", "crm_id": "CRM-DEMO-001", "active_licenses": 6, "status": "active"}
                    ]
                }
        
        # Multi-tenant tables exist, get real data
        customers = get_vendor_customers("techvendor")
        if not customers:
            # Fallback to demo data if none found
            return {
                "customers": [
                    {"tenant_id": "acme", "company_name": "Acme Corporation", "domain": "acme.com", "crm_id": "CRM-ACME-001", "active_licenses": 3, "status": "active"},
                    {"tenant_id": "globex", "company_name": "Globex Industries", "domain": "globex.com", "crm_id": "CRM-GLOBEX-002", "active_licenses": 2, "status": "active"}
                ]
            }
        return {"customers": customers}
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        # Return demo data if error
        return {
            "customers": [
                {"tenant_id": "demo", "company_name": "Demo Company", "domain": "demo.com", "crm_id": "CRM-DEMO-001", "active_licenses": 6, "status": "active"}
            ]
        }


@app.post("/api/vendor/customers")
def add_customer(req: AddCustomerRequest):
    """Add a new customer tenant"""
    from datetime import datetime
    from .db import get_connection
    
    try:
        # Ensure multi-tenant tables exist
        initialize_database(enable_multitenant=True)
        
        with get_connection(False) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            
            cur.execute(
                "INSERT INTO tenants(tenant_id, company_name, domain, crm_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
                (req.tenant_id, req.company_name, req.domain, req.crm_id, now)
            )
            conn.commit()
        
        logger.info(f"Added customer: {req.company_name} ({req.tenant_id})")
        return {"status": "ok", "tenant_id": req.tenant_id}
    except Exception as e:
        logger.error(f"Error adding customer: {e}")
        raise HTTPException(500, f"Failed to add customer: {str(e)}")


@app.post("/api/vendor/provision")
def provision_license(req: ProvisionLicenseRequest):
    """Provision a new license to a customer"""
    try:
        # Ensure multi-tenant tables exist
        initialize_database(enable_multitenant=True)
        
        package_id = provision_license_to_tenant(
            vendor_id="vector",
            tenant_id=req.tenant_id,
            product_config={
                "product_id": req.product_id,
                "product_name": req.product_name,
                "total": req.total,
                "commit_qty": req.commit_qty,
                "max_overage": req.max_overage,
                "commit_price": req.commit_price,
                "overage_price_per_license": req.overage_price_per_license,
                "crm_opportunity_id": req.crm_opportunity_id
            }
        )
        
        logger.info(f"Provisioned license package {package_id} to tenant {req.tenant_id}")
        return {"status": "provisioned", "package_id": package_id}
    except Exception as e:
        logger.error(f"Error provisioning license: {e}")
        raise HTTPException(500, f"Failed to provision license: {str(e)}")


# ============================================================================
# ADMIN API ENDPOINTS
# ============================================================================

def verify_admin_api_key(request: Request) -> bool:
    """Verify admin API key from Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    provided_key = auth_header.replace("Bearer ", "")
    admin_key = os.getenv("PERMETRIX_ADMIN_API_KEY")
    
    if not admin_key:
        raise HTTPException(500, "Admin API not configured. Set PERMETRIX_ADMIN_API_KEY environment variable.")
    
    if provided_key != admin_key:
        logger.warning(f"Invalid admin API key attempt from {request.client.host}")
        raise HTTPException(403, "Invalid admin API key")
    
    return True


# Request models
class CreateTenantRequest(BaseModel):
    company_name: str
    contact_email: str
    tenant_id: Optional[str] = None
    crm_id: Optional[str] = None
    company_domain: Optional[str] = None


class CreateVendorRequest(BaseModel):
    vendor_name: str
    contact_email: str
    vendor_id: Optional[str] = None


@app.post("/api/admin/tenants")
async def admin_create_tenant(req: CreateTenantRequest, request: Request):
    """Create a new customer tenant (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        result = create_tenant(
            company_name=req.company_name,
            contact_email=req.contact_email,
            tenant_id=req.tenant_id,
            crm_id=req.crm_id,
            company_domain=req.company_domain
        )
        logger.info(f"Admin created tenant: {result['tenant_id']} ({req.company_name})")
        return result
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise HTTPException(500, f"Failed to create tenant: {str(e)}")


@app.get("/api/admin/tenants")
async def admin_list_tenants(request: Request):
    """List all tenants (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        tenants = get_all_tenants()
        return {"tenants": tenants}
    except Exception as e:
        logger.error(f"Error listing tenants: {e}")
        raise HTTPException(500, f"Failed to list tenants: {str(e)}")


@app.get("/api/admin/tenants/{tenant_id}")
async def admin_get_tenant(tenant_id: str, request: Request):
    """Get tenant details (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        tenants = get_all_tenants()
        tenant = next((t for t in tenants if t["tenant_id"] == tenant_id), None)
        if not tenant:
            raise HTTPException(404, f"Tenant {tenant_id} not found")
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant: {e}")
        raise HTTPException(500, f"Failed to get tenant: {str(e)}")


@app.post("/api/admin/vendors")
async def admin_create_vendor(req: CreateVendorRequest, request: Request):
    """Create a new vendor (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        result = create_vendor(
            vendor_name=req.vendor_name,
            contact_email=req.contact_email,
            vendor_id=req.vendor_id
        )
        logger.info(f"Admin created vendor: {result['vendor_id']} ({req.vendor_name})")
        return result
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        logger.error(f"Error creating vendor: {e}")
        raise HTTPException(500, f"Failed to create vendor: {str(e)}")


@app.get("/api/admin/vendors")
async def admin_list_vendors(request: Request):
    """List all vendors (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        vendors = get_all_vendors()
        return {"vendors": vendors}
    except Exception as e:
        logger.error(f"Error listing vendors: {e}")
        raise HTTPException(500, f"Failed to list vendors: {str(e)}")


@app.get("/api/admin/vendors/{vendor_id}")
async def admin_get_vendor(vendor_id: str, request: Request):
    """Get vendor details (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        vendors = get_all_vendors()
        vendor = next((v for v in vendors if v["vendor_id"] == vendor_id), None)
        if not vendor:
            raise HTTPException(404, f"Vendor {vendor_id} not found")
        return vendor
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vendor: {e}")
        raise HTTPException(500, f"Failed to get vendor: {str(e)}")


@app.get("/api/admin/stats")
async def admin_platform_stats(request: Request):
    """Get platform statistics (Admin API)"""
    verify_admin_api_key(request)
    
    try:
        initialize_database(enable_multitenant=True)
        
        with get_connection(True) as conn:
            cur = conn.cursor()
            
            # Tenant stats
            try:
                cur.execute("SELECT COUNT(*) FROM tenants")
                total_tenants = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM tenants WHERE status = 'active'")
                active_tenants = cur.fetchone()[0]
            except sqlite3.OperationalError:
                total_tenants = 0
                active_tenants = 0
            
            # Vendor stats
            try:
                cur.execute("SELECT COUNT(*) FROM vendors")
                total_vendors = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM vendors WHERE status = 'active'")
                active_vendors = cur.fetchone()[0]
            except sqlite3.OperationalError:
                total_vendors = 0
                active_vendors = 0
            
            # License stats
            try:
                cur.execute("SELECT COUNT(*) FROM licenses")
                total_licenses = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM borrows")
                active_borrows = cur.fetchone()[0]
            except sqlite3.OperationalError:
                total_licenses = 0
                active_borrows = 0
        
        return {
            "tenants": {
                "total": total_tenants,
                "active": active_tenants
            },
            "vendors": {
                "total": total_vendors,
                "active": active_vendors
            },
            "licenses": {
                "total_provisioned": total_licenses,
                "active_borrows": active_borrows
            }
        }
    except Exception as e:
        logger.error(f"Error getting platform stats: {e}")
        raise HTTPException(500, f"Failed to get platform stats: {str(e)}")


@app.delete("/api/admin/tenants/{tenant_id}")
async def admin_delete_tenant(tenant_id: str, request: Request, hard_delete: bool = False):
    """Delete a tenant (Admin API)
    
    Args:
        tenant_id: Tenant ID to delete
        hard_delete: If True, permanently delete. If False, soft delete (default).
    """
    verify_admin_api_key(request)
    
    try:
        result = delete_tenant(tenant_id, hard_delete=hard_delete)
        logger.info(f"Admin deleted tenant: {tenant_id} (hard_delete={hard_delete})")
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error deleting tenant: {e}")
        raise HTTPException(500, f"Failed to delete tenant: {str(e)}")


@app.delete("/api/admin/vendors/{vendor_id}")
async def admin_delete_vendor(vendor_id: str, request: Request, hard_delete: bool = False):
    """Delete a vendor (Admin API)
    
    Args:
        vendor_id: Vendor ID to delete
        hard_delete: If True, permanently delete. If False, soft delete (default).
    """
    verify_admin_api_key(request)
    
    try:
        result = delete_vendor(vendor_id, hard_delete=hard_delete)
        logger.info(f"Admin deleted vendor: {vendor_id} (hard_delete={hard_delete})")
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error deleting vendor: {e}")
        raise HTTPException(500, f"Failed to delete vendor: {str(e)}")


