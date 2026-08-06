-- Canonical warehouse configuration (single source of truth).
-- load_medusa.py creates the same warehouse with the same settings; keep them in sync.
-- AUTO_SUSPEND is intentionally long so the warehouse stays warm through a live demo.
-- Note: the first (cold) call after a suspend still pays a resume + model warm-up cost;
-- run warmup.py before presenting. A resource monitor caps monthly spend.

CREATE WAREHOUSE IF NOT EXISTS PM_MEDIATOR_WH
  WAREHOUSE_SIZE = XSMALL
  AUTO_SUSPEND = 600          -- seconds; long enough to avoid mid-demo suspend
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- If it already exists, enforce the canonical settings:
ALTER WAREHOUSE PM_MEDIATOR_WH SET AUTO_SUSPEND = 600 AUTO_RESUME = TRUE;

-- Spend guardrail (monthly credit cap; suspends the warehouse at 90%).
CREATE RESOURCE MONITOR IF NOT EXISTS PM_MEDIATOR_GUARD
  WITH CREDIT_QUOTA = 25 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 90 PERCENT DO SUSPEND ON 100 PERCENT DO SUSPEND_IMMEDIATE;
ALTER WAREHOUSE PM_MEDIATOR_WH SET RESOURCE_MONITOR = PM_MEDIATOR_GUARD;
