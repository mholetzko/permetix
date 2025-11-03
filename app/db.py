import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, List
from passlib.context import CryptContext


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


def initialize_database(tools_config: Optional[List[dict]] = None) -> None:
    """
    Initialize database with optional seed data.
    
    Args:
        tools_config: List of dicts with keys: tool, total, commit_qty, max_overage, commit_price (optional), overage_price_per_license (optional)
    """
    with get_connection(readonly=False) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                tool TEXT PRIMARY KEY,
                total INTEGER NOT NULL,
                borrowed INTEGER NOT NULL DEFAULT 0,
                commit_qty INTEGER DEFAULT 0,
                max_overage INTEGER DEFAULT 0,
                commit_price REAL DEFAULT 0.0,
                overage_price_per_license REAL DEFAULT 0.0
            )
            """
        )
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


