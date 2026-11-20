"""Parts Buyer screens (Streamlit).

Display only. All money and compliance logic lives in rules.py; this file
reads the database, shows it, and calls the backend when a button is pressed.
"""

import json
import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_PATH = ROOT / "parts_buyer.db"
TODAY = os.getenv("TODAY", "2026-11-20")

st.set_page_config(page_title="Parts Buyer", page_icon="🔧", layout="wide")

# --- Backend modules (Shuhang's). Missing ones show a note instead of crashing.
backend = {}
missing = []
for _name in ("db", "rules", "agent"):
    try:
        backend[_name] = __import__(_name)
    except Exception as exc:  # ImportError, or an error inside a half-built module
        missing.append((_name, exc))


def backend_note(name):
    """Yellow note for a module that is not there yet. Returns True if missing."""
    if name in backend:
        return False
    st.warning(f"backend not ready: {name}")
    return True


# --- Read-only database helpers --------------------------------------------
def read_table(sql, params=()):
    """Return a DataFrame, or None if the database or table is not there yet."""
    if not DB_PATH.exists():
        return None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError):
        return None


def money(value):
    try:
        return f"${float(value):,.0f}" if float(value).is_integer() else f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0"


STEP_LABELS = {
    "checked": "Checked",
    "gap_found": "Needs buying",
    "shopping": "Shopping",
    "rejected_option": "Ruled out",
    "chosen": "Chosen",
    "recheck": "Rechecked",
    "order_placed": "Order placed",
    "approval_requested": "Asked the owner",
    "approved": "Approved",
    "skipped": "Skipped",
    "no_viable_offer": "No offer works",
    "agent_note": "Agent's explanation",
    "recalled": "Recalled from memory",
}


def plain_english(text):
    """Presentation only: drop rule codes like (R4) and add commas to dollar amounts."""
    text = str(text or "")
    text = re.sub(r"\s*\(R\d+\)", "", text)          # "... misses due date (R4)"
    text = re.sub(r"\bR\d+\s*:\s*", "", text)         # "R6: $301 under ..."
    text = re.sub(
        r"\$(\d{4,})(\.\d+)?",
        lambda m: "$" + f"{int(m.group(1)):,}" + (m.group(2) or ""),
        text,
    )
    return text


# --- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.title("Parts Buyer")
    st.caption("Your shop's purchasing agent, with receipts")
    st.text_input("Today", value=TODAY, disabled=True)
    spend_limit = st.number_input("Spending limit ($)", min_value=0, value=1000, step=100)
    mode = st.radio("Mode", ["Agent", "Rules only"], horizontal=True)
    crash_test = st.toggle("Crash test", help="Stops the run on purpose after 2 orders.")
    run_clicked = st.button("Run agent", type="primary", width="stretch")
    reset_clicked = st.button("Reset demo", width="stretch")

    for _name, _exc in missing:
        st.warning(f"backend not ready: {_name}")

if reset_clicked:
    if "db" in backend:
        try:
            backend["db"].reset_demo()
            st.session_state["flash"] = ("success", "Demo reset. Fresh data loaded.")
        except Exception as exc:
            st.session_state["flash"] = ("error", f"Reset failed: {exc}")
    else:
        st.session_state["flash"] = ("warning", "backend not ready: db")

if run_clicked:
    module = "agent" if mode == "Agent" else "rules"
    if module not in backend:
        st.session_state["flash"] = ("warning", f"backend not ready: {module}")
    else:
        # The crash switch is read by the backend from CRASH_AFTER_ORDERS (SPEC section 7).
        previous_crash = os.environ.get("CRASH_AFTER_ORDERS")
        os.environ["CRASH_AFTER_ORDERS"] = "2" if crash_test else "0"
        try:
            with st.spinner("Running..."):
                if module == "agent":
                    result = backend["agent"].run_agent(spend_limit=spend_limit)
                else:
                    result = backend["rules"].run_rules_only(spend_limit=spend_limit)
            st.session_state["flash"] = ("success", "Run finished.")
            st.session_state["last_result"] = result
        except Exception as exc:
            if "simulated crash" in str(exc).lower():
                st.session_state["flash"] = (
                    "error",
                    "Simulated crash. The run stopped on purpose; everything saved so far is kept. "
                    "Turn Crash test off and run again.",
                )
            else:
                st.session_state["flash"] = ("error", f"Run failed: {exc}")
        finally:
            if previous_crash is None:
                os.environ.pop("CRASH_AFTER_ORDERS", None)
            else:
                os.environ["CRASH_AFTER_ORDERS"] = previous_crash

