"""Parts Buyer rules: inventory math and R1 to R8 (SPEC sections 2 and 7).

All money and compliance decisions live in this file. The agent (tools.py,
agent.py) and the screens (app.py) call these functions; they never repeat
the logic.

    available = on_hand - reserved + on_order

Public API (also listed in CLAUDE.md):
    start_run() -> run_id
    get_inventory_status() -> list of dicts
    get_spend_limit(override=None) -> float
    evaluate_part(part_id, run_id, spend_limit=None) -> dict
    recheck_offer(offer_id, qty, run_id) -> dict
    place_order(part_id, offer_id, qty, run_id, spend_limit=None) -> dict
    approve_order(po_id), reject_order(po_id)
    run_rules_only(spend_limit=None) -> summary dict
"""

import json
import os
import sqlite3
from datetime import date, timedelta

import audit
import db
import suppliers


# ---------------------------------------------------------------- settings --
def get_spend_limit(override=None):
    """The one place the spending limit is read. override wins (sidebar box);
    otherwise Statsig via config_flags, otherwise SPEND_LIMIT in .env."""
    if override is not None:
        return float(override)
    try:
        from config_flags import get_live_limit
        return float(get_live_limit()[0])
    except Exception:
        return float(os.getenv("SPEND_LIMIT", "1000"))


def _crash_after():
    """Read at the start of each run, so the app's Crash test toggle takes effect."""
    try:
        return int(os.getenv("CRASH_AFTER_ORDERS", "0") or 0)
    except ValueError:
        return 0


def start_run():
    return audit.new_run_id()


def idempotency_key(part_id):
    return f"{part_id}-{db.today()}"                                    # R7


def _money(v):
    v = float(v)
    return f"${v:,.0f}" if v.is_integer() else f"${v:,.2f}"


def _supplier_name(name):
    return str(name).replace(" (mock)", "")


