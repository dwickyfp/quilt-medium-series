# Customer Clustering with k-Means in Quilt

*Series 5 of 5 — letting an unsupervised model discover customer segments, instead of writing the rules ourselves.*

## Background

[Series 4](../04-rfm-segmentation/ARTICLE.md) segmented customers with RFM, but we wrote the segment definitions by hand: `CASE WHEN freq_q >= 3 AND mon_q = 4 THEN 'frequent_whale'`. That works when you already know the segments you're looking for. But what if you don't? What if the natural groupings in your customer base aren't the ones you'd think to write down?

That is what **clustering** is for. You give an unsupervised algorithm the features — recency, frequency, monetary, average basket — and it finds the groups on its own, with no labels and no rules. The classic algorithm for this is **k-Means**: pick `k`, and it partitions customers into `k` clusters by minimizing the distance between each customer and its cluster's center.

This final article runs k-Means end to end inside a Quilt pipeline — train, predict, write back — and verifies that the clusters it discovers match the customer profiles we planted in the data.

## Problem

Clustering has two traps that catch people who treat it as "just another node."

**Trap one: scale.** k-Means measures distance. If `monetary` ranges 0–16,000 and `recency_days` ranges 0–365, then monetary utterly dominates the distance calculation — recency and frequency barely register. The algorithm effectively clusters on spend alone, and your "four-feature" model is really a one-feature model. The fix is to **standardize** every feature to the same scale (mean 0, standard deviation 1) before fitting.

**Trap two: train/predict separation.** A real ML workflow fits a model on data, then applies that model to assign labels. Those are two distinct steps with a model passed between them. A pipeline tool has to express "this node produces a model; that node consumes it" — a different kind of wiring than the row-in-row-out transforms we've used so far.

And underneath both is the harder question for an article like this: *does the engine actually do real machine learning, or is it faking it with SQL?* If the "clustering" were just `NTILE` quartiles in disguise (as the hand-rolled RFM rules essentially were), calling it k-Means would be dishonest.

## Solution

