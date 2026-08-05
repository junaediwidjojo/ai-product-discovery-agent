# Nomy Explores — Demo Script (≈3 minutes)

Snowflake CoCo CLI Hackathon · Category: AI-Native Data Application

## Opening line
> Teams don't usually fail because they can't write a PRD. They fail because they write a precise PRD for the *wrong* problem. Nomy interviews the stakeholder, reads the current code, checks the business data, and only then recommends what to build.

## Scenario
> "Customers contact support because they can't request a return from their order page."

(Focus chips: **Order Journey**, **Returns & Refunds**.)

## Run sheet

| ~Time | Show | What proves the point |
|------:|------|-----------------------|
| 0:00–0:20 | Product overview + focus chips; type the request; **Start discovery** | `BUILD_OVERVIEW` / `BUILD_TAXONOMY` (repo-derived) |
| 0:20–1:20 | Answer **3** questions. Point at the **"From your data"** line (return rate + top reason) and the **Enterprise knowledge** panel showing **code** (the order-help page only links to /contact) | `DATA_SIGNALS` (live metrics) + `RETRIEVE_EVIDENCE` (code-blended) + `DISCOVERY_NEXT` |
| 1:20–1:35 | Coverage bars + **Discovery Confidence** rise → click **"I have enough → summary"** | `DISCOVERY_NEXT` orchestration |
| 1:35–2:05 | **Discovery Summary** brief → **Send to PM** → **Approve** | `DISCOVERY_ARTIFACTS` + approval gate |
| 2:05–2:45 | **RICE** (with bands) → **Generate PRD** (13 sections, Download .md) → **Generate tickets** → Jira cards | `SCORE_RICE` + `GENERATE_PRD` + `CREATE_TASKS` |
| 2:45–3:00 | Close (see below) | — |

## Closing line
> A generic AI assistant knows how product discovery *should* work. Nomy knows how *this* company's product currently works, what its data says, and what's still unknown.

## Two capabilities to highlight if time allows (10–20s)
- **Already-built detection:** type "add a voucher field at checkout" → Nomy sees the promotion-code input already exists in the code and pivots to *"what do you want to improve — discoverability, eligibility, validation?"* (investigate the gap, not a blank rebuild).
- **Honest data gaps:** a checkout-abandonment question → Nomy states the dataset has no cart/abandonment tables rather than inventing a number.

## Reliability tips (for the recording)
- Do one full dry run first so the warehouse is warm and the SiS package cache is built (avoids a slow first load). `AUTO_SUSPEND` is 300s so mid-demo pauses won't cold-start.
- Have the 3 answers ready (use the quick-answer chips); stop at 3 questions via "I have enough".
- **Record with a backup**: keep a screen recording of a known-good run in case a live Cortex call is slow during the session.

## Object inventory (all reproducible — see `sql/`)
- `MOCK`: Medusa commerce tables (loaded by scripts) + `COMMERCE_SV` semantic view; `DTC_STARTER_REPO` Git object.
- `KNOWLEDGE`: normalized graph (code/docs/issues) + `KNOWLEDGE_SEARCH` Cortex Search; `REFRESH_GIT` task.
- `DISCOVERY`: the agent skills, session/artifact tables, `@APP_STAGE`, `PRODUCT_DISCOVERY_AGENT`, `DISCOVERY_WORKBENCH` app.
