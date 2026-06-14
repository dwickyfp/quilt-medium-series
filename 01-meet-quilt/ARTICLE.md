# Meet Quilt: Local-First Visual ETL That Compiles to SQL

*Series 1 of 5 — an introduction to building data pipelines on your own machine.*

## Background

Most data work starts the same way: a CSV lands in a folder, someone needs a cleaned-up slice of it, and you reach for whatever is closest. A throwaway pandas script. A notebook cell that only you can run. A spreadsheet formula nobody will ever be able to audit. It works once, and then it rots — the script lives on one laptop, the logic lives in someone's head, and six months later nobody remembers why `status == 'paid'` was hardcoded on line 40.

At the other end of the spectrum sit the heavyweight platforms: orchestration servers, cloud warehouses, managed pipeline services. They are powerful and completely overkill when all you want is to reshape a file on your laptop without standing up infrastructure.

[Quilt](https://github.com/dwickyfp/Quilt) sits in the gap. It is a local-first, visual ETL/ELT desktop studio: you draw a pipeline on a canvas, and it compiles that graph to SQL and runs it through [DuckDB](https://duckdb.org) on your own machine. No server, no cloud account, no API key. This first article is the orientation — what Quilt is, why it exists, and what problem it actually solves — and we end by building and running a real pipeline.

## Problem

The tools most of us default to force a bad trade-off.

Hand-written scripts are flexible but opaque. The transformation logic is buried in code, the intermediate state is invisible until you add print statements, and reproducing a run means recreating someone's exact Python environment. Reviewing a change is reading a diff and hoping you understand the data flow.

Heavyweight ETL platforms solve the reproducibility problem but introduce operational weight. You are now running (or paying for) infrastructure to move a few hundred megabytes of data. For a single analyst, a small team, or anyone prototyping, that is a lot of ceremony for not much payoff.

And the "easy" visual tools usually hide the engine. You drag boxes around, but you cannot see the SQL, cannot read the execution plan, and cannot tell whether the thing is doing what you think. When it breaks, you are debugging a black box.

What is missing is a tool that is **visual but not opaque**, **reproducible but not heavy**, and **local but still fast**.

## Solution

Quilt's approach is built on three decisions.

**Compile the canvas to SQL.** Every node you draw becomes a stage of generated SQL you can read. The canvas is a friendly editor on top of a real query engine, not a replacement for it. There is no hidden state — click any node and you see both its generated SQL and a live preview of the rows flowing through it.

**Run on DuckDB, locally.** DuckDB is a vectorized, columnar engine that is genuinely fast on the single-machine analytical workloads most ETL actually is. A clean-and-aggregate job that crawls in a spreadsheet finishes in milliseconds. Nothing leaves your machine.

**Persist everything as plain files.** A workspace is a folder you choose. Pipelines, connections, and context variables are plain JSON in that folder. You can diff them, branch them, and review them in a normal pull request — the same way you treat the rest of your code.

The trade-off Quilt accepts on purpose: it is single-machine and embedded by design. If you outgrow one box, you point Quilt's output at a system that scales — a warehouse, an object store, a lakehouse. It does not pretend to be a distributed cluster, and that honesty is what keeps it simple.

## Implementation

Let's build the smallest pipeline that is still real: read a CSV of orders, keep only the paid ones, and write the result as Parquet.

### The data

The workspace ships with 200 synthetic orders. If you want to regenerate them:

```python
import csv, random
random.seed(1)
statuses = ["paid", "paid", "paid", "pending", "cancelled", "refunded"]
products = ["Keyboard","Mouse","Monitor","Webcam","Headset","Dock","Cable","Stand"]
rows = []
for i in range(1, 201):
    qty = random.randint(1, 5)
    price = round(random.uniform(8, 320), 2)
    rows.append({
        "order_id": 1000 + i,
        "order_date": f"2026-{random.randint(1,6):02d}-{random.randint(1,28):02d}",
        "product": random.choice(products),
        "quantity": qty, "unit_price": price,
        "amount": round(qty * price, 2),
        "status": random.choice(statuses),
    })
with open("data/orders.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
```

That gives a realistic mix — roughly 113 of the 200 rows are `paid`, the rest are pending, cancelled, or refunded.

### The pipeline

Three nodes, wired left to right:

1. **CSV source** → points at `data/orders.csv`, header row on, comma-delimited. Quilt autodetects the schema, so `order_date` comes back as a real `date`, `amount` as `float64`, and so on.
2. **Filter** → a single predicate, `status = 'paid'`. The filter node has a `pass` port (rows that match) and a `reject` port (rows that don't) — here we only wire the `pass` port forward.
3. **Parquet sink** → writes `output/paid_orders.parquet`, overwrite mode, Zstd compression.

The saved pipeline (`pipelines/orders_to_parquet.json`) is just JSON — nodes with a `componentId` and `properties`, plus edges that connect ports:

```json
{
  "nodes": [
    { "id": "s1", "type": "source",
      "data": { "componentId": "src.csv",
                "properties": { "path": "data/orders.csv", "hasHeader": true } } },
    { "id": "t1", "type": "transform",
      "data": { "componentId": "xf.filter",
                "properties": { "predicate": "status = 'paid'" } } },
    { "id": "k1", "type": "sink",
      "data": { "componentId": "snk.parquet",
                "properties": { "path": "output/paid_orders.parquet",
                                "mode": "overwrite", "compression": "zstd" } } }
  ],
  "edges": [
    { "source": "s1", "target": "t1", "sourceHandle": "main", "targetHandle": "main" },
    { "source": "t1", "target": "k1", "sourceHandle": "main", "targetHandle": "main" }
  ]
}
```

The filter predicate is raw SQL. That is the theme of the whole tool: the friendly node is a thin wrapper, and the thing underneath is SQL you can read and reason about.

### Running it

In the desktop app: open this folder as a workspace, select `orders_to_parquet`, press **Run**. The nodes light up in execution order, each showing its row count. Headlessly, you point the Quilt engine at `pipelines/orders_to_parquet.json` and it does the same thing without the UI.

## Result

Here is the actual run, executed through the Quilt engine on DuckDB:

| Node | Kind | Rows in → out | Time |
|------|------|---------------|------|
| `orders.csv` | source | → 200 | 171 ms |
| `Paid only` (filter) | transform | 200 → 113 | 25 ms |
| `paid_orders.parquet` | sink | 113 written | 47 ms |

**Total: 313 ms** for the whole pipeline, end to end, on a laptop.

Verifying the output directly with DuckDB rather than trusting the run summary:

```bash
$ duckdb -c "SELECT count(*) AS rows, count(DISTINCT status) AS statuses,
                    min(status) AS only_status
             FROM read_parquet('output/paid_orders.parquet');"
┌───────┬──────────┬─────────────┐
│ rows  │ statuses │ only_status │
├───────┼──────────┼─────────────┤
│  113  │    1     │    paid     │
└───────┴──────────┴─────────────┘
```

113 rows, exactly one distinct status, and that status is `paid`. The filter did precisely what the canvas said it would, the count matches the data we generated, and the result is a portable Parquet file you can hand to anyone.

That is the whole point: the pipeline is readable (three nodes, one SQL predicate), reproducible (a JSON file in a folder), and fast (sub-second, fully local).

## Conclusion

Quilt is not trying to replace your warehouse or your orchestrator. It is trying to make the everyday data work — read this, clean that, reshape it, write it somewhere useful — fast, visible, and version-controllable, without spinning up infrastructure.

If you have ever written a one-off script to filter a CSV and then lost it, or inherited a notebook nobody can rerun, this is the tool aimed squarely at that pain. You drew a graph, you can read the SQL it generates, the run finished in 313 milliseconds, and the whole thing is a JSON file you can commit.

In the next article we make the data messy on purpose — nulls, mixed casing, malformed values, out-of-range numbers — and use Quilt's validation and cleaning nodes to quarantine the bad rows instead of letting them poison everything downstream.

---

*Workspace for this article: [`01-meet-quilt`](.) in the [quilt-medium-series](https://github.com/dwickyfp/quilt-medium-series) repo. Open the folder in Quilt, or run `pipelines/orders_to_parquet.json` headlessly.*
