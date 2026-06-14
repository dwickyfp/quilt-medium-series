-- Series 5: k-Means clustering source + result tables.
-- customer_features holds per-customer RFM-style features (pre-aggregated for
-- clarity); customer_cluster is the empty result table the pipeline fills with
-- each customer's assigned cluster id.

CREATE TABLE IF NOT EXISTS public.customer_features (
    user_id          BIGINT PRIMARY KEY,
    recency_days     BIGINT NOT NULL,
    frequency        BIGINT NOT NULL,
    monetary         DOUBLE PRECISION NOT NULL,
    avg_order_value  DOUBLE PRECISION NOT NULL,
    true_profile     TEXT          -- planted ground truth, for interpretation only
);

CREATE TABLE IF NOT EXISTS public.customer_cluster (
    user_id     BIGINT PRIMARY KEY,
    cluster_id  BIGINT
);
