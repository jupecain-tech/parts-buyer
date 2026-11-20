# Parts Buyer

Purchasing agent for an equipment service shop, built at the Personal Agents Hackathon (AWS Loft SF, Nov 20, 2026; submit by 4:30 PM, demo at 5:00).
Spec: docs/SPEC.md. Part B is the spec; Part A wins on conflicts.

## People
- Mike: product owner, not a coder. Explain errors in one or two plain sentences and make the smallest fix.
- Shuhang: backend (agent).

## File ownership
- Mike: app.py, check_answer_key.py, evals/, config_flags.py, Firedrill setup,
  and db.py, suppliers.py, audit.py, rules.py (taken over from Shuhang).
- Shuhang (never edit these): tools.py, agent.py.
  If one of them needs a change, tell Mike what to ask Shuhang.

## Rules
- All money and compliance logic lives only in rules.py. app.py and check_answer_key.py hold no business logic.
- Python 3.12 (.venv). Never commit .env, .venv, or *.db.
- Run git status before every push. Small commits; git pull before git push.
- If one of Shuhang's modules is missing, wrap the import in try/except and show a yellow
  "backend not ready: <module>" note instead of crashing.
- `python check_answer_key.py --all` must pass before any push that touches rules.py.

## Backend API (for tools.py / agent.py; wrap these, never repeat their logic)

rules.py
- `start_run() -> run_id`. run_rules_only calls it; the agent calls it once per run.
- `get_inventory_status() -> [dict]`: part_id, name, on_hand, reserved, on_order, available,
  reorder_point, status (OK / Short / Ordered / Awaiting approval), order_today.
- `get_spend_limit(override=None) -> float`: override, else Statsig (config_flags), else SPEND_LIMIT in .env.
- `evaluate_part(part_id, run_id, spend_limit=None) -> dict`: qty, deadline, eligible_offers
  (ranked by landed cost, each with offer_id, supplier_id, landed), rejected (offer_id,
  supplier_id, reason), needs_buying, existing_order, action. Logs gap_found and
  rejected_option rows (or checked / skipped when nothing needs buying).
- `recheck_offer(offer_id, qty, run_id) -> dict`: offer_id, supplier_id, live_stock, live_price,
  passed, reason. Logs a recheck row (plus a rejected_option row if it fails).
- `place_order(part_id, offer_id, qty, run_id, spend_limit=None) -> dict`: status
  (placed / pending_approval / refused / exists), po_id, reason. REFUSES unless the offer is
  eligible (R3, R4), qty is what evaluate_part says (R2), and a passing recheck of that same
  offer exists in this run's audit log (R5). Over the limit -> pending_approval (R6).
  One order per part per day (R7). Logs chosen, then order_placed or approval_requested.
- `approve_order(po_id)`, `reject_order(po_id)`.
- `run_rules_only(spend_limit=None) -> summary`. Reads CRASH_AFTER_ORDERS at the start of each run.

audit.py
- `log(run_id, part_id, step, message, data)`. Save the agent's explanation as step `agent_note`.
- `read_by_run(run_id)`, `read_by_part(part_id, run_id=None)`, `new_run_id()`.

Audit rows for recheck, rejected_option and chosen always carry supplier_id in data_json.
