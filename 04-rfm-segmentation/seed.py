#!/usr/bin/env python3
"""Seed the retail DB for Series 4 (RFM segmentation).

Generates `sales` rows for 2025 driven by latent buying profiles, so the
RFM segments the pipeline finds map back to a known ground truth. Run after
`docker compose up -d --wait`.

    python seed.py
"""
import os
import random
import datetime as dt

import psycopg2

DSN = os.environ.get(
    "QUILT_DSN",
    "host=127.0.0.1 port=55434 dbname=retail user=quilt password=quilt_demo_pw",
)

# Latent profiles: (weight, orders/year range, amount/order range)
PROFILES = {
    "rare_big":       (0.20, (1, 4),   (600, 1400)),
    "frequent_small": (0.25, (15, 30), (40, 180)),
    "frequent_whale": (0.18, (15, 28), (400, 900)),
    "standard":       (0.27, (4, 9),   (120, 320)),
    "inactive":       (0.10, (1, 2),   (50, 200)),
}

N_USERS = 800
YEAR_START = dt.date(2025, 1, 1)
YEAR_END = dt.date(2025, 12, 31)
SPAN_DAYS = (YEAR_END - YEAR_START).days


def pick_profile(rng):
    r = rng.random()
    acc = 0.0
    for name, (w, *_rest) in PROFILES.items():
        acc += w
        if r <= acc:
            return name
    return "standard"


def main():
    rng = random.Random(42)
    users = []
    for uid in range(1, N_USERS + 1):
        users.append((uid, pick_profile(rng)))

    sales = []
    sid = 1
    for uid, profile in users:
        _w, (omin, omax), (amin, amax) = PROFILES[profile]
        n_orders = rng.randint(omin, omax)
        # inactive users only buy early in the year (high recency_days)
        for _ in range(n_orders):
            if profile == "inactive":
                day = rng.randint(0, 60)
            else:
                day = rng.randint(0, SPAN_DAYS)
            sale_date = YEAR_START + dt.timedelta(days=day)
            amount = round(rng.uniform(amin, amax), 2)
            status = "paid" if rng.random() > 0.12 else rng.choice(["pending", "cancelled"])
            sales.append((sid, uid, sale_date, amount, status))
            sid += 1

    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE public.sales, public.user_segment RESTART IDENTITY;")
    args = b",".join(
        cur.mogrify("(%s,%s,%s,%s,%s)", row) for row in sales
    )
    cur.execute(b"INSERT INTO public.sales (sale_id,user_id,sale_date,amount,status) VALUES " + args)

    cur.execute("SELECT count(*), count(DISTINCT user_id) FROM public.sales;")
    total, distinct_users = cur.fetchone()
    cur.execute("SELECT count(*) FROM public.sales WHERE status='paid';")
    paid = cur.fetchone()[0]
    print(f"seeded {total} sales across {distinct_users} users ({paid} paid)")

    # Print ground-truth profile distribution for later spot-checks
    from collections import Counter
    dist = Counter(p for _u, p in users)
    print("profile distribution:", dict(dist))
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
