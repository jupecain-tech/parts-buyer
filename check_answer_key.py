"""Answer key checker (SPEC Part B, sections 3 and 11).

Resets the demo, runs the backend, then compares what landed in the database
against the answer key. It holds no business logic: it only states the
expected results and looks at purchase_orders and audit_log.

  python check_answer_key.py              rules only mode, tests 1-7 and 9
  python check_answer_key.py --agent      same, through the tool calling agent
  python check_answer_key.py --crash      adds the crash and recovery tests (10, 11)
  python check_answer_key.py --limit-test adds the $3,000 limit test (12)
  python check_answer_key.py --all        everything above
  --skip-rerun   skip test 9 (saves one agent run)
  --json         machine readable output for evals/

Exit code: 0 all pass, 1 any failure, 2 backend not ready.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "parts_buyer.db"

# ---- The answer key (section 3). Data only. --------------------------------
EXPECTED_AT_1000 = {
    "P01": ("placed", "OEMD", 725),
    "P02": ("placed", "BRKA", 295),
    "P04": ("placed", "OEMD", 301),
    "P06": ("pending_approval", "BRKA", 2395),
}
EXPECTED_AT_3000 = {**EXPECTED_AT_1000, "P06": ("placed", "BRKA", 2395)}
NO_ORDER_PARTS = ["P03", "P05", "P07", "P08"]
ALL_PARTS = ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08"]
SUPPLIER_NAMES = {"OEMD": "OEM Direct", "BRKA": "Broker A", "BRKB": "Broker B"}


class BackendNotReady(Exception):
    pass


def load_backend(mode):
    mods = {}
    for name in ("db", "agent" if mode == "agent" else "rules"):
        try:
            mods[name] = __import__(name)
        except Exception as exc:
            raise BackendNotReady(f"backend not ready: {name} ({exc})")
    return mods


def run_once(mods, mode, limit, crash_after=0):
    """One run. Returns the error text if the run raised, else None."""
    os.environ["CRASH_AFTER_ORDERS"] = str(crash_after)
    try:
        if mode == "agent":
            mods["agent"].run_agent(spend_limit=limit)
        else:
            mods["rules"].run_rules_only(spend_limit=limit)
        return None
    except Exception as exc:
        return str(exc)
    finally:
        os.environ["CRASH_AFTER_ORDERS"] = "0"


# ---- Reading the database --------------------------------------------------
def rows(sql, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params)]


def orders():
    return rows("SELECT * FROM purchase_orders ORDER BY po_id")


def audit():
    return rows("SELECT * FROM audit_log ORDER BY ts, id")


def mentions(entry, supplier_id):
    text = f"{entry.get('message') or ''} {entry.get('data_json') or ''}"
    return supplier_id in text or SUPPLIER_NAMES[supplier_id] in text


def money(v):
    return f"${v:,.0f}"


# ---- Checks ----------------------------------------------------------------
class Report:
    def __init__(self):
        self.results = []

    def check(self, test, ok, detail):
        self.results.append({"test": test, "pass": bool(ok), "detail": detail})

    @property
    def passed(self):
        return all(r["pass"] for r in self.results)


def check_orders(rep, test, expected, label):
    pos = orders()
    by_part = {}
    for po in pos:
        by_part.setdefault(po["part_id"], []).append(po)
    for part, (status, supplier, total) in expected.items():
        found = by_part.get(part, [])
        ok = (
            len(found) == 1
            and found[0]["status"] == status
            and found[0]["supplier_id"] == supplier
            and abs(float(found[0]["total"] or 0) - total) < 0.01
        )
        want = f"{part} {SUPPLIER_NAMES[supplier]} {money(total)} {status}"
        got = ", ".join(
            f"{p['supplier_id']} {money(float(p['total'] or 0))} {p['status']}" for p in found
        ) or "no order"
        rep.check(test, ok, f"{label}: want {want}; got {got}")
    for part in NO_ORDER_PARTS:
        found = by_part.get(part, [])
        rep.check(test, not found, f"{label}: {part} should have no order; got {len(found)}")
    keys = [p["idempotency_key"] for p in pos]
    rep.check(test, len(keys) == len(set(keys)), f"{label}: no duplicate order keys")
    placed = sum(p["status"] == "placed" for p in pos)
    pending = sum(p["status"] == "pending_approval" for p in pos)
    want_placed = sum(s == "placed" for s, _, _ in expected.values())
    want_pending = sum(s == "pending_approval" for s, _, _ in expected.values())
    rep.check(
        test,
        placed == want_placed and pending == want_pending,
        f"{label}: want {want_placed} placed, {want_pending} awaiting approval; "
        f"got {placed} placed, {pending} awaiting approval",
    )


def check_trail(rep):
    log = audit()
    steps = lambda part: [e for e in log if e["part_id"] == part]  # noqa: E731

    # Test 2: P01 stale data. Broker A rechecked and rejected, OEM Direct chosen.
    p01 = steps("P01")
    rechecked_a = any(e["step"] == "recheck" and mentions(e, "BRKA") for e in p01)
    rejected_a = any(e["step"] == "rejected_option" and mentions(e, "BRKA") for e in p01)
    chose_oem = any(e["step"] == "chosen" and mentions(e, "OEMD") for e in p01)
    rep.check("2 stale data", rechecked_a, "P01: Broker A was rechecked")
    rep.check("2 stale data", rejected_a, "P01: Broker A was ruled out")
    rep.check("2 stale data", chose_oem, "P01: OEM Direct was chosen")

    # Test 3: P02 landed cost. Broker B not chosen.
    p02 = steps("P02")
    rep.check(
        "3 landed cost",
        not any(e["step"] == "chosen" and mentions(e, "BRKB") and not mentions(e, "BRKA") for e in p02)
        and any(e["step"] == "chosen" and mentions(e, "BRKA") for e in p02),
        "P02: Broker A chosen over Broker B",
    )

    # Test 4: P04 deadline. Broker B ruled out.
    rep.check(
        "4 deadline",
        any(e["step"] == "rejected_option" and mentions(e, "BRKB") for e in steps("P04")),
        "P04: Broker B ruled out (too late for job J2)",
    )

    # Test 5: P06 approved list. Broker B ruled out, approval requested.
    p06 = steps("P06")
    rep.check(
        "5 approved list",
        any(e["step"] == "rejected_option" and mentions(e, "BRKB") for e in p06),
        "P06: Broker B ruled out (not approved for this part)",
    )
    rep.check(
        "5 approved list",
        any(e["step"] == "approval_requested" for e in p06),
        "P06: owner asked for approval",
    )

    # Test 6 and 7: no false alarms.
    for part in NO_ORDER_PARTS:
        s = steps(part)
        ok = any(e["step"] == "checked" for e in s) and not any(e["step"] == "gap_found" for e in s)
        rep.check("6/7 no false alarms", ok, f"{part}: checked OK, no gap found")

    # Recheck before every purchase (eval metric 2).
    for po in orders():
        if po["status"] not in ("placed", "pending_approval"):
            continue
        part_log = steps(po["part_id"])
        first_action = next(
            (i for i, e in enumerate(part_log) if e["step"] in ("order_placed", "approval_requested")),
            None,
        )
        ok = first_action is not None and any(
            e["step"] == "recheck" for e in part_log[:first_action]
        )
        rep.check("recheck first", ok, f"{po['part_id']}: rechecked before ordering")

    # Every part shows up in the trail (feeds test 13).
    logged = {e["part_id"] for e in log}
    missing = [p for p in ALL_PARTS if p not in logged]
    rep.check("13 trail covers all parts", not missing, f"missing from audit trail: {missing or 'none'}")


def run_check(mode="rules", limit=1000, rerun=True, crash=False, limit_test=False):
    mods = load_backend(mode)
    rep = Report()

    # Tests 1-7: clean run.
    mods["db"].reset_demo()
    err = run_once(mods, mode, limit)
    rep.check("1 clean run", err is None, f"run finished without error ({err or 'ok'})")
    check_orders(rep, "1 clean run", EXPECTED_AT_1000 if limit < 2395 else EXPECTED_AT_3000, "clean run")
    check_trail(rep)

    # Test 9: same day rerun places nothing new.
    if rerun:
        before = len(orders())
        err = run_once(mods, mode, limit)
        after = len(orders())
        rep.check("9 same day rerun", err is None and after == before,
                  f"rerun added {after - before} orders (want 0)")

    # Tests 10-11: crash after 2 orders, then recover.
    if crash:
        mods["db"].reset_demo()
        err = run_once(mods, mode, limit, crash_after=2)
        placed = sorted(p["part_id"] for p in orders() if p["status"] == "placed")
        rep.check("10 crash", err is not None and "simulated crash" in err.lower(),
                  f"run stopped with 'Simulated crash' (got: {err or 'no error'})")
        rep.check("10 crash", placed == ["P01", "P02"], f"exactly P01, P02 placed; got {placed}")
        err = run_once(mods, mode, limit)
        rep.check("11 recovery", err is None, f"recovery run finished ({err or 'ok'})")
        check_orders(rep, "11 recovery", EXPECTED_AT_1000, "after recovery")
        skipped = {e["part_id"] for e in audit() if e["step"] == "skipped"}
        rep.check("11 recovery", {"P01", "P02"} <= skipped, "P01, P02 skipped on recovery")

    # Test 12: owner raises the limit to $3,000.
    if limit_test:
        mods["db"].reset_demo()
        err = run_once(mods, mode, 3000)
        rep.check("12 limit $3,000", err is None, f"run finished ({err or 'ok'})")
        check_orders(rep, "12 limit $3,000", EXPECTED_AT_3000, "limit $3,000")

    return rep


def main():
    ap = argparse.ArgumentParser(description="Check a run against the answer key.")
    ap.add_argument("--agent", action="store_true", help="use the tool calling agent")
    ap.add_argument("--limit", type=float, default=1000)
    ap.add_argument("--skip-rerun", action="store_true")
    ap.add_argument("--crash", action="store_true")
    ap.add_argument("--limit-test", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    mode = "agent" if args.agent else "rules"

    try:
        rep = run_check(
            mode=mode,
            limit=args.limit,
            rerun=not args.skip_rerun,
            crash=args.crash or args.all,
            limit_test=args.limit_test or args.all,
        )
    except BackendNotReady as exc:
        print(json.dumps({"ready": False, "error": str(exc)}) if args.json else str(exc))
        sys.exit(2)

    if args.json:
        print(json.dumps({"ready": True, "mode": mode, "pass": rep.passed, "results": rep.results}, indent=2))
    else:
        for r in rep.results:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  [{r['test']}] {r['detail']}")
        n_ok = sum(r["pass"] for r in rep.results)
        print(f"\n{mode} mode: {n_ok}/{len(rep.results)} checks passed -> "
              f"{'ALL PASS' if rep.passed else 'FAILURES ABOVE'}")
    sys.exit(0 if rep.passed else 1)


if __name__ == "__main__":
    main()
