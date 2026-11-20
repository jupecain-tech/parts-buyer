"""Audit log: write and read (SPEC sections 6 and R8).

Steps: checked, gap_found, shopping, rejected_option, chosen, recheck,
order_placed, approval_requested, approved, rejected, skipped,
no_viable_offer, agent_note.
"""

import json
import uuid
from datetime import datetime, timezone

import db


def new_run_id(prefix="run"):
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def log(run_id, part_id, step, message, data=None, conn=None):
    """Write one audit entry. Pass conn to write inside an open transaction."""
    sql = "INSERT INTO audit_log (run_id, ts, part_id, step, message, data_json) VALUES (?, ?, ?, ?, ?, ?)"
    args = (run_id, now_iso(), part_id, step, message, json.dumps(data or {}, default=str))
    if conn is not None:
        conn.execute(sql, args)
        return
    with db.connect() as c:
        c.execute(sql, args)
    c.close()


def _read(where, params):
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT id, run_id, ts, part_id, step, message, data_json FROM audit_log "
            f"WHERE {where} ORDER BY ts, id",
            params,
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data_json"] or "{}")
        out.append(d)
    return out


def read_by_run(run_id):
    return _read("run_id = ?", (run_id,))


def read_by_part(part_id, run_id=None):
    if run_id:
        return _read("part_id = ? AND run_id = ?", (part_id, run_id))
    return _read("part_id = ?", (part_id,))
