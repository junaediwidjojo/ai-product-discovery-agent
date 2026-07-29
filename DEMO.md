# AI Product Discovery Agent - Demo Script

Snowflake CoCo CLI Hackathon | Category: AI-Native Data Application

## One-line pitch
A Product Manager mediator that turns a plain business request into an evidence-grounded
recommendation, PRD, wireframe, and engineering tasks - reasoning across enterprise DATA + CODE +
DOCS + COMMUNITY, entirely on Snowflake-native services, built and orchestrated with CoCo CLI.

## Why it scores (map to judging criteria)
- Real-world relevance: business <-> engineering translation is a universal, expensive gap.
- Technical execution: native Cortex Agent + Cortex Analyst + Cortex Search + AISQL + stored-proc
  tools + a normalized knowledge graph. Not a chatbot, not basic RAG.
- Snowflake-native: everything runs in Snowflake; the app is Streamlit-in-Snowflake.
- AI reasoning: a transparent Opportunity Score (impact x demand / effort) + human-in-the-loop.
- Completeness: question -> insight -> recommendation -> ACTION (tasks persisted).
- Demo quality: one prompt visibly expands into a full discovery brief.
- Originality: cross-source knowledge graph + evidence ledger with a citation for every claim.

## Live demo (3 minutes)
1. Open Snowsight -> Projects -> Streamlit -> DISCOVERY_WORKBENCH.
2. Type: "I want refunds".
3. Watch it expand:
   - Intent -> topic=refund.
   - Impact (Cortex Analyst / COMMERCE_SV): 12% return rate on 1,200 orders; top reason
     "Size too small" ($8.3K). [source shown]
   - Evidence (Cortex Search / KNOWLEDGE_SEARCH), each cited:
     - CODE: apps/storefront/src/modules/order/components/help/index.tsx:13 - "Returns & Exchanges"
       is a static /contact link; no self-serve returns.
     - DOCS: "Create Order Returns in the Storefront" - how it SHOULD work.
     - COMMUNITY: "Refund workflow can report success after partial refund failures" + 5 more.
   - Clarifying question (human-in-the-loop): "Self-serve for all reasons, or sizing-first (top driver)?"
   - Opportunity Score: ~8/10 with impact/demand/effort breakdown.
   - Existing vs Proposed wireframe.
   - Grounded PRD (expandable).
   - 7 engineering tasks -> click "Approve & create tasks".
4. Close: "Every number and claim has a citation, and it ended by creating real tickets."

## Architecture talking points
- Two data planes: operational (MOCK) vs knowledge graph (KNOWLEDGE, normalized supertype/subtype
  + graph edges + provenance). DB schema itself is cataloged as knowledge (DB_TABLE/DB_COLUMN).
- Native Cortex Agent PRODUCT_DISCOVERY_AGENT (Analyst + Search tools) is the reusable reasoning engine.
- Action tools are stored procedures = reusable agent tools (score, PRD, wireframe, tasks).
- CoCo CLI built all of it via its skills (semantic-view, search-optimization, cortex-agent), and the
  product-discovery skill encodes/orchestrates the workflow.
- Robustness: Resource Monitor hard cap; graceful "insufficient data"; standardized on mistral-large2.

## Object inventory
- PM_MEDIATOR.MOCK: 68 commerce tables + synthesized refund domain; COMMERCE_SV semantic view;
  3 specialized Cortex Search services; DTC_STARTER_REPO git object.
- PM_MEDIATOR.KNOWLEDGE: normalized model + unified KNOWLEDGE_SEARCH + REFRESH_GIT task.
- PM_MEDIATOR.DISCOVERY: SESSION/EVIDENCE/IMPACT/RECOMMENDATION/PRD/TASK, @ARTIFACTS stage,
  4 action procedures, PRODUCT_DISCOVERY_AGENT, DISCOVERY_WORKBENCH app.

## Extensibility (documented, not faked)
GitLab MRs, Jira, APIs (OpenAPI), support tickets map cleanly into the KNOWLEDGE model as new
artifact_types + subtype tables + a connector - no schema redesign.
