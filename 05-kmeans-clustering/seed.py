#!/usr/bin/env python3
"""Seed customer_features for Series 5 (k-Means clustering).

Generates ~600 customers drawn from 4 latent buying profiles, each with its own
recency / frequency / monetary / avg-order-value ranges. The profile label is
stored in `true_profile` so we can interpret (not supervise) the clusters
k-means discovers. Run after `docker compose up -d --wait`.

    python seed.py
"""
import os
import random

import psycopg2

DSN = os.environ.get(
    "QUILT_DSN",
    "host=127.0.0.1 port=55435 dbname=retail user=quilt password=quilt_demo_pw",
)

# profile: (count, recency_days range, frequency range, monetary range, aov range)
PROFILES = {
    "loyal_whale":   (150, (1, 45),    (18, 30), (8000, 16000), (450, 850)),
    "frequent_small":(160, (1, 40),    (15, 28), (1200, 2600),  (70, 160)),
    "rare_big":      (150, (60, 200),  (1, 4),   (900, 2200),    (500, 1100)),
    "dormant":       (140, (200, 365), (1, 3),   (60, 400),      (40, 180)),
}


def main():
    rng = random.Random(2026)
    rows = []
    uid = 1
    for profile, (n, (rmin, rmax), (fmin, fmax), (mmin, mmax), (amin, amax)) in PROFILES.items():
        for _ in range(n):
            recency = rng.randint(rmin, rmax)
            freq = rng.randint(fmin, fmax)
            monetary = round(rng.uniform(mmin, mmax), 2)
            aov = round(rng.uniform(amin, amax), 2)
            rows.append((uid, recency, freq, monetary, aov, profile))
            uid += 1

    rng.shuffle(rows)

    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE public.customer_features, public.customer_cluster RESTART IDENTITY;")
    args = b",".join(cur.mogrify("(%s,%s,%s,%s,%s,%s)", r) for r in rows)
    cur.execute(
        b"INSERT INTO public.customer_features "
        b"(user_id,recency_days,frequency,monetary,avg_order_value,true_profile) VALUES " + args
    )

    cur.execute("SELECT count(*) FROM public.customer_features;")
    total = cur.fetchone()[0]
    print(f"seeded {total} customers")
    cur.execute(
        "SELECT true_profile, count(*), round(avg(recency_days)) r, "
        "round(avg(frequency)) f, round(avg(monetary)) m, round(avg(avg_order_value)) a "
        "FROM public.customer_features GROUP BY true_profile ORDER BY true_profile;"
    )
    print("profile           n    recency  freq  monetary  aov")
    for p, n, r, f, m, a in cur.fetchall():
        print(f"{p:16} {n:4}   {r:6}  {f:4}  {m:8}  {a:5}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
