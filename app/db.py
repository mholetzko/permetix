import os
import sqlite3
import secrets
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, List
from passlib.context import CryptContext
from datetime import datetime


DEFAULT_DB_PATH = "licenses.db"


def get_db_path() -> str:
    env_path = os.getenv("LICENSE_DB_PATH")
    return env_path if env_path else DEFAULT_DB_PATH


def ensure_parent_dir(path: str) -> None:
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    db_path = get_db_path()
    if db_path != ":memory:":
        ensure_parent_dir(db_path)
    uri = f"file:{db_path}?mode={'ro' if readonly else 'rwc'}"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def initialize_database(tools_config: Optional[List[dict]] = None, enable_multitenant: bool = False) -> None:
    """
    Initialize database with optional seed data.
    
    Args:
        tools_config: List of dicts with keys: tool, total, commit_qty, max_overage, commit_price (optional), overage_price_per_license (optional)
        enable_multitenant: If True, add multi-tenant tables and seed data
    """
    with get_connection(readonly=False) as conn:
        cur = conn.cursor()
        
        # Multi-tenant tables (if enabled)
        if enable_multitenant:
            # Tenants (customers like BMW, Mercedes, Audi)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    domain TEXT,
                    crm_id TEXT UNIQUE,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
                """
            )
            
            # Vendors (like Vector, Greenhills)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS vendors (
                    vendor_id TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    contact_email TEXT,
                    api_key_hash TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            
            # License packages (vendor → tenant)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS license_packages (
                    package_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    crm_opportunity_id TEXT,
                    status TEXT DEFAULT 'active',
                    provisioned_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY(vendor_id) REFERENCES vendors(vendor_id)
                )
                """
            )
        
        # Licenses table (now with tenant_id for multi-tenant mode)
        if enable_multitenant:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    package_id TEXT,
                    tool TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    borrowed INTEGER NOT NULL DEFAULT 0,
                    commit_qty INTEGER DEFAULT 0,
                    max_overage INTEGER DEFAULT 0,
                    commit_price REAL DEFAULT 0.0,
                    overage_price_per_license REAL DEFAULT 0.0,
                    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY(package_id) REFERENCES license_packages(package_id),
                    UNIQUE(tenant_id, tool)
                )
                """
            )
        else:
            # Original single-tenant schema
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    tool TEXT PRIMARY KEY,
                    total INTEGER NOT NULL,
                    borrowed INTEGER NOT NULL DEFAULT 0,
                    commit_qty INTEGER DEFAULT 0,
                    max_overage INTEGER DEFAULT 0,
                    commit_price REAL DEFAULT 0.0,
                    overage_price_per_license REAL DEFAULT 0.0,
                    vendor_total INTEGER,
                    vendor_commit_qty INTEGER,
                    vendor_max_overage INTEGER,
                    customer_total INTEGER,
                    customer_commit_qty INTEGER,
                    customer_max_overage INTEGER
                )
                """
            )
        # Borrows table (tenant-aware if multi-tenant)
        if enable_multitenant:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS borrows (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    user TEXT NOT NULL,
                    borrowed_at TEXT NOT NULL,
                    is_overage INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS borrows (
                    id TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    user TEXT NOT NULL,
                    borrowed_at TEXT NOT NULL,
                    is_overage INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(tool) REFERENCES licenses(tool)
                )
                """
            )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
            """
        )
        # Overage charges table (tenant-aware if multi-tenant)
        if enable_multitenant:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS overage_charges (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    borrow_id TEXT NOT NULL,
                    user TEXT NOT NULL,
                    charged_at TEXT NOT NULL,
                    amount REAL NOT NULL,
                    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
                    FOREIGN KEY(borrow_id) REFERENCES borrows(id)
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS overage_charges (
                    id TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    borrow_id TEXT NOT NULL,
                    user TEXT NOT NULL,
                    charged_at TEXT NOT NULL,
                    amount REAL NOT NULL,
                    FOREIGN KEY(tool) REFERENCES licenses(tool),
                    FOREIGN KEY(borrow_id) REFERENCES borrows(id)
                )
                """
            )
        
        # API Keys table (for tenant authentication)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                key_hash TEXT NOT NULL UNIQUE,
                name TEXT,
                environment TEXT DEFAULT 'live',
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                expires_at TEXT,
                status TEXT DEFAULT 'active',
                scopes TEXT DEFAULT 'borrow,return,status',
                FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")
        
        if tools_config:
            for config in tools_config:
                tool = config["tool"]
                total = config["total"]
                commit_qty = config.get("commit_qty", max(1, int(total * 0.8)))
                max_overage = config.get("max_overage", max(1, int(total * 0.2)))
                commit_price = config.get("commit_price", 1000.0)
                overage_price = config.get("overage_price_per_license", 100.0)
                
                cur.execute(
                    "INSERT OR IGNORE INTO licenses(tool, total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license) VALUES (?, ?, 0, ?, ?, ?, ?)",
                    (tool, int(total), commit_qty, max_overage, commit_price, overage_price),
                )
        # seed demo user if empty
        cur.execute("SELECT COUNT(1) AS c FROM users")
        if int(cur.fetchone()["c"]) == 0:
            pwd = get_password_context().hash("demo123")
            cur.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)", ("demo", pwd))
        conn.commit()


def borrow_license(tool: str, user: str, borrow_id: str, borrowed_at_iso: str) -> tuple[bool, bool]:
    """Returns (success, is_overage)"""
    with get_connection(False) as conn:
        cur = conn.cursor()
        cur.execute("SELECT total, borrowed, commit_qty, max_overage, overage_price_per_license FROM licenses WHERE tool = ?", (tool,))
        row = cur.fetchone()
        if row is None:
            return False, False
        total = int(row["total"])
        borrowed = int(row["borrowed"])
        commit = int(row["commit_qty"] or 0)
        max_overage = int(row["max_overage"] or 0)
        overage_price = float(row["overage_price_per_license"] or 0.0)
        
        # Check if we can borrow
        if borrowed >= total:
            return False, False
        
        # Check if we're in commit range or overage
        is_overage = borrowed >= commit
        if is_overage:
            # Count current overage
            current_overage = borrowed - commit
            if current_overage >= max_overage:
                return False, False  # Max overage reached
        
        cur.execute("UPDATE licenses SET borrowed = borrowed + 1 WHERE tool = ?", (tool,))
        cur.execute(
            "INSERT INTO borrows(id, tool, user, borrowed_at, is_overage) VALUES (?, ?, ?, ?, ?)",
            (borrow_id, tool, user, borrowed_at_iso, 1 if is_overage else 0),
        )
        
        # Record overage charge if this is an overage borrow
        if is_overage and overage_price > 0:
            import uuid
            charge_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO overage_charges(id, tool, borrow_id, user, charged_at, amount) VALUES (?, ?, ?, ?, ?, ?)",
                (charge_id, tool, borrow_id, user, borrowed_at_iso, overage_price)
            )
        
        conn.commit()
        return True, is_overage


def return_license(borrow_id: str) -> Optional[str]:
    with get_connection(False) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tool FROM borrows WHERE id = ?", (borrow_id,))
        row = cur.fetchone()
        if row is None:
            return None
        tool = row["tool"]
        cur.execute("DELETE FROM borrows WHERE id = ?", (borrow_id,))
        cur.execute("UPDATE licenses SET borrowed = borrowed - 1 WHERE tool = ?", (tool,))
        conn.commit()
        return tool


def get_status(tool: str) -> Optional[dict]:
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license FROM licenses WHERE tool = ?", (tool,))
        row = cur.fetchone()
        if row is None:
            return None
        total = int(row["total"])
        borrowed = int(row["borrowed"])
        commit = int(row["commit_qty"] or 0)
        max_overage = int(row["max_overage"] or 0)
        commit_price = float(row["commit_price"] or 0.0)
        overage_price = float(row["overage_price_per_license"] or 0.0)
        available = max(total - borrowed, 0)
        overage = max(borrowed - commit, 0)
        
        # Calculate accumulated overage costs from overage_charges table (persists even after return)
        cur.execute("SELECT COUNT(*) as cnt FROM overage_charges WHERE tool = ?", (tool,))
        overage_charges_count = int(cur.fetchone()["cnt"] or 0)
        current_overage_cost = overage_charges_count * overage_price
        total_cost = commit_price + current_overage_cost
        
        return {
            "tool": tool,
            "total": total,
            "borrowed": borrowed,
            "available": available,
            "commit": commit,
            "max_overage": max_overage,
            "overage": overage,
            "overage_borrows": overage_charges_count,
            "in_commit": borrowed <= commit,
            "commit_price": commit_price,
            "overage_price_per_license": overage_price,
            "current_overage_cost": current_overage_cost,
            "total_cost": total_cost
        }


_pwd_context: Optional[CryptContext] = None


def get_password_context() -> CryptContext:
    global _pwd_context
    if _pwd_context is None:
        _pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    return _pwd_context


def verify_user_credentials(username: str, password: str) -> bool:
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row is None:
            return False
        return get_password_context().verify(password, row["password_hash"])


def update_budget_config(tool: str, total: int, commit: int, max_overage: int, commit_price: float, overage_price_per_license: float) -> bool:
    """Update total, commit, max_overage, and prices for a tool"""
    with get_connection(False) as conn:
        cur = conn.cursor()
        # Ensure total is at least as much as currently borrowed
        cur.execute("SELECT borrowed FROM licenses WHERE tool = ?", (tool,))
        row = cur.fetchone()
        if row and int(row["borrowed"]) > total:
            return False  # Can't reduce total below current borrows
        cur.execute(
            "UPDATE licenses SET total = ?, commit_qty = ?, max_overage = ?, commit_price = ?, overage_price_per_license = ? WHERE tool = ?",
            (total, commit, max_overage, commit_price, overage_price_per_license, tool)
        )
        conn.commit()
        return cur.rowcount > 0


def get_all_tools() -> List[dict]:
    """Get all tools with budget info"""
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tool, total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license FROM licenses ORDER BY tool ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "tool": r["tool"],
                "total": int(r["total"]),
                "borrowed": int(r["borrowed"]),
                "commit": int(r["commit_qty"] or 0),
                "max_overage": int(r["max_overage"] or 0),
                "commit_price": float(r["commit_price"] or 0.0),
                "overage_price_per_license": float(r["overage_price_per_license"] or 0.0),
            })
        return result


def get_overage_charges(tool: Optional[str] = None) -> List[dict]:
    """Get all overage charges, optionally filtered by tool"""
    with get_connection(True) as conn:
        cur = conn.cursor()
        if tool:
            cur.execute(
                "SELECT id, tool, borrow_id, user, charged_at, amount FROM overage_charges WHERE tool = ? ORDER BY charged_at DESC",
                (tool,)
            )
        else:
            cur.execute("SELECT id, tool, borrow_id, user, charged_at, amount FROM overage_charges ORDER BY charged_at DESC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "tool": r["tool"],
                "borrow_id": r["borrow_id"],
                "user": r["user"],
                "charged_at": r["charged_at"],
                "amount": float(r["amount"])
            })
        return result


# ============================================================================
# MULTI-TENANT FUNCTIONS
# ============================================================================

def seed_multitenant_demo_data() -> None:
    """Seed database with demo tenants, vendors, and licenses for demo"""
    from datetime import datetime
    import uuid
    
    with get_connection(False) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        # Create 3 tenant companies
        tenants = [
            {"id": "acme", "name": "Acme Corporation", "domain": "acme-corp.com", "crm_id": "CRM-ACME-001"},
            {"id": "globex", "name": "Globex Industries", "domain": "globex.com", "crm_id": "CRM-GLOBEX-002"},
            {"id": "initech", "name": "Initech Systems", "domain": "initech.com", "crm_id": "CRM-INITECH-003"},
        ]
        
        for tenant in tenants:
            cur.execute(
                "INSERT OR IGNORE INTO tenants(tenant_id, company_name, domain, crm_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
                (tenant["id"], tenant["name"], tenant["domain"], tenant["crm_id"], now)
            )
        
        # Create TechVendor as vendor
        cur.execute(
            "INSERT OR IGNORE INTO vendors(vendor_id, vendor_name, contact_email, created_at) VALUES (?, ?, ?, ?)",
            ("techvendor", "TechVendor Software Inc", "sales@techvendor.com", now)
        )
        
        # License packages and licenses for each tenant
        products = [
            {"id": "ecu-dev-suite", "name": "ECU Development Suite", "total": 20, "commit": 5, "overage": 15, "commit_price": 5000.0, "overage_price": 500.0},
            {"id": "greenhills-multi", "name": "GreenHills Multi IDE", "total": 15, "commit": 10, "overage": 5, "commit_price": 8000.0, "overage_price": 800.0},
        ]
        
        for tenant in tenants:
            for product in products:
                # Create package
                package_id = f"pkg-{tenant['id']}-{product['id']}-{uuid.uuid4().hex[:8]}"
                cur.execute(
                    "INSERT OR IGNORE INTO license_packages(package_id, tenant_id, vendor_id, product_id, product_name, crm_opportunity_id, status, provisioned_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)",
                    (package_id, tenant["id"], "techvendor", product["id"], product["name"], f"CRM-OPP-{tenant['crm_id']}-{product['id']}", now)
                )
                
                # Create license for tenant
                license_id = f"lic-{tenant['id']}-{product['id']}-{uuid.uuid4().hex[:8]}"
                cur.execute(
                    "INSERT OR IGNORE INTO licenses(id, tenant_id, package_id, tool, total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
                    (license_id, tenant["id"], package_id, product["name"], product["total"], product["commit"], product["overage"], product["commit_price"], product["overage_price"])
                )
        
        conn.commit()


def get_all_tenants() -> List[dict]:
    """Get all tenants"""
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tenant_id, company_name, domain, crm_id, status, created_at FROM tenants ORDER BY company_name ASC")
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_vendor_customers(vendor_id: str) -> List[dict]:
    """Get all customers (tenants) for a vendor"""
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT 
                t.tenant_id, 
                t.company_name, 
                t.domain, 
                t.crm_id,
                COUNT(DISTINCT lp.package_id) as package_count
            FROM tenants t
            JOIN license_packages lp ON t.tenant_id = lp.tenant_id
            WHERE lp.vendor_id = ? AND lp.status = 'active'
            GROUP BY t.tenant_id
            ORDER BY t.company_name ASC
            """,
            (vendor_id,)
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                "tenant_id": row["tenant_id"],
                "company_name": row["company_name"],
                "domain": row["domain"],
                "crm_id": row["crm_id"],
                "active_licenses": row["package_count"]
            })
        return result


