# Series 4 — Customer Segmentation with RFM

A multi-step analytical pipeline: read sales from Postgres, aggregate per user into RFM metrics (Recency, Frequency, Monetary), score each customer into quartiles, label them into segments, and write the result back to Postgres.

## Layout

```
04-rfm-segmentation/
├── ARTICLE.md
├── docker-compose.yml             # Postgres 16 on host port 55434
├── init/01_schema.sql             # sales (source) + user_segment (result)
├── seed.py                        # generates 2025 sales from latent buying profiles
├── pipelines/rfm_segmentation.json
├── quilt.json
└── repository.json
```

## Setup

```bash
docker compose up -d --wait
python3 -m venv .venv && .venv/bin/pip install psycopg2-binary
.venv/bin/python seed.py          # seeds ~9,500 sales across 800 users
```

## Run

Open the workspace and run `rfm_segmentation`, or run the pipeline headlessly. It reads `public.sales`, computes per-user RFM, and writes 795 scored customers to `public.user_segment` (truncate + insert).

## Verify

```bash
docker exec quilt-s4-postgres psql -U quilt -d retail \
  -c "SELECT segment_label, count(*), round(avg(frequency),1) AS avg_freq,
             round(avg(monetary)) AS avg_mon
      FROM public.user_segment GROUP BY segment_label ORDER BY count(*) DESC;"
```

The segments recover the latent buying profiles planted by `seed.py`: `rare_big_basket` (low frequency, high basket), `frequent_small_basket` (high frequency, small basket), `frequent_whale` (high frequency, high monetary), and `standard`.

## Teardown

```bash
docker compose down -v
```
