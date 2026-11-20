# For Shuhang: live spending limit (Statsig)

Mike's `config_flags.py` is in the repo. It exposes `get_live_limit()`, which returns
`(value, source)`, with `source` either `"Statsig"` or `".env"`. It never raises.
When `USE_STATSIG=1`, the app calls your run functions with `spend_limit=None`,
so the limit has to be resolved inside rules.py.

## 1. rules.py: add this near the top, and use it as the only place the limit is read

```python
import os

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
```

## 2. rules.py: at the start of `run_rules_only(spend_limit=None)`, before the loop over parts

```python
    limit = get_spend_limit(spend_limit)
```

Use `limit` in the R6 check (`if total <= limit:`) instead of SPEND_LIMIT.
Call it once per run, not once per part, so one run never mixes two limits.

## 3. agent.py

`run_agent(spend_limit=None)` and `run_explain_only(spend_limit=None)` should do the same:
`limit = rules.get_spend_limit(spend_limit)`, then put `limit` in the system prompt's
"${SPEND_LIMIT}" spot. They should also hand the same `limit` to whatever place_order
uses, so the model is told the same limit the code enforces.

Until this lands, Statsig mode is still safe: the app passes `spend_limit=None`,
and your code falls back to the `.env` value.