# ------------------------------------------------------------------- reads --
def _part(conn, part_id):
    row = conn.execute("SELECT * FROM parts WHERE part_id = ?", (part_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown part {part_id}")
    p = dict(row)
    p["approved"] = [s for s in p["approved_suppliers"].split(";") if s]
    p["available"] = p["on_hand"] - p["reserved"] + p["on_order"]
    return p


def _order_for_key(conn, key):
    row = conn.execute("SELECT * FROM purchase_orders WHERE idempotency_key = ?", (key,)).fetchone()
    return dict(row) if row else None


def _earliest_job(conn, part_id):
    row = conn.execute(
        "SELECT job_id, due_date FROM jobs WHERE part_id = ? ORDER BY due_date, job_id LIMIT 1",
        (part_id,),
    ).fetchone()
    return dict(row) if row else None


def get_inventory_status():
    """Each part with on hand, reserved, on order, available, reorder point,
    status (OK / Short / Ordered / Awaiting approval) and today's order if any."""
    status_for = {"placed": "Ordered", "pending_approval": "Awaiting approval"}
    out = []
    conn = db.connect()
    try:
        for row in conn.execute("SELECT part_id FROM parts ORDER BY part_id").fetchall():
            p = _part(conn, row["part_id"])
            order = _order_for_key(conn, idempotency_key(p["part_id"]))
            if order and order["status"] in status_for:
                status = status_for[order["status"]]
            elif p["available"] < p["reorder_point"]:
                status = "Short"
            else:
                status = "OK"
            out.append(
                {
                    "part_id": p["part_id"],
                    "name": p["name"],
                    "on_hand": p["on_hand"],
                    "reserved": p["reserved"],
                    "on_order": p["on_order"],
                    "available": p["available"],
                    "reorder_point": p["reorder_point"],
                    "status": status,
                    "order_today": (
                        {"po_id": order["po_id"], "status": order["status"], "total": order["total"]}
                        if order else None
                    ),
                }
            )
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------- evaluate --
def _evaluate(part_id, spend_limit=None):
    """R1 to R4 for one part. No side effects. Used by evaluate_part (which logs)
    and by place_order (which re-validates)."""
    conn = db.connect()
    try:
        p = _part(conn, part_id)
        job = _earliest_job(conn, part_id)
        existing = _order_for_key(conn, idempotency_key(part_id))
    finally:
        conn.close()
    limit = get_spend_limit(spend_limit)

    ev = {
        "part_id": part_id,
        "name": p["name"],
        "on_hand": p["on_hand"],
        "reserved": p["reserved"],
        "on_order": p["on_order"],
        "available": p["available"],
        "reorder_point": p["reorder_point"],
        "existing_order": existing,
        "needs_buying": p["available"] < p["reorder_point"],              # R1
        "qty": 0,
        "deadline": None,
        "job": job,
        "spend_limit": limit,
        "eligible_offers": [],
        "rejected": [],
    }
    if not ev["needs_buying"]:
        return ev

    qty = max(p["reorder_qty"], p["reorder_point"] - p["available"])        # R2
    deadline = (date.fromisoformat(job["due_date"]) - timedelta(days=1)) if job else None
    ev["qty"] = qty
    ev["deadline"] = deadline.isoformat() if deadline else None
    run_day = date.fromisoformat(db.today())

    for o in suppliers.search_offers(part_id):
        name = _supplier_name(o["supplier_name"])
        base = {"offer_id": o["offer_id"], "supplier_id": o["supplier_id"], "supplier_name": name}
        if o["supplier_id"] not in p["approved"]:                           # R3
            ev["rejected"].append(
                {**base, "rule": "R3", "reason": f"{name} is not an approved supplier for this part"}
            )
            continue
        arrival = run_day + timedelta(days=o["lead_time_days"])
        if deadline and arrival > deadline:                                 # R4 timing
            ev["rejected"].append(
                {
                    **base,
                    "rule": "R4",
                    "arrival": arrival.isoformat(),
                    "reason": (
                        f"{name} would arrive {arrival:%b %d} ({o['lead_time_days']} day lead time), "
                        f"too late: job {job['job_id']} needs it by {deadline:%b %d}"
                    ),
                }
            )
            continue
        if o["listed_stock"] < qty:
            ev["rejected"].append(
                {**base, "rule": "stock",
                 "reason": f"{name} lists only {o['listed_stock']} in stock, need {qty}"}
            )
            continue
        landed = o["unit_price"] * qty + o["shipping_flat"]                 # R4 landed cost
        ev["eligible_offers"].append(
            {
                **base,
                "country": o["country"],
                "unit_price": o["unit_price"],
                "shipping": o["shipping_flat"],
                "listed_stock": o["listed_stock"],
                "lead_time_days": o["lead_time_days"],
                "arrival": arrival.isoformat(),
                "qty": qty,
                "landed": landed,
                "needs_owner_approval": landed > limit,                     # R6 preview
            }
        )
    ev["eligible_offers"].sort(key=lambda x: (x["landed"], x["offer_id"]))
    return ev


SKIP_MESSAGES = {
    "placed": "Already ordered today ({po_id}); not ordering again.",
    "pending_approval": "Awaiting the owner's approval ({po_id}); not ordering again.",
    "rejected": "The owner rejected today's order ({po_id}); not ordering again today.",
}


def evaluate_part(part_id, run_id, spend_limit=None):
    """R1 to R4 for one part, with audit rows.

    Logs skipped (order exists, R7), checked (no need, R1), or gap_found plus
    shopping and one rejected_option per ruled-out offer; no_viable_offer if
    nothing is eligible. Returns qty, deadline, eligible_offers ranked by
    landed cost (offer_id, supplier_id, landed, ...), rejected (offer_id,
    supplier_id, reason), plus the inventory numbers.
    """
    ev = _evaluate(part_id, spend_limit)

    if ev["existing_order"]:                                                  # R7
        o = ev["existing_order"]
        audit.log(run_id, part_id, "skipped", SKIP_MESSAGES[o["status"]].format(po_id=o["po_id"]),
                  {"po_id": o["po_id"], "status": o["status"], "rule": "R7",
                   "idempotency_key": idempotency_key(part_id)})
        ev["eligible_offers"] = []
        ev["action"] = "skip: order exists"
        return ev

    if not ev["needs_buying"]:                                                # R1
        audit.log(run_id, part_id, "checked",
                  f"OK: available {ev['available']}, reorder point {ev['reorder_point']}.",
                  {"available": ev["available"], "on_hand": ev["on_hand"], "reserved": ev["reserved"],
                   "on_order": ev["on_order"], "reorder_point": ev["reorder_point"], "rule": "R1"})
        ev["action"] = "none: stock is OK"
        return ev

    trigger = f"Available {ev['available']} is below the reorder point of {ev['reorder_point']}"
    if ev["job"]:
        trigger += (f"; job {ev['job']['job_id']} is due {ev['job']['due_date']}, "
                    f"so it must arrive by {ev['deadline']}")
    audit.log(run_id, part_id, "gap_found", f"{trigger}. Buying {ev['qty']}.",
              {"available": ev["available"], "on_hand": ev["on_hand"], "reserved": ev["reserved"],
               "on_order": ev["on_order"], "reorder_point": ev["reorder_point"], "qty": ev["qty"],
               "deadline": ev["deadline"], "job": ev["job"], "rule": "R1, R2"})
    n_offers = len(ev["eligible_offers"]) + len(ev["rejected"])
    audit.log(run_id, part_id, "shopping",
              f"Found {n_offers} offers; {len(ev['eligible_offers'])} meet the rules.",
              {"eligible_offers": ev["eligible_offers"], "rejected": ev["rejected"]})
    for r in ev["rejected"]:
        audit.log(run_id, part_id, "rejected_option", r["reason"], r)
    if not ev["eligible_offers"]:
        audit.log(run_id, part_id, "no_viable_offer",
                  "No offer meets the rules. Nothing ordered; the owner should look at this part.",
                  {"rejected": ev["rejected"], "qty": ev["qty"], "deadline": ev["deadline"]})
        ev["action"] = "none: no eligible offer"
    else:
        ev["action"] = "recheck the best eligible offer, then place_order"
    return ev


# ----------------------------------------------------------------- recheck --
def recheck_offer(offer_id, qty, run_id):
    """R5: live stock and price right before ordering. Logs a recheck row,
    and a rejected_option row if it fails."""
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT o.offer_id, o.part_id, o.supplier_id, o.unit_price, o.listed_stock, s.name "
            "FROM offers o JOIN suppliers s ON s.supplier_id = o.supplier_id WHERE o.offer_id = ?",
            (offer_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"offer_id": offer_id, "supplier_id": None, "live_stock": None, "live_price": None,
                "passed": False, "reason": f"offer {offer_id} not found"}
    live = suppliers.recheck_offer(offer_id)
    name = _supplier_name(row["name"])
    reasons = []
    if live["live_stock"] < qty:
        reasons.append(f"live stock {live['live_stock']}, need {qty}")
    if float(live["unit_price"]) != float(row["unit_price"]):
        reasons.append(f"price changed from {_money(row['unit_price'])} to {_money(live['unit_price'])}")
    result = {
        "offer_id": offer_id,
        "supplier_id": row["supplier_id"],
        "live_stock": live["live_stock"],
        "live_price": live["unit_price"],
        "passed": not reasons,
        "qty": qty,
        "reason": "; ".join(reasons) or "stock and price confirmed",
    }
    audit.log(
        run_id, row["part_id"], "recheck",
        f"Rechecked {name}: catalog said {row['listed_stock']} in stock at {_money(row['unit_price'])}, "
        f"live says {live['live_stock']} at {_money(live['unit_price'])}.",
        {**result, "listed_stock": row["listed_stock"], "listed_price": row["unit_price"], "rule": "R5"},
    )
    if reasons:
        audit.log(run_id, row["part_id"], "rejected_option",
                  f"{name} failed the recheck ({result['reason']}).",
                  {"offer_id": offer_id, "supplier_id": row["supplier_id"], "supplier_name": name,
                   "rule": "R5", "reason": result["reason"]})
    return result


# ------------------------------------------------------------------ orders --
def _passing_recheck_in_run(run_id, offer_id, qty):
    for e in audit.read_by_run(run_id):
        d = e["data"]
        if e["step"] == "recheck" and d.get("offer_id") == offer_id and d.get("passed") and d.get("qty", 0) >= qty:
            return True
    return False


def _recheck_failed_in_run(run_id, offer_id):
    return any(
        e["step"] == "recheck" and e["data"].get("offer_id") == offer_id and not e["data"].get("passed")
        for e in audit.read_by_run(run_id)
    )


def _next_po_id(conn):
    n = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    return f"PO-{n + 1:04d}"


def _refuse(run_id, part_id, reason, data):
    audit.log(run_id, part_id, "refused", f"Order refused: {reason}.", {**data, "reason": reason})
    return {"status": "refused", "po_id": None, "reason": reason}


def place_order(part_id, offer_id, qty, run_id, spend_limit=None):
    """R3 to R7 enforced in code before anything is written.

    Returns {"status": "placed" | "pending_approval" | "refused" | "exists",
             "po_id", "reason", ...}.
    Refuses unless the offer is eligible for this part now (R3, R4, stock),
    qty is the quantity the rules call for (R2), and a passing recheck of this
    same offer exists in this run's audit log (R5). Logs chosen, then
    order_placed or approval_requested.
    """
    data = {"offer_id": offer_id, "qty": qty}
    ev = _evaluate(part_id, spend_limit)
    limit = ev["spend_limit"]
    key = idempotency_key(part_id)

    if ev["existing_order"]:                                                  # R7 check 1
        o = ev["existing_order"]
        return {"status": "exists", "po_id": o["po_id"],
                "reason": SKIP_MESSAGES[o["status"]].format(po_id=o["po_id"])}
    if not ev["needs_buying"]:
        return _refuse(run_id, part_id, "this part does not need buying", data)
    offer = next((o for o in ev["eligible_offers"] if o["offer_id"] == offer_id), None)
    if offer is None:
        why = next((r["reason"] for r in ev["rejected"] if r["offer_id"] == offer_id),
                   f"offer {offer_id} is not an offer for {part_id}")
        return _refuse(run_id, part_id, f"offer not eligible: {why}", data)
    data["supplier_id"] = offer["supplier_id"]
    if qty != ev["qty"]:
        return _refuse(run_id, part_id, f"quantity must be {ev['qty']} (asked for {qty})", data)
    if not _passing_recheck_in_run(run_id, offer_id, qty):                    # R5
        return _refuse(run_id, part_id, f"no passing recheck of {offer['supplier_name']} in this run", data)

    live = suppliers.recheck_offer(offer_id)
    unit_price = float(live["unit_price"])
    shipping = float(offer["shipping"])
    total = unit_price * qty + shipping
    status = "placed" if total <= limit else "pending_approval"              # R6
    cheaper = [o for o in ev["eligible_offers"] if o["landed"] < offer["landed"]]
    pricier = [o for o in ev["eligible_offers"] if o["landed"] >= offer["landed"] and o["offer_id"] != offer_id]
    why = "".join(
        f" {o['supplier_name']} looked cheaper at {_money(o['landed'])} but failed the live recheck."
        if _recheck_failed_in_run(run_id, o["offer_id"])
        else f" {o['supplier_name']} looked cheaper at {_money(o['landed'])} but was passed over."
        for o in cheaper
    )
    if pricier:
        why += f" Next best: {pricier[0]['supplier_name']} at {_money(pricier[0]['landed'])}."

    conn = db.connect()
    try:
        po_id = _next_po_id(conn)
        row_data = {"po_id": po_id, "idempotency_key": key, "supplier_id": offer["supplier_id"],
                    "offer_id": offer_id, "qty": qty, "unit_price": unit_price, "shipping": shipping,
                    "total": total, "spend_limit": limit, "arrival": offer["arrival"]}
        try:
            conn.execute(
                "INSERT INTO purchase_orders (po_id, idempotency_key, part_id, supplier_id, offer_id, "
                "qty, unit_price, shipping, total, status, approved_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (po_id, key, part_id, offer["supplier_id"], offer_id, qty, unit_price, shipping,
                 total, status, None, audit.now_iso()),
            )
        except sqlite3.IntegrityError:                                       # R7 check 2
            conn.rollback()
            o = _order_for_key(conn, key)
            return {"status": "exists", "po_id": o["po_id"],
                    "reason": SKIP_MESSAGES[o["status"]].format(po_id=o["po_id"])}

        audit.log(run_id, part_id, "chosen",
                  f"Chose {offer['supplier_name']}: {qty} x {_money(unit_price)} + "
                  f"{_money(shipping)} shipping = {_money(total)}, the lowest landed cost that arrives in time"
                  f"{' and passed the recheck' if cheaper else ''}.{why}",
                  {**row_data, "rule": "R4"}, conn=conn)
        if status == "placed":
            conn.execute("UPDATE parts SET on_order = on_order + ? WHERE part_id = ?", (qty, part_id))
            msg = (f"Placed {po_id} with {offer['supplier_name']}: {_money(total)}, within the "
                   f"{_money(limit)} limit. {qty} added to on order.")
            audit.log(run_id, part_id, "order_placed", msg, {**row_data, "rule": "R6, R7"}, conn=conn)
        else:
            msg = (f"{_money(total)} is over the {_money(limit)} spending limit. {po_id} with "
                   f"{offer['supplier_name']} is waiting for the owner's approval.")
            audit.log(run_id, part_id, "approval_requested", msg, {**row_data, "rule": "R6"}, conn=conn)
        conn.commit()
    finally:
        conn.close()
    return {"status": status, "po_id": po_id, "reason": msg, "total": total,
            "spend_limit": limit, "supplier_id": offer["supplier_id"]}


def _decide(po_id, new_status, approver):
    run_id = audit.new_run_id("owner")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")  # one decision at a time: a double click can't approve twice
        po = conn.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,)).fetchone()
        if po is None:
            raise ValueError(f"No order {po_id}")
        if po["status"] != "pending_approval":
            done = {"placed": "already approved", "rejected": "already rejected"}.get(po["status"], po["status"])
            raise ValueError(f"{po_id} was {done}")
        changed = conn.execute(
            "UPDATE purchase_orders SET status = ?, approved_by = ? WHERE po_id = ? AND status = 'pending_approval'",
            (new_status, approver, po_id),
        ).rowcount
        if changed != 1:
            raise ValueError(f"{po_id} is no longer waiting for approval")
        data = {"po_id": po_id, "supplier_id": po["supplier_id"], "total": po["total"],
                "approved_by": approver}
        if new_status == "placed":
            conn.execute("UPDATE parts SET on_order = on_order + ? WHERE part_id = ?",
                         (po["qty"], po["part_id"]))
            audit.log(run_id, po["part_id"], "approved",
                      f"Owner approved {po_id} ({_money(po['total'])}). Order placed; "
                      f"{po['qty']} added to on order.", data, conn=conn)
        else:
            audit.log(run_id, po["part_id"], "rejected",
                      f"Owner rejected {po_id} ({_money(po['total'])}). Nothing ordered.", data, conn=conn)
        conn.commit()
        return {"po_id": po_id, "status": new_status}
    finally:
        conn.close()