# --- Main area -------------------------------------------------------------
flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
if st.session_state.get("last_result"):
    with st.expander("Last run summary"):
        result = st.session_state["last_result"]
        if isinstance(result, (dict, list)):
            st.json(result)
        else:
            st.write(result)

db_ready = DB_PATH.exists()
if not db_ready:
    st.info("Press Reset demo")

orders = read_table(
    "SELECT po_id, idempotency_key, part_id, supplier_id, offer_id, qty, unit_price, "
    "shipping, total, status, approved_by, created_at FROM purchase_orders"
)
audit = read_table(
    "SELECT id, run_id, ts, part_id, step, message, data_json FROM audit_log ORDER BY ts, id"
)
names = read_table("SELECT part_id, name FROM parts")
part_names = dict(zip(names["part_id"], names["name"])) if names is not None else {}
sups = read_table("SELECT supplier_id, name FROM suppliers")
supplier_names = dict(zip(sups["supplier_id"], sups["name"])) if sups is not None else {}


def supplier_label(sid):
    return str(supplier_names.get(sid, sid)).replace(" (mock)", "")

# Top row of numbers
if audit is not None and not audit.empty:
    latest_run = audit["run_id"].iloc[-1]
    parts_checked = audit.loc[audit["run_id"] == latest_run, "part_id"].dropna().nunique()
else:
    parts_checked = 0
if orders is not None and not orders.empty:
    placed = orders[orders["status"] == "placed"]
    orders_placed = len(placed)
    dollars = placed["total"].fillna(0).sum()
    awaiting = int((orders["status"] == "pending_approval").sum())
else:
    orders_placed, dollars, awaiting = 0, 0, 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Parts checked", parts_checked)
c2.metric("Orders placed", orders_placed)
c3.metric("Dollars committed", money(dollars))
c4.metric("Awaiting approval", awaiting)

tab_inv, tab_appr, tab_orders, tab_audit = st.tabs(
    ["Inventory", "Approvals", "Orders", "Audit trail"]
)

# Inventory
with tab_inv:
    if not db_ready:
        st.info("Press Reset demo")
    elif not backend_note("rules"):
        try:
            rows = backend["rules"].get_inventory_status()
            inv = pd.DataFrame(rows)
            cols = {
                "part_id": "Part",
                "name": "Name",
                "on_hand": "On hand",
                "reserved": "Reserved",
                "on_order": "On order",
                "available": "Available",
                "reorder_point": "Reorder point",
                "status": "Status",
            }
            inv = inv[[c for c in cols if c in inv.columns]].rename(columns=cols)
            styled = inv.style
            if "Available" in inv.columns:
                styled = styled.set_properties(subset=["Available"], **{"font-weight": "bold"})
            st.dataframe(styled, hide_index=True, width="stretch")
        except Exception as exc:
            st.warning(f"backend not ready: rules ({exc})")

# Approvals
def decide(action, po_id, part_id):
    """Button callback: runs before the page redraws, so the numbers refresh at once."""
    try:
        getattr(backend["rules"], f"{action}_order")(po_id)
        verb = "approved and placed" if action == "approve" else "rejected"
        st.session_state["flash"] = ("success", f"{po_id} for {part_id} {verb}.")
    except Exception as exc:
        st.session_state["flash"] = ("error", f"Could not {action} {po_id}: {exc}")