Quilt ships a real **Machine Learning** node category backed by [`smartcore`](https://smartcorelib.org/), a pure-Rust ML library compiled into the engine. The k-Means Learner genuinely fits a k-means model — iterative centroid assignment, not a SQL trick.

The pipeline expresses the full ML shape:

- **Z-Score** nodes standardize each of the four features. This is the node that defuses trap one — `(value - mean) / stddev` across the column, so all four features carry equal weight.
- **k-Means Learner** (`k=4`) fits the model on the standardized features and emits it on a dedicated **model port** — a different port type than the usual data flow.
- **Predictor** takes two inputs: the customer rows on its `main` port and the trained model on its `model` port. It appends a `cluster_id` to every row. This is trap two solved: the model is a first-class thing that flows from learner to predictor along a typed edge.
- **Drop Columns** + **Postgres sink** keep `user_id` + `cluster_id` and write the assignments back.

That model-port wiring is the part worth seeing on a canvas — it's what makes "train here, apply there" legible instead of buried in a script.

> **An honest aside about how this article got written.** When I first checked, Quilt's MCP automation server reported *no* ML nodes — `ml.learner.kmeans` came back "unknown component." It would have been easy to conclude clustering wasn't supported and write a SQL-flavored substitute. Digging into the engine source told a different story: the k-Means node was fully implemented in Rust (`smartcore::cluster::kmeans`) and marked available in the UI — but the MCP server's embedded component catalog was a stale snapshot exported *before* the ML nodes landed. The node worked; the automation index describing it was out of date. Regenerating the catalog and rebuilding the server surfaced all ten ML nodes. The lesson is the one this whole series runs on: **the engine is the source of truth, and you confirm a capability by running it — not by trusting an index that claims it exists, or claims it doesn't.**

## Implementation

### The data

`seed.py` generates **600 customers** from four latent buying profiles, each with distinct feature ranges:

| Profile | n | recency (days) | frequency | monetary | avg order value |
|---|---|---|---|---|---|
| loyal_whale | 150 | low (1–45) | high (18–30) | very high (8k–16k) | high (450–850) |
| frequent_small | 160 | low (1–40) | high (15–28) | mid (1.2k–2.6k) | low (70–160) |
| rare_big | 150 | high (60–200) | low (1–4) | mid (900–2.2k) | high (500–1100) |
| dormant | 140 | very high (200–365) | low (1–3) | low (60–400) | low (40–180) |

The `true_profile` label is stored only so we can *check* the clustering afterward — k-Means never sees it. It's the ground truth, not an input.

### The pipeline (9 nodes)

```
customer_features (Postgres)
  → Z-Score recency_days   → recency_z
  → Z-Score frequency      → frequency_z
  → Z-Score monetary       → monetary_z
  → Z-Score avg_order_value→ aov_z
  → k-Means Learner (k=4, features = the 4 *_z columns) ──model──┐
  → Predictor (outputColumn = cluster_id) ◄──────────────────────┘
  → Drop Columns (keep user_id, cluster_id)
  → customer_cluster (Postgres, truncate + insert)
```

The Predictor sits on the main data path; the Learner hangs below it, feeding the model port. One graph, both ML steps visible.

## Result

Running the pipeline through the Quilt engine: **600 customers → 600 cluster assignments** written to `customer_cluster` in about 1.5 seconds, including fitting the model.

Then the real test — does k-Means, with no labels, recover the profiles we planted? A crosstab of discovered `cluster_id` against the hidden `true_profile`, queried straight from Postgres:

```sql
SELECT cf.true_profile, cc.cluster_id, count(*)
FROM public.customer_cluster cc
JOIN public.customer_features cf USING (user_id)
GROUP BY 1, 2 ORDER BY 1, 2;
```

| true_profile | cluster_id | count |
|---|---|---|
| dormant | 1 | 140 |
| frequent_small | 0 | 160 |
| loyal_whale | 2 | 150 |
| rare_big | 3 | 150 |

**Perfect separation.** Every one of the 600 customers landed in the single cluster corresponding to its true profile — 140/140 dormant, 160/160 frequent_small, 150/150 loyal_whale, 150/150 rare_big. Zero customers crossed over. (The cluster *numbers* are arbitrary — k-Means doesn't know the profiles are called "dormant" — but the *partition* it found is exactly the one we planted.)

This clean a result is a property of well-separated synthetic data; real customers smear across fuzzy boundaries and you'd see mixing. But that is precisely why the check matters: on data where we *know* the answer, the pipeline got it exactly right, which means the machinery — standardize, fit, predict — is sound. Point it at messier data and you can trust the mechanism even when the clusters are harder to name.

## Conclusion

Clustering is where a data pipeline stops applying rules and starts *discovering structure*. k-Means took four standardized features and, with no labels and no hand-written `CASE` statements, found the same four customer groups we'd built into the data. Quilt expressed the whole thing — standardize, train, predict, persist — as one readable graph, with the trained model flowing along a typed port from learner to predictor.

Two ideas carried this series from the first article to this one. The visual graph keeps even a machine-learning workflow legible: you can see where standardization happens, where the model is fit, where it's applied. And every single pipeline — from the three-node CSV filter in Series 1 to this k-Means model — was *run and verified against real engine output*, not just drawn and described. The row counts were checked, the outputs were queried back from Parquet and PostgreSQL, and when an automation index claimed a node didn't exist, the engine itself settled the question.

That is the whole pitch of local-first, visible ETL: you can see what it does, you can run it yourself, and you can check that it's true.

---

*Workspace: [`05-kmeans-clustering`](.) in [quilt-medium-series](https://github.com/dwickyfp/quilt-medium-series). `docker compose up -d --wait`, `python seed.py`, then run `kmeans_clustering` and query `public.customer_cluster`.*