def get_tenant_licenses(tenant_id: str) -> List[dict]:
    """Get all licenses for a tenant"""
    with get_connection(True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                l.id, 
                l.tool, 
                l.total, 
                l.borrowed, 
                l.commit_qty, 
                l.max_overage,
                l.commit_price,
                l.overage_price_per_license,
                lp.vendor_id,
                v.vendor_name
            FROM licenses l
            LEFT JOIN license_packages lp ON l.package_id = lp.package_id
            LEFT JOIN vendors v ON lp.vendor_id = v.vendor_id
            WHERE l.tenant_id = ?
            ORDER BY l.tool ASC
            """,
            (tenant_id,)
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "tool": row["tool"],
                "total": int(row["total"]),
                "borrowed": int(row["borrowed"]),
                "commit": int(row["commit_qty"] or 0),
                "max_overage": int(row["max_overage"] or 0),
                "available": max(int(row["total"]) - int(row["borrowed"]), 0),
                "commit_price": float(row["commit_price"] or 0.0),
                "overage_price_per_license": float(row["overage_price_per_license"] or 0.0),
                "vendor_id": row["vendor_id"],
                "vendor_name": row["vendor_name"]
            })
        return result


def provision_license_to_tenant(vendor_id: str, tenant_id: str, product_config: dict) -> str:
    """Provision a new license from vendor to tenant. Returns package_id"""
    from datetime import datetime
    import uuid
    
    with get_connection(False) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        # Create package
        package_id = f"pkg-{tenant_id}-{product_config['product_id']}-{uuid.uuid4().hex[:8]}"
        cur.execute(
            "INSERT INTO license_packages(package_id, tenant_id, vendor_id, product_id, product_name, crm_opportunity_id, status, provisioned_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)",
            (package_id, tenant_id, vendor_id, product_config["product_id"], product_config["product_name"], product_config.get("crm_opportunity_id"), now)
        )
        
        # Create license
        license_id = f"lic-{tenant_id}-{product_config['product_id']}-{uuid.uuid4().hex[:8]}"
        cur.execute(
            "INSERT INTO licenses(id, tenant_id, package_id, tool, total, borrowed, commit_qty, max_overage, commit_price, overage_price_per_license) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (license_id, tenant_id, package_id, product_config["product_name"], product_config["total"], product_config["commit_qty"], product_config["max_overage"], product_config.get("commit_price", 1000.0), product_config.get("overage_price_per_license", 100.0))
        )
        
        conn.commit()
        return package_id




# ============================================================================
# API Key Management
# ============================================================================

def generate_api_key(tenant_id: Optional[str] = None, name: str = "Default Key", environment: str = "live") -> tuple[str, str]:
    """
    Generate a new API key for a tenant.
    
    Args:
        tenant_id: Tenant ID (e.g., "acme") or None for single-tenant mode
        name: Human-readable name for the key
        environment: "live", "test", or "dev"
    
    Returns:
        tuple: (api_key, key_id) - The plaintext key (show once!) and the database ID
    """
    # Generate cryptographically random key
    random_part = secrets.token_urlsafe(32)  # 32 bytes = 43 chars in base64
    
    # Format: {tenant}_{env}_pk_{random} or just pk_{random} for single-tenant
    if tenant_id:
        api_key = f"{tenant_id}_{environment}_pk_{random_part}"
    else:
        api_key = f"{environment}_pk_{random_part}"
    
    # Hash the key for storage (never store plaintext!)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Create key ID
    key_id = f"key_{secrets.token_hex(8)}"
    
    # Store in database
    with get_connection(False) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        cur.execute(
            """
            INSERT INTO api_keys(id, tenant_id, key_hash, name, environment, created_at, status, scopes)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 'borrow,return,status')
            """,
            (key_id, tenant_id, key_hash, name, environment, now)
        )
        conn.commit()
    
    return (api_key, key_id)


def validate_api_key(api_key: str) -> Optional[dict]:
    """
    Validate an API key and return tenant information.
    
    Args:
        api_key: The API key to validate
    
    Returns:
        dict with tenant info if valid, None if invalid
        {
            "key_id": "key_abc123",
            "tenant_id": "acme" or None,
            "environment": "live",
            "scopes": ["borrow", "return", "status"]
        }
    """
    if not api_key:
        return None
    
    # Hash the provided key
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    with get_connection(False) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        # Find key by hash
        cur.execute(
            """
            SELECT id, tenant_id, environment, status, scopes, expires_at
            FROM api_keys
            WHERE key_hash = ? AND status = 'active'
            """,
            (key_hash,)
        )
        row = cur.fetchone()
        
        if not row:
            return None
        
        # Check expiration
        if row["expires_at"] and row["expires_at"] < now:
            return None
        
        # Update last_used_at
        cur.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (now, row["id"])
        )
        conn.commit()
        
        return {
            "key_id": row["id"],
            "tenant_id": row["tenant_id"],
            "environment": row["environment"],
            "scopes": row["scopes"].split(",") if row["scopes"] else []
        }


def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key by ID"""
    with get_connection(False) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE api_keys SET status = 'revoked' WHERE id = ?",
            (key_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def list_api_keys(tenant_id: Optional[str] = None) -> List[dict]:
    """List all API keys for a tenant (or all keys if tenant_id is None)"""
    with get_connection(False) as conn:
        cur = conn.cursor()
        
        if tenant_id:
            cur.execute(
                """
                SELECT id, tenant_id, name, environment, created_at, last_used_at, status
                FROM api_keys
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                """,
                (tenant_id,)
            )
        else:
            cur.execute(
                """
                SELECT id, tenant_id, name, environment, created_at, last_used_at, status
                FROM api_keys
                ORDER BY created_at DESC
                """
            )
        
        rows = cur.fetchall()
        return [dict(row) for row in rows]


# ============================================================================
# Vendor-Controlled Budget Configuration
# ============================================================================

def _ensure_vendor_customer_columns(conn) -> None:
    """Ensure vendor_* and customer_* columns exist on licenses table (for existing DBs)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(licenses)")
    cols = {row[1] for row in cur.fetchall()}
    to_add = []
    if "vendor_total" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN vendor_total INTEGER")
    if "vendor_commit_qty" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN vendor_commit_qty INTEGER")
    if "vendor_max_overage" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN vendor_max_overage INTEGER")
    if "customer_total" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN customer_total INTEGER")
    if "customer_commit_qty" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN customer_commit_qty INTEGER")
    if "customer_max_overage" not in cols:
        to_add.append("ALTER TABLE licenses ADD COLUMN customer_max_overage INTEGER")
    for stmt in to_add:
        cur.execute(stmt)
    if to_add:
        conn.commit()


def set_vendor_budget(tool: str, total: int, commit_qty: int, max_overage: int) -> bool:
    """
    Vendor sets the maximum budget for a tool.
    These are the limits that cannot be exceeded by the customer.
    
    Args:
        tool: Tool name
        total: Vendor-provisioned total licenses
        commit_qty: Vendor-provisioned commit quantity
        max_overage: Vendor-provisioned max overage
    
    Returns:
        True if successful
    """
    with get_connection(False) as conn:
        cur = conn.cursor()
        # Ensure columns exist for older databases
        _ensure_vendor_customer_columns(conn)
        try:
            # Update vendor limits + active
            cur.execute(
                """
                UPDATE licenses
                SET vendor_total = ?,
                    vendor_commit_qty = ?,
                    vendor_max_overage = ?,
                    total = ?,
                    commit_qty = ?,
                    max_overage = ?
                WHERE tool = ?
                """,
                (total, commit_qty, max_overage, total, commit_qty, max_overage, tool)
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            # Fallback for legacy schema: update only active fields
            cur.execute(
                """
                UPDATE licenses
                SET total = ?,
                    commit_qty = ?,
                    max_overage = ?
                WHERE tool = ?
                """,
                (total, commit_qty, max_overage, tool)
            )
            conn.commit()
            return cur.rowcount > 0


def set_customer_budget_restrictions(tool: str, total: int = None, commit_qty: int = None, max_overage: int = None) -> tuple[bool, str]:
    """
    Customer can ONLY restrict (lower) their budget, not exceed vendor limits.
    
    Args:
        tool: Tool name
        total: Customer-restricted total (must be <= vendor_total)
        commit_qty: Customer-restricted commit (must be <= vendor_commit_qty)
        max_overage: Customer-restricted overage (must be <= vendor_max_overage)
    
    Returns:
        (success, error_message)
    """
    with get_connection(False) as conn:
        cur = conn.cursor()
        # Ensure columns for older databases
        _ensure_vendor_customer_columns(conn)
        
        # Get current vendor limits
        cur.execute(
            "SELECT vendor_total, vendor_commit_qty, vendor_max_overage, borrowed FROM licenses WHERE tool = ?",
            (tool,)
        )
        row = cur.fetchone()
        
        if not row:
            return False, "Tool not found"
        
        vendor_total = row["vendor_total"] or row["borrowed"] + 100  # Default if not set
        vendor_commit = row["vendor_commit_qty"] or vendor_total
        vendor_overage = row["vendor_max_overage"] or 0
        borrowed = row["borrowed"]
        
        # Validate customer restrictions
        if total is not None:
            if total > vendor_total:
                return False, f"Cannot exceed vendor limit of {vendor_total} total licenses"
            if total < borrowed:
                return False, f"Cannot reduce below currently borrowed ({borrowed})"
        else:
            total = vendor_total
        
        if commit_qty is not None:
            if commit_qty > vendor_commit:
                return False, f"Cannot exceed vendor limit of {vendor_commit} commit licenses"
            if commit_qty > total:
                return False, f"Commit quantity cannot exceed total ({total})"
        else:
            commit_qty = vendor_commit
        
        if max_overage is not None:
            if max_overage > vendor_overage:
                return False, f"Cannot exceed vendor limit of {vendor_overage} overage licenses"
            if commit_qty + max_overage > total:
                return False, f"Commit + overage cannot exceed total ({total})"
        else:
            max_overage = vendor_overage
        
        # Apply customer restrictions
        try:
            cur.execute(
                """
                UPDATE licenses
                SET customer_total = ?,
                    customer_commit_qty = ?,
                    customer_max_overage = ?,
                    total = ?,
                    commit_qty = ?,
                    max_overage = ?
                WHERE tool = ?
                """,
                (total, commit_qty, max_overage, total, commit_qty, max_overage, tool)
            )
        except Exception:
            # Legacy schema: update only active fields
            cur.execute(
                """
                UPDATE licenses
                SET total = ?,
                    commit_qty = ?,
                    max_overage = ?
                WHERE tool = ?
                """,
                (total, commit_qty, max_overage, tool)
            )
        
        conn.commit()
        return True, "Success"


def get_budget_config(tool: str) -> Optional[dict]:
    """
    Get both vendor and customer budget configuration for a tool.
    
    Returns:
        {
            "tool": str,
            "vendor_total": int,
            "vendor_commit_qty": int,
            "vendor_max_overage": int,
            "customer_total": int or None,
            "customer_commit_qty": int or None,
            "customer_max_overage": int or None,
            "active_total": int,
            "active_commit_qty": int,
            "active_max_overage": int,
            "borrowed": int
        }
    """
    with get_connection(False) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tool, total, commit_qty, max_overage, borrowed,
                   vendor_total, vendor_commit_qty, vendor_max_overage,
                   customer_total, customer_commit_qty, customer_max_overage,
                   commit_price, overage_price_per_license
            FROM licenses
            WHERE tool = ?
            """,
            (tool,)
        )
        row = cur.fetchone()
        
        if not row:
            return None
        
        return {
            "tool": row["tool"],
            "vendor_total": row["vendor_total"],
            "vendor_commit_qty": row["vendor_commit_qty"],
            "vendor_max_overage": row["vendor_max_overage"],
            "customer_total": row["customer_total"],
            "customer_commit_qty": row["customer_commit_qty"],
            "customer_max_overage": row["customer_max_overage"],
            "active_total": row["total"],
            "active_commit_qty": row["commit_qty"],
            "active_max_overage": row["max_overage"],
            "borrowed": row["borrowed"],
            "commit_price": row["commit_price"],
            "overage_price_per_license": row["overage_price_per_license"]
        }
