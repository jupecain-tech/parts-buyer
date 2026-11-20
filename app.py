"""Parts Buyer screens (Streamlit).

Display only. All money and compliance logic lives in rules.py; this file
reads the database, shows it, and calls the backend when a button is pressed.
"""

import json
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_PATH = ROOT / "parts_buyer.db"
TODAY = os.getenv("TODAY", "2026-11-20")
USE_STATSIG = os.getenv("USE_STATSIG", "0").strip() == "1"
LOCAL_TZ = datetime.now().astimezone().tzinfo

st.set_page_config(page_title="Parts Buyer", page_icon="🔧", layout="wide")

# Projector sizing: bigger base text, numbers, tabs and tables.
st.markdown(
    """
    <style>
    html { font-size: 19px; }
    .stMarkdown p, .stMarkdown li, .stAlert p { font-size: 1.12rem; line-height: 1.5; }
    [data-testid="stMetricValue"] { font-size: 2.4rem; font-weight: 700; }
    [data-testid="stMetricLabel"] p { font-size: 1.05rem; }
    [data-testid="stTab"] p, button[data-baseweb="tab"] p { font-size: 1.3rem; font-weight: 600; }
    [data-testid="stExpander"] summary p { font-size: 1.15rem; font-weight: 600; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { font-size: 1.05rem; }
    .pb-summary { font-size: 1.6rem; font-weight: 700; margin: 0.2rem 0 0.8rem; }
    .pb-table { width: 100%; border-collapse: collapse; font-size: 1.05rem; }
    .pb-table th { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 2px solid rgba(128,128,128,.5); }
    .pb-table td { padding: 0.55rem 0.6rem; border-bottom: 1px solid rgba(128,128,128,.25); vertical-align: top; }
    .pb-table td:first-child { min-width: 17rem; }
    .pb-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .pb-table td.avail { font-weight: 800; font-size: 1.2rem; }
    .pb-why { display: block; font-size: 0.92rem; opacity: 0.75; margin-top: 0.15rem; }
    .pb-pill { padding: 0.1rem 0.55rem; border-radius: 999px; font-weight: 700; font-size: 0.95rem; white-space: nowrap; }
    .pb-ok { background: rgba(33,150,83,.18); color: #1b7f46; }
    .pb-short { background: rgba(214,69,65,.16); color: #b3261e; }
    .pb-ordered { background: rgba(30,110,220,.16); color: #1a5fb4; }
    .pb-waiting { background: rgba(230,160,0,.22); color: #8a5a00; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Backend modules. Missing ones show a note instead of crashing.
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


def local_time(ts, fmt="%-I:%M:%S %p"):
    try:
        t = pd.Timestamp(ts)
        if t.tzinfo is not None:
            t = t.tz_convert(LOCAL_TZ)
        return t.strftime(fmt)
    except (ValueError, TypeError):
        return str(ts or "")


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


STEP_LABELS = {
    "checked": "Checked",
    "gap_found": "Needs buying",
    "shopping": "Compared offers",
    "rejected_option": "Ruled out",
    "chosen": "Chosen",
    "recheck": "Live check",
    "order_placed": "Order placed",
    "approval_requested": "Asked you to approve",
    "approved": "You approved",
    "rejected": "You rejected",
    "refused": "Order blocked",
    "skipped": "Already handled",
    "no_viable_offer": "No offer works",
    "agent_note": "Agent's explanation",
    "recalled": "Recalled from memory",
}


def plain_english(text):
    """Presentation only: drop rule codes, add commas to dollars, swap jargon for plain words."""
    text = str(text or "")
    text = re.sub(r"\s*\(R\d+\)", "", text)          # "... misses due date (R4)"
    text = re.sub(r"\bR\d+\s*:\s*", "", text)         # "R6: $301 under ..."
    text = re.sub(
        r"\$(\d{4,})(\.\d+)?",
        lambda m: "$" + f"{int(m.group(1)):,}" + (m.group(2) or ""),
        text,
    )
    text = text.replace("lowest landed cost", "lowest total cost including shipping")
    text = text.replace("landed cost", "total cost including shipping")
    text = re.sub(r"(\d) x \$", r"\1 × $", text)
    text = re.sub(                                    # 2026-11-27 -> Nov 27
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
        lambda m: date(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%b %-d"),
        text,
    )
    return text


def today_label():
    try:
        return date.fromisoformat(TODAY).strftime("%a, %b %-d, %Y")
    except ValueError:
        return TODAY


# --- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.title("Parts Buyer")
    st.caption("Your shop's purchasing agent, with receipts")
    st.text_input("Today", value=today_label(), disabled=True)
    if USE_STATSIG:
        # Owner sets the limit in the Statsig console; rules.py fetches it on each run.
        try:
            from config_flags import get_live_limit

            spend_limit, limit_source = get_live_limit()
        except Exception as exc:
            spend_limit, limit_source = float(os.getenv("SPEND_LIMIT", "1000")), ".env"
            st.warning(f"backend not ready: config_flags ({exc})")
        run_limit = None
        with st.container(border=True):
            st.markdown("**Live rules**")
            st.markdown(f"Spending limit per order: **{money(spend_limit)}**")
            if limit_source == "Statsig":
                st.caption("Set by the owner in Statsig. Changes apply on the next run.")
            else:
                st.caption(":orange[Couldn't reach Statsig, so using the default limit.]")
    else:
        spend_limit = st.number_input(
            "Spending limit per order ($)", min_value=0, value=1000, step=100,
            help="Orders up to this total are placed automatically. Bigger ones wait for you.",
        )
        run_limit = spend_limit
    mode = st.radio(
        "Mode", ["Agent", "Rules only"], horizontal=True,
        help="Agent: the AI shops and explains. Rules only: the same rules run without the AI.",
    )
    crash_test = st.toggle("Crash test", help="Stops the run on purpose after 2 orders, to show a restart never orders twice.")
    run_clicked = st.button("Run agent", type="primary", width="stretch")
    reset_clicked = st.button("Reset demo", width="stretch")

    for _name, _exc in missing:
        st.warning(f"backend not ready: {_name}")

if reset_clicked:
    st.session_state.pop("ran", None)
    st.session_state.pop("last_result", None)
    if "db" in backend:
        try:
            backend["db"].reset_demo()
            st.session_state["flash"] = ("success", "Demo reset. Fresh stock, no orders.")
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
            with st.spinner("Checking parts and shopping suppliers..."):
                if module == "agent":
                    result = backend["agent"].run_agent(spend_limit=run_limit)
                else:
                    result = backend["rules"].run_rules_only(spend_limit=run_limit)
            st.session_state["ran"] = True
            st.session_state["last_result"] = result
        except Exception as exc:
            st.session_state.pop("ran", None)
            if "simulated crash" in str(exc).lower():
                st.session_state["flash"] = (
                    "error",
                    "Crash test: the run stopped on purpose. Everything saved so far is kept. "
                    "Turn Crash test off and run again: nothing will be ordered twice.",
                )
            else:
                st.session_state["flash"] = ("error", f"The run stopped with an error: {exc}")
        finally:
            if previous_crash is None:
                os.environ.pop("CRASH_AFTER_ORDERS", None)
            else:
                os.environ["CRASH_AFTER_ORDERS"] = previous_crash

# --- Data ------------------------------------------------------------------
db_ready = DB_PATH.exists()
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

inventory, inventory_error = None, None
if db_ready and "rules" in backend:
    try:
        inventory = backend["rules"].get_inventory_status()
    except Exception as exc:
        inventory_error = exc


def supplier_label(sid):
    return str(supplier_names.get(sid, sid)).replace(" (mock)", "")


def part_label(pid):
    return f"{pid} {part_names.get(pid, '')}".strip()


def row_data(row):
    try:
        return json.loads(row["data_json"] or "{}")
    except (TypeError, ValueError):
        return {}


if orders is not None and not orders.empty:
    placed = orders[orders["status"] == "placed"]
    orders_placed = len(placed)
    dollars = placed["total"].fillna(0).sum()
    awaiting = int((orders["status"] == "pending_approval").sum())
else:
    orders_placed, dollars, awaiting = 0, 0, 0

runs = audit[~audit["run_id"].astype(str).str.startswith("owner-")] if audit is not None else None
if runs is not None and not runs.empty:
    latest_run = runs["run_id"].iloc[-1]  # owner approvals are not runs
    parts_checked = runs.loc[runs["run_id"] == latest_run, "part_id"].dropna().nunique()
else:
    parts_checked = 0

# --- Main area -------------------------------------------------------------
flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
if not db_ready:
    st.info("Press Reset demo")

# One-line run summary: "3 orders placed ($1,321), 1 needs your approval, 4 parts OK."
if st.session_state.get("ran") and db_ready:
    ok_parts = sum(1 for p in (inventory or []) if p.get("status") == "OK")
    if awaiting == 0:
        approval_text = "nothing needs your approval"
    else:
        approval_text = f"{awaiting} {'needs' if awaiting == 1 else 'need'} your approval"
    st.markdown(
        f'<div class="pb-summary">✅ {plural(orders_placed, "order", "orders")} placed '
        f"({money(dollars)}), {approval_text}, {plural(ok_parts, 'part', 'parts')} OK.</div>",
        unsafe_allow_html=True,
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("Parts checked", parts_checked)
c2.metric("Orders placed", orders_placed)
c3.metric("Dollars committed", money(dollars))
c4.metric("Awaiting approval", awaiting)

waiting_tab = f"Approvals ({awaiting})" if awaiting else "Approvals"
tab_inv, tab_appr, tab_orders, tab_audit = st.tabs(["Inventory", waiting_tab, "Orders", "Audit trail"])

# Inventory
STATUS_PILLS = {
    "OK": ("pb-ok", "OK"),
    "Short": ("pb-short", "Short"),
    "Ordered": ("pb-ordered", "Ordered"),
    "Awaiting approval": ("pb-waiting", "Awaiting approval"),
}


def available_line(p):
    """'1 on hand - 1 reserved + 2 on order = 2, enough.' Wording follows the backend's status."""
    sums = f"{p['on_hand']} on hand - {p['reserved']} reserved + {p['on_order']} on order = {p['available']}"
    verdict = {
        "OK": "enough.",
        "Short": f"short: you want at least {p['reorder_point']}.",
        "Ordered": "includes today's order.",
        "Awaiting approval": "short; an order is waiting for your approval.",
    }.get(p["status"], f"{p['status'].lower()}.")
    return f"{sums}, {verdict}"


with tab_inv:
    if not db_ready:
        st.info("Press Reset demo")
    elif backend_note("rules"):
        pass
    elif inventory is None:
        st.warning(f"backend not ready: rules ({inventory_error})")
    else:
        head = (
            "<tr><th>Part</th><th>On hand</th><th>Reserved for jobs</th><th>On order</th>"
            "<th>Available</th><th>Reorder at</th><th>Status</th></tr>"
        )
        body = []
        for p in inventory:
            pill_class, pill_text = STATUS_PILLS.get(p["status"], ("", p["status"]))
            body.append(
                f"<tr><td><b>{p['part_id']}</b> {p['name']}<span class='pb-why'>{available_line(p)}</span></td>"
                f"<td class='num'>{p['on_hand']}</td><td class='num'>{p['reserved']}</td>"
                f"<td class='num'>{p['on_order']}</td><td class='num avail'>{p['available']}</td>"
                f"<td class='num'>{p['reorder_point']}</td>"
                f"<td><span class='pb-pill {pill_class}'>{pill_text}</span></td></tr>"
            )
        st.markdown(f"<table class='pb-table'>{head}{''.join(body)}</table>", unsafe_allow_html=True)
        st.caption("Available = on hand - reserved for jobs + on order.")


# Approvals
def decide(action, po_id, description):
    """Button callback: runs before the page redraws, so the numbers refresh at once."""
    try:
        getattr(backend["rules"], f"{action}_order")(po_id)
        if action == "approve":
            st.session_state["flash"] = ("success", f"Approved: {description}. The order is placed.")
        else:
            st.session_state["flash"] = ("info", f"Rejected: {description}. Nothing was ordered.")
    except Exception as exc:
        st.session_state["flash"] = ("error", f"Could not {action} that order: {exc}")


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
            asked = part_log[part_log["step"] == "approval_requested"] if not part_log.empty else pd.DataFrame()
            limit_then = row_data(asked.iloc[-1]).get("spend_limit") if len(asked) else None
            limit_then = float(limit_then) if limit_then is not None else float(spend_limit)
            over = float(po["total"]) - limit_then
            notes = part_log[part_log["step"] == "agent_note"]["message"] if not part_log.empty else []
            chosen = part_log[part_log["step"] == "chosen"]["message"] if not part_log.empty else []
            reason = notes.iloc[-1] if len(notes) else chosen.iloc[-1] if len(chosen) else "No reason was logged."
            supplier = supplier_label(po["supplier_id"])
            description = f"{part_label(pid)} from {supplier}, {money(po['total'])}"

            with st.container(border=True):
                st.markdown(f"### {part_names.get(pid, pid)}")
                left, right = st.columns([3, 2])
                with left:
                    st.markdown(
                        f"**Part:** {pid} · {int(po['qty'])} needed  \n"
                        f"**Supplier:** {supplier}  \n"
                        f"**Total:** {money(po['total'])} "
                        f"({int(po['qty'])} × {money(po['unit_price'])} + {money(po['shipping'])} shipping)"
                    )
                with right:
                    st.warning(f"**{money(over)} over your {money(limit_then)} limit**")
                st.markdown(f"**Why this one:** {plain_english(reason)}")
                a, r, _ = st.columns([1.3, 1, 3])
                a.button(f"Approve {money(po['total'])}", key=f"approve_{po['po_id']}", type="primary",
                         disabled=not rules_ready, width="stretch",
                         on_click=decide, args=("approve", po["po_id"], description))
                r.button("Reject", key=f"reject_{po['po_id']}", disabled=not rules_ready, width="stretch",
                         on_click=decide, args=("reject", po["po_id"], description))

# Orders
STATUS_LABELS = {"placed": "Placed", "pending_approval": "Waiting for you", "rejected": "Rejected by you"}

with tab_orders:
    if not db_ready:
        st.info("Press Reset demo")
    elif orders is None:
        st.warning("backend not ready: purchase orders table")
    elif orders.empty:
        st.caption("No orders yet. Press Run agent.")
    else:
        po_table = orders.sort_values(["created_at", "po_id"], ascending=False)

        def approved_by(row):
            if row["status"] == "pending_approval":
                return "—"
            if row["approved_by"]:
                return str(row["approved_by"]).capitalize()
            return "Auto (under limit)" if row["status"] == "placed" else ""

        st.table(
            pd.DataFrame(
                {
                    "Order #": po_table["po_id"],
                    "Part": [part_label(p) for p in po_table["part_id"]],
                    "Supplier": [supplier_label(s) for s in po_table["supplier_id"]],
                    "Qty": po_table["qty"],
                    "Total": po_table["total"].map(money),
                    "Status": po_table["status"].map(lambda s: STATUS_LABELS.get(s, s)),
                    "Approved by": [approved_by(r) for _, r in po_table.iterrows()],
                    "Daily order ID": po_table["idempotency_key"],
                }
            ).set_index("Order #")
        )
        st.caption("Daily order ID: one order per part per day, so a retry or restart can never order twice.")

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
            "Show part",
            ["All parts"] + part_ids,
            format_func=lambda p: p if p == "All parts" else part_label(p),
        )
        shown = part_ids if choice == "All parts" else [choice]
        latest_order = (
            orders.sort_values("created_at").groupby("part_id").tail(1).set_index("part_id")
            if orders is not None and not orders.empty
            else pd.DataFrame()
        )
        for pid in shown:
            steps = audit[audit["part_id"] == pid]
            catches = [
                d for d in (row_data(r) for _, r in steps[steps["step"] == "recheck"].iterrows())
                if d.get("passed") is False and d.get("listed_stock") is not None
                and d.get("live_stock") is not None and d["live_stock"] < d["listed_stock"]
            ]
            if pid in latest_order.index:
                o = latest_order.loc[pid]
                outcome = f"{STATUS_LABELS.get(o['status'], o['status'])}: {supplier_label(o['supplier_id'])}, {money(o['total'])}"
            elif (steps["step"] == "checked").any():
                outcome = "OK, nothing to buy"
            else:
                outcome = "No order"
            title = f"{part_label(pid)}  —  {outcome}" + ("  ⚠️ stale stock caught" if catches else "")
            with st.expander(title, expanded=bool(catches)):
                for d in catches:
                    st.warning(
                        f"**Caught before buying ({supplier_label(d.get('supplier_id'))}):** "
                        f"Catalog said {d['listed_stock']} in stock. Live check said {d['live_stock']}.",
                        icon="🔎",
                    )
                show_details = st.toggle("Show raw data", key=f"details_{pid}")
                for _, row in steps.iterrows():
                    label = STEP_LABELS.get(row["step"], str(row["step"]).replace("_", " ").capitalize())
                    st.markdown(
                        f"**{label}** · {plain_english(row['message'])}  \n:gray[{local_time(row['ts'])}]"
                    )
                    if show_details:
                        st.json(row_data(row), expanded=False)

if st.session_state.get("last_result"):
    with st.expander("Technical details of the last run"):
        result = st.session_state["last_result"]
        if isinstance(result, (dict, list)):
            st.json(result)
        else:
            st.write(result)
