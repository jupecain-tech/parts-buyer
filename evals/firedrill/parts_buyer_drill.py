"""Firedrill driver for Parts Buyer (jsonl-process.v1).

Firedrill writes one JSON object per line on stdin:
    {"id": "step-1.1", "session": "drill-7f3a", "kind": "message", "input": "..."}
We answer one JSON object per line on stdout with the same id:
    {"id": "step-1.1", "output": "..."}
Logs go to stderr. "READY" is printed once before the first step.

What the simulated shop manager can ask (plain words, any order):
    "run this morning's check"          reset on the first message of a drill, then run
    "run again" / "rerun"               run again the same day (must order nothing new)
    "crash" / "restart"                 crash after 2 orders, then restart the run
    "limit 3000" / "$3,000 limit"       run with that spending limit
    "approve"                           approve what is waiting
Every reply is a plain-English report built from the database and audit trail,
so the judge sees exactly what happened, including a duplicate-order check.

Uses rules.run_rules_only, or agent.run_agent when PB_MODE=agent and agent.py exists.
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import audit  # noqa: E402
import db  # noqa: E402
import rules  # noqa: E402

sessions_seen = set()


def log(*args):
    print(*args, file=sys.stderr, flush=True)


def money(v):
    v = float(v)
    return f"${v:,.0f}" if v.is_integer() else f"${v:,.2f}"


def run_once(limit):
    if os.getenv("PB_MODE") == "agent":
        import agent  # Shuhang's file; only when asked for
        return agent.run_agent(spend_limit=limit)
    return rules.run_rules_only(spend_limit=limit)


def report(run_id, header):
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    orders = conn.execute("SELECT * FROM purchase_orders ORDER BY po_id").fetchall()
    names = {r["supplier_id"]: r["name"].replace(" (mock)", "")
             for r in conn.execute("SELECT supplier_id, name FROM suppliers")}
    parts = {r["part_id"]: r["name"] for r in conn.execute("SELECT part_id, name FROM parts")}
    keys = [o["idempotency_key"] for o in orders]
    conn.close()

    lines = [header, ""]
    if run_id:
        lines.append("What the agent did this run, part by part:")
        current = None
        for e in audit.read_by_run(run_id):
            if e["part_id"] != current:
                current = e["part_id"]
                lines.append(f"- {current} {parts.get(current, '')}:")
            if e["step"] in ("shopping",):
                continue
            lines.append(f"    [{e['step']}] {e['message']}")
        lines.append("")
    lines.append("All purchase orders for today:")
    if not orders:
        lines.append("    none")
    for o in orders:
        status = {"placed": "PLACED", "pending_approval": "WAITING FOR OWNER APPROVAL",
                  "rejected": "REJECTED BY OWNER"}.get(o["status"], o["status"])
        lines.append(f"    {o['po_id']}: {o['part_id']} {parts.get(o['part_id'], '')}, {o['qty']} from "
                     f"{names.get(o['supplier_id'], o['supplier_id'])}, total {money(o['total'])}, {status}"
                     + (f" (approved by {o['approved_by']})" if o["approved_by"] else ""))
    dupes = len(keys) - len(set(keys))
    lines.append("")
    lines.append(f"Duplicate check: {len(orders)} orders, {len(set(keys))} distinct part-per-day keys, "
                 f"{dupes} duplicates.")
    return "\n".join(lines)


def handle(text, session):
    t = (text or "").lower()
    if session not in sessions_seen:
        sessions_seen.add(session)
        db.reset_demo()
        log(f"[{session}] fresh demo data")

    m = re.search(r"\$?\s*(\d[\d,]{2,})\s*(?:dollar)?\s*limit|limit\D{0,20}\$?\s*(\d[\d,]{2,})", t)
    limit = float((m.group(1) or m.group(2)).replace(",", "")) if m else None

    if "approve" in t:
        conn = sqlite3.connect(db.DB_PATH)
        waiting = [r[0] for r in conn.execute("SELECT po_id FROM purchase_orders WHERE status='pending_approval'")]
        conn.close()
        for po in waiting:
            rules.approve_order(po)
        return report(None, f"Owner approved {len(waiting)} waiting order(s): {', '.join(waiting) or 'none'}.")

    if "crash" in t or "restart" in t:
        os.environ["CRASH_AFTER_ORDERS"] = "2"
        try:
            run_once(limit)
            crashed = "The run did not crash."
        except RuntimeError as exc:
            crashed = f"The run stopped: {exc} (after 2 orders, on purpose)."
        finally:
            os.environ["CRASH_AFTER_ORDERS"] = "0"
        summary = run_once(limit)
        return report(summary.get("run_id") if isinstance(summary, dict) else None,
                      f"{crashed} Restarted the run with the crash switch off.")

    summary = run_once(limit)
    run_id = summary.get("run_id") if isinstance(summary, dict) else None
    lim = summary.get("spend_limit") if isinstance(summary, dict) else limit
    src = summary.get("spend_limit_source", "") if isinstance(summary, dict) else ""
    where = rules.LIMIT_SOURCE_WORDS.get(src, "the default limit")
    return report(run_id, f"Run finished. Spending limit used: {money(lim or 0)} ({where}).")


def main():
    print("READY", flush=True)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            step = json.loads(raw)
        except ValueError:
            log("bad input line:", raw[:200])
            continue
        sid = step.get("id")
        try:
            out = handle(step.get("input", ""), step.get("session", "default"))
            print(json.dumps({"id": sid, "output": out}), flush=True)
        except Exception as exc:  # never crash the driver; report the error to Firedrill
            log("error:", repr(exc))
            print(json.dumps({"id": sid, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()
