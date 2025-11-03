import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from .db import initialize_database, borrow_license, return_license, get_status, update_budget_config, get_all_tools, get_overage_charges


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


@app.on_event("startup")
def startup_event() -> None:
    # Seed some tools unless running tests
    if os.getenv("LICENSE_DB_SEED", "true").lower() == "true":
        # Seed with automotive software license products
        tools_config = [
            {"tool": "Vector - DaVinci Configurator SE", "total": 20, "commit_qty": 5, "max_overage": 15, "commit_price": 5000.0, "overage_price_per_license": 500.0},
            {"tool": "Vector - DaVinci Configurator IDE", "total": 10, "commit_qty": 10, "max_overage": 0, "commit_price": 3000.0, "overage_price_per_license": 0.0},
            {"tool": "Greenhills - Multi 8.2", "total": 20, "commit_qty": 5, "max_overage": 15, "commit_price": 8000.0, "overage_price_per_license": 800.0},
            {"tool": "Vector - ASAP2 v20", "total": 20, "commit_qty": 5, "max_overage": 15, "commit_price": 4000.0, "overage_price_per_license": 400.0},
            {"tool": "Vector - DaVinci Teams", "total": 10, "commit_qty": 10, "max_overage": 0, "commit_price": 2000.0, "overage_price_per_license": 0.0},
            {"tool": "Vector - VTT", "total": 10, "commit_qty": 10, "max_overage": 0, "commit_price": 2500.0, "overage_price_per_license": 0.0},
        ]
        initialize_database(tools_config)
        logger.info("database initialized with seed data for automotive tools")
    else:
        initialize_database()
        logger.info("database initialized without seed data")
    logger.info("app_version=%s", APP_VERSION)


@app.post("/licenses/borrow", response_model=BorrowResponse)
def borrow(req: BorrowRequest):
    start = time.perf_counter()
    borrow_attempts.labels(req.tool, req.user).inc()
    borrow_id = str(uuid.uuid4())
    borrowed_at = datetime.now(timezone.utc).isoformat()
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
    
    overage_str = " (overage)" if is_overage else ""
    logger.info("borrow success tool=%s user=%s id=%s borrowed=%d/%d%s", req.tool, req.user, borrow_id, status["borrowed"], status["total"] if status else -1, overage_str)
    return BorrowResponse(id=borrow_id, tool=req.tool, user=req.user, borrowed_at=borrowed_at)


@app.post("/licenses/return")
def return_(req: ReturnRequest) -> Dict[str, str]:
    tool = return_license(req.id)
    if tool is None:
        logger.warning("return failed id=%s not_found=1", req.id)
        raise HTTPException(status_code=404, detail="Borrow record not found")
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


@app.get("/version")
def get_version() -> Dict[str, str]:
    return {"version": APP_VERSION}


@app.get("/config/budget")
def get_budget_config():
    """Get budget configuration for all tools"""
    tools = get_all_tools()
    return {"tools": tools}


@app.put("/config/budget")
def update_budget(req: BudgetConfigRequest):
    """Update budget configuration for a tool"""
    if not update_budget_config(req.tool, req.total, req.commit, req.max_overage, req.commit_price, req.overage_price_per_license):
        raise HTTPException(status_code=400, detail="Tool not found or total cannot be reduced below current borrows")
    logger.info("budget updated tool=%s total=%d commit=%d max_overage=%d commit_price=%.2f overage_price=%.2f", req.tool, req.total, req.commit, req.max_overage, req.commit_price, req.overage_price_per_license)
    return {"status": "ok", "tool": req.tool}


@app.get("/config", response_class=HTMLResponse)
def config_page():
    with open("app/static/config.html", "r", encoding="utf-8") as f:
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


