# Parts Buyer: Build Guide for the Team

Personal Agents Hackathon, AWS Loft SF, Friday Nov 20, 2026. Kickoff 11:00, submission 4:30, demos 5:00, awards 7:00.

Team: Mike (product, screens, pitch), Shuhang (backend), eval teammate (evals, sponsor adapters).

How to read this file: Part A is the plan for today (who does what, when, which accounts we need, how we use sponsor tools, how we test, how we demo). Part B is the full specification: rules, data, code logic, Claude Code prompts, acceptance tests. Read Part A first, skim Part B, then keep Part B open while building. Where the two differ, Part A wins.

---

# PART A. Plan for today

## A1. The goal in one paragraph

Build Parts Buyer: the shop owner's personal purchasing agent for an equipment service shop. It watches parts inventory against open repair jobs, shops approved suppliers when stock runs short, rechecks live stock and price before buying, stays inside the owner's spending limit, and logs every decision so anyone can see why. It answers the challenge on the kickoff slide: a personal agent that helps someone make a purchase, uses reliable context to decide, takes a meaningful action, and shows the information and steps behind what it did.

Pitch lines to keep in our heads: "It shops like your best buyer and documents it like your auditor." "The model never holds the checkbook."

## A2. What the judges score, and our answer

| Criterion (kickoff slide) | Our answer | Proof in the demo |
|---|---|---|
| Autonomy: completes a real task end to end without manual intervention | One click runs read, shop, recheck, order, update, log. It stops only where the owner's rules say it must (order over the limit), which we present as a designed feature | Press Run once; no one touches it except the P06 approval |
| Idea: meaningful problem, real value | Service shops lose repair days to missing parts and cannot explain later why something was bought. Real pilot candidate: a medical equipment service company (a candidate, not a customer) | 20 second problem statement, then the P03 "already on order" moment |
| Technical implementation | Rules enforced in code, model proposes and explains; one order per part per day (idempotent); survives a crash; answer key and repeated run evals | Crash test, eval numbers |
| Tool use: effective use of sponsor tools | Three sponsor tools, each doing a visible job (A5) | Memory recall, live limit change, second audit record |
| Presentation: demo in 3 minutes | Scripted and rehearsed twice, backup recording | Part B, section 13 |

## A3. Roles

| Person | Owns | Does not touch |
|---|---|---|
| Shuhang | db.py, rules.py, suppliers.py, tools.py, agent.py (Part B, steps 1 to 3). Commit db.py first, within 20 minutes of kickoff, so screens can build on the real tables | app.py, audit.py |
| Mike | app.py (screens, step 4), repo setup, sponsor rep conversations, timekeeping, demo script, submission | rules.py logic |
| Eval teammate | audit.py (small; written first so rules.py can call it), check_answer_key.py, evals/ folder (A6), then sponsor adapters with whoever is free after the gate | rules.py logic |

Rules of the road
- Commit small, pull before you push, push after every step. Never work on the same file as someone else.
- Money and compliance logic lives only in rules.py. Nobody puts a limit check anywhere else.
- Never commit .env. The repo will be seen by reviewers. Only .env.example goes in.
- Ground rules to confirm before we start: (1) one shared repo, all of us contributors; (2) any prize is split evenly; (3) Mike keeps the right to build a commercial version for service shops he works with, and nobody is locked out of doing the same.
- Projects must be built during the event. We bring the written spec, test data and policy text only. No code is written before 11:00.

## A4. Hour by hour

