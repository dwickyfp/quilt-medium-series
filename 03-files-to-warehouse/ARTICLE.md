# From Files to a Warehouse: Loading PostgreSQL with Quilt

*Series 3 of 5 — moving from throwaway files to a database that other systems can query, without creating duplicates on every re-run.*

## Background

The first two articles kept everything in files. We read a CSV, filtered it, cleaned it, and wrote Parquet. Files are a great place to *land* data, but they are a poor place to *serve* it. A dashboard cannot query a Parquet file sitting on your laptop. A web app cannot join against a folder. Sooner or later the clean data has to live somewhere a real system can reach it — and for most teams that somewhere is a relational database.

This article makes that jump. We stand up PostgreSQL with Docker Compose and load order batches into a real table. The interesting part is not the insert — anyone can insert. The interesting part is what happens the *second* time you run the load.

## Problem

Loading data into a database once is trivial. Loading it repeatedly, correctly, is where pipelines quietly break.

Real ingestion is rarely a single clean shot. You get yesterday's batch, then today's batch, and today's batch includes some of the same orders (their status changed from `pending` to `paid`) plus some genuinely new ones. If your load just does `INSERT`, the second run either explodes on a primary-key violation or — worse, if there's no key — silently doubles your rows. Now your revenue total is wrong and nobody knows why.

The naive fixes are all bad:

- **Truncate-and-reload** throws away history and only works if every run sees the complete dataset. It doesn't scale and it's dangerous if today's extract is partial.
- **Insert-and-pray** creates duplicates the moment any key reappears.
- **Hand-written `INSERT ... ON CONFLICT`** works, but now your "pipeline" is a SQL script someone has to maintain, and the conflict logic is invisible to anyone reading the data flow.

What you actually want is an **idempotent** load: running it twice with overlapping data leaves the table in the same correct state as running it once with the union. Update the rows that already exist, insert the ones that don't, and never duplicate.

## Solution

Quilt's PostgreSQL sink has an **upsert** mode built in. You give it a set of conflict columns — the natural key — and it generates the `INSERT ... ON CONFLICT (key) DO UPDATE` for you. Existing rows get updated, new rows get inserted, and the operation is idempotent by construction.

That turns "load data into Postgres" from a SQL-maintenance task into a single node property. The data flow stays readable on the canvas (CSV → Postgres), and the tricky correctness logic — the conflict handling — is declared, not hand-written.

For infrastructure, we use Docker Compose. The database is a disposable, reproducible container: anyone who clones the repo runs `docker compose up` and has the exact same Postgres the pipeline was tested against. No "works on my machine," no shared dev database to corrupt.

## Implementation

### The database

`docker-compose.yml` brings up Postgres 16 on host port `55433` (off the default 5432 so it won't collide with a local install), with an init script that creates the target table:

```sql
CREATE TABLE IF NOT EXISTS public.orders (
    order_id    BIGINT PRIMARY KEY,   -- the upsert conflict key
    order_date  DATE,
    product     TEXT,
    quantity    BIGINT,
    unit_price  DOUBLE PRECISION,
    amount      DOUBLE PRECISION,
    status      TEXT
);
```

```bash
docker compose up -d --wait
```

The `order_id` primary key is what makes the upsert safe — it's the natural key Postgres conflicts on.

### The data: two overlapping batches

- **`orders_batch1.csv`** — 250 orders, ids `3000–3249`.
- **`orders_batch2.csv`** — 150 orders, ids `3200–3349`. The first 50 (`3200–3249`) overlap batch 1 and have all been flipped to `refunded`; the remaining 100 (`3250–3349`) are brand new.

This is the realistic shape: a later batch that *corrects* some earlier rows and *adds* others.

### The pipelines

Two pipelines, both two nodes (CSV → Postgres sink). The sink configuration is the whole point:

```json
{
  "componentId": "snk.postgres",
  "properties": {
    "host": "127.0.0.1", "port": 55433,
    "database": "warehouse", "username": "quilt", "password": "quilt_demo_pw",
    "schemaName": "public", "tableName": "orders",
    "mode": "upsert",
    "conflictColumns": ["order_id"]
  }
}
```

`load_batch1` does the initial load. `load_batch2_upsert` loads the overlapping batch in the same upsert mode. Because the mode is upsert with `order_id` as the conflict key, the second run *updates* the 50 overlapping orders and *inserts* the 100 new ones.

> A note on credentials: the demo password sits in plain text in both `docker-compose.yml` and the pipeline files. That's deliberate — it's a throwaway local container, not a secret. For real connections, Quilt supports saved connections (a `connectionRef`) so the credential lives in the workspace's Connections folder, not inline in every pipeline.

## Result

Running `load_batch1`, then `load_batch2_upsert`, through the Quilt engine:

| Run | Rows processed | Time |
|-----|----------------|------|
| `load_batch1` (insert 250) | 250 | 583 ms |
| `load_batch2_upsert` (50 update + 100 insert) | 150 | 525 ms |

Then verifying the table state directly in Postgres — not trusting the pipeline's self-reported counts:

```sql
SELECT count(*) FROM public.orders;
-- 350

-- the 50 overlapping ids were UPDATED, not duplicated:
SELECT count(*) FROM public.orders
WHERE order_id BETWEEN 3200 AND 3249 AND status = 'refunded';
-- 50

-- and the proof it's idempotent — zero duplicate keys:
SELECT count(*) FROM (
  SELECT order_id FROM public.orders GROUP BY order_id HAVING count(*) > 1
) d;
-- 0
```

350 rows, exactly the union of the two batches (250 + 100 new). The 50 overlapping orders were updated in place to `refunded`. Zero duplicate keys. That is the definition of a correct, idempotent load: 250 + 150 processed, but 350 — not 400 — rows in the table, because the 50 repeats updated instead of duplicating.

Run `load_batch2_upsert` a third, fourth, tenth time — the table stays at 350. That repeatability is the whole reason upsert exists.

## Conclusion

The leap from files to a database is where data pipelines meet the real world, and it's where idempotency stops being a fancy word and starts being the thing that keeps your row counts honest. Insert-only loads rot the moment data overlaps; truncate-and-reload throws away anything not in the latest extract. Upsert — update what exists, insert what's new, keyed on a natural identifier — is the pattern that survives daily re-runs.

Quilt makes that a property on a sink node rather than a SQL script someone has to own. The canvas still reads as "CSV goes into Postgres," and the correctness lives in `mode: upsert` plus a conflict key. Pair it with a Docker Compose database and the whole thing is reproducible by anyone who clones the repo.

We now have clean data in a real warehouse. In the next article we put it to work: joining multiple source tables and scoring customers with an RFM (Recency, Frequency, Monetary) segmentation — the kind of analytical pipeline that turns raw orders into something a marketing team can actually act on.

---

*Workspace: [`03-files-to-warehouse`](.) in [quilt-medium-series](https://github.com/dwickyfp/quilt-medium-series). `docker compose up -d --wait`, then run the two pipelines and inspect `public.orders`.*