def approve_order(po_id, approver="owner"):
    return _decide(po_id, "placed", approver)


def reject_order(po_id, approver="owner"):
    return _decide(po_id, "rejected", approver)


# --------------------------------------------------------------------- run --
def run_rules_only(spend_limit=None):
    """Section 7: every part in part_id order, using the same public functions
    the agent tools wrap. spend_limit overrides the live/.env limit. Raises
    "Simulated crash" when CRASH_AFTER_ORDERS is reached; everything written
    before stays."""
    run_id = start_run()
    limit = get_spend_limit(spend_limit)      # once per run: one run never mixes two limits
    crash_after = _crash_after()
    summary = {"run_id": run_id, "spend_limit": limit, "today": db.today(),
               "placed": [], "pending_approval": [], "skipped": [], "checked": [],
               "no_viable_offer": [], "refused": []}

    conn = db.connect()
    try:
        part_ids = [r[0] for r in conn.execute("SELECT part_id FROM parts ORDER BY part_id")]
    finally:
        conn.close()

    for part_id in part_ids:
        ev = evaluate_part(part_id, run_id, spend_limit=limit)
        if ev["existing_order"]:
            summary["skipped"].append(part_id)
            continue
        if not ev["needs_buying"]:
            summary["checked"].append(part_id)
            continue
        outcome = "no_viable_offer"
        for offer in ev["eligible_offers"]:
            if not recheck_offer(offer["offer_id"], ev["qty"], run_id)["passed"]:    # R5
                continue
            outcome = place_order(part_id, offer["offer_id"], ev["qty"], run_id, spend_limit=limit)["status"]
            break
        else:
            if ev["eligible_offers"]:
                audit.log(run_id, part_id, "no_viable_offer",
                          "Every eligible offer failed the recheck. Nothing ordered; "
                          "the owner should look at this part.", {"qty": ev["qty"]})
        summary.setdefault(outcome, []).append(part_id)
        if outcome == "placed" and crash_after > 0 and len(summary["placed"]) >= crash_after:
            raise RuntimeError("Simulated crash")
    return summary


if __name__ == "__main__":
    import sys

    if "--reset" in sys.argv:
        db.reset_demo()
    print(json.dumps(run_rules_only(), indent=2))
