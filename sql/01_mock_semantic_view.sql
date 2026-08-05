-- MOCK: commerce semantic view COMMERCE_SV (Cortex Analyst).
-- MOCK commerce tables are loaded by load_medusa.py + gen_refunds.py; this file defines the semantic view over them.

create or replace semantic view PM_MEDIATOR.MOCK.COMMERCE_SV
	tables (
		PM_MEDIATOR.MOCK.ORDERS primary key (ID) with synonyms=('orders','sales orders') comment='Customer orders',
		ORDER_ITEMS as PM_MEDIATOR.MOCK.ORDER_ITEM primary key (ID) comment='Order-to-line-item association with quantities',
		LINE_ITEMS as PM_MEDIATOR.MOCK.ORDER_LINE_ITEM primary key (ID) comment='Line item product and unit price',
		RETURNS as PM_MEDIATOR.MOCK.RETURN primary key (ID) with synonyms=('returns') comment='Return requests',
		RETURN_ITEMS as PM_MEDIATOR.MOCK.RETURN_ITEM primary key (ID) comment='Items within a return',
		RETURN_REASONS as PM_MEDIATOR.MOCK.RETURN_REASON primary key (ID) with synonyms=('return reasons') comment='Return reason catalog',
		REFUNDS as PM_MEDIATOR.MOCK.REFUND primary key (ID) with synonyms=('refunds') comment='Processed refunds',
		CUSTOMERS as PM_MEDIATOR.MOCK.CUSTOMER primary key (ID) comment='Customers'
	)
	relationships (
		ORD_TO_CUST as ORDERS(CUSTOMER_ID) references CUSTOMERS(ID),
		OI_TO_LI as ORDER_ITEMS(ITEM_ID) references LINE_ITEMS(ID),
		OI_TO_ORDERS as ORDER_ITEMS(ORDER_ID) references ORDERS(ID),
		RET_TO_ORDERS as RETURNS(ORDER_ID) references ORDERS(ID),
		RI_TO_LI as RETURN_ITEMS(ITEM_ID) references LINE_ITEMS(ID),
		RI_TO_RET as RETURN_ITEMS(RETURN_ID) references RETURNS(ID),
		RI_TO_REASON as RETURN_ITEMS(REASON_ID) references RETURN_REASONS(ID)
	)
	facts (
		ORDER_ITEMS.ITEM_QUANTITY as QUANTITY,
		LINE_ITEMS.UNIT_PRICE as UNIT_PRICE,
		RETURNS.REFUND_AMOUNT_FACT as REFUND_AMOUNT,
		RETURN_ITEMS.RI_QUANTITY as QUANTITY,
		REFUNDS.REFUND_AMOUNT as AMOUNT
	)
	dimensions (
		ORDERS.ORDER_STATUS as STATUS,
		ORDERS.ORDER_DATE as CAST(CREATED_AT AS DATE) with synonyms=('order date'),
		ORDERS.CURRENCY_CODE as CURRENCY_CODE,
		LINE_ITEMS.PRODUCT_TITLE as PRODUCT_TITLE,
		LINE_ITEMS.PRODUCT_TYPE as PRODUCT_TYPE,
		RETURNS.RETURN_STATUS as STATUS with synonyms=('return status'),
		RETURNS.RETURN_DATE as CAST(CREATED_AT AS DATE) with synonyms=('return date'),
		RETURN_REASONS.REASON_LABEL as LABEL with synonyms=('return reason'),
		CUSTOMERS.HAS_ACCOUNT as HAS_ACCOUNT
	)
	metrics (
		ORDERS.ORDER_COUNT as COUNT(DISTINCT orders.ID) comment='Number of orders',
		RETURNS.RETURN_COUNT as COUNT(DISTINCT returns.ID) comment='Number of returns',
		RETURNS.TOTAL_REFUND_AMOUNT as SUM(returns.REFUND_AMOUNT) comment='Total refund amount from returns',
		RETURNS.AVG_REFUND_AMOUNT as AVG(returns.REFUND_AMOUNT) comment='Average refund per return',
		REFUNDS.REFUNDS_PROCESSED_AMOUNT as SUM(refunds.AMOUNT) comment='Total processed refund amount',
		RETURN_ITEMS.RETURNED_QUANTITY as SUM(return_items.QUANTITY) comment='Units returned'
	)
	comment='Commerce and refund analytics for the AI Product Discovery Agent';