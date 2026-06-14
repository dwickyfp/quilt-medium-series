# Series 3 — From Files to a Warehouse

Loads CSV order batches into a real PostgreSQL table using **upsert** mode, so re-running the load never creates duplicates. Postgres runs locally via Docker Compose.

## Layout

```
03-files-to-warehouse/
├── ARTICLE.md
├── docker-compose.yml             # Postgres 16 on host port 55433
├── init/01_schema.sql             # creates public.orders (order_id PRIMARY KEY)
├── data/orders_batch1.csv         # 250 rows, ids 3000..3249
├── data/orders_batch2.csv         # 150 rows, ids 3200..3349 (50 overlap + 100 new)
├── pipelines/load_batch1.json
├── pipelines/load_batch2_upsert.json
├── quilt.json
└── repository.json
```

## Start Postgres

```bash
docker compose up -d --wait
```

Postgres listens on **localhost:55433** (db `warehouse`, user `quilt`, password `quilt_demo_pw` — a throwaway local credential). The init script creates `public.orders` with `order_id` as the primary key.

## Run the loads

1. `load_batch1` — inserts 250 orders (ids 3000–3249).
2. `load_batch2_upsert` — upserts 150 orders (ids 3200–3349): 50 update existing rows (now `refunded`), 100 are new.

Both use the Postgres sink in **upsert** mode with `order_id` as the conflict key.

## Verify

```bash
docker exec quilt-s3-postgres psql -U quilt -d warehouse \
  -c "SELECT count(*) FROM public.orders;" \
  -c "SELECT count(*) FROM (SELECT order_id FROM public.orders GROUP BY order_id HAVING count(*)>1) d;"
-- 350 rows, 0 duplicates
```

## Teardown

```bash
docker compose down          # keep data
docker compose down -v        # wipe the volume too
```
