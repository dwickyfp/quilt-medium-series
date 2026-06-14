# Taming Dirty Data: Validation and Dead-Letter Queues in Quilt

*Series 2 of 5 — turning messy input into trustworthy output without losing the evidence.*

## Background

In [the first article](../01-meet-quilt/ARTICLE.md) we built a clean three-node pipeline: read a CSV, filter it, write Parquet. The data was tidy on purpose. Real data never is.

Open any production CSV and you find the same things: a status column where someone typed `PAID`, `Paid`, and ` paid ` for the same concept; rows where the status is just blank; a quantity of `-3` or `99999` that should never have made it past a form. These are not exotic edge cases. They are the default state of data that came from humans, legacy systems, or three different upstream teams who never agreed on a convention.

This article is about what Quilt does when the data fights back.

## Problem

The naive instinct is to clean inline and move on — lowercase everything, drop the nulls, clamp the numbers. That works until someone asks the question every data pipeline eventually faces: *"Wait, we processed 300 orders yesterday but only 268 showed up in the report. Where did the other 32 go?"*

If your cleaning step silently dropped them, you have no answer. The rows are gone. You cannot tell whether they were genuinely invalid or whether your filter had a bug that quietly deleted good data. Silent data loss is worse than a crash, because nobody notices until a number is wrong downstream and trust is already broken.

There are really two problems tangled together:

1. **Validation** — deciding which rows are acceptable (status present, quantity in a sane range) and which are not.
2. **Accountability** — when a row is rejected, keeping it somewhere you can inspect, count, and explain, instead of dropping it into the void.

A good pipeline does both. It lets the clean rows through *and* it keeps an auditable record of everything it threw out and why.

## Solution

Quilt's validation nodes are built around a **reject port**. A validator like Not-Null or Range Check splits its input into two streams: rows that pass continue on the main port, and rows that fail leave through the reject port. You decide where each stream goes.

That design makes accountability the natural path rather than the extra-effort path. You wire each reject port to a **Dead Letter Queue** — a terminal node that writes the rejected rows to a file (CSV, JSON, or Parquet). Now the failures are not lost; they are sitting in a file you can open, count, and hand back to whoever owns the upstream system.

For the messy-but-not-invalid cases — the `PAID` vs ` paid ` casing chaos — we don't reject at all. We **standardize**: trim the whitespace, collapse internal spaces, and lowercase. Those rows are fine; they just need normalizing so that `GROUP BY status` later doesn't treat `paid` and `PAID` as two different things.

The approach in one sentence: **reject what is invalid (and keep the evidence), normalize what is merely messy.**

## Implementation

The workspace ships 300 synthetic orders with deliberate dirt planted in them: roughly 8% have a blank status, roughly 6% have a quantity that is zero, negative, or absurdly large (`99999`), and the status column is a mess of casing and padding (`PAID`, ` paid `, `Paid`, `PENDING `).

The pipeline is a single source feeding a validation chain, with two reject branches peeling off into dead-letter files:

```
orders_dirty.csv (300)
   │
   ├─ Not-Null Check (status) ──── reject ──▶ dead_letter/missing_status.csv
   │
   ├─ Range Check (quantity 1..1000) ── reject ──▶ dead_letter/bad_quantity.csv
   │
   ├─ Standardize (status: trim + collapse + lowercase)
   │
   └─▶ clean_orders.parquet
```

Three node configurations matter:

**Not-Null Check** — `columns: ["status"]`, `onFail: "reject"`. Any row with a null/blank status leaves through the reject port. (The other `onFail` options are `warn`, which keeps the row and logs, and `fail`, which aborts the whole run — useful when a null should never happen.)

**Range Check** — `column: "quantity"`, `min: 1`, `max: 1000`, `inclusive: true`, `onFail: "reject"`. Quantities outside `[1, 1000]` get rejected. This catches both the zeros/negatives and the `99999` fat-finger.

**Standardize** — `columns: ["status"]`, `trim: true`, `collapseWhitespace: true`, `case: "lower"`. This runs *after* validation, on the rows that survived, turning ` paid `, `PAID`, and `Paid` all into `paid`.

> One practical note: Standardize offers a "Title Case" option, but the bundled DuckDB build doesn't ship the `INITCAP` function it compiles to, so title-casing fails at run time. Stick to `lower` or `upper`. This is exactly the kind of thing you only learn by running the pipeline, not by reading the form — which is why every pipeline in this series was executed, not just drawn.

Each reject port is wired to a **Dead Letter Queue** node writing CSV. The clean stream lands in Parquet.

## Result

Running the pipeline through the Quilt engine on DuckDB:

| Node | Rows in → out | Note |
|------|---------------|------|
| `orders_dirty.csv` | → 300 | raw input |
| Not-Null (status) | 300 → 279 | **21 → missing_status.csv** |
| Range (quantity) | 279 → 268 | **11 → bad_quantity.csv** |
| Standardize (status) | 268 → 268 | normalizes casing, drops no rows |
| `clean_orders.parquet` | 268 written | the clean output |

**Total: 414 ms.** And critically, the arithmetic closes: `300 = 268 clean + 21 missing-status + 11 bad-quantity`. Nothing vanished.

Verifying the outputs directly rather than trusting the run summary:

```bash
$ duckdb -c "SELECT count(*) AS rows, string_agg(DISTINCT status, ',') AS statuses
             FROM read_parquet('output/clean_orders.parquet');"
┌──────┬─────────────────────────────────┐
│ rows │            statuses             │
├──────┼─────────────────────────────────┤
│ 268  │ paid,pending,cancelled,refunded │
└──────┴─────────────────────────────────┘

$ wc -l dead_letter/*.csv
  12 dead_letter/bad_quantity.csv     # 11 rows + header
  22 dead_letter/missing_status.csv   # 21 rows + header
```

Two things to notice. First, the clean output has exactly four distinct statuses, all lowercase — the casing chaos (`PAID`, ` paid `, `Paid`) collapsed into a single `paid`. Standardize did its job. Second, the rejected rows are not gone; they are sitting in two CSV files you can open, count, and send back upstream with a note that says "fix your quantity validation."

That is the difference between a pipeline you can defend and one you just hope is right.

## Conclusion

Cleaning data is the easy half. The hard half — the half that earns trust — is being able to account for every row you didn't let through.

Quilt's reject-port-plus-dead-letter pattern makes that the default shape of a pipeline rather than something you have to remember to bolt on. Validators split clean from dirty, dead-letter queues preserve the dirty, and standardization handles the rows that were never really wrong, just inconsistent. When someone asks where the missing 32 orders went, you open two CSV files and answer in ten seconds.

So far everything has started and ended in files. In the next article we point the output at something that outlives a folder: we stand up PostgreSQL with Docker Compose and load these clean orders into a real warehouse table — including the upsert pattern that lets you re-run the pipeline without creating duplicates.

---

*Workspace: [`02-taming-dirty-data`](.) in [quilt-medium-series](https://github.com/dwickyfp/quilt-medium-series). Run `pipelines/clean_orders.json` and inspect `output/` and `dead_letter/`.*
