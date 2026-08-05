-- PRODUCT_DISCOVERY_AGENT native Cortex Agent (tools: query_commerce/COMMERCE_SV, search_knowledge/KNOWLEDGE_SEARCH).

create or replace agent PM_MEDIATOR.DISCOVERY.PRODUCT_DISCOVERY_AGENT
from specification
$$
models:
  orchestration: "auto"
instructions:
  response: "Be concise and evidence-first; present numbers with sources and reference\
    \ retrieved snippets."
  orchestration: "You are an AI Product Discovery agent acting as a PM mediator. For\
    \ a feature request: (1) quantify impact with query_commerce, (2) gather cited\
    \ evidence with search_knowledge (filter by ARTIFACT_TYPE: code_file/doc_page/issue/db_table),\
    \ (3) call score_opportunity with the concept id (return/refund/exchange/order/payment/fulfillment/checkout/product/inventory)\
    \ to get a transparent opportunity score. Always cite evidence (file:line, doc\
    \ title, issue URL, metrics). Ask ONE clarifying question if ambiguous. Never\
    \ invent facts."
tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "query_commerce"
      description: "Quantify orders, returns, refunds, reasons from COMMERCE_SV. Use\
        \ for how-many/rate/$-impact/top-reason questions."
  - tool_spec:
      type: "cortex_search"
      name: "search_knowledge"
      description: "Search enterprise knowledge (code, docs, community, db schema).\
        \ Filter by ARTIFACT_TYPE."
  - tool_spec:
      type: "generic"
      name: "score_opportunity"
      description: "Compute a transparent opportunity score (impact x demand / effort)\
        \ for a concept id such as refund, return, product, checkout."
      input_schema:
        type: "object"
        properties:
          topic:
            type: "string"
            description: "concept id, e.g. refund"
        required:
          - "topic"
tool_resources:
  query_commerce:
    execution_environment:
      type: "warehouse"
      warehouse: "PM_MEDIATOR_WH"
      query_timeout: 299
    semantic_view: "PM_MEDIATOR.MOCK.COMMERCE_SV"
  search_knowledge:
    execution_environment:
      type: "warehouse"
      warehouse: "PM_MEDIATOR_WH"
      query_timeout: 299
    search_service: "PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH"
  score_opportunity:
    type: "procedure"
    identifier: "PM_MEDIATOR.DISCOVERY.SCORE_OPPORTUNITY"
    execution_environment:
      type: "warehouse"
      warehouse: "PM_MEDIATOR_WH"
      query_timeout: 300
$$;