# Parts Buyer

Purchasing agent for an equipment service shop, built at the Personal Agents Hackathon (AWS Loft SF, Nov 20, 2026; submit by 4:30 PM, demo at 5:00).
Spec: docs/SPEC.md. Part B is the spec; Part A wins on conflicts.

## People
- Mike: product owner, not a coder. Explain errors in one or two plain sentences and make the smallest fix.
- Shuhang: backend.

## File ownership
- Mike: app.py, check_answer_key.py, evals/, config_flags.py, Firedrill setup.
- Shuhang (never edit these): db.py, suppliers.py, audit.py, rules.py, tools.py, agent.py.
  If one of them needs a change, tell Mike what to ask Shuhang.

## Rules
- All money and compliance logic lives only in rules.py. app.py and check_answer_key.py hold no business logic.
- Python 3.12 (.venv). Never commit .env, .venv, or *.db.
- Run git status before every push. Small commits; git pull before git push.
- If one of Shuhang's modules is missing, wrap the import in try/except and show a yellow
  "backend not ready: <module>" note instead of crashing.