with tab_appr:
    pending = (
        orders[orders["status"] == "pending_approval"].sort_values("created_at")
        if orders is not None and not orders.empty
        else None
    )
    if not db_ready:
        st.info("Press Reset demo")
    elif pending is None or pending.empty:
        st.success("Nothing waiting on you.")
    else:
        rules_ready = not backend_note("rules")
        for _, po in pending.iterrows():
            pid = po["part_id"]
            part_log = audit[audit["part_id"] == pid] if audit is not None else pd.DataFrame()
            notes = part_log[part_log["step"] == "agent_note"]["message"] if not part_log.empty else []
            asked = part_log[part_log["step"] == "approval_requested"]["message"] if not part_log.empty else []
            explanation = (
                notes.iloc[-1] if len(notes) else asked.iloc[-1] if len(asked) else "No explanation logged."
            )
            with st.container(border=True):
                st.markdown(f"#### {pid} {part_names.get(pid, '')}  ·  {money(po['total'])}")
                st.markdown(
                    f"{int(po['qty'])} from **{supplier_label(po['supplier_id'])}** at "
                    f"{money(po['unit_price'])} each + {money(po['shipping'])} shipping. "
                    f"This is over your {money(spend_limit)} spending limit, so it needs you."
                )
                st.markdown(f"> {plain_english(explanation)}")
                st.caption(f"{po['po_id']} · created {po['created_at']}")
                a, r, _ = st.columns([1, 1, 4])
                a.button("Approve", key=f"approve_{po['po_id']}", type="primary", disabled=not rules_ready,
                         on_click=decide, args=("approve", po["po_id"], pid))
                r.button("Reject", key=f"reject_{po['po_id']}", disabled=not rules_ready,
                         on_click=decide, args=("reject", po["po_id"], pid))

# Orders
STATUS_LABELS = {"placed": "Placed", "pending_approval": "Awaiting approval", "rejected": "Rejected"}

with tab_orders:
    if not db_ready:
        st.info("Press Reset demo")
    elif orders is None:
        st.warning("backend not ready: purchase orders table")
    elif orders.empty:
        st.caption("No orders yet. Press Run agent.")
    else:
        po_table = orders.sort_values(["created_at", "po_id"], ascending=False)
        po_table = pd.DataFrame(
            {
                "PO": po_table["po_id"],
                "Part": [f"{p} {part_names.get(p, '')}".strip() for p in po_table["part_id"]],
                "Supplier": [supplier_label(s) for s in po_table["supplier_id"]],
                "Qty": po_table["qty"],
                "Unit price": po_table["unit_price"].map(money),
                "Shipping": po_table["shipping"].map(money),
                "Total": po_table["total"].map(money),
                "Status": po_table["status"].map(lambda s: STATUS_LABELS.get(s, s)),
                "Approved by": po_table["approved_by"].fillna(""),
                "Created": po_table["created_at"],
                "Order key": po_table["idempotency_key"],
            }
        )
        st.dataframe(po_table, hide_index=True, width="stretch")

# Audit trail
with tab_audit:
    if not db_ready:
        st.info("Press Reset demo")
    elif audit is None:
        st.warning("backend not ready: audit log table")
    elif audit.empty:
        st.caption("No steps yet. Press Run agent.")
    else:
        part_ids = sorted(audit["part_id"].dropna().unique())
        choice = st.selectbox(
            "Part",
            ["All parts"] + part_ids,
            format_func=lambda p: p if p == "All parts" else f"{p} {part_names.get(p, '')}".strip(),
        )
        shown = part_ids if choice == "All parts" else [choice]
        for pid in shown:
            steps = audit[audit["part_id"] == pid]
            title = f"{pid} {part_names.get(pid, '')}".strip() + f"  ({len(steps)} steps)"
            with st.expander(title):
                show_details = st.toggle("details", key=f"details_{pid}")
                for _, row in steps.iterrows():
                    label = STEP_LABELS.get(row["step"], str(row["step"]).replace("_", " ").capitalize())
                    when = str(row["ts"])[11:19] or str(row["ts"])
                    st.markdown(f"**{label}** · {plain_english(row['message'])}  \n:gray[{when}]")
                    if show_details:
                        try:
                            st.json(json.loads(row["data_json"] or "{}"), expanded=False)
                        except (TypeError, ValueError):
                            st.code(str(row["data_json"]))
