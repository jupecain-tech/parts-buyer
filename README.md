# Parts Buyer

The shop owner's personal purchasing agent for an equipment service shop. It checks inventory against open repair jobs, shops approved suppliers, rechecks live stock and price before buying, stays under the owner's spending limit, and logs every decision.

The model never holds the checkbook: rules are enforced in code (rules.py); the model proposes and explains.

Built at the Personal Agents Hackathon, AWS Loft SF, Nov 20, 2026. Spec: docs/SPEC.md.

## Setup
```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
