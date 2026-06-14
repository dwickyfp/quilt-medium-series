-- Target warehouse table for Series 3.
-- order_id is the natural key the upsert pipeline conflicts on, so re-running
-- the load never creates duplicates.
CREATE TABLE IF NOT EXISTS public.orders (
    order_id    BIGINT PRIMARY KEY,
    order_date  DATE,
    product     TEXT,
    quantity    BIGINT,
    unit_price  DOUBLE PRECISION,
    amount      DOUBLE PRECISION,
    status      TEXT
);
