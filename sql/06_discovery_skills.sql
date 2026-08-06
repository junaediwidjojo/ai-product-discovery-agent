-- DISCOVERY: agent-skill procedures/functions, tables, stage, Streamlit object.
-- (full export of the PM_MEDIATOR.DISCOVERY schema)

create or replace schema PM_MEDIATOR.DISCOVERY;

create or replace TABLE PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT (
	SESSION_ID VARCHAR(16777216),
	ARTIFACT_TYPE VARCHAR(16777216),
	CONTENT VARCHAR(16777216),
	UPDATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP()
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (
	SESSION_ID VARCHAR(16777216) NOT NULL,
	ASK_TEXT VARCHAR(16777216),
	CREATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP(),
	STATUS VARCHAR(16777216),
	OPPORTUNITY_SCORE FLOAT,
	CONFIDENCE VARCHAR(16777216),
	CLARIFYING_QUESTION VARCHAR(16777216),
	CLARIFYING_ANSWER VARCHAR(16777216),
	UPDATED_AT TIMESTAMP_TZ(9),
	primary key (SESSION_ID)
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN (
	SESSION_ID VARCHAR(16777216),
	SEQ NUMBER(38,0),
	ROLE VARCHAR(16777216),
	QUESTION VARCHAR(16777216),
	ANSWER VARCHAR(16777216),
	CREATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP()
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.EVIDENCE (
	EVIDENCE_ID VARCHAR(16777216) NOT NULL,
	SESSION_ID VARCHAR(16777216),
	SOURCE_TYPE VARCHAR(16777216),
	SNIPPET VARCHAR(16777216),
	CITATION VARCHAR(16777216),
	URL VARCHAR(16777216),
	SCORE FLOAT,
	CREATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP(),
	primary key (EVIDENCE_ID)
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.IMPACT (
	IMPACT_ID VARCHAR(16777216) NOT NULL,
	SESSION_ID VARCHAR(16777216),
	METRIC_NAME VARCHAR(16777216),
	METRIC_VALUE FLOAT,
	UNIT VARCHAR(16777216),
	SQL_USED VARCHAR(16777216),
	primary key (IMPACT_ID)
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.PRD (
	SESSION_ID VARCHAR(16777216) NOT NULL,
	MARKDOWN VARCHAR(16777216),
	ARTIFACT_PATH VARCHAR(16777216),
	CREATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP(),
	primary key (SESSION_ID)
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.PRODUCT_PROFILE (
	OVERVIEW VARCHAR(16777216),
	BUILT_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP()
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.RECOMMENDATION (
	SESSION_ID VARCHAR(16777216) NOT NULL,
	SUMMARY VARCHAR(16777216),
	RATIONALE VARCHAR(16777216),
	IMPACT_COMPONENT FLOAT,
	DEMAND_COMPONENT FLOAT,
	EFFORT_COMPONENT FLOAT,
	OPPORTUNITY_SCORE FLOAT,
	primary key (SESSION_ID)
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.REPO_TAXONOMY (
	TAXONOMY_JSON VARCHAR(16777216),
	BUILT_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP()
);
create or replace TABLE PM_MEDIATOR.DISCOVERY.TASK (
	TASK_ID VARCHAR(16777216) NOT NULL,
	SESSION_ID VARCHAR(16777216),
	TASK_KEY VARCHAR(16777216),
	TITLE VARCHAR(16777216),
	DESCRIPTION VARCHAR(16777216),
	AREA VARCHAR(16777216),
	ESTIMATE VARCHAR(16777216),
	STATUS VARCHAR(16777216) DEFAULT 'proposed',
	CREATED_AT TIMESTAMP_TZ(9) DEFAULT CURRENT_TIMESTAMP(),
	TYPE VARCHAR(16777216),
	PRIORITY VARCHAR(16777216),
	primary key (TASK_ID)
);
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.BUILD_OVERVIEW()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE inv STRING; part STRING; scale STRING; prompt STRING; raw STRING;
BEGIN
  SELECT ''Storefront modules: '' || COALESCE(LISTAGG(DISTINCT m, '', ''), '''') INTO :inv
    FROM (SELECT REGEXP_SUBSTR(PATH, ''modules/([^/]+)'', 1, 1, ''e'', 1) m FROM PM_MEDIATOR.KNOWLEDGE.CODE_FILE) WHERE m IS NOT NULL;
  SELECT ''. Business concepts: '' || LISTAGG(NAME, '', '') INTO :part FROM PM_MEDIATOR.KNOWLEDGE.CONCEPT;
  inv := :inv || :part;
  scale := ''Catalog '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT) || '' products across ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_CATEGORY) || '' categories; ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS) || '' orders from ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.CUSTOMER) || '' customers; sells across ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.REGION) || '' regions and ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.SALES_CHANNEL) || '' sales channels.'';
  prompt := ''You are briefing a stakeholder who is about to start a product discovery session. ''
    || ''Write ONE neutral, descriptive paragraph (3-4 sentences, plain business language, no bullet points or headings) explaining WHAT this product is and the main capability areas it covers, so they understand the product before picking a topic. ''
    || ''Describe the domain (an e-commerce storefront) and the areas it spans based on the modules/concepts, and cite 2-3 scale figures. ''
    || ''IMPORTANT: Stay purely descriptive. Do NOT single out returns or refunds, do NOT claim any current initiative, priority, problem, or "what we are working on". No recommendations.\\n''
    || ''MODULES/CONCEPTS: '' || :inv || ''\\n''
    || ''SCALE FIGURES: '' || :scale || ''\\n''
    || ''Reply with the paragraph text only.'';
  raw := TRIM((SELECT AI_COMPLETE(''mistral-large2'', :prompt)));
  DELETE FROM PM_MEDIATOR.DISCOVERY.PRODUCT_PROFILE;
  INSERT INTO PM_MEDIATOR.DISCOVERY.PRODUCT_PROFILE (OVERVIEW) VALUES (:raw);
  RETURN :raw;
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.BUILD_TAXONOMY()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE inv STRING; part STRING; raw STRING; cleaned STRING; prompt STRING;
BEGIN
  SELECT ''Storefront modules: '' || COALESCE(LISTAGG(DISTINCT m, '', ''), '''') INTO :inv
    FROM (SELECT REGEXP_SUBSTR(PATH, ''modules/([^/]+)'', 1, 1, ''e'', 1) m FROM PM_MEDIATOR.KNOWLEDGE.CODE_FILE) WHERE m IS NOT NULL;
  SELECT ''. Data domains: '' || COALESCE(LISTAGG(DISTINCT d, '', ''), '''') INTO :part
    FROM (SELECT REGEXP_SUBSTR(PATH, ''lib/data/([^/.]+)'', 1, 1, ''e'', 1) d FROM PM_MEDIATOR.KNOWLEDGE.CODE_FILE) WHERE d IS NOT NULL;
  inv := :inv || :part;
  SELECT ''. Business concepts: '' || LISTAGG(NAME, '', '') INTO :part FROM PM_MEDIATOR.KNOWLEDGE.CONCEPT;
  inv := :inv || :part;
  SELECT ''. Documentation topics: '' || LISTAGG(t, ''; '') INTO :part
    FROM (SELECT DISTINCT SECTION_PATH t FROM PM_MEDIATOR.KNOWLEDGE.DOC_PAGE WHERE SECTION_PATH IS NOT NULL LIMIT 40);
  inv := :inv || :part;
  prompt := ''You are a product strategist. Inspect this e-commerce codebase inventory and identify the 10 most important END-TO-END BUSINESS AREAS / USER JOURNEYS that a business stakeholder would want to improve. '' ||
    ''Use high-level, business-outcome names a non-technical person understands (e.g. "Order Journey", "Checkout & Payment", "Returns & Refunds", "Product Discovery", "Customer Accounts", "Fulfillment & Shipping", "Promotions & Marketing", "Admin Operations", "Internationalization", "Notifications & Messaging"). '' ||
    ''NOT low-level technical items. INVENTORY: '' || :inv || ''\\n'' ||
    ''Reply ONLY compact JSON, no prose, no code fences: {"topics":[{"name":"...","desc":"short one-line business description"}]}. EXACTLY 10 topics, ordered by how prominent they are in this repo.'';
  raw := (SELECT AI_COMPLETE(''mistral-large2'', :prompt));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  DELETE FROM PM_MEDIATOR.DISCOVERY.REPO_TAXONOMY;
  INSERT INTO PM_MEDIATOR.DISCOVERY.REPO_TAXONOMY (TAXONOMY_JSON) VALUES (:cleaned);
  RETURN TRY_PARSE_JSON(:cleaned);
END';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.CLARIFY_NEED("P_ASK" VARCHAR, "P_TOPIC" VARCHAR, "P_CONTEXT" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE raw STRING; cleaned STRING;
BEGIN
  raw := (SELECT AI_COMPLETE(''mistral-large2'',
    ''You are a PM gathering requirements. Request: '' || :P_ASK || '' (topic='' || :P_TOPIC ||
    ''). Context: '' || :P_CONTEXT ||
    ''. If ONE clarifying question would materially scope the solution, reply JSON {"clarify":true,"question":"...","options":["...","...","..."]}. Otherwise reply {"clarify":false}. Reply ONLY JSON.''));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  RETURN TRY_PARSE_JSON(:cleaned);
END';
CREATE OR REPLACE FUNCTION PM_MEDIATOR.DISCOVERY.CONTRADICTION_HINT("P_TEXT" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS '
  CASE
    WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(daily|every day|multiple times a day|several times a day|hourly).*''
     AND REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(fewer than|less than|only a few|a handful|once a month|a few times a month|a few per month|per month|monthly|rarely|seldom).*''
      THEN ''Frequency mismatch: one answer implies high frequency (e.g. daily) while another implies low frequency (e.g. a few per month). Which is accurate?''
    WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(all customers|every customer|all users|everyone).*''
     AND REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(just one|only one|a single|one specific|one enterprise|a specific|single) (customer|client|account|user|enterprise).*''
      THEN ''Scope mismatch: one answer said all customers while another pointed to a single/specific customer. Is this for everyone or one segment?''
    WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(fully automated|fully automatic|no manual|zero touch|completely automated).*''
     AND REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(manually approved|manual approval|approved by hand|approved manually|manually by|approve.{0,15}manually).*''
     AND NOT REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(from manual|instead of manual|replace manual|rather than manual|move to|migrate to|transition to|want to automate|plan to automate|currently manual|today.{0,25}manual).*''
      THEN ''Process mismatch: one answer said fully automated while another said manually approved. Which is the target state?''
    ELSE ''''
  END
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.CREATE_TASKS("P_SESSION" VARCHAR, "P_PRD" VARCHAR)
RETURNS NUMBER(38,0)
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE raw STRING; cleaned STRING; prompt STRING; n INT;
BEGIN
  prompt := ''From the PRD below, produce ONLY a JSON array of 4-7 engineering tickets a team could drop into Jira. ''
    || ''Each item: {"title": short imperative summary, "description": 1-2 actionable sentences, ''
    || ''"type": one of [Story,Task,Bug,Spike], "area": one of [frontend,backend,data,qa], ''
    || ''"priority": one of [High,Medium,Low], "estimate": one of [1,2,3,5,8] (story points)}. ''
    || ''Order by priority (High first).\\\\n\\\\nPRD:\\\\n'' || :P_PRD;
  raw := (SELECT AI_COMPLETE(''mistral-large2'', :prompt));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\[.*\\\\]'', 1, 1, ''s'');
  DELETE FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID = :P_SESSION;
  INSERT INTO PM_MEDIATOR.DISCOVERY.TASK (TASK_ID, SESSION_ID, TASK_KEY, TITLE, DESCRIPTION, TYPE, AREA, PRIORITY, ESTIMATE, STATUS)
  SELECT UUID_STRING(), :P_SESSION, ''NOMY-'' || (100 + f.INDEX),
         f.value:title::string, f.value:description::string, f.value:type::string,
         f.value:area::string, f.value:priority::string, f.value:estimate::string, ''To Do''
  FROM LATERAL FLATTEN(input => TRY_PARSE_JSON(:cleaned)) f;
  SELECT COUNT(*) INTO :n FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID = :P_SESSION;
  RETURN :n;
END;
';
CREATE OR REPLACE FUNCTION PM_MEDIATOR.DISCOVERY.DATA_SIGNALS("P_TEXT" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS '
CASE
  WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(refund|return|exchange|rma).*'' THEN
    ''Returns & refunds: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK."RETURN") || '' returns (''
    || (SELECT ROUND(100.0*(SELECT COUNT(*) FROM PM_MEDIATOR.MOCK."RETURN")/NULLIF((SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS),0))) || ''% of orders); avg ''
    || COALESCE((SELECT TO_VARCHAR(ROUND(AVG(DATEDIFF(''day'',REQUESTED_AT,RECEIVED_AT)),1)) FROM PM_MEDIATOR.MOCK."RETURN" WHERE RECEIVED_AT IS NOT NULL AND REQUESTED_AT IS NOT NULL),''?'') || '' days to process; top reasons: ''
    || COALESCE((SELECT LISTAGG(lbl||'' (''||c||'')'', '', '') FROM (SELECT COALESCE(rr.LABEL,rr.VALUE,''unknown'') lbl, COUNT(*) c FROM PM_MEDIATOR.MOCK.RETURN_ITEM ri LEFT JOIN PM_MEDIATOR.MOCK.RETURN_REASON rr ON ri.REASON_ID=rr.ID GROUP BY 1 ORDER BY c DESC LIMIT 3)),''n/a'')
    || ''; refunds '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.REFUND) || '' totaling $'' || (SELECT ROUND(SUM(AMOUNT)) FROM PM_MEDIATOR.MOCK.REFUND) || ''.''
  WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(account|username|login|log in|sign in|sign-up|signup|register|profile|password|email address).*'' THEN
    ''Customer accounts: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.CUSTOMER) || '' customers; ''
    || (SELECT COUNT(DISTINCT CUSTOMER_ID) FROM PM_MEDIATOR.MOCK.ORDERS) || '' have placed orders; ''
    || (SELECT COUNT(*) FROM (SELECT CUSTOMER_ID FROM PM_MEDIATOR.MOCK.ORDERS GROUP BY CUSTOMER_ID HAVING COUNT(*)>1)) || '' are repeat buyers; ''
    || (SELECT COUNT(DISTINCT CUSTOMER_ID) FROM PM_MEDIATOR.MOCK.CUSTOMER_ADDRESS) || '' have a saved address.''
  WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(product|catalog|browse|search|variant|size|collection|inventory|stock|assortment|sku).*'' THEN
    ''Catalog: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT) || '' products across ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_CATEGORY) || '' categories, ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_VARIANT) || '' variants (avg ''
    || (SELECT ROUND((SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_VARIANT)/NULLIF((SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT),0),1)) || '' per product); ''
    || (SELECT COUNT(*) FROM (SELECT PRODUCT_ID FROM PM_MEDIATOR.MOCK.PRODUCT_VARIANT GROUP BY PRODUCT_ID HAVING COUNT(*)=1)) || '' products have only 1 variant; top categories: ''
    || COALESCE((SELECT LISTAGG(nm||'' (''||c||'')'', '', '') FROM (SELECT pc.NAME nm, COUNT(*) c FROM PM_MEDIATOR.MOCK.PRODUCT_CATEGORY_PRODUCT pcp JOIN PM_MEDIATOR.MOCK.PRODUCT_CATEGORY pc ON pc.ID=pcp.PRODUCT_CATEGORY_ID GROUP BY pc.NAME ORDER BY c DESC LIMIT 3)),''n/a'')
    || ''; typical item price $'' || (SELECT ROUND(AVG(UNIT_PRICE)) FROM PM_MEDIATOR.MOCK.ORDER_LINE_ITEM WHERE UNIT_PRICE IS NOT NULL) || ''.''
  WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(checkout|cart|payment|pay|coupon|promo|discount).*'' THEN
    ''Orders & checkout: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS) || '' orders (completed ''
    || (SELECT COUNT_IF(STATUS=''completed'') FROM PM_MEDIATOR.MOCK.ORDERS) || '', pending ''
    || (SELECT COUNT_IF(STATUS=''pending'') FROM PM_MEDIATOR.MOCK.ORDERS) || '', requires_action ''
    || (SELECT COUNT_IF(STATUS=''requires_action'') FROM PM_MEDIATOR.MOCK.ORDERS) || '', canceled ''
    || (SELECT COUNT_IF(STATUS=''canceled'') FROM PM_MEDIATOR.MOCK.ORDERS) || ''); typical item price $''
    || (SELECT ROUND(AVG(UNIT_PRICE)) FROM PM_MEDIATOR.MOCK.ORDER_LINE_ITEM WHERE UNIT_PRICE IS NOT NULL) || ''. ''
    || ''DATA GAP: carts, checkout sessions, coupons/discounts and cart-abandonment are NOT captured in the current dataset (no cart/promotion tables), so abandonment or coupon-usage rates cannot be measured from data.''
  WHEN REGEXP_REPLACE(LOWER(COALESCE(P_TEXT,'''')),''[[:space:]]+'','' '') RLIKE ''.*(fulfil|ship|deliver|track|order status|dispatch|logistic).*'' THEN
    ''Fulfillment: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS) || '' orders; ''
    || (SELECT COUNT_IF(STATUS=''pending'') FROM PM_MEDIATOR.MOCK.ORDERS) || '' pending, ''
    || (SELECT COUNT_IF(STATUS=''requires_action'') FROM PM_MEDIATOR.MOCK.ORDERS) || '' require action, ''
    || (SELECT COUNT_IF(STATUS=''canceled'') FROM PM_MEDIATOR.MOCK.ORDERS) || '' canceled; ''
    || (SELECT COUNT_IF(STATUS<>''completed'') FROM PM_MEDIATOR.MOCK.ORDERS) || '' orders not yet completed.''
  ELSE
    ''Store scale: '' || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS) || '' orders from ''
    || (SELECT COUNT(DISTINCT CUSTOMER_ID) FROM PM_MEDIATOR.MOCK.ORDERS) || '' customers; ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT) || '' products across ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_CATEGORY) || '' categories; ''
    || (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.PRODUCT_VARIANT) || '' variants.''
END
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACTS("P_TRANSCRIPT" VARCHAR, "P_EVIDENCE" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE raw STRING; cleaned STRING; prompt STRING;
BEGIN
  prompt := ''You are a Senior Product Manager. From the discovery transcript and enterprise knowledge below, produce a PM-ready business understanding (NOT a technical spec). '' ||
    ''Base everything on what was actually said; mark gaps as open_questions rather than inventing.\\n\\n'' ||
    ''TRANSCRIPT:\\n'' || :P_TRANSCRIPT || ''\\n\\nENTERPRISE KNOWLEDGE:\\n'' || :P_EVIDENCE || ''\\n\\n'' ||
    ''Reply ONLY compact JSON, no prose, no code fences: '' ||
    ''{"problem_statement":"...","business_goal":"...","stakeholders":["..."],"personas":["..."],'' ||
    ''"current_workflow":"...","pain_points":["..."],"success_metrics":["..."],"assumptions":["..."],'' ||
    ''"constraints":["..."],"risks":["..."],"open_questions":["..."],"scope":["..."],"out_of_scope":["..."]}'';
  raw := (SELECT AI_COMPLETE(''mistral-large2'', :prompt));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  RETURN TRY_PARSE_JSON(:cleaned);
END';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT("P_TRANSCRIPT" VARCHAR, "P_EVIDENCE" VARCHAR, "P_ASKED" NUMBER(38,0))
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE raw STRING; cleaned STRING; prompt STRING; sig STRING; mdl STRING; hint STRING; res VARIANT;
BEGIN
  mdl := (SELECT PM_MEDIATOR.DISCOVERY.MODEL());
  sig := ''n/a'';
  BEGIN sig := (SELECT PM_MEDIATOR.DISCOVERY.DATA_SIGNALS(:P_TRANSCRIPT)); EXCEPTION WHEN OTHER THEN sig := ''n/a''; END;
  hint := (SELECT PM_MEDIATOR.DISCOVERY.CONTRADICTION_HINT(:P_TRANSCRIPT));
  prompt := ''You are a Senior PM running product discovery. Understand the real PROBLEM (goal, users, current workflow, frequency, success metrics, constraints, assumptions, alternatives); do not take the request at face value.\\n''
    || ''TRANSCRIPT:\\n'' || :P_TRANSCRIPT || ''\\n''
    || ''CODE/DOCS (real, cited):\\n'' || :P_EVIDENCE || ''\\n''
    || ''DATA SIGNALS (real, topic-scoped, never empty):\\n'' || :sig || ''\\n''
    || ''Questions asked: '' || TO_VARCHAR(:P_ASKED) || (CASE WHEN :hint <> '''' THEN ''\\nCONTRADICTION DETECTED: '' || :hint ELSE '''' END) || ''.\\n''
    || ''RULES:\\n''
    || ''1) EXISTING-CAPABILITY / GAP: if the requested capability already exists in the code, set already_exists=true and existing_note=one line citing it. Code existing does NOT mean the problem is solved. Make the question probe the GAP - discoverability, correctness/validation, workflow fit, eligibility rules, or adoption. working_problem = closing the specific gap. Do NOT tell the user to stop.\\n''
    || ''2) Infer current_workflow from the code; never ask the stakeholder how the system works.\\n''
    || ''3) DATA: data_insight MUST include at least one concrete figure from DATA SIGNALS EVERY turn (never blank, never invent numbers); weave a number into the question when natural; never mention returns/refunds unless the topic is returns/refunds/exchanges. When DATA SIGNALS carries a relevant "DATA GAP", ALSO state plainly that the metric cannot be measured from current data while STILL keeping a concrete number.\\n''
    || ''4) Do not ask for counts/rates the data can answer; ask only goals, qualitative pain, priorities, constraints.\\n''
    || ''5) Score each of the 8 coverage dims 0-100 from transcript+code+data; confidence = rounded average; stop=true only if confidence>=78 or asked>=8.\\n''
    || ''6) Ask ONE new question on the lowest-covered dimension; never repeat or reword an answered question.\\n''
    || ''7) Accept a proposed spec without judgement; steer toward the underlying problem.\\n''
    || ''8) adjustment.needed=true ONLY for a genuine contradiction (if CONTRADICTION DETECTED above, set it true and reconcile in the note); else false with empty note/reframe.\\n''
    || ''9) options = 2-4 short declarative ANSWERS to your question (not questions; none end with "?" or start with What/How/Why/When/Who); distinct; cite a data figure where relevant.\\n''
    || ''Reply ONLY compact JSON, no prose or fences: ''
    || ''{"coverage":{"business_goal":0,"stakeholders":0,"current_workflow":0,"frequency":0,"success_metrics":0,"constraints":0,"assumptions":0,"alternatives":0},''
    || ''"confidence":0,"stop":false,"already_exists":false,"existing_note":"","working_problem":"...","data_insight":"...","adjustment":{"needed":false,"note":"","reframe":""},"question":"...","why":"...","options":["..."],"detected":[]}'';
  raw := (SELECT AI_COMPLETE(:mdl, :prompt));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  res := TRY_PARSE_JSON(:cleaned);
  IF (:hint <> '''' AND res IS NOT NULL) THEN
    res := OBJECT_INSERT(res, ''adjustment'', OBJECT_CONSTRUCT(''needed'', TRUE, ''note'', :hint, ''reframe'', ''''), TRUE);
  END IF;
  RETURN res;
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT_V2("P_STATE" VARCHAR, "P_EVIDENCE" VARCHAR, "P_SIGNAL" VARCHAR, "P_ASKED" NUMBER(38,0))
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE raw STRING; cleaned STRING; prompt STRING; mdl STRING; hint STRING; res VARIANT;
BEGIN
  mdl := (SELECT PM_MEDIATOR.DISCOVERY.MODEL());
  hint := (SELECT PM_MEDIATOR.DISCOVERY.CONTRADICTION_HINT(:P_STATE));
  prompt := ''You are a Senior PM running product discovery. Reply ONLY compact JSON, no prose or fences.\\n''
    || ''STATE (idea, focus, working problem, latest answer, established facts by dimension, prior coverage, questions already asked):\\n'' || :P_STATE || ''\\n''
    || ''CODE/DOCS EVIDENCE (real, cited - use for current workflow; never ask how the system works):\\n'' || :P_EVIDENCE || ''\\n''
    || ''LIVE DATA (real, topic-scoped; may include a DATA GAP):\\n'' || :P_SIGNAL || ''\\n''
    || ''asked='' || TO_VARCHAR(:P_ASKED) || (CASE WHEN :hint <> '''' THEN ''\\nCONTRADICTION DETECTED: '' || :hint ELSE '''' END) || ''\\n''
    || ''RULES: ''
    || ''(1) Investigate the underlying problem, not the literal request. ''
    || ''(2) data_insight MUST include a concrete figure from LIVE DATA; if a relevant DATA GAP is present, also state plainly that the metric cannot be measured from current data (still keep a real number); never invent numbers; mention returns/refunds only if the topic is returns/refunds/exchanges. ''
    || ''(3) If the capability already exists in the code, set already_exists=true and existing_note citing it, and make the question probe the remaining GAP (discoverability, correctness, workflow fit, eligibility, adoption); never tell the user to stop. ''
    || ''(4) Ask exactly ONE new question on the lowest-covered dimension; never repeat a question already asked in STATE. ''
    || ''(5) options = 2-4 short declarative ANSWERS (not questions; none end with "?" or start with What/How/Why/When/Who). ''
    || ''(6) Score all 8 coverage dimensions 0-100; confidence = rounded average; stop=true only if confidence>=78 or asked>=8. ''
    || ''(7) adjustment.needed=true ONLY for a genuine contradiction (if CONTRADICTION DETECTED above, set it true and reconcile in the note); otherwise false with empty note. ''
    || ''JSON schema: {"coverage":{"business_goal":0,"stakeholders":0,"current_workflow":0,"frequency":0,"success_metrics":0,"constraints":0,"assumptions":0,"alternatives":0},"confidence":0,"stop":false,"already_exists":false,"existing_note":"","working_problem":"...","data_insight":"...","adjustment":{"needed":false,"note":"","reframe":""},"question":"...","why":"...","options":["..."],"detected":[]}'';
  raw := (SELECT AI_COMPLETE(:mdl, :prompt));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  res := TRY_PARSE_JSON(:cleaned);
  IF (:hint <> '''' AND res IS NOT NULL) THEN
    res := OBJECT_INSERT(res, ''adjustment'', OBJECT_CONSTRUCT(''needed'', TRUE, ''note'', :hint, ''reframe'', ''''), TRUE);
  END IF;
  RETURN res;
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.GENERATE_PRD("P_SESSION" VARCHAR, "P_TOPIC" VARCHAR, "P_EVIDENCE" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE md STRING; prompt STRING; sig STRING;
BEGIN
  sig := ''n/a'';
  BEGIN sig := (SELECT PM_MEDIATOR.DISCOVERY.DATA_SIGNALS(:P_TOPIC)); EXCEPTION WHEN OTHER THEN sig := ''n/a''; END;
  prompt := ''You are a senior product manager writing a complete, engineering-ready PRD in GitHub-flavored Markdown for THIS request: "'' || :P_TOPIC || ''". ''
    || ''Ground everything ONLY in the discovery context, code/doc evidence, and real data below. Cite evidence inline (reference the file/doc names given). Do NOT invent facts and do NOT introduce unrelated topics or metrics (no refunds unless the request is about refunds). If needed data is missing, list it under Open Questions rather than guessing. ''
    || ''Write a thorough but tight PRD (~500-800 words) with EXACTLY these sections and markdown headings: ''
    || ''# <concise product title>\\\\n## 1. Summary\\\\n## 2. Problem & Context\\\\n## 3. Goals & Non-Goals\\\\n## 4. Target Users & Personas\\\\n## 5. Current State (from the codebase)\\\\n## 6. Proposed Solution\\\\n## 7. Functional Requirements (numbered, testable)\\\\n## 8. UX Notes\\\\n## 9. Data & Success Metrics\\\\n## 10. Dependencies & Risks\\\\n## 11. Acceptance Criteria (Given/When/Then)\\\\n## 12. Rollout & Milestones\\\\n## 13. Open Questions\\\\n\\\\n''
    || ''DISCOVERY CONTEXT & EVIDENCE:\\\\n'' || :P_EVIDENCE || ''\\\\n\\\\nREAL DATA SIGNALS:\\\\n'' || :sig;
  md := (SELECT AI_COMPLETE(''mistral-large2'', :prompt));
  DELETE FROM PM_MEDIATOR.DISCOVERY.PRD WHERE SESSION_ID = :P_SESSION;
  INSERT INTO PM_MEDIATOR.DISCOVERY.PRD (SESSION_ID, MARKDOWN) VALUES (:P_SESSION, :md);
  RETURN :md;
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.GENERATE_WIREFRAME("P_TOPIC" VARCHAR, "P_EXISTING" VARCHAR, "P_PROPOSED" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE html STRING; prompt STRING;
BEGIN
  prompt := ''Generate a single self-contained HTML snippet (no external CSS/JS) showing a side-by-side comparison for "'' || :P_TOPIC ||
    ''". Two columns: left titled "Existing" describing: '' || :P_EXISTING || ''  ; right titled "Proposed" describing: '' || :P_PROPOSED ||
    ''. Use simple inline-styled divs, clear headings, and a few mock UI boxes per side. Return ONLY the HTML, no explanation.'';
  html := (SELECT AI_COMPLETE(''mistral-large2'', :prompt));
  RETURN :html;
END';
CREATE OR REPLACE FUNCTION PM_MEDIATOR.DISCOVERY.MODEL()
RETURNS VARCHAR
LANGUAGE SQL
AS ' ''mistral-large2'' ';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.PROPOSE_FEATURE("P_TOPIC" VARCHAR, "P_ASK" VARCHAR, "P_EVIDENCE" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE raw STRING; cleaned STRING;
BEGIN
  raw := (SELECT AI_COMPLETE(''mistral-large2'',
    ''For the storefront request: '' || :P_ASK || '' (topic='' || :P_TOPIC ||
    ''), propose ONE concrete UI feature to add to the product/order page, grounded in this evidence: '' || :P_EVIDENCE ||
    ''. Reply ONLY JSON: {"title":"<=4 words","desc":"one sentence","cta":"<=3 words"}.''));
  cleaned := REGEXP_SUBSTR(:raw, ''\\\\{.*\\\\}'', 1, 1, ''s'');
  RETURN TRY_PARSE_JSON(:cleaned);
END';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.QUANTIFY_IMPACT("P_TOPIC" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE
  orders INT; returns INT; rate FLOAT; refund_total FLOAT; reasons VARIANT;
  metrics VARIANT; breakdown VARIANT; blabel STRING; t STRING;
  pcount INT; vcount INT; avgp FLOAT; completed INT; aov FLOAT;
BEGIN
  t := LOWER(:P_TOPIC);
  SELECT COUNT(*) INTO :orders FROM PM_MEDIATOR.MOCK.ORDERS;
  SELECT COUNT(*) INTO :returns FROM PM_MEDIATOR.MOCK."RETURN";
  rate := ROUND(100.0*:returns/NULLIF(:orders,0),1);
  SELECT COALESCE(SUM(AMOUNT),0) INTO :refund_total FROM PM_MEDIATOR.MOCK.REFUND;
  SELECT ARRAY_AGG(OBJECT_CONSTRUCT(''reason'',reason,''n'',n,''val'',val)) WITHIN GROUP (ORDER BY val DESC)
    INTO :reasons FROM (SELECT rr.LABEL reason, COUNT(*) n, ROUND(SUM(r.REFUND_AMOUNT),2) val
       FROM PM_MEDIATOR.MOCK.RETURN_ITEM ri JOIN PM_MEDIATOR.MOCK.RETURN_REASON rr ON rr.ID=ri.REASON_ID
       JOIN PM_MEDIATOR.MOCK."RETURN" r ON r.ID=ri.RETURN_ID GROUP BY 1);

  IF (t IN (''refund'',''return'',''exchange'')) THEN
    metrics := ARRAY_CONSTRUCT(
      OBJECT_CONSTRUCT(''label'',''Return rate'',''value'', :rate||''%''),
      OBJECT_CONSTRUCT(''label'',''Returns'',''value'', :returns),
      OBJECT_CONSTRUCT(''label'',''Refunded'',''value'', ''$''||TO_VARCHAR(ROUND(:refund_total))));
    blabel := ''Refund value by return reason'';
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(''name'',reason,''val'',val)) WITHIN GROUP (ORDER BY val DESC)
      INTO :breakdown FROM (SELECT rr.LABEL reason, ROUND(SUM(r.REFUND_AMOUNT),2) val
        FROM PM_MEDIATOR.MOCK.RETURN_ITEM ri JOIN PM_MEDIATOR.MOCK.RETURN_REASON rr ON rr.ID=ri.REASON_ID
        JOIN PM_MEDIATOR.MOCK."RETURN" r ON r.ID=ri.RETURN_ID GROUP BY 1);
  ELSEIF (t IN (''product'',''inventory'')) THEN
    SELECT COUNT(*) INTO :pcount FROM PM_MEDIATOR.MOCK.PRODUCT;
    SELECT COUNT(*) INTO :vcount FROM PM_MEDIATOR.MOCK.PRODUCT_VARIANT;
    SELECT ROUND(AVG(UNIT_PRICE),2) INTO :avgp FROM PM_MEDIATOR.MOCK.ORDER_LINE_ITEM WHERE UNIT_PRICE IS NOT NULL;
    metrics := ARRAY_CONSTRUCT(
      OBJECT_CONSTRUCT(''label'',''Products'',''value'', :pcount),
      OBJECT_CONSTRUCT(''label'',''Variants'',''value'', :vcount),
      OBJECT_CONSTRUCT(''label'',''Avg price'',''value'', ''$''||TO_VARCHAR(:avgp)));
    blabel := ''Top products by revenue'';
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(''name'',name,''val'',val)) WITHIN GROUP (ORDER BY val DESC)
      INTO :breakdown FROM (SELECT li.PRODUCT_TITLE name, ROUND(SUM(oi.QUANTITY*li.UNIT_PRICE),2) val
        FROM PM_MEDIATOR.MOCK.ORDER_ITEM oi JOIN PM_MEDIATOR.MOCK.ORDER_LINE_ITEM li ON li.ID=oi.ITEM_ID
        WHERE li.PRODUCT_TITLE IS NOT NULL GROUP BY 1 ORDER BY val DESC LIMIT 6);
  ELSE
    SELECT COUNT(*) INTO :completed FROM PM_MEDIATOR.MOCK.ORDERS WHERE STATUS=''completed'';
    SELECT ROUND(SUM(oi.QUANTITY*li.UNIT_PRICE)/NULLIF(COUNT(DISTINCT oi.ORDER_ID),0),2) INTO :aov
      FROM PM_MEDIATOR.MOCK.ORDER_ITEM oi JOIN PM_MEDIATOR.MOCK.ORDER_LINE_ITEM li ON li.ID=oi.ITEM_ID;
    metrics := ARRAY_CONSTRUCT(
      OBJECT_CONSTRUCT(''label'',''Orders'',''value'', :orders),
      OBJECT_CONSTRUCT(''label'',''Completed'',''value'', :completed),
      OBJECT_CONSTRUCT(''label'',''Avg order value'',''value'', ''$''||TO_VARCHAR(:aov)));
    blabel := ''Orders by status'';
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(''name'',status,''val'',c)) WITHIN GROUP (ORDER BY c DESC)
      INTO :breakdown FROM (SELECT STATUS status, COUNT(*) c FROM PM_MEDIATOR.MOCK.ORDERS GROUP BY 1);
  END IF;

  RETURN OBJECT_CONSTRUCT(''topic'',:P_TOPIC,''orders'',:orders,''returns'',:returns,''return_rate_pct'',:rate,
    ''refund_total'',:refund_total,''top_reasons'',:reasons,''metrics'',:metrics,''breakdown'',:breakdown,''breakdown_label'',:blabel);
END';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE("P_QUERY" VARCHAR, "P_LIMIT" NUMBER(38,0), "P_TYPE" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE obj OBJECT; payload STRING; raw STRING;
BEGIN
  -- Build the Cortex Search payload with JSON object functions (safe escaping) - never string-concat user text.
  obj := OBJECT_CONSTRUCT(
           ''query'', :P_QUERY,
           ''columns'', ARRAY_CONSTRUCT(''ARTIFACT_TYPE'',''TITLE'',''URL'',''LINE_START'',''LINE_END'',''CONTENT''),
           ''limit'', :P_LIMIT);
  IF (COALESCE(:P_TYPE,'''') <> '''') THEN
    obj := OBJECT_INSERT(:obj, ''filter'', OBJECT_CONSTRUCT(''@eq'', OBJECT_CONSTRUCT(''ARTIFACT_TYPE'', :P_TYPE)), TRUE);
  END IF;
  payload := TO_JSON(:obj);
  SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(''PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH'', :payload) INTO :raw;
  RETURN TRY_PARSE_JSON(:raw);
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.SAVE_DISCOVERY_ARTIFACTS("P_SID" VARCHAR, "P_ARTS" VARIANT)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS '
BEGIN
  DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=:P_SID;
  INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT (SESSION_ID, ARTIFACT_TYPE, CONTENT, UPDATED_AT)
    SELECT :P_SID, f.key,
           CASE WHEN IS_VARCHAR(f.value) THEN f.value::string ELSE TO_JSON(f.value) END,
           CURRENT_TIMESTAMP()
    FROM LATERAL FLATTEN(input => :P_ARTS) f;
  RETURN ''ok'';
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.SAVE_DISCOVERY_TURN("P_SID" VARCHAR, "P_SEQ" NUMBER(38,0), "P_Q" VARCHAR, "P_A" VARCHAR, "P_STATUS" VARCHAR, "P_CONF" VARCHAR, "P_IDEA" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS '
BEGIN
  IF (:P_SEQ > 0) THEN
    DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN WHERE SESSION_ID=:P_SID AND SEQ=:P_SEQ;
    INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN (SESSION_ID,SEQ,ROLE,QUESTION,ANSWER)
    VALUES (:P_SID, :P_SEQ, ''qa'', :P_Q, :P_A);
  END IF;
  MERGE INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION t
  USING (SELECT :P_SID AS SID) s ON t.SESSION_ID = s.SID
  WHEN MATCHED THEN UPDATE SET STATUS=:P_STATUS, CONFIDENCE=:P_CONF, UPDATED_AT=CURRENT_TIMESTAMP()
  WHEN NOT MATCHED THEN INSERT (SESSION_ID, ASK_TEXT, STATUS, CONFIDENCE, CREATED_AT, UPDATED_AT)
    VALUES (:P_SID, :P_IDEA, :P_STATUS, :P_CONF, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());
  RETURN ''ok'';
END;
';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.SCORE_OPPORTUNITY("P_TOPIC" VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS 'DECLARE
  demand INT; effort INT; ret_rate FLOAT; refund_total FLOAT;
  imp FLOAT; dem FLOAT; eff FLOAT; score FLOAT;
BEGIN
  SELECT COUNT(*) INTO :demand
    FROM PM_MEDIATOR.KNOWLEDGE.ARTIFACT_CONCEPT ac
    JOIN PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_ARTIFACT a ON a.ARTIFACT_ID = ac.ARTIFACT_ID
    WHERE ac.CONCEPT_ID = :P_TOPIC AND a.ARTIFACT_TYPE = ''issue'';
  SELECT COUNT(*) INTO :effort
    FROM PM_MEDIATOR.KNOWLEDGE.ARTIFACT_CONCEPT ac
    JOIN PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_ARTIFACT a ON a.ARTIFACT_ID = ac.ARTIFACT_ID
    WHERE ac.CONCEPT_ID = :P_TOPIC AND a.ARTIFACT_TYPE = ''code_file'';
  SELECT r.c * 100.0 / NULLIF(o.c, 0) INTO :ret_rate
    FROM (SELECT COUNT(*) c FROM PM_MEDIATOR.MOCK."RETURN") r,
         (SELECT COUNT(*) c FROM PM_MEDIATOR.MOCK.ORDERS) o;
  SELECT COALESCE(SUM(AMOUNT), 0) INTO :refund_total FROM PM_MEDIATOR.MOCK.REFUND;
  imp := LEAST(10, COALESCE(:ret_rate, 0));
  dem := LEAST(10, :demand / 5.0);
  eff := LEAST(10, :effort / 5.0);
  score := ROUND(0.5 * :imp + 0.4 * :dem + 0.1 * (10 - :eff), 1);
  RETURN OBJECT_CONSTRUCT(
    ''topic'', :P_TOPIC,
    ''return_rate_pct'', ROUND(:ret_rate, 1),
    ''refund_total_usd'', :refund_total,
    ''demand_issue_count'', :demand,
    ''effort_code_files'', :effort,
    ''impact_score'', ROUND(:imp, 1),
    ''demand_score'', ROUND(:dem, 1),
    ''effort_score'', ROUND(:eff, 1),
    ''opportunity_score'', :score,
    ''formula'', ''0.5*impact + 0.4*demand + 0.1*(10-effort)'');
END';
CREATE OR REPLACE PROCEDURE PM_MEDIATOR.DISCOVERY.SCORE_RICE("P_TOPIC" VARCHAR, "P_DISC_CONF" NUMBER(38,0))
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS OWNER
AS '
DECLARE
  reach INT; demand INT; effort_files INT; impact FLOAT; conf FLOAT; effort FLOAT; rice FLOAT; t STRING;
  band STRING; reason STRING; reach_band STRING; impact_band STRING; confidence_band STRING; effort_band STRING;
BEGIN
  t := LOWER(:P_TOPIC);
  IF (t IN (''refund'',''return'',''exchange'')) THEN
    SELECT COUNT(*) INTO :reach FROM PM_MEDIATOR.MOCK."RETURN";
  ELSE
    SELECT COUNT(*) INTO :reach FROM PM_MEDIATOR.MOCK.ORDERS;
  END IF;
  SELECT COUNT(*) INTO :demand FROM PM_MEDIATOR.KNOWLEDGE.ARTIFACT_CONCEPT ac
    JOIN PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_ARTIFACT a ON a.ARTIFACT_ID=ac.ARTIFACT_ID
    WHERE ac.CONCEPT_ID=:P_TOPIC AND a.ARTIFACT_TYPE=''issue'';
  SELECT COUNT(*) INTO :effort_files FROM PM_MEDIATOR.KNOWLEDGE.ARTIFACT_CONCEPT ac
    JOIN PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_ARTIFACT a ON a.ARTIFACT_ID=ac.ARTIFACT_ID
    WHERE ac.CONCEPT_ID=:P_TOPIC AND a.ARTIFACT_TYPE=''code_file'';
  IF (:reach >= 1000) THEN impact := 3;
  ELSEIF (:reach >= 300) THEN impact := 2;
  ELSEIF (:reach >= 100) THEN impact := 1;
  ELSEIF (:reach >= 30) THEN impact := 0.5;
  ELSE impact := 0.25;
  END IF;
  -- RICE confidence mirrors discovery confidence when provided (even 0), so the two never contradict.
  IF (:P_DISC_CONF IS NOT NULL) THEN
    conf := LEAST(95, GREATEST(0, :P_DISC_CONF));
  ELSE
    conf := LEAST(95, 50 + :demand*3);
  END IF;
  effort := GREATEST(1, ROUND(:effort_files/3.0, 1));
  rice := ROUND(:reach * :impact * (:conf/100.0) / :effort, 0);
  IF (:rice >= 1500) THEN band := ''Very High priority'';
  ELSEIF (:rice >= 500) THEN band := ''High priority'';
  ELSEIF (:rice >= 100) THEN band := ''Moderate priority'';
  ELSE band := ''Low priority'';
  END IF;
  reach_band := IFF(:reach>=500,''High'',IFF(:reach>=100,''Med'',''Low''));
  impact_band := IFF(:impact>=2,''High'',IFF(:impact>=1,''Med'',''Low''));
  confidence_band := IFF(:conf>=78,''High'',IFF(:conf>=50,''Med'',''Low''));
  effort_band := IFF(:effort<=2,''Low'',IFF(:effort<=4,''Med'',''High''));
  reason := '''';
  IF (:reach >= 500) THEN reason := reason || ''broad reach; '';
  ELSEIF (:reach < 100) THEN reason := reason || ''narrow reach; ''; END IF;
  IF (:impact >= 2) THEN reason := reason || ''high per-user impact; '';
  ELSEIF (:impact <= 0.5) THEN reason := reason || ''low per-user impact; ''; END IF;
  IF (:conf >= 78) THEN reason := reason || ''well understood; '';
  ELSEIF (:conf < 50) THEN reason := reason || ''low confidence (complete more discovery); ''; END IF;
  IF (:effort <= 2) THEN reason := reason || ''low build effort.'';
  ELSEIF (:effort >= 5) THEN reason := reason || ''high build effort.'';
  ELSE reason := reason || ''moderate build effort.''; END IF;
  RETURN OBJECT_CONSTRUCT(''topic'',:P_TOPIC,''reach'',:reach,''impact'',:impact,''confidence_pct'',:conf,
    ''effort_pm'',:effort,''rice'',:rice,''band'',:band,''reason'',:reason,
    ''reach_band'',:reach_band,''impact_band'',:impact_band,''confidence_band'',:confidence_band,''effort_band'',:effort_band,
    ''demand_issues'',:demand,''code_files'',:effort_files,
    ''formula'',''RICE = Reach x Impact x Confidence / Effort'');
END;
';
create or replace streamlit PM_MEDIATOR.DISCOVERY.DISCOVERY_WORKBENCH
	root_location='@PM_MEDIATOR.DISCOVERY.APP_STAGE
	main_file='discovery_app.py'
	query_warehouse='PM_MEDIATOR_WH'
	comment='Nomy Explores - AI Product Discovery Facilitator';