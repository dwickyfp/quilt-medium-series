# Series 5 — Customer Clustering with k-Means

An unsupervised machine-learning pipeline: read per-customer RFM features from Postgres, standardize them, fit a **k-Means clustering model in the engine**, assign every customer a cluster, and write the result back to Postgres. No labels, no rules — the algorithm discovers the segments.

## Layout

```
05-kmeans-clustering/
├── ARTICLE.md
├── docker-compose.yml             # Postgres 16 on host port 55435
├── init/01_schema.sql             # customer_features (source) + customer_cluster (result)
├── seed.py                        # 600 customers from 4 latent buying profiles
├── pipelines/kmeans_clustering.json
├── quilt.json
└── repository.json
```

## Setup

```bash
docker compose up -d --wait
python3 -m venv .venv && .venv/bin/pip install psycopg2-binary
.venv/bin/python seed.py          # seeds 600 customers
```

## Run

Open the workspace and run `kmeans_clustering`, or run the pipeline headlessly. It reads `public.customer_features`, z-scores the four RFM features, trains k-Means (k=4), assigns each customer a cluster, and writes 600 rows to `public.customer_cluster`.

## The pipeline

```
customer_features (Postgres)
   → Z-Score recency / frequency / monetary / avg_order_value   (4 nodes)
   → k-Means Learner (k=4)  ──model──┐
   → Predictor (main) ◄──────────────┘  → appends cluster_id
   → Drop helper columns (keep user_id + cluster_id)
   → customer_cluster (Postgres, truncate + insert)
```

## Verify

The seed plants 4 latent profiles (`true_profile`). A correct clustering recovers them:

```bash
docker exec quilt-s5-postgres psql -U quilt -d retail -c "
  SELECT cf.true_profile, cc.cluster_id, count(*)
  FROM public.customer_cluster cc JOIN public.customer_features cf USING(user_id)
  GROUP BY 1,2 ORDER BY 1,2;"
```

Each true profile maps cleanly to a single cluster (perfect separation on this synthetic data): dormant→1, frequent_small→0, loyal_whale→2, rare_big→3.

## Teardown

```bash
docker compose down -v
```
