import os
import time
import uuid
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from .db import initialize_database, borrow_license, return_license, get_status, update_budget_config, get_all_tools, get_overage_charges, get_all_tenants, get_vendor_customers, provision_license_to_tenant


app = FastAPI(title="License Server", version="0.1.0")

# App version for observability/journey (surfaced in logs & API)
APP_VERSION = os.getenv("APP_VERSION", "dev")

# Basic structured logging to stdout so Promtail/Loki can scrape container logs
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("license-server")


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
http_500_total = Counter("license_http_500_total", "Total HTTP 500 responses emitted by the app", ["route"]) 


@app.middleware("http")
async def catch_500s(request: Request, call_next):
    """Catch all 500 responses and increment metric."""
    response = await call_next(request)
    if response.status_code == 500:
        route = request.url.path
        http_500_total.labels(route=route).inc()
        logger.warning("500 response route=%s", route)
    return response


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
    
    is_valid, error_msg = validate_signature(request, req.tool, req.user, api_key=api_key, require=None)
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
            
            # Send update every second
            now = time.time()
            if now - last_sent >= 1.0:
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


