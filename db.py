"""SQLite storage for Parts Buyer (SPEC section 6).

parts_buyer.db is rebuilt from the four CSVs in data/ by reset_demo().
Run `python db.py` to reset and print the row count of every table.
"""

import csv
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DB_PATH = ROOT / "parts_buyer.db"
DATA_DIR = ROOT / "data"


def today():
    """Demo date. Read each call so a changed .env or test override takes effect."""
    return os.getenv("TODAY", "2026-11-20")


SCHEMA = """
CREATE TABLE parts (
    part_id            TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    on_hand            INTEGER NOT NULL,
    reserved           INTEGER NOT NULL,
    on_order           INTEGER NOT NULL,
    reorder_point      INTEGER NOT NULL,
    reorder_qty        INTEGER NOT NULL,
    approved_suppliers TEXT NOT NULL          -- split on ";"
);
CREATE TABLE suppliers (
    supplier_id    TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    country        TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL,
    shipping_flat  REAL NOT NULL
);
CREATE TABLE offers (
    offer_id     TEXT PRIMARY KEY,
    part_id      TEXT NOT NULL REFERENCES parts(part_id),
    supplier_id  TEXT NOT NULL REFERENCES suppliers(supplier_id),
    unit_price   REAL NOT NULL,
    listed_stock INTEGER NOT NULL,
    live_stock   INTEGER NOT NULL
);
CREATE TABLE jobs (
    job_id   TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    part_id  TEXT NOT NULL REFERENCES parts(part_id),
    qty      INTEGER NOT NULL,
    due_date TEXT NOT NULL
);
CREATE TABLE purchase_orders (
    po_id           TEXT PRIMARY KEY,         -- PO-0001
    idempotency_key TEXT NOT NULL UNIQUE,     -- part_id-TODAY (R7)
    part_id         TEXT NOT NULL,
    supplier_id     TEXT NOT NULL,
    offer_id        TEXT NOT NULL,
    qty             INTEGER NOT NULL,
    unit_price      REAL NOT NULL,
    shipping        REAL NOT NULL,
    total           REAL NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('placed', 'pending_approval', 'rejected')),
    approved_by     TEXT,
    created_at      TEXT NOT NULL
);
CREATE TABLE audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL,
    ts        TEXT NOT NULL,
    part_id   TEXT,
    step      TEXT NOT NULL,
    message   TEXT NOT NULL,
    data_json TEXT
);
"""

INT_COLUMNS = {
    "parts": {"on_hand", "reserved", "on_order", "reorder_point", "reorder_qty"},
    "suppliers": {"lead_time_days"},
    "offers": {"listed_stock", "live_stock"},
    "jobs": {"qty"},
}
REAL_COLUMNS = {"suppliers": {"shipping_flat"}, "offers": {"unit_price"}}


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _load_csv(conn, table):
    with open(DATA_DIR / f"{table}.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for col in INT_COLUMNS.get(table, ()):
            row[col] = int(row[col])
        for col in REAL_COLUMNS.get(table, ()):
            row[col] = float(row[col])
    cols = list(rows[0].keys())
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [tuple(r[c] for c in cols) for r in rows],
    )


def reset_demo():
    """Delete the database and rebuild it from data/*.csv."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table in ("parts", "suppliers", "offers", "jobs"):
            _load_csv(conn, table)
    conn.close()


def row_counts():
    with connect() as conn:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("parts", "suppliers", "offers", "jobs", "purchase_orders", "audit_log")
        }


if __name__ == "__main__":
    reset_demo()
    for table, n in row_counts().items():
        print(f"{table}: {n}")
