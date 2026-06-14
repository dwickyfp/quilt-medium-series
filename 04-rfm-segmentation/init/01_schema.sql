-- Series 4: RFM segmentation source + result tables.
-- A single sales table drives the whole pipeline; user_segment is the
-- empty result table the pipeline fills (truncate + insert each run).

CREATE TABLE IF NOT EXISTS public.sales (
    sale_id    BIGINT PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    sale_date  DATE NOT NULL,
    amount     DOUBLE PRECISION NOT NULL,
    status     TEXT
);

CREATE TABLE IF NOT EXISTS public.user_segment (
    user_id          BIGINT PRIMARY KEY,
    recency_days     BIGINT,
    frequency        BIGINT,
    monetary         DOUBLE PRECISION,
    avg_order_value  DOUBLE PRECISION,
    segment_label    TEXT,
    tier_flag        TEXT
);
