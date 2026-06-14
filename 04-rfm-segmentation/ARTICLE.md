# Customer Segmentation with RFM in Quilt

*Series 4 of 5 — turning a raw sales table into customer segments a marketing team can act on, entirely inside a visual pipeline.*

## Background

By [Series 3](../03-files-to-warehouse/ARTICLE.md) we had clean orders living in PostgreSQL. That's a milestone, but a `sales` table is not an answer to a business question. "Who are our best customers?" "Which ones are about to churn?" "Who buys often but small, versus rarely but big?" Those questions need the raw transactions rolled up into per-customer metrics and then sorted into groups.

The classic, durable technique for this is **RFM**: score every customer on three axes — **Recency** (how long since their last purchase), **Frequency** (how many orders), and **Monetary** (how much they've spent) — and use those scores to segment them. It's been the backbone of retail analytics for decades because it's simple, explainable, and it works.

This article builds a complete RFM segmentation as a single Quilt pipeline: Postgres in, aggregate, score into quartiles, label, Postgres out.

## Problem

RFM is conceptually simple and operationally fiddly. A correct implementation has to:

1. **Aggregate** thousands of transactions into one row per customer (count orders, sum spend, average basket, find the last purchase date).
2. **Rank** customers into quartiles on each metric — which means a window function (`NTILE`), not a simple `GROUP BY`.
3. **Label** them with business rules that combine those quartiles ("frequent and high-spend → whale", "rare but big basket → ...").
4. **Land** the result in a table other systems can read, re-runnably.

Do this in a notebook and you get a 200-line script that one person understands. Do it in raw SQL and you get a CTE stack that's correct but opaque to anyone who isn't fluent. Either way, the *logic* — the part the business actually cares about, the segment definitions — is buried in code.

And there's a subtle correctness trap: ranking. People reach for `GROUP BY` when they actually need a window function. Quartile scoring is `NTILE(4) OVER (ORDER BY metric)` — it ranks every row against all the others, which is a fundamentally different operation from aggregation. Get that wrong and your segments are garbage.

## Solution

Quilt lets you build the whole thing as a readable left-to-right pipeline where each step is one node:

- **Aggregate** with a Group By node (group by `user_id`, with count/sum/avg/max aggregations).
- **Derive RFM metrics** with Add Column nodes that name the aggregates into `frequency`, `monetary`, `avg_order_value`, and compute `recency_days` from the max sale date.
- **Score into quartiles** with Add Column nodes whose expression is a window function: `NTILE(4) OVER (ORDER BY frequency)`. This is the key move — the quartile is a SQL window expression dropped into a column.
- **Label** with Add Column nodes containing `CASE` expressions that combine the quartiles into segment names and tiers.
- **Write back** to Postgres in truncate-and-insert mode.

The segment rules live in plain `CASE` expressions you can read on the canvas. Changing "what makes a whale" is editing one expression, not refactoring a script.

> Two hard-won notes baked into this pipeline. First, Quilt's NTILE helper compiles to `NTILE(1)` (a no-op) if you use it directly, and the Group By node ignores custom output names (aggregates come back as `count_sale_id`, `sum_amount`, etc.). The fix for both is the same: use **Add Column with an explicit SQL expression** — `NTILE(4) OVER (...)` for quartiles, and a rename-via-expression for the aggregates. Second, the column *order* matters because the Postgres sink maps positionally to the table — so the Add Column nodes are sequenced to build the row in exactly the `user_segment` DDL order, and a Drop Columns node strips the seven helper columns at the end.

## Implementation

### The data

`seed.py` generates a year of 2025 sales for **800 users**, each assigned one of five latent buying profiles — `rare_big`, `frequent_small`, `frequent_whale`, `standard`, `inactive` — with its own orders-per-year and amount-per-order ranges. Those profiles are the **ground truth**: if the RFM pipeline is correct, the segments it discovers should line up with the profiles we planted. The seed produces **9,542 sales** (8,392 paid).

### The pipeline (15 nodes)

```
sales (Postgres)
  → Standardize status (lowercase)
  → Filter status = 'paid'
  → Group By user_id  →  count_sale_id, sum_amount, avg_amount, max_sale_date
  → Add recency_days   = date_diff('day', max_sale_date, DATE '2025-12-31')
  → Add frequency       = count_sale_id
  → Add monetary        = sum_amount
  → Add avg_order_value = avg_amount
  → Add freq_q = NTILE(4) OVER (ORDER BY frequency)
  → Add mon_q  = NTILE(4) OVER (ORDER BY monetary)
  → Add aov_q  = NTILE(4) OVER (ORDER BY avg_order_value)
  → Add segment_label  (CASE on the quartiles)
  → Add tier_flag      (CASE on mon_q)
  → Drop 7 helper columns
  → user_segment (Postgres, truncate + insert)
```

The two business-rule expressions:

```sql
-- segment_label
CASE WHEN freq_q <= 2 AND aov_q >= 3 THEN 'rare_big_basket'
     WHEN freq_q >= 3 AND mon_q  = 4 THEN 'frequent_whale'
     WHEN freq_q >= 3 AND aov_q <= 2 THEN 'frequent_small_basket'
     ELSE 'standard' END

-- tier_flag
CASE WHEN mon_q = 4 THEN 'gold'
     WHEN mon_q >= 2 THEN 'silver'
     ELSE 'brown' END
```

## Result

Running the pipeline through the Quilt engine: **9,542 sales → 795 segmented customers** (800 users minus a handful whose only sales were non-paid) written to `user_segment`, end to end in **1.6 seconds**.

Verifying the result directly in Postgres — and, crucially, checking the discovered segments against the planted ground truth:

```sql
SELECT segment_label, count(*),
       round(avg(frequency),1) AS avg_freq,
       round(avg(monetary))     AS avg_mon,
       round(avg(avg_order_value)) AS avg_aov
FROM public.user_segment GROUP BY segment_label ORDER BY count(*) DESC;
```

| segment_label | count | avg_freq | avg_mon | avg_aov |
|---|---|---|---|---|
| rare_big_basket | 232 | 3.2 | 1,822 | **722** |
| frequent_small_basket | 218 | **17.6** | 1,999 | 119 |
| standard | 187 | 3.8 | 748 | 174 |
| frequent_whale | 158 | 19.5 | **11,406** | 601 |

Read those averages and the segments are exactly what the names promise. `rare_big_basket`: low frequency (3.2 orders) but high average basket (722). `frequent_small_basket`: high frequency (17.6 orders) and tiny baskets (119). `frequent_whale`: high frequency *and* huge total spend (11,406). The RFM scoring recovered the latent buying profiles `seed.py` planted — which is the real test that the pipeline is correct, not just that it ran.

Tier distribution lines up too: `gold` 198, `silver` 398, `brown` 199 — close to the 25/50/25 split you'd expect from monetary quartiles (gold = top quartile, silver = middle two, brown = bottom).

## Conclusion

RFM is a great example of the kind of work Quilt is built for: not a one-liner, not a distributed batch job, but a real multi-step analytical transformation that's easy to get subtly wrong. Building it as a pipeline makes the moving parts visible — you can see the aggregation, the quartile scoring, and the labeling as distinct, readable steps, and the segment definitions live in `CASE` expressions a stakeholder can actually review.

The validation that mattered here wasn't "did it run" — it was that the segments matched the buying profiles we planted. That's the difference between a pipeline that executes and a pipeline that's correct.

In the final article we go one step further: instead of scoring customers with rules we wrote, we let Quilt's in-engine machine-learning nodes *learn* a churn model from this same customer data — training a classifier, predicting on held-out customers, and scoring them, all without leaving the pipeline.

---

*Workspace: [`04-rfm-segmentation`](.) in [quilt-medium-series](https://github.com/dwickyfp/quilt-medium-series). `docker compose up -d --wait`, `python seed.py`, then run `rfm_segmentation` and query `public.user_segment`.*