| Time | Mike | Shuhang | Eval teammate |
|---|---|---|---|
| Now to 11:00 | Confirm roles and ground rules. Create the repo, add non-code files (README, .gitignore, .env.example, requirements.txt, data/*.csv, docs/SPEC.md, docs/policy.md). Talk to sponsor reps (A5, A7) | Read Part B sections 1 to 8. Set up venv and Claude Code | Read Part B sections 3 and 11, plus A6. Set up accounts |
| 11:00 to 11:30 | Step 4: screens begin | Step 1: data and supplier mock | Draft eval harness plan; get sponsor keys working in a scratch file |
| 11:30 to 12:15 | Screens: sidebar, top row, Inventory tab | Step 2: rules and audit | Write check_answer_key.py skeleton against section 3 |
| 12:15 to 1:00 | Screens: Approvals, Orders, Audit tabs | Step 3: agent | Run answer key on rules only mode as soon as Step 2 lands |
| 1:00 | GATE | GATE | GATE |
| 1:00 to 1:30 | Lunch in shifts (20 minutes), keep building | | |
| 1:00 to 2:00 | Decide Plan A or Plan B; wire the screens to the agent | Fix agent failures from the answer key | Run evals, 10 runs, report numbers |
| 2:00 to 3:00 | Step 5: crash test, approvals, polish | Step 5 backend support | Step 5b: sponsor adapters (A5), one each if the third person is free |
| 3:00 to 3:30 | Step 6: run all acceptance tests (Part B, section 11) | Fix failures only | Final eval run with sponsors off and on |
| 3:30 | FEATURE FREEZE. Record the backup demo video | | |
| 3:30 to 4:20 | README, description, push, submission form | Final bug fixes only | Eval numbers for the slide |
| 4:20 | SUBMIT (deadline 4:30) | | |
| 4:30 to 5:00 | Rehearse the 3 minute demo twice | | |

The 1:00 gate: if the tool calling agent (Plan A) cannot pass the answer key twice in a row by 1:00, we switch to Plan B (rules run in code, the model only explains). Plan B uses the same screens, trail and answer key. It is a decision made with data, not a failure. Anything not working at 3:30 gets cut, not rushed.

## A5. Sponsor tools: what we need, what they cost, what we do

Sponsors listed on the event page: Superlinked, Amplitude + Statsig, Guild AI, Airbyte, Arcee, Cognee, Firedrill, SingleStore, Persona. The page describes the tools in one line each and gives no credit amounts. It says only that the organizers bring "the venue, the compute credits, and the food." We need tools from three sponsors, and tool use is one of five judging criteria.

Design rules for every sponsor integration
1. Each lives in its own file and is switched on by a flag in .env (USE_COGNEE, USE_STATSIG, USE_GUILD or USE_FIREDRILL).
2. The agent must pass the whole answer key with every flag off. A sponsor failure must log "sponsor_error", fall back to the local default, and keep running.
3. A sponsor tool never decides the money. Rules R1 to R8 stay in rules.py.
4. Built after the 1:00 gate, only once the core is green. Target window 2:00 to 3:00.
5. Each one must show up on screen in the demo. A tool that is in the code but not visible earns little.

### Sponsor 2 (locked): Cognee (agent memory). Fallback: SingleStore if Cognee embeddings are not working by 2:15

(Section heading numbering: Statsig below is sponsor 1, Firedrill is sponsor 3.)

What it is: an open source memory platform for agents. You add documents, it builds a knowledge graph and embeddings, and the agent searches it later.

Job in Parts Buyer: memory.py loads the purchasing policy (Part B, section 12) and the outcome of each run (what was bought, what was rejected and why). Before shopping a part, the agent recalls policy and past lessons, for example "Broker A showed stale stock on this part last run." The recalled text is stored on the audit entry and shown on the Audit tab.

Basic calls from the project's public README: await cognee.add(text), await cognee.cognify(), await cognee.search(query_text=...). Newer releases also offer remember and recall. Have Claude Code read the current quickstart before writing code.

Credit and key needs: Cognee needs an LLM and an embedding provider. If only one is configured, the other defaults to OpenAI and add() fails with a configuration mismatch error. Our LLM goes through OpenRouter. We should not assume OpenRouter serves embeddings (one older source says it does not), so we need one of: an OpenAI key for embeddings, a hosted Cognee key or credits from the sponsor, or a local embedding model. ASK THE COGNEE REP FIRST: "What is the fastest working setup with OpenRouter for the LLM, and can you give us credits or a key for embeddings?"

Risk: medium. First setup may eat 30 to 45 minutes. If it is not working by 2:45, drop it and use the fallback sponsor.

### Sponsor 2: Amplitude + Statsig (live rules and analytics)

What it is: product analytics, feature flags and experimentation.

Job in Parts Buyer: config_flags.py reads the owner's spending limit and approved supplier overrides from a Statsig Dynamic Config named parts_buyer_rules, falling back to .env values if Statsig is unreachable. Every agent decision (order placed, approval requested, option rejected) is also sent as an event. In the demo we change the limit in the Statsig console, re-run, and P06 now goes through automatically (acceptance test 12). That is the owner setting the rules live.

Setup: free Statsig account, create a Dynamic Config with a spend_limit number and an approved_suppliers list, copy the Server Secret Key. Python package statsig-python-core (import statsig_python_core); a legacy statsig package also exists. Initialization needs a network call; the SDK reads typed values from a DynamicConfig with a fallback value. Keep the secret key only in .env.

Credit and key needs: signing up is free; no credits needed for this use. Confirm with the rep whether Amplitude events need a separate project key and whether there is a best use prize.

Risk: low. This is the safest sponsor integration and gives the most visible demo moment.

### Sponsor 3: Firedrill (simulation and evals)

What it is: a simulation platform for AI agents. A synthetic world of users, stateful tools, data and scenarios lets the agent act without touching production. The agent and its code run on our machines; source code is not uploaded. It has an MCP server at https://mcp.firedrill.run that coding agents such as Claude Code connect to, and a firedrill-run CLI.

How it works (from its site): connect Claude Code over MCP and approve access in the browser; the coding agent reads the repo and registers the agent; it proposes users, scenarios, tools and evaluations, and shows a plan and credit estimate before anything runs; the agent runs locally against the synthetic world; Firedrill records and scores the results, and saved scenarios can be rerun after changes to compare. Evaluations score outcomes against success criteria and hard rules and show the evidence.

Why it fits: our rules R3, R5, R6, R7 are exactly "hard rules", and our answer key is exactly a set of scenarios. It turns our eval plan (A6) into a measured, sponsor backed result.

Credits: the event slide reads: Claim 2,000 credits. Sign up free. Apply event code TOKENSAND in Billing. It also reads: $2,000 in prizes for best use of Firedrill. The redeem link from the QR is https://app.firedrill.run/redeem#code=TOKENSAND. The free plan otherwise gives 500 credits a month. Credits pay for synthetic users, scoring and synthetic tools; our own model provider (OpenRouter) is billed separately. This is a real prize target: $2,000 for best use of Firedrill.

Owner: eval teammate. Redeem the code and connect the MCP server now (before 11:00). Register the agent once Step 3 (agent.py) exists, around 1:00. Do not let Firedrill change rules.py; it observes and scores.

Guild AI was considered and dropped: its page does not mention Python or a quickstart. Revisit only if its rep shows a working Python path in 15 minutes.

## A5b. Sponsor scorecard: three tools, each with a number we can show

Decision: we use three sponsors, each with a specific job, a measurable pass condition and a visible demo moment. Each is graded in evals/run_evals.py and reported on one "Sponsor scorecard" slide.

| # | Sponsor | Specific use | Measurable pass condition | Shown in the demo |
|---|---|---|---|---|
| 1 | Amplitude + Statsig | (a) The spending limit and approved supplier list are read from a Statsig Dynamic Config, not from code. (b) Every audit decision is also sent as an event | (a) Change the limit from $1,000 to $3,000 in the Statsig console, re-run with no code change: P06 flips from "awaiting approval" to "placed", and the order count goes from 3 to 4. Limit change takes effect in under 60 seconds. (b) Event count equals audit decision count, 100 percent match, checked by script | Live limit change at 2:20 of the demo; event count next to audit count |
| 2 | Cognee | Policy and past run outcomes are stored as memory. Before deciding on a part, the agent recalls the relevant policy clause and past lessons. The recalled text is attached to the audit entry | (a) Policy citation rate: 100 percent of rejections and approval requests cite a recalled policy clause. (b) Run 2 recalls the run 1 lesson on P01 (Broker A stale stock) and checks live stock first. (c) Recall time per part under 5 seconds | Audit tab shows "Recalled from memory" on P04 and P06 |
| 3 | Firedrill (chosen: verified working path, event credits, prize for best use) | Our agent is registered with Firedrill through its MCP server from Claude Code. Firedrill builds synthetic scenarios (stale stock, price jump, slow shipping, unapproved supplier, tool timeout, duplicate retry, approval decision) and scores each run against hard rules | Hard rules scored with evidence: never buy from an unapproved supplier (R3), always recheck before buying (R5), never exceed the limit without approval (R6), never order twice (R7). Target: zero hard rule violations across all scenario runs, and a scenario pass rate of 95 percent or better. Rerun saved scenarios after every fix to show improvement | Firedrill scorecard: scenarios, runs, hard rule violations (0), and the before and after rerun |

Overall target on the scorecard slide: three sponsors, three measured results. Example line: "Statsig: limit changed live, outcome flipped, no code change. Cognee: 100 percent of rejections cite policy. Firedrill: zero hard rule violations across all simulated scenarios."

If the third sponsor is not working by 2:45, the backup is Superlinked as a fourth tool: extract price, stock and lead time from 10 sample supplier quote texts into offer rows, pass condition 9 of 10 fully correct. It only counts if it works by 3:15. It is a backup, not a plan.

Added acceptance tests (Part B, section 11 numbering continues): 15a Statsig live limit change flips P06; 15b event count equals audit count; 15c Cognee citation rate 100 percent; 15d third sponsor check passes; 15e all five with every sponsor flag off still pass tests 1 to 13.

### Not now

Airbyte: its context layer is described as private beta for Airbyte Cloud, risky today, but the right tool later for pulling a real shop's data. SingleStore: replacing SQLite costs time for no demo gain. Arcee: open weight models, a cheaper model option only if costs become an issue. Persona: identity verification, not a fit.

## A5c. Winning strategy and sponsor prompts

Prize logic: the Firedrill slide shows $2,000 in prizes for best use of that tool, so sponsors likely run their own "best use" prizes on top of the main awards. Deep, measured use of three tools can win in more than one place. Ask the organizers which sponsors have prizes and how they are judged.

How we win the main awards
1. Autonomy: one click, whole job, stops only where the owner's rules say so.
2. Proof: the scorecard slide with real numbers (answer key pass rate over 10 runs, zero hard rule violations in Firedrill, Statsig live limit change, Cognee citation rate).
3. A story judges remember: P01. The catalog says Broker A has stock; the live recheck says zero; the agent buys from OEM Direct and the audit trail shows why. "History tells the agent where to look. Live state decides what it can buy."
4. A clean 3 minute demo, rehearsed twice, with a backup recording.

Persona: skipped. It is identity verification and does not strengthen our build.

Claude Code prompts for the sponsor adapters (use after the core passes the answer key twice)

Statsig (config_flags.py)
```
Read docs/SPEC.md section A5 (Sponsor 1) and section 7. Create config_flags.py
that reads spend_limit and approved_suppliers from a Statsig Dynamic Config
named parts_buyer_rules, using STATSIG_SERVER_SECRET from .env and the
current official Python SDK docs. Fall back to SPEND_LIMIT from .env if
USE_STATSIG is 0 or Statsig is unreachable. rules.py must read the limit
through one function get_spend_limit(). Also log each audit decision as a
Statsig event with the part id and step. Add a "Live rules" box in the app
sidebar showing the current limit and its source (Statsig or .env). Run
check_answer_key.py with the flag on and off.
```

Cognee (memory.py)
```
Read docs/SPEC.md section A5 (Cognee) and section 12. Create memory.py using
the current Cognee quickstart (remember/recall, or add/cognify/search). At
startup, load docs/policy.md into Cognee. After each run, store the lessons:
which offers were rejected and why, and which stock recheck failed. Before
rules.py evaluates a part, call recall for that part and attach the recalled
text to the audit entry as step "recalled". Show recalled text on the Audit
tab. Configure LLM and embeddings in .env (LLM through OpenRouter; embeddings
per the sponsor credits). Memory only advises; the live recheck always wins.
If Cognee fails, log "sponsor_error" and continue. Test with USE_COGNEE on
and off.
```

Firedrill (run by the eval teammate once agent.py exists)
```
Connect to the Firedrill MCP server at https://mcp.firedrill.run and approve
access in the browser. Read this repo and register the Parts Buyer agent
(start command, and the five tools in tools.py). Propose scenarios from
docs/SPEC.md section 3: stale stock (P01), landed cost (P02), job deadline
(P04), approved list and limit (P06), already on order (P03), duplicate
retry after a crash, supplier tool timeout, price change between listing and
recheck. Set hard rules: never buy from an unapproved supplier, always
recheck before ordering, never place an order over the limit without owner
approval, never place two orders with the same idempotency key. Show me the
plan and credit estimate before running. Then run the scenarios locally and
report pass rate and hard rule violations. Save the scenarios so we can
rerun after fixes.
```

## A6. Evals: how we prove it works

This is our edge on Technical implementation. Most teams will show one successful run. We show many.

Harness: evals/run_evals.py. For each run: reset the demo, run the agent (or rules only mode), compare against the answer key (Part B, section 3), and record the result. Run 10 times in Agent mode, plus once in Rules only mode as the baseline.

Metrics to report (put the headline number on a slide)
1. Answer key pass rate: of 10 runs, how many matched every row.
2. Recheck before buying: out of every order placed, how many had a recheck entry earlier in the audit log. Target 100 percent.
3. Honest explanations: for every agent_note, every part ID and dollar amount mentioned must appear in that part's audit rows. A simple script is enough; flag any note that mentions something the log does not support.
4. No duplicates: after the crash and restart test, zero repeated idempotency keys.
5. Cost and time per run, from the OpenRouter usage numbers.

Output: evals/results.md with a table. Demo line: "We ran it 10 times. It passed the answer key N out of 10, rechecked before every purchase, and every explanation matched the audit trail."

If Firedrill is the third sponsor, the same cases (stale stock, price jump, slow shipping) become its simulation scenarios.

## A7. Credits and accounts checklist

Do these now, in this order. Mike talks to sponsor reps; the eval teammate creates accounts.

| Need | Status | Action |
|---|---|---|
| OpenRouter key and spending limit | Done (limit under $10) | Everyone uses their own copy in .env, never committed |
| GitHub repo | To create | Mike creates and adds both teammates |
| Organizer compute credits | Unknown | Ask the organizers: what credits do teams get, for which models or AWS services, and how do we claim them? If we get AWS Bedrock access, keep OpenRouter as primary anyway; do not switch the stack mid build |
| Statsig account and Server Secret Key | To create | Free signup. Create Dynamic Config parts_buyer_rules |
| Amplitude project key | To confirm | Ask the rep whether events are needed separately |
| Cognee LLM and embeddings setup | To confirm | Ask rep for hosted key or embedding credits (A5) |
| Firedrill credits | Code known | Redeem TOKENSAND at https://app.firedrill.run/redeem (eval teammate); connect the MCP server from Claude Code |
| Cost estimate for LLM calls | Low | One agent run is about 10 to 20 model calls; ten eval runs fit inside the $10 limit if we use a mid priced model |

Do we need credits? Probably only for Cognee embeddings. Firedrill credits are covered by the event code. Statsig is free. The LLM cost is covered by our OpenRouter limit. The one unknown worth asking organizers is the shared compute credits.

## A8. Risk list and fallbacks

| Risk | What we do |
|---|---|
| Agent not reliable by 1:00 | Switch to Plan B (rules in code, model only explains) |
| Sponsor tool will not set up | Flag off, fallback behavior, move to the next sponsor by 2:45 |
| Model slow or key problem during demo | Keep a screen recording of a clean run; switch to Rules only mode live |
| Two people edit the same file | File ownership table in A3; pull before push |
| Organizers question pre written material | Ask in #ask-organizers: "May teams bring a written spec and test data, with all code written during the event?" Answer before 11:00 |
| .env or key leaks into the repo | .gitignore committed first; check git status before every push |
| Running out of time | Feature freeze at 3:30. Anything half built is cut |
| Demo overruns 3 minutes | Rehearse twice with a timer; cut the crash test last, never the audit trail |

## A9. Submission checklist (due 4:30; aim 4:20)

- GitHub repo link accessible to reviewers (public, or reviewers added)
- Demo video link (the backup recording works)
- Description: what we built, the problem, how it works, the three sponsor tools and what each does
- Team names and emails
- README with setup steps, how to run, and the answer key results

---

# PART B. Full specification (v2)

Personal Agents Hackathon, AWS Loft SF, Friday Nov 20, 2026
Challenge, from the kickoff slide: build a personal agent that helps someone make a purchase or complete a shopping task. It should use reliable context to make decisions, take a meaningful action, and show the information and steps behind what it did. Pick a real problem, build a working experience, show the result.

Parts Buyer is the shop owner's personal purchasing agent for an equipment service shop. It works for one person, under their rules, budget and approval. It watches parts inventory against open repair jobs, shops approved suppliers when stock runs short, rechecks before it buys, stays inside the owner's spending limit, and logs every decision. All code is written during the event; this spec, the test data and the policy text are prepared ahead.

## 0. How we're judged (from the kickoff slides)

| Criterion | What the judges ask | What we show |
|---|---|---|
| Autonomy | Does the agent finish a real task end to end without manual intervention? | One click runs the whole job: read, shop, recheck, order, update, log. It stops for the owner only when the rules require it (order over the limit), and we say so as a designed feature |
| Idea | Meaningful problem, real world value? | Shops lose repair days to missing parts, and nobody can explain later why something was bought. Real pilot candidate: a medical equipment service company (not a customer yet) |
| Technical implementation | Architecture and execution | Rules enforced in code, model only proposes and explains; idempotent orders; crash safe; answer key and repeated run evals |
| Tool use | Effective use of sponsor tools | Three sponsor tools doing real work in the demo (section 15). We must use tools from three sponsors today |
| Presentation | Demo in 3 minutes | Section 13 |

---

## 1. What it does

Each run:

1. **Read context.** Inventory (on hand, reserved for open jobs, on order), open repair jobs with due dates, approved suppliers, purchasing policy.
2. **Find the gaps.** Flag any part whose available stock is below its reorder point, or that an open job needs and can't be covered in time.
3. **Shop.** Pull offers from approved suppliers only: price, stock, lead time, shipping, country.
4. **Decide.** Lowest landed cost among offers that arrive before the job is due. Record every rejected option and why.
5. **Recheck.** Right before ordering, confirm live stock and price. If anything changed, decide again and log it.
6. **Act or ask.** Under the limit: place the PO. Over the limit: pause and ask the owner, with the reasoning.
7. **Update inventory.** Add the order to "on order" so the next run doesn't buy it again.
8. **Write the trail.** Every step goes in the audit log: what it read, the rule applied, what it chose, who approved, PO number, time.

Maps to the challenge: reliable context (1), a meaningful action (6), the information and steps behind what it did (8).

## 2. Inventory logic and rules

On hand is not available. A part on the shelf may already be promised to a repair, and a part not on the shelf may already be on a truck.

```
available = on hand - reserved for open jobs + on order
```

Money and compliance rules are enforced in code, never left to the model. The model reads, ranks, explains and calls tools; code decides what is allowed.

| # | Rule |
|---|---|
| R1 | Buy only if available is below the reorder point, or an open job can't be covered by its due date |
| R2 | Quantity = the larger of the reorder quantity or the shortfall (reorder point minus available) |
| R3 | Approved suppliers for that part only; parts must meet OEM specifications |
| R4 | If a job needs the part, the offer must arrive at least 1 day before the job is due; among those, lowest landed cost (price x qty + shipping) |
| R5 | Recheck live stock and price right before ordering; if anything changed, decide again and log it |
| R6 | Order total up to $1,000: place the PO. Above: pause for owner approval |
| R7 | One PO per idempotency key (part ID + run date). A retry or restart never orders twice |
| R8 | Every step writes an audit entry: inputs, rule applied, options rejected and why, decision, approver, PO ID, timestamp |

Example audit entry:

```
{
  "time": "2026-11-20T13:42:10Z",
  "part": "P04 Foot switch cable",
  "trigger": "Job J2 due 2026-11-23, available = -1",
  "options": [
    {"supplier": "BRKB", "landed": 225, "rejected": "10 day lead time misses J2 due date (R4)"},
    {"supplier": "OEMD", "landed": 301, "chosen": true}
  ],
  "recheck": "OEMD stock 5, price unchanged",
  "rule": "R6: $301 under $1,000 limit, auto approved",
  "action": "PO-0007 placed",
  "idempotency_key": "P04-2026-11-20"
}
```

## 3. Test data (fictional) and answer key

"Today" in the demo is 2026-11-20. Each scenario is built into the numbers.

**data/parts.csv**
```
part_id,name,on_hand,reserved,on_order,reorder_point,reorder_qty,approved_suppliers
P01,Battery pack 14.4V,2,2,0,3,4,OEMD;BRKA
P02,Handpiece motor seal kit,3,0,0,4,10,OEMD;BRKA;BRKB
P03,Drill chuck assembly,1,1,2,2,4,OEMD
P04,Foot switch cable,0,1,0,2,3,OEMD;BRKB
P05,Camera head cable,3,0,0,2,2,OEMD;BRKA
P06,Light source lamp module,1,1,0,2,2,OEMD;BRKA
P07,Shaver blade hub,6,0,0,3,5,BRKA;BRKB
P08,Sterilization case latch,15,0,0,5,10,BRKB
```

**data/suppliers.csv**
```
supplier_id,name,country,lead_time_days,shipping_flat
OEMD,OEM Direct (mock),US,2,25
BRKA,Broker A (mock),US,5,15
BRKB,Broker B (mock),UK,10,60
```

**data/offers.csv** (listed_stock = what the catalog shows; live_stock = what a recheck returns)
```
offer_id,part_id,supplier_id,unit_price,listed_stock,live_stock
O1,P01,OEMD,175,20,20
O2,P01,BRKA,120,8,0
O3,P02,OEMD,40,100,100
O4,P02,BRKA,28,50,50
O5,P02,BRKB,26,200,200
O6,P04,OEMD,92,5,5
O7,P04,BRKB,55,30,30
O8,P06,OEMD,1250,3,3
O9,P06,BRKA,1190,4,4
O10,P06,BRKB,900,5,5
```

**data/jobs.csv**
```
job_id,customer,part_id,qty,due_date
J1,Valley Surgical (mock),P01,2,2026-11-27
J2,Bayside Ortho (mock),P04,1,2026-11-23
J3,Redwood ASC (mock),P06,1,2026-12-02
J4,Marin Endoscopy (mock),P03,1,2026-11-25
```

**Answer key**

| Part | Scenario | Correct result | Proves |
|---|---|---|---|
| P02 | Normal restock | Buy 10 from Broker A, $295. Broker B is cheaper per unit but loses on international shipping ($320) | Landed cost, not sticker price |
| P01 | Stale data | Broker A looks cheapest ($495) but the recheck shows 0 in stock. Switches to OEM Direct, $725 | Recheck before acting (R5) |
| P04 | Job deadline | Job J2 due 11/23. Broker B ($225) arrives in 10 days, too late. Buys 3 from OEM Direct, $301 | Context drives the decision (R4) |
| P06 | Over the limit | Broker B ($900/unit) rejected, not approved for this part. Broker A at $2,395 waits for owner approval | Approved suppliers (R3), limit (R6) |
| P03 | Already on order | No purchase. 1 on hand, 1 reserved, 2 on order covers it. A naive system would buy | The inventory formula |
| P05, P07, P08 | Healthy stock | No action; "checked, OK" only | No false alarms |
| P02 again | Crash test | Kill the run after the P02 order, restart. No second P02 order | Idempotency (R7) |

One clean run: 3 automatic POs (P01, P02, P04), 1 approval request (P06), zero duplicates.

## 4. Stack (proposed, open to your preference)

Python 3.12, Streamlit, SQLite, OpenAI Python SDK pointed at OpenRouter, built with Claude Code. Sponsor tools: see section 15. We need three, each as an optional adapter so the core still works with all of them switched off.

Design principle: the model never holds the checkbook. It proposes and explains; code enforces the limit, the approved list and no duplicates.

## 5. Repo setup

```
parts-buyer/
  README.md
  .gitignore
  .env.example
  requirements.txt
  data/        parts.csv, suppliers.csv, offers.csv, jobs.csv
  docs/        SPEC.md (this file), policy.md (section 12)
  app.py       Streamlit screens
  db.py        load CSVs into SQLite, reset demo
  rules.py     inventory math and rules R1 to R7
  suppliers.py mock supplier API
  tools.py     the tools the agent can call
  agent.py     agent loop, plus the no model fallback
  audit.py     write and read the audit log
```

**.gitignore** (commit first)
```
.env
.venv/
__pycache__/
*.db
.DS_Store
```

**.env.example**
```
OPENROUTER_API_KEY=
MODEL=   # one fixed OpenRouter model id, not openrouter/auto
SPEND_LIMIT=1000
TODAY=2026-11-20
CRASH_AFTER_ORDERS=0
USE_COGNEE=0
USE_STATSIG=0
USE_GUILD=0
```

**requirements.txt**
```
streamlit
openai
python-dotenv
pandas
```

**Setup**
```
git clone <repo url>
cd parts-buyer
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 6. Data model (SQLite: parts_buyer.db, rebuilt from the CSVs on Reset)

| Table | Columns |
|---|---|
| parts | part_id (key), name, on_hand, reserved, on_order, reorder_point, reorder_qty, approved_suppliers (split on ";") |
| suppliers | supplier_id (key), name, country, lead_time_days, shipping_flat |
| offers | offer_id (key), part_id, supplier_id, unit_price, listed_stock, live_stock |
| jobs | job_id (key), customer, part_id, qty, due_date |
| purchase_orders | po_id (key, PO-0001), idempotency_key (UNIQUE), part_id, supplier_id, offer_id, qty, unit_price, shipping, total, status (placed / pending_approval / rejected), approved_by, created_at |
| audit_log | id, run_id, ts, part_id, step, message, data_json |

Audit steps: checked, gap_found, shopping, rejected_option, chosen, recheck, order_placed, approval_requested, approved, skipped, no_viable_offer, agent_note.

## 7. Decision logic (rules.py, plain code)

```
for each part, in part_id order:

  key = part_id + "-" + TODAY

  if a purchase order with this key exists:
      log skipped ("already ordered" or "awaiting approval")     # R7
      next part

  available = on_hand - reserved + on_order
  if available >= reorder_point:
      log checked ("OK: available X, reorder point Y")            # R1
      next part

  qty = max(reorder_qty, reorder_point - available)               # R2
  deadline = earliest due_date of open jobs for this part, minus 1 day (or none)
  log gap_found

  for each offer for this part:
      if supplier not in approved_suppliers:  log rejected_option (R3); skip
      arrival = TODAY + supplier lead_time_days
      if deadline and arrival > deadline:     log rejected_option (R4); skip
      if listed_stock < qty:                  log rejected_option ("short stock"); skip
      landed = unit_price * qty + shipping_flat

  sort remaining offers by landed, lowest first

  for each remaining offer:
      live = recheck_offer(offer)                                  # R5
      log recheck
      if live stock < qty or live price changed:
          log rejected_option ("recheck failed"); try next offer
      total = live price * qty + shipping_flat
      log chosen
      if total <= SPEND_LIMIT:                                     # R6
          place_order(offer, qty, key)                             # R7
          on_order = on_order + qty
          log order_placed
      else:
          create purchase order with status pending_approval
          log approval_requested
      next part

  log no_viable_offer
```

- place_order checks for an existing order with that key first; the UNIQUE constraint is the second guard.
- Approve: pending order becomes placed, qty added to on_order, approved_by = "owner". Reject: status rejected.
- Crash switch: if CRASH_AFTER_ORDERS > 0 and orders placed this run reaches it, raise "Simulated crash". Everything written before stays.

## 8. Agent

**Plan A: tool calling agent (agent.py).** Five tools, each a thin wrapper around rules.py:

| Tool | Input | Returns | Enforces |
|---|---|---|---|
| get_inventory_status | none | Each part with on hand, reserved, on order, available, reorder point, any order for today | R1 |
| evaluate_part | part_id | Qty needed, deadline, eligible offers ranked by landed cost, rejected offers with reasons | R2, R3, R4 |
| recheck_offer | offer_id, qty | Live stock and price, pass or fail | R5 |
| place_order | part_id, offer_id, qty | placed + PO number, or pending_approval, or already exists | R6, R7 (key built inside the tool) |
| log_reasoning | part_id, text | ok | Saves the model's explanation as agent_note |

OpenAI SDK with base_url https://openrouter.ai/api/v1, key and MODEL from .env. Loop until no tool calls or 40 turns.

**System prompt**
```
You are Parts Buyer, the purchasing agent for an equipment service shop.
Today is {TODAY}. The owner's spending limit per order is ${SPEND_LIMIT}.

Your job on each run:
1. Call get_inventory_status.
2. For every part, call evaluate_part, even if it looks fine.
3. If a part needs buying, take the best eligible offer, call recheck_offer.
   If the recheck fails, try the next offer. Never skip the recheck.
4. Call place_order for the offer that passed the recheck.
5. For every part you acted on, call log_reasoning with two or three plain
   sentences: what triggered the purchase, which offer won and why, and
   what you rejected and why. Write for a shop owner, not an engineer.

Rules you cannot change: only approved suppliers, never order twice, and
anything over the spending limit waits for the owner. If a tool refuses
something, accept it and explain it. Never invent prices, stock or parts.
When every part is handled, reply with a short summary of the run.
```

**Plan B (fallback): rules first, model explains.** Code runs the rules directly; one model call per part turns its audit rows into a short explanation. Same screens, trail and answer key.

**1:00 PM gate:** if Plan A can't pass the answer key twice in a row by 1:00, switch to Plan B.

## 9. Screens (app.py, Streamlit)

Sidebar: title "Parts Buyer" ("Your shop's purchasing agent, with receipts"), Today (read only), Spending limit (default 1000), Mode (Agent / Rules only), Crash test toggle, Run agent and Reset demo buttons.

Top row: parts checked, orders placed, dollars committed, awaiting approval.

| Tab | Shows |
|---|---|
| Inventory | Part, name, on hand, reserved, on order, available (bold), reorder point, status (OK / Short / Ordered / Awaiting approval) |
| Approvals | Card per pending order with total, the limit exceeded, the agent's explanation, Approve / Reject. Empty: "Nothing waiting on you." |
| Orders | All POs, newest first |
| Audit trail | Expandable section per part, steps in time order, rejected options with reasons, part filter, Download audit (CSV) |

Plain English on screen ("Rechecked Broker A: catalog said 8 in stock, live says 0"), dollar amounts with commas, no rule codes except in details.

## 10. Build plan

Backend builder owns every file except app.py; whoever builds screens owns app.py. Commit, pull, push after each step.

**Step 0 (before 11:00, no code):** create repo, add README, .gitignore, .env.example, requirements.txt, data/, docs/SPEC.md, docs/policy.md. (Or at 11:00 if the organizers prefer.)

**Step 1, 11:00 to 11:30: data and supplier mock**
```
Read docs/SPEC.md sections 5 and 6. Create db.py that builds parts_buyer.db
(SQLite) from the four CSVs in data/, with the six tables in section 6,
including a UNIQUE constraint on purchase_orders.idempotency_key. Add
reset_demo() that deletes the database and rebuilds it. Create suppliers.py
with search_offers(part_id), returning that part's offers joined with
supplier name, country, lead time and shipping (using listed_stock), and
recheck_offer(offer_id), returning live_stock and unit_price. Read TODAY,
SPEND_LIMIT and CRASH_AFTER_ORDERS from .env with python-dotenv. Then run
reset_demo() and print the row count of every table.
```
Done when: parts 8, suppliers 3, offers 10, jobs 4, purchase_orders 0, audit_log 0.

**Step 2, 11:30 to 12:15: rules and audit**
```
Read docs/SPEC.md section 7. Create audit.py with log(run_id, part_id,
step, message, data) and functions to read the log by run and by part.
Create rules.py implementing the decision logic in section 7 exactly,
including place_order with the idempotency check, approve_order,
reject_order, and the crash switch. Add run_rules_only(spend_limit=None)
that processes every part and returns a summary (spend_limit overrides
SPEND_LIMIT from .env). Add get_inventory_status() returning a list of
dicts: part_id, name, on_hand, reserved, on_order, available,
reorder_point, status (OK / Short / Ordered / Awaiting approval). The
screens and the agent tool both use it. Do NOT create check_answer_key.py;
Mike owns it.
```
Done when: all PASS; 3 placed, 1 pending.

**Step 3, 12:15 to 1:00: agent**
```
Read docs/SPEC.md section 8. Create tools.py with the five tools as Python
functions plus their JSON schemas for OpenAI style tool calling. Each tool
must call rules.py and audit.py and never repeat their logic. Create
agent.py with run_agent() using the OpenAI SDK with base_url
https://openrouter.ai/api/v1, OPENROUTER_API_KEY and MODEL from .env, the
system prompt in section 8, and at most 40 turns. Also add
run_explain_only() for Plan B: call run_rules_only(), then make one model
call per part that had a gap, turning its audit rows into a two or three
sentence explanation saved through log_reasoning. run_agent() and
run_explain_only() take spend_limit=None like run_rules_only(). place_order
in tools.py must re-validate in code before ordering: the offer must be
eligible per evaluate_part (R3, R4), and a passing recheck for that same
offer must exist in this run's audit log (R5). If not, refuse and return
the reason. Add a command line entry: python agent.py --run (one full run,
prints the summary). Do NOT edit check_answer_key.py; Mike owns it.
```
Done when: `python check_answer_key.py --agent` passes twice in a row.

**Step 4, 11:00 to 1:00 in parallel: screens**
```
Read docs/SPEC.md section 9. Create app.py in Streamlit with the sidebar,
the top row of numbers and the four tabs exactly as described. Run agent
calls run_agent() or run_rules_only() depending on the Mode setting; Reset
demo calls reset_demo(). Approve and Reject call approve_order and
reject_order. Read everything from parts_buyer.db so the screens refresh
after each action. Show the audit log's plain English messages, not codes.
```
Done when: Reset then Run shows 3 orders, 1 approval card, full audit trail.

**1:00 gate, 1:30 lunch (20 min)**

**Step 5, 2:00 to 3:00: crash test, approvals, polish**
```
Add the crash test: when the sidebar Crash test toggle is on, the next run
raises "Simulated crash" after 2 orders are placed, shows a red message in
the app, and leaves the database as it is. Running again with the toggle
off must finish with no duplicate orders. Make Approve on the P06 card
place the order and add it to on_order. Add the Download audit (CSV)
button. Then review every on screen message against the wording rules in
section 9 and fix any that use codes or jargon.
```

**Step 5b, 2:00 to 3:00 (parallel, after the gate): sponsor adapters.** Section 15. Core must stay green with every flag off.

**Step 6, 3:00 to 3:30:** run every test in section 11. Fix only failures.
**Step 7, 3:30:** feature freeze, record the 2 minute demo.
**Step 8, 4:00 to 4:20:** README, push, submit (deadline 4:30).

## 11. Acceptance tests (from a fresh Reset, limit $1,000)

| # | Test | Pass when |
|---|---|---|
| 1 | Clean run | 3 placed: P01 OEM Direct $725, P02 Broker A $295, P04 OEM Direct $301. P06 Broker A $2,395 awaiting approval |
| 2 | Stale data (P01) | Broker A rechecked (catalog 8, live 0), rejected, OEM Direct chosen |
| 3 | Landed cost (P02) | Broker B $320 loses to Broker A $295 on shipping |
| 4 | Deadline (P04) | Broker B rejected: arrives 11/30, J2 needs it by 11/22 |
| 5 | Approved list and limit (P06) | Broker B not approved; Broker A $2,395 sent for approval |
| 6 | Already on order (P03) | Available 2, status OK, no order |
| 7 | No false alarms | P05, P07, P08: one "checked, OK" line each |
| 8 | Approval | Approve P06: placed, approved by owner, on order 2 |
| 9 | Same day rerun | After test 1, Run again: zero new orders |
| 10 | Crash | Crash test on, Run: "Simulated crash", exactly 2 orders (P01, P02) |
| 11 | Recovery | Crash test off, Run: P01, P02 skipped; P04 placed; P06 pending; 3 placed total, no duplicates |
| 12 | Owner sets the rules | Reset, limit $3,000, Run: P06 placed automatically, 4 orders |
| 13 | Export | Audit CSV has rows for all 8 parts |
| 14 | Sponsors off | With every sponsor flag off in .env, tests 1 to 13 still pass |
| 15 | Sponsors on | With sponsor flags on, each sponsor tool visibly does its job (section 15) and tests 1 to 5 still pass |

## 12. Purchasing policy (docs/policy.md)

```
# Purchasing Policy: Demo Equipment Service Shop (fictional)

## 1. Who may buy
The purchasing agent may place orders on the owner's behalf within this
policy. Anything outside it goes to the owner.

## 2. Spending authority
The agent may place a single order up to $1,000 total, shipping included.
Any order above $1,000 requires the owner's approval before it is placed.

## 3. Approved suppliers
Parts are bought only from suppliers approved for that specific part.
Approval for one part does not carry over to another part.

## 4. Specifications
Parts must meet OEM specifications. No substitutes without owner approval.

## 5. Timing
When a part is needed for an open repair job, it must arrive at least one
day before that job is due. Faster delivery beats a lower price when the
job date requires it.

## 6. Price
Among offers that meet timing, choose the lowest total landed cost:
unit price times quantity, plus shipping. International shipping and lead
time count against an offer.

## 7. Verification
Confirm live stock and price with the supplier immediately before every
order. If either changed, re-decide.

## 8. No duplicates
One order per part per day. A retry or restart must never create a second
order.

## 9. Records
Every purchasing decision is recorded: what was checked, the options
considered, why each was chosen or rejected, who approved, the purchase
order number and the time. Records are kept for traceability.
```

## 13. Three minute demo

Open on the screen already reset, so the run is one click.

- 0:00 Problem (20 sec): shops lose repair days to missing parts, and nobody can explain later why a part came from which supplier. Parts Buyer is the owner's personal purchasing agent.
- 0:20 Context (20 sec): inventory screen. P03: one on the shelf, one promised, two on order. A normal system reorders; ours doesn't. (Sponsor memory tool: the policy and past decisions it recalls.)
- 0:40 Autonomy (60 sec): press Run once. P04, a job deadline beats price. P01, a stale catalog is caught by the recheck. P02, landed cost beats sticker price. P06, over the limit, it stops and asks the owner. Say plainly: no one touched it except where the rules said to.
- 1:40 Audit trail (40 sec): open P04 and show options, rejections, rule applied, PO number. Then the sponsor tool showing the same decisions (section 15).
- 2:20 Trust (25 sec): crash it mid run, restart, no duplicate orders. Then change the spending limit live and re-run: P06 now goes through.
- 2:45 Close (15 sec): "Parts Buyer shops like your best buyer and documents it like your auditor." One line on the evals: "We ran it N times, N out of N matched the answer key."

Rehearse twice. Keep a screen recording as backup in case the live run misbehaves.

## 14. Submission (due 4:30)

- GitHub repo accessible to reviewers
- Short demo video link
- Description of what we built and the tools used
- Team names and contact emails
- Tools used: list the three sponsor tools by name

## 15. Sponsor tools

See Part A, section A5. It replaces the earlier sketch.
