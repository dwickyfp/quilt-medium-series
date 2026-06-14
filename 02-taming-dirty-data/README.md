# Series 2 — Taming Dirty Data

A cleaning-and-validation workspace. Real data is messy: blank fields, mixed casing, out-of-range numbers. This pipeline quarantines the bad rows into dead-letter files instead of letting them poison everything downstream.

## Layout

```
02-taming-dirty-data/
├── ARTICLE.md
├── data/orders_dirty.csv          # 300 rows, ~8% blank status, ~6% bad quantity
├── pipelines/clean_orders.json
├── output/                        # clean_orders.parquet (268 rows)
├── dead_letter/                   # missing_status.csv (21), bad_quantity.csv (11)
├── quilt.json
└── repository.json
```

## The pipeline

```
orders_dirty.csv
   → Not-Null (status)        ── reject ──▶ dead_letter/missing_status.csv  (21)
   → Range (quantity 1..1000) ── reject ──▶ dead_letter/bad_quantity.csv    (11)
   → Standardize (status: trim + lowercase)
   → clean_orders.parquet (268)
```

## Run it

**Desktop app:** open this folder, select `clean_orders`, press Run.
**Headless / MCP:** run `pipelines/clean_orders.json`.

## Verify

```bash
duckdb -c "SELECT count(*), string_agg(DISTINCT status, ',') FROM read_parquet('output/clean_orders.parquet');"
-- 268 rows, statuses: paid,pending,cancelled,refunded  (all normalized to lowercase)
wc -l dead_letter/*.csv   # 22 and 12 lines (21 + 11 data rows + headers)
```
