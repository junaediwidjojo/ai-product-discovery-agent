-- Native Git integration: the medusajs/dtc-starter repo is cloned into Snowflake as a
-- first-class Git repository object and kept fresh by the REFRESH_GIT task. index_code.py
-- reads files straight from this object to build the KNOWLEDGE graph.

CREATE API INTEGRATION IF NOT EXISTS MEDUSA_GIT_API
  API_PROVIDER = GIT_HTTPS_API
  API_ALLOWED_PREFIXES = ('https://github.com/medusajs')
  ENABLED = TRUE;

CREATE OR REPLACE GIT REPOSITORY PM_MEDIATOR.MOCK.DTC_STARTER_REPO
  API_INTEGRATION = MEDUSA_GIT_API
  ORIGIN = 'https://github.com/medusajs/dtc-starter.git';

-- Refresh task (auto-generated DDL):
create or replace task REFRESH_GIT
	warehouse=PM_MEDIATOR_WH
	schedule='USING CRON 0 6 * * 1 UTC'
	COMMENT='Weekly fetch of the dtc-starter Git repository to keep code knowledge fresh'
	as ALTER GIT REPOSITORY PM_MEDIATOR.MOCK.DTC_STARTER_REPO FETCH;